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


def test_recommendations_for_garden(db, garden, plant_in_bed, bed):
    bed.bed_plants[0].last_watered = date.today() - timedelta(days=6)
    recs = get_watering_recommendations(garden, [], None)
    assert len(recs) == 1
    rec = recs[0]
    assert rec['bed_id'] == bed.id
    assert rec['label'] in ('ok', 'consider', 'water_today', 'urgent')
    assert rec['plants'] == ['Tomato']
    assert rec['days_since_watered'] == 6


def test_empty_beds_skipped(db, garden, bed):
    assert get_watering_recommendations(garden, [], None) == []
