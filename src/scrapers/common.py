import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def data_path(relative_path: str) -> str:
    """Resolve a data path relative to the project root's data/ directory."""
    return os.path.join(PROJECT_ROOT, relative_path)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
}

def fetch_page(url: str, timeout: int = 20) -> str:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def save_raw_html(html: str, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def extract_clean_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def save_json(data, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_page_with_playwright(
    url: str,
    timeout: int = 60000,
    wait_for_selector: str | None = None,
    extra_wait_ms: int = 3000,
) -> str:
    """
    Fetch a page using a real Chromium browser (handles JS-rendered content).

    Args:
        url:               Target URL.
        timeout:           Navigation timeout in ms (default 60s).
        wait_for_selector: Optional CSS selector — waits until this element
                           appears in the DOM before capturing HTML.
                           Use this for JS-heavy pages where content loads
                           after the initial page load event.
        extra_wait_ms:     Extra pause in ms AFTER the selector appears (or
                           after domcontentloaded if no selector given).
                           Gives React/Vue apps time to finish rendering.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except Exception:
            page.goto(url, wait_until="load", timeout=timeout)

        # If a specific element is expected, wait for it to appear
        if wait_for_selector:
            try:
                page.wait_for_selector(wait_for_selector, timeout=timeout)
            except Exception:
                print(f"  [warn] wait_for_selector {wait_for_selector!r} timed out — continuing anyway")

        # Extra pause so JS frameworks finish rendering
        page.wait_for_timeout(extra_wait_ms)

        html = page.content()
        browser.close()
        return html