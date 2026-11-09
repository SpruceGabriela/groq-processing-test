"""FastAPI service called by n8n through an HTTP Request node."""

import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from jsonschema import ValidationError, validate
from pydantic import BaseModel

import rules

load_dotenv()  # reads ENGINE, GROQ_API_KEY and GROQ_MODEL from .env
ENGINE = os.getenv("ENGINE", "dummy")  # "dummy" or "groq"
SCHEMA = json.load(open("schemas/extraction.schema.json", encoding="utf-8"))
app = FastAPI(title="AI processing", version=ENGINE)


class Document(BaseModel):
    source_id: str
    canonical_url: str | None = None
    publication_date: str | None = None
    language: str = "en"
    title: str = ""
    text: str


def get_claims(doc):
    if ENGINE == "groq":
        import llm

        claims = llm.extract_claims_llm(doc)
    else:
        claims = rules.extract_claims(doc)
    try:
        validate({"claims": claims}, SCHEMA)
    except ValidationError as err:
        raise HTTPException(status_code=502, detail=f"Schema error: {err.message}")
    # Faithful extraction: keep only claims whose quote really exists in the text.
    return [c for c in claims if c["original_support_span"] in doc["text"]]


@app.get("/health")
def health():
    return {"status": "ok", "engine": ENGINE}


@app.post("/extract")
def extract(doc: Document):
    return {"claims": get_claims(doc.model_dump())}


@app.post("/verify")
def verify(doc: Document):
    data = doc.model_dump()
    if ENGINE == "groq":
        import llm

        claims = llm.extract_claims_llm(data)
    else:
        claims = rules.extract_claims(data)
    return {"results": rules.verify_claims(claims, data)}


@app.post("/process")
def process(doc: Document):
    data = doc.model_dump()
    claims = get_claims(data)
    result = rules.assess(data, claims)  # dummy result, also the baseline
    if ENGINE == "groq":
        import llm

        tier = rules.source_tier(data.get("canonical_url"))
        ai = llm.assess_llm(data, claims, tier)
        result.update(
            {
                k: ai.get(k, result.get(k))
                for k in (
                    "title_en",
                    "summary_en",
                    "focus_area",
                    "credibility_label",
                    "relevance_score",
                    "justification",
                    "uncertain",
                )
            }
        )
        result["red_flags"] = ai.get("red_flags", [])
        result["opportunity"] = ai.get("opportunity")
        # Guardrails: the model cannot mark anything as Verified or go outside 1-5.
        if result["credibility_label"] not in (
            "Likely reliable",
            "Unverified",
            "Discarded",
        ):
            result["credibility_label"] = "Unverified"
        result["relevance_score"] = min(5, max(1, int(result["relevance_score"])))
    score, label = result["relevance_score"], result["credibility_label"]
    if label == "Discarded" or score <= 2:
        result["decision"] = "discard"
    elif label == "Likely reliable" and score >= 3:
        result["decision"] = "briefing"
    else:
        result["decision"] = "human review"
    return result
