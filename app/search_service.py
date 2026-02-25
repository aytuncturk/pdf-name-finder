import pandas as pd
from rapidfuzz import fuzz
from app.utils import normalize_text
from app.pdf_service import extract_names_from_page


FUZZY_THRESHOLD = 82


def read_names_from_excel(path: str):
    df = pd.read_excel(path, header=None)
    return df.iloc[:, 0].dropna().astype(str).tolist()


def search_names_in_pages(names, pages):

    results_exact = {name: [] for name in names}
    results_similar = {name: [] for name in names}

    normalized_names = {
        name: normalize_text(name)
        for name in names
    }

    for page_number, text in pages.items():

        normalized_page = normalize_text(text)
        page_names = extract_names_from_page(text)

        for original_name, normalized_name in normalized_names.items():

            # 1️⃣ Tam eşleşme
            if normalized_name in normalized_page:
                results_exact[original_name].append(page_number)
                continue

            # 2️⃣ Benzer eşleşme
            for candidate in page_names:
                score = fuzz.ratio(normalized_name, candidate)

                if score >= FUZZY_THRESHOLD:
                    results_similar[original_name].append(
                        (page_number, score)
                    )

    return results_exact, results_similar
