"""Recommendation pipeline with computed confidence and human gate."""
from datetime import datetime, timezone
import db
import llm
from risk import action_for_bucket, load_config, raise_bucket, score_risk, should_apply_caution_nudge


def build_recommendation(plot_id, config=None):
    config = config or load_config()
    all_days = db.weather_for_plot(plot_id)
    by_date = {r["date"]: r for r in all_days}
    last_date = max((datetime.fromisoformat(day).date() for day in by_date), default=datetime.now(timezone.utc).date())
    last_seven = [by_date.get((last_date.fromordinal(last_date.toordinal() - offset)).isoformat()) for offset in range(6, -1, -1)]
    present = [r for r in last_seven if r is not None]
    risk = score_risk(present, config)
    cases = db.get_past_overrides(risk["bucket"], 3)
    if should_apply_caution_nudge(cases):
        risk["bucket"] = raise_bucket(risk["bucket"])
        risk["action"] = action_for_bucket(risk["bucket"], risk["days_since_last_spray"], config)
    payload = {"plot_id": plot_id, "weather_last_7_days": last_seven, "risk": risk,
               "completeness_days": len(present), "past_cases": cases}
    try:
        answer = llm.recommend(payload)
    except Exception as exc:
        answer = {"action": risk["action"], "rationale": f"Using the rule action because the model was unavailable or returned invalid data: {exc}",
                  "evidence": [], "cited_case_ids": []}
    valid_case_ids = {case["id"] for case in cases}
    answer["cited_case_ids"] = [case_id for case_id in answer["cited_case_ids"] if case_id in valid_case_ids]
    agreement = 1.0 if answer["action"] == risk["action"] else (0.5 if "inspect" in (answer["action"], risk["action"]) else 0.0)
    confidence = 0.5 * (len(present) / 7) + 0.5 * agreement
    gated = confidence < config["confidence_threshold"]
    action = "inspect" if gated else answer["action"]
    evidence = answer["evidence"] + [f"Data completeness: {len(present)}/7 days",
                                     f"Placeholder rule bucket: {risk['bucket']} ({risk['action']})"]
    return {"plot_id": plot_id, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "risk_bucket": risk["bucket"], "action": action, "model_action": answer["action"],
            "rationale": answer["rationale"], "evidence": evidence, "confidence": round(confidence, 3),
            "gated": gated, "cited_case_ids": answer["cited_case_ids"], "risk": risk}


def create_and_log_recommendation(plot_id):
    result = build_recommendation(plot_id)
    result["id"] = db.add_decision(result)
    return result
