import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import dataclasses
import fastapi
import uvicorn
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from dotenv import load_dotenv

# Import Core Context, Diagnosis, RAG and Memory stores
from core.context_engine import ContextEngine, DB_PATH
from core.diagnosis_layer import DiagnosisLayer
from core.rag_engine import RAGEngine, KB_PATH
from core.memory_store import MemoryStore

# Import Agent and Tools
from agent.agent import BorrowerAgent

# Load environment variables
load_dotenv()

# Initialize FastAPI App
app = fastapi.FastAPI(title="CredResolve Voice Agent API")

# Active sessions dictionary mapping session_id -> BorrowerAgent instance
active_sessions = {}

# Pydantic Request & Response Models
class ChatRequest(BaseModel):
    borrower_identifier: str = Field(..., description="Phone number or borrower_id of the customer")
    message: str = Field(..., description="Spoken message or text utterance from the user")
    session_id: str = Field("default", description="Session identifier for multi-turn tracking")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Spoken assistant output text")
    intent: str = Field(..., description="Classified conversation intent")
    risk_signals: List[str] = Field(..., description="Active warning risk flags")
    tools_used: List[str] = Field(..., description="Names of tools executed during this turn")
    session_id: str = Field(..., description="Associated session ID")

class ContextRequest(BaseModel):
    borrower_identifier: str = Field(..., description="Phone number or borrower_id of the customer")

class CommitmentRequest(BaseModel):
    borrower_id: str = Field(..., description="Database ID of the borrower")
    amount: float = Field(..., description="Amount borrower has promised to pay")
    date: str = Field(..., description="Due date of commitment (format: YYYY-MM-DD)")
    reason: str = Field(..., description="Stated reason for payment delay")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Main endpoint to chat with the voice agent, managing multi-turn session instances."""
    session_id = req.session_id
    if session_id not in active_sessions:
        active_sessions[session_id] = BorrowerAgent()
        
    agent = active_sessions[session_id]
    try:
        response_text = agent.chat(req.borrower_identifier, req.message)
        return ChatResponse(
            response=response_text,
            intent=agent.last_intent,
            risk_signals=agent.last_risk_signals,
            tools_used=agent.last_tools_used,
            session_id=session_id
        )
    except Exception as e:
        raise fastapi.HTTPException(status_code=400, detail=str(e))

@app.get("/context/{borrower_identifier}")
async def get_context(borrower_identifier: str):
    """Exposes dynamic borrower profile context assembled from the database."""
    context = ContextEngine.build_context(borrower_identifier)
    if not context:
        raise fastapi.HTTPException(status_code=404, detail=f"Borrower with identifier '{borrower_identifier}' was not found.")
    return dataclasses.asdict(context)

@app.get("/memory/{borrower_id}")
async def get_memory(borrower_id: str):
    """Exposes all stored borrower memory profiles (commitments, preferences, risk notes, callbacks)."""
    store = MemoryStore()
    return store.get_borrower_memory(borrower_id)

@app.post("/memory/commitment")
async def post_commitment(req: CommitmentRequest):
    """Saves a promise-to-pay commitment for a borrower to persistent memory."""
    store = MemoryStore()
    res = store.save_commitment(req.borrower_id, req.amount, req.date, req.reason)
    return res

@app.get("/health")
async def health():
    """Returns application health checks, database status, and knowledge document count."""
    db_exists = os.path.exists(DB_PATH)
    kb_doc_count = 0
    if os.path.exists(KB_PATH):
        kb_doc_count = len([f for f in os.listdir(KB_PATH) if f.endswith(".json")])
        
    return {
        "status": "ok",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "db_exists": db_exists,
        "kb_doc_count": kb_doc_count
    }

@app.get("/")
async def root():
    """Root info page detailing available API services."""
    return {
        "name": "CredResolve Voice Agent API",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/chat", "method": "POST", "description": "Interact with the voice agent"},
            {"path": "/context/{borrower_identifier}", "method": "GET", "description": "Retrieve dynamic borrower context profile"},
            {"path": "/memory/{borrower_id}", "method": "GET", "description": "Retrieve borrower preferences and commitments memory"},
            {"path": "/memory/commitment", "method": "POST", "description": "Save borrower payment commitment"},
            {"path": "/health", "method": "GET", "description": "Service health check status"}
        ]
    }

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
