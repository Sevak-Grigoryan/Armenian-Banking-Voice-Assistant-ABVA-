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


def isolate_main_deposits_section(text: str) -> str:
    start_marker = "Մելլաթ ավանդներ"
    end_marker = "Մելլաթ Բանկը վերահսկվում է ՀՀ կենտրոնական բանկի կողմից"

    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)

    if start_idx == -1:
        start_idx = 0
    if end_idx == -1:
        end_idx = len(text)

    return text[start_idx:end_idx].strip()


def extract_metadata_from_deposit_content(content: str) -> dict:
    metadata = {
        "currency": None,
        "interest_rate": None,
        "term": None,
        "min_amount": None
    }

    currency_match = re.search(r"\b(AMD|USD|EUR)\b", content)
    if currency_match:
        metadata["currency"] = currency_match.group(1)

    rate_match = re.search(r"(\d+(?:[\.,]\d+)?\s*-\s*\d+(?:[\.,]\d+)?%|\d+(?:[\.,]\d+)?%)", content)
    if rate_match:
        metadata["interest_rate"] = rate_match.group(1).replace(" ", "")

    term_match = re.search(r"(\d+\s*-\s*\d+\s*(?:օր|Օր|ամիս|Ամիս)|\d+\s*(?:օր|Օր|ամիս|Ամիս))", content)
    if term_match:
        metadata["term"] = term_match.group(1).strip()

    min_amount_match = re.search(r"(?:ՆՎԱԶԱԳՈՒՅՆ ԳՈՒՄԱՐ|ՍԿԶԲՆԱԿԱՆ ԳՈՒՄԱՐ)\s*([\d\.,]+)", content)
    if min_amount_match:
        metadata["min_amount"] = min_amount_match.group(1).strip()

    return metadata


def scrape_mellat_deposits():
    url = "https://mellatbank.am/hy/Deposits"

    print("Fetching deposits page with Playwright...")
    html = fetch_page_with_playwright(url)

    print("Saving raw HTML...")
    save_raw_html(html, data_path("data/raw/mellatbank/deposits.html"))

    print("Extracting text...")
    text = extract_clean_text_from_html(html)

    print("Cleaning text...")
    text = remove_common_noise(text)

    print("Isolating deposits section...")
    text = isolate_main_deposits_section(text)

    record = {
        "id": "mellatbank_deposits_001",
        "bank_name": "Mellat Bank",
        "topic": "deposits",
        "subcategory": "general",
        "title": "Մելլաթ ավանդներ",
        "content": text,
        "metadata": extract_metadata_from_deposit_content(text),
        "source_url": url,
        "language": "hy",
        "scraped_at": str(date.today())
    }

    if not validate_record(record):
        raise ValueError("Invalid deposit record generated")

    print("Saving JSON dataset...")
    save_json([record], data_path("data/processed/MellatBank/mellatbank_deposits.json"))

    print("Done ✔ Saved 1 deposits record")


if __name__ == "__main__":
    scrape_mellat_deposits()