import subprocess
import sys
import os


def run_script(script_path):
   result = subprocess.run([sys.executable, script_path])
   if result.returncode != 0:
       print(f"Error: {script_path} failed with exit code {result.returncode}")
       sys.exit(result.returncode)


def main():
   base_dir = os.path.dirname(os.path.abspath(__file__))


   # Step 1: Extract assets
   print("Step 1: Extracting assets...")
   run_script(os.path.join(base_dir, "asset_extraction", "extract_assets.py"))


   # Step 2: Index assets
   print("Step 2: Indexing assets...")
   run_script(os.path.join(base_dir, "asset_indexing", "index_assets.py"))


   # Step 3: Run RAG interface
   print("Step 3: Launching RAG interface...")
   run_script(os.path.join(base_dir, "asset_rag", "rag_query.py"))


   print("All steps completed!")


if __name__ == "__main__":
   main()



