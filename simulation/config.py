from dataclasses import dataclass

@dataclass
class SimConfig:
    # day window (minutes) from 08:00 to 17:00 => 540 mins
    day_start_hour: int = 8
    day_end_hour: int = 17
    sla_wait_minutes: int = 20

    # baseline staff
    reg_staff = 2
    svc_staff = 5
    pay_staff = 2
    # peak staffing window
    peak_start_hour: int = 10
    peak_end_hour: int = 12  # inclusive end hour in logic below

    # service times (minutes) - mean/stdev
    reg_mean: float = 6
    reg_std: float = 2

    svc_mean: float = 12
    svc_std: float = 4

    pay_mean: float = 4
    pay_std: float = 2

    # optional cost per staff-hour
    cost_per_staff_hour: float = 1.0
