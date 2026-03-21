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
LISTING_URL = "https://www.artsakhbank.am/loans"


ARMENIAN_LOAN_KEYWORDS = [
    "վարկ",
    "հիփոթեք",
    "ավտո",
    "սպառողական",
    "ապառիկ",
    "գյուղատնտես",
    "ուսանողական",
    "ոսկու",
    "էքսպրես",
]

_NAV_END_MARKER = "Ապահովագրություն"


_SLIDER_ONLY_ARTIFACTS = {
    "Վարկերի ֆիլտր",           
    "Համեմատել",               
    "Ջջնջել",                  
    "Բոլորը",                   
    "Հիմնական",                
    "Սակագներ և պայմաններ",     
    "Օգտակար տեղեկատվություն",  
}

_FOOTER_CUTOFF_PREFIXES = (
    "Թարմացվել է", 
)

def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ")
    text = text.replace("․", ".")   # Armenian full stop → Latin full stop
    text = text.replace("՝", ":")   # Armenian modifier letter → colon
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def contains_armenian(text: str) -> bool:
    return bool(re.search(r"[Ա-Ֆա-ֆև]", text))

def extract_armenian_loan_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")

    all_anchors = soup.find_all("a", href=True)
    print(f"  [debug] total <a href> tags in HTML: {len(all_anchors)}")
    if len(all_anchors) == 0:
        print("  [debug] WARNING: no anchors found — HTML may be empty or not fully rendered.")
        print(f"  [debug] HTML length: {len(html)} chars")
        print(f"  [debug] HTML snippet: {html[:500]!r}")
        return []

    loans_anchors = [a for a in all_anchors if "/loans" in urljoin(BASE_URL, a["href"]).lower()]
    print(f"  [debug] <a> tags containing '/loans': {len(loans_anchors)}")
    for a in loans_anchors[:5]:
        print(f"    href={a['href']!r}  text={a.get_text(' ', strip=True)[:60]!r}")

    links = []
    for a in all_anchors:
        href = a["href"].strip()
        link_text = a.get_text(" ", strip=True)

        full_url = urljoin(BASE_URL, href)
        full_url_lower = full_url.lower()

        if "/loans" not in full_url_lower:
            continue

        text_is_hy = contains_armenian(link_text)
        href_has_loan_keyword = any(k in href.lower() for k in ARMENIAN_LOAN_KEYWORDS)
        text_has_loan_keyword = any(k in link_text.lower() for k in ARMENIAN_LOAN_KEYWORDS)

        if text_is_hy or href_has_loan_keyword or text_has_loan_keyword or "/loans" in href.lower():
            links.append(full_url)

    seen = set()
    unique_links = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    return unique_links


def strip_page_boilerplate(text: str) -> str:

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    content_start = 0
    for i, line in enumerate(lines):
        if line == _NAV_END_MARKER:
            content_start = i + 1
            break
    lines = lines[content_start:]

    footer_start = len(lines)
    for i, line in enumerate(lines):
        if line.startswith(_FOOTER_CUTOFF_PREFIXES):
            footer_start = i
            break
    lines = lines[:footer_start]

    cleaned = []
    for line in lines:
        if line in _SLIDER_ONLY_ARTIFACTS:
            continue
        if re.fullmatch(r"\d+", line):   
            continue
        cleaned.append(line)

    return "\n".join(cleaned)



_GENERIC_PAGE_LABELS = {
    "Վարկեր", "Գումար", "Արժույթ", "Վարկի ժամկետ",
    "Հիփոթեքային վարկեր", "Ավտովարկեր", "Սպառողական վարկեր",
    "Ապառիկ", "Վարկային գծեր քարտերով", "Գյուղատնտեսական վարկեր",
    # Slider max-value label shown on listing pages — not a real title
    "25 տարի",
}

_URL_SLUG_TO_TITLE = {
    "mortgage-loans":   "Հիփոթեքային վարկեր",
    "car-loans":        "Ավտովարկեր",
    "consumer-loans":   "Սպառողական վարկեր",
    "installment":      "Ապառիկ վարկավորում",
    "card-credit-lines":"Վարկային գծեր քարտերով",
    "agricultural":     "Գյուղատնտեսական վարկեր",
    "compare":          "Վարկերի համեմատություն",
}


