"""Bucket model (FAO-56 soil water balance) prototype: the physical properties it
must have, not exact numbers."""
import pytest

from ml.experiments.water_balance import (
    Bed, available_water, depletion_fraction, from_snapshot, recommend,
    root_depth_m, simulate, step,
)

DRY_DAY = {'et0_mm': 5.0, 'rain_mm': 0.0}


def _loam(kc=1.0, seedling_frac=0.0):
    return Bed.from_soil(kc=kc, seedling_frac=seedling_frac)


def test_sand_holds_less_water_than_loam_and_compost_adds_some():
    assert available_water(90, 5) < available_water(None, None)
    assert available_water(None, None, compost_pct=50) > available_water(None, None)


def test_seedlings_root_shallower_and_a_shallow_bed_caps_roots():
    assert root_depth_m(1.0) < root_depth_m(0.0)
    assert root_depth_m(0.0, bed_depth_ft=0.5) == pytest.approx(0.1524)


def test_dry_days_deplete_by_kc_times_et0_before_stress():
    bed = _loam(kc=0.8)
    assert step(0.0, bed, et0_mm=5.0, rain_mm=0.0) == pytest.approx(4.0)


def test_rain_beyond_field_capacity_drains_away():
    bed = _loam()
    assert step(5.0, bed, et0_mm=1.0, rain_mm=50.0) == 0.0


def test_stressed_plants_deplete_more_slowly():
    bed = _loam()
    raw = depletion_fraction(5.0) * bed.taw_mm
    fresh = step(0.0, bed, 5.0, 0.0)
    stressed = step(raw + 0.9 * (bed.taw_mm - raw), bed, 5.0, 0.0) - (raw + 0.9 * (bed.taw_mm - raw))
    assert stressed < fresh


def test_depletion_never_exceeds_the_bucket():
    bed = _loam()
    assert simulate(bed, [DRY_DAY] * 200) <= bed.taw_mm


def test_a_watering_refills_the_bucket():
    bed = _loam()
    dr = simulate(bed, [DRY_DAY] * 5 + [{'et0_mm': 5.0, 'rain_mm': 0.0, 'watered': True}])
    assert dr == 0.0


def test_sandy_bed_needs_water_before_a_clay_bed():
    sandy = Bed.from_soil(kc=1.0, sand_pct=90, clay_pct=5)
    clay = Bed.from_soil(kc=1.0, sand_pct=10, clay_pct=60)
    days_until = {}
    for name, bed in (('sandy', sandy), ('clay', clay)):
        dr = 0.0
        for day in range(1, 30):
            dr = step(dr, bed, 5.0, 0.0)
            if recommend(dr, bed, 5.0)['water_today']:
                days_until[name] = day
                break
    assert days_until['sandy'] < days_until['clay']


def test_score_is_50_at_the_stress_threshold():
    bed = _loam()
    raw = depletion_fraction(bed.kc * 3.0) * bed.taw_mm
    rec = recommend(raw - bed.kc * 3.0, bed, et0_today_mm=3.0)
    assert rec['score'] == 50 and rec['water_today'] is True


def test_waits_for_heavy_forecast_rain_unless_badly_dry():
    bed = _loam()
    raw = depletion_fraction(bed.kc * 3.0) * bed.taw_mm
    just_dry = recommend(raw, bed, 3.0, forecast_rain_d1_d2_mm=60.0)
    assert just_dry['water_today'] is False and just_dry['deferred_for_rain'] is True
    assert just_dry['score'] < 50

    parched = recommend(bed.taw_mm * 0.9, bed, 3.0, forecast_rain_d1_d2_mm=60.0)
    assert parched['water_today'] is True


def test_snapshot_storm_is_averaged_over_when_it_could_have_fallen():
    base = {'kc_avg': 1.0, 'days_since_watered': 7, 'et0_7d_mm': 14.0,
            'sand_pct': None, 'clay_pct': None, 'seedling_frac': 0.0}
    dry = from_snapshot({**base, 'rain_7d_mm': 0.0})
    stormy = from_snapshot({**base, 'rain_7d_mm': 20.0})

    # 2 mm/day ET for 7 days, then today's 2 mm.
    assert dry['depletion_mm'] == pytest.approx(16.0)
    # A 20 mm storm on day k refills the bucket, leaving 2*(6-k) mm by tonight;
    # averaged over k = 0..6 that is 6 mm, plus today's 2 mm.
    assert stormy['depletion_mm'] == pytest.approx(8.0)
