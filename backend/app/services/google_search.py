import os
import re
import logging
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

# ----------------------------
# Configuration / constants
# ----------------------------
REQUEST_TIMEOUT = 10  # seconds
REQUEST_HEADERS = {
    "User-Agent": "LeakSentinel/1.0 (+https://example.local/)"
}

# Accept either GOOGLE_CSE_ID or GOOGLE_CX (your .env uses GOOGLE_CX)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID") or os.getenv("GOOGLE_CX")

# ----------------------------
# Regexes
# ----------------------------
# Accept +60, 60, or leading 0; allow separators (space, -, ., parentheses)
PHONE_RE = re.compile(
    r'(?:\+?60|60|0)(?:[\s\-\.\(]?\d{1,3}[\s\-\.\)]?)(?:[\s\-\.\d]){6,12}'
)

# Malaysian IC: YYMMDD-##-#### or 12 continuous digits
IC_RE = re.compile(r'(?:\d{6}-\d{2}-\d{4}|\d{12})')

# ----------------------------
# Helpers
# ----------------------------
def google_search_raw(query: str, num: int = 5) -> List[Dict[str, Any]]:
    """
    Minimal wrapper for Google Custom Search API.
    Returns the list of 'items' (may be empty).
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        raise RuntimeError("GOOGLE_API_KEY and GOOGLE_CSE_ID (or GOOGLE_CX) must be set in environment")

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "num": num,
    }
    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", []) or []


def normalize_malaysia_phone(raw: str) -> str:
    """
    Convert a matched raw phone snippet into canonical +60XXXXXXXXX
    """
    digits = re.sub(r'\D', '', raw.strip())
    if digits.startswith('0'):
        digits = '60' + digits[1:]
    if not digits.startswith('60') and len(digits) in (9, 10):
        digits = '60' + digits
    # Ensure leading +
    return '+' + digits if not digits.startswith('+') else digits


def text_from_pagemap(pagemap: Any) -> str:
    """
    Extract string content from pagemap structures returned by Google CSE.
    """
    parts = []
    if isinstance(pagemap, dict):
        for vals in pagemap.values():
            if isinstance(vals, list):
                for entry in vals:
                    if isinstance(entry, dict):
                        for v in entry.values():
                            if isinstance(v, str):
                                parts.append(v)
    return " \n ".join(parts)


def extract_matches_from_text(text: str) -> Dict[str, List[str]]:
    """
    Find both phone and IC matches in the given text.
    Returns dict with keys 'phones' and 'ics' containing raw matched strings.
    """
    phones = [m.group(0) for m in PHONE_RE.finditer(text)]
    ics = [m.group(0) for m in IC_RE.finditer(text)]

    def dedupe(seq):
        seen = set()
        out = []
        for s in seq:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    return {"phones": dedupe(phones), "ics": dedupe(ics)}


# ----------------------------
# Redaction / extract_matches expected by UI
# ----------------------------
def redact_ic(ic: str) -> str:
    """Return a masked IC string in a predictable format for UI (e.g. 'YYMMDD-**-****')."""
    if not ic:
        return ic
    s = ic.replace("-", "")
    if len(s) == 12:
        # show first 6, mask the rest partially
        return f"{s[:6]}-{s[6:8]}-****"
    # fallback: keep prefix and mask remainder
    if "-" in ic:
        parts = ic.split("-")
        if len(parts) == 3:
            return f"{parts[0]}-{parts[1]}-****"
    return ic[:6] + "-**-****"


def redact_phone(phone: str) -> str:
    """Return a masked phone string for UI (keeps some prefix and suffix digits)."""
    if not phone:
        return phone
    digits = re.sub(r'\D', '', phone)
    if len(digits) <= 6:
        return digits
    # keep first 4 and last 2 if possible
    if len(digits) <= 8:
        return digits[:3] + "****" + digits[-1:]
    return digits[:4] + "****" + digits[-2:]


def extract_matches(text: str) -> Dict[str, List[str]]:
    """
    Return dict shaped for the UI and orchestrator:
      {"ic_numbers": [...redacted...], "phone_numbers": [...redacted...]}
    """
    if not text:
        return {"ic_numbers": [], "phone_numbers": []}

    raw = extract_matches_from_text(text)
    raw_phones = raw.get("phones", [])
    raw_ics = raw.get("ics", [])

    # dedupe while preserving order, applying redaction
    seen = set()
    phones = []
    for p in raw_phones:
        r = redact_phone(p)
        if r not in seen:
            seen.add(r)
            phones.append(r)

    seen = set()
    ics = []
    for i in raw_ics:
        r = redact_ic(i)
        if r not in seen:
            seen.add(r)
            ics.append(r)

    return {"ic_numbers": ics, "phone_numbers": phones}


# ----------------------------
# Core extraction from items (kept for compatibility if needed)
# ----------------------------
def extract_phone_ic_hits_from_google_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse Google CSE items and return a list of hits:
    { type: 'phone'|'ic', raw_match, normalized (phone) or None, source_title, source_link, source_snippet }
    (This helper is not used by run_google_dork below but kept in case you need raw hits elsewhere.)
    """
    hits: List[Dict[str, Any]] = []
    for it in items:
        parts = []
        for k in ("title", "snippet", "htmlSnippet", "formattedUrl", "link"):
            v = it.get(k)
            if v:
                parts.append(v)
        pm_text = text_from_pagemap(it.get("pagemap", {}))
        if pm_text:
            parts.append(pm_text)

        combined = " \n ".join(parts)
        found = extract_matches_from_text(combined)

        if not found["phones"] and not found["ics"]:
            link = it.get("link")
            if link:
                try:
                    r = requests.get(link, timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS)
                    page_text = BeautifulSoup(r.text, "html.parser").get_text(" ")
                    found = extract_matches_from_text(page_text)
                except Exception:
                    logging.debug("Failed to fetch page %s for deeper extraction", link, exc_info=True)

        for p in found["phones"]:
            try:
                norm = normalize_malaysia_phone(p)
            except Exception:
                norm = None
            hits.append({
                "type": "phone",
                "raw_match": p,
                "normalized": norm,
                "source_title": it.get("title"),
                "source_link": it.get("link"),
                "source_snippet": it.get("snippet"),
            })
        for i in found["ics"]:
            hits.append({
                "type": "ic",
                "raw_match": i,
                "normalized": None,
                "source_title": it.get("title"),
                "source_link": it.get("link"),
                "source_snippet": it.get("snippet"),
            })

    return hits


