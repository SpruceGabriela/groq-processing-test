"""Run the component on the samples and log the run to MLflow."""
import json
import os
import time

import mlflow
from fastapi.testclient import TestClient

from app import ENGINE, app

client = TestClient(app)
samples = json.load(open("data/samples.json", encoding="utf-8"))

params = {"engine": ENGINE, "n_documents": len(samples)}
if ENGINE == "groq":
    import llm
    params.update({"model": llm.MODEL, "temperature": llm.TEMPERATURE, "prompt_version": llm.PROMPT_VERSION})
else:
    params.update({"min_keywords": 1, "max_span": 240})

mlflow.set_experiment("ai-processing")
with mlflow.start_run(run_name=ENGINE):
    mlflow.log_params(params)
    latencies, ok, claims_total = [], 0, 0
    for doc in samples:
        start = time.perf_counter()
        response = client.post("/process", json=doc)
        latencies.append(time.perf_counter() - start)
        if response.status_code == 200:
            ok += 1
            claims_total += len(response.json()["claims"])
        if ENGINE == "groq":
            time.sleep(3)  # stay under the free tier rate limit
    mlflow.log_metrics({"avg_latency_s": sum(latencies) / len(latencies),
                        "valid_response_rate": ok / len(samples),
                        "claims_per_document": claims_total / len(samples)})
print("Run logged. Open it with: mlflow ui")
