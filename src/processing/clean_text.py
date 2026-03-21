import re


def normalize_whitespace(text: str) -> str:
    """
    Remove excessive spaces and normalize line breaks
    """
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def remove_common_noise(text: str) -> str:
    """
    Remove common website noise like cookie messages
    """

    noisy_phrases = [
        "Cookie",
        "Accept",
        "Close",
        "Մեր կայքը օգտագործում է cookie",
        "Privacy policy"
    ]

    for phrase in noisy_phrases:
        text = text.replace(phrase, "")

    return normalize_whitespace(text)