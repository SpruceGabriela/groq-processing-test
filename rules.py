"""Rule-based dummy for the AI processing component (no LLM yet)."""
import re
from datetime import date

RULES_VERSION = "dummy-v1"

STACK_KEYWORDS = {
    "Energy supply": ["lng", "natural gas", "lpg", "uranium", "energy", "天然气", "能源", "液化"],
    "Food security": ["canola", "agri", "food", "pork", "seafood", "油菜", "农产品", "粮食"],
    "Payments, settlement, and investment": ["payment", "settlement", "fintech", "investment", "支付", "投资", "结算"],
    "Pharmaceuticals and biotech": ["pharma", "biotech", "drug", "vaccine", "医药", "生物", "药品"],
}
CANADA_WORDS = ["canada", "canadian", "加拿大"]
POLICY_WORDS = ["tariff", "export control", "regulation", "ban", "quota", "agreement", "关税", "出口管制", "协议"]

# Domain fragment -> tier (A official, B media/research, C state media, D social/unknown)
SOURCE_TIERS = {
    "gc.ca": "A", "gov.cn": "A",
    "reuters": "B", "cbc.ca": "B", "theglobeandmail": "B", "scmp": "B",
    "xinhua": "C", "people.com.cn": "C", "cgtn": "C", "chinadaily": "C",
    "weibo": "D", "wechat": "D", "x.com": "D",
}
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


def split_paragraphs(text):
    return [p.strip() for p in text.splitlines() if p.strip()]


def split_sentences(paragraph):
    parts = re.split(r"(?<=[.!?。！？])\s*", paragraph)
    return [s.strip() for s in parts if s.strip()]


def find_stack(text):
    lower = text.lower()
    hits = {stack: sum(k in lower for k in kws) for stack, kws in STACK_KEYWORDS.items()}
    best = max(hits, key=hits.get)
    return (best, hits[best]) if hits[best] > 0 else (None, 0)


def find_date(sentence):
    m = re.search(r"\d{4}-\d{2}-\d{2}", sentence)
    if m:
        return m.group(0)
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", sentence)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    m = re.search(r"(\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})", sentence, re.I)
    if m:
        return date(int(m[3]), MONTHS[m[2].lower()], int(m[1])).isoformat()
    return None


def find_amount(sentence):
    m = re.search(r"(US\$|C\$|CAD|USD|RMB|CNY|\$)\s?(\d[\d.,]*)\s?(million|billion)?", sentence, re.I)
    if not m:
        return None
    value = float(m[2].replace(",", "").rstrip("."))
    value *= {"million": 1e6, "billion": 1e9}.get((m[3] or "").lower(), 1)
    symbol = m[1].upper()
    # A dollar sign alone does not identify a currency (starter prompt 01).
    currency = {"US$": "USD", "USD": "USD", "C$": "CAD", "CAD": "CAD",
                "RMB": "CNY", "CNY": "CNY"}.get(symbol)
    return {"value": value, "currency": currency, "kind": "other",
            "original_expression": m.group(0).strip(), "canadian_share_verified": False}


def source_tier(url):
    for fragment, tier in SOURCE_TIERS.items():
        if fragment in (url or "").lower():
            return tier
    return "D"


def extract_claims(doc, max_span=240, min_keywords=1):
    """Return claims in the starter's extraction.schema.json format."""
    claims = []
    for p_index, paragraph in enumerate(split_paragraphs(doc["text"]), start=1):
        for sentence in split_sentences(paragraph):
            stack, hits = find_stack(sentence)
            if hits < min_keywords:
                continue
            words = sentence.split()
            claims.append({
                "source_id": doc["source_id"],
                "document_id": doc.get("document_id") or doc["source_id"],
                "subject_name_original": words[0] if words else sentence[:20],
                "subject_name_english": None,
                "predicate": "mentions",
                "claim_english": sentence if doc.get("language") == "en" else "[translation pending]",
                "original_support_span": sentence[:max_span],
                "locator": f"para {p_index}",
                "publication_date": doc.get("publication_date"),
                "event_date": find_date(sentence),
                "effective_date": None,
                "expires_on": None,
                "stage": None,
                "territories": ["Canada"] if any(w in sentence.lower() for w in CANADA_WORDS) else [],
                "conditions": [],
                "amount": find_amount(sentence),
                "quantity": None,
                "uncertainty": ["rule-based extraction, not reviewed"],
            })
    return claims


def verify_claims(claims, doc):
    """A claim is supported only if its span appears word for word in the document."""
    return [{"locator": c["locator"],
             "status": "supported" if c["original_support_span"] in doc["text"] else "not established"}
            for c in claims]


def assess(doc, claims):
    """Article-level output agreed with Roles 3, 5 and 6."""
    text = doc["text"].lower()
    stack, _ = find_stack(text)
    tier = source_tier(doc.get("canonical_url"))
    credibility = "Likely reliable" if tier in ("A", "B") else "Unverified"
    if not claims or stack is None:
        score, why = 1, "No match with the focus areas."
    elif any(w in text for w in CANADA_WORDS):
        score, why = 5, f"Mentions Canada directly ({stack})."
    elif any(w in text for w in POLICY_WORDS):
        score, why = 4, f"Possible policy change ({stack})."
    else:
        score, why = 3, f"Related to {stack}, no clear link to Canada."
    first = claims[0]["original_support_span"] if claims else ""
    return {
        "article_id": doc["source_id"],
        "language": doc.get("language"),
        "title_en": doc.get("title", ""),
        "focus_area": stack,
        "source_tier": tier,
        "credibility_label": credibility,
        "relevance_score": score,
        "justification": why,
        "summary_en": first if doc.get("language") == "en" else "[translation pending]",
        "evidence": [{"quote": c["original_support_span"], "source_url": doc.get("canonical_url"),
                      "location": c["locator"]} for c in claims[:3]],
        "uncertain": True,
        "claims": claims,
    }
