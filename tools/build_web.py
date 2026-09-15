"""Assemble the standalone PayLens website from web/src.

    python tools/build_web.py

Writes:
  web/index.html     complete single-file site — double-click to open, no install
  web/artifact.html  same page without the <html>/<head>/<body> shell (for hosted publishing)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "src"
FONT = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">'

css = (SRC / "app.css").read_text()
body = (SRC / "body.html").read_text()
js = (SRC / "engine.js").read_text() + "\n" + (SRC / "ui.js").read_text()

inner = f"<title>PayLens</title>\n{FONT}\n<style>\n{css}</style>\n{body}\n<script>\n{js}</script>\n"
(ROOT / "web" / "artifact.html").write_text(inner)
# Only the standalone site gets a favicon link; the artifact host supplies its own.
ICON = '<link rel="icon" type="image/png" href="favicon.png">'
full = ("<!doctype html>\n<html lang=\"en-AU\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>PayLens</title>\n{ICON}\n{FONT}\n<style>\n{css}</style>\n</head>\n<body>\n{body}\n"
        f"<script>\n{js}</script>\n</body>\n</html>\n")
(ROOT / "web" / "index.html").write_text(full)
print("built", len(full) // 1024, "KB")
