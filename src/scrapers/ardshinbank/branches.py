import re
from datetime import date

from bs4 import BeautifulSoup

from scrapers.common import (
    data_path,
    fetch_page_with_playwright,
    save_raw_html,
    save_json,
)
from processing.validators import validate_record


BRANCHES_URL = "https://ardshinbank.am/Information/branch-atm"

# Tab labels on the page — used as subcategory
_TAB_LABELS = {
    "ՄԱՍՆԱՃՅՈՒՂԵՐ":                                    "մասնաճյուղ",
    "ՇԱԲԱԹ ՕՐԵՐԻՆ ԱՇԽԱՏՈՂ ՄԱՍՆԱՃՅՈՒՂԵՐ":              "մասնաճյուղ_շաբաթ",
    "ՀԱՏՈՒԿ ԳՐԱՖԻԿՈՎ ԱՇԽԱՏՈՂ ՄԱՍՆԱՃՅՈՒՂԵՐ":           "մասնաճյուղ_հատուկ",
    "ԲԱՆԿՈՄԱՏՆԵՐ":                                     "բանկոմատ",
    "ԱՎՏՈՄԱՏ ՓՈԽԱՐԿՄԱՆ ԵՎ CASH IN ԲԱՆԿՈՄԱՏՆԵՐ":       "բանկոմատ_cash_in",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ")
    text = text.replace("․", ".").replace("՝", ":")
    # Remove emoji (wheelchair symbol etc.)
    text = re.sub(r"[^\u0000-\u05FF\u2000-\u206F\u2E00-\u2E7F\u0020-\u007E]+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sel_text(el, selector: str) -> str:
    found = el.select_one(selector)
    return normalize(found.get_text(" ", strip=True)) if found else ""

def extract_branches(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")

    cards = soup.select("div.quicktabs-views-group")
    print(f"  [debug] found {len(cards)} branch cards")

    if not cards:
        # Fallback debug — show what IS on the page
        print("  [debug] quicktabs-views-group not found — dumping all div classes:")
        for div in soup.find_all("div", class_=True)[:30]:
            print(f"    {div.get('class')}")
        return []

    branches = []
    for card in cards:
        name    = sel_text(card, "div.views-field-title")
        address = sel_text(card, "div.views-field-field-address")
        phone   = sel_text(card, "div.views-field-field-telephone")
        hours   = sel_text(card, "div.views-field-field-working-hours")
        btype   = sel_text(card, "div.views-field-field-type")

        if not name:
            continue

        branches.append({
            "անուն":            name,
            "հասցե":            address,
            "հեռախոս":          phone,
            "աշխատանքային_ժամ": hours,
            "տեսակ":            btype,
        })

    return branches



def build_record(idx: int, branch: dict) -> dict:
    name    = branch["անուն"]
    address = branch["հասցե"]
    phone   = branch["հեռախոս"]
    hours   = branch["աշխատանքային_ժամ"]
    btype   = branch["տեսակ"]

    # Derive subcategory from type field value
    subcategory = "մասնաճյուղ"
    for label, slug in _TAB_LABELS.items():
        if label.lower() in btype.lower():
            subcategory = slug
            break

    content_lines = []
    if name:    content_lines.append(f"Անուն: {name}")
    if btype:   content_lines.append(f"Տեսակ: {btype}")
    if address: content_lines.append(f"Հասցե: {address}")
    if phone:   content_lines.append(f"Հեռախոս: {phone}")
    if hours:   content_lines.append(f"Աշխատանքային ժամ: {hours}")

    return {
        "id":          f"ardshinbank_branches_{idx:03d}",
        "bank_name":   "Արդշինբանկ",
        "topic":       "branches",
        "subcategory": subcategory,
        "title":       name,
        "content":     "\n".join(content_lines),
        "metadata": {
            "հասցե":            address,
            "հեռախոս":          phone,
            "աշխատանքային_ժամ": hours,
            "տեսակ":            btype,
        },
        "source_url":  BRANCHES_URL,
        "language":    "hy",
        "scraped_at":  str(date.today()),
    }

def scrape_ardshinbank_branches():
    print("Fetching Ardshinbank branch/ATM page...")
    html = fetch_page_with_playwright(BRANCHES_URL)

    print("Saving raw HTML...")
    save_raw_html(html, data_path("data/raw/ardshinbank/branches.html"))

    print("Extracting branch records...")
    branches = extract_branches(html)

    if not branches:
        print("  WARNING: 0 branches found — check data/raw/ardshinbank/branches.html")
        return

    records = []
    for idx, branch in enumerate(branches, start=1):
        record = build_record(idx, branch)
        if validate_record(record):
            records.append(record)

    print("Saving dataset...")
    save_json(records, data_path("data/processed/ArdshinBank/ardshinbank_branches.json"))
    print(f"Done ✔  Saved {len(records)} Ardshinbank branch records")


if __name__ == "__main__":
    scrape_ardshinbank_branches()