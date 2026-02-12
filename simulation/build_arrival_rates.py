import pandas as pd

def main():
    df = pd.read_csv("data/raw/service_events.csv", parse_dates=["arrival_time"])
    # use only Registration rows to avoid counting each visit multiple times
    reg = df[df["stage"] == "Registration"].copy()
    reg["hour"] = reg["arrival_time"].dt.hour

    hourly = reg.groupby("hour").size().reset_index(name="arrivals")
    # convert arrivals (for 7 days) -> average arrivals per hour per day
    hourly["arrivals_per_hour"] = (hourly["arrivals"] / 7.0).round(2)
    hourly = hourly[["hour", "arrivals_per_hour"]].sort_values("hour")

    hourly.to_csv("data/processed/arrival_rates.csv", index=False)
    print("Saved:", "data/processed/arrival_rates.csv")
    print(hourly.head(10))

if __name__ == "__main__":
    main()
