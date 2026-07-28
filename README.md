# Enterprise RAG Application with Role-Based Access Control (RBAC)

This project demonstrates a secure Enterprise Retrieval-Augmented Generation (RAG) application utilizing Role-Based Access Control (RBAC) at the retrieval level.

## The Importance of Metadata Filtering in RAG

In enterprise environments, standard RAG applications often face a critical security flaw: an LLM can potentially regurgitate any information it receives in its context window. If a user manages to query sensitive information, the LLM has no inherent concept of access rights.

### Preventing Prompt Injection and Data Exfiltration

Without metadata filtering, malicious actors or unauthorized employees could use sophisticated prompt injections to bypass application-level restrictions and extract sensitive data (e.g., executive financials or IT credentials) from the vector database. 

By applying **Metadata Filtering** directly to the vector database query (in this case, ChromaDB), we enforce security *before* the context is ever passed to the LLM. 
1. The vector search is restricted strictly to documents tagged with the user's role (or public data).
2. The LLM simply cannot leak data it was never provided.

### Zero-Trust Security in Enterprise AI

This architecture adheres to the principles of Zero-Trust Security. We do not trust the LLM to filter sensitive information. Instead, we ensure data isolation at the storage and retrieval layer. The LLM acts purely as a synthesizer for data the user is already explicitly authorized to view.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```
3. Send a POST request to `/ask`:
   ```json
   {
       "query": "What is the wifi password and the Q4 merger value?",
       "user_role": "public"
   }
   ```
   *An `executive` role would retrieve the merger data, while a `public` role would only see the wifi password.*
