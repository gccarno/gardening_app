"""Nightly forecast archive: both providers are recorded per lead day so forecast
accuracy can later be scored against WeatherLog."""
from datetime import date, timedelta

from apps.backend.app.db.models import WeatherForecastArchive, WeatherLog
from apps.backend.app.routers import weather as weather_mod
from apps.backend.app.services import forecast_archive as fa


def _day(offset, **kw):
    base = {'date': (date.today() + timedelta(days=offset)).isoformat(),
            'precip_mm': 1.0, 'precip_prob': 40, 'temp_max_c': 25.0, 'temp_min_c': 12.0,
            'wind_kmh': 10.0, 'et0_mm': 3.5}
    return {**base, **kw}


def _rows(db, garden, provider=None):
    q = db.query(WeatherForecastArchive).filter_by(garden_id=garden.id)
    return (q.filter_by(provider=provider) if provider else q).order_by(
        WeatherForecastArchive.target_date).all()


def test_archives_each_provider_with_lead_days(db, garden, monkeypatch):
    monkeypatch.setitem(fa._PROVIDERS, 'open-meteo', lambda lat, lon: [_day(0), _day(1), _day(2)])
    monkeypatch.setitem(fa._PROVIDERS, 'tomorrow-io', lambda lat, lon: [_day(0, precip_mm=9.0), _day(1)])

    assert fa.archive_forecasts(db, garden.id, 1.0, 2.0) == 5

    om = _rows(db, garden, 'open-meteo')
    assert [r.lead_days for r in om] == [0, 1, 2]
    assert [r.fetched_date for r in om] == [date.today()] * 3
    assert _rows(db, garden, 'tomorrow-io')[0].precip_mm == 9.0


def test_rerun_same_day_replaces_rather_than_duplicates(db, garden, monkeypatch):
    monkeypatch.setitem(fa._PROVIDERS, 'tomorrow-io', lambda lat, lon: [])
    monkeypatch.setitem(fa._PROVIDERS, 'open-meteo', lambda lat, lon: [_day(0, precip_mm=1.0)])
    fa.archive_forecasts(db, garden.id, 1.0, 2.0)

    monkeypatch.setitem(fa._PROVIDERS, 'open-meteo', lambda lat, lon: [_day(0, precip_mm=7.0)])
    fa.archive_forecasts(db, garden.id, 1.0, 2.0)

    rows = _rows(db, garden)
    assert len(rows) == 1 and rows[0].precip_mm == 7.0


def test_one_provider_failing_does_not_block_the_other(db, garden, monkeypatch):
    def boom(lat, lon):
        raise RuntimeError('provider down')

    monkeypatch.setitem(fa._PROVIDERS, 'tomorrow-io', boom)
    monkeypatch.setitem(fa._PROVIDERS, 'open-meteo', lambda lat, lon: [_day(1)])

    assert fa.archive_forecasts(db, garden.id, 1.0, 2.0) == 1
    assert [r.provider for r in _rows(db, garden)] == ['open-meteo']


def test_past_dates_are_skipped(db, garden, monkeypatch):
    monkeypatch.setitem(fa._PROVIDERS, 'tomorrow-io', lambda lat, lon: [])
    monkeypatch.setitem(fa._PROVIDERS, 'open-meteo', lambda lat, lon: [_day(-1), _day(0)])

    fa.archive_forecasts(db, garden.id, 1.0, 2.0)

    assert [r.lead_days for r in _rows(db, garden)] == [0]


def test_weather_log_records_which_provider_supplied_each_row(db, garden, monkeypatch):
    yesterday = date.today() - timedelta(days=1)
    hole = date.today() - timedelta(days=3)
    monkeypatch.setattr(weather_mod, '_tomorrow_io_history_rows',
                        lambda g: [(yesterday, 0.0, 80.0, 60.0, 70.0, 4.0)])
    monkeypatch.setattr(weather_mod, '_open_meteo_archive_rows',
                        lambda g, s, e: [(hole, 0.5, 80.0, 60.0, 70.0, 4.0)])
    for i in (2, 4, 5, 6, 7):
        db.add(WeatherLog(garden_id=garden.id, date=date.today() - timedelta(days=i),
                          rainfall_in=0.0, source='api'))
    db.flush()

    weather_mod._fetch_weather_for_garden(db, garden.id)

    src = {lg.date: lg.source for lg in db.query(WeatherLog).filter_by(garden_id=garden.id)}
    assert src[yesterday] == 'tomorrow-io'
    assert src[hole] == 'open-meteo'
