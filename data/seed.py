"""Create reproducible, explicitly simulated cocoa plot weather."""
from datetime import date, timedelta
import random

PLOTS = {"Plot A": "Rising rain and humidity", "Plot B": "Recent gaps in observations", "Plot C": "Middle-range conditions"}


def generate_seed_data(today: date | None = None) -> list[dict]:
    today = today or date.today()
    rng = random.Random(17)
    rows = []
    for plot in PLOTS:
        for ago in range(29, -1, -1):
            day = today - timedelta(days=ago)
            if plot == "Plot B" and ago in (1, 3, 5, 6):
                continue
            if plot == "Plot A":
                rainfall = 2 + (29 - ago) * 0.25 + rng.uniform(0, 1.8)
                humidity = min(96, 68 + (29 - ago) * 0.72 + rng.uniform(0, 4))
                since_spray = 22 + ago
            elif plot == "Plot B":
                rainfall = rng.uniform(0, 5)
                humidity = rng.uniform(70, 82)
                since_spray = 18 + ago
            else:
                rainfall = rng.uniform(2.5, 5.5)
                humidity = rng.uniform(79, 88)
                since_spray = 20 + ago
            rows.append({"plot_id": plot, "date": day.isoformat(), "rainfall_mm": round(rainfall, 1),
                         "humidity_pct": round(humidity, 1), "temp_c": round(rng.uniform(23, 30), 1),
                         "days_since_last_spray": since_spray, "inspection_note": None})
    return rows
