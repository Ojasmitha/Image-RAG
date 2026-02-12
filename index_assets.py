import json
from collections import defaultdict, Counter
import json
import openai
import time
import os

from dotenv import load_dotenv
load_dotenv()


with open("output/assets_extracted.json") as f:
   entries = json.load(f)

seen = set()
unique_entries = []


for entry in entries:
   key = json.dumps(entry, sort_keys=True) 
   if key not in seen:
       seen.add(key)
       unique_entries.append(entry)

# Save the unique entries to a new file
with open("output/unique_assets_extracted.json", "w") as f:
   json.dump(unique_entries, f, indent=2)


print(f"Removed {len(entries) - len(unique_entries)} duplicates.")
print(f"Unique entries saved to unique_assets_extracted.json.")


#Analyse Assets

def get_base_type(type_string):
   """Extracts base type (before comma)."""
   return type_string.split(",")[0].strip() if type_string else "Unknown"

def flatten_fields(d, prefix=''):
   """Yields all keys, including nested ones (with dot notation)."""
   for k, v in d.items():
       if isinstance(v, dict):
           yield from flatten_fields(v, f"{prefix}{k}.")
       else:
           yield f"{prefix}{k}"


with open("output/unique_assets_extracted.json", "r") as infile:
   original_assets = json.load(infile)


type_to_fields = defaultdict(lambda: Counter())
type_to_count = Counter()


for entry in original_assets:
   obj_type = get_base_type(entry.get("type", "Unknown"))
   type_to_count[obj_type] += 1
   fields = set(flatten_fields(entry))
   for field in fields:
       type_to_fields[obj_type][field] += 1


# Print distribution
for obj_type in type_to_count:
   print(f"\nType: {obj_type} ({type_to_count[obj_type]} entries)")
   print("Attributes present and count of entries they appear in:")
   for attr, count in type_to_fields[obj_type].most_common():
       print(f"  {attr}: {count}")


#Flatten Assets

def flatten_gameobject(entry):
   gobj = entry.get("GameObject", {})
   return {
       "asset_type": "GameObject",
       "asset_name": entry.get("name", ""),
       "guid": entry.get("guid", ""),
       "type": entry.get("type", "").split(",")[0].strip(),
       "unity_module": entry.get("type", "").split(",")[1].strip() if "," in entry.get("type", "") else "",
       "file_id": entry.get("fileID", ""),
       "path": entry.get("path", ""),
       "tag": gobj.get("m_TagString", "").lower(),
       "layer": gobj.get("m_Layer", 0),
       "is_active": gobj.get("m_IsActive", False),
       "nav_mesh_layer": gobj.get("m_NavMeshLayer", 0),
       "static_editor_flags": gobj.get("m_StaticEditorFlags", 0),
       "icon_instance_id": gobj.get("m_Icon", {}).get("instanceID", None),
       "summary": (
           f"Prefab '{entry.get('name', '')}' (UnityEngine.GameObject) at {entry.get('path', '')}. "
           f"Active: {gobj.get('m_IsActive', False)}. Tag: {gobj.get('m_TagString', '').lower()}. "
           f"Layer: {gobj.get('m_Layer', 0)}. NavMesh layer: {gobj.get('m_NavMeshLayer', 0)}."
       ),
   }


def flatten_mesh(entry):
   mesh_name = entry.get("name", entry.get("Name", ""))
   return {
       "asset_type": "Mesh",
       "asset_name": mesh_name,
       "guid": entry.get("guid", ""),
       "type": entry.get("type", "").split(",")[0].strip(),
       "file_id": entry.get("fileID", ""),
       "path": entry.get("path", ""),
       "vertex_count": entry.get("VertexCount", None),
       "bounds_center": {
           "x": entry.get("Bounds.Center.x", None),
           "y": entry.get("Bounds.Center.y", None),
           "z": entry.get("Bounds.Center.z", None),
       },
       "bounds_extents": {
           "x": entry.get("Bounds.Extents.x", None),
           "y": entry.get("Bounds.Extents.y", None),
           "z": entry.get("Bounds.Extents.z", None),
       },
       "summary": (
           f"Mesh '{mesh_name}' at {entry.get('path', '')}. "
           f"Vertex count: {entry.get('VertexCount', 'N/A')}. "
           f"Bounds center: ({entry.get('Bounds.Center.x', 'N/A')}, {entry.get('Bounds.Center.y', 'N/A')}, {entry.get('Bounds.Center.z', 'N/A')})."
       ),
   }


def flatten_asset(entry):
   asset_type = get_base_type(entry.get("type", ""))
   if asset_type == "UnityEngine.GameObject":
       return flatten_gameobject(entry)
   elif asset_type == "UnityEngine.Mesh":
       return flatten_mesh(entry)
   else:
       # For other types, include basic info
       return {
           "asset_type": asset_type,
           "asset_name": entry.get("name", entry.get("Name", "")),
           "guid": entry.get("guid", ""),
           "type": asset_type,
           "file_id": entry.get("fileID", ""),
           "path": entry.get("path", ""),
           "summary": f"Asset '{entry.get('name', entry.get('Name', ''))}' of type {asset_type} at {entry.get('path', '')}."
       }


# Now create the RAG-ready assets
rag_ready_assets = [flatten_asset(asset) for asset in original_assets]


with open("output/assets_rag_ready.json", "w") as outfile:
   json.dump(rag_ready_assets, outfile, indent=2)


print("\nRAG-ready asset file saved to output/assets_rag_ready.json")


#Embed the flattened assets


BATCH_SIZE = 100  # Can increase up to 2048 if under token limit


openai.api_key = os.getenv("OPENAI_API_KEY")
def asset_to_text(asset):
   """Concatenate all available fields into one string for embedding."""
   parts = []
   for k, v in asset.items():
       # Skip the embedding field if re-embedding
       if k == "embedding":
           continue
       # Handle nested dicts (e.g., for mesh bounds)
       if isinstance(v, dict):
           for subk, subv in v.items():
               parts.append(f"{k}.{subk}: {subv}")
       else:
           parts.append(f"{k}: {v}")
   return ". ".join(parts)


# Load assets
with open("output/assets_rag_ready.json", "r") as infile:
   assets = json.load(infile)


# Create texts for embedding
texts = [asset_to_text(asset) for asset in assets]


# Batch embedding
for start in range(0, len(texts), BATCH_SIZE):
   end = min(start + BATCH_SIZE, len(texts))
   batch = texts[start:end]
   print(f"Embedding batch {start}-{end}...")


   try:
  
       openai.api_key = os.getenv("OPENAI_API_KEY")
       response = openai.embeddings.create(
           input=batch,
           model="text-embedding-3-large"
       )
       for i, emb in enumerate(response.data):
           assets[start + i]["embedding"] = emb.embedding
   except Exception as e:
       print(f"Error embedding batch {start}-{end}: {e}")
      


# Save results
with open("output/assets_rag_embedded.json", "w") as outfile:
   json.dump(assets, outfile, indent=2)


print("Full-field embedding complete! Output saved to output/assets_rag_embedded.json")

