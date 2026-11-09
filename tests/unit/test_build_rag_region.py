"""Region filtering for growing-guide retrieval.

A garden's region should drop *other* regions' Black & Decker books, not the
region-agnostic chunks (General books, TAMU guides). The old strict equality
left an IL garden with only its 531 'Lower Midwest' chunks.
"""
from sqlalchemy import column, select
from sqlalchemy.dialects import postgresql

from scripts.build_rag import _region_clause


def _sql(clause):
    stmt = select(column('id')).where(clause)
    return str(stmt.compile(dialect=postgresql.dialect(),
                            compile_kwargs={'literal_binds': True}))


def test_keeps_own_region_general_and_unlabelled_chunks():
    sql = _sql(_region_clause(column('region'), 'Lower Midwest'))
    assert "region = 'Lower Midwest'" in sql
    assert 'region IS NULL' in sql
    # every other regional book is excluded...
    for other in ('Northeast', 'Lower South', 'Upper Midwest', 'Western Plains'):
        assert f"'{other}'" in sql
    # ...but region-agnostic labels are never in the exclusion list
    assert "'General'" not in sql
    assert 'Texas' not in sql


def test_own_region_is_not_in_the_exclusion_list():
    sql = _sql(_region_clause(column('region'), 'Lower Midwest'))
    not_in = sql.split('NOT IN', 1)[1]
    assert "'Lower Midwest'" not in not_in
