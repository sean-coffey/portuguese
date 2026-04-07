import pathlib

BAD_CHARS = ["“", "”", "‘", "’"]

for path in pathlib.Path("app").rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    for ch in BAD_CHARS:
        if ch in text:
            print(f"{path} contains {repr(ch)}")