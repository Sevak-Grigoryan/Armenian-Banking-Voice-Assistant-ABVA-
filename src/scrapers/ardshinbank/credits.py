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


CATEGORY_TITLES = [
    "Անգրավ",
    "Կանխիկով ապահովված վարկեր",
    "Անշարժ գույքի գրավադրմամբ",
    "Հատուկ պետական ծրագրեր",
    "Ոսկու գրավադրմամբ",
]


def normalize_text(text):
    text = text.replace("`", "")
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def isolate_loans_section(text):

    start = text.find("Սպառողական վարկեր")

    end_candidates = [
        "Ֆինանսական օգնական",
        "© 2026",
        "Մոբայլ բանկինգ",
        "ԻՆՉՈՒ ԱՐԴՇԻՆԲԱՆԿ"
    ]

    end = len(text)

    for marker in end_candidates:
        pos = text.find(marker)
        if pos != -1:
            end = pos
            break

    return text[start:end]


def extract_metadata(content):

    metadata = {
        "currency": None,
        "amount": None,
        "term": None,
        "interest_rate": None,
        "actual_interest_rate": None
    }

    currency = re.search(r"(ՀՀ դրամ|AMD|USD|EUR)", content)
    if currency:
        metadata["currency"] = currency.group(1)

    amount = re.search(r"Առավելագույն գումար\s*մինչև\s*([^\n]+)", content)
    if amount:
        metadata["amount"] = amount.group(1).strip()

    term = re.search(r"Վարկի ժամկետ[:՝]\s*([^\n]+)", content)
    if term:
        metadata["term"] = term.group(1).strip()

    rate = re.search(r"Տոկոսադրույք[:՝]\s*([^\n]+)", content)
    if rate:
        metadata["interest_rate"] = rate.group(1).strip()

    actual_rate = re.search(
        r"Տարեկան փաստացի առավելագույն տոկոսադրույք[:՝]\s*([^\n]+)",
        content
    )

    if actual_rate:
        metadata["actual_interest_rate"] = actual_rate.group(1).strip()

    return metadata


def extract_loans(text):

    records = []

    for category in CATEGORY_TITLES:

        # category record
        records.append({
            "type": "category",
            "title": category,
            "content": category
        })

        pattern = rf"{category}(.+?)(?={'|'.join(CATEGORY_TITLES)}|$)"

        match = re.search(pattern, text, re.S)

        if not match:
            continue

        section = match.group(1)

        blocks = section.split(
            "Վարկերը տրամադրվում են ՀՀ քաղաքացի ֆիզիկական անձանց"
        )

        for block in blocks[1:]:

            loan_text = (
                "Վարկերը տրամադրվում են ՀՀ քաղաքացի ֆիզիկական անձանց"
                + block
            )

            records.append({
                "type": "loan",
                "title": category,
                "content": loan_text.strip()
            })

    return records


def scrape_ardshinbank_credits():

    url = "https://ardshinbank.am/for-you/loans-ardshinbank?lang=hy"

    print("Fetching page...")
    html = fetch_page_with_playwright(url)

    print("Saving raw HTML...")
    save_raw_html(html, data_path("data/raw/ardshinbank/loans.html"))

    print("Extracting text...")
    text = extract_clean_text_from_html(html)

    print("Cleaning text...")
    text = remove_common_noise(text)
    text = normalize_text(text)

    print("Isolating loans section...")
    text = isolate_loans_section(text)

    print("Extracting loans...")
    items = extract_loans(text)

    records = []

    for i, item in enumerate(items, 1):

        metadata = {}

        if item["type"] == "loan":
            metadata = extract_metadata(item["content"])

        record = {
            "id": f"ardshinbank_credits_{i:03d}",
            "bank_name": "Ardshinbank",
            "topic": "credits",
            "subcategory": item["type"],
            "title": item["title"],
            "content": item["content"],
            "metadata": metadata,
            "source_url": url,
            "language": "hy",
            "scraped_at": str(date.today())
        }

        if validate_record(record):
            records.append(record)

    print("Saving JSON...")
    save_json(records, data_path("data/processed/ArdshinBank/ardshinbank_credits.json"))

    print(f"Done ✔ Saved {len(records)} records")


if __name__ == "__main__":
    scrape_ardshinbank_credits()