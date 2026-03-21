import re
from datetime import date

from scrapers.common import (
    data_path,
    fetch_page_with_playwright,
    save_raw_html,
    extract_clean_text_from_html,
    save_json
)
from processing.clean_text import remove_common_noise
from processing.validators import validate_record


def isolate_main_loans_section(text: str) -> str:
    start_marker = "Հիփոթեքային վարկ\nՏունն այնտեղ է, որտեղ Ձեր ընտանիքն է:"
    end_marker = "Մելլաթ Բանկը վերահսկվում է ՀՀ կենտրոնական բանկի կողմից"

    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)

    if start_idx == -1:
        start_idx = 0

    if end_idx == -1:
        end_idx = len(text)

    return text[start_idx:end_idx].strip()


def split_mellat_credit_products(text: str) -> list[dict]:
    product_titles = [
        "Հիփոթեքային վարկ",
        "Վերանորոգման վարկ",
        "Ուսանողական վարկ",
        "Ավտովարկ",
        "Արագ սպառողական վարկ",
        "\"Արտոնյալ\" վարկ",
        "Անշարժ գույքի գրավադրմամբ սպառողական վարկ (եկամտի հիմնավորմամբ)",
        "Անշարժ գույքի գրավադրմամբ սպառողական վարկ (առանց եկամտի հիմնավորման)"
    ]

    escaped_titles = [re.escape(title) for title in product_titles]
    pattern = r"(?=^(" + "|".join(escaped_titles) + r")\n)"

    parts = re.split(pattern, text, flags=re.MULTILINE)

    records = []
    i = 1

    while i < len(parts):
        title = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""

        full_content = content.strip()

        if full_content.startswith(title):
            full_content = full_content[len(title):].strip()

        full_content = f"{title}\n{full_content}".strip()

        if full_content:
            records.append({
                "title": title,
                "content": full_content
            })

        i += 2

    return records


def extract_metadata_from_credit_content(content: str) -> dict:
    metadata = {
        "currency": None,
        "max_amount": None,
        "term": None,
        "interest_rate": None
    }

    currency_match = re.search(r"\b(AMD|USD|EUR)\b", content)
    if currency_match:
        metadata["currency"] = currency_match.group(1)

    max_amount_match = re.search(
        r"ՎԱՐԿԻ ԳՈՒՄԱՐԸ ՄԻՆՉԵՎ\s*([\d\.,]+)",
        content
    )
    if max_amount_match:
        metadata["max_amount"] = max_amount_match.group(1).strip()

    term_match = re.search(
        r"ԺԱՄԿԵՏ\s*([\d\-]+\s*Ամիս)",
        content
    )
    if term_match:
        metadata["term"] = term_match.group(1).strip()

    rate_match = re.search(
        r"ՏՈԿՈՍԱԴՐՈՒՅՔ ?%\s*([\d\-\.]+%)",
        content
    )
    if rate_match:
        metadata["interest_rate"] = rate_match.group(1).strip()

    return metadata


def scrape_mellat_credits():
    url = "https://mellatbank.am/hy/loans_individual"

    print("Fetching page with Playwright...")
    html = fetch_page_with_playwright(url)

    print("Saving raw HTML...")
    save_raw_html(html, data_path("data/raw/mellatbank/loans_individual.html"))

    print("Extracting text...")
    text = extract_clean_text_from_html(html)

    print("Cleaning text...")
    text = remove_common_noise(text)

    print("Isolating loans section...")
    text = isolate_main_loans_section(text)

    print("Splitting product blocks...")
    product_blocks = split_mellat_credit_products(text)

    records = []

    for idx, product in enumerate(product_blocks, start=1):
        metadata = extract_metadata_from_credit_content(product["content"])

        record = {
            "id": f"mellatbank_credits_{idx:03d}",
            "bank_name": "Mellat Bank",
            "topic": "credits",
            "subcategory": "general",
            "title": product["title"],
            "content": product["content"],
            "metadata": metadata,
            "source_url": url,
            "language": "hy",
            "scraped_at": str(date.today())
        }

        if validate_record(record):
            records.append(record)

    print("Saving JSON dataset...")
    save_json(records, data_path("data/processed/MellatBank/mellatbank_credits.json"))

    print(f"Done ✔ Saved {len(records)} records")


if __name__ == "__main__":
    scrape_mellat_credits()