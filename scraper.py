"""
scraper.py
----------
Gathers raw, publicly available information about a person from the open web.

Design goals:
- No paid search API required (uses DuckDuckGo's HTML endpoint, which is free
  and does not require an API key). This satisfies the "seek public info via
  scraping" requirement from the brief.
- Wikipedia is queried directly via its public REST API for a reliable,
  structured starting point (when a page exists for the person).
- Every piece of text we keep is tagged with its source URL, so the final
  report can cite references and so the AI synthesis step is grounded only
  in retrieved text (reduces hallucination).
- Defensive: any single failed request (timeout, 4xx/5xx, parsing error)
  is swallowed and logged, never crashes the whole run.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("profile_agent.scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 10  # seconds
MAX_PAGE_CHARS = 6000  # cap per-page text so the AI context stays manageable


@dataclass
class Source:
    title: str
    url: str
    text: str


@dataclass
class ResearchBundle:
    person_name: str
    sources: list[Source] = field(default_factory=list)

    def as_context_text(self) -> str:
        """Flatten all collected sources into a single labeled text blob
        suitable for feeding to an LLM as grounding context."""
        chunks = []
        for i, s in enumerate(self.sources, start=1):
            chunks.append(
                f"[SOURCE {i}] {s.title}\nURL: {s.url}\n---\n{s.text}\n"
            )
        return "\n\n".join(chunks)

    def reference_list(self) -> list[dict]:
        return [{"title": s.title, "url": s.url} for s in self.sources]


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return url


def wikipedia_lookup(name: str) -> Source | None:
    """Fetch a Wikipedia summary + extract for the person, if a page exists."""
    try:
        search_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": name,
                "format": "json",
                "srlimit": 1,
            },
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        search_resp.raise_for_status()
        results = search_resp.json().get("query", {}).get("search", [])
        if not results:
            return None
        title = results[0]["title"]

        extract_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "prop": "extracts",
                "explaintext": 1,
                "titles": title,
                "format": "json",
            },
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        extract_resp.raise_for_status()
        pages = extract_resp.json().get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {})
        extract = page.get("extract", "")
        if not extract:
            return None
        return Source(
            title=f"Wikipedia: {title}",
            url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            text=extract[:MAX_PAGE_CHARS],
        )
    except Exception as exc:
        logger.warning("Wikipedia lookup failed for %r: %s", name, exc)
        return None


def duckduckgo_search(query: str, max_results: int = 8) -> list[dict]:
    """Scrape DuckDuckGo's HTML (non-JS) search results page.
    Returns a list of {title, url, snippet} dicts. Free, no API key needed.
    """
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("DuckDuckGo search failed for %r: %s", query, exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for result in soup.select("div.result")[:max_results]:
        link_tag = result.select_one("a.result__a")
        snippet_tag = result.select_one("a.result__snippet") or result.select_one(
            "div.result__snippet"
        )
        if not link_tag:
            continue
        url = link_tag.get("href", "")
        title = link_tag.get_text(strip=True)
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
        if url:
            results.append({"title": title, "url": url, "snippet": snippet})
    return results


def fetch_page_text(url: str) -> str | None:
    """Download a page and extract readable visible text (best-effort)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        logger.info("Could not fetch %s: %s", url, exc)
        return None

    try:
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:MAX_PAGE_CHARS] if text else None
    except Exception as exc:
        logger.info("Could not parse %s: %s", url, exc)
        return None


def gather_sources(
    person_name: str,
    max_results_per_query: int = 6,
    max_pages_to_fetch: int = 8,
    politeness_delay: float = 0.3,
) -> ResearchBundle:
    """Run a small battery of targeted searches to cover every section of the
    profile schema, deduplicate by domain, fetch page text for the most
    promising results, and return a ResearchBundle ready for AI synthesis.
    """
    bundle = ResearchBundle(person_name=person_name)

    wiki = wikipedia_lookup(person_name)
    if wiki:
        bundle.sources.append(wiki)

    queries = [
        f"{person_name} biography",
        f"{person_name} career timeline",
        f"{person_name} net worth occupation",
        f"{person_name} current city residence",
        f"{person_name} interests hobbies",
        f"{person_name} recent news",
    ]

    seen_domains: set[str] = {_domain(s.url) for s in bundle.sources}
    candidate_urls: list[dict] = []

    for q in queries:
        for r in duckduckgo_search(q, max_results=max_results_per_query):
            dom = _domain(r["url"])
            if dom in seen_domains:
                continue
            seen_domains.add(dom)
            candidate_urls.append(r)
        time.sleep(politeness_delay)

    for r in candidate_urls[:max_pages_to_fetch]:
        text = fetch_page_text(r["url"])
        if text:
            bundle.sources.append(Source(title=r["title"], url=r["url"], text=text))
        else:
            # Even without full page text, keep the search snippet — it's
            # still a usable, attributable fragment of public information.
            if r.get("snippet"):
                bundle.sources.append(
                    Source(title=r["title"], url=r["url"], text=r["snippet"])
                )
        time.sleep(politeness_delay)

    return bundle
