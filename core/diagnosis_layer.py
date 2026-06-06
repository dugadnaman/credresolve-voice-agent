import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Any
from core.context_engine import BorrowerContext, ContextEngine, DB_PATH

@dataclass
class DiagnosisResult:
    intent: str
    confidence: float
    known_facts: List[str]
    missing_info: List[str]
    next_question: str
    can_resolve_immediately: bool
    suggested_tools: List[str]
    resolution_hint: str

class DiagnosisLayer:
    @staticmethod
    def diagnose(context: BorrowerContext, user_utterance: str) -> DiagnosisResult:
        bp = context.borrower
        ps = context.payments
        ts = context.tickets
        cs = context.conversations
        
        utterance_lower = user_utterance.lower()
        
        # Intent keywords configuration
        keywords_by_intent = {
            "EMI_INQUIRY": ["emi", "installment", "how many", "remaining", "left", "tenure", "due date", "next payment"],
            "INTEREST_INQUIRY": ["interest", "how much interest", "interest paid", "principal"],
            "PENALTY_INQUIRY": ["penalty", "charge", "fine", "extra charge", "why charged", "late fee"],
            "PAYMENT_FAILURE": ["payment failed", "not debited", "deducted but", "failed", "not credited", "balance was there", "bank issue", "glitch"],
            "PENALTY_WAIVER": ["waive", "waiver", "remove penalty", "cancel penalty", "bank's fault", "not my fault", "reverse"],
            "SETTLEMENT_REQUEST": ["settle", "settlement", "one time", "close the loan", "lump sum", "can't pay full"],
            "PAYMENT_COMMITMENT": ["will pay", "pay by", "salary", "next week", "friday", "promise", "few days", "pay soon", "transfer"]
        }
        
        # Count matching keywords
        match_counts = {}
        for intent_name, keywords in keywords_by_intent.items():
            count = 0
            for kw in keywords:
                if kw in utterance_lower:
                    count += 1
            if count > 0:
                match_counts[intent_name] = count
                
        # Resolve intent
        if not match_counts:
            intent = "GENERAL_INQUIRY"
            confidence = 0.5
        else:
            intent = max(match_counts, key=match_counts.get)
            confidence = 0.90
            
        known_facts = []
        missing_info = []
        next_question = ""
        can_resolve_immediately = False
        suggested_tools = []
        resolution_hint = ""
        
        # Exact logic for each of the 8 intents
        if intent == "EMI_INQUIRY":
            known_facts = [
                f"EMIs Paid: {bp.emis_paid}",
                f"EMIs Remaining: {bp.emis_remaining}",
                f"Next Due Date: {bp.next_due_date}",
                f"EMI Amount: ₹{bp.emi_amount:,.2f}"
            ]
            missing_info = []
            can_resolve_immediately = True
            suggested_tools = ["get_loan_details"]
            resolution_hint = f"Tell borrower {bp.emis_remaining} EMIs are left, next due on {bp.next_due_date}, amount {bp.emi_amount}"
            
        elif intent == "INTEREST_INQUIRY":
            known_facts = [
                f"Total Interest Paid: ₹{ps.total_interest_paid:,.2f}",
                f"Total Principal Paid: ₹{ps.total_principal_paid:,.2f}",
                f"Outstanding Balance: ₹{bp.outstanding_balance:,.2f}"
            ]
            missing_info = []
            can_resolve_immediately = True
            suggested_tools = ["get_payment_history"]
            resolution_hint = f"Tell borrower total interest paid so far (₹{ps.total_interest_paid:,.2f}) and outstanding balance (₹{bp.outstanding_balance:,.2f})"
            
        elif intent == "PENALTY_INQUIRY":
            known_facts = [
                f"Penalty Amount: ₹{bp.penalty_amount:,.2f}",
                f"Overdue Days: {bp.overdue_days}",
                f"Delinquency Status: {bp.delinquency_status}"
            ]
            if bp.penalty_amount > 0:
                if ps.recent_failures:
                    missing_info = []
                else:
                    missing_info = ["reason for payment failure"]
            else:
                missing_info = []
            
            can_resolve_immediately = True  # penalty_amount is always a float in context, hence known
            suggested_tools = ["get_penalty_details", "search_knowledge_base"]
            resolution_hint = "Explain penalty amount, why it was charged based on overdue days, retrieve policy via RAG"
            
        elif intent == "PAYMENT_FAILURE":
            known_facts = [
                f"Last Payment Status: {ps.last_payment_status}",
                f"Last Failure Reason: {ps.last_failure_reason}",
                f"Last Payment Date: {ps.last_payment_date}"
            ]
            if not ps.last_failure_reason:
                missing_info.append("reason for failure from bank/gateway")
            elif "balance" in ps.last_failure_reason.lower() or "funds" in ps.last_failure_reason.lower():
                missing_info.append("confirmation of balance at time of transaction")
                
            can_resolve_immediately = False if missing_info else True
            suggested_tools = ["get_payment_history", "search_knowledge_base", "create_ticket"]
            resolution_hint = "Investigate failure reason, classify as bank-side vs borrower-side, suggest retry or waiver if bank-side"
            
        elif intent == "PENALTY_WAIVER":
            known_facts = [
                f"Penalty Amount: ₹{bp.penalty_amount:,.2f}",
                f"Last Failure Reason: {ps.last_failure_reason}",
                f"Successful Payments: {ps.successful_payments}"
            ]
            if not ps.last_failure_reason:
                missing_info.append("documented proof of bank/gateway error")
            missing_info.append("borrower's confirmation of the specific failed payment date")
            
            can_resolve_immediately = False
            suggested_tools = ["get_penalty_details", "search_knowledge_base", "create_ticket"]
            resolution_hint = "Check waiver eligibility: bank-side error + good history = likely eligible. Create ticket if eligible."
            
        elif intent == "SETTLEMENT_REQUEST":
            known_facts = [
                f"Outstanding Balance: ₹{bp.outstanding_balance:,.2f}",
                f"Delinquency Status: {bp.delinquency_status}",
                f"Overdue Days: {bp.overdue_days}"
            ]
            missing_info = [
                "reason for settlement request",
                "current monthly income or financial situation"
            ]
            can_resolve_immediately = False
            suggested_tools = ["get_loan_details", "search_knowledge_base", "create_ticket", "escalate_to_human"]
            resolution_hint = "Explain settlement process and impact on CIBIL. Collect reason. Create ticket and escalate to human agent."
            
        elif intent == "PAYMENT_COMMITMENT":
            known_facts = [
                f"Outstanding Balance: ₹{bp.outstanding_balance:,.2f}",
                f"Overdue Days: {bp.overdue_days}",
                f"EMI Amount: ₹{bp.emi_amount:,.2f}"
            ]
            
            # Simple heuristic detection for date and amount in user utterance
            has_date = False
            date_keywords = ["today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "next week", "week", "month", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "day", "date"]
            if any(kw in utterance_lower for kw in date_keywords):
                has_date = True
                
            has_amount = False
            if any(char.isdigit() for char in user_utterance) or any(kw in utterance_lower for kw in ["rupee", "rs", "inr", "full", "half", "entire"]):
                has_amount = True
                
            if not has_date:
                missing_info.append("exact date of payment")
            if not has_amount:
                missing_info.append("exact amount to be paid")
                
            can_resolve_immediately = True
            suggested_tools = ["get_loan_details", "schedule_callback"]
            resolution_hint = "Record promise-to-pay with exact date and amount. Schedule follow-up callback for commitment_date + 1 day."
            
        else:  # GENERAL_INQUIRY
            known_facts = [
                f"Borrower Name: {bp.name}",
                f"Loan Type: {bp.loan_type}",
                f"Loan Status: {bp.delinquency_status}"
            ]
            missing_info = ["specific question or concern"]
            can_resolve_immediately = False
            suggested_tools = ["get_loan_details", "search_knowledge_base"]
            resolution_hint = "Ask borrower to clarify their specific concern"
            
        # Formulate next question based on missing info
        if missing_info:
            if intent == "PENALTY_INQUIRY":
                next_question = "Could you please share the reason for your payment failure?"
            elif intent == "PAYMENT_FAILURE":
                if any("balance" in mi for mi in missing_info):
                    next_question = "Could you confirm if you had sufficient balance in your account at the time of the transaction?"
                else:
                    next_question = "Could you please tell me what failure reason or error message you received from your bank?"
            elif intent == "PENALTY_WAIVER":
                if any("documented proof" in mi for mi in missing_info):
                    next_question = "Do you have any documented proof from your bank showing a gateway or bank-side error?"
                else:
                    next_question = "Could you please confirm the exact date of the failed payment you are requesting a waiver for?"
            elif intent == "SETTLEMENT_REQUEST":
                next_question = "Could you please share the reason for requesting a settlement, and tell me about your current monthly income or financial situation?"
            elif intent == "PAYMENT_COMMITMENT":
                has_date_missing = "exact date of payment" in missing_info
                has_amt_missing = "exact amount to be paid" in missing_info
                if has_date_missing and has_amt_missing:
                    next_question = "Could you please specify the exact date you will pay and the exact amount you commit to pay?"
                elif has_date_missing:
                    next_question = "Could you please specify the exact date you commit to make this payment?"
                else:
                    next_question = "Could you please specify the exact amount you commit to pay on that date?"
            elif intent == "GENERAL_INQUIRY":
                next_question = "Could you please clarify your specific concern or question regarding your loan?"

        # Special Case: Commitment Overdue
        if cs.pending_commitment is not None and cs.commitment_overdue:
            warning_fact = f"WARNING: Borrower made a previous commitment to pay by {cs.commitment_date} which was not fulfilled"
            known_facts.insert(0, warning_fact)
            
            warning_question = f"Before we proceed — during our last call you had committed to paying by {cs.commitment_date}. Were you able to make that payment?"
            if next_question:
                next_question = warning_question + " " + next_question
            else:
                next_question = warning_question

        return DiagnosisResult(
            intent=intent,
            confidence=confidence,
            known_facts=known_facts,
            missing_info=missing_info,
            next_question=next_question,
            can_resolve_immediately=can_resolve_immediately,
            suggested_tools=suggested_tools,
            resolution_hint=resolution_hint
        )

if __name__ == "__main__":
    # Get an OVERDUE_30 borrower from the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM borrowers WHERE delinquency_status = 'OVERDUE_30' LIMIT 1;")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print("No OVERDUE_30 borrower found. Trying any borrower.")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT phone FROM borrowers LIMIT 1;")
        row = cursor.fetchone()
        conn.close()
        
    if row:
        phone = row[0]
        context = ContextEngine.build_context(phone)
        if not context:
            print("Failed to build context.")
            exit(1)
            
        print(f"Testing DiagnosisLayer for Borrower: {context.borrower.name} ({context.borrower.delinquency_status})")
        print("=" * 60)
        
        # Utterance test cases
        test_cases = {
            "EMI_INQUIRY": "When is my next emi installment due and how many remaining?",
            "INTEREST_INQUIRY": "I want to know how much interest and principal I have paid so far.",
            "PENALTY_INQUIRY": "Why did you apply late fee charges on my account?",
            "PAYMENT_FAILURE": "My payment failed and got deducted from bank but didn't credit here.",
            "PENALTY_WAIVER": "Please waive and cancel this late penalty charge, my bank account had some error.",
            "SETTLEMENT_REQUEST": "I am bankrupt and cannot pay full. Can we do a one time settlement?",
            "PAYMENT_COMMITMENT": "I promise I will pay my overdue amount by next week.",
            "GENERAL_INQUIRY": "What is the company address or customer support email?"
        }
        
        for intent_name, utterance in test_cases.items():
            result = DiagnosisLayer.diagnose(context, utterance)
            print(f"Utterance: \"{utterance}\"")
            print(f"  Detected Intent: {result.intent} (Confidence: {result.confidence})")
            print(f"  Known Facts: {result.known_facts}")
            print(f"  Missing Info: {result.missing_info}")
            print(f"  Next Question: {result.next_question}")
            print(f"  Can Resolve Immediately: {result.can_resolve_immediately}")
            print(f"  Suggested Tools: {result.suggested_tools}")
            print(f"  Resolution Hint: {result.resolution_hint}")
            print("-" * 60)
    else:
        print("No borrower found to test.")
