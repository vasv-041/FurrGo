"""
app/services/rag/chunker.py
"""
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    Splits text into chunks of `chunk_size` characters with an `overlap`.
    A more advanced chunker would use tokens, but character chunking is robust for plain text.
    """
    if not text:
        return []
        
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = min(start + chunk_size, text_length)
        
        # Try to find a good boundary (like a newline or space) if we are not at the end
        if end < text_length:
            # Look back up to 50 chars for a newline
            newline_pos = text.rfind('\n', start, end)
            if newline_pos != -1 and (end - newline_pos) < 100:
                end = newline_pos + 1
            else:
                # Look back for a space
                space_pos = text.rfind(' ', start, end)
                if space_pos != -1 and (end - space_pos) < 50:
                    end = space_pos + 1
                    
        chunks.append(text[start:end].strip())
        
        # Advance start, accounting for overlap
        start = end - overlap
        if start >= end:
            start = end # prevent infinite loop if overlap is somehow broken
            
    return chunks
