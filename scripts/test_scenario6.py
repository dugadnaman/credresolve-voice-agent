import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from core.memory_store import MemoryStore
from core.context_engine import ContextEngine
from agent.agent import BorrowerAgent

# Step 1 - Get a real OVERDUE_15 borrower from DB:
conn = sqlite3.connect("data/borrowers.db")
row = conn.execute("SELECT borrower_id, name, phone, emi_amount FROM borrowers WHERE delinquency_status='OVERDUE_15' LIMIT 1").fetchone()
conn.close()
borrower_id, name, phone, emi_amount = row

# Step 2 - Simulate FIRST CALL:
print("=" * 60)
print("SCENARIO 6 - FIRST CALL")
print("=" * 60)
print(f"Borrower: {name} | Phone: {phone}")
print("")

# Create BorrowerAgent and simulate:
agent1 = BorrowerAgent()
response1 = agent1.chat(phone, "My salary got delayed. I will pay my overdue EMI next Friday.")
print(f"User: My salary got delayed. I will pay my overdue EMI next Friday.")
print(f"Agent: {response1}")

# Then save commitment to memory:
memory = MemoryStore()
from datetime import datetime, timedelta
friday = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
result = memory.save_commitment(borrower_id, emi_amount, friday, "Salary delayed")
print(f"\n✅ Commitment saved: Pay ₹{emi_amount} by {friday}")

# Step 3 - Show memory prompt:
print("")
print("MEMORY STORED AFTER FIRST CALL:")
print(memory.build_memory_prompt(borrower_id))

# Step 4 - Simulate SECOND CALL (3 days later):
print("=" * 60)
print("SCENARIO 6 - SECOND CALL (3 days later)")
print("=" * 60)

agent2 = BorrowerAgent()
opening = agent2.chat(phone, "hello")
print(f"User: Hello")
print(f"Agent: {opening}")
print("")

followup = agent2.chat(phone, "I wanted to ask about my account")
print(f"User: I wanted to ask about my account")
print(f"Agent: {followup}")

# Step 5 - Verify memory was used:
print("")
print("MEMORY CHECK:")
mem = memory.get_borrower_memory(borrower_id)
if mem["commitments"]:
    print(f"✅ Commitment found in memory: {mem['commitments'][0]}")
else:
    print("❌ No commitment in memory")

print("")
print("=" * 60)
print("Scenario 6 test complete.")
print("=" * 60)
