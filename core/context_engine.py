import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import datetime
import math
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/borrowers.db")

@dataclass
class BorrowerProfile:
    borrower_id: str
    name: str
    phone: str
    email: str
    city: str
    loan_id: str
    loan_type: str
    loan_amount: float
    interest_rate: float
    tenure_months: int
    emi_amount: float
    loan_start_date: str
    loan_end_date: str
    outstanding_balance: float
    delinquency_status: str
    overdue_days: int
    penalty_amount: float
    bank_name: str
    kyc_status: str
    emis_paid: int
    emis_remaining: int
    next_due_date: str

@dataclass
class PaymentSummary:
    total_payments: int
    successful_payments: int
    failed_payments: int
    missed_payments: int
    partial_payments: int
    last_payment_date: Optional[str]
    last_payment_amount: Optional[float]
    last_payment_status: Optional[str]
    last_failure_reason: Optional[str]
    recent_failures: List[Dict[str, Any]]
    total_principal_paid: float
    total_interest_paid: float

@dataclass
class TicketSummary:
    open_tickets: List[Dict[str, Any]]
    recent_tickets: List[Dict[str, Any]]
    has_open_penalty_waiver: bool
    has_open_settlement: bool

@dataclass
class ConversationSummary:
    last_call_date: Optional[str]
    last_call_intent: Optional[str]
    last_call_summary: Optional[str]
    pending_commitment: Optional[str]
    commitment_date: Optional[str]
    commitment_overdue: bool
    call_count: int
    sentiment_history: List[str]

@dataclass
class BorrowerContext:
    retrieved_at: str
    borrower: BorrowerProfile
    payments: PaymentSummary
    tickets: TicketSummary
    conversations: ConversationSummary
    risk_signals: List[str]
    agent_notes: str

