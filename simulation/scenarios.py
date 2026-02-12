import pandas as pd
from config import SimConfig
from simulate import run_one_day, summarize

def estimate_cost(cfg: SimConfig, scenario: dict) -> float:
    # staff-hours baseline
    hours = cfg.day_end_hour - cfg.day_start_hour
    baseline_staff = cfg.reg_staff + cfg.svc_staff + cfg.pay_staff
    baseline_cost = baseline_staff * hours * cfg.cost_per_staff_hour

    # peak add cost only during peak window
    peak_hours = (cfg.peak_end_hour - cfg.peak_start_hour + 1)  # inclusive
    peak_add = scenario.get("reg_peak_add", 0) + scenario.get("svc_peak_add", 0) + scenario.get("pay_peak_add", 0)
    add_cost = peak_add * peak_hours * cfg.cost_per_staff_hour
    return round(baseline_cost + add_cost, 2)

def main():
    cfg = SimConfig(sla_wait_minutes=20, cost_per_staff_hour=1.0)

    arrival_rates_csv = "data/processed/arrival_rates.csv"

    scenarios = [
        {"scenario_name": "baseline", "reg_peak_add": 0, "svc_peak_add": 0, "pay_peak_add": 0},
        {"scenario_name": "add_reg_peak_+1", "reg_peak_add": 1, "svc_peak_add": 0, "pay_peak_add": 0},
        {"scenario_name": "add_svc_peak_+1", "reg_peak_add": 0, "svc_peak_add": 1, "pay_peak_add": 0},
        {"scenario_name": "add_reg_peak_+1_add_svc_peak_+1", "reg_peak_add": 1, "svc_peak_add": 1, "pay_peak_add": 0},
        {"scenario_name": "add_pay_peak_+1", "reg_peak_add": 0, "svc_peak_add": 0, "pay_peak_add": 1},
    ]

    summaries = []
    baseline_summary = None

    for sc in scenarios:
        df = run_one_day(cfg, arrival_rates_csv, sc)
        # save baseline detailed events (optional)
        if sc["scenario_name"] == "baseline":
            df.to_csv("data/processed/sim_events_baseline.csv", index=False)

        s = summarize(df, cfg)
        if not s:
            continue

        s.update(sc)
        s["estimated_cost"] = estimate_cost(cfg, sc)
        summaries.append(s)

        if sc["scenario_name"] == "baseline":
            baseline_summary = s

    out = pd.DataFrame(summaries)

    # improvement vs baseline
    if baseline_summary:
        out["sla_improvement"] = (out["sla_percent"] - baseline_summary["sla_percent"]).round(2)
        out["p95_wait_improvement"] = (baseline_summary["p95_wait_total"] - out["p95_wait_total"]).round(2)

    out = out.sort_values(["sla_percent", "p95_wait_total"], ascending=[False, True])
    out.to_csv("data/processed/scenario_summary.csv", index=False)

    print("Saved:")
    print(" - data/processed/sim_events_baseline.csv (baseline events)")
    print(" - data/processed/scenario_summary.csv (scenario comparison)")
    print(out)

if __name__ == "__main__":
    main()
