"""
Per-bed soil water balance ("bucket model"), FAO-56 single crop coefficient.

PROTOTYPE: evaluated offline (ml/evaluation/watering_real_eval.py), not served.
See ml/docs/WATERING_MODEL.md, "Bucket model".

The bed's root zone is a bucket. Depletion Dr (mm below field capacity) rises
with crop evapotranspiration and falls with effective rain and watering; water
above field capacity drains away (Dr floors at 0). The bucket holds TAW mm of
plant-available water. Plants stop drinking freely once Dr passes RAW = p*TAW;
that is the point to water.

What the rule engine lacks and this adds:
  * soil texture sets how much water the bed can hold (sand drains, clay holds);
  * roots deepen as plants establish, so seedlings dry out faster;
  * stressed plants transpire less (Ks), so depletion slows as soil dries;
  * a threshold in mm of this bed's own capacity instead of "3 days of mm_day".

Every constant below is a textbook default (FAO Irrigation and Drainage Paper
56, Table 19 for available water by texture, Table 22 for depletion fraction),
not fitted. Fitting them needs ground truth: the soil moisture check-ins.
"""
from dataclasses import dataclass

# Effective-rain interception, shared with the rule engine so the two disagree
# only where the physics differs.
INTERCEPTION_MM = 2.0

# Available water (field capacity minus wilting point), m3/m3, FAO-56 Table 19
# mid-range: sand 0.05-0.11, loam 0.13-0.18, clay 0.12-0.20.
AW_SAND, AW_CLAY, AW_LOAM = 0.08, 0.16, 0.15
AW_COMPOST_BONUS = 0.05   # organic matter raises holding capacity
AW_MIN, AW_MAX = 0.05, 0.22

ROOT_SEEDLING_M, ROOT_ESTABLISHED_M = 0.15, 0.40
P_BASE = 0.50             # depletion fraction for most vegetables, FAO-56 Table 22
DEFAULT_ET0_MM = 3.5      # same no-data fallback as the rule engine


def effective_rain(rain_mm: float | None) -> float:
    return max(0.0, (rain_mm or 0.0) - INTERCEPTION_MM)


def available_water(sand_pct: float | None, clay_pct: float | None,
                    compost_pct: float | None = None) -> float:
    """m3/m3 of plant-available water for the bed's soil mix. Missing texture
    means loam, which is what most raised-bed mixes approximate."""
    if sand_pct is None and clay_pct is None:
        aw = AW_LOAM
    else:
        s = min(max((sand_pct or 0) / 100, 0), 1)
        c = min(max((clay_pct or 0) / 100, 0), 1 - s)
        aw = AW_SAND * s + AW_CLAY * c + AW_LOAM * (1 - s - c)
    aw += AW_COMPOST_BONUS * min(max((compost_pct or 0) / 100, 0), 1)
    return min(max(aw, AW_MIN), AW_MAX)


def root_depth_m(seedling_frac: float | None, bed_depth_ft: float | None = None) -> float:
    """Seedlings root shallow; established plants deeper. A shallow raised bed
    caps the root zone. Unknown stage is treated as half established."""
    sf = 0.5 if seedling_frac is None else min(max(seedling_frac, 0), 1)
    zr = ROOT_SEEDLING_M * sf + ROOT_ESTABLISHED_M * (1 - sf)
    if bed_depth_ft:
        zr = min(zr, bed_depth_ft * 0.3048)
    return max(zr, 0.05)


def depletion_fraction(etc_mm: float) -> float:
    """FAO-56 eq. 85 adjustment: plants tolerate less depletion on hot days."""
    return min(max(P_BASE + 0.04 * (5.0 - etc_mm), 0.1), 0.8)


@dataclass(frozen=True)
class Bed:
    kc: float
    taw_mm: float   # total available water in the root zone

    @classmethod
    def from_soil(cls, kc: float, sand_pct=None, clay_pct=None, compost_pct=None,
                  seedling_frac=None, bed_depth_ft=None) -> 'Bed':
        taw = 1000 * available_water(sand_pct, clay_pct, compost_pct) * root_depth_m(seedling_frac, bed_depth_ft)
        return cls(kc=kc, taw_mm=taw)


