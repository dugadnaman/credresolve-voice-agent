import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import json
import datetime
import math
from dotenv import load_dotenv

# Load database path
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/borrowers.db")

def get_loan_details(borrower_id: str) -> dict:
    """Retrieves loan schedule and details for a borrower."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM borrowers WHERE borrower_id = ?", (borrower_id,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Borrower {borrower_id} not found."}
        
        # Compute EMIs paid, remaining, next due date
        loan_start_date = row["loan_start_date"]
        tenure_months = row["tenure_months"]
        overdue_days = row["overdue_days"]
        
        loan_start_date_dt = datetime.datetime.strptime(loan_start_date, "%Y-%m-%d").date()
        today = datetime.date.today()
        
        months_elapsed = (today.year - loan_start_date_dt.year) * 12 + (today.month - loan_start_date_dt.month)
        if today.day < loan_start_date_dt.day:
            months_elapsed -= 1
        months_elapsed = max(0, months_elapsed)
        
        num_missed = int(math.ceil(overdue_days / 30.0)) if overdue_days > 0 else 0
        emis_paid = max(0, months_elapsed - num_missed)
        emis_paid = min(emis_paid, tenure_months)
        
        emis_remaining = tenure_months - emis_paid
        
        next_due_date_dt = loan_start_date_dt + datetime.timedelta(days=(emis_paid + 1) * 30)
        next_due_date = next_due_date_dt.strftime("%Y-%m-%d")
        
        return {
            "loan_id": row["loan_id"],
            "loan_type": row["loan_type"],
            "loan_amount": row["loan_amount"],
            "interest_rate": row["interest_rate"],
            "tenure_months": row["tenure_months"],
            "emi_amount": row["emi_amount"],
            "loan_start_date": row["loan_start_date"],
            "loan_end_date": row["loan_end_date"],
            "outstanding_balance": row["outstanding_balance"],
            "emis_paid": emis_paid,
            "emis_remaining": emis_remaining,
            "next_due_date": next_due_date
        }
    finally:
        conn.close()

def get_payment_history(borrower_id: str, limit: int = 10) -> dict:
    """Retrieves the recent payment history of a borrower."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT due_date, payment_date, amount_due, amount_paid, status, failure_reason, channel 
            FROM payments 
            WHERE borrower_id = ? 
            ORDER BY due_date DESC 
            LIMIT ?
        """, (borrower_id, limit))
        rows = cursor.fetchall()
        
        payments_list = []
        status_counts = {}
        for r in rows:
            p_dict = dict(r)
            payments_list.append(p_dict)
            status = p_dict["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
            
        return {
            "payments": payments_list,
            "summary": status_counts
        }
    finally:
        conn.close()

def get_penalty_details(borrower_id: str) -> dict:
    """Retrieves penalty details and details of the last payment failure."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT penalty_amount, overdue_days, delinquency_status FROM borrowers WHERE borrower_id = ?", (borrower_id,))
        brow = cursor.fetchone()
        if not brow:
            return {"error": f"Borrower {borrower_id} not found."}
        
        cursor.execute("""
            SELECT failure_reason, payment_date 
            FROM payments 
            WHERE borrower_id = ? AND status in ('FAILED', 'AUTO_DEBIT_FAIL') 
            ORDER BY due_date DESC 
            LIMIT 1
        """, (borrower_id,))
        prow = cursor.fetchone()
        
        last_failure_reason = prow["failure_reason"] if prow else None
        last_failure_date = prow["payment_date"] if prow else None
        
        return {
            "penalty_amount": brow["penalty_amount"],
            "overdue_days": brow["overdue_days"],
            "delinquency_status": brow["delinquency_status"],
            "last_failure_reason": last_failure_reason,
            "last_failure_date": last_failure_date,
            "penalty_policy_summary": "2% per month for days 4-15, 3% for days 16-30, 4% for days 31-60"
        }
    finally:
        conn.close()

def create_ticket(borrower_id: str, category: str, subject: str, description: str) -> dict:
    """Creates a support ticket in the database."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT loan_id FROM borrowers WHERE borrower_id = ?", (borrower_id,))
        row = cursor.fetchone()
        loan_id = row[0] if row else None
        
        ticket_id = f"TKT{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        priority = "HIGH" if category in ("PENALTY_WAIVER", "SETTLEMENT") else "MEDIUM"
        created_date = datetime.date.today().strftime("%Y-%m-%d")
        
        cursor.execute("""
            INSERT INTO tickets (ticket_id, borrower_id, loan_id, category, subject, description, status, priority, created_date, resolved_date, resolution_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticket_id, borrower_id, loan_id, category, subject, description, "OPEN", priority, created_date, None, None))
        conn.commit()
        
        return {
            "ticket_id": ticket_id,
            "status": "OPEN",
            "message": f"Support ticket {ticket_id} created successfully under category {category}."
        }
    finally:
        conn.close()

