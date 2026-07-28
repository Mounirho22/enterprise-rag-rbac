from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
import chromadb
# pyrefly: ignore [missing-import]
from langchain_community.vectorstores import Chroma
# pyrefly: ignore [missing-import]
from langchain_huggingface import HuggingFaceEmbeddings
# pyrefly: ignore [missing-import]
from langchain_core.documents import Document
import requests

# In-memory Chroma client
chroma_client = chromadb.EphemeralClient()

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

collection_name = "enterprise_docs"

# We will initialize vectorstore during startup
vectorstore = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vectorstore
    
    # Initialize Chroma vector store with LangChain
    vectorstore = Chroma(
        client=chroma_client,
        collection_name=collection_name,
        embedding_function=embeddings,
    )
    
    # Define mock documents with RBAC metadata
    docs = [
        Document(
            page_content="The public guest wifi password is 'welcome2026'.",
            metadata={"role": "public"}
        ),
        Document(
            page_content="The upcoming Q4 financial merger with Acme Corp is valued at $50M.",
            metadata={"role": "executive"}
        ),
        Document(
            page_content="The master database SSH key is stored in /var/secure/keys.",
            metadata={"role": "it_admin"}
        )
    ]
    
    # Add documents to the vector store
    vectorstore.add_documents(docs)
    print("Vector store populated with initial documents.")
    yield
    # Cleanup on shutdown
    vectorstore = None

app = FastAPI(title="Enterprise RAG with RBAC", lifespan=lifespan)

class AskRequest(BaseModel):
    query: str
    user_role: str

@app.post("/ask")
def ask(request: AskRequest):
    if not vectorstore:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    # Implement RBAC Retrieval: Metadata filter for 'public' or the user's specific role
    if request.user_role == "public":
        filter_dict = {"role": "public"}
    else:
        # ChromaDB supports logical operators in filters
        filter_dict = {
            "$or": [
                {"role": {"$eq": "public"}},
                {"role": {"$eq": request.user_role}}
            ]
        }
    
    # Retrieve documents using the constructed filter
    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": 3,
            "filter": filter_dict
        }
    )
    
    retrieved_docs = retriever.invoke(request.query)
    
    # Prepare context for the LLM
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    
    # Prepare prompt
    prompt = f"""Use the following context to answer the query. If the context does not contain the answer, say you don't know. Do not use outside knowledge.

Context:
{context}

Query: {request.query}

Answer:"""

    # Call local Ollama instance
    ollama_url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(ollama_url, json=payload)
        response.raise_for_status()
        llm_result = response.json()
        answer = llm_result.get("response", "")
    except Exception as e:
        answer = f"Error communicating with Ollama: {str(e)}"
    
    return {
        "answer": answer,
        "retrieved_docs": [{"content": doc.page_content, "metadata": doc.metadata} for doc in retrieved_docs]
    }
