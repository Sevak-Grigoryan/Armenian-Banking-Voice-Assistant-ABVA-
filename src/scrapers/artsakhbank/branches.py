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


URL = "https://www.artsakhbank.am/map-and-branches"


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("․", ".")
    text = text.replace("՝", ":")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def isolate_branches_section(text: str) -> str:
    start_marker = "Գլխամասային գրասենյակ"
    end_candidates = [
        "Օգտակար հղումներ",
        "Կապ մեզ հետ",
        "«ԱՐՑԱԽԲԱՆԿ» ՓԲԸ ՎԵՐԱՀՍԿՎՈՒՄ Է ՀՀ ԿԵՆՏՐՈՆԱԿԱՆ ԲԱՆԿԻ ԿՈՂՄԻՑ",
        "ISO/IEC",
        "Բոլոր իրավունքները պաշտպանված են"
    ]

    start_idx = text.find(start_marker)
    if start_idx == -1:
        return text

    end_idx = len(text)
    for marker in end_candidates:
        pos = text.find(marker, start_idx)
        if pos != -1:
            end_idx = pos
            break

    return text[start_idx:end_idx].strip()


def is_branch_title(line: str) -> bool:
    line = line.strip()
    if not line:
        return False

    branch_keywords = [
        "Գլխամասային գրասենյակ",
        "մասնաճյուղ"
    ]

    if any(k in line for k in branch_keywords):
        return True

    return False


def split_branch_blocks(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    blocks = []
    current = []

    def flush():
        nonlocal current, blocks
        if current:
            block = "\n".join(current).strip()
            blocks.append(block)
            current = []

    for line in lines:
        if is_branch_title(line) and current:
            flush()
        current.append(line)

    flush()

    result = []
    for block in blocks:
        block_lines = [x.strip() for x in block.splitlines() if x.strip()]
        if not block_lines:
            continue

        # keep only blocks that really look like branch records
        has_phone = any("+374" in x for x in block_lines)
        has_email = any("@" in x for x in block_lines)
        has_address = any("ՀՀ," in x or "Երևան" in x or "Կոտայք" in x for x in block_lines)

        if has_phone and has_address:
            result.append({
                "title": block_lines[0],
                "content": "\n".join(block_lines)
            })

    return result


def extract_branch_metadata(content: str) -> dict:
    metadata = {
        "հասցե": None,
        "հեռախոս": None,
        "էլ_հասցե": None,
        "քաղաք": None,
        "աշխատաժամեր": None
    }

    lines = [line.strip() for line in content.splitlines() if line.strip()]

    # address
    for line in lines[1:4]:
        if "ՀՀ," in line or "Երևան" in line or "Կոտայք" in line:
            metadata["հասցե"] = normalize_text(line)
            break

    # phone - first number
    phone_match = re.search(r"\+374\s*\d{2}\s*\d{6}(?:,\s*\d{6})*", content)
    if phone_match:
        metadata["հեռախոս"] = normalize_text(phone_match.group(0))

    # email
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", content)
    if email_match:
        metadata["էլ_հասցե"] = email_match.group(0).strip()

    # hours
    hours_patterns = [
        r"(Երկուշաբթի\s*-\s*Ուրբաթ[`:]?\s*[0-9: ]+\-\s*[0-9: ]+)",
        r"(Երկուշաբթի\s*-\s*Կիրակի[:` ]\s*[0-9: ]+\-\s*[0-9: ]+)",
        r"(Շաբաթ[: ]\s*[0-9: ]+\-\s*[0-9: ]+)"
    ]

    hours_found = []
    for pattern in hours_patterns:
        for m in re.finditer(pattern, content):
            hours_found.append(normalize_text(m.group(1)))

    if hours_found:
        metadata["աշխատաժամեր"] = " | ".join(hours_found)

    # city
    joined = f"{content}\n{metadata['հասցե'] or ''}"
    if "Երևան" in joined:
        metadata["քաղաք"] = "Երևան"
    elif "Կոտայք" in joined:
        metadata["քաղաք"] = "Կոտայք"

    return metadata


def clean_content(content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    cleaned = []

    for line in lines:
        if line in {"Թարմացվել է 28.11.2025 09:22"}:
            continue
        cleaned.append(line)

    return "\n".join(cleaned).strip()


def scrape_artsakhbank_branches():
    print("Fetching Artsakhbank branches page...")
    html = fetch_page_with_playwright(URL)

    print("Saving raw HTML...")
    save_raw_html(html, data_path("data/raw/artsakhbank/branches.html"))

    print("Extracting text...")
    text = extract_clean_text_from_html(html)

    print("Cleaning text...")
    text = remove_common_noise(text)
    text = normalize_text(text)

    print("Isolating real branches section...")
    text = isolate_branches_section(text)

    print("Splitting real branch blocks...")
    branch_blocks = split_branch_blocks(text)

    records = []

    for idx, branch in enumerate(branch_blocks, start=1):
        cleaned_content = clean_content(branch["content"])
        metadata = extract_branch_metadata(cleaned_content)

        record = {
            "id": f"artsakhbank_branches_{idx:03d}",
            "bank_name": "Artsakhbank",
            "topic": "branches",
            "subcategory": "branch",
            "title": branch["title"],
            "content": cleaned_content,
            "metadata": metadata,
            "source_url": URL,
            "language": "hy",
            "scraped_at": str(date.today())
        }

        if validate_record(record):
            records.append(record)

    print("Saving dataset...")
    save_json(records, data_path("data/processed/ArtsakhBank/artsakhbank_branches.json"))

    print(f"Done ✔ Saved {len(records)} Artsakhbank branch records")


if __name__ == "__main__":
    scrape_artsakhbank_branches()