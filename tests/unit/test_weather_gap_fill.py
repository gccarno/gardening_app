"""WeatherLog gap-fill: Tomorrow.io only returns yesterday, so a missed nightly
run used to leave a permanent hole in the 7-day window (2026-08-01). The
Open-Meteo archive covers the whole window and can close it.
"""
from datetime import date, timedelta

import pytest
import requests as http

from apps.backend.app.db.models import WeatherLog
from apps.backend.app.routers import weather as weather_mod


def _row(day, rainfall=0.0):
    """(date, rainfall_in, temp_high_f, temp_low_f, humidity_pct, et0_mm)"""
    return (day, rainfall, 80.0, 60.0, 70.0, 4.0)


@pytest.fixture
def yesterday_only(monkeypatch):
    """Tomorrow.io behaving normally: yesterday and nothing else."""
    yesterday = date.today() - timedelta(days=1)
    monkeypatch.setattr(weather_mod, '_tomorrow_io_history_rows',
                        lambda garden: [_row(yesterday)])
    return yesterday


def test_fills_a_hole_left_by_a_missed_night(db, garden, yesterday_only, monkeypatch):
    hole = date.today() - timedelta(days=3)
    # Every window day except the hole (and yesterday) is already stored.
    for i in range(2, 8):
        day = date.today() - timedelta(days=i)
        if day != hole:
            db.add(WeatherLog(garden_id=garden.id, date=day, rainfall_in=0.0, source='api'))
    db.flush()

    requested = {}

    def fake_archive(g, start, end):
        requested['range'] = (start, end)
        return [_row(hole, rainfall=0.5)]

    monkeypatch.setattr(weather_mod, '_open_meteo_archive_rows', fake_archive)

    weather_mod._fetch_weather_for_garden(db, garden.id)

    assert requested['range'] == (hole, hole), 'should ask only for the missing span'
    filled = db.query(WeatherLog).filter_by(garden_id=garden.id, date=hole).one()
    assert filled.rainfall_in == 0.5


def test_no_archive_call_when_the_window_is_complete(db, garden, yesterday_only, monkeypatch):
    for i in range(2, 8):
        db.add(WeatherLog(garden_id=garden.id, date=date.today() - timedelta(days=i),
                          rainfall_in=0.0, source='api'))
    db.flush()

    def boom(*a):
        pytest.fail('archive must not be called when nothing is missing')

    monkeypatch.setattr(weather_mod, '_open_meteo_archive_rows', boom)
    weather_mod._fetch_weather_for_garden(db, garden.id)


def test_gap_fill_failure_does_not_lose_yesterday(db, garden, yesterday_only, monkeypatch):
    """The archive is a bonus; yesterday's data is the point of the run."""
    def boom(*a):
        raise http.exceptions.RequestException('archive down')

    monkeypatch.setattr(weather_mod, '_open_meteo_archive_rows', boom)

    weather_mod._fetch_weather_for_garden(db, garden.id)  # must not raise

    assert db.query(WeatherLog).filter_by(garden_id=garden.id, date=yesterday_only).one()


def test_gap_fill_preserves_a_manual_rain_log(db, garden, yesterday_only, monkeypatch):
    """A hand-entered reading is real data — it is not a gap to overwrite."""
    manual_day = date.today() - timedelta(days=3)
    db.add(WeatherLog(garden_id=garden.id, date=manual_day, rainfall_in=1.25, source='manual'))
    db.flush()

    monkeypatch.setattr(weather_mod, '_open_meteo_archive_rows',
                        lambda g, s, e: [_row(d, rainfall=0.0) for d in
                                         (s + timedelta(days=i) for i in range((e - s).days + 1))])

    weather_mod._fetch_weather_for_garden(db, garden.id)

    kept = db.query(WeatherLog).filter_by(garden_id=garden.id, date=manual_day).one()
    assert (kept.rainfall_in, kept.source) == (1.25, 'manual')


def test_archive_is_the_whole_source_when_tomorrow_io_is_unavailable(db, garden, monkeypatch):
    monkeypatch.setattr(weather_mod, '_tomorrow_io_history_rows', lambda garden: None)
    window = [date.today() - timedelta(days=i) for i in range(1, 8)]
    monkeypatch.setattr(weather_mod, '_open_meteo_archive_rows',
                        lambda g, s, e: [_row(d) for d in window])

    assert weather_mod._fetch_weather_for_garden(db, garden.id) == 7


def test_archive_failure_still_raises_when_it_is_the_only_source(db, garden, monkeypatch):
    monkeypatch.setattr(weather_mod, '_tomorrow_io_history_rows', lambda garden: None)

    def boom(*a):
        raise http.exceptions.RequestException('archive down')

    monkeypatch.setattr(weather_mod, '_open_meteo_archive_rows', boom)

    with pytest.raises(http.exceptions.RequestException):
        weather_mod._fetch_weather_for_garden(db, garden.id)
