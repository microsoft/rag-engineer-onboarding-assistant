# Phase 1: RAG Chatbot 🤖
This code is modified from the [Azure AI RAG Workshop](https://github.com/nitya/azure-ai-rag-workshop). You can build your own RAG chatbot following these steps:

## 1. Setup
- Run `pip install -r requirements.txt`
- Run `az login`
- Follow steps [2.1](https://nitya.github.io/azure-ai-rag-workshop/1-Hybrid-Workshop/2-Setup/01/) and [2.2](https://nitya.github.io/azure-ai-rag-workshop/1-Hybrid-Workshop/2-Setup/02/) from the [Azure AI RAG Workshop](https://github.com/nitya/azure-ai-rag-workshop)
- Create and complete an .env file using the [samples.env](../../sample.env) file from the root of this directory ([instructions to find your project connection string](https://nitya.github.io/azure-ai-rag-workshop/1-Hybrid-Workshop/2-Setup/07/#2-update-connection-string))
- Modify the company information and complete any prompt engineering in [grounded_chat.prompty](../../assets/grounded_chat.prompty) and [intent_mapping.prompty](../../assets/intent_mapping.prompty).

## 2. Create search index
Run `python create_search_index.py` with the argument `--csv-file` that specifies the path to the csv file containing your grounding documents

## 3. Test document retrieval
Run `python get_documents.py` with the argument `--query` to view intent mapping and document retreval outputs for different queries

## 4. Test chatbot
Run `python chat.py` with the argument `--query` to see complete outputs for different queries