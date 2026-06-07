import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
import sqlite3
import json
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "data/borrowers.db")

# ── SYSTEM 1: CRM (simulates Zoho CRM) ───────────────────────
class CRMSystem:
    """Simulates Zoho CRM - stores borrower profile and KYC data"""
    system_name = "Zoho CRM (Mock)"
    
    def get_borrower_profile(self, phone: str) -> dict:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT borrower_id, name, phone, email, city, kyc_status, pan_number, bank_name FROM borrowers WHERE phone=?",
            (phone,)
        ).fetchone()
        conn.close()
        if not row:
            return {"error": "Borrower not found in CRM"}
        return {"source": self.system_name, "data": dict(row)}
    
    def update_borrower_notes(self, borrower_id: str, note: str) -> dict:
        # In real system: would update Zoho CRM via API
        return {"source": self.system_name, "status": "updated", "note": note, "borrower_id": borrower_id}

# ── SYSTEM 2: Loan Management System (simulates Finflux/Nucleus) ──
class LoanManagementSystem:
    """Simulates Loan Management System - stores loan details and EMI schedule"""
    system_name = "Loan Management System (Mock)"
    
    def get_loan_details(self, borrower_id: str) -> dict:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT loan_id, loan_type, loan_amount, interest_rate, tenure_months, emi_amount, loan_start_date, loan_end_date, outstanding_balance, delinquency_status, overdue_days, penalty_amount FROM borrowers WHERE borrower_id=?",
            (borrower_id,)
        ).fetchone()
        conn.close()
        if not row:
            return {"error": "Loan not found"}
        return {"source": self.system_name, "data": dict(row)}
    
    def get_emi_schedule(self, borrower_id: str) -> dict:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT loan_start_date, tenure_months, emi_amount FROM borrowers WHERE borrower_id=?",
            (borrower_id,)
        ).fetchone()
        conn.close()
        if not row:
            return {"error": "Not found"}
        start = datetime.strptime(row[0], "%Y-%m-%d")
        emis_paid = min((datetime.now() - start).days // 30, row[1])
        return {
            "source": self.system_name,
            "emis_paid": emis_paid,
            "emis_remaining": row[1] - emis_paid,
            "emi_amount": row[2]
        }

# ── SYSTEM 3: Payment Gateway (simulates Razorpay) ───────────
class PaymentGatewaySystem:
    """Simulates Razorpay payment gateway - stores transaction history"""
    system_name = "Razorpay Gateway (Mock)"
    
    def get_payment_history(self, borrower_id: str, limit: int = 10) -> dict:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT payment_id, due_date, payment_date, amount_due, amount_paid, status, failure_reason, gateway_ref, channel FROM payments WHERE borrower_id=? ORDER BY due_date DESC LIMIT ?",
            (borrower_id, limit)
        ).fetchall()
        conn.close()
        return {
            "source": self.system_name,
            "transactions": [dict(r) for r in rows],
            "total_fetched": len(rows)
        }
    
    def get_failure_details(self, borrower_id: str) -> dict:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT payment_id, due_date, failure_reason, status FROM payments WHERE borrower_id=? AND status IN ('FAILED','AUTO_DEBIT_FAIL','MISSED') ORDER BY due_date DESC LIMIT 5",
            (borrower_id,)
        ).fetchall()
        conn.close()
        return {"source": self.system_name, "failures": [dict(r) for r in rows]}

