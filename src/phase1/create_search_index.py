# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# ----------------------------------------------
# Setup
# ----------------------------------------------
import os
import sys
import uuid
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import ConnectionType
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
import pandas as pd
from config import get_logger

# initialize logging object
logger = get_logger(__name__)

# create a project client using environment variables loaded from the .env file
project = AIProjectClient.from_connection_string(
  conn_str=os.environ["AIPROJECT_CONNECTION_STRING"], credential=DefaultAzureCredential()
)

# create a vector embeddings client that will be used to generate vector embeddings
embeddings = project.inference.get_embeddings_client()

# use the project client to get the default search connection
search_connection = project.connections.get_default(
  connection_type=ConnectionType.AZURE_AI_SEARCH, include_credentials=True
)

# create a search index client using the search connection
index_client = SearchIndexClient(
  endpoint=search_connection.endpoint_url, credential=AzureKeyCredential(key=search_connection.key)
)

# ----------------------------------------------
# Create search index
# ----------------------------------------------
from azure.search.documents.indexes.models import (
  SemanticSearch,
  SearchField,
  SimpleField,
  SearchableField,
  SearchFieldDataType,
  SemanticConfiguration,
  SemanticPrioritizedFields,
  SemanticField,
  VectorSearch,
  HnswAlgorithmConfiguration,
  VectorSearchAlgorithmKind,
  HnswParameters,
  VectorSearchAlgorithmMetric,
  ExhaustiveKnnAlgorithmConfiguration,
  ExhaustiveKnnParameters,
  VectorSearchProfile,
  SearchIndex,
)


def create_index_definition(index_name: str, model: str) -> SearchIndex:
  dimensions = 1536 # text-embedding-ada-002
  if model == "text-embedding-3-large":
    dimensions = 3072

  # rhe fields we want to index. The "embedding" field is a vector field that will
  # be used for vector search.
  fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SearchableField(name="content", type=SearchFieldDataType.String),
    SimpleField(name="filepath", type=SearchFieldDataType.String),
    SearchableField(name="title", type=SearchFieldDataType.String),
    SimpleField(name="url", type=SearchFieldDataType.String),
    SearchField(
      name="contentVector",
      type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
      searchable=True,
      vector_search_dimensions=dimensions,
      vector_search_profile_name="myHnswProfile",
    ),
  ]

  # the "content" field should be prioritized for semantic ranking.
  semantic_config = SemanticConfiguration(
    name="default",
    prioritized_fields=SemanticPrioritizedFields(
      title_field=SemanticField(field_name="title"),
      keywords_fields=[],
      content_fields=[SemanticField(field_name="content")],
    ),
  )

  # for vector search, we want to use the HNSW (Hierarchical Navigable Small World)
  #  algorithm (a type of approximate nearest neighbor search algorithm) with cosine
  #  distance.
  vector_search = VectorSearch(
    algorithms=[
      HnswAlgorithmConfiguration(
        name="myHnsw",
        kind=VectorSearchAlgorithmKind.HNSW,
        parameters=HnswParameters(
          m=4,
          ef_construction=1000,
          ef_search=1000,
          metric=VectorSearchAlgorithmMetric.COSINE,
        ),
      ),
      ExhaustiveKnnAlgorithmConfiguration(
        name="myExhaustiveKnn",
        kind=VectorSearchAlgorithmKind.EXHAUSTIVE_KNN,
        parameters=ExhaustiveKnnParameters(metric=VectorSearchAlgorithmMetric.COSINE),
      ),
    ],
    profiles=[
      VectorSearchProfile(
        name="myHnswProfile",
        algorithm_configuration_name="myHnsw",
      ),
      VectorSearchProfile(
        name="myExhaustiveKnnProfile",
        algorithm_configuration_name="myExhaustiveKnn",
      ),
    ],
  )

  # create the semantic settings with the configuration
  semantic_search = SemanticSearch(configurations=[semantic_config])

  # create the search index definition
  return SearchIndex(
    name=index_name,
    fields=fields,
    semantic_search=semantic_search,
    vector_search=vector_search,
  )

# define a function for indexing a csv file, that adds each row as a document
# and generates vector embeddings for the specified content_column
def create_docs(path: str, content_column: str, model: str) -> list[dict[str, any]]:
    products = pd.read_csv(path)
    items = []
    for product in products.to_dict("records"):
        content = product[content_column]
        id = str(product["id"])
        title = product["name"]
        url = f"/data/{title.lower().replace(' ', '-')}"
        emb = embeddings.embed(input=content, model=model)
        rec = {
            "id": id,
            "content": content,
            "filepath": f"{title.lower().replace(' ', '-')}",
            "title": title,
            "url": url,
            "contentVector": emb.data[0].embedding,
        }
        items.append(rec)

    return items

def create_index(path, index_name):
  try:
    index_definition = index_client.get_index(index_name)
    index_client.delete_index(index_name)
    logger.info(f"🗑️ Found existing index named '{index_name}', and deleted it")
  except Exception:
    pass

  # create an empty search index
  index_definition = create_index_definition(index_name, model=os.environ["EMBEDDINGS_MODEL"])
  index_client.create_index(index_definition)

  # load docs
  docs = create_docs(path=path, model=os.environ["EMBEDDINGS_MODEL"])

  # Add the documents to the index using the Azure AI Search client
  search_client = SearchClient(
    endpoint=search_connection.endpoint_url,
    index_name=index_name,
    credential=AzureKeyCredential(key=search_connection.key),
  )
  search_client.upload_documents(docs)
  logger.info(f"➕ Uploaded {len(docs)} documents to '{index_name}' index")


if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument(
      "--csv-file", type=str, help="path to data for creating search index", default="assets/data.csv"
  )
  args = parser.parse_args()
  csv_file = args.csv_file

  create_index(os.environ["AISEARCH_INDEX_NAME"])