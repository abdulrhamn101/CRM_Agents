"""Email finder — tries to discover a contact email for a company.

Strategy (in order):
1. Fetch the company website and a few common contact pages (/contact, /about, ...).
2. Regex-scan the HTML for email addresses; prefer ones matching the company's domain.
3. If website scrape yields nothing (or no website at all), fall back to a
   DuckDuckGo web search for "<company> contact email <city>" and regex
   the result snippets.
4. If still nothing, fall back to a heuristic guess: info@<domain>.

Returns a dict with `email`, `source`, `confidence`:
- "website_scrape"   / high   → scraped, domain-matching
- "website_scrape"   / medium → scraped, off-domain (e.g. agency contact)
- "web_search"       / medium → found via web search, matches domain
- "web_search"       / low    → found via web search, off-domain
- "heuristic_guess"  / low    → info@<domain> fallback
- "not_found"        / none   → no website + no search hits
"""

import re
from urllib.parse import urljoin, urlparse

import requests

try:
    from duckduckgo_search import DDGS
    _WEB_SEARCH_AVAILABLE = True
except ImportError:
    _WEB_SEARCH_AVAILABLE = False


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

CONTACT_PATHS = ["", "contact", "contact-us", "contactus", "about", "about-us", "ar/contact", "en/contact"]

USER_AGENT = "Mozilla/5.0 (compatible; BeamDataEmailFinder/1.0)"

# Email locals that strongly indicate a real human/business inbox
GOOD_LOCALS = {"info", "contact", "hello", "sales", "business", "inquiries", "inquiry"}
# Locals worth keeping but lower-priority
OK_LOCALS = {"support", "help", "marketing", "press", "media"}
# Locals to deprioritise
BAD_LOCALS = {"admin", "webmaster", "noreply", "no-reply", "donotreply", "do-not-reply", "postmaster"}

# Common junk hits (CDNs, image filenames, tracker domains, etc.)
JUNK_SUBSTR = (
    "example.com", "example.org", "your-domain", "yourcompany",
    "sentry.io", "wixpress.com", "google-analytics", "googletagmanager",
    "@x.com", "@2x.png", "@3x.png",
)
ASSET_EXTS = ("png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "css", "js")


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _domain_of(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc.removeprefix("www.")


def _fetch(url: str, timeout: float = 6.0) -> str:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
        if resp.status_code == 200 and "text" in resp.headers.get("Content-Type", ""):
            return resp.text
    except Exception:
        pass
    return ""


def _extract_emails(html: str) -> list[str]:
    found = EMAIL_RE.findall(html)
    out, seen = [], set()
    for raw in found:
        e = raw.lower().strip(".,;:)(<>\"'")
        if e in seen:
            continue
        if any(e.endswith("." + ext) for ext in ASSET_EXTS):
            continue
        if any(j in e for j in JUNK_SUBSTR):
            continue
        if "@" not in e or e.count("@") != 1:
            continue
        seen.add(e)
        out.append(e)
    return out


def _score(email: str, target_domain: str) -> tuple[int, int]:
    """Sort key — bigger first. (locality_score, domain_match)."""
    local = email.split("@", 1)[0]
    domain = email.split("@", 1)[1]

    if local in GOOD_LOCALS:
        locality = 30
    elif local in OK_LOCALS:
        locality = 15
    elif local in BAD_LOCALS:
        locality = -20
    else:
        locality = 5

    domain_match = 1 if target_domain and (domain == target_domain or domain.endswith("." + target_domain)) else 0
    return (locality, domain_match)


def _web_search_for_email(company_name: str, city: str | None = None) -> list[str]:
    """Search the web (DuckDuckGo) for the company's contact email.
    Returns the emails found in result titles, snippets, and URLs."""
    if not _WEB_SEARCH_AVAILABLE:
        return []

    queries = [
        f'"{company_name}" contact email' + (f' {city}' if city else ''),
        f'"{company_name}" email site:linkedin.com' + (f' {city}' if city else ''),
    ]

    blob_parts: list[str] = []
    for q in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(q, max_results=8, safesearch="off"))
            for r in results:
                blob_parts.append(r.get("title", ""))
                blob_parts.append(r.get("body", ""))
                blob_parts.append(r.get("href", ""))
        except Exception:
            continue

    return _extract_emails(" ".join(blob_parts))


def find_email(company_name: str, website: str | None = None, city: str | None = None) -> dict:
    """Try to find a contact email. Returns {email, source, confidence, ...}."""
    url = _normalize_url(website or "")
    domain = _domain_of(url) if url else ""

    # 1. Website scrape
    scraped: list[str] = []
    if url and domain:
        for path in CONTACT_PATHS:
            page_url = urljoin(url.rstrip("/") + "/", path)
            html = _fetch(page_url)
            if html:
                scraped.extend(_extract_emails(html))

    if scraped:
        scraped.sort(key=lambda e: _score(e, domain), reverse=True)
        best = scraped[0]
        on_domain = best.split("@", 1)[1].endswith(domain)
        return {
            "email": best,
            "source": "website_scrape",
            "confidence": "high" if on_domain else "medium",
            "company_name": company_name,
            "candidates": scraped[:5],
        }

    # 2. Web search fallback
    web_hits = _web_search_for_email(company_name, city=city)
    if web_hits:
        if domain:
            web_hits.sort(key=lambda e: _score(e, domain), reverse=True)
        best = web_hits[0]
        on_domain = bool(domain) and best.split("@", 1)[1].endswith(domain)
        return {
            "email": best,
            "source": "web_search",
            "confidence": "medium" if on_domain else "low",
            "company_name": company_name,
            "candidates": web_hits[:5],
        }

    # 3. Heuristic guess (only useful if we have a domain at all)
    if domain:
        return {
            "email": f"info@{domain}",
            "source": "heuristic_guess",
            "confidence": "low",
            "company_name": company_name,
        }

    return {
        "email": None,
        "source": "not_found",
        "confidence": "none",
        "company_name": company_name,
        "note": "no website provided and no web-search hits"
                + ("" if _WEB_SEARCH_AVAILABLE else " (install duckduckgo-search to enable web search)"),
    }
