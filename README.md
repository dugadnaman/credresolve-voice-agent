# CredResolve Voice Agent

An AI-powered inbound voice agent for borrower support at a lending company. Built as an agentic system that understands borrower context, diagnoses intent, retrieves policies, and learns from previous interactions.

---

## Architecture

```
BORROWER CALL
↓
[Context Engine]     → Fetches borrower profile, payment history, tickets, conversations
↓
[Diagnosis Layer]    → Detects intent, identifies known facts, finds missing info
↓
[LLM Agent]          → Reasons, calls tools, generates response
↑         ↓
[RAG]           [Tools]   → Policy retrieval + CRM/payment/ticket actions
↓
[Memory Store]       → Saves commitments, preferences, resolution paths
↓
BORROWER HEARS ANSWER
```

---

## Project Structure

```
voice-agent/
├── core/
│   ├── context_engine.py      # Builds unified borrower profile before every call
│   ├── diagnosis_layer.py     # Detects intent, identifies info gaps
│   ├── rag_engine.py          # Keyword-based policy document retrieval
│   └── memory_store.py        # Persistent memory across calls
├── agent/
│   ├── tools.py               # 8 tool definitions for the LLM agent
│   └── agent.py               # Main agent loop with tool use
├── api/
│   ├── main.py                # FastAPI server
│   └── dashboard.py           # Live demo dashboard
├── data/
│   ├── borrowers.db           # SQLite: 100 borrowers, 500 payments, 100 tickets
│   └── knowledge_base/        # 20 JSON policy documents
├── scripts/
│   └── generate_data.py       # Synthetic data generator
└── requirements.txt
```

---

## Setup

```bash
git clone https://github.com/dugadnaman/credresolve-voice-agent.git
cd credresolve-voice-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
python scripts/generate_data.py
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check, DB status |
| GET | / | API info and endpoint list |
| POST | /chat | Chat with the voice agent |
| GET | /context/{identifier} | Get full borrower context |
| GET | /memory/{borrower_id} | Get borrower memory |
| POST | /memory/commitment | Save payment commitment |

### Example: Chat with agent
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"borrower_identifier": "+919636045484", "message": "Why was a penalty charged on my account?", "session_id": "demo1"}'
```

---

## Key Components

### Context Engine
Runs before every interaction. Assembles a unified borrower profile from the database including loan details, payment history, open tickets, conversation history, and risk signals. The LLM never queries the database directly.

### Diagnosis Layer
Detects borrower intent from 8 categories (EMI inquiry, penalty inquiry, payment failure, waiver request, settlement, foreclosure, payment commitment, general). Identifies what is already known from context vs what is missing, and generates the most relevant follow-up question.

### RAG Engine
Keyword-based retrieval over 20 policy documents covering late payment policy, penalty waiver eligibility, foreclosure charges, settlement terms, NACH setup, CIBIL impact, and more. Retrieved policies are injected into the LLM system prompt to ground responses.

### Memory Store
Persists borrower commitments, preferences, and agent resolution paths across calls. Enables Scenario 6: the agent remembers a promise-to-pay from a previous call and opens the follow-up call by referencing it.

---

## Demo Scenarios

### Scenario 1: Remaining EMI Inquiry
Borrower: "How many EMIs are remaining on my loan?"
Agent: Identifies borrower, retrieves loan details from LMS, calculates remaining tenure, explains next due date and amount.

### Scenario 2: Interest Paid Inquiry
Borrower: "How much interest have I paid so far?"
Agent: Retrieves full payment history from Razorpay gateway, calculates principal vs interest breakdown, explains outstanding balance.

### Scenario 3: Penalty Charge Inquiry
Borrower: "Why was a penalty charged on my account?"
Agent: Retrieves penalty amount and overdue days from context, fetches late payment policy via RAG, explains the exact charge calculation and reason.

### Scenario 4: Payment Failure Due to Bank Glitch
Borrower: "My payment failed even though I had enough balance."
Agent: Checks payment logs, retrieves gateway response codes, classifies failure as bank-side vs borrower-side, recommends next actions.

### Scenario 5: Penalty Waiver Request
Borrower: "Can my penalty be waived? The payment failed due to a bank error."
Agent: Checks payment history, retrieves waiver eligibility policy via RAG, determines eligibility, creates support ticket automatically.

### Scenario 6: Follow-up Call With Memory
First call - Borrower: "My salary is delayed. I will pay next Friday."
Agent: Records commitment with exact date and amount in memory store.
Second call - Agent opens with: "During our last call you committed to paying ₹[amount] by [date] due to a salary delay. Were you able to complete that payment?"

---

## Tech Stack

- **LLM**: Claude (Anthropic) with tool use
- **RAG**: Keyword TF-IDF over JSON knowledge base
- **Database**: SQLite
- **API**: FastAPI + Uvicorn
- **Memory**: SQLite persistent store
- **Voice**: Deepgram (STT) + ElevenLabs (TTS) — configurable via .env
