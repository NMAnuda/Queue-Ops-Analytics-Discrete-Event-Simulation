import random
import math
import pandas as pd
import simpy
from datetime import datetime, timedelta

from config import SimConfig

random.seed(42)

def clamp_positive(x: float, minimum: float = 0.0) -> float:
    return max(minimum, x)

def normal_minutes(mean: float, std: float) -> float:
    return clamp_positive(random.gauss(mean, std), minimum=0.5)

def to_sim_minutes(config: SimConfig, dt: datetime) -> int:
    day_start = dt.replace(hour=config.day_start_hour, minute=0, second=0, microsecond=0)
    return int((dt - day_start).total_seconds() / 60)

def hour_from_sim_minutes(config: SimConfig, t: float) -> int:
    return config.day_start_hour + int(t // 60)

class StageResources:
    """
    Allows dynamic capacity (peak staffing) by swapping resources at peak window boundaries.
    Simple approach: we create separate resources for peak vs off-peak for each stage.
    """
    def __init__(self, env: simpy.Environment, config: SimConfig, reg_peak_add=0, svc_peak_add=0, pay_peak_add=0):
        self.env = env
        self.config = config

        # off-peak resources
        self.reg_off = simpy.Resource(env, capacity=config.reg_staff)
        self.svc_off = simpy.Resource(env, capacity=config.svc_staff)
        self.pay_off = simpy.Resource(env, capacity=config.pay_staff)

        # peak resources (baseline + additional)
        self.reg_peak = simpy.Resource(env, capacity=config.reg_staff + reg_peak_add)
        self.svc_peak = simpy.Resource(env, capacity=config.svc_staff + svc_peak_add)
        self.pay_peak = simpy.Resource(env, capacity=config.pay_staff + pay_peak_add)

    def _is_peak(self) -> bool:
        h = hour_from_sim_minutes(self.config, self.env.now)
        return (h >= self.config.peak_start_hour) and (h <= self.config.peak_end_hour)

    def reg(self):
        return self.reg_peak if self._is_peak() else self.reg_off

    def svc(self):
        return self.svc_peak if self._is_peak() else self.svc_off

    def pay(self):
        return self.pay_peak if self._is_peak() else self.pay_off

def arrival_stream_for_day(arrival_rates_csv: str, config: SimConfig) -> dict:
    rates = pd.read_csv(arrival_rates_csv)
    # hours in [day_start, day_end)
    mapping = {int(r["hour"]): float(r["arrivals_per_hour"]) for _, r in rates.iterrows()}
    return mapping

def arrivals_for_hour(rate_per_hour: float) -> int:
    """
    Convert expected arrivals/hour to an integer count for the simulated day.
    We use Poisson sampling for realism.
    """
    if rate_per_hour <= 0:
        return 0
    # Poisson via Knuth method (simple, ok for small rates)
    L = math.exp(-rate_per_hour)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1

def customer(env: simpy.Environment, cfg: SimConfig, res: StageResources, cust_id: str, priority: str, channel: str, results: list):
    # stage order
    stages = [
        ("Registration", res.reg, cfg.reg_mean, cfg.reg_std),
        ("Service", res.svc, cfg.svc_mean, cfg.svc_std),
        ("Payment", res.pay, cfg.pay_mean, cfg.pay_std),
    ]

    arrival_t = env.now
    current_t = arrival_t

    total_wait = 0.0
    total_service = 0.0

    for stage_name, resource_fn, mean, std in stages:
        # priority can influence service slightly (optional small effect)
        prio_factor = 0.9 if priority == "urgent" else 1.0
        appt_factor = 0.95 if channel == "appointment" else 1.0

        service_time = normal_minutes(mean, std) * prio_factor * appt_factor

        resource = resource_fn()
        with resource.request() as req:
            q_enter = env.now
            yield req
            start = env.now
            wait = start - q_enter

            yield env.timeout(service_time)
            end = env.now

        results.append({
            "customer_id": cust_id,
            "arrival_minute": arrival_t,
            "stage": stage_name,
            "wait_minutes": round(wait, 2),
            "service_minutes": round(service_time, 2),
            "service_start_minute": round(start, 2),
            "service_end_minute": round(end, 2),
            "priority": priority,
            "channel": channel
        })

        total_wait += wait
        total_service += service_time
        current_t = end

    # store end-to-end summary row as a separate record type (optional)
    results.append({
        "customer_id": cust_id,
        "arrival_minute": arrival_t,
        "stage": "__TOTAL__",
        "wait_minutes": round(total_wait, 2),
        "service_minutes": round(total_service, 2),
        "service_start_minute": round(arrival_t, 2),
        "service_end_minute": round(current_t, 2),
        "priority": priority,
        "channel": channel
    })

def run_one_day(cfg: SimConfig, arrival_rates_csv: str, scenario: dict) -> pd.DataFrame:
    env = simpy.Environment()
    res = StageResources(
        env, cfg,
        reg_peak_add=scenario.get("reg_peak_add", 0),
        svc_peak_add=scenario.get("svc_peak_add", 0),
        pay_peak_add=scenario.get("pay_peak_add", 0),
    )

    hour_rates = arrival_stream_for_day(arrival_rates_csv, cfg)
    results = []

    # build arrivals schedule: for each hour, create N arrivals uniformly within the hour
    cust_counter = 0
    for hour in range(cfg.day_start_hour, cfg.day_end_hour):
        rate = hour_rates.get(hour, 0.0)
        n = arrivals_for_hour(rate)
        for _ in range(n):
            minute_in_hour = random.randint(0, 59)
            t = (hour - cfg.day_start_hour) * 60 + minute_in_hour
            priority = random.choices(["normal", "urgent"], weights=[92, 8], k=1)[0]
            channel  = random.choices(["walk_in", "appointment"], weights=[80, 20], k=1)[0]
            cust_id = f"C{cust_counter:06d}"
            cust_counter += 1
            env.process(_spawn_at(env, t, customer, cfg, res, cust_id, priority, channel, results))

    # run the day
    sim_duration = (cfg.day_end_hour - cfg.day_start_hour) * 60
    env.run(until=sim_duration)

    return pd.DataFrame(results)

def _spawn_at(env: simpy.Environment, t: int, fn, *args):
    # wait until t then call fn
    yield env.timeout(max(0, t - env.now))
    yield env.process(fn(env, *args))
def summarize(df: pd.DataFrame, cfg: SimConfig) -> dict:
    totals = df[df["stage"] == "__TOTAL__"].copy()
    if totals.empty:
        return {}

    waits = totals["wait_minutes"].astype(float)
    avg_wait = waits.mean()
    p95_wait = waits.quantile(0.95)

    # SLA: percent of customers whose TOTAL wait <= SLA threshold
    pass_rate = (waits <= cfg.sla_wait_minutes).mean()
    sla_percent = pass_rate * 100.0

    stage_avg = (
        df[df["stage"].isin(["Registration", "Service", "Payment"])]
        .groupby("stage")["wait_minutes"]
        .mean()
        .to_dict()
    )

    return {
        "avg_wait_total": round(float(avg_wait), 2),
        "p95_wait_total": round(float(p95_wait), 2),
        "sla_percent": round(float(sla_percent), 2),
        "avg_wait_registration": round(float(stage_avg.get("Registration", 0.0)), 2),
        "avg_wait_service": round(float(stage_avg.get("Service", 0.0)), 2),
        "avg_wait_payment": round(float(stage_avg.get("Payment", 0.0)), 2),
        "customers": int(len(totals))
    }
