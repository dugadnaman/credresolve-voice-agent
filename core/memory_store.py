import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import json
import datetime
from dotenv import load_dotenv

# Load database path
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/borrowers.db")

class MemoryStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Creates the memory tables if they do not exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS borrower_memory (
                    memory_id TEXT PRIMARY KEY,
                    borrower_id TEXT,
                    memory_type TEXT,
                    key TEXT,
                    value TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
            """)
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
            conn.commit()
        finally:
            conn.close()

    def save_commitment(self, borrower_id: str, amount: float, date: str, reason: str) -> dict:
        """Saves or updates a promise-to-pay commitment for a borrower."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            value_dict = {
                "amount": amount,
                "date": date,
                "reason": reason,
                "fulfilled": False,
                "created_at": now_str
            }
            value_json = json.dumps(value_dict)
            
            cursor.execute("""
                SELECT memory_id FROM borrower_memory 
                WHERE borrower_id = ? AND memory_type = 'COMMITMENT' AND key = 'promise_to_pay'
            """, (borrower_id,))
            row = cursor.fetchone()
            
            if row:
                memory_id = row[0]
                cursor.execute("""
                    UPDATE borrower_memory 
                    SET value = ?, updated_at = ? 
                    WHERE memory_id = ?
                """, (value_json, now_str, memory_id))
            else:
                memory_id = f"MEM{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
                cursor.execute("""
                    INSERT INTO borrower_memory (memory_id, borrower_id, memory_type, key, value, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (memory_id, borrower_id, "COMMITMENT", "promise_to_pay", value_json, now_str, now_str))
            
            conn.commit()
            return {
                "status": "success",
                "memory_id": memory_id,
                "commitment": value_dict,
                "message": "Commitment saved successfully."
            }
        finally:
            conn.close()

    def mark_commitment_fulfilled(self, borrower_id: str) -> dict:
        """Marks the borrower's active promise-to-pay commitment as fulfilled."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT memory_id, value FROM borrower_memory 
                WHERE borrower_id = ? AND memory_type = 'COMMITMENT' AND key = 'promise_to_pay'
            """, (borrower_id,))
            row = cursor.fetchone()
            
            if not row:
                return {"status": "error", "message": "No active commitment found for this borrower."}
            
            memory_id, value_json = row
            value_dict = json.loads(value_json)
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            value_dict["fulfilled"] = True
            value_dict["fulfilled_at"] = now_str
            
            cursor.execute("""
                UPDATE borrower_memory 
                SET value = ?, updated_at = ? 
                WHERE memory_id = ?
            """, (json.dumps(value_dict), now_str, memory_id))
            conn.commit()
            
            return {
                "status": "success",
                "memory_id": memory_id,
                "message": "Commitment marked as fulfilled."
            }
        finally:
            conn.close()

    def save_preference(self, borrower_id: str, key: str, value: str) -> None:
        """Saves a borrower preference detail (e.g. language, best call time) as an upsert."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                SELECT memory_id FROM borrower_memory 
                WHERE borrower_id = ? AND memory_type = 'PREFERENCE' AND key = ?
            """, (borrower_id, key))
            row = cursor.fetchone()
            
            if row:
                memory_id = row[0]
                cursor.execute("""
                    UPDATE borrower_memory 
                    SET value = ?, updated_at = ? 
                    WHERE memory_id = ?
                """, (value, now_str, memory_id))
            else:
                memory_id = f"MEM{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
                cursor.execute("""
                    INSERT INTO borrower_memory (memory_id, borrower_id, memory_type, key, value, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (memory_id, borrower_id, "PREFERENCE", key, value, now_str, now_str))
            
            conn.commit()
        finally:
            conn.close()

    def get_borrower_memory(self, borrower_id: str) -> dict:
        """Retrieves and segments all stored memories associated with a borrower."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM borrower_memory WHERE borrower_id = ?", (borrower_id,))
            rows = cursor.fetchall()
            
            commitments = []
            preferences = {}
            risk_notes = []
            callbacks = []
            
            for r in rows:
                r_dict = dict(r)
                m_type = r_dict["memory_type"]
                if m_type == "COMMITMENT":
                    commitments.append(r_dict)
                elif m_type == "PREFERENCE":
                    preferences[r_dict["key"]] = r_dict["value"]
                elif m_type == "RISK":
                    risk_notes.append(r_dict)
                elif m_type == "CALLBACK":
                    callbacks.append(r_dict)
                    
            return {
                "commitments": commitments,
                "preferences": preferences,
                "risk_notes": risk_notes,
                "callbacks": callbacks
            }
        finally:
            conn.close()

    def save_resolution_path(self, borrower_id: str, intent: str, tools_used: list, outcome: str) -> None:
        """Saves tool execution patterns and outcomes for operational analytical learning."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            memory_id = f"MEM{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            value_json = json.dumps({
                "tools_used": tools_used,
                "outcome": outcome,
                "timestamp": now_str
            })
            
            cursor.execute("""
                INSERT INTO agent_memory (memory_id, borrower_id, memory_type, key, value, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (memory_id, borrower_id, "RESOLUTION_PATH", intent, value_json, now_str))
            conn.commit()
        finally:
            conn.close()

    def get_successful_resolution_paths(self, intent: str) -> list:
        """Retrieves history of successful agent resolution paths for a specific intent."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT value FROM agent_memory 
                WHERE memory_type = 'RESOLUTION_PATH' AND key = ?
            """, (intent,))
            rows = cursor.fetchall()
            
            successful_paths = []
            for r in rows:
                try:
                    data = json.loads(r[0])
                    if data.get("outcome") == "RESOLVED":
                        successful_paths.append({
                            "tools_used": data.get("tools_used"),
                            "timestamp": data.get("timestamp")
                        })
                except Exception:
                    pass
            return successful_paths
        finally:
            conn.close()

    def build_memory_prompt(self, borrower_id: str) -> str:
        """Constructs an LLM system prompt segment containing user history, unfulfilled payments, and notes."""
        mem = self.get_borrower_memory(borrower_id)
        
        has_memory = (
            len(mem["commitments"]) > 0 or 
            len(mem["preferences"]) > 0 or 
            len(mem["risk_notes"]) > 0 or 
            len(mem["callbacks"]) > 0
        )
        if not has_memory:
            return ""
        
        prompt = []
        prompt.append("=== BORROWER MEMORY ===")
        
        # Extract unfulfilled commitments
        unfulfilled_commits = []
        for c in mem["commitments"]:
            try:
                c_val = json.loads(c["value"])
                if not c_val.get("fulfilled", False):
                    unfulfilled_commits.append(c_val)
            except Exception:
                pass
                
        if unfulfilled_commits:
            first_commit = unfulfilled_commits[0]
            prompt.append(f"⚠️ PREVIOUS COMMITMENT: This borrower committed to paying ₹{first_commit['amount']:.2f} by {first_commit['date']}. Check if fulfilled.")
            prompt.append("")
            prompt.append("Unfulfilled Commitments:")
            for commit in unfulfilled_commits:
                prompt.append(f"  - Commitment to pay ₹{commit['amount']:.2f} on {commit['date']} (Reason: {commit['reason']})")
            prompt.append("")
            
        if mem["preferences"]:
            prompt.append("Preferences:")
            for k, v in mem["preferences"].items():
                prompt.append(f"  - {k}: {v}")
            prompt.append("")
            
        if mem["risk_notes"]:
            prompt.append("Risk Notes:")
            for note in mem["risk_notes"]:
                prompt.append(f"  - {note['value']} (Recorded: {note['created_at']})")
            prompt.append("")
            
        if mem["callbacks"]:
            prompt.append("Scheduled Callbacks:")
            for cb in mem["callbacks"]:
                prompt.append(f"  - Date: {cb['key']} | Reason: {cb['value']}")
            prompt.append("")
            
        return "\n".join(prompt)

if __name__ == "__main__":
    store = MemoryStore()
    
    # Fetch a sample borrower
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT borrower_id, name, emi_amount FROM borrowers LIMIT 1;")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        borrower_id, name, emi_amount = row
        first_name = name.split()[0]
        
        # Step 1: Simulate first call
        print("=== FIRST CALL ===")
        commitment_date = (datetime.date.today() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        
        save_res = store.save_commitment(
            borrower_id=borrower_id,
            amount=emi_amount,
            date=commitment_date,
            reason="Salary delayed"
        )
        print("Commitment saved:")
        print(json.dumps(save_res, indent=2))
        print("\nGenerated Prompt for First Call:")
        print(store.build_memory_prompt(borrower_id))
        print("=" * 60)
        
        # Step 2: Simulate second call
        print("=== SECOND CALL (3 days later) ===")
        print(store.build_memory_prompt(borrower_id))
        print("\nAgent opening: Hi " + first_name + ", I see you committed to paying your EMI of ₹" + f"{emi_amount:,.2f}" + " by " + commitment_date + " due to a salary delay. Were you able to make that payment?")
        print("=" * 60)
    else:
        print("No borrowers found in database to run memory scenario tests.")
