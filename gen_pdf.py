import markdown
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

# Read the markdown content
with open("output/浙江觉纤_投资概要.md", "r", encoding="utf-8") as f:
    md_content = f.read()

# Convert markdown to HTML
html_content = markdown.markdown(md_content, extensions=["tables", "toc", "fenced_code"])

# Add CSS for styling
css = CSS(
    string="""
@page { size: A4; margin: 2cm; @bottom-center { content: counter(page); } }
body { font-family: "Microsoft YaHei", "SimSun", sans-serif; font-size: 11pt; line-height: 1.6; color: #222; }
h1 { color: #1a3c5e; border-bottom: 2px solid #1a3c5e; padding-bottom: 6px; font-size: 22pt; margin-top: 30px; }
h2 { color: #2c5f8a; border-bottom: 1px solid #ccc; padding-bottom: 4px; font-size: 16pt; margin-top: 24px; }
h3 { color: #3a7ab5; font-size: 13pt; margin-top: 18px; }
h4 { color: #4a8fc7; font-size: 11.5pt; margin-top: 14px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 9.5pt; page-break-inside: avoid; }
th { background: #1a3c5e; color: white; padding: 6px 8px; text-align: left; font-weight: 600; }
td { border: 1px solid #ddd; padding: 5px 8px; }
tr:nth-child(even) td { background: #f7f9fc; }
code { background: #f0f4f8; padding: 2px 4px; border-radius: 3px; font-family: "Consolas", monospace; font-size: 9pt; }
pre { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 5px; overflow-x: auto; font-size: 8.5pt; }
pre code { background: none; padding: 0; color: inherit; }
blockquote { border-left: 3px solid #1a3c5e; padding-left: 12px; margin: 12px 0; color: #555; font-style: italic; }
hr { border: none; border-top: 1px solid #ccc; margin: 20px 0; }
ul, ol { margin: 8px 0 8px 24px; }
li { margin: 4px 0; }
strong { color: #1a3c5e; }
"""
)

font_config = FontConfiguration()
HTML(
    string=f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>浙江觉纤 — 投资概要</title>
</head>
<body>
{html_content}
</body>
</html>
"""
).write_pdf("output/浙江觉纤_投资概要.pdf", stylesheets=[css], font_config=font_config)
print("PDF generated successfully")
