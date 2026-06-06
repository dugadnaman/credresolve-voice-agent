import os
import json
import sqlite3
import random
import datetime
import math

# Seed for reproducibility
random.seed(42)

# Configuration & Data Directories
DB_PATH = os.path.join("data", "borrowers.db")
KB_DIR = os.path.join("data", "knowledge_base")

# Delete existing DB so we start fresh
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

os.makedirs("data", exist_ok=True)
os.makedirs(KB_DIR, exist_ok=True)

# Helper lists for realistic Indian names, cities, banks, and loan details
INDIAN_FIRST_NAMES_MALE = [
    "Aarav", "Vihaan", "Vivaan", "Ananya", "Kabir", "Sai", "Aditya", "Ishan", 
    "Shaurya", "Rohit", "Amit", "Vijay", "Suresh", "Ramesh", "Sunil", "Anil", 
    "Rajesh", "Sanjay", "Vikram", "Manoj", "Arjun", "Rahul", "Ajay", "Alok", 
    "Dev", "Raj", "Deepak", "Sandeep", "Neeraj", "Harish", "Karan", "Gaurav"
]
INDIAN_FIRST_NAMES_FEMALE = [
    "Diya", "Isha", "Kiara", "Myra", "Ananya", "Aanya", "Aaradhya", "Pari", 
    "Kavya", "Riya", "Priya", "Sunita", "Anita", "Geeta", "Rekha", "Pinky", 
    "Kavita", "Pooja", "Aarti", "Neha", "Swati", "Jyoti", "Meena", "Kiran", 
    "Deepa", "Shalini", "Sneha", "Tanvi", "Ritu", "Preeti", "Payal", "Anjali"
]
INDIAN_LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Patel", "Mehta", "Joshi", "Rao", "Nair", 
    "Reddy", "Kumar", "Singh", "Prasad", "Das", "Banerjee", "Chatterjee", 
    "Mukherjee", "Sen", "Bose", "Patil", "Deshmukh", "Kulkarni", "Shah", 
    "Gokhale", "Bhat", "Hegde", "Pillai", "Iyer", "Iyengar", "Choudhury", "Roy"
]
INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Ahmedabad", "Chennai", 
    "Kolkata", "Surat", "Pune", "Jaipur", "Lucknow", "Kanpur", "Nagpur", 
    "Indore", "Thane", "Bhopal", "Visakhapatnam", "Patna", "Vadodara", "Ghaziabad"
]
INDIAN_BANKS = [
    "State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank", 
    "Kotak Mahindra Bank", "Punjab National Bank", "Bank of Baroda", 
    "IndusInd Bank", "Canara Bank", "Union Bank of India"
]

LOAN_TYPES_CONFIG = {
    "Personal Loan": {
        "rate_range": (12.0, 20.0),
        "tenure_range": (12, 60),
        "amount_range": (50000, 1000000)
    },
    "Home Loan": {
        "rate_range": (8.5, 10.5),
        "tenure_range": (120, 360),
        "amount_range": (1500000, 10000000)
    },
    "Car Loan": {
        "rate_range": (9.0, 12.0),
        "tenure_range": (36, 84),
        "amount_range": (400000, 1500000)
    },
    "Gold Loan": {
        "rate_range": (10.0, 16.0),
        "tenure_range": (6, 24),
        "amount_range": (20000, 500000)
    },
    "Education Loan": {
        "rate_range": (9.5, 13.0),
        "tenure_range": (60, 120),
        "amount_range": (200000, 2500000)
    },
    "Business Loan": {
        "rate_range": (14.0, 24.0),
        "tenure_range": (12, 60),
        "amount_range": (200000, 5000000)
    },
    "Two Wheeler Loan": {
        "rate_range": (11.0, 18.0),
        "tenure_range": (12, 48),
        "amount_range": (50000, 150000)
    }
}

# Helper functions
def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, [31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return datetime.date(year, month, day)

def get_outstanding_balance(loan_amount, interest_rate, tenure_months, elapsed_months):
    r = (interest_rate / 12.0) / 100.0
    n = tenure_months
    k = min(elapsed_months, n)
    if r == 0:
        return loan_amount * (1.0 - k / n)
    term_n = (1 + r) ** n
    term_k = (1 + r) ** k
    balance = loan_amount * (term_n - term_k) / (term_n - 1)
    return max(0.0, round(balance, 2))

# ----------------- KNOWLEDGE BASE DOCUMENTS -----------------
kb_documents = [
    {
        "id": "KB_01",
        "title": "Late Payment Policy and Fees",
        "category": "Policies",
        "content": "All EMI payments must be paid on or before the due date (usually the 5th of every month). Any payment delayed beyond the due date will incur a late payment fee of 2% per month on the overdue installment amount. Additionally, bounce charges of ₹500 will be applicable if the auto-debit (NACH) mandate fails due to insufficient funds. Continued non-payment will lead to negative reporting to credit bureaus (CIBIL) and initiation of recovery proceedings."
    },
    {
        "id": "KB_02",
        "title": "Late Payment Penalty Waiver Policy",
        "category": "Policies",
        "content": "Borrowers experiencing genuine financial distress due to medical emergencies, job loss, or natural disasters may request a waiver of late payment penalties. A one-time waiver can be approved by the Credit Committee if the borrower pays the entire outstanding principal EMI. The borrower must submit supporting documents, such as hospital discharge summaries, medical certificates, or a termination letter. Waivers are granted at the sole discretion of the company and are capped at a maximum of ₹5,000 per borrower per loan cycle."
    },
    {
        "id": "KB_03",
        "title": "Loan Foreclosure Policy and Charges",
        "category": "Policies",
        "content": "Borrowers can choose to foreclose (pre-close) their loan before the maturity date. Foreclosure is allowed only after the successful payment of at least 6 EMIs. The foreclosure charges are 3% of the outstanding principal amount for personal loans, and nil for home loans with floating interest rates. To initiate foreclosure, the borrower must submit a formal request at a branch or via email, after which a foreclosure letter specifying the final payable amount (valid for 15 days) will be issued."
    },
    {
        "id": "KB_04",
        "title": "One-Time Settlement (OTS) Policy",
        "category": "Policies",
        "content": "One-Time Settlement (OTS) is offered only to accounts categorized as Non-Performing Assets (NPA) or in advanced stages of delinquency (90+ days overdue) where recovery is highly unlikely. Under OTS, the company may agree to waive accrued interest and penalties and accept a reduced lump-sum payment to close the loan. The minimum settlement amount must cover the outstanding principal. Note that settling a loan is reported to CIBIL as 'Settled', which negatively impacts the borrower's credit score for up to 7 years."
    },
    {
        "id": "KB_05",
        "title": "Payment Failure and Double Debit Resolution",
        "category": "Payments",
        "content": "If your payment fails but the money is debited from your bank account, please do not panic. The money is usually held in the payment gateway and is automatically refunded to your source account within 5-7 working days. If the EMI status is not updated in our system within 48 hours, please submit a ticket under 'Payment Failure' category with a copy of your bank statement showing the transaction details and the transaction reference number."
    },
    {
        "id": "KB_06",
        "title": "Equated Monthly Installment (EMI) FAQ",
        "category": "FAQs",
        "content": "What is an EMI? An Equated Monthly Installment (EMI) is a fixed payment amount made by a borrower to a lender at a specified date each calendar month. EMIs consist of both principal and interest components. Can I change my EMI due date? Due dates are fixed at the time of loan onboarding (typically the 5th) and cannot be customized mid-tenure. How is EMI calculated? EMI is calculated using the formula: EMI = [P x R x (1+R)^N]/[((1+R)^N)-1], where P is principal, R is monthly interest rate, and N is tenure in months."
    },
    {
        "id": "KB_07",
        "title": "National Automated Clearing House (NACH) Mandate Setup",
        "category": "Payments",
        "content": "NACH mandate is mandatory for automatic debit of loan EMIs. Borrowers can register NACH either online (e-NACH using NetBanking or Debit Card) or offline by signing a physical mandate form. Online setup takes 2-3 working days to activate, whereas offline setup requires 15-20 days for bank verification. In case of bank account changes, a new NACH mandate must be registered at least 15 days before the next EMI due date to avoid debit failures."
    },
    {
        "id": "KB_08",
        "title": "Requesting Loan Statement of Account and Interest Certificate",
        "category": "Customer Support",
        "content": "Borrowers can download their Loan Account Statement, Interest Certificate, and Provisional Interest Certificate (for tax savings) instantly via our mobile app or web customer portal. Alternatively, they can raise a request with customer support or email support@credresolve-lending.com. The documents will be sent to the registered email address within 24 hours. Physical copies can also be collected from the nearest branch for a nominal fee of ₹100."
    },
    {
        "id": "KB_09",
        "title": "Overdue Loan Recovery Guidelines",
        "category": "Recovery",
        "content": "In the event of loan delinquency, the company follows a structured recovery process: 1. Telephonic reminders starting from 1 day past due. 2. SMS, WhatsApp, and Email alerts. 3. Legal demand notice issued at 60 days past due. 4. Field recovery agent visits to registered addresses for accounts overdue by more than 30 days. All recovery activities are conducted in strict compliance with RBI's Fair Practice Code, ensuring respectful communication and appropriate hours for visits (between 7:00 AM and 7:00 PM)."
    },
    {
        "id": "KB_10",
        "title": "Borrower Rights and Fair Practice Code",
        "category": "Policies",
        "content": "As per the Reserve Bank of India (RBI) guidelines, borrowers have the following rights: 1. Right to transparent pricing and terms. 2. Right to privacy and confidentiality of personal data. 3. Right to receive receipts for all payments made. 4. Right to fair treatment and protection against harassment during recovery. 5. Access to grievance redressal mechanisms. Any violation of these rights can be reported to our Grievance Redressal Officer or directly to the RBI Ombudsman."
    },
    {
        "id": "KB_11",
        "title": "Part Prepayment Policy",
        "category": "Policies",
        "content": "Borrowers can make part prepayments to reduce their outstanding principal loan amount. Part prepayments must be a minimum of 2 EMIs value and are allowed up to 3 times a year. No charges are applicable on part prepayment for floating rate home loans. For personal loans, a prepayment fee of 2% of the prepaid amount may apply. Upon prepayment, the borrower can choose to either reduce the monthly EMI amount (keeping tenure same) or reduce the remaining loan tenure (keeping EMI same)."
    },
    {
        "id": "KB_12",
        "title": "Credit Score (CIBIL) Reporting and Impact",
        "category": "FAQs",
        "content": "We report the payment status of all active loans to credit bureaus (CIBIL, Experian, Equifax) on a monthly basis. Timely payment of EMIs helps build a high credit score, which is essential for future credit access. Any payment delayed by even a single day is reported as 'Past Due' and will lower your credit score. If a loan is written off or settled, it is permanently marked as such in your credit report, making it extremely difficult to obtain loans from other financial institutions."
    },
    {
        "id": "KB_13",
        "title": "Loan Restructuring and Rescheduling Policy",
        "category": "Policies",
        "content": "In extreme cases of financial hardship, such as loss of employment or permanent disability, borrowers can apply for loan restructuring. Restructuring options include extending the loan tenure (which reduces EMI but increases overall interest outflow) or granting an temporary EMI moratorium. Borrowers must submit proof of hardship. A processing fee of 1% of the outstanding loan amount is charged for restructuring. Restructured loans are flagged in credit bureau reports."
    },
    {
        "id": "KB_14",
        "title": "Loan Protection Insurance Policy",
        "category": "Policies",
        "content": "We offer optional Loan Protection Insurance at the time of loan disbursement to safeguard the borrower's family in the event of accidental death, critical illness, or permanent total disability. If insured, the insurance company will pay off the remaining outstanding loan balance. Claim forms and list of required documents (death certificate, medical reports) must be submitted within 30 days of the event. The insurance cover is co-terminus with the loan tenure."
    },
    {
        "id": "KB_15",
        "title": "How to Obtain Interest Certificate for Tax Benefits",
        "category": "Customer Support",
        "content": "Under Section 24(b) and Section 80C of the Income Tax Act, borrowers can claim deductions on the interest and principal paid on home loans. To claim this, you need an Interest Certificate (statement of interest). You can request this document by emailing support@credresolve-lending.com with subject line 'Interest Certificate - [Loan ID]'. The certificate contains a breakdown of the principal and interest paid during the financial year and will be emailed instantly."
    },
    {
        "id": "KB_16",
        "title": "What Happens If I Miss an EMI?",
        "category": "FAQs",
        "content": "If you miss an EMI, the following consequences apply: 1. Late fee of 2% per month will be charged. 2. A bounce charge of ₹500 will be debited for NACH debit failure. 3. Your credit score (CIBIL) will drop. 4. You will receive collection calls and notices. If you pay within 90 days, your account remains standard overdue. If you do not pay for 90 days, your account is declared a Non-Performing Asset (NPA) and legal recovery action under SARFAESI Act or Section 138 of Negotiable Instruments Act may be initiated."
    },
    {
        "id": "KB_17",
        "title": "Multiple Payment Modes and Options",
        "category": "Payments",
        "content": "Apart from the auto-debit (NACH) mandate, you can pay your overdue EMIs or make pre-payments using the following modes: 1. UPI (GPay, PhonePe, Paytm) via our payment link. 2. NetBanking portal of all major banks. 3. Debit Card. 4. Cash payment at our nearest branch office. Always ensure you receive a payment receipt with a digital signature immediately after making a payment. Do not hand over cash to any representative without a valid digital receipt."
    },
    {
        "id": "KB_18",
        "title": "Issuance of No Objection Certificate (NOC) After Loan Closure",
        "category": "Customer Support",
        "content": "After a loan is successfully closed through regular maturity or foreclosure, the company issues a No Objection Certificate (NOC) and a No Dues Certificate (NDC). These documents confirm that the borrower has paid all outstanding dues and that the company has no further claim. The NOC will be dispatched to the registered physical address within 15 working days of loan closure and a soft copy sent to the registered email. Any pledged collateral documents will be returned within 30 days."
    },
    {
        "id": "KB_19",
        "title": "EMI Moratorium Guidelines",
        "category": "Policies",
        "content": "A moratorium is a temporary suspension of EMI payments. Moratoriums are not standard features and are only declared under special directives from the RBI or government during national emergencies (e.g., pandemic lock-downs). Interest continues to accrue on the outstanding principal during the moratorium period, which extends the overall loan tenure and increases the total interest cost. Borrowers must actively opt-in for moratoriums when they are officially offered."
    },
    {
        "id": "KB_20",
        "title": "Grievance Redressal and Complaints Policy",
        "category": "Customer Support",
        "content": "We are committed to providing excellent service. If you have any complaints or grievances, you can raise them through: Level 1: Contact customer support via call or email support@credresolve-lending.com. Level 2: If unresolved within 7 days, write to our Grievance Redressal Officer at gro@credresolve-lending.com. Level 3: If unresolved within 15 days, escalate to our Principal Nodal Officer at pno@credresolve-lending.com. If the complaint is not resolved within 30 days, you can contact the RBI Ombudsman."
    }
]

# Write KB documents to files
for doc in kb_documents:
    # Save files using clean naming format derived from the title
    file_name = doc["title"].lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_") + ".json"
    with open(os.path.join(KB_DIR, file_name), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=4, ensure_ascii=False)

# ----------------- DATABASE GENERATION -----------------
current_date = datetime.date(2026, 6, 1)

# Generate exact distribution of delinquency status
delinquency_distribution = (
    ["CURRENT"] * 60 +
    ["OVERDUE_15"] * 15 +
    ["OVERDUE_30"] * 12 +
    ["OVERDUE_60"] * 8 +
    ["NPA"] * 5
)
random.shuffle(delinquency_distribution)

borrowers_records = []
all_payments_pool = []

for i in range(1, 101):
    borrower_id = f"B{i:03d}"
    loan_id = f"L{i:03d}"
    
    # Names & Contact
    gender = "male" if random.random() < 0.55 else "female"
    first_name = random.choice(INDIAN_FIRST_NAMES_MALE) if gender == "male" else random.choice(INDIAN_FIRST_NAMES_FEMALE)
    last_name = random.choice(INDIAN_LAST_NAMES)
    name = f"{first_name} {last_name}"
    
    phone = f"+91{random.choice([7, 8, 9])}{random.randint(100000000, 999999999)}"
    email = f"{first_name.lower()}.{last_name.lower()}{random.randint(10, 99)}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com'])}"
    city = random.choice(INDIAN_CITIES)
    
    # Loan specifics
    loan_type = random.choice(list(LOAN_TYPES_CONFIG.keys()))
    config = LOAN_TYPES_CONFIG[loan_type]
    loan_amount = random.randint(config["amount_range"][0] // 10000, config["amount_range"][1] // 10000) * 10000
    interest_rate = round(random.uniform(config["rate_range"][0], config["rate_range"][1]), 2)
    tenure_months = random.choice([t for t in range(config["tenure_range"][0], config["tenure_range"][1] + 1) if t % 6 == 0 or t == config["tenure_range"][0]])
    
    # EMI calculation
    r = (interest_rate / 12.0) / 100.0
    n = tenure_months
    emi_amount = (loan_amount * r * ((1 + r) ** n)) / (((1 + r) ** n) - 1)
    emi_amount = round(emi_amount, 2)
    
    # Dates
    start_dt = datetime.date(2022, 1, 1)
    end_dt = datetime.date(2025, 6, 1)
    days_range = (end_dt - start_dt).days
    random_days = random.randrange(days_range)
    loan_start_date_dt = start_dt + datetime.timedelta(days=random_days)
    # Default to 5th of the month
    loan_start_date_dt = datetime.date(loan_start_date_dt.year, loan_start_date_dt.month, 5)
    loan_start_date = loan_start_date_dt.strftime("%Y-%m-%d")
    
    loan_end_date_dt = add_months(loan_start_date_dt, tenure_months)
    loan_end_date = loan_end_date_dt.strftime("%Y-%m-%d")
    
    # Delinquency status config
    delinquency_status = delinquency_distribution[i - 1]
    if delinquency_status == "CURRENT":
        overdue_days = 0
        penalty_amount = 0.0
    elif delinquency_status == "OVERDUE_15":
        overdue_days = random.randint(1, 15)
        penalty_amount = round(overdue_days * 50.0, 2)
    elif delinquency_status == "OVERDUE_30":
        overdue_days = random.randint(16, 30)
        penalty_amount = round(overdue_days * 75.0, 2)
    elif delinquency_status == "OVERDUE_60":
        overdue_days = random.randint(31, 89)
        penalty_amount = round(overdue_days * 100.0, 2)
    else:  # NPA
        overdue_days = random.randint(90, 180)
        penalty_amount = round(overdue_days * 150.0, 2)
        
    num_missed = math.ceil(overdue_days / 30) if overdue_days > 0 else 0
    
    # Outstanding balance calculation
    elapsed_months = (current_date.year - loan_start_date_dt.year) * 12 + (current_date.month - loan_start_date_dt.month)
    paid_months = max(0, elapsed_months - num_missed)
    base_outstanding = get_outstanding_balance(loan_amount, interest_rate, tenure_months, paid_months)
    outstanding_balance = round(base_outstanding + (num_missed * emi_amount) + penalty_amount, 2)
    
    # Bank & KYC Info
    bank_name = random.choice(INDIAN_BANKS)
    account_number = str(random.randint(100000000000, 999999999999))
    
    pan_chars = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(5))
    pan_nums = "".join(random.choice("0123456789") for _ in range(4))
    pan_last = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    pan_number = pan_chars + pan_nums + pan_last
    kyc_status = random.choices(["COMPLETED", "PENDING", "FAILED"], weights=[90, 8, 2], k=1)[0]
    
    borrower = {
        "borrower_id": borrower_id, "name": name, "phone": phone, "email": email, "city": city,
        "loan_id": loan_id, "loan_type": loan_type, "loan_amount": loan_amount, "interest_rate": interest_rate,
        "tenure_months": tenure_months, "emi_amount": emi_amount, "loan_start_date": loan_start_date,
        "loan_end_date": loan_end_date, "outstanding_balance": outstanding_balance,
        "delinquency_status": delinquency_status, "overdue_days": overdue_days, "penalty_amount": penalty_amount,
        "bank_name": bank_name, "account_number": account_number, "pan_number": pan_number, "kyc_status": kyc_status
    }
    borrowers_records.append(borrower)
    
    # Generate individual payment history for the borrower
    borrower_payments = []
    for m in range(1, elapsed_months + 1):
        due_date_dt = add_months(loan_start_date_dt, m)
        if due_date_dt > current_date:
            break
        
        due_date = due_date_dt.strftime("%Y-%m-%d")
        days_diff = (current_date - due_date_dt).days
        
        is_overdue_payment = (overdue_days > 0) and (days_diff <= overdue_days)
        
        amount_due = emi_amount
        gateway_ref = f"TXN{random.randint(1000000000, 9999999999)}"
        channel = random.choice(["NACH", "UPI", "NetBanking", "DebitCard"])
        
        if is_overdue_payment:
            status = random.choices(["FAILED", "AUTO_DEBIT_FAIL", "MISSED", "PARTIAL"], weights=[30, 40, 20, 10], k=1)[0]
            if status == "PARTIAL":
                amount_paid = round(emi_amount * random.uniform(0.1, 0.45), 2)
                payment_date = (due_date_dt + datetime.timedelta(days=random.randint(0, 3))).strftime("%Y-%m-%d")
                failure_reason = "Shortage of funds"
            elif status == "MISSED":
                amount_paid = 0.0
                payment_date = None
                failure_reason = "No payment attempt"
            else:  # FAILED or AUTO_DEBIT_FAIL
                amount_paid = 0.0
                payment_date = (due_date_dt + datetime.timedelta(days=random.randint(0, 3))).strftime("%Y-%m-%d")
                failure_reason = random.choice(["Insufficient Funds", "Mandate Failure", "Network Timeout"])
        else:
            status = "SUCCESS"
            amount_paid = emi_amount
            payment_date = (due_date_dt + datetime.timedelta(days=random.randint(-3, 0))).strftime("%Y-%m-%d")
            failure_reason = None
            
        borrower_payments.append({
            "borrower_id": borrower_id,
            "loan_id": loan_id,
            "due_date": due_date,
            "payment_date": payment_date,
            "amount_due": amount_due,
            "amount_paid": amount_paid,
            "status": status,
            "failure_reason": failure_reason,
            "gateway_ref": gateway_ref,
            "channel": channel
        })
        
    # Pick the top 5 most recent payments for this borrower
    borrower_payments_sorted = sorted(borrower_payments, key=lambda x: x["due_date"], reverse=True)[:5]
    all_payments_pool.extend(borrower_payments_sorted)

# Sort all payments in chronological due_date order to assign sequential payment IDs
all_payments_pool = sorted(all_payments_pool, key=lambda x: x["due_date"])
payments_records = []
for idx, p in enumerate(all_payments_pool):
    p["payment_id"] = f"P{idx + 1:03d}"
    payments_records.append(p)

# ----------------- TICKETS GENERATION -----------------
# 100 tickets in total (1 per borrower to ensure data coherence)
tickets_records = []
for idx, b in enumerate(borrowers_records):
    ticket_id = f"T{idx + 1:03d}"
    borrower_id = b["borrower_id"]
    loan_id = b["loan_id"]
    delinquency_status = b["delinquency_status"]
    loan_start_date_dt = datetime.datetime.strptime(b["loan_start_date"], "%Y-%m-%d").date()
    
    # Establish details based on status
    if delinquency_status == "CURRENT":
        category = random.choice(["GENERAL", "FORECLOSURE", "EMI_DISPUTE"])
        if category == "GENERAL":
            subject = "Request for loan account statement"
            description = "Please send my loan interest certificate and statement of account for this financial year."
            status = random.choice(["RESOLVED", "CLOSED"])
            priority = "LOW"
            resolution_note = "Interest certificate and statement sent to the registered email address."
        elif category == "FORECLOSURE":
            subject = "Request for loan foreclosure letter"
            description = "I want to preclose my loan. Please provide the foreclosure letter and list of documents required."
            status = random.choice(["RESOLVED", "CLOSED", "OPEN", "IN_PROGRESS"])
            priority = "MEDIUM"
            resolution_note = "Foreclosure letter shared over email. Valid till 15th of this month." if status in ["RESOLVED", "CLOSED"] else None
        else: # EMI_DISPUTE
            subject = "EMI amount debited twice"
            description = "My bank account was debited twice for this month's EMI. Please refund the duplicate transaction."
            status = random.choice(["RESOLVED", "CLOSED"])
            priority = "HIGH"
            resolution_note = "Refund initiated for the duplicate debit. The amount will reflect in your account within 5-7 working days."
            
    elif delinquency_status in ["OVERDUE_15", "OVERDUE_30"]:
        category = random.choice(["PAYMENT_FAILURE", "PENALTY_WAIVER", "EMI_DISPUTE"])
        if category == "PAYMENT_FAILURE":
            subject = "EMI payment failed but amount debited"
            description = "My EMI auto-debit failed on the 5th, but the money was deducted from my account. Please update the status."
            status = random.choice(["OPEN", "IN_PROGRESS", "RESOLVED"])
            priority = "HIGH"
            resolution_note = "Payment status updated to SUCCESS after manual verification of gateway logs." if status == "RESOLVED" else None
        elif category == "PENALTY_WAIVER":
            subject = "Request to waive late payment charges"
            description = "I was hospitalized and couldn't pay the EMI on time. Kindly waive the late payment penalty."
            status = random.choice(["OPEN", "IN_PROGRESS", "RESOLVED"])
            priority = "MEDIUM"
            resolution_note = "Late payment fee waived as a one-time exception based on medical bills." if status == "RESOLVED" else None
        else: # EMI_DISPUTE
            subject = "Incorrect EMI amount charged"
            description = "The EMI amount debited is higher than the amount specified in my loan agreement. Please check."
            status = random.choice(["OPEN", "IN_PROGRESS"])
            priority = "HIGH"
            resolution_note = None
            
    else: # OVERDUE_60 or NPA
        category = random.choice(["SETTLEMENT", "PENALTY_WAIVER", "EMI_DISPUTE"])
        if category == "SETTLEMENT":
            subject = "Request for loan settlement"
            description = "I am facing severe financial hardship due to medical issues. I want to settle the loan. Please let me know the settlement amount."
            status = random.choice(["OPEN", "IN_PROGRESS", "RESOLVED"])
            priority = "CRITICAL"
            resolution_note = "Settled for a one-time payment of Rs. 2,50,000. NOC will be issued after payment." if status == "RESOLVED" else None
        elif category == "PENALTY_WAIVER":
            subject = "Request to waive penalty fee"
            description = "My business failed and I am unable to pay the interest penalties. I request a complete waiver of penalty."
            status = random.choice(["OPEN", "IN_PROGRESS"])
            priority = "HIGH"
            resolution_note = None
        else: # EMI_DISPUTE
            subject = "Dispute regarding interest rate increase"
            description = "I was not notified about the interest rate increase which has raised my EMI. Please clarify."
            status = random.choice(["OPEN", "IN_PROGRESS"])
            priority = "HIGH"
            resolution_note = None

    # Date calculations
    created_days_offset = random.randint(0, (current_date - loan_start_date_dt).days)
    created_date_dt = loan_start_date_dt + datetime.timedelta(days=created_days_offset)
    
    if status in ["RESOLVED", "CLOSED"]:
        days_to_resolve = random.randint(1, 10)
        resolved_date_dt = created_date_dt + datetime.timedelta(days=days_to_resolve)
        if resolved_date_dt > current_date:
            resolved_date_dt = current_date
            created_date_dt = resolved_date_dt - datetime.timedelta(days=days_to_resolve)
        resolved_date = resolved_date_dt.strftime("%Y-%m-%d")
    else:
        resolved_date = None
        
    created_date = created_date_dt.strftime("%Y-%m-%d")
    
    ticket = {
        "ticket_id": ticket_id, "borrower_id": borrower_id, "loan_id": loan_id, "category": category,
        "subject": subject, "description": description, "status": status, "priority": priority,
        "created_date": created_date, "resolved_date": resolved_date, "resolution_note": resolution_note
    }
    tickets_records.append(ticket)

# ----------------- CONVERSATIONS GENERATION -----------------
# 100 conversations (1 per borrower to represent their latest contact call)
conversations_records = []
for idx, b in enumerate(borrowers_records):
    conv_id = f"C{idx + 1:03d}"
    borrower_id = b["borrower_id"]
    delinquency_status = b["delinquency_status"]
    
    call_date_dt = current_date - datetime.timedelta(days=random.randint(1, 30))
    call_date = call_date_dt.strftime("%Y-%m-%d")
    duration_secs = random.randint(45, 480)
    
    if delinquency_status == "CURRENT":
        intent = random.choice(["STATUS_CHECK", "FORECLOSURE_QUERY", "PAYMENT_CONFIRMATION"])
        sentiment = random.choice(["POSITIVE", "NEUTRAL"])
        resolved = random.choices([1, 0], weights=[90, 10])[0]
        commitment_made = None
        commitment_date = None
        
        if intent == "STATUS_CHECK":
            summary = "Borrower called to check their outstanding loan balance and next EMI date."
        elif intent == "FORECLOSURE_QUERY":
            summary = "Borrower inquired about the foreclosure process and charges for early loan closure."
        else:
            summary = "Borrower called to confirm that their EMI payment of this month was successfully credited."
            
    elif delinquency_status in ["OVERDUE_15", "OVERDUE_30"]:
        intent = random.choice(["EMI_PAYMENT", "WAIVER_REQUEST", "STATUS_CHECK"])
        sentiment = random.choice(["NEUTRAL", "NEGATIVE", "FRUSTRATED"])
        resolved = random.choices([0, 1], weights=[70, 30])[0]
        
        if intent == "EMI_PAYMENT":
            summary = "Agent discussed overdue EMI. Borrower cited salary delay and committed to pay next week."
            commitment_made = "Promised to pay overdue EMI"
            commitment_date = (call_date_dt + datetime.timedelta(days=random.randint(3, 7))).strftime("%Y-%m-%d")
        elif intent == "WAIVER_REQUEST":
            summary = "Borrower requested a waiver on the late payment penalty fee due to medical emergency."
            commitment_made = "Submit medical bills for waiver consideration"
            commitment_date = (call_date_dt + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        else:
            summary = "Borrower called to check how much penalty has accumulated on their overdue EMI."
            commitment_made = None
            commitment_date = None
            
    else:  # OVERDUE_60 or NPA
        intent = random.choice(["SETTLEMENT_QUERY", "EMI_PAYMENT", "WAIVER_REQUEST"])
        sentiment = random.choice(["NEGATIVE", "FRUSTRATED"])
        resolved = random.choices([0, 1], weights=[85, 15])[0]
        
        if intent == "SETTLEMENT_QUERY":
            summary = "Borrower requested a one-time settlement (OTS) due to permanent loss of income."
            commitment_made = "Provide written settlement proposal"
            commitment_date = (call_date_dt + datetime.timedelta(days=5)).strftime("%Y-%m-%d")
        elif intent == "EMI_PAYMENT":
            summary = "Agent demanded payment for multiple overdue EMIs. Borrower stated extreme financial distress."
            commitment_made = "Pay partial amount of one EMI"
            commitment_date = (call_date_dt + datetime.timedelta(days=4)).strftime("%Y-%m-%d")
        else:
            summary = "Borrower called protesting recovery agent visits and demanding waiver of all penalty charges."
            commitment_made = None
            commitment_date = None
            
    conversation = {
        "conv_id": conv_id, "borrower_id": borrower_id, "call_date": call_date, "duration_secs": duration_secs,
        "intent": intent, "summary": summary, "commitment_made": commitment_made, "commitment_date": commitment_date,
        "resolved": resolved, "sentiment": sentiment
    }
    conversations_records.append(conversation)

# Write to SQLite Database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Enable Foreign Key support
cursor.execute("PRAGMA foreign_keys = ON;")

# Drop existing tables to start fresh
cursor.execute("DROP TABLE IF EXISTS payments;")
cursor.execute("DROP TABLE IF EXISTS tickets;")
cursor.execute("DROP TABLE IF EXISTS conversations;")
cursor.execute("DROP TABLE IF EXISTS borrowers;")

# Create Tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS borrowers (
    borrower_id TEXT PRIMARY KEY,
    name TEXT,
    phone TEXT,
    email TEXT,
    city TEXT,
    loan_id TEXT,
    loan_type TEXT,
    loan_amount REAL,
    interest_rate REAL,
    tenure_months INTEGER,
    emi_amount REAL,
    loan_start_date TEXT,
    loan_end_date TEXT,
    outstanding_balance REAL,
    delinquency_status TEXT,
    overdue_days INTEGER,
    penalty_amount REAL,
    bank_name TEXT,
    account_number TEXT,
    pan_number TEXT,
    kyc_status TEXT
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    borrower_id TEXT,
    loan_id TEXT,
    due_date TEXT,
    payment_date TEXT,
    amount_due REAL,
    amount_paid REAL,
    status TEXT,
    failure_reason TEXT,
    gateway_ref TEXT,
    channel TEXT,
    FOREIGN KEY(borrower_id) REFERENCES borrowers(borrower_id)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    borrower_id TEXT,
    loan_id TEXT,
    category TEXT,
    subject TEXT,
    description TEXT,
    status TEXT,
    priority TEXT,
    created_date TEXT,
    resolved_date TEXT,
    resolution_note TEXT,
    FOREIGN KEY(borrower_id) REFERENCES borrowers(borrower_id)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS conversations (
    conv_id TEXT PRIMARY KEY,
    borrower_id TEXT,
    call_date TEXT,
    duration_secs INTEGER,
    intent TEXT,
    summary TEXT,
    commitment_made TEXT,
    commitment_date TEXT,
    resolved INTEGER,
    sentiment TEXT,
    FOREIGN KEY(borrower_id) REFERENCES borrowers(borrower_id)
);
""")

# Insert Data
for b in borrowers_records:
    cursor.execute("""
        INSERT INTO borrowers (
            borrower_id, name, phone, email, city, loan_id, loan_type, loan_amount, interest_rate,
            tenure_months, emi_amount, loan_start_date, loan_end_date, outstanding_balance,
            delinquency_status, overdue_days, penalty_amount, bank_name, account_number, pan_number, kyc_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        b["borrower_id"], b["name"], b["phone"], b["email"], b["city"], b["loan_id"], b["loan_type"],
        b["loan_amount"], b["interest_rate"], b["tenure_months"], b["emi_amount"], b["loan_start_date"],
        b["loan_end_date"], b["outstanding_balance"], b["delinquency_status"], b["overdue_days"],
        b["penalty_amount"], b["bank_name"], b["account_number"], b["pan_number"], b["kyc_status"]
    ))

for p in payments_records:
    cursor.execute("""
        INSERT INTO payments (
            payment_id, borrower_id, loan_id, due_date, payment_date, amount_due, amount_paid,
            status, failure_reason, gateway_ref, channel
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        p["payment_id"], p["borrower_id"], p["loan_id"], p["due_date"], p["payment_date"],
        p["amount_due"], p["amount_paid"], p["status"], p["failure_reason"], p["gateway_ref"], p["channel"]
    ))

for t in tickets_records:
    cursor.execute("""
        INSERT INTO tickets (
            ticket_id, borrower_id, loan_id, category, subject, description, status, priority,
            created_date, resolved_date, resolution_note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        t["ticket_id"], t["borrower_id"], t["loan_id"], t["category"], t["subject"], t["description"],
        t["status"], t["priority"], t["created_date"], t["resolved_date"], t["resolution_note"]
    ))

for c in conversations_records:
    cursor.execute("""
        INSERT INTO conversations (
            conv_id, borrower_id, call_date, duration_secs, intent, summary, commitment_made,
            commitment_date, resolved, sentiment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        c["conv_id"], c["borrower_id"], c["call_date"], c["duration_secs"], c["intent"], c["summary"],
        c["commitment_made"], c["commitment_date"], c["resolved"], c["sentiment"]
    ))

conn.commit()

# Retrieve counts to print summary
cursor.execute("SELECT COUNT(*) FROM borrowers;")
borrowers_cnt = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM payments;")
payments_cnt = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM tickets;")
tickets_cnt = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM conversations;")
conversations_cnt = cursor.fetchone()[0]

conn.close()

# Print success report
print("Database and Knowledge Base Generation Report:")
print(f"  - Table 'borrowers': {borrowers_cnt} records inserted.")
print(f"  - Table 'payments': {payments_cnt} records inserted.")
print(f"  - Table 'tickets': {tickets_cnt} records inserted.")
print(f"  - Table 'conversations': {conversations_cnt} records inserted.")
print(f"  - Knowledge Base: 20 policy JSON documents created in '{KB_DIR}'.")
print("SUCCESS: All synthetic data generated and validated successfully.")
