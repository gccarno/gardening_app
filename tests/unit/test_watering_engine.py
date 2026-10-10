"""Watering engine pure-logic tests (no network)."""
from datetime import date, timedelta

from apps.ml_service.app.watering_engine import (
    calculate_deficit,
    days_since_last_watered,
    estimate_et0_from_temp,
    get_plant_kc,
    get_urgency_label,
    get_watering_recommendations,
    score_urgency,
)


def test_kc_lookup_by_name():
    assert get_plant_kc('Roma Tomato')['kc'] == 1.15
    assert get_plant_kc('Sweet Basil')['mm_day'] == 4.0


def test_kc_fallback_to_water_need():
    assert get_plant_kc('Unknownius plantus', 'High')['kc'] == 1.10
    assert get_plant_kc('Unknownius plantus', 'Low')['drought'] == 'high'


def test_kc_default():
    assert get_plant_kc('Unknownius plantus') == {'kc': 0.85, 'mm_day': 4.0, 'drought': 'medium'}


def test_et0_missing_temps_fallback():
    assert estimate_et0_from_temp(None, None) == 3.5


def test_et0_hotter_days_evaporate_more():
    cool = estimate_et0_from_temp(60, 45)
    hot = estimate_et0_from_temp(95, 70)
    assert hot > cool > 0


def test_urgency_labels():
    assert get_urgency_label(0) == 'ok'
    assert get_urgency_label(20) == 'consider'
    assert get_urgency_label(50) == 'water_today'
    assert get_urgency_label(75) == 'urgent'


def test_rain_forecast_lowers_urgency():
    kc = {'kc': 1.0, 'mm_day': 5.0, 'drought': 'medium'}
    dry = score_urgency(15.0, kc, {'temp_max_c': 25, 'precip_prob': 0, 'precip_mm': 0, 'wind_kmh': 5})
    rainy = score_urgency(15.0, kc, {'temp_max_c': 25, 'precip_prob': 90, 'precip_mm': 10, 'wind_kmh': 5})
    assert rainy < dry


def test_heat_raises_urgency():
    kc = {'kc': 1.0, 'mm_day': 5.0, 'drought': 'medium'}
    mild = score_urgency(10.0, kc, {'temp_max_c': 20, 'precip_prob': 0, 'precip_mm': 0, 'wind_kmh': 5})
    scorching = score_urgency(10.0, kc, {'temp_max_c': 38, 'precip_prob': 0, 'precip_mm': 0, 'wind_kmh': 5})
    assert scorching > mild


def test_days_since_last_watered(db, plant_in_bed, bed):
    assert days_since_last_watered(bed) == 999
    bed.bed_plants[0].last_watered = date.today() - timedelta(days=3)
    assert days_since_last_watered(bed) == 3


def test_deficit_zero_when_just_watered(db, plant_in_bed, bed):
    bed.bed_plants[0].last_watered = date.today()
    assert calculate_deficit(bed, {'kc': 1.0}, []) == 0.0


def test_deficit_accumulates_dry_days(db, plant_in_bed, bed):
    bed.bed_plants[0].last_watered = date.today() - timedelta(days=5)
    deficit = calculate_deficit(bed, {'kc': 1.0}, [])
    # 5 dry days at default ET0 3.5 mm/day
    assert deficit == 17.5


def _logs(garden, days, et0, hi=80.0, lo=60.0):
    from types import SimpleNamespace
    return [SimpleNamespace(date=date.today() - timedelta(days=i), et0_mm=et0,
                            temp_high_f=hi, temp_low_f=lo, rainfall_in=0.0)
            for i in range(1, days + 1)]


def test_deficit_uses_the_providers_stored_et0(db, garden, plant_in_bed, bed):
    bed.bed_plants[0].last_watered = date.today() - timedelta(days=3)
    # Hargreaves from these temps would be ~2-3 mm/day; stored says 5.
    deficit = calculate_deficit(bed, {'kc': 1.0}, _logs(garden, 3, et0=5.0))
    assert deficit == 15.0


def test_deficit_falls_back_to_hargreaves_without_stored_et0(db, garden, plant_in_bed, bed):
    bed.bed_plants[0].last_watered = date.today() - timedelta(days=3)
    logs = _logs(garden, 3, et0=None)
    deficit = calculate_deficit(bed, {'kc': 1.0}, logs)
    assert deficit == round(3 * estimate_et0_from_temp(80.0, 60.0), 1)


def test_a_stored_et0_of_zero_is_honoured_not_treated_as_missing(db, garden, plant_in_bed, bed):
    """A cold, still, overcast day can legitimately have ~0 ET0."""
    bed.bed_plants[0].last_watered = date.today() - timedelta(days=2)
    assert calculate_deficit(bed, {'kc': 1.0}, _logs(garden, 2, et0=0.0)) == 0.0


def test_recommendations_for_garden(db, garden, plant_in_bed, bed):
    bed.bed_plants[0].last_watered = date.today() - timedelta(days=6)
    recs = get_watering_recommendations(garden, [], None)
    assert len(recs) == 1
    rec = recs[0]
    assert rec['bed_id'] == bed.id
    assert rec['label'] in ('ok', 'consider', 'water_today', 'urgent')
    assert rec['plants'] == ['Tomato']
    assert rec['days_since_watered'] == 6


def test_model_is_shadow_by_default(db, garden, plant_in_bed, bed, monkeypatch):
    from apps.ml_service.app import watering_engine
    monkeypatch.setattr(watering_engine, 'predict_water_mm', lambda feats: 30.0)
    bed.bed_plants[0].last_watered = date.today() - timedelta(days=6)

    monkeypatch.delenv('WATERING_MODEL_SERVE', raising=False)
    shadow = get_watering_recommendations(garden, [], None)[0]
    assert shadow['model_used'] is False
    assert shadow['predicted_mm'] == 30.0  # still logged for the snapshot

    monkeypatch.setenv('WATERING_MODEL_SERVE', '1')
    served = get_watering_recommendations(garden, [], None)[0]
    assert served['model_used'] is True
    assert served['urgency_score'] == 100


def test_model_sees_the_same_capped_days_since_watered_as_the_snapshot(db, garden, plant_in_bed, bed,
                                                                      monkeypatch):
    from apps.ml_service.app import watering_engine
    seen = {}
    monkeypatch.setattr(watering_engine, 'predict_water_mm',
                        lambda feats: seen.update(feats) or 1.0)
    rec = get_watering_recommendations(garden, [], None)[0]  # never watered -> 999 uncapped
    assert seen['days_since_watered'] == 99
    assert rec['days_since_watered'] == 99


def test_empty_beds_skipped(db, garden, bed):
    assert get_watering_recommendations(garden, [], None) == []