class ContextEngine:
    @staticmethod
    def build_context(identifier: str) -> Optional[BorrowerContext]:
        """Looks up a borrower by phone or borrower_id, assembles and returns a BorrowerContext."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM borrowers WHERE phone = ? OR borrower_id = ?", (identifier, identifier))
            borrower_row = cursor.fetchone()
            if not borrower_row:
                return None
            
            # Extract basic fields
            borrower_id = borrower_row['borrower_id']
            name = borrower_row['name']
            phone = borrower_row['phone']
            email = borrower_row['email']
            city = borrower_row['city']
            loan_id = borrower_row['loan_id']
            loan_type = borrower_row['loan_type']
            loan_amount = borrower_row['loan_amount']
            interest_rate = borrower_row['interest_rate']
            tenure_months = borrower_row['tenure_months']
            emi_amount = borrower_row['emi_amount']
            loan_start_date = borrower_row['loan_start_date']
            loan_end_date = borrower_row['loan_end_date']
            outstanding_balance = borrower_row['outstanding_balance']
            delinquency_status = borrower_row['delinquency_status']
            overdue_days = borrower_row['overdue_days']
            penalty_amount = borrower_row['penalty_amount']
            bank_name = borrower_row['bank_name']
            kyc_status = borrower_row['kyc_status']
            
            # Compute emis_paid, emis_remaining, and next_due_date
            loan_start_date_dt = datetime.datetime.strptime(loan_start_date, "%Y-%m-%d").date()
            today = datetime.date.today()
            
            # Months elapsed since start
            months_elapsed = (today.year - loan_start_date_dt.year) * 12 + (today.month - loan_start_date_dt.month)
            if today.day < loan_start_date_dt.day:
                months_elapsed -= 1
            months_elapsed = max(0, months_elapsed)
            
            # Adjust emis_paid based on missed payments
            num_missed = int(math.ceil(overdue_days / 30.0)) if overdue_days > 0 else 0
            emis_paid = max(0, months_elapsed - num_missed)
            emis_paid = min(emis_paid, tenure_months)
            
            emis_remaining = tenure_months - emis_paid
            
            next_due_date_dt = loan_start_date_dt + datetime.timedelta(days=(emis_paid + 1) * 30)
            next_due_date = next_due_date_dt.strftime("%Y-%m-%d")
            
            profile = BorrowerProfile(
                borrower_id=borrower_id,
                name=name,
                phone=phone,
                email=email,
                city=city,
                loan_id=loan_id,
                loan_type=loan_type,
                loan_amount=loan_amount,
                interest_rate=interest_rate,
                tenure_months=tenure_months,
                emi_amount=emi_amount,
                loan_start_date=loan_start_date,
                loan_end_date=loan_end_date,
                outstanding_balance=outstanding_balance,
                delinquency_status=delinquency_status,
                overdue_days=overdue_days,
                penalty_amount=penalty_amount,
                bank_name=bank_name,
                kyc_status=kyc_status,
                emis_paid=emis_paid,
                emis_remaining=emis_remaining,
                next_due_date=next_due_date
            )
            
            # Fetch payments
            cursor.execute("SELECT * FROM payments WHERE borrower_id = ? ORDER BY due_date DESC", (borrower_id,))
            payment_rows = cursor.fetchall()
            
            total_payments = len(payment_rows)
            successful_payments = sum(1 for p in payment_rows if p['status'] == 'SUCCESS')
            failed_payments = sum(1 for p in payment_rows if p['status'] in ('FAILED', 'AUTO_DEBIT_FAIL'))
            missed_payments = sum(1 for p in payment_rows if p['status'] == 'MISSED')
            partial_payments = sum(1 for p in payment_rows if p['status'] == 'PARTIAL')
            
            last_payment_date = None
            last_payment_amount = None
            for p in payment_rows:
                if p['amount_paid'] > 0:
                    last_payment_date = p['payment_date']
                    last_payment_amount = p['amount_paid']
                    break
            
            if last_payment_date is None and payment_rows:
                last_payment_date = payment_rows[0]['payment_date']
                last_payment_amount = payment_rows[0]['amount_paid']
                
            if payment_rows:
                last_payment_status = payment_rows[0]['status']
                last_failure_reason = payment_rows[0]['failure_reason']
            else:
                last_payment_status = None
                last_failure_reason = None
                
            recent_failures = []
            for p in payment_rows:
                if p['status'] in ('FAILED', 'AUTO_DEBIT_FAIL'):
                    recent_failures.append(dict(p))
                    if len(recent_failures) == 3:
                        break
            
            # Compute total principal/interest paid dynamically
            r_monthly = (interest_rate / 12.0) / 100.0
            n_tenure = tenure_months
            k_paid = min(emis_paid, n_tenure)
            if r_monthly == 0:
                total_principal_paid = loan_amount * (k_paid / n_tenure)
                total_interest_paid = 0.0
            else:
                term_n = (1 + r_monthly) ** n_tenure
                term_k = (1 + r_monthly) ** k_paid
                balance_after_k = loan_amount * (term_n - term_k) / (term_n - 1)
                total_principal_paid = loan_amount - balance_after_k
                total_paid_total = k_paid * emi_amount
                total_interest_paid = total_paid_total - total_principal_paid
                
            total_principal_paid = max(0.0, round(total_principal_paid, 2))
            total_interest_paid = max(0.0, round(total_interest_paid, 2))
            
            payments_summary = PaymentSummary(
                total_payments=total_payments,
                successful_payments=successful_payments,
                failed_payments=failed_payments,
                missed_payments=missed_payments,
                partial_payments=partial_payments,
                last_payment_date=last_payment_date,
                last_payment_amount=last_payment_amount,
                last_payment_status=last_payment_status,
                last_failure_reason=last_failure_reason,
                recent_failures=recent_failures,
                total_principal_paid=total_principal_paid,
                total_interest_paid=total_interest_paid
            )
            
            # Fetch tickets
            cursor.execute("SELECT * FROM tickets WHERE borrower_id = ? ORDER BY created_date DESC", (borrower_id,))
            ticket_rows = cursor.fetchall()
            
            open_tickets = [dict(t) for t in ticket_rows if t['status'] in ('OPEN', 'IN_PROGRESS')]
            recent_tickets = [dict(t) for t in ticket_rows[:3]]
            has_open_penalty_waiver = any(t['category'] == 'PENALTY_WAIVER' for t in open_tickets)
            has_open_settlement = any(t['category'] == 'SETTLEMENT' for t in open_tickets)
            
            tickets_summary = TicketSummary(
                open_tickets=open_tickets,
                recent_tickets=recent_tickets,
                has_open_penalty_waiver=has_open_penalty_waiver,
                has_open_settlement=has_open_settlement
            )
            
            # Fetch conversations
            cursor.execute("SELECT * FROM conversations WHERE borrower_id = ? ORDER BY call_date DESC", (borrower_id,))
            conv_rows = cursor.fetchall()
            
            if conv_rows:
                last_call_date = conv_rows[0]['call_date']
                last_call_intent = conv_rows[0]['intent']
                last_call_summary = conv_rows[0]['summary']
                pending_commitment = conv_rows[0]['commitment_made']
                commitment_date = conv_rows[0]['commitment_date']
            else:
                last_call_date = None
                last_call_intent = None
                last_call_summary = None
                pending_commitment = None
                commitment_date = None
                
            commitment_overdue = False
            today_str = today.strftime("%Y-%m-%d")
            if commitment_date:
                if commitment_date < today_str:
                    has_payment_after_commitment = False
                    for p in payment_rows:
                        if p['status'] == 'SUCCESS' and p['payment_date'] and p['payment_date'] >= commitment_date:
                            has_payment_after_commitment = True
                            break
                    if not has_payment_after_commitment:
                        commitment_overdue = True
            
            call_count = len(conv_rows)
            sentiment_history = [c['sentiment'] for c in conv_rows[:3]]
            
            conversations_summary = ConversationSummary(
                last_call_date=last_call_date,
                last_call_intent=last_call_intent,
                last_call_summary=last_call_summary,
                pending_commitment=pending_commitment,
                commitment_date=commitment_date,
                commitment_overdue=commitment_overdue,
                call_count=call_count,
                sentiment_history=sentiment_history
            )
            
            # Risk Signals
            risk_signals = []
            if delinquency_status != "CURRENT":
                risk_signals.append(delinquency_status)
            if failed_payments + missed_payments >= 3:
                risk_signals.append("REPEATED_FAILURES")
            
            failures_in_last_3 = sum(1 for p in payment_rows[:3] if p['status'] in ('FAILED', 'AUTO_DEBIT_FAIL'))
            if failures_in_last_3 >= 2:
                risk_signals.append("RECENT_FAILURE_STREAK")
                
            if len(open_tickets) > 0:
                risk_signals.append("OPEN_TICKETS")
            if has_open_penalty_waiver:
                risk_signals.append("PENDING_WAIVER_REQUEST")
            if has_open_settlement:
                risk_signals.append("SETTLEMENT_IN_PROGRESS")
            if commitment_overdue:
                risk_signals.append("BROKEN_PROMISE_TO_PAY")
            if pending_commitment and commitment_date and commitment_date >= today_str:
                risk_signals.append("ACTIVE_PROMISE_TO_PAY")
            if sentiment_history and sentiment_history[0] in ("NEGATIVE", "FRUSTRATED"):
                risk_signals.append("FRUSTRATED_BORROWER")
            if penalty_amount > emi_amount:
                risk_signals.append("HIGH_PENALTY_ACCRUED")
                
            # Construct agent notes (single human-readable paragraph)
            notes = f"{name} has an active {loan_type} of ₹{loan_amount:,.2f}."
            if delinquency_status == "CURRENT":
                notes += f" The loan is currently up to date with no overdue days."
            else:
                notes += f" The loan is in {delinquency_status} status with {overdue_days} days overdue and accrued penalty of ₹{penalty_amount:,.2f}."

            if last_payment_status:
                if last_payment_status == "SUCCESS":
                    notes += f" Their last payment on {last_payment_date} of ₹{last_payment_amount:,.2f} was successful."
                elif last_payment_status == "PARTIAL":
                    notes += f" Their last payment on {last_payment_date} was a partial payment of ₹{last_payment_amount:,.2f}."
                else:
                    notes += f" Their last payment attempt resulted in a failure ({last_payment_status}) on {last_payment_date} due to: {last_failure_reason or 'unknown reason'}."
            else:
                notes += " No payment history was found in the system."

            if open_tickets:
                ticket_cats = [t['category'] for t in open_tickets]
                notes += f" There are open support tickets under categories: {', '.join(ticket_cats)}."
            else:
                notes += " There are no open support tickets."

            if pending_commitment:
                if commitment_overdue:
                    notes += f" A commitment to pay ('{pending_commitment}') was made for {commitment_date} but is now overdue."
                else:
                    notes += f" There is a pending commitment to pay ('{pending_commitment}') scheduled for {commitment_date}."
            else:
                notes += " There are no pending commitments."

            if risk_signals:
                notes += f" Key risk factors identified: {', '.join(risk_signals)}."
            else:
                notes += " No critical risk signals are present."
                
            retrieved_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return BorrowerContext(
                retrieved_at=retrieved_at,
                borrower=profile,
                payments=payments_summary,
                tickets=tickets_summary,
                conversations=conversations_summary,
                risk_signals=risk_signals,
                agent_notes=notes
            )
            
        finally:
            conn.close()

    @staticmethod
    def to_llm_prompt(context: BorrowerContext) -> str:
        """Formats the context as a clean readable string prepended to the system prompt."""
        bp = context.borrower
        ps = context.payments
        ts = context.tickets
        cs = context.conversations
        
        prompt = []
        prompt.append("=== BORROWER CONTEXT ===")
        prompt.append(f"Retrieved At: {context.retrieved_at}")
        prompt.append("")
        prompt.append("--- BORROWER PROFILE ---")
        prompt.append(f"Borrower ID: {bp.borrower_id}")
        prompt.append(f"Name: {bp.name}")
        prompt.append(f"Phone: {bp.phone}")
        prompt.append(f"Email: {bp.email}")
        prompt.append(f"City: {bp.city}")
        prompt.append(f"KYC Status: {bp.kyc_status}")
        prompt.append("")
        prompt.append("--- LOAN DETAILS ---")
        prompt.append(f"Loan ID: {bp.loan_id}")
        prompt.append(f"Loan Type: {bp.loan_type}")
        prompt.append(f"Loan Amount: ₹{bp.loan_amount:,.2f}")
        prompt.append(f"Interest Rate: {bp.interest_rate}%")
        prompt.append(f"Tenure Months: {bp.tenure_months}")
        prompt.append(f"EMI Amount: ₹{bp.emi_amount:,.2f}")
        prompt.append(f"Loan Start Date: {bp.loan_start_date}")
        prompt.append(f"Loan End Date: {bp.loan_end_date}")
        prompt.append(f"Outstanding Balance: ₹{bp.outstanding_balance:,.2f}")
        prompt.append(f"EMIs Paid: {bp.emis_paid}")
        prompt.append(f"EMIs Remaining: {bp.emis_remaining}")
        prompt.append(f"Next Due Date: {bp.next_due_date}")
        prompt.append("")
        prompt.append("--- DELINQUENCY & PENALTY ---")
        prompt.append(f"Delinquency Status: {bp.delinquency_status}")
        prompt.append(f"Overdue Days: {bp.overdue_days}")
        prompt.append(f"Penalty Amount: ₹{bp.penalty_amount:,.2f}")
        prompt.append(f"Bank Name: {bp.bank_name}")
        prompt.append("")
        prompt.append("--- PAYMENT HISTORY SUMMARY ---")
        prompt.append(f"Total Logged Payments: {ps.total_payments}")
        prompt.append(f"Successful Payments: {ps.successful_payments}")
        prompt.append(f"Failed Payments: {ps.failed_payments}")
        prompt.append(f"Missed Payments: {ps.missed_payments}")
        prompt.append(f"Partial Payments: {ps.partial_payments}")
        prompt.append(f"Total Principal Paid: ₹{ps.total_principal_paid:,.2f}")
        prompt.append(f"Total Interest Paid: ₹{ps.total_interest_paid:,.2f}")
        prompt.append(f"Last Payment Date: {ps.last_payment_date}")
        prompt.append(f"Last Payment Amount: ₹{ps.last_payment_amount:,.2f}" if ps.last_payment_amount is not None else "Last Payment Amount: None")
        prompt.append(f"Last Payment Status: {ps.last_payment_status}")
        prompt.append(f"Last Failure Reason: {ps.last_failure_reason}")
        prompt.append("")
        prompt.append("--- SUPPORT TICKETS ---")
        prompt.append(f"Has Open Penalty Waiver Request: {ts.has_open_penalty_waiver}")
        prompt.append(f"Has Open Settlement Request: {ts.has_open_settlement}")
        prompt.append(f"Open Tickets Count: {len(ts.open_tickets)}")
        for t in ts.open_tickets:
            prompt.append(f"  - [{t['ticket_id']}] Category: {t['category']} | Status: {t['status']} | Priority: {t['priority']} | Subject: {t['subject']}")
        prompt.append("")
        prompt.append("--- CONVERSATION HISTORY ---")
        prompt.append(f"Total Calls: {cs.call_count}")
        prompt.append(f"Last Call Date: {cs.last_call_date}")
        prompt.append(f"Last Call Intent: {cs.last_call_intent}")
        prompt.append(f"Last Call Summary: {cs.last_call_summary}")
        prompt.append(f"Pending Commitment: {cs.pending_commitment}")
        prompt.append(f"Commitment Date: {cs.commitment_date}")
        prompt.append(f"Commitment Overdue: {cs.commitment_overdue}")
        prompt.append(f"Sentiment History (Latest First): {', '.join(cs.sentiment_history)}")
        prompt.append("")
        prompt.append("--- RISK SIGNALS ---")
        if context.risk_signals:
            for signal in context.risk_signals:
                prompt.append(f"  - [WARNING] {signal}")
        else:
            prompt.append("  - No active risk signals")
        prompt.append("")
        prompt.append("--- AGENT NOTES ---")
        prompt.append(context.agent_notes)
        prompt.append("=========================")
        
        return "\n".join(prompt)

if __name__ == "__main__":
    # Test connection and fetch first borrower
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM borrowers LIMIT 1;")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        phone = row[0]
        print(f"Testing ContextEngine for phone: {phone}\n")
        context = ContextEngine.build_context(phone)
        if context:
            print(ContextEngine.to_llm_prompt(context))
            print("\nVerification Stats:")
            print(f"Risk Signals: {context.risk_signals}")
            print(f"EMIs Remaining: {context.borrower.emis_remaining}")
        else:
            print("Failed to build context.")
    else:
        print("No borrowers found in the database.")