def extract_armenian_title_from_text(text: str, source_url: str = "") -> str:

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    for line in lines:
        # Skip known generic page-level labels
        if line in _GENERIC_PAGE_LABELS:
            continue
        # Skip pure numbers (slider artifacts that may have survived)
        if re.fullmatch(r"[\d\s%,.–-]+", line):
            continue
        # Must contain Armenian and be a reasonable title length
        if contains_armenian(line) and 4 <= len(line) <= 120:
            return line

    # Fallback: derive from the URL slug
    if source_url:
        for slug, label in _URL_SLUG_TO_TITLE.items():
            if slug in source_url:
                return label

    return "Արցախբանկ վարկ"


def extract_metadata(content: str) -> dict:

    metadata = {
        "արժույթ": None,
        "գումար": None,
        "ժամկետ": None,
        "տոկոսադրույք": None,
    }

    lines = content.splitlines()

    def next_short_value(idx: int, max_len: int = 80) -> str | None:
        for j in range(idx + 1, min(idx + 4, len(lines))):
            val = lines[j].strip()
            if val and len(val) <= max_len:
                return val
        return None

    for i, line in enumerate(lines):
        s = line.strip()

        if s == "Տարեկան անվանական տոկոսադրույք" and not metadata["տոկոսադրույք"]:
            val = next_short_value(i)
            if val:
                metadata["տոկոսադրույք"] = val

        if s in ("Վարկի ժամկետ", "Ժամկետ") and not metadata["ժամկետ"]:
            val = next_short_value(i)
            if val and not val.startswith("«"):
                metadata["ժամկետ"] = val

        if s in ("Վարկի արժույթ", "Արժույթ") and not metadata["արժույթ"]:
            val = next_short_value(i, max_len=30)
            if val:
                metadata["արժույթ"] = val

        if s == "Վարկի գումար" and not metadata["գումար"]:
            val = next_short_value(i)
            if val:
                metadata["գումար"] = val

    if not metadata["արժույթ"]:
        m = re.search(
            r"(ՀՀ դրամ|ԱՄՆ դոլար|եվրո|ռուբլի|AMD|USD|EUR|RUB)",
            content,
            flags=re.IGNORECASE,
        )
        if m:
            metadata["արժույթ"] = m.group(1)

    if not metadata["տոկոսադրույք"]:
        m = re.search(
            r"տոկոսադրույք\s*[:\n]\s*([^\n]{1,40})",
            content,
            flags=re.IGNORECASE,
        )
        if m:
            metadata["տոկոսադրույք"] = m.group(1).strip()

    return metadata



def scrape_artsakhbank_credits():
    print("Fetching Artsakhbank loans listing page...")
    listing_html = fetch_page_with_playwright(LISTING_URL)

    print("Saving raw listing HTML...")
    save_raw_html(listing_html, data_path("data/raw/artsakhbank/loans_listing.html"))

    print(f"  [debug] listing HTML length: {len(listing_html)} chars")
    if len(listing_html) < 500:
        print(f"  [debug] WARNING: listing HTML is suspiciously short!")
        print(f"  [debug] content: {listing_html!r}")

    print("Extracting Armenian loan links...")
    loan_links = extract_armenian_loan_links(listing_html)
    print(f"Found {len(loan_links)} possible Armenian loan links")

    records = []
    seen_urls: set[str] = set()

    for idx, url in enumerate(loan_links, start=1):
        if url in seen_urls:
            print(f"  Skipping duplicate URL: {url}")
            continue
        seen_urls.add(url)

        try:
            print(f"Fetching loan page {idx}: {url}")
            html = fetch_page_with_playwright(url)
            save_raw_html(html, data_path(f"data/raw/artsakhbank/loan_{idx:03d}.html"))

            text = extract_clean_text_from_html(html)
            text = remove_common_noise(text)
            text = normalize_text(text)
            text = strip_page_boilerplate(text)

            if not text or not contains_armenian(text):
                print(f"  Skipping {url} — no Armenian content after cleaning")
                continue

            title = extract_armenian_title_from_text(text, source_url=url)

            record = {
                "id": f"artsakhbank_credits_{idx:03d}",
                "bank_name": "Artsakhbank",
                "topic": "credits",
                "subcategory": "loan_page",
                "title": title,
                "content": text,
                "metadata": extract_metadata(text),
                "source_url": url,
                "language": "hy",
                "scraped_at": str(date.today()),
            }

            if validate_record(record):
                records.append(record)

        except Exception as e:
            print(f"  Skipped {url} because of error: {e}")

    print("Saving dataset...")
    save_json(records, data_path("data/processed/ArtsakhBank/artsakhbank_credits.json"))
    print(f"Done ✔  Saved {len(records)} Artsakhbank credit records")


if __name__ == "__main__":
    scrape_artsakhbank_credits()