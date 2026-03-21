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


def isolate_contact_section(text: str) -> str:
    start_candidates = [
        "Կապ մեզ հետ",
        "Բանկի հասցեն",
        "Հասցե"
    ]
    end_candidates = [
        "© Բոլոր իրավունքները պաշտպանված են",
        "English version"
    ]

    start_idx = -1
    for marker in start_candidates:
        pos = text.find(marker)
        if pos != -1:
            start_idx = pos
            break

    end_idx = len(text)
    for marker in end_candidates:
        pos = text.find(marker)
        if pos != -1:
            end_idx = pos
            break

    if start_idx == -1:
        start_idx = 0

    return text[start_idx:end_idx].strip()


def extract_branch_metadata(content: str) -> dict:
    metadata = {
        "address": None,
        "phone": None,
        "email": None,
        "website": None,
        "city": None,
        "hours": None
    }

    phone_match = re.search(r"(\(\d{3}\)\s*\d{2}\s*\d{2}\s*\d{2,}|\+?\d[\d\s\-\(\)]{7,})", content)
    if phone_match:
        metadata["phone"] = phone_match.group(1).strip()

    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", content)
    if email_match:
        metadata["email"] = email_match.group(0).strip()

    website_match = re.search(r"(www\.[\w\.-]+\.\w+)", content)
    if website_match:
        metadata["website"] = website_match.group(1).strip()

    address_patterns = [
        r"Բանկի հասցեն\s*(.+)",
        r"Հասցե\s*[`\:]*\s*(.+)"
    ]

    for pattern in address_patterns:
        address_match = re.search(pattern, content)
        if address_match:
            metadata["address"] = address_match.group(1).strip(" ,")
            break

    if metadata["address"] and "Երևան" in metadata["address"]:
        metadata["city"] = "Երևան"

    return metadata


def scrape_mellat_branches():
    url = "https://mellatbank.am/hy/About%20Us"

    print("Fetching branches/contact page with Playwright...")
    html = fetch_page_with_playwright(url)

    print("Saving raw HTML...")
    save_raw_html(html, data_path("data/raw/mellatbank/about_us.html"))

    print("Extracting text...")
    text = extract_clean_text_from_html(html)

    print("Cleaning text...")
    text = remove_common_noise(text)

    print("Isolating contact section...")
    text = isolate_contact_section(text)

    metadata = extract_branch_metadata(text)

    record = {
        "id": "mellatbank_branches_001",
        "bank_name": "Mellat Bank",
        "topic": "branches",
        "subcategory": "contact",
        "title": "Mellat Bank Contact / Branch Info",
        "content": text,
        "metadata": metadata,
        "source_url": url,
        "language": "hy",
        "scraped_at": str(date.today())
    }

    if not validate_record(record):
        raise ValueError("Invalid branches record generated")

    print("Saving JSON dataset...")
    save_json([record], data_path("data/processed/MellatBank/mellatbank_branches.json"))

    print("Done ✔ Saved 1 branches record")


if __name__ == "__main__":
    scrape_mellat_branches()