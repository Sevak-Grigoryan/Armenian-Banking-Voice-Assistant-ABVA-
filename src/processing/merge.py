import json
import os


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "processed")

BANKS = {
    "ArdshinBank": [
        "ArdshinBank/ardshinbank_branches.json",
        "ArdshinBank/ardshinbank_credits.json",
        "ArdshinBank/ardshinbank_deposits.json",
    ],
    "ArtsakhBank": [
        "ArtsakhBank/artsakhbank_branches.json",
        "ArtsakhBank/artsakhbank_credits.json",
        "ArtsakhBank/artsakhbank_deposits.json",
    ],
    "MellatBank": [
        "MellatBank/mellatbank_branches.json",
        "MellatBank/mellatbank_credits.json",
        "MellatBank/mellatbank_deposits.json",
    ],
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_bank(bank_name, source_files):
    all_records = []
    for rel_path in source_files:
        full_path = os.path.join(DATA_DIR, rel_path)
        if os.path.exists(full_path):
            records = load_json(full_path)
            all_records.extend(records)
            print(f"  Loaded {len(records)} records from {rel_path}")
        else:
            print(f"  WARNING: {rel_path} not found, skipping")

    output_path = os.path.join(DATA_DIR, "full_data", f"{bank_name}.json")
    save_json(all_records, output_path)
    print(f"  Saved {len(all_records)} total records to full_data/{bank_name}.json")


def merge_all():
    for bank_name, source_files in BANKS.items():
        print(f"\nMerging {bank_name}...")
        merge_bank(bank_name, source_files)
    print("\nAll banks merged successfully.")


if __name__ == "__main__":
    merge_all()