def step(dr: float, bed: Bed, et0_mm: float | None, rain_mm: float | None,
         watered: bool = False) -> float:
    """Advance depletion by one day. A gardener's watering of unknown volume is
    assumed to refill the root zone (the FAO convention for irrigation events);
    rain is applied through effective_rain, so rain-credited watering events
    must NOT also be passed as watered=True or rain is counted twice."""
    et0 = DEFAULT_ET0_MM if et0_mm is None else et0_mm
    p = depletion_fraction(bed.kc * et0)
    raw = p * bed.taw_mm
    ks = 1.0 if dr <= raw else max(0.0, (bed.taw_mm - dr) / ((1 - p) * bed.taw_mm))
    dr = dr - effective_rain(rain_mm) + ks * bed.kc * et0
    if watered:
        dr = 0.0
    return min(max(dr, 0.0), bed.taw_mm)


def simulate(bed: Bed, days: list[dict], dr0: float = 0.0) -> float:
    """Run a sequence of daily inputs, oldest first. Each day is a dict with
    et0_mm, rain_mm and optional watered. Returns depletion at the end."""
    dr = dr0
    for d in days:
        dr = step(dr, bed, d.get('et0_mm'), d.get('rain_mm'), d.get('watered', False))
    return dr


def recommend(dr: float, bed: Bed, et0_today_mm: float | None = None,
              forecast_rain_today_mm: float | None = None,
              forecast_rain_d1_d2_mm: float | None = None) -> dict:
    """Today's call from the morning's depletion.

    score is on the rule engine's 0-100 scale so the 50/75 cutoffs keep their
    meaning: 50 means today's projected depletion reaches RAW (start of stress),
    100 means twice RAW.

    Defers to rain: if the next two days' effective rain would refill what is
    needed and the bed is not yet badly dry (under 75% of TAW), wait.
    """
    et0 = DEFAULT_ET0_MM if et0_today_mm is None else et0_today_mm
    p = depletion_fraction(bed.kc * et0)
    raw = p * bed.taw_mm
    projected = max(0.0, dr + bed.kc * et0 - effective_rain(forecast_rain_today_mm))
    score = round(min(100.0, projected / max(raw, 0.1) * 50.0))
    water_today = projected >= raw
    deferred = False
    if water_today and projected < 0.75 * bed.taw_mm \
            and effective_rain(forecast_rain_d1_d2_mm) >= projected:
        water_today, deferred = False, True
        score = min(score, 49)
    return {
        'depletion_mm': round(projected, 1),
        'taw_mm': round(bed.taw_mm, 1),
        'raw_mm': round(raw, 1),
        'score': score,
        'water_today': water_today,
        'deferred_for_rain': deferred,
        'amount_mm': round(projected, 1) if water_today else 0.0,   # refill to field capacity
    }


def from_snapshot(row: dict) -> dict:
    """Approximate the morning call from one MlWateringSnapshot row.

    Snapshots store 7-day sums, not daily series, so this spreads them evenly
    over the days since the last watering (at most 7) and starts the bucket full
    at that point, the same assumption the rule engine's deficit makes. Use it
    for comparison on history only; real replays should use daily WeatherLog
    rows, which are kept from 2026-10-09 on.
    """
    bed = Bed.from_soil(kc=row.get('kc_avg') or 0.85, sand_pct=row.get('sand_pct'),
                        clay_pct=row.get('clay_pct'), seedling_frac=row.get('seedling_frac'))
    n = min(row.get('days_since_watered') or 7, 7)
    et0_day = (row['et0_7d_mm'] / 7) if row.get('et0_7d_mm') is not None else DEFAULT_ET0_MM
    # The window's rain is treated as one event of unknown timing, and the
    # result is averaged over every day it could have fallen. Spreading it thin
    # would subtract the interception loss every day (a 20 mm storm becomes
    # ~6 mm); putting it on day one would always drain it from a bucket that
    # starts full, ignoring rain entirely.
    rain_in_window = (row.get('rain_7d_mm') or 0.0) * n / 7
    if n == 0:
        dr = 0.0
    else:
        dr = sum(
            simulate(bed, [{'et0_mm': et0_day, 'rain_mm': rain_in_window if i == k else 0.0}
                           for i in range(n)])
            for k in range(n)
        ) / n
    return recommend(dr, bed, et0_day, row.get('forecast_precip_mm_d0'),
                     row.get('forecast_precip_mm_d1_d2'))
