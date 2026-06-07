import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# 1200x900 pixels = 12x9 inches at 100 DPI
fig, ax = plt.subplots(figsize=(12, 9), dpi=100)
fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
fig.patch.set_facecolor('#0f172a')
ax.set_facecolor('#0f172a')
ax.set_xlim(0, 12)
ax.set_ylim(0, 9)
ax.axis('off')

# Title & Subtitle
ax.text(6.0, 8.6, "CredResolve AI Voice Agent — Architecture", color='white', fontsize=18, fontweight='bold', ha='center', va='center')
ax.text(6.0, 8.3, "Agentic Inbound Voice Agent for Borrower Support", color='#94a3b8', fontsize=11, ha='center', va='center')

# Connected Systems Left Panel (slate background)
panel = patches.FancyBboxPatch(
    (0.4, 1.25), 2.6, 6.4,
    boxstyle="round,pad=0.05",
    fc='#1e293b', ec='#334155', lw=1.5, zorder=2
)
ax.add_patch(panel)

ax.text(1.7, 7.35, "Connected Systems", color='white', fontsize=11, fontweight='bold', ha='center', va='center', zorder=3)

# 5 Systems in Left Panel
systems = [
    ("Zoho CRM", 6.5),
    ("Loan Management System", 5.5),
    ("Razorpay Gateway", 4.5),
    ("Freshdesk", 3.5),
    ("Confluence KB", 2.5)
]

for name, y in systems:
    # Green status dot
    dot = patches.Circle((0.8, y), 0.08, color='#22c55e', zorder=3)
    ax.add_patch(dot)
    ax.text(1.05, y, name, color='#e2e8f0', fontsize=9.5, ha='left', va='center', zorder=3)

# Draw Box helper function
def draw_box(x, y, w, h, text, subtext="", fc='white', ec='none', text_color='white'):
    x_min = x - w/2
    y_min = y - h/2
    
    # Shadow
    shadow = patches.FancyBboxPatch(
        (x_min + 0.05, y_min - 0.05), w, h,
        boxstyle="round,pad=0.03",
        fc='black', alpha=0.3, zorder=1
    )
    ax.add_patch(shadow)
    
    # Main Box
    box = patches.FancyBboxPatch(
        (x_min, y_min), w, h,
        boxstyle="round,pad=0.03",
        fc=fc, ec=ec, lw=1.5, zorder=2
    )
    ax.add_patch(box)
    
    # Text
    if subtext:
        ax.text(x, y + 0.09, text, color=text_color, fontsize=10, fontweight='bold', ha='center', va='center', zorder=3)
        ax.text(x, y - 0.11, subtext, color=text_color, fontsize=8, ha='center', va='center', zorder=3)
    else:
        ax.text(x, y, text, color=text_color, fontsize=10, fontweight='bold', ha='center', va='center', zorder=3)

# Draw Arrow helper
def draw_arrow(x_start, y_start, x_end, y_end, color='#64748b', style='->', lw=1.5, ls='-'):
    ax.annotate(
        "", xy=(x_end, y_end), xytext=(x_start, y_start),
        arrowprops=dict(arrowstyle=style, color=color, lw=lw, ls=ls, shrinkA=0, shrinkB=0),
        zorder=1
    )

# Main Flow Boxes
draw_box(7.5, 7.7, 2.6, 0.5, "Borrower Call", fc='white', text_color='#0f172a')
draw_box(7.5, 6.8, 2.8, 0.5, "Deepgram STT", "Speech to Text", fc='#3b82f6', text_color='white')
draw_box(7.5, 5.9, 3.5, 0.55, "Context Engine", "Aggregates 5 systems in 0.3s", fc='#8b5cf6', text_color='white')
draw_box(7.5, 5.0, 3.5, 0.55, "Diagnosis Layer", "Intent detection + Gap analysis", fc='#3b82f6', text_color='white')
draw_box(7.5, 4.0, 2.8, 0.6, "LLM Agent (Groq)", "Reasoning + Tool calls", fc='#22c55e', text_color='white')

# Side Branches (Y = 4.0)
draw_box(4.5, 4.0, 2.2, 0.6, "RAG Engine", "Policy retrieval", fc='#f59e0b', text_color='white')
draw_box(10.5, 4.0, 2.2, 0.6, "Tools", "CRM, Payments, Tickets", fc='#f59e0b', text_color='white')

# Downward flow
draw_box(7.5, 3.0, 3.5, 0.55, "Memory Store", "Commitments + Preferences", fc='#eab308', text_color='#0f172a')
draw_box(7.5, 2.1, 2.8, 0.5, "Text to Speech", "Mac TTS / ElevenLabs", fc='#3b82f6', text_color='white')
draw_box(7.5, 1.2, 2.6, 0.5, "Borrower Hears Answer", fc='white', text_color='#0f172a')

# Flow Arrows
draw_arrow(7.5, 7.45, 7.5, 7.05)   # 1 -> 2
draw_arrow(7.5, 6.55, 7.5, 6.175)  # 2 -> 3
draw_arrow(7.5, 5.625, 7.5, 5.275) # 3 -> 4
draw_arrow(7.5, 4.725, 7.5, 4.3)   # 4 -> 5

# Left Branch Arrows (Agent <-> RAG)
draw_arrow(6.1, 4.12, 5.6, 4.12)    # Agent -> RAG
draw_arrow(5.6, 3.88, 6.1, 3.88)    # RAG -> Agent

# Right Branch Arrows (Agent <-> Tools)
draw_arrow(8.9, 4.12, 9.4, 4.12)    # Agent -> Tools
draw_arrow(9.4, 3.88, 8.9, 3.88)    # Tools -> Agent

# Continue downward
draw_arrow(7.5, 3.7, 7.5, 3.275)    # 5 -> 6
draw_arrow(7.5, 2.725, 7.5, 2.35)   # 6 -> 7
draw_arrow(7.5, 1.85, 7.5, 1.45)    # 7 -> 8

# Dashed aggregation arrow from Connected Systems Panel to Context Engine
draw_arrow(3.05, 5.9, 5.75, 5.9, style='->', ls='--', color='#94a3b8')

# Save exactly 1200x900 pixels
plt.savefig('data/architecture_diagram.png', facecolor='#0f172a', edgecolor='none')
print("✅ Architecture diagram generated and saved to data/architecture_diagram.png")
