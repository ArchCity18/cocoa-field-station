"""Placeholder rule score. Values are not agronomy guidance."""
from pathlib import Path
import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def score_risk(days, config=None):
    config = config or load_config()
    present = [r for r in days if r is not None]
    rainfall = sum(float(r["rainfall_mm"]) for r in present)
    humidity = sum(float(r["humidity_pct"]) for r in present) / len(present) if present else 0.0
    since_spray = int(present[-1]["days_since_last_spray"]) if present else 0
    t = config["thresholds"]
    if rainfall >= t["rainfall_7d_high_mm"] and humidity >= t["humidity_7d_high_pct"]:
        bucket = "high"
    elif rainfall >= t["rainfall_7d_medium_mm"] or humidity >= t["humidity_7d_medium_pct"]:
        bucket = "medium"
    else:
        bucket = "low"
    if bucket == "high":
        action = "spray" if since_spray >= t["min_spray_interval_days"] else "inspect"
    else:
        action = "inspect" if bucket == "medium" else "wait"
    return {"bucket": bucket, "action": action, "rainfall_7d_mm": round(rainfall, 1),
            "mean_humidity_7d_pct": round(humidity, 1), "days_since_last_spray": since_spray}


def raise_bucket(bucket):
    return {"low": "medium", "medium": "high", "high": "high"}[bucket]


def action_for_bucket(bucket, days_since_spray, config=None):
    config = config or load_config()
    if bucket == "high" and days_since_spray >= config["thresholds"]["min_spray_interval_days"]:
        return "spray"
    return "inspect" if bucket == "medium" or bucket == "high" else "wait"


def should_apply_caution_nudge(cases):
    """Whether at least two retrieved overrides moved to a more cautious action."""
    # Withholding treatment is the more cautious choice: spray < inspect < wait.
    caution = {"spray": 0, "inspect": 1, "wait": 2}
    return sum(caution[c["human_decision"]] > caution[c["recommendation"]]
               for c in cases if c["human_decision"] in caution and c["recommendation"] in caution) >= 2
