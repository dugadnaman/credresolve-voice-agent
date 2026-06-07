import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
from groq import Groq
from dotenv import load_dotenv

# Import core system modules
from core.context_engine import ContextEngine, DB_PATH
from core.diagnosis_layer import DiagnosisLayer
from core.rag_engine import RAGEngine

# Import tool functions and definitions
from agent.tools import (
    get_loan_details,
    get_payment_history,
    get_penalty_details,
    create_ticket,
    generate_payment_link,
    schedule_callback,
    escalate_to_human,
    search_knowledge_base,
    TOOL_DEFINITIONS
)

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Mock classes for testing without API keys
class MockContentBlock:
    def __init__(self, type: str, text: str = None, id: str = None, name: str = None, input: dict = None):
        self.type = type
        self.text = text
        self.id = id
        self.name = name
        self.input = input

class MockMessages:
    def __init__(self, content: list, stop_reason: str):
        self.content = content
        self.stop_reason = stop_reason

class BorrowerAgent:
    def __init__(self):
        self.context_engine = ContextEngine()
        self.diagnosis_layer = DiagnosisLayer()
        self.rag_engine = RAGEngine()
        
        # Check if we should run in mock mode (missing, invalid, or placeholder keys)
        self.is_mock = (
            not GROQ_API_KEY 
            or "your_key_here" in GROQ_API_KEY
        )
        
        if not self.is_mock:
            try:
                self.groq_client = Groq(api_key=GROQ_API_KEY)
            except Exception as e:
                print(f"[API Error] Groq client init failed: {e}. Running in mock mode.")
                self.is_mock = True
                self.groq_client = None
        else:
            self.groq_client = None
            
        self.conversation_history = []
        self.current_borrower_id = None
        self.system_prompt = None
        self.context = None
        self.last_intent = "GENERAL_INQUIRY"
        self.last_risk_signals = []
        self.last_tools_used = []

    def build_system_prompt(self, context, diagnosis, rag_docs) -> str:
        """Assembles context details, RAG policy matches, intent diagnosis and instructions into the LLM system prompt."""
        prompt = []
        # 1. Role
        prompt.append("You are a professional loan servicing agent for CredResolve Lending. You speak clearly, empathetically, and concisely. Always address the borrower by first name.")
        prompt.append("")
        
        # 2. Borrower Context
        prompt.append(self.context_engine.to_llm_prompt(context))
        prompt.append("")
        
        # 3. RAG Documents
        prompt.append(self.rag_engine.format_for_prompt(rag_docs))
        prompt.append("")
        
        # 4. Diagnosis Hints
        prompt.append("=== DIAGNOSIS HINTS ===")
        prompt.append(f"Detected Intent: {diagnosis.intent}")
        prompt.append(f"Known Facts: {', '.join(diagnosis.known_facts)}")
        prompt.append(f"Missing Info: {', '.join(diagnosis.missing_info)}")
        prompt.append(f"Recommended Next Question: {diagnosis.next_question}")
        prompt.append(f"Resolution Hint: {diagnosis.resolution_hint}")
        prompt.append("")
        
        # 5. Rules
        prompt.append("=== INSTRUCTIONS AND RULES ===")
        prompt.append("- Never ask for information you already have in the context.")
        prompt.append("- If can_resolve_immediately is True, answer directly without asking questions.")
        prompt.append("- Always ground penalty/policy explanations in the retrieved policy documents.")
        prompt.append("- If borrower mentions salary delay or payment commitment, always ask for exact date and amount.")
        prompt.append("- For settlement or escalation, always create a ticket before ending the call.")
        prompt.append("- Keep responses under 3 sentences for simple queries, longer only for complex explanations.")
        prompt.append("- Never refer to yourself as [Your Name]. Always introduce yourself as 'your CredResolve loan servicing agent'.")
        
        return "\n".join(prompt)

    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Executes corresponding database or RAG tool function for the current borrower ID."""
        self.last_tools_used.append(tool_name)
        borrower_id = self.current_borrower_id
        if tool_name == "get_loan_details":
            res = get_loan_details(borrower_id)
        elif tool_name == "get_payment_history":
            limit = tool_input.get("limit", 10)
            res = get_payment_history(borrower_id, limit)
        elif tool_name == "get_penalty_details":
            res = get_penalty_details(borrower_id)
        elif tool_name == "create_ticket":
            res = create_ticket(
                borrower_id,
                category=tool_input["category"],
                subject=tool_input["subject"],
                description=tool_input["description"]
            )
        elif tool_name == "generate_payment_link":
            res = generate_payment_link(borrower_id, tool_input["amount"])
        elif tool_name == "schedule_callback":
            res = schedule_callback(borrower_id, tool_input["callback_date"], tool_input["reason"])
        elif tool_name == "escalate_to_human":
            res = escalate_to_human(borrower_id, tool_input["reason"], tool_input.get("priority", "HIGH"))
        elif tool_name == "search_knowledge_base":
            res = search_knowledge_base(borrower_id, tool_input["query"])
        else:
            res = {"error": f"Unknown tool: {tool_name}"}
        return json.dumps(res)

    def _get_mock_response(self) -> MockMessages:
        """Simulates LLM responses and tool usage calls for validation testing when API keys are absent."""
        user_message = ""
        for msg in reversed(self.conversation_history):
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                user_message = msg["content"]
                break
                
        msg_lower = user_message.lower()
        
        name = "Borrower"
        penalty_amount = 0.0
        overdue_days = 0
        emi_amount = 0.0
        emis_remaining = 0
        next_due_date = "N/A"
        interest_paid = 0.0
        outstanding_balance = 0.0
        
        if self.context:
            if self.context.borrower:
                full_name = self.context.borrower.name
                name = full_name.split()[0] if full_name else "Borrower"
                penalty_amount = self.context.borrower.penalty_amount
                overdue_days = self.context.borrower.overdue_days
                emi_amount = self.context.borrower.emi_amount
                emis_remaining = self.context.borrower.emis_remaining
                next_due_date = self.context.borrower.next_due_date
                outstanding_balance = self.context.borrower.outstanding_balance
            if self.context.payments:
                interest_paid = self.context.payments.total_interest_paid
                
        if "penalty" in msg_lower or "charge" in msg_lower:
            text = f"Hi {name}. A penalty of ₹{penalty_amount} has been charged because your account is {overdue_days} days overdue. This is per our late payment policy which applies from day 4 onwards."
        elif "ticket" in msg_lower or "create" in msg_lower:
            import time
            timestamp = int(time.time())
            text = f"I've created support ticket TKT{timestamp} for your penalty waiver request. Our team will review within 2 business days."
        elif "waive" in msg_lower or "waiver" in msg_lower or "bank" in msg_lower:
            text = "I understand the payment failure was due to a bank error. As per our waiver policy, bank-side failures are eligible for full waiver. I'll create a support ticket for this right away."
        elif "emi" in msg_lower or "remaining" in msg_lower or "installment" in msg_lower:
            text = f"You have {emis_remaining} EMIs remaining on your loan. Your next EMI of ₹{emi_amount} is due on {next_due_date}."
        elif "interest" in msg_lower:
            text = f"You've paid approximately ₹{interest_paid} in interest so far. Your outstanding balance is ₹{outstanding_balance}."
        elif any(k in msg_lower for k in ["salary", "pay", "friday", "next week"]):
            text = "I've noted your commitment. Could you confirm the exact date and amount you plan to pay?"
        else:
            text = f"Thank you for calling CredResolve. I have your account details ready. How can I help you today, {name}?"
        return MockMessages(
            content=[MockContentBlock(type="text", text=text)],
            stop_reason="end_turn"
        )

    def _run_agent_loop(self) -> str:
        """Executes the loop/call with Groq until a final text response is produced."""
        if self.is_mock:
            response = self._get_mock_response()
            result = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": result})
            return result
            
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "system", "content": self.system_prompt}] + self.conversation_history,
                max_tokens=300
            )
            result = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": result})
            return result
        except Exception as e:
            print(f"[API Error] Groq API failed: {e}. Falling back to mock mode.")
            self.is_mock = True
            response = self._get_mock_response()
            result = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": result})
            return result

    def chat(self, borrower_identifier: str, user_message: str) -> str:
        """Main interaction interface for borrower support agent chat turns."""
        self.last_tools_used = []
        
        # Build/refresh context
        context = self.context_engine.build_context(borrower_identifier)
        if not context:
            raise ValueError(f"Borrower profile for identifier '{borrower_identifier}' was not found in DB.")
        
        self.context = context
        self.current_borrower_id = context.borrower.borrower_id
        self.last_risk_signals = context.risk_signals
        
        # Formulate diagnosis
        diagnosis = self.diagnosis_layer.diagnose(context, user_message)
        self.last_intent = diagnosis.intent
        
        if not self.conversation_history:
            # Fetch policies from RAG
            rag_docs = self.rag_engine.retrieve_for_intent(diagnosis.intent, context.risk_signals)
            
            # Generate system instructions prompt
            self.system_prompt = self.build_system_prompt(context, diagnosis, rag_docs)
            
        self.conversation_history.append({"role": "user", "content": user_message})
        response = self._run_agent_loop()
        
        # Check if the response contains commitment keywords and borrower is overdue
        resp_lower = response.lower()
        keywords = ["friday", "pay by", "commit", "will pay", "next week"]
        if any(kw in resp_lower for kw in keywords) and self.context.borrower.overdue_days > 0:
            from core.memory_store import MemoryStore
            memory = MemoryStore()
            from datetime import datetime, timedelta
            commit_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            memory.save_commitment(self.current_borrower_id, self.context.borrower.emi_amount, commit_date, "Mentioned in conversation")
            print("💾 Commitment auto-saved to memory")
            
        return response

if __name__ == "__main__":
    # Test script for simulated conversation
    agent = BorrowerAgent()
    
    # Fetch an OVERDUE_15 borrower from the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT phone, name FROM borrowers WHERE delinquency_status = 'OVERDUE_15' LIMIT 1;")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print("No OVERDUE_15 borrower found in DB. Trying any borrower.")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT phone, name FROM borrowers LIMIT 1;")
        row = cursor.fetchone()
        conn.close()
        
    if row:
        phone, name = row
        print(f"Starting simulated chat session with: {name} (Phone: {phone})")
        if agent.is_mock:
            print("[INFO] Running in mock mode because GROQ_API_KEY is not configured.")
        print("=" * 60)
        
        # Turn 1
        print("User: \"Why was a penalty charged on my account?\"")
        reply1 = agent.chat(phone, "Why was a penalty charged on my account?")
        print(f"Agent: \"{reply1}\"\n")
        print("-" * 60)
        
        # Turn 2
        print("User: \"Can you waive the penalty? The payment failed because of a bank server error.\"")
        reply2 = agent.chat(phone, "Can you waive the penalty? The payment failed because of a bank server error.")
        print(f"Agent: \"{reply2}\"\n")
        print("-" * 60)
        
        # Turn 3
        print("User: \"Okay please create a ticket for the waiver request.\"")
        reply3 = agent.chat(phone, "Okay please create a ticket for the waiver request.")
        print(f"Agent: \"{reply3}\"\n")
        print("=" * 60)
    else:
        print("No borrower found in the database to run validation tests.")
