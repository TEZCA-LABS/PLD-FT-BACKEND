
import unicodedata

def normalize_text(text: str) -> str:
    """
    Remove accents and standardize text.
    """
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    return text.upper().strip()