def generate_payment_link(borrower_id: str, amount: float) -> dict:
    """Generates a secure mock payment link."""
    mock_id = f"MOCK{datetime.datetime.now().strftime('%M%S%f')[:6]}"
    return {
        "payment_link": f"https://pay.credresolve.com/pay?id={mock_id}&amount={amount:.2f}",
        "amount": amount,
        "expires_in": "24 hours",
        "instructions": "Click the link to pay securely using UPI, NetBanking, or Debit Card."
    }

def schedule_callback(borrower_id: str, callback_date: str, reason: str) -> dict:
    """Schedules a borrower callback and saves it to agent memory."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_memory (
                memory_id TEXT PRIMARY KEY,
                borrower_id TEXT,
                memory_type TEXT,
                key TEXT,
                value TEXT,
                created_at TEXT
            );
        """)
        memory_id = f"MEM{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO agent_memory (memory_id, borrower_id, memory_type, key, value, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (memory_id, borrower_id, "CALLBACK", callback_date, reason, created_at))
        conn.commit()
        
        return {
            "message": f"Callback scheduled successfully for {callback_date}.",
            "callback_date": callback_date,
            "reason": reason
        }
    finally:
        conn.close()

def escalate_to_human(borrower_id: str, reason: str, priority: str = "HIGH") -> dict:
    """Escalates borrower call to a human agent."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT loan_id FROM borrowers WHERE borrower_id = ?", (borrower_id,))
        row = cursor.fetchone()
        loan_id = row[0] if row else None
        
        ticket_id = f"TKT{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        created_date = datetime.date.today().strftime("%Y-%m-%d")
        
        cursor.execute("""
            INSERT INTO tickets (ticket_id, borrower_id, loan_id, category, subject, description, status, priority, created_date, resolved_date, resolution_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticket_id, borrower_id, loan_id, "ESCALATION", f"Human Escalation: {reason}", reason, "OPEN", priority, created_date, None, None))
        conn.commit()
        
        return {
            "ticket_id": ticket_id,
            "message": "Escalating to human agent. Expected wait time: 5-10 minutes.",
            "priority": priority
        }
    finally:
        conn.close()

def search_knowledge_base(borrower_id: str, query: str = None) -> dict:
    """Searches the policies and FAQ database for relevant snippets."""
    if query is None:
        query = borrower_id
    from core.rag_engine import RAGEngine
    engine = RAGEngine()
    docs = engine.retrieve(query, top_k=2)
    results = []
    for doc in docs:
        results.append({
            "title": doc.title,
            "content": doc.content[:500],
            "category": doc.category
        })
    return {"results": results}

# Tool definitions in Anthropic format
TOOL_DEFINITIONS = [
    {
        "name": "get_loan_details",
        "description": "Retrieves the financial and schedule details of the borrower's loan, including EMI amounts, outstanding balance, start/end dates, and payment counts.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_payment_history",
        "description": "Retrieves the past payments logged for the borrower, including payment date, amount due, amount paid, status, failure reasons, and channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of payment records to retrieve (default: 10).",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "get_penalty_details",
        "description": "Retrieves details of late fees or penalties applied to the borrower's account, including overdue days, delinquency status, and details of the last payment failure.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "create_ticket",
        "description": "Creates a support ticket for requests like penalty waivers, settlements, foreclosure letters, or disputes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["EMI_DISPUTE", "SETTLEMENT", "FORECLOSURE", "PAYMENT_FAILURE", "PENALTY_WAIVER", "GENERAL"],
                    "description": "The category of the ticket."
                },
                "subject": {
                    "type": "string",
                    "description": "Brief subject summarizing the request."
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the issue or request."
                }
            },
            "required": ["category", "subject", "description"]
        }
    },
    {
        "name": "generate_payment_link",
        "description": "Generates a mock payment link for the borrower to clear outstanding dues or pay EMIs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "The amount for the payment link."
                }
            },
            "required": ["amount"]
        }
    },
    {
        "name": "schedule_callback",
        "description": "Schedules a follow-up callback call for the borrower.",
        "input_schema": {
            "type": "object",
            "properties": {
                "callback_date": {
                    "type": "string",
                    "description": "The date for the callback (format: YYYY-MM-DD)."
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for the callback."
                }
            },
            "required": ["callback_date", "reason"]
        }
    },
    {
        "name": "escalate_to_human",
        "description": "Escalates the borrower to a human support agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for escalation."
                },
                "priority": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    "description": "Escalation priority.",
                    "default": "HIGH"
                }
            },
            "required": ["reason"]
        }
    },
    {
        "name": "search_knowledge_base",
        "description": "Searches the policy and FAQ knowledge base for information relating to waivers, settlements, foreclosure, interest, NACH setup, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query string to search for in the policy docs."
                }
            },
            "required": ["query"]
        }
    }
]
