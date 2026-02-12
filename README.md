## Setup

1.  **Clone this repo and navigate to the directory:**

2.  **Install all dependencies:**

    ```bash
    uv pip install -r requirements.txt
    ```

3.  **Configure environment variables:**

        ```
        OPENAI_API_KEY=your-openai-api-key-here
        BRAINTRUST_API_KEY=your-braintrust-api-key-here
```

## Running the Pipeline

The entire pipeline is orchestrated by `main.py`.  
Running this file will execute all three steps in sequence:

1. **Asset Extraction**
2. **Asset Indexing/Embedding**
3. **RAG LLM Search (Gradio UI)**

**To run:**

```bash
python main.py

```
## Quick Start: Run the Asset RAG MCP Server Without Extraction and Indexing

If you want to quickly test the retrieval-augmented asset search agent, you **do not need to run the entire pipeline**.  
You can skip the time-consuming asset extraction and embedding steps (Steps 1 & 2) by using the **precomputed [`assets_rag_embedded.json`](https://drive.google.com/file/d/17SIM5X3SCBk6bV95V3Az4P7OXRVL8pvl/view?usp=sharing)** provided here.

### Steps

1. **Skip or comment out Step 1 (Asset Extraction) and Step 2 (Asset Indexing/Embedding) in `main.py`.**

2. **Ensure `asset_rag/rag_query.py` loads the precomputed file.**  
   **Add the full file path** to your local copy of `assets_rag_embedded.json` in rag_query.py.  
   For example:
   ```python
   with open("/Users/XYZ/RAGPipeline/asset_rag/output/assets_rag_embedded.json", "r") as infile:
       assets = json.load(infile)

3. **Start the MCP server:**  
   Run the following command from your project root:
   ```bash
   python asset_rag/rag_query.py
4. **Configure Cursor to connect to your MCP server:**

   Add or update the following block in your `mcp.json` file (be sure to use your actual paths):

   ```json
   "RAGMCP": {
     "command": "/Users/XYZ/venv/bin/python", // Path to your Python environment. Use `which python` to find your path.
     "args": [
       "/asset_rag/rag_query.py" // path to your `rag_query.py` script.
     ]
   }
5. ### Select the RAGMCP Agent in Cursor

After starting your MCP server and configuring mcp.json in Cursor, make sure the **RAGMCP** agent is enabled in the MCP tools menu:

![Select RAGMCP in Cursor MCP tools](img/select_ragmcp.png)


