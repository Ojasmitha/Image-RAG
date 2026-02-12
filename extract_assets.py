import os
import json
from tqdm import tqdm
import asyncio
from langchain_mcp_tools import convert_mcp_to_langchain_tools

#output paths for different stages of this pipeline

OUTPUT_DIR = "output"
FETCHED_ASSETS_PATH = os.path.join(OUTPUT_DIR, "fetched_assets.json")
FILTERED_ASSETS_PATH = os.path.join(OUTPUT_DIR, "FILTERED_assets.json")
UNKNOWN_ASSETS_PATH = os.path.join(OUTPUT_DIR, "unknown_type_assets.json")
MERGED_ASSET_OUTPUT_PATH = os.path.join(OUTPUT_DIR, "assets_extracted.json")
FAILED_ASSET_OUTPUT_PATH = os.path.join(OUTPUT_DIR, "failed_asset_get_tool.json")

# Fetch detailed asset content via the get_asset_contents tool and merge it with invoked asset search metadata

async def fetch_and_merge_asset(data, get_tool):
   name = data.get("name", "unknown_asset")
   fileID = data.get("fileID")
   guid = data.get("guid")


   args = {}
   if guid:
       args["guid"] = guid
   if fileID:
       args["fileID"] = fileID
   if name:
       args["name"] = name
   if not args:
       print(f"Skipping {name} — no GUID or FileID present.")
       return None, {
           "name": name, "guid": guid, "fileID": fileID, "error": "Missing identifiers"
       }


   try:
       print(f"Invoking get_tool with: {args}")
       raw_content = await get_tool.ainvoke(args)


       # Deserialize response
       if isinstance(raw_content, str):
           try:
               content = json.loads(raw_content)
           except json.JSONDecodeError:
               print(f"Invalid JSON from get_tool for {name}")
               return None, {
                   "name": name, "guid": guid, "fileID": fileID, "error": "Invalid JSON"
               }
       elif isinstance(raw_content, dict):
           content = raw_content
       else:
           print(f"Unsupported response type for {name}")
           return None, {
               "name": name, "guid": guid, "fileID": fileID, "error": "Unsupported response"
           }


       merged_data = {**data, **content}
       merged_data["name"] = name
       if guid:
           merged_data["guid"] = guid
       if fileID:
           merged_data["fileID"] = fileID


       return merged_data, None


   except Exception as e:
       return None, {
           "name": name, "guid": guid, "fileID": fileID, "error": str(e)
       }


#configuring unity mcp server endpoints


