import os
import markdown
from weasyprint import HTML

def main():
    md_path = "system_design.md"
    if not os.path.exists(md_path):
        md_path = os.path.join("docs", "system_design.md")
        if not os.path.exists(md_path):
            raise FileNotFoundError("system_design.md not found in the root directory or docs/ directory.")
    
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    # Convert markdown to html using the markdown library with tables extension
    # We also use fenced_code to handle standard markdown code blocks cleanly
    html_content = markdown.markdown(md_content, extensions=["tables", "fenced_code"])
    
    # Wrap in complete HTML document with specific CSS styling requested by the user:
    # - Font: Georgia for body, monospace for code
    # - Background: white
    # - Max width: 800px, margin auto
    # - Line height: 1.7
    # - H1: color #1e293b, border-bottom 2px solid #3b82f6
    # - H2: color #1e293b, margin-top 2em
    # - H3: color #3b82f6
    # - Tables: full width, border-collapse, alternating row colors (#f8fafc)
    # - Code blocks: background #f1f5f9, padding, border-radius
    # - Page breaks: avoid breaking inside tables and code blocks
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>CredResolve AI Voice Agent — System Design Document</title>
    <style>
        @page {{
            size: A4;
            margin: 20mm;
        }}
        body {{
            font-family: Georgia, serif;
            background-color: white;
            color: #1e293b;
            max-width: 800px;
            margin: auto;
            line-height: 1.7;
            font-size: 11pt;
        }}
        h1 {{
            font-family: Georgia, serif;
            color: #1e293b;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 8px;
            margin-top: 0;
            margin-bottom: 1.5em;
            font-size: 24pt;
        }}
        h2 {{
            font-family: Georgia, serif;
            color: #1e293b;
            margin-top: 2em;
            margin-bottom: 1em;
            font-size: 18pt;
            page-break-after: avoid;
        }}
        h3 {{
            font-family: Georgia, serif;
            color: #3b82f6;
            margin-top: 1.5em;
            margin-bottom: 0.8em;
            font-size: 14pt;
            page-break-after: avoid;
        }}
        p, li, blockquote {{
            margin-bottom: 1em;
        }}
        blockquote {{
            border-left: 4px solid #3b82f6;
            padding-left: 15px;
            color: #475569;
            margin-left: 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.5em 0;
            font-size: 10pt;
            page-break-inside: avoid;
        }}
        th, td {{
            border: 1px solid #cbd5e1;
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background-color: #f1f5f9;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background-color: #f8fafc;
        }}
        code {{
            font-family: monospace;
            font-size: 9.5pt;
        }}
        pre {{
            background-color: #f1f5f9;
            padding: 12px 16px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 1.5em 0;
            page-break-inside: avoid;
        }}
        pre code {{
            background-color: transparent;
            padding: 0;
            border-radius: 0;
        }}
        ul, ol {{
            margin-bottom: 1.5em;
            padding-left: 20px;
        }}
        /* Avoid breaks inside list items, blockquotes, code blocks, and tables */
        tr, li, blockquote, pre {{
            page-break-inside: avoid;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""
    
    # Save as system_design.pdf using weasyprint
    HTML(string=full_html).write_pdf("system_design.pdf")
    print("✅ PDF generated: system_design.pdf")

if __name__ == "__main__":
    main()
