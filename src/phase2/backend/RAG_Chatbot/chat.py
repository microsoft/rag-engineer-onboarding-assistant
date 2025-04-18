# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# ----------------------------------------------
# Setup
# ----------------------------------------------
import os
from pathlib import Path
from opentelemetry import trace
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from RAG_Chatbot.config import ASSET_PATH, get_logger, enable_telemetry
from RAG_Chatbot.get_documents import get_documents

# initialize logging and tracing objects
logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# create a project client using environment variables loaded from the .env file
project = AIProjectClient.from_connection_string(
 conn_str=os.environ["AIPROJECT_CONNECTION_STRING"], credential=DefaultAzureCredential()
)

# ----------------------------------------------
# Chat
# ----------------------------------------------
from azure.ai.inference.prompts import PromptTemplate

# create a chat client we can use for testing
chat = project.inference.get_chat_completions_client()

@tracer.start_as_current_span(name="chat_with_products")
def send_chat(messages: list, context: dict = None) -> dict:
 print(messages)
 if context is None:
  context = {}

 documents = get_documents(messages, context)

 # do a grounded chat call using the search results
 grounded_chat_prompt = PromptTemplate.from_prompty(Path(ASSET_PATH) / "grounded_chat.prompty")

 for doc in documents:
  logger.info(f"📄 Document found: {doc['filepath']}")
 system_message = grounded_chat_prompt.create_messages(documents=documents, context=context)
 response = chat.complete(
  model=os.environ["CHAT_MODEL"],
  messages=system_message + messages,
  **grounded_chat_prompt.parameters,
 )
 logger.info(f"💬 Response: {response.choices[0].message}")

 # return a chat protocol compliant response
 return {"message": response.choices[0].message, "context": context}

if __name__ == "__main__":
  import argparse

  # load command line arguments
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--query",
    type=str,
    default="How can I start the onboarding process?",
  )
  parser.add_argument(
    "--enable-telemetry",
    action="store_true",
    help="Enable sending telemetry back to the project",
  )
  args = parser.parse_args()
  if args.enable_telemetry:
    enable_telemetry(True)

  # run chat with products
  response = send_chat(messages=[{"role": "user", "content": args.query}])


# ----------------------------------------------------------
# To test:
# - make sure `assets/grounded_chat.prompty` exists
# - run as: 
#   python chat_with_products.py 
#    --query "My manager told me to do a hotfix. What does this mean?"
# ----------------------------------------------------------
# Response Looks Something Like:
'''
💬 Response: {
  'content': "<explanation>", 'role': 'assistant'
  }
'''
# ----------------------------------------------------------