async def main():
   mcp_servers = {
       "unity": {"url": "http://localhost:5000/sse"}
   }
   all_entries = []
   tools, cleanup = await convert_mcp_to_langchain_tools(mcp_servers)
   search_tool = next(t for t in tools if t.name == "search")
   get_tool = next(t for t in tools if t.name == "get_asset_contents")

   print("Starting paginated asset search...")
   filters = ["t:GameObject", "t:Prefab", "t:Mesh"]
   # filter_type = ["type:UnityEngine.GameObject"]

   all_entries = []
   NUM_PASSES = 1 #define the number of times you want to invoke search
   for current_pass in range(NUM_PASSES):
       print(f"\nStarting search pass {current_pass+1}/{NUM_PASSES}")
       for filter_type in filters:
           cursor = 0
           has_more = True
           total_fetched = 0

           pbar = tqdm(desc=f"Fetching {filter_type} (pass {current_pass+1})", unit="assets")
           while has_more:
               try:
                   response = await search_tool.ainvoke({"filters": filter_type, "cursor": cursor})
                   parsed = json.loads(response) if isinstance(response, str) else response
                   batch = parsed.get("entries", [])

                   if not batch:
                       print(f"Empty batch at cursor {cursor}.")
                       break

                   if current_pass == NUM_PASSES - 1:
                       all_entries.extend(batch)

                   cursor = parsed.get("nextCursor", -1)
                   has_more = parsed.get("hasMore", False)


                   total_fetched += len(batch)
                   pbar.update(len(batch))


                   if cursor == -1:
                       break


               except Exception as e:
                   print(f"Failed at cursor {cursor}: {e}")
                   break


           pbar.close()
           print(f"Done. Total assets fetched in this pass: {total_fetched}")


   # Deduplicate ONLY the last pass entries
   seen_keys = set()
   deduped_final_entries = []


   for entry in all_entries:
       data = entry.get("data", {})
       key = f"{data.get('guid', '')}:{data.get('fileID', '')}:{data.get('name', '')}"
       if key not in seen_keys:
           seen_keys.add(key)
           deduped_final_entries.append(entry)

   # Stats
   total_final_pass = len(all_entries)
   final_deduped_count = len(deduped_final_entries)
   duplicates_removed = total_final_pass - final_deduped_count

   print(f"Deduplicated final pass entries: {final_deduped_count} from {total_final_pass}")
   print(f"Duplicates removed from final pass : {duplicates_removed}")
  
   # Save to file
   os.makedirs(OUTPUT_DIR, exist_ok=True)
   with open(FILTERED_ASSETS_PATH, "w") as f:
       json.dump(deduped_final_entries, f, indent=2)
   print(f"Saved deduplicated fetched assets to {FILTERED_ASSETS_PATH}")

   # Classify known and unknown asset types
   known_assets = []
   unknown_assets = []
   for entry in deduped_final_entries:
       data = entry.get("data", {})
       path = data.get("path", "").lower()
       inferred_type = None
      
       # Heuristics for type inference from path or fields
       if path.endswith(".prefab"):
           inferred_type = "Prefab"
       elif any(path.endswith(ext) for ext in [".mesh", ".fbx"]):
           inferred_type = "Mesh"
       elif data.get("scenePath") or data.get("hierarchyPath"):
           inferred_type = "GameObject"

       if inferred_type:
           known_assets.append(entry)
       else:
           unknown_assets.append(entry)

   with open(FILTERED_ASSETS_PATH, "w") as f:
       json.dump(known_assets, f, indent=2)
   with open(UNKNOWN_ASSETS_PATH, "w") as f:
       json.dump(unknown_assets, f, indent=2)

   print(f"Saved known assets to {FILTERED_ASSETS_PATH}")
   print(f"Saved unknown assets to {UNKNOWN_ASSETS_PATH}")

   # Now read FILTERED assets
   with open(FILTERED_ASSETS_PATH, "r") as f:
      asset_entries = json.load(f)

   merged_assets = []
   get_content_failed_assets = []

   # Create a list of tasks for parallel processing
   tasks = [
       fetch_and_merge_asset(entry.get("data", {}), get_tool)
       for entry in asset_entries
   ]

   # tqdm for better visibility
   for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Fetching Assets"):
       merged_data, error = await coro
       if merged_data:
           merged_assets.append(merged_data)
       if error:
           get_content_failed_assets.append(error)

   if merged_assets:
       os.makedirs(os.path.dirname(MERGED_ASSET_OUTPUT_PATH), exist_ok=True)
       with open(MERGED_ASSET_OUTPUT_PATH, "w") as f_out:
           json.dump(merged_assets, f_out, indent=2)
       print(f"Saved {len(merged_assets)} merged assets to {MERGED_ASSET_OUTPUT_PATH}")

   if get_content_failed_assets:
       os.makedirs(os.path.dirname(FAILED_ASSET_OUTPUT_PATH), exist_ok=True)
       with open(FAILED_ASSET_OUTPUT_PATH, "w") as f:
           json.dump(get_content_failed_assets, f, indent=2)
       print(f"Saved failed assets to {FAILED_ASSET_OUTPUT_PATH}")

   # Clean up tool connections

   await cleanup()


if __name__ == "__main__":
   asyncio.run(main())



