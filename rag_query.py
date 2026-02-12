import os
import openai


from dotenv import load_dotenv
load_dotenv()
import time


import numpy as np
import json


from braintrust import init_logger, wrap_openai, traced
from braintrust_langchain import BraintrustCallbackHandler, set_global_handler

from mcp.server.fastmcp import FastMCP
from openai import OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")


# Initialize Braintrust logger
braintrust_api_key = os.getenv("BRAINTRUST_API_KEY")
init_logger(project="LangChain MCP Agent", api_key=braintrust_api_key)
set_global_handler(BraintrustCallbackHandler())
client = wrap_openai(OpenAI(api_key=os.environ["OPENAI_API_KEY"]))

with open("/users/XYZ/asset_rag/output/assets_rag_embedded.json", "r") as infile:

   assets = json.load(infile)


def embed_query(text):
   response = openai.embeddings.create(
       input=text,
       model="text-embedding-3-large"
   )
   return np.array(response.data[0].embedding)


def cosine_similarity(a, b):
   return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


#Find the top_n most similar assets to the query based on cosine similarity


def search_assets(query, top_n=5):
   query_emb = embed_query(query)
   results = []
   for asset in assets:
       asset_emb = np.array(asset["embedding"])
       sim = cosine_similarity(query_emb, asset_emb)
       results.append((sim, asset))
   results.sort(reverse=True, key=lambda x: x[0])
   top_results = results[:top_n]
  
   # Format for display
   table_data = []
   for score, asset in top_results:
       table_data.append([
           f"{score:.4f}",
           asset.get("asset_name", ""),
           asset.get("path", ""),
           asset.get("summary", "")
       ])
   return table_data


@traced
def gpt_response(query, table_data):
    context = "\n\n".join([row[3] for row in table_data])
    prompt = f"""
A Unity developer searched: '{query}'
Here are the most relevant assets:
{context}

Answer the developer's question using the above assets.
"""
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert Unity asset search assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# Unified interface
def main_fn(query, top_n=5):
    table_data = search_assets(query, top_n)
    answer = gpt_response(query, table_data)
    return table_data, answer

# Create the MCP server with the agent name "RAGMCP"
mcp = FastMCP("RAGMCP")

@mcp.tool()
def rag_asset(query: str, top_n: int = 5) -> str:
    table_data = search_assets(query, top_n)
    answer = gpt_response(query, table_data)
    return answer
print("About to run MCP server...")
if __name__ == "__main__":
    mcp.run()