# ----------------------------
# Public entrypoint
# ----------------------------
def run_google_dork(search_data: str, num_results: int = 5):
    """
    Primary function for the orchestrator.
    This new version is simpler and more effective for ALL data types.
    It returns ALL URLs found by Google as potential leads, without trying to
    be too strict and filtering them out. This is better for username scans.
    """
    results = []
    query = f'"{search_data}"'

    try:
        items = google_search_raw(query, num=num_results)
    except Exception as e:
        logging.exception("run_google_dork: google_search_raw failed")
        return {"success": False, "error": str(e), "results": []}

    logging.info("run_google_dork: google returned %d items for query=%s", len(items), query)

    # Loop through every item Google found and format it for the frontend.
    # We no longer try to verify matches, as this was filtering out username results.
    for item in items:
        # We still check for phone/IC in the snippet for display purposes, but we don't filter.
        snippet = item.get("snippet", "")
        matches = extract_matches(snippet) # This function is still useful for the UI

        results.append({
            "source_url": item.get("link"),
            "snippet": snippet,
            "matches": matches
        })

    logging.info("run_google_dork: finished, returning %d potential web mentions.", len(results))

    return {"success": True, "results": results}
# ---------- START: NEW PHONE/IC EXTRACTION BLOCK ----------
PHONE_CAND_RE = re.compile(r'[\+\(]?\d[\d\-\.\s\(\)]{6,25}\d')

def _validate_and_normalize_phone(candidate: str) -> Optional[str]:
    digits = re.sub(r'\D', '', candidate)
    if not digits:
        return None
    if len(digits) < 9 or len(digits) > 12:
        return None
    if digits.startswith('0'):
        digits = '60' + digits[1:]
    if not digits.startswith('60'):
        return None
    return '+' + digits

def extract_matches_from_text(text: str) -> Dict[str, List[str]]:
    if not text:
        return {"phones": [], "ics": []}
    ics = [m.group(0) for m in IC_RE.finditer(text)]
    candidates = PHONE_CAND_RE.findall(text)
    phones_normalized = []
    seen = set()
    for cand in candidates:
        norm = _validate_and_normalize_phone(cand)
        if not norm:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        phones_normalized.append(norm)
    return {"phones": phones_normalized, "ics": ics}

def extract_matches(text: str) -> Dict[str, List[str]]:
    if not text:
        return {"ic_numbers": [], "phone_numbers": []}
    raw = extract_matches_from_text(text)
    raw_phones = raw.get("phones", [])
    raw_ics = raw.get("ics", [])
    phones = []
    seen = set()
    for p in raw_phones:
        digits = re.sub(r'\D', '', p)
        if len(digits) <= 6:
            masked = digits
        elif len(digits) <= 8:
            masked = digits[:3] + "****" + digits[-1:]
        else:
            masked = digits[:4] + "****" + digits[-2:]
        if masked not in seen:
            seen.add(masked)
            phones.append(masked)
    ics = []
    seen = set()
    for i in raw_ics:
        s = i.replace("-", "")
        if len(s) == 12:
            masked = f"{s[:6]}-{s[6:8]}-****"
        else:
            masked = i
        if masked not in seen:
            seen.add(masked)
            ics.append(masked)
    return {"ic_numbers": ics, "phone_numbers": phones}
