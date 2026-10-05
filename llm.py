"""OpenAI-compatible JSON client with a deterministic local mock."""
import json
import os

import requests
import streamlit as st

ACTIONS = {"spray", "wait", "inspect"}


def _setting(name, default=""):
    """Read model settings from environment variables or Streamlit secrets."""
    value = os.getenv(name)
    if value is not None:
        return value
    try:
        value = st.secrets.get(name, default)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default
    return str(value)


def _validate(value):
    if not isinstance(value, dict) or value.get("action") not in ACTIONS:
        raise ValueError("LLM response must contain a supported action")
    if not isinstance(value.get("rationale"), str) or not isinstance(value.get("evidence"), list):
        raise ValueError("LLM response has invalid rationale or evidence")
    citations = value.get("cited_case_ids", [])
    if not isinstance(citations, list):
        raise ValueError("cited_case_ids must be a list")
    return {"action": value["action"], "rationale": value["rationale"],
            "evidence": [str(x) for x in value["evidence"]], "cited_case_ids": citations}


def _mock(payload):
    rule = payload["risk"]["action"]
    cases = payload.get("past_cases", [])
    action = rule
    rationale = f"Mock response follows the placeholder rule action ({rule})."
    evidence = [f"7-day rainfall: {payload['risk']['rainfall_7d_mm']} mm",
                f"7-day mean humidity: {payload['risk']['mean_humidity_7d_pct']}%",
                f"Recent observations: {payload['completeness_days']}/7 days"]
    if len(cases) >= 2 and sum(c["human_decision"] in ("inspect", "wait") for c in cases) >= 2:
        action = "inspect"
        rationale = "Similar past overrides favored a more cautious inspection."
    return {"action": action, "rationale": rationale, "evidence": evidence,
            "cited_case_ids": [c["id"] for c in cases]}


def recommend(payload):
    if _setting("LLM_MOCK", "1") == "1":
        return _validate(_mock(payload))
    base = _setting("LLM_BASE_URL").rstrip("/")
    key = _setting("LLM_API_KEY")
    model = _setting("LLM_MODEL")
    if not base or not model:
        raise RuntimeError("Set LLM_MOCK=1 or configure LLM_BASE_URL and LLM_MODEL")
    prompt = "Return JSON only with action (spray|wait|inspect), rationale, evidence (array), cited_case_ids (array). Never invent case IDs.\n" + json.dumps(payload)
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": 300}
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    last_error = None
    for attempt in range(2):
        if attempt:
            body["messages"][0]["content"] += "\nYour previous answer was invalid. Return valid JSON only."
        try:
            response = requests.post(f"{base}/chat/completions", json=body, headers=headers, timeout=20)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return _validate(json.loads(content))
        except (ValueError, KeyError, IndexError, requests.RequestException) as exc:
            last_error = exc
    raise RuntimeError(f"LLM response failed validation after retry: {last_error}")
