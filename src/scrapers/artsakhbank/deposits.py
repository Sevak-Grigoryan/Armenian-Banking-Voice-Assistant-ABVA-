import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapers.common import (
    data_path,
    fetch_page_with_playwright,
    save_raw_html,
    extract_clean_text_from_html,
    save_json
)
from processing.clean_text import remove_common_noise
from processing.validators import validate_record


BASE_URL = "https://www.artsakhbank.am"
LISTING_URL = "https://www.artsakhbank.am/deposit"


ARMENIAN_DEPOSIT_KEYWORDS = [
    "ավանդ",
    "ժամկետային",
    "կուտակային",
    "ժառանգ",
    "պրեմիում",
    "նվազող",
]


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("․", ".")
    text = text.replace("՝", ":")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def contains_armenian(text: str) -> bool:
    return bool(re.search(r"[Ա-Ֆա-ֆև]", text))


def extract_armenian_deposit_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        link_text = a.get_text(" ", strip=True)

        full_url = urljoin(BASE_URL, href)
        full_url_lower = full_url.lower()

        if "/deposit" not in full_url_lower:
            continue

        text_is_hy = contains_armenian(link_text)
        href_has_keyword = any(k in href.lower() for k in ARMENIAN_DEPOSIT_KEYWORDS)
        text_has_keyword = any(k in link_text.lower() for k in ARMENIAN_DEPOSIT_KEYWORDS)

        if text_is_hy or href_has_keyword or text_has_keyword:
            links.append(full_url)

    seen = set()
    unique_links = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    return unique_links


def keep_mostly_armenian_content(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    kept = []
    for line in lines:
        if contains_armenian(line):
            kept.append(line)
        elif re.search(r"\d", line) and len(line) < 150:
            kept.append(line)

    return "\n".join(kept).strip()


def extract_armenian_title_from_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        if contains_armenian(line) and len(line) <= 100:
            return line

    return "Արցախբանկ ավանդ"


def extract_metadata(content: str) -> dict:
    metadata = {
        "արժույթ": None,
        "գումար": None,
        "ժամկետ": None,
        "տոկոսադրույք": None
    }

    currency_match = re.search(
        r"(ՀՀ դրամ|ԱՄՆ դոլար|եվրո|ռուբլի|AMD|USD|EUR|RUB)",
        content,
        flags=re.IGNORECASE
    )
    if currency_match:
        metadata["արժույթ"] = currency_match.group(1)

    amount_patterns = [
        r"(?:նվազագույն գումար|առավելագույն գումար|գումար)\s*[: ]\s*([^\n]+)",
    ]
    for pattern in amount_patterns:
        m = re.search(pattern, content, flags=re.IGNORECASE)
        if m:
            metadata["գումար"] = m.group(1).strip()
            break

    term_patterns = [
        r"(?:ժամկետ)\s*[: ]\s*([^\n]+)",
    ]
    for pattern in term_patterns:
        m = re.search(pattern, content, flags=re.IGNORECASE)
        if m:
            metadata["ժամկետ"] = m.group(1).strip()
            break

    rate_patterns = [
        r"(?:տարեկան տոկոսադրույք|տոկոսադրույք)\s*[: ]\s*([^\n]+)",
    ]
    for pattern in rate_patterns:
        m = re.search(pattern, content, flags=re.IGNORECASE)
        if m:
            metadata["տոկոսադրույք"] = m.group(1).strip()
            break

    return metadata


def scrape_artsakhbank_deposits():
    print("Fetching Artsakhbank deposits listing page...")
    listing_html = fetch_page_with_playwright(LISTING_URL)

    print("Saving raw listing HTML...")
    save_raw_html(listing_html, data_path("data/raw/artsakhbank/deposit_listing.html"))

    print("Extracting Armenian deposit links...")
    deposit_links = extract_armenian_deposit_links(listing_html)

    print(f"Found {len(deposit_links)} possible Armenian deposit links")

    records = []

    for idx, url in enumerate(deposit_links, start=1):
        try:
            print(f"Fetching deposit page {idx}: {url}")
            html = fetch_page_with_playwright(url)

            save_raw_html(html, data_path(f"data/raw/artsakhbank/deposit_{idx:03d}.html"))

            text = extract_clean_text_from_html(html)
            text = remove_common_noise(text)
            text = normalize_text(text)
            text = keep_mostly_armenian_content(text)

            if not text or not contains_armenian(text):
                continue

            title = extract_armenian_title_from_text(text)

            record = {
                "id": f"artsakhbank_deposits_{idx:03d}",
                "bank_name": "Artsakhbank",
                "topic": "deposits",
                "subcategory": "deposit_page",
                "title": title,
                "content": text,
                "metadata": extract_metadata(text),
                "source_url": url,
                "language": "hy",
                "scraped_at": str(date.today())
            }

            if validate_record(record):
                records.append(record)

        except Exception as e:
            print(f"Skipped {url} because of error: {e}")

    print("Saving dataset...")
    save_json(records, data_path("data/processed/ArtsakhBank/artsakhbank_deposits.json"))

    print(f"Done ✔ Saved {len(records)} Artsakhbank deposit records")


if __name__ == "__main__":
    scrape_artsakhbank_deposits()