import re
import unicodedata

def normalize_text(text: str) -> str:
    if not text:
        return ""

    # Unicode normalize önce
    text = unicodedata.normalize("NFKD", text)

    # ASCII'ye zorla (aksanları at)
    text = text.encode("ascii", "ignore").decode("ascii")

    text = text.lower()
    text = re.sub(r"\s+", " ", text)

    return text.strip()