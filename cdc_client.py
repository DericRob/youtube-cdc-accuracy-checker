"""
CDC Content Syndication API client.
Docs: https://tools.cdc.gov/api/docs/info.aspx
Free, no authentication required.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

CDC_API_BASE    = "https://tools.cdc.gov/api/v2/resources"
CDC_SEARCH_URL  = f"{CDC_API_BASE}/media"
CDC_SYNDICATE_URL = f"{CDC_API_BASE}/media/{{media_id}}/syndicate"
HEADERS = {"User-Agent": "cdc-youtube-checker/1.0 (health accuracy research)"}
TIMEOUT = 15


def search_cdc(query: str, max_results: int = 5) -> list[dict]:
    # Note: 'sort=relevance' breaks many queries — omit it.
    # languageisocode=en is required; without it results are empty.
    params = {
        "q": query, "max": max_results,
        "mediatype": "html", "languageisocode": "en",
    }
    try:
        resp = requests.get(CDC_SEARCH_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not isinstance(results, list):
            return []
        return [
            {
                "id":          r.get("id"),
                "name":        r.get("name", ""),
                "sourceUrl":   r.get("sourceUrl", ""),
                "description": r.get("description", ""),
            }
            for r in results
            if r.get("id") and r.get("sourceUrl", "").startswith("https://www.cdc.gov")
        ]
    except Exception:
        return []


def fetch_cdc_content(media_id: int) -> str:
    try:
        url = CDC_SYNDICATE_URL.format(media_id=media_id)
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        # The syndicate endpoint returns results as a dict, not a list
        results = resp.json().get("results", {})
        if isinstance(results, list):
            html = results[0].get("content", "") if results else ""
        else:
            html = results.get("content", "")
        if not html:
            return ""
        return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    except Exception:
        return ""


def find_best_cdc_page(topic: str) -> dict | None:
    """
    Return the single most relevant CDC page for the topic.
    Tries progressively shorter queries if the full topic yields no results.
    Dict: {id, name, sourceUrl, content}
    """
    # Build a list of query variations to try: full → first 3 words → first 2 words → first word
    words = topic.split()
    queries = [topic]
    if len(words) > 3:
        queries.append(" ".join(words[:3]))
    if len(words) > 2:
        queries.append(" ".join(words[:2]))
    if len(words) > 1:
        queries.append(words[0])

    for query in queries:
        results = search_cdc(query, max_results=5)
        if results:
            best = results[0]
            content = fetch_cdc_content(best["id"])
            if content:
                return {
                    "id":        best["id"],
                    "name":      best["name"],
                    "sourceUrl": best["sourceUrl"],
                    "content":   content,
                }
    return None
