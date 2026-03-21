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


def normalize_text(text: str) -> str:
    text = text.replace("`", "")
    text = text.replace("\xa0", " ")
    text = text.replace("․", ".")
    text = text.replace("՝", ":")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def isolate_deposits_section(text: str) -> str:
    start_candidates = [
        "Ավանդ",
        "Բանկային ավանդ",
        "Կատարե՛ք խնայողություններ, ապահովե՛ք բարձր և կայուն եկամուտներ"
    ]
    end_candidates = [
        "Երեք քայլ ավանդը առցանց (online) ներդնելու համար",
        "Մեր առաջարկը",
        "Ավանդային հաշվիչ",
        "© 2026",
        "Մոբայլ բանկինգ"
    ]

    start_idx = -1
    for marker in start_candidates:
        pos = text.find(marker)
        if pos != -1:
            start_idx = pos
            break

    if start_idx == -1:
        start_idx = 0

    end_idx = len(text)
    for marker in end_candidates:
        pos = text.find(marker, start_idx)
        if pos != -1:
            end_idx = pos
            break

    return text[start_idx:end_idx].strip()


def build_general_content(text: str) -> str:
    start_marker = "Ավանդ"
    end_candidates = [
        "Կարևոր է իմանալ",
        "Հատուկ պայմաններ",
        "Տոկոսների հաշվարկման և վճարման կարգ",
        "Երաշխավորված ավանդի առավելագույն սահմանաչափերը և հաշվարկման կարգը"
    ]

    start_idx = text.find(start_marker)
    if start_idx == -1:
        start_idx = 0

    end_idx = len(text)
    for marker in end_candidates:
        pos = text.find(marker, start_idx)
        if pos != -1:
            end_idx = pos
            break

    return text[start_idx:end_idx].strip()


def extract_general_deposit_metadata(text: str) -> dict:
    metadata = {
        "currencies": [],
        "max_amount_amd": None,
        "max_amount_usd": None,
        "max_amount_eur": None,
        "max_amount_rub": None
    }

    currencies = []

    currency_patterns = [
        ("ՀՀ դրամ", r"(ՀՀ դրամ|AMD)"),
        ("ԱՄՆ դոլար", r"(ԱՄՆ դոլար|USD)"),
        ("Եվրո", r"(եվրո|EUR)"),
        ("Ռուբլի", r"(ռուբլի|RUB)")
    ]

    for label, pattern in currency_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            currencies.append(label)

    metadata["currencies"] = currencies

    if re.search(r"մինչև\s*100\s*մլն\s*ՀՀ դրամ", text, flags=re.IGNORECASE):
        metadata["max_amount_amd"] = "100 մլն ՀՀ դրամ"

    if re.search(r"մինչև\s*200,?000\s*ԱՄՆ դոլար", text, flags=re.IGNORECASE):
        metadata["max_amount_usd"] = "200,000 ԱՄՆ դոլար"

    if re.search(r"մինչև\s*200,?000\s*եվրո", text, flags=re.IGNORECASE):
        metadata["max_amount_eur"] = "200,000 եվրո"

    if re.search(r"մինչև\s*10\s*մլն\s*ռուբլի", text, flags=re.IGNORECASE):
        metadata["max_amount_rub"] = "10 մլն ռուբլի"

    return metadata


def is_term_line(line: str) -> bool:
    return bool(re.match(r"^\d+\s*-\s*\d+\s*օր$", line.strip()))


def extract_rate_rows(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    rows = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if is_term_line(line):
            term = line
            values = []

            j = i + 1
            while j < len(lines) and not is_term_line(lines[j]):
                candidate = lines[j].strip()

                if re.fullmatch(r"-", candidate):
                    values.append(candidate)
                elif re.fullmatch(r"\d+(?:\.\d+)?%\s*\(\d+(?:\.\d+)?%\)", candidate):
                    values.append(candidate)
                else:
                    # stop if we reached non-table narrative
                    if len(values) >= 4:
                        break

                if len(values) >= 4:
                    break

                j += 1

            raw_row = " ".join([term] + values).strip()

            parsed = {
                "term": term,
                "raw_row": raw_row,
                "amd_nominal_rate": None,
                "amd_apy": None,
                "usd_nominal_rate": None,
                "usd_apy": None,
                "eur_nominal_rate": None,
                "eur_apy": None,
                "rub_nominal_rate": None,
                "rub_apy": None
            }

            currency_order = ["amd", "usd", "eur", "rub"]

            for idx, value in enumerate(values[:4]):
                cur = currency_order[idx]

                if value == "-":
                    parsed[f"{cur}_nominal_rate"] = None
                    parsed[f"{cur}_apy"] = None
                else:
                    m = re.match(r"(\d+(?:\.\d+)?)%\s*\((\d+(?:\.\d+)?)%\)", value)
                    if m:
                        parsed[f"{cur}_nominal_rate"] = f"{m.group(1)}%"
                        parsed[f"{cur}_apy"] = f"{m.group(2)}%"

            rows.append(parsed)
            i = j
        else:
            i += 1

    return rows


def scrape_ardshinbank_deposits():
    url = "https://ardshinbank.am/for-you/avand?lang=hy"

    print("Fetching Ardshinbank deposits page...")
    html = fetch_page_with_playwright(url)

    print("Saving raw HTML...")
    save_raw_html(html, data_path("data/raw/ardshinbank/deposits.html"))

    print("Extracting text...")
    text = extract_clean_text_from_html(html)

    print("Cleaning text...")
    text = remove_common_noise(text)
    text = normalize_text(text)

    print("Isolating deposits section...")
    deposits_text = isolate_deposits_section(text)

    records = []

    general_content = build_general_content(deposits_text)

    general_record = {
        "id": "ardshinbank_deposits_001",
        "bank_name": "Ardshinbank",
        "topic": "deposits",
        "subcategory": "deposit_category",
        "title": "Բանկային ավանդ",
        "content": general_content,
        "metadata": extract_general_deposit_metadata(deposits_text),
        "source_url": url,
        "language": "hy",
        "scraped_at": str(date.today())
    }

    if validate_record(general_record):
        records.append(general_record)

    rate_rows = extract_rate_rows(deposits_text)

    for idx, row in enumerate(rate_rows, start=2):
        record = {
            "id": f"ardshinbank_deposits_{idx:03d}",
            "bank_name": "Ardshinbank",
            "topic": "deposits",
            "subcategory": "deposit_term_row",
            "title": f"Ավանդ {row['term']}",
            "content": row["raw_row"],
            "metadata": row,
            "source_url": url,
            "language": "hy",
            "scraped_at": str(date.today())
        }

        if validate_record(record):
            records.append(record)

    print("Saving JSON dataset...")
    save_json(records, data_path("data/processed/ArdshinBank/ardshinbank_deposits.json"))

    print(f"Done ✔ Saved {len(records)} Ardshinbank deposit records")


if __name__ == "__main__":
    scrape_ardshinbank_deposits()