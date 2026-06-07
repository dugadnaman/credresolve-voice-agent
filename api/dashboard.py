import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import uvicorn
from dotenv import load_dotenv
from dataclasses import asdict

# Load env variables
load_dotenv()

app = FastAPI(title="CredResolve AI Inbound Voice Agent Dashboard")

# Keep a module-level dictionary to cache agent conversations keyed by phone
agents = {}

@app.get("/api/borrowers")
def get_borrowers():
    db_path = os.getenv("DB_PATH", "data/borrowers.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT borrower_id, name, phone, loan_type, delinquency_status, emi_amount, outstanding_balance, penalty_amount, overdue_days 
            FROM borrowers
        """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/api/context/{phone}")
def get_context(phone: str):
    from core.context_engine import ContextEngine
    context = ContextEngine.build_context(phone)
    if not context:
        return {"error": "Borrower not found"}
    return asdict(context)

@app.get("/api/systems/{phone}")
def get_systems_profile(phone: str):
    from core.system_integrations import UnifiedDataAggregator
    agg = UnifiedDataAggregator()
    profile = agg.get_unified_profile(phone)
    return profile

@app.get("/api/memory/{borrower_id}")
def get_memory(borrower_id: str):
    from core.memory_store import MemoryStore
    store = MemoryStore()
    mem = store.get_borrower_memory(borrower_id)
    
    # Parse commitment values if they are JSON strings
    parsed_commitments = []
    for c in mem.get("commitments", []):
        try:
            c_val = json.loads(c["value"])
            parsed_commitments.append({
                "amount": c_val.get("amount"),
                "date": c_val.get("date"),
                "reason": c_val.get("reason"),
                "fulfilled": c_val.get("fulfilled"),
                "created_at": c_val.get("created_at"),
                "fulfilled_at": c_val.get("fulfilled_at", None)
            })
        except Exception:
            parsed_commitments.append({"value": c["value"]})
            
    return {
        "commitments": parsed_commitments,
        "preferences": mem.get("preferences", {}),
        "risk_notes": [r["value"] for r in mem.get("risk_notes", [])],
        "callbacks": [{"date": cb["key"], "reason": cb["value"]} for cb in mem.get("callbacks", [])]
    }

@app.get("/api/chat")
def chat_with_agent(phone: str, message: str):
    from agent.agent import BorrowerAgent
    from core.context_engine import ContextEngine
    from core.diagnosis_layer import DiagnosisLayer
    from core.rag_engine import RAGEngine
    
    if phone not in agents:
        agents[phone] = BorrowerAgent()
        
    agent = agents[phone]
    response = agent.chat(phone, message)
    
    context = agent.context
    if not context:
        context = ContextEngine.build_context(phone)
        
    diagnosis = DiagnosisLayer.diagnose(context, message)
    
    rag_engine = RAGEngine()
    rag_docs = rag_engine.retrieve_for_intent(diagnosis.intent, context.risk_signals if context else None)
    
    return {
        "response": response,
        "intent": diagnosis.intent,
        "risk_signals": context.risk_signals if context else [],
        "known_facts": diagnosis.known_facts,
        "missing_info": diagnosis.missing_info,
        "retrieved_policies": [asdict(doc) for doc in rag_docs]
    }

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CredResolve AI Inbound Voice Agent Dashboard</title>
    <!-- Tailwind CSS v3 CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        darknavy: '#0f172a',
                        panelbg: '#1e293b',
                        bordercolor: '#334155',
                        textcol: '#e2e8f0',
                        accent: '#3b82f6',
                        success: '#22c55e',
                        warning: '#f59e0b',
                        danger: '#ef4444'
                    }
                }
            }
        }
    </script>
    <!-- Google Fonts: Inter -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
        }
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #0f172a;
        }
        ::-webkit-scrollbar-thumb {
            background: #334155;
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #3b82f6;
        }
    </style>
</head>
<body class="h-screen flex flex-col overflow-hidden">
    <!-- Header -->
    <header class="bg-panelbg border-b border-bordercolor px-6 py-4 flex items-center justify-between shadow-lg z-10">
        <div class="flex items-center space-x-3">
            <span class="text-2xl">🎙️</span>
            <div>
                <h1 class="text-xl font-bold tracking-tight text-white">CredResolve</h1>
                <p class="text-xs text-slate-400">AI Inbound Voice Agent Dashboard</p>
            </div>
        </div>
        <div class="flex items-center space-x-4">
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-success/20 text-success border border-success/30">
                <span class="w-1.5 h-1.5 mr-1.5 rounded-full bg-success animate-pulse"></span>
                System Online
            </span>
        </div>
    </header>

    <!-- Systems Integration Bar -->
    <div class="bg-darknavy border-b border-bordercolor px-6 py-3 flex items-center justify-between text-xs z-10">
        <div class="flex items-center space-x-3">
            <span class="font-bold text-white text-sm">🔗 Connected Systems</span>
            <span id="aggregation-status" class="text-slate-400 font-normal"></span>
        </div>
        <div class="flex space-x-6 flex-wrap gap-y-2">
            <!-- Zoho CRM -->
            <div class="flex items-center space-x-2 bg-panelbg/50 px-3 py-1 rounded-full border border-bordercolor cursor-help" title="Production: Zoho CRM API v2">
                <span id="badge-dot-crm" class="w-2.5 h-2.5 rounded-full bg-success"></span>
                <span class="font-semibold text-white">Zoho CRM</span>
                <span id="badge-status-crm" class="text-slate-400">Mock (Ready for API)</span>
            </div>
            <!-- Loan Management System -->
            <div class="flex items-center space-x-2 bg-panelbg/50 px-3 py-1 rounded-full border border-bordercolor cursor-help" title="Production: Finflux / Nucleus LMS API">
                <span id="badge-dot-lms" class="w-2.5 h-2.5 rounded-full bg-success"></span>
                <span class="font-semibold text-white">Loan Management System</span>
                <span id="badge-status-lms" class="text-slate-400">Mock (Ready for API)</span>
            </div>
            <!-- Razorpay Gateway -->
            <div class="flex items-center space-x-2 bg-panelbg/50 px-3 py-1 rounded-full border border-bordercolor cursor-help" title="Production: Razorpay Payment Gateway API">
                <span id="badge-dot-payments" class="w-2.5 h-2.5 rounded-full bg-success"></span>
                <span class="font-semibold text-white">Razorpay Gateway</span>
                <span id="badge-status-payments" class="text-slate-400">Mock (Ready for API)</span>
            </div>
            <!-- Freshdesk -->
            <div class="flex items-center space-x-2 bg-panelbg/50 px-3 py-1 rounded-full border border-bordercolor cursor-help" title="Production: Freshdesk REST API v2">
                <span id="badge-dot-freshdesk" class="w-2.5 h-2.5 rounded-full bg-success"></span>
                <span class="font-semibold text-white">Freshdesk</span>
                <span id="badge-status-freshdesk" class="text-slate-400">Mock (Ready for API)</span>
            </div>
            <!-- Confluence KB -->
            <div class="flex items-center space-x-2 bg-panelbg/50 px-3 py-1 rounded-full border border-bordercolor cursor-help" title="Production: Confluence REST API">
                <span id="badge-dot-kb" class="w-2.5 h-2.5 rounded-full bg-success"></span>
                <span class="font-semibold text-white">Confluence KB</span>
                <span id="badge-status-kb" class="text-slate-400">Mock (Ready for API)</span>
            </div>
        </div>
    </div>

    <!-- Main Container -->
    <main class="flex-1 flex overflow-hidden">
        <!-- Left Panel: Borrowers -->
        <section class="w-1/3 bg-darknavy border-r border-bordercolor flex flex-col h-full">
            <div class="p-4 border-b border-bordercolor bg-panelbg/30">
                <h2 class="text-lg font-semibold text-white mb-3 flex items-center justify-between">
                    <span>Borrowers</span>
                    <span id="borrower-count" class="text-xs text-slate-400 font-normal">0 borrowers</span>
                </h2>
                <div class="relative">
                    <input type="text" id="search" placeholder="Search by name or phone..." class="w-full bg-panelbg border border-bordercolor rounded-lg px-4 py-2 text-sm text-textcol placeholder-slate-400 focus:outline-none focus:border-accent transition-colors">
                    <span class="absolute right-3 top-2.5 text-slate-400">🔍</span>
                </div>
            </div>
            <div id="borrowers-list" class="flex-1 overflow-y-auto p-4 space-y-3">
                <!-- Borrower cards loaded dynamically -->
                <div class="flex justify-center items-center h-32">
                    <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-accent"></div>
                </div>
            </div>
        </section>

        <!-- Middle Panel: Borrower Context -->
        <section class="w-1/3 bg-panelbg border-r border-bordercolor flex flex-col h-full overflow-y-auto">
            <div class="p-4 border-b border-bordercolor bg-darknavy/30">
                <h2 class="text-lg font-semibold text-white">Borrower Context</h2>
            </div>
            <div id="context-content" class="p-6 space-y-6">
                <!-- Default state -->
                <div class="text-center text-slate-400 py-20">
                    <span class="text-5xl block mb-4">👤</span>
                    Select a borrower to inspect unified profile
                </div>
            </div>
        </section>

        <!-- Right Panel: Live Conversation -->
        <section class="w-1/3 bg-darknavy flex flex-col h-full">
            <div class="p-4 border-b border-bordercolor bg-panelbg/30 flex items-center justify-between">
                <div class="flex items-center space-x-2">
                    <h2 class="text-lg font-semibold text-white">Live Conversation</h2>
                    <span id="intent-badge" class="hidden px-2.5 py-0.5 rounded-full text-xs font-semibold bg-accent/20 text-accent border border-accent/30 uppercase"></span>
                </div>
                <button type="button" id="speak-toggle-btn" onclick="toggleSpeaker()" class="text-slate-400 hover:text-white transition-colors" title="Toggle Text-to-Speech">
                    🔊
                </button>
            </div>

            <!-- Scenario Buttons -->
            <div class="px-4 py-2 border-b border-bordercolor bg-panelbg/10 flex flex-wrap gap-1.5">
                <button type="button" onclick="sendScenarioMsg('Why was a penalty charged on my account?')" class="scenario-btn px-2 py-1 text-[10px] bg-panelbg hover:bg-slate-700 text-slate-300 rounded border border-bordercolor transition-colors disabled:opacity-50" disabled>Scenario 3: Penalty</button>
                <button type="button" onclick="sendScenarioMsg('Can my penalty be waived? The payment failed due to a bank error.')" class="scenario-btn px-2 py-1 text-[10px] bg-panelbg hover:bg-slate-700 text-slate-300 rounded border border-bordercolor transition-colors disabled:opacity-50" disabled>Scenario 5: Waiver</button>
                <button type="button" onclick="sendScenarioMsg('My salary got delayed. I will pay my EMI next Friday.')" class="scenario-btn px-2 py-1 text-[10px] bg-panelbg hover:bg-slate-700 text-slate-300 rounded border border-bordercolor transition-colors disabled:opacity-50" disabled>Scenario 6a: Commitment</button>
                <button type="button" onclick="sendScenarioMsg('Hello, I am calling to follow up on my previous commitment.')" class="scenario-btn px-2 py-1 text-[10px] bg-panelbg hover:bg-slate-700 text-slate-300 rounded border border-bordercolor transition-colors disabled:opacity-50" disabled>Scenario 6b: Follow-up</button>
            </div>
            
            <!-- Context clues / Diagnosis above conversation -->
            <div id="diagnosis-header" class="border-b border-bordercolor p-4 bg-panelbg/10 hidden grid grid-cols-2 gap-4 text-xs">
                <div>
                    <h4 class="font-semibold text-slate-400 mb-1">Known Facts</h4>
                    <ul id="known-facts" class="list-disc pl-4 space-y-1 text-slate-300 max-h-24 overflow-y-auto"></ul>
                </div>
                <div>
                    <h4 class="font-semibold text-slate-400 mb-1">Missing Info</h4>
                    <ul id="missing-info" class="list-disc pl-4 space-y-1 text-slate-300 max-h-24 overflow-y-auto"></ul>
                </div>
            </div>

            <!-- Retrieved Policies Collapsible -->
            <div id="policies-section" class="border-b border-bordercolor hidden">
                <button onclick="togglePolicies()" class="w-full px-4 py-2 bg-panelbg/50 flex items-center justify-between text-xs font-medium text-slate-300 hover:bg-panelbg/70 transition-colors">
                    <span>📖 Retrieved Policies (RAG)</span>
                    <span id="policies-arrow">▼</span>
                </button>
                <div id="policies-content" class="hidden p-4 bg-panelbg/20 space-y-3 max-h-48 overflow-y-auto text-xs">
                    <!-- Loaded dynamically -->
                </div>
            </div>

            <!-- Conversation History scrollable area -->
            <div id="chat-history" class="flex-1 overflow-y-auto p-4 space-y-4 flex flex-col">
                <div class="text-center text-slate-500 my-auto text-sm">
                    Select a borrower and send a message to start conversation
                </div>
            </div>

            <!-- Text Input Area -->
            <div class="p-4 border-t border-bordercolor bg-panelbg/30">
                <form id="chat-form" onsubmit="sendMessage(event)" class="flex space-x-2 items-center">
                    <input type="text" id="message-input" placeholder="Type a message to the agent..." disabled class="flex-1 bg-panelbg border border-bordercolor rounded-lg px-4 py-2.5 text-sm text-textcol placeholder-slate-400 focus:outline-none focus:border-accent disabled:opacity-50 transition-colors">
                    <button type="button" id="mic-btn" disabled onclick="toggleVoiceInput()" class="w-10 h-10 flex items-center justify-center rounded-full bg-accent hover:bg-accent/80 text-white transition-colors disabled:opacity-50 flex-shrink-0" title="Speak message">
                        <span id="mic-icon">🎤</span>
                    </button>
                    <button type="submit" id="send-btn" disabled class="bg-accent hover:bg-accent/80 text-white rounded-lg px-5 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50">
                        Send
                    </button>
                </form>
            </div>
        </section>
    </main>

    <script>
        let allBorrowers = [];
        let selectedBorrower = null;
        let chatMessages = {};

        // Load all borrowers on load
        async function fetchBorrowers() {
            try {
                const res = await fetch('/api/borrowers');
                allBorrowers = await res.json();
                renderBorrowers(allBorrowers);
                document.getElementById('borrower-count').innerText = `${allBorrowers.length} borrowers`;
            } catch (err) {
                console.error("Error fetching borrowers:", err);
            }
        }

        // Render borrower list
        function renderBorrowers(borrowers) {
            const listContainer = document.getElementById('borrowers-list');
            listContainer.innerHTML = '';
            
            if (borrowers.length === 0) {
                listContainer.innerHTML = `<div class="text-slate-500 text-center py-10 text-sm">No borrowers found</div>`;
                return;
            }

            borrowers.forEach(b => {
                let badgeColor = 'bg-success/20 text-success border-success/30';
                if (b.delinquency_status === 'OVERDUE_15') badgeColor = 'bg-warning/20 text-warning border-warning/30';
                else if (b.delinquency_status === 'OVERDUE_30') badgeColor = 'bg-orange-500/20 text-orange-400 border-orange-500/30';
                else if (b.delinquency_status.includes('OVERDUE') || b.delinquency_status === 'NPA') badgeColor = 'bg-danger/20 text-danger border-danger/30';

                const card = document.createElement('div');
                card.className = `p-4 rounded-xl border transition-all duration-200 cursor-pointer ${selectedBorrower && selectedBorrower.borrower_id === b.borrower_id ? 'bg-panelbg border-accent shadow-md scale-[1.01]' : 'bg-panelbg/50 border-bordercolor hover:border-slate-500 hover:bg-panelbg/70 hover:scale-[1.005]'}`;
                card.onclick = () => loadBorrower(b);
                
                card.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <h3 class="font-semibold text-white">${b.name}</h3>
                        <span class="px-2 py-0.5 rounded text-[10px] font-semibold uppercase border ${badgeColor}">${b.delinquency_status}</span>
                    </div>
                    <div class="text-xs text-slate-400 space-y-1">
                        <div class="flex justify-between"><span>Loan: ${b.loan_type}</span></div>
                        <div class="flex justify-between"><span>EMI Amount: ₹${Number(b.emi_amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span></div>
                        <div class="flex justify-between"><span>Overdue Days: ${b.overdue_days} days</span></div>
                    </div>
                `;
                listContainer.appendChild(card);
            });
        }

        // Search filter
        document.getElementById('search').addEventListener('input', (e) => {
            const val = e.target.value.toLowerCase();
            const filtered = allBorrowers.filter(b => 
                b.name.toLowerCase().includes(val) || 
                b.phone.includes(val) || 
                b.borrower_id.toLowerCase().includes(val)
            );
            renderBorrowers(filtered);
        });

        // Load specific borrower context
        async function loadBorrower(borrower) {
            selectedBorrower = borrower;
            renderBorrowers(allBorrowers); // Re-render to highlight selected
            
            const contentContainer = document.getElementById('context-content');
            contentContainer.innerHTML = `
                <div class="flex justify-center items-center py-20">
                    <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-accent"></div>
                </div>
            `;
            
            try {
                animateSystemsAggregation();
                const resSystems = fetch(`/api/systems/${borrower.phone}`);
                const res = await fetch(`/api/context/${borrower.phone}`);
                const ctx = await res.json();
                renderContext(ctx);
                enableChat();
                renderChatHistory();
                await fetchMemory(borrower.borrower_id);
                
                // Read response from systems integration profile to ensure correct aggregation
                const systemsRes = await resSystems;
                const systemsProfile = await systemsRes.json();
                console.log("Unified systems profile retrieved:", systemsProfile);
            } catch (err) {
                console.error("Error loading borrower context:", err);
                contentContainer.innerHTML = `<div class="text-danger text-center">Failed to load context.</div>`;
            }
        }

        // Render Context Details
        function renderContext(ctx) {
            const container = document.getElementById('context-content');
            const bp = ctx.borrower;
            const ps = ctx.payments;
            const ts = ctx.tickets;
            const cs = ctx.conversations;

            let badgeColor = 'bg-success/20 text-success border-success/30';
            if (bp.delinquency_status === 'OVERDUE_15') badgeColor = 'bg-warning/20 text-warning border-warning/30';
            else if (bp.delinquency_status === 'OVERDUE_30') badgeColor = 'bg-orange-500/20 text-orange-400 border-orange-500/30';
            else if (bp.delinquency_status.includes('OVERDUE') || bp.delinquency_status === 'NPA') badgeColor = 'bg-danger/20 text-danger border-danger/30';

            // Risk tags
            const riskTags = ctx.risk_signals.map(s => 
                `<span class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold bg-danger/10 text-danger border border-danger/20">${s}</span>`
            ).join(' ') || '<span class="text-xs text-slate-500">None</span>';

            // Payment attempts history
            let paymentHTML = '<p class="text-xs text-slate-500">No recent payments logged</p>';
            if (ps.recent_failures && ps.recent_failures.length > 0) {
                paymentHTML = ps.recent_failures.slice(0, 3).map(f => `
                    <div class="flex justify-between items-center text-xs p-2 rounded bg-darknavy/30 border border-bordercolor">
                        <div>
                            <p class="font-medium text-white">${f.payment_date || 'N/A'}</p>
                            <p class="text-[10px] text-slate-400">Failed: ${f.failure_reason || 'Unknown error'}</p>
                        </div>
                        <span class="text-danger font-semibold">-₹${Number(bp.emi_amount).toLocaleString('en-IN', {maximumFractionDigits: 2})}</span>
                    </div>
                `).join(' ');
            } else if (ps.last_payment_date) {
                paymentHTML = `
                    <div class="flex justify-between items-center text-xs p-2 rounded bg-darknavy/30 border border-bordercolor">
                        <div>
                            <p class="font-medium text-white">${ps.last_payment_date}</p>
                            <p class="text-[10px] text-success">${ps.last_payment_status}</p>
                        </div>
                        <span class="text-success font-semibold">+₹${Number(ps.last_payment_amount).toLocaleString('en-IN', {maximumFractionDigits: 2})}</span>
                    </div>
                `;
            }

            // Commitment Warn Box
            let commitmentHTML = '';
            if (cs.pending_commitment) {
                commitmentHTML = `
                    <div class="bg-warning/10 border border-warning/30 rounded-xl p-4 flex items-start space-x-2 text-warning">
                        <span class="text-base">⚠️</span>
                        <div class="text-xs">
                            <p class="font-semibold mb-0.5">Pending Payment Commitment</p>
                            <p class="text-slate-300">Committed: ${cs.pending_commitment} by ${cs.commitment_date}</p>
                            ${cs.commitment_overdue ? '<p class="text-danger font-medium mt-1">Status: OVERDUE</p>' : ''}
                        </div>
                    </div>
                `;
            }

            container.innerHTML = `
                <!-- Profile Summary -->
                <div class="space-y-4 bg-darknavy/30 rounded-2xl p-5 border border-bordercolor">
                    <div class="flex justify-between items-center">
                        <h3 class="text-xl font-bold text-white">${bp.name}</h3>
                        <span class="px-2.5 py-0.5 rounded text-xs font-semibold uppercase border ${badgeColor}">${bp.delinquency_status}</span>
                    </div>
                    <div class="grid grid-cols-2 gap-y-3 gap-x-4 text-xs">
                        <div><p class="text-slate-400">Borrower ID</p><p class="text-white font-medium">${bp.borrower_id}</p></div>
                        <div><p class="text-slate-400">Phone</p><p class="text-white font-medium">${bp.phone}</p></div>
                        <div><p class="text-slate-400">Loan Type</p><p class="text-white font-medium">${bp.loan_type}</p></div>
                        <div><p class="text-slate-400">Bank Name</p><p class="text-white font-medium">${bp.bank_name || 'N/A'}</p></div>
                        <div class="col-span-2 border-t border-bordercolor/50 my-1"></div>
                        <div><p class="text-slate-400">Outstanding Balance</p><p class="text-white font-semibold">₹${Number(bp.outstanding_balance).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p></div>
                        <div><p class="text-slate-400">EMI Amount</p><p class="text-white font-semibold">₹${Number(bp.emi_amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p></div>
                        <div><p class="text-slate-400">Penalty Charges</p><p class="text-danger font-semibold">₹${Number(bp.penalty_amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p></div>
                        <div><p class="text-slate-400">Overdue Days</p><p class="text-white font-medium">${bp.overdue_days} days</p></div>
                    </div>
                </div>

                <!-- Commitment Box -->
                ${commitmentHTML}

                <!-- Risk Signals -->
                <div class="space-y-2">
                    <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">Risk Signals</h4>
                    <div class="flex flex-wrap gap-1.5">${riskTags}</div>
                </div>

                <!-- Payment History -->
                <div class="space-y-2">
                    <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">Payment Attempts</h4>
                    <div class="space-y-2">${paymentHTML}</div>
                </div>

                <!-- Agent Notes -->
                <div class="space-y-2">
                    <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">Unified Brief</h4>
                    <div class="bg-darknavy/40 border border-bordercolor rounded-xl p-4 text-xs text-slate-300 leading-relaxed">${ctx.agent_notes}</div>
                </div>

                <!-- Memory Panel -->
                <div class="space-y-2">
                    <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">Memory Store</h4>
                    <div id="memory-content" class="bg-darknavy/40 border border-bordercolor rounded-xl p-4 text-xs text-slate-300 space-y-2">
                        <div class="text-slate-500">Loading memory logs...</div>
                    </div>
                </div>

                <!-- Data Sources Panel -->
                <div class="space-y-2">
                    <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">🔗 Data Sources</h4>
                    <div class="bg-darknavy/40 border border-bordercolor rounded-xl p-4 text-xs text-slate-300 space-y-2">
                        <div class="grid grid-cols-3 gap-2">
                            <span class="font-semibold text-slate-400">System</span>
                            <span class="font-semibold text-slate-400 col-span-2">Retrieved Fields</span>
                            
                            <span class="text-white">CRM</span>
                            <span class="text-slate-300 col-span-2">Name, KYC, Contact</span>
                            
                            <span class="text-white">LMS</span>
                            <span class="text-slate-300 col-span-2">Loan details, EMI schedule</span>
                            
                            <span class="text-white">Razorpay</span>
                            <span class="text-slate-300 col-span-2">Payment history</span>
                            
                            <span class="text-white">Freshdesk</span>
                            <span class="text-slate-300 col-span-2">Support tickets</span>
                            
                            <span class="text-white">Confluence</span>
                            <span class="text-slate-300 col-span-2">Policies retrieved</span>
                        </div>
                    </div>
                </div>
            `;
        }

        // Enable Chat Input
        function enableChat() {
            document.getElementById('message-input').removeAttribute('disabled');
            document.getElementById('send-btn').removeAttribute('disabled');
            document.getElementById('mic-btn').removeAttribute('disabled');
            document.querySelectorAll('.scenario-btn').forEach(btn => btn.removeAttribute('disabled'));
        }

        // Render Chat History
        function renderChatHistory() {
            const chatContainer = document.getElementById('chat-history');
            chatContainer.innerHTML = '';
            
            const phone = selectedBorrower.phone;
            const messages = chatMessages[phone] || [];

            if (messages.length === 0) {
                chatContainer.innerHTML = `<div class="text-center text-slate-500 my-auto text-sm">Type a message to start conversation with ${selectedBorrower.name}</div>`;
                return;
            }

            messages.forEach(msg => {
                const bubble = document.createElement('div');
                bubble.className = `flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`;
                
                const innerClass = msg.role === 'user' 
                    ? 'bg-accent text-white rounded-br-none' 
                    : 'bg-panelbg text-slate-200 border border-bordercolor rounded-bl-none';
                
                bubble.innerHTML = `
                    <div class="max-w-[80%] rounded-2xl px-4 py-2.5 text-sm shadow-sm leading-relaxed ${innerClass}">
                        ${msg.content}
                    </div>
                `;
                chatContainer.appendChild(bubble);
            });

            // Scroll to bottom
            setTimeout(() => {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }, 50);
        }

        // Send Message to Agent
        async function sendMessage(e) {
            e.preventDefault();
            const inputField = document.getElementById('message-input');
            const message = inputField.value.trim();
            if (!message || !selectedBorrower) return;

            const phone = selectedBorrower.phone;
            
            // Append User Message immediately
            if (!chatMessages[phone]) {
                chatMessages[phone] = [];
            }
            chatMessages[phone].push({ role: 'user', content: message });
            renderChatHistory();
            inputField.value = '';

            try {
                const params = new URLSearchParams({ phone, message });
                const res = await fetch(`/api/chat?${params.toString()}`);
                const data = await res.json();

                // Append Agent Response
                chatMessages[phone].push({ role: 'agent', content: data.response });
                renderChatHistory();

                // Update Diagnosis Badges
                updateDiagnosisUI(data);

                // Reload Memory Store
                if (selectedBorrower) {
                    await fetchMemory(selectedBorrower.borrower_id);
                }

                // Text-to-Speech
                if (speakEnabled) {
                    speakResponse(data.response);
                }

            } catch (err) {
                console.error("Error sending message:", err);
                chatMessages[phone].push({ role: 'agent', content: "⚠️ Error generating response. Please check API configurations." });
                renderChatHistory();
            }
        }

        // Fetch and display borrower memory logs
        async function fetchMemory(borrowerId) {
            const memoryContainer = document.getElementById('memory-content');
            if (!memoryContainer) return;
            try {
                const res = await fetch(`/api/memory/${borrowerId}`);
                const data = await res.json();
                
                let html = '';
                
                // Unfulfilled commitment warning box
                const pending = data.commitments.find(c => !c.fulfilled);
                if (pending) {
                    html += `
                        <div class="bg-warning/10 border border-warning/30 rounded-lg p-3 text-warning mb-3 flex items-start space-x-2">
                            <span class="text-sm">⚠️</span>
                            <div>
                                <p class="font-semibold text-xs leading-snug">Pending commitment: Pay ₹${Number(pending.amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})} by ${pending.date}</p>
                                <p class="text-[10px] text-slate-300 mt-0.5">Reason: ${pending.reason || 'Not specified'}</p>
                            </div>
                        </div>
                    `;
                }
                
                // Preferences
                const prefs = data.preferences;
                let prefsHtml = '';
                if (prefs && Object.keys(prefs).length > 0) {
                    prefsHtml += `<div class="space-y-1">
                        <p class="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Preferences:</p>
                        <ul class="list-disc pl-4 space-y-0.5">`;
                    for (const [key, val] of Object.entries(prefs)) {
                        prefsHtml += `<li><span class="text-slate-400">${key}:</span> ${val}</li>`;
                    }
                    prefsHtml += `</ul></div>`;
                }
                
                // Risk Notes
                let riskHtml = '';
                if (data.risk_notes && data.risk_notes.length > 0) {
                    riskHtml += `<div class="space-y-1 mt-2">
                        <p class="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Risk Notes:</p>
                        <ul class="list-disc pl-4 space-y-0.5 text-danger">`;
                    data.risk_notes.forEach(note => {
                        riskHtml += `<li>${note}</li>`;
                    });
                    riskHtml += `</ul></div>`;
                }

                // Callbacks
                let callbackHtml = '';
                if (data.callbacks && data.callbacks.length > 0) {
                    callbackHtml += `<div class="space-y-1 mt-2">
                        <p class="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Callbacks:</p>
                        <ul class="list-disc pl-4 space-y-0.5">`;
                    data.callbacks.forEach(cb => {
                        callbackHtml += `<li>${cb.date}: ${cb.reason}</li>`;
                    });
                    callbackHtml += `</ul></div>`;
                }

                if (!pending && !prefsHtml && !riskHtml && !callbackHtml) {
                    html += `<div class="text-slate-500">No memory logs found.</div>`;
                } else {
                    html += prefsHtml + riskHtml + callbackHtml;
                }
                
                memoryContainer.innerHTML = html;
            } catch (err) {
                console.error("Error loading memory:", err);
                memoryContainer.innerHTML = `<div class="text-danger">Failed to load memory details.</div>`;
            }
        }

        // Send Scenario Message
        function sendScenarioMsg(message) {
            const inputField = document.getElementById('message-input');
            inputField.value = message;
            sendMessage({ preventDefault: () => {} });
        }

        // Animate Connected Systems Aggregation
        function animateSystemsAggregation() {
            const systems = [
                { dot: 'badge-dot-crm', status: 'badge-status-crm', name: 'Zoho CRM' },
                { dot: 'badge-dot-lms', status: 'badge-status-lms', name: 'Loan Management System' },
                { dot: 'badge-dot-payments', status: 'badge-status-payments', name: 'Razorpay Gateway' },
                { dot: 'badge-dot-freshdesk', status: 'badge-status-freshdesk', name: 'Freshdesk' },
                { dot: 'badge-dot-kb', status: 'badge-status-kb', name: 'Confluence KB' }
            ];

            const statusEl = document.getElementById('aggregation-status');
            statusEl.innerText = '• Aggregating data...';
            statusEl.className = 'text-warning font-semibold animate-pulse text-xs';

            // Reset all to yellow/Querying
            systems.forEach(sys => {
                const dot = document.getElementById(sys.dot);
                const stat = document.getElementById(sys.status);
                dot.className = 'w-2.5 h-2.5 rounded-full bg-warning animate-ping';
                stat.innerText = 'Querying...';
                stat.className = 'text-warning';
            });

            // Staggered green connection
            systems.forEach((sys, index) => {
                const startDelay = 50 * index; // 50ms stagger
                const duration = 300; // 300ms query duration

                setTimeout(() => {
                    setTimeout(() => {
                        const dot = document.getElementById(sys.dot);
                        const stat = document.getElementById(sys.status);
                        dot.className = 'w-2.5 h-2.5 rounded-full bg-success';
                        stat.innerText = 'Mock ✓';
                        stat.className = 'text-success font-semibold';
                        
                        if (index === systems.length - 1) {
                            statusEl.innerText = '• Data aggregated from 5 systems in 0.3s';
                            statusEl.className = 'text-success font-semibold text-xs';
                        }
                    }, duration);
                }, startDelay);
            });
        }

        // Speaker Enable state
        let speakEnabled = true;

        function toggleSpeaker() {
            speakEnabled = !speakEnabled;
            const btn = document.getElementById('speak-toggle-btn');
            if (speakEnabled) {
                btn.innerText = '🔊';
                btn.classList.remove('text-slate-500');
                btn.classList.add('text-slate-400');
            } else {
                btn.innerText = '🔇';
                btn.classList.remove('text-slate-400');
                btn.classList.add('text-slate-500');
            }
        }

        function speakResponse(text) {
            const cleaned = text.replace(/₹/g, 'rupees ').replace(/[^\w\s.,?!'-]/g, ' ');
            const utterance = new SpeechSynthesisUtterance(cleaned);
            utterance.rate = 0.95;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;
            // Pick a female voice if available
            const voices = window.speechSynthesis.getVoices();
            const female = voices.find(v => v.name.includes('Samantha') || v.name.includes('Female') || v.name.includes('Google UK English Female'));
            if (female) utterance.voice = female;
            window.speechSynthesis.speak(utterance);
        }

        // Voice Input Recognition Handler
        let recognition = null;
        let isListening = false;

        function toggleVoiceInput() {
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                alert("Speech recognition is not supported in this browser. Please use Chrome or Safari.");
                return;
            }

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            if (!recognition) {
                recognition = new SpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = false;
                recognition.lang = 'en-US';

                recognition.onstart = () => {
                    isListening = true;
                    document.getElementById('mic-icon').innerText = '🛑';
                    document.getElementById('mic-btn').classList.remove('bg-accent');
                    document.getElementById('mic-btn').classList.add('bg-danger');
                    document.getElementById('message-input').value = '';
                    document.getElementById('message-input').placeholder = 'Listening...';
                };

                recognition.onerror = (e) => {
                    console.error("Speech recognition error:", e.error);
                    resetMicUI();
                };

                recognition.onend = () => {
                    isListening = false;
                    resetMicUI();
                };

                recognition.onresult = (event) => {
                    const transcript = event.results[0][0].transcript;
                    const inputField = document.getElementById('message-input');
                    
                    inputField.placeholder = "Transcribing...";
                    inputField.value = transcript;
                    
                    // Auto submit
                    setTimeout(() => {
                        sendMessage({ preventDefault: () => {} });
                    }, 500);
                };
            }

            if (isListening) {
                recognition.stop();
            } else {
                recognition.start();
            }
        }

        function resetMicUI() {
            document.getElementById('mic-icon').innerText = '🎤';
            document.getElementById('mic-btn').classList.remove('bg-danger');
            document.getElementById('mic-btn').classList.add('bg-accent');
            document.getElementById('message-input').placeholder = 'Type a message to the agent...';
        }

        // Update Diagnosis, Intent & RAG UI
        function updateDiagnosisUI(data) {
            const intentBadge = document.getElementById('intent-badge');
            intentBadge.innerText = data.intent;
            intentBadge.classList.remove('hidden');

            const diagHeader = document.getElementById('diagnosis-header');
            diagHeader.classList.remove('hidden');

            const kFactsList = document.getElementById('known-facts');
            kFactsList.innerHTML = data.known_facts.map(f => `<li>${f}</li>`).join('') || '<li>None</li>';

            const mInfoList = document.getElementById('missing-info');
            mInfoList.innerHTML = data.missing_info.map(m => `<li>${m}</li>`).join('') || '<li>None</li>';

            // Retrieved Policies RAG list
            const policiesSection = document.getElementById('policies-section');
            policiesSection.classList.remove('hidden');

            const policiesContent = document.getElementById('policies-content');
            if (data.retrieved_policies && data.retrieved_policies.length > 0) {
                policiesContent.innerHTML = data.retrieved_policies.map(doc => `
                    <div class="border-b border-bordercolor pb-2 mb-2 last:border-0">
                        <p class="font-bold text-white">${doc.title} (${doc.category})</p>
                        <p class="text-slate-400 mt-1">${doc.content}</p>
                    </div>
                `).join('');
            } else {
                policiesContent.innerHTML = '<p class="text-slate-500">No matching policy documents retrieved.</p>';
            }
        }

        // Toggle Policies Section
        function togglePolicies() {
            const content = document.getElementById('policies-content');
            const arrow = document.getElementById('policies-arrow');
            if (content.classList.contains('hidden')) {
                content.classList.remove('hidden');
                arrow.innerText = '▲';
            } else {
                content.classList.add('hidden');
                arrow.innerText = '▼';
            }
        }

        // Init page
        fetchBorrowers();
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    uvicorn.run("api.dashboard:app", host="0.0.0.0", port=8001, reload=False)
