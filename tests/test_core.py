import pytest
from risk import action_for_bucket, raise_bucket, score_risk, should_apply_caution_nudge
from agent import build_recommendation

CONFIG = {"thresholds": {"rainfall_7d_high_mm": 50, "rainfall_7d_medium_mm": 25,
                          "humidity_7d_high_pct": 90, "humidity_7d_medium_pct": 82,
                          "min_spray_interval_days": 14}, "confidence_threshold": 0.7}


def days(rain, humidity, since=20):
    return [{"rainfall_mm": rain, "humidity_pct": humidity, "days_since_last_spray": since}]


def test_risk_bucketing_and_rule_actions():
    assert score_risk(days(55, 91), CONFIG)["bucket"] == "high"
    assert score_risk(days(30, 80), CONFIG)["bucket"] == "medium"
    assert score_risk(days(2, 70), CONFIG)["bucket"] == "low"
    assert score_risk(days(55, 91, since=4), CONFIG)["action"] == "inspect"


def test_confidence_and_gate_behavior(monkeypatch):
    monkeypatch.setattr("agent.load_config", lambda: CONFIG)
    monkeypatch.setattr("agent.db.weather_for_plot", lambda plot: [])
    monkeypatch.setattr("agent.db.get_past_overrides", lambda bucket, limit: [])
    monkeypatch.setattr("agent.llm.recommend", lambda payload: {"action": "spray", "rationale": "test",
                      "evidence": [], "cited_case_ids": []})
    result = build_recommendation("missing")
    assert result["confidence"] == 0.0
    assert result["gated"] is True
    assert result["action"] == "inspect"


def test_confidence_formula_complete_agreement(monkeypatch):
    monkeypatch.setattr("agent.load_config", lambda: CONFIG)
    monkeypatch.setattr("agent.db.get_past_overrides", lambda bucket, limit: [])
    # Avoid depending on the wall clock: no present days yields zero completeness.
    monkeypatch.setattr("agent.db.weather_for_plot", lambda plot: [])
    monkeypatch.setattr("agent.llm.recommend", lambda payload: {"action": "wait", "rationale": "test",
                      "evidence": [], "cited_case_ids": []})
    result = build_recommendation("missing")
    # Missing weather gives 0 completeness, but rule/model agreement contributes 0.5.
    assert result["confidence"] == pytest.approx(0.5)


def test_override_nudge_level_and_action():
    assert raise_bucket("low") == "medium"
    assert raise_bucket("medium") == "high"
    assert raise_bucket("high") == "high"
    assert action_for_bucket("high", 20, CONFIG) == "spray"


def test_override_nudge_requires_two_more_cautious_overrides():
    cases = [{"recommendation": "spray", "human_decision": "inspect"},
             {"recommendation": "inspect", "human_decision": "wait"}]
    assert should_apply_caution_nudge(cases)
    assert not should_apply_caution_nudge(cases[:1])
    assert not should_apply_caution_nudge([{"recommendation": "wait", "human_decision": "inspect"}])
