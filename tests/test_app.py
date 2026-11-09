import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)
SAMPLES = json.loads(Path("data/samples.json").read_text(encoding="utf-8"))


def test_every_claim_has_evidence_and_locator():
    for doc in SAMPLES:
        for claim in client.post("/extract", json=doc).json()["claims"]:
            assert claim["original_support_span"] and claim["locator"]


def test_dollar_sign_alone_has_no_currency():
    doc = {**SAMPLES[0], "text": "The energy deal is worth $5 million."}
    claim = client.post("/extract", json=doc).json()["claims"][0]
    assert claim["amount"]["currency"] is None


def test_unrelated_text_gets_low_score():
    assert client.post("/process", json=SAMPLES[2]).json()["relevance_score"] == 1


def test_canada_mention_gets_high_score():
    assert client.post("/process", json=SAMPLES[1]).json()["relevance_score"] == 5
