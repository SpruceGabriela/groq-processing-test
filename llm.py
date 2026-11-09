"""Groq version of the AI processing component."""
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TEMPERATURE = 0.1
PROMPT_VERSION = "v1"
client = OpenAI(api_key=os.getenv("GROQ_API_KEY", "missing"), base_url="https://api.groq.com/openai/v1")


def read(path):
    return open(path, encoding="utf-8").read()


EXTRACT_PROMPT = read("prompts/01_extract.md") + "\n\nSchema:\n" + read("schemas/extraction.schema.json")
ASSESS_PROMPT = read("prompts/assess.md")


def ask(system, payload):
    r = client.chat.completions.create(
        model=MODEL, temperature=TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
    return json.loads(r.choices[0].message.content)


def extract_claims_llm(doc):
    return ask(EXTRACT_PROMPT, doc).get("claims", [])


def assess_llm(doc, claims, tier):
    return ask(ASSESS_PROMPT, {"document": doc, "claims": claims, "source_tier": tier})