# ── SYSTEM 4: Support Ticketing (simulates Freshdesk) ────────
class SupportTicketingSystem:
    """Simulates Freshdesk - stores and manages support tickets"""
    system_name = "Freshdesk (Mock)"
    
    def get_tickets(self, borrower_id: str) -> dict:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ticket_id, category, subject, status, priority, created_date, resolved_date FROM tickets WHERE borrower_id=? ORDER BY created_date DESC",
            (borrower_id,)
        ).fetchall()
        conn.close()
        return {"source": self.system_name, "tickets": [dict(r) for r in rows]}
    
    def create_ticket(self, borrower_id: str, category: str, subject: str, description: str) -> dict:
        conn = sqlite3.connect(DB_PATH)
        ticket_id = f"TKT{int(datetime.now().timestamp())}"
        priority = "HIGH" if category in ("PENALTY_WAIVER", "SETTLEMENT") else "MEDIUM"
        conn.execute(
            "INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ticket_id, borrower_id, None, category, subject, description, "OPEN", priority,
             datetime.now().strftime("%Y-%m-%d"), None, None)
        )
        conn.commit()
        conn.close()
        return {"source": self.system_name, "ticket_id": ticket_id, "status": "OPEN", "priority": priority}

# ── SYSTEM 5: Knowledge Base (simulates Confluence) ──────────
class KnowledgeBaseSystem:
    """Simulates Confluence knowledge base - stores policy documents"""
    system_name = "Confluence KB (Mock)"
    KB_PATH = os.getenv("KB_PATH", "data/knowledge_base")
    
    def search_policies(self, query: str) -> dict:
        from core.rag_engine import RAGEngine
        rag = RAGEngine()
        results = rag.retrieve(query, top_k=2)
        return {
            "source": self.system_name,
            "results": [{"id": r.id, "title": r.title, "snippet": r.relevant_snippet} for r in results]
        }
    
    def get_all_documents(self) -> dict:
        import pathlib
        docs = list(pathlib.Path(self.KB_PATH).glob("*.json"))
        return {"source": self.system_name, "document_count": len(docs), "documents": [d.stem for d in docs]}

# ── UNIFIED DATA AGGREGATOR ───────────────────────────────────
class UnifiedDataAggregator:
    """
    Aggregates data from all 5 systems into one borrower profile.
    This is what the Context Engine calls.
    """
    def __init__(self):
        self.crm        = CRMSystem()
        self.lms        = LoanManagementSystem()
        self.payments   = PaymentGatewaySystem()
        self.ticketing  = SupportTicketingSystem()
        self.knowledge  = KnowledgeBaseSystem()
        self.systems    = [self.crm, self.lms, self.payments, self.ticketing, self.knowledge]
    
    def get_unified_profile(self, phone: str) -> dict:
        """Calls all 5 systems and merges into one profile"""
        # Get borrower_id first
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT borrower_id FROM borrowers WHERE phone=?", (phone,)).fetchone()
        conn.close()
        if not row:
            return {"error": "Borrower not found"}
        borrower_id = row[0]
        
        return {
            "aggregated_at": datetime.now().isoformat(),
            "systems_queried": [s.system_name for s in self.systems],
            "crm_profile":      self.crm.get_borrower_profile(phone),
            "loan_details":     self.lms.get_loan_details(borrower_id),
            "payment_history":  self.payments.get_payment_history(borrower_id, limit=5),
            "support_tickets":  self.ticketing.get_tickets(borrower_id),
            "knowledge_base":   self.knowledge.get_all_documents()
        }

# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    agg = UnifiedDataAggregator()
    
    conn = sqlite3.connect(DB_PATH)
    phone = conn.execute("SELECT phone FROM borrowers LIMIT 1").fetchone()[0]
    conn.close()
    
    print(f"Testing UnifiedDataAggregator for phone: {phone}")
    print(f"Systems connected: 5")
    print()
    
    profile = agg.get_unified_profile(phone)
    print(f"Systems queried: {profile['systems_queried']}")
    print(f"CRM: {profile['crm_profile']['data']['name']}")
    print(f"Loan: {profile['loan_details']['data']['loan_type']} - ₹{profile['loan_details']['data']['loan_amount']:,.0f}")
    print(f"Payments fetched: {profile['payment_history']['total_fetched']}")
    print(f"Tickets fetched: {len(profile['support_tickets']['tickets'])}")
    print(f"KB documents: {profile['knowledge_base']['document_count']}")
    print()
    print("✅ All 5 systems responding. Multi-system integration complete.")
