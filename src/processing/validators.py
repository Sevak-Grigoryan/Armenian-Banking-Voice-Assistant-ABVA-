VALID_TOPICS = {"credits", "deposits", "branches"}


def validate_record(record: dict) -> bool:
    """
    Validate that the scraped record contains required fields
    """

    required_fields = [
        "id",
        "bank_name",
        "topic",
        "title",
        "content",
        "source_url",
        "language",
        "scraped_at"
    ]

    for field in required_fields:
        if field not in record:
            return False

        if record[field] is None or record[field] == "":
            return False

    if record["topic"] not in VALID_TOPICS:
        return False

    return True