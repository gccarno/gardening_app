"""fetch_forecast_window: today's forecast and the next-two-days rainfall come
from one call, so the live API and the nightly snapshot see the same numbers.

Regression for the 2026-08-01 split — the request path skipped the d1_d2 fetch
and the feature encoder defaulted it to "no rain coming", so the API scored a
bed 100 (urgent) that the nightly snapshot, holding the real 96.2mm forecast,
scored 40.
"""
from apps.ml_service.app import watering_engine as we


def _days(*precip):
    return [{'date': f'2026-08-0{i + 1}', 'temp_max_c': 30.0, 'wind_kmh': 10.0,
             'precip_prob': 50, 'precip_mm': p} for i, p in enumerate(precip)]


def test_returns_today_and_the_next_two_days_rain(monkeypatch):
    monkeypatch.setattr(we, 'fetch_7day_forecast', lambda lat, lon: _days(0.0, 40.0, 56.2, 3.0))

    today, d1_d2 = we.fetch_forecast_window(40.0, -75.2)

    assert today['precip_mm'] == 0.0
    assert today['temp_max_c'] == 30.0
    assert d1_d2 == 96.2, 'day 3 onward must not be counted'


def test_falls_back_to_tomorrow_io_for_both_values(monkeypatch):
    monkeypatch.setattr(we, 'fetch_7day_forecast', lambda lat, lon: None)
    monkeypatch.setattr(we, '_tomorrow_io_daily', lambda lat, lon: _days(1.0, 2.0, 3.0))

    today, d1_d2 = we.fetch_forecast_window(40.0, -75.2)

    assert today['precip_mm'] == 1.0
    assert d1_d2 == 5.0


def test_returns_none_when_every_provider_is_down(monkeypatch):
    monkeypatch.setattr(we, 'fetch_7day_forecast', lambda lat, lon: None)
    monkeypatch.setattr(we, '_tomorrow_io_daily', lambda lat, lon: None)

    assert we.fetch_forecast_window(40.0, -75.2) == (None, None)


def test_short_forecast_yields_no_d1_d2(monkeypatch):
    """One day of forecast says nothing about tomorrow — None, not a false 0.0."""
    monkeypatch.setattr(we, 'fetch_7day_forecast', lambda lat, lon: _days(2.0))

    today, d1_d2 = we.fetch_forecast_window(40.0, -75.2)

    assert today['precip_mm'] == 2.0
    assert d1_d2 is None


def test_forecast_rain_reaches_the_model(db, garden, bed, plant_in_bed, monkeypatch):
    """The whole point: a wet two-day forecast must change the recommendation."""
    captured = []
    monkeypatch.setattr(we, 'predict_water_mm',
                        lambda row: captured.append(row) or 5.0)

    forecast_today = {'temp_max_c': 30.0, 'wind_kmh': 10.0, 'precip_prob': 3, 'precip_mm': 0.0}
    we.get_watering_recommendations(garden, [], forecast_today, 96.2)

    assert captured[0]['forecast_precip_mm_d1_d2'] == 96.2
