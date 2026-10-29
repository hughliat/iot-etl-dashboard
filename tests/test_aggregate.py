"""聚合逻辑：小时 / 天粒度均值、最大、最小、标准差（REQ-04）。"""

from __future__ import annotations

import sqlite3
import statistics

import pytest

from src.etl.aggregate import aggregate_daily, aggregate_hourly
from src.generate.schema import create_schema


def _insert_dwd(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    """rows 为 (site_id, device_id, ts, temp, humidity, pressure, pm25)。"""
    conn.executemany(
        "INSERT INTO dwd_sensor_clean "
        "(site_id, device_id, ts, temp, humidity, pressure, pm25, quality_flag) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'OK')",
        rows,
    )
    conn.commit()


def test_aggregate_hourly_values():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    _insert_dwd(
        conn,
        [
            (1, 1, "2026-01-01 00:05:00", 10.0, 50.0, 1000.0, 20.0),
            (1, 1, "2026-01-01 00:25:00", 20.0, 50.0, 1000.0, 20.0),
            (1, 1, "2026-01-01 00:45:00", 30.0, 50.0, 1000.0, 20.0),
            (1, 1, "2026-01-01 01:05:00", 0.0, 40.0, 1000.0, 10.0),
            (1, 1, "2026-01-01 01:35:00", 4.0, 40.0, 1000.0, 10.0),
        ],
    )
    n = aggregate_hourly(conn)
    assert n == 2

    r1 = conn.execute(
        "SELECT temp_mean, temp_max, temp_min, temp_std "
        "FROM dws_sensor_hourly WHERE period_start = '2026-01-01 00:00:00'"
    ).fetchone()
    assert r1[0] == pytest.approx(20.0)
    assert r1[1] == pytest.approx(30.0)
    assert r1[2] == pytest.approx(10.0)
    assert r1[3] == pytest.approx(statistics.stdev([10.0, 20.0, 30.0]))

    r2 = conn.execute(
        "SELECT temp_mean, temp_std "
        "FROM dws_sensor_hourly WHERE period_start = '2026-01-01 01:00:00'"
    ).fetchone()
    assert r2[0] == pytest.approx(2.0)
    assert r2[1] == pytest.approx(statistics.stdev([0.0, 4.0]))


def test_aggregate_ignores_null():
    """NULL 值不参与聚合（均值 / 标准差只统计非空值）。"""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    _insert_dwd(
        conn,
        [
            (1, 1, "2026-01-01 00:05:00", 10.0, 50.0, 1000.0, 20.0),
            (1, 1, "2026-01-01 00:25:00", None, 50.0, 1000.0, 20.0),
            (1, 1, "2026-01-01 00:45:00", 30.0, 50.0, 1000.0, 20.0),
        ],
    )
    aggregate_hourly(conn)
    r = conn.execute(
        "SELECT temp_mean, temp_std FROM dws_sensor_hourly WHERE period_start = '2026-01-01 00:00:00'"
    ).fetchone()
    assert r[0] == pytest.approx(20.0)
    assert r[1] == pytest.approx(statistics.stdev([10.0, 30.0]))


def test_aggregate_std_null_single_value():
    """单值分组的样本标准差为 NULL。"""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    _insert_dwd(conn, [(1, 1, "2026-01-01 00:05:00", 10.0, 50.0, 1000.0, 20.0)])
    aggregate_hourly(conn)
    r = conn.execute(
        "SELECT temp_std FROM dws_sensor_hourly WHERE period_start = '2026-01-01 00:00:00'"
    ).fetchone()
    assert r[0] is None


def test_aggregate_daily():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    _insert_dwd(
        conn,
        [
            (1, 1, "2026-01-01 00:00:00", 10.0, 50.0, 1000.0, 20.0),
            (1, 1, "2026-01-01 12:00:00", 30.0, 50.0, 1000.0, 20.0),
            (1, 1, "2026-01-02 00:00:00", 5.0, 50.0, 1000.0, 20.0),
        ],
    )
    n = aggregate_daily(conn)
    assert n == 2
    r = conn.execute(
        "SELECT temp_mean, temp_max, temp_min FROM dws_sensor_daily "
        "WHERE period_start = '2026-01-01'"
    ).fetchone()
    assert r[0] == pytest.approx(20.0)
    assert r[1] == pytest.approx(30.0)
    assert r[2] == pytest.approx(10.0)
