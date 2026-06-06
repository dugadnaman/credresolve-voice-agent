import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
import anthropic
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
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

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
        
        # Check if we should run in mock mode
        self.is_mock = not ANTHROPIC_API_KEY or "your_key_here" in ANTHROPIC_API_KEY
        
        if not self.is_mock:
            self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        else:
            self.client = None
            
        self.conversation_history = []
        self.current_borrower_id = None
        self.system_prompt = None
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
        history_len = len(self.conversation_history)
        
        if history_len == 1:
            # Turn 1: User asked "Why was a penalty charged..."
            # Request tool call get_penalty_details
            return MockMessages(
                content=[MockContentBlock(type="tool_use", id="mock_u_1", name="get_penalty_details", input={})],
                stop_reason="tool_use"
            )
        elif history_len == 3:
            # Turn 1 (follow-up): Tool result received. Explain late charges.
            return MockMessages(
                content=[MockContentBlock(type="text", text="Hi Arjun. A late fee penalty of ₹550.00 was charged because your payment due in May was missed, and your loan is currently 11 days overdue. We also recorded an auto-debit bounce charge.")],
                stop_reason="end_turn"
            )
        elif history_len == 5:
            # Turn 2: User asks for a waiver
            # Request tool call search_knowledge_base
            return MockMessages(
                content=[MockContentBlock(type="tool_use", id="mock_u_2", name="search_knowledge_base", input={"query": "penalty waiver bank error"})],
                stop_reason="tool_use"
            )
        elif history_len == 7:
            # Turn 2 (follow-up): Tool result received. Explain waiver conditions.
            return MockMessages(
                content=[MockContentBlock(type="text", text="According to our penalty waiver policy, a waiver is considered if the late payment resulted from a bank or gateway server error rather than user shortage of funds. Since you indicated there was a server glitch, we can raise a support ticket to initiate a waiver request. Would you like me to create this ticket now?")],
                stop_reason="end_turn"
            )
        elif history_len == 9:
            # Turn 3: User says to create ticket
            # Request tool call create_ticket
            return MockMessages(
                content=[MockContentBlock(type="tool_use", id="mock_u_3", name="create_ticket", input={
                    "category": "PENALTY_WAIVER",
                    "subject": "Late Fee Waiver Request - Bank Server Error",
                    "description": "Borrower requested waiver of ₹550 late fee. Stated the auto-debit bounced due to bank gateway failure on the due date."
                })],
                stop_reason="tool_use"
            )
        elif history_len == 11:
            # Turn 3 (follow-up): Tool result received. Confirm ticket creation.
            return MockMessages(
                content=[MockContentBlock(type="text", text="I have successfully created support ticket TKT-WAIVER-2026 for you. Our credit committee will review the bank transmission failure and get back to you within 2 business days. Is there anything else I can help you with today?")],
                stop_reason="end_turn"
            )
        else:
            return MockMessages(
                content=[MockContentBlock(type="text", text="I'm here to assist you. Please let me know what query you have.")],
                stop_reason="end_turn"
            )

    def _run_agent_loop(self) -> str:
        """Executes the tool usage handling loop with Claude until a final text response is produced."""
        while True:
            if self.is_mock:
                response = self._get_mock_response()
            else:
                response = self.client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=1024,
                    system=self.system_prompt,
                    tools=TOOL_DEFINITIONS,
                    messages=self.conversation_history
                )
                
            content_list = []
            tool_calls = []
            final_text = ""
            
            for block in response.content:
                # Handle both SDK object blocks and mock dictionary/object blocks
                b_type = getattr(block, "type", None) or block.type
                if b_type == "text":
                    b_text = getattr(block, "text", None) or block.text
                    content_list.append({"type": "text", "text": b_text})
                    final_text = b_text
                elif b_type == "tool_use":
                    b_id = getattr(block, "id", None) or block.id
                    b_name = getattr(block, "name", None) or block.name
                    b_input = getattr(block, "input", None) or block.input
                    content_list.append({
                        "type": "tool_use",
                        "id": b_id,
                        "name": b_name,
                        "input": b_input
                    })
                    tool_calls.append(block)
                    
            self.conversation_history.append({"role": "assistant", "content": content_list})
            
            # Handle tool use branch
            if response.stop_reason == "tool_use":
                tool_results_content = []
                for tool in tool_calls:
                    t_name = getattr(tool, "name", None) or tool.name
                    t_input = getattr(tool, "input", None) or tool.input
                    t_id = getattr(tool, "id", None) or tool.id
                    
                    # Run target tool code and serialize output
                    result_str = self.handle_tool_call(t_name, t_input)
                    
                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": t_id,
                        "content": result_str
                    })
                self.conversation_history.append({"role": "user", "content": tool_results_content})
            else:
                # Return text message once LLM finishes call actions
                return final_text

    def chat(self, borrower_identifier: str, user_message: str) -> str:
        """Main interaction interface for borrower support agent chat turns."""
        self.last_tools_used = []
        
        # Build/refresh context
        context = self.context_engine.build_context(borrower_identifier)
        if not context:
            raise ValueError(f"Borrower profile for identifier '{borrower_identifier}' was not found in DB.")
        
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
        return self._run_agent_loop()

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
            print("[INFO] Running in mock mode because ANTHROPIC_API_KEY is not configured.")
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
