# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# ----------------------------------------------
# Setup
# ----------------------------------------------
import os
from pathlib import Path
from opentelemetry import trace
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import ConnectionType
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from config import ASSET_PATH, get_logger

# initialize logging and tracing objects
logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# create a project client using environment variables loaded from the .env file
project = AIProjectClient.from_connection_string(
  conn_str=os.environ["AIPROJECT_CONNECTION_STRING"], credential=DefaultAzureCredential()
)

# create a vector embeddings client that will be used to generate vector embeddings
chat = project.inference.get_chat_completions_client()
embeddings = project.inference.get_embeddings_client()

# use the project client to get the default search connection
search_connection = project.connections.get_default(
  connection_type=ConnectionType.AZURE_AI_SEARCH, include_credentials=True
)

# create a search index client using the search connection
search_client = SearchClient(
  index_name=os.environ["AISEARCH_INDEX_NAME"],
  endpoint=search_connection.endpoint_url,
  credential=AzureKeyCredential(key=search_connection.key),
)

# ----------------------------------------------
# Retrieve documents
# ----------------------------------------------
from azure.ai.inference.prompts import PromptTemplate
from azure.search.documents.models import VectorizedQuery
import json

@tracer.start_as_current_span(name="get_documents")
def get_documents(messages: list, context: dict = None) -> dict:
  if context is None:
    context = {}

  overrides = context.get("overrides", {})
  top = overrides.get("top", 3)

  # generate a search query from the chat messages
  intent_prompty = PromptTemplate.from_prompty(Path(ASSET_PATH) / "intent_mapping.prompty")

  intent_mapping_response = chat.complete(
    model=os.environ["INTENT_MAPPING_MODEL"],
    messages=intent_prompty.create_messages(conversation=messages),
    **intent_prompty.parameters,
  )

  # the search_query returned here will be a stringified JSON object
  search_query = intent_mapping_response.choices[0].message.content
  logger.debug(f"🧠 Intent mapping: {search_query}")

  # The intent mapping response is a stringied JSON object 
  #  with the intent and search_query components. We need to
  #  extract the search_query term and create embedding from it
  intent_map = json.loads(search_query)
  embedding = embeddings.embed(model=os.environ["EMBEDDINGS_MODEL"], input=intent_map["search_query"])
  search_vector = embedding.data[0].embedding

  # search the index for products matching the search query
  vector_query = VectorizedQuery(vector=search_vector, k_nearest_neighbors=top, fields="contentVector")

  search_results = search_client.search(
    search_text=search_query, vector_queries=[vector_query], select=["id", "content", "filepath", "title", "url"]
  )

  documents = [
    {
      "id": result["id"],
      "content": result["content"],
      "filepath": result["filepath"],
      "title": result["title"],
      "url": result["url"],
    }
    for result in search_results
  ]

  # add results to the provided context
  if "thoughts" not in context:
    context["thoughts"] = []

  # add thoughts and documents to the context object so it can be returned to the caller
  context["thoughts"].append(
    {
      "title": "Generated search query",
      "description": search_query,
    }
  )

  if "grounding_data" not in context:
    context["grounding_data"] = []
  context["grounding_data"].append(documents)

  logger.debug(f"📄 {len(documents)} documents retrieved:")
  for doc in documents:
    logger.debug(f"file: {doc['filepath']}")
  return documents

if __name__ == "__main__":
  import logging
  import argparse

  # set logging level to debug when running this module directly
  logger.setLevel(logging.DEBUG)

  # load command line arguments
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--query",
    type=str,
    help="Query to use to get help from the chatbot",
    default="Where do I get started?"
  )

  args = parser.parse_args()
  query = args.query

  result = get_documents(messages=[{"role": "user", "content": query}])


# ----------------------------------------------------------
# To test:
# - make sure `assets/intent_mapping.prompty` exists
# - run as: 
#   python get_documents.py 
#    --query "My manager told me to do a hotfix. What does this mean?"
# ----------------------------------------------------------
# Response Looks Something Like:
'''
🧠 Intent mapping: {
  "intent": "The user wants to know what a hotfix is and how to do it",
  "search_query": "hotfix definition and process"
}
📄 3 documents retrieved: 
file: <filepath/title>
...
'''
# ----------------------------------------------------------