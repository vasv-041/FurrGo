"""
app/services/rag/text_cleaner.py
"""
import re

def clean_text(text: str) -> str:
    """Basic text cleaning to remove extra whitespace and normalize."""
    if not text:
        return ""
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n+', '\n', text)
    # Replace multiple spaces with a single space
    text = re.sub(r' +', ' ', text)
    return text.strip()
