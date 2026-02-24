import pandas as pd
from app.utils import normalize_text

def read_names_from_excel(path: str):
    df = pd.read_excel(path, header=None)  # HEADER YOK!
    return df.iloc[:, 0].dropna().astype(str).tolist()

def search_names_in_pages(names, pages):
    results = {name: [] for name in names}

    for page_number, text in pages.items():
        normalized_page = normalize_text(text)
        page_tokens = set(normalized_page.split())

        for name in names:
            normalized_name = normalize_text(name)
            name_tokens = set(normalized_name.split())

            if name_tokens.issubset(page_tokens):
                results[name].append(page_number)

    return results