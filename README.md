# AI Processing – MVP (Role 4)

First version of the AI processing component for the China Foreign Policy Roll-up.
It receives one article and returns its focus area, credibility label, relevance
score (1–5), justification, summary and evidence, plus claims in the starter's
`extraction.schema.json` format.

Two engines, chosen in `.env`:
- `ENGINE=dummy`: keyword and regex rules (no AI). Also our keyword baseline.
- `ENGINE=groq`: Groq LLM using the starter's prompt 01 and `prompts/assess.md`.

## Run it
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
uvicorn app:app --reload
```
Open http://localhost:8000/docs and try `POST /process` with an item from `data/samples.json`.

## Test and log to MLflow
```bash
pytest -q                 # with ENGINE=dummy
python run_eval.py        # logs a run (3+ params, 2+ metrics)
mlflow ui                 # http://localhost:5000
```

## Safeguards
- Every response is validated against `schemas/extraction.schema.json`.
- Claims whose quote is not found in the original text are dropped.
- The model can never mark an item as "Verified", and the score is kept between 1 and 5.

## Known limitations
Keyword rules misclassify (e.g. "investment" is read as Payments), miss sentences
without keywords and do not translate. Use only public articles with the Groq free tier.
