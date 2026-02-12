import random
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

def minutes(x):
    return timedelta(minutes=int(x))

def generate_day(date_str: str, n_visits: int, location="Bank_Branch_A"):
    date = datetime.strptime(date_str, "%Y-%m-%d")
    stages = ["Registration", "Service", "Payment"]

    rows = []
    for i in range(n_visits):
        hour = random.choices(
            population=[8,9,10,11,12,13,14,15,16],
            weights=[6,8,18,20,18,10,7,6,4],
            k=1
        )[0]
        arrival = date.replace(hour=hour, minute=random.randint(0, 59), second=0)

        priority = random.choices(["normal", "urgent"], weights=[92, 8], k=1)[0]
        channel  = random.choices(["walk_in", "appointment"], weights=[80, 20], k=1)[0]

        current_time = arrival
        visit_id = f"{date_str.replace('-','')}_V{i:05d}"

        for stage in stages:
            if stage == "Registration":
                service_min = max(2, int(random.gauss(6, 2)))
            elif stage == "Service":
                service_min = max(3, int(random.gauss(12, 4)))
            else:
                service_min = max(1, int(random.gauss(4, 2)))

            peak_factor = 1.6 if hour in [10, 11, 12] else 1.0
            stage_factor = 1.3 if stage == "Registration" else 1.0
            urgent_factor = 0.7 if priority == "urgent" else 1.0
            appt_factor = 0.85 if channel == "appointment" else 1.0

            wait_min = max(0, int(random.gauss(7, 5) * peak_factor * stage_factor * urgent_factor * appt_factor))

            service_start = current_time + minutes(wait_min)
            service_end   = service_start + minutes(service_min)

            rows.append({
                "visit_id": visit_id,
                "arrival_time": arrival,
                "stage": stage,
                "wait_minutes": wait_min,
                "service_minutes": service_min,
                "service_start_time": service_start,
                "service_end_time": service_end,
                "priority": priority,
                "channel": channel,
                "location": location
            })
            current_time = service_end

    return pd.DataFrame(rows)

def main():
    # project root = parent of "simulation" folder
    project_root = Path(__file__).resolve().parents[1]
    raw_dir = project_root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    start = datetime(2026, 2, 1)
    all_days = []
    for d in range(7):
        day = start + timedelta(days=d)
        n = random.randint(240, 360)
        all_days.append(generate_day(day.strftime("%Y-%m-%d"), n))

    df = pd.concat(all_days, ignore_index=True)
    out_path = raw_dir / "service_events.csv"
    df.to_csv(out_path, index=False)

    print("✅ Saved:", out_path)
    print("Rows:", len(df))
    print(df.head(3))

if __name__ == "__main__":
    main()
