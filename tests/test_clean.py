"""清洗逻辑：去重、异常值置空标记、缺失值标记（REQ-03）。"""

from __future__ import annotations

import sqlite3

from src.etl.clean import clean_ods_to_dwd
from src.generate.schema import create_schema


def _insert_raw(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    conn.executemany(
        "INSERT INTO ods_sensor_raw (site_id, device_id, ts, temp, humidity, pressure, pm25) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def test_clean_dedup_outlier_missing():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    _insert_raw(
        conn,
        [
            (1, 1, "2026-01-01 00:00:00", 20.0, 50.0, 1000.0, 30.0),   # 保留（首条）
            (1, 1, "2026-01-01 00:00:00", 21.0, 51.0, 1001.0, 31.0),   # 重复
            (1, 1, "2026-01-01 00:01:00", 999.0, 50.0, 1000.0, 30.0),  # 越界温度
            (1, 1, "2026-01-01 00:02:00", 20.0, None, 1000.0, 30.0),   # 缺失湿度
            (1, 2, "2026-01-01 00:00:00", 20.0, 50.0, 1000.0, 30.0),   # 干净
        ],
    )

    report = clean_ods_to_dwd(conn)

    assert report.before_rows == 5
    assert report.after_rows == 4
    assert report.duplicates_removed == 1
    assert report.outlier_count == 1
    assert report.missing_count == 1

    # 越界值置 NULL 并标记 OUTLIER
    r_out = conn.execute(
        "SELECT temp, quality_flag FROM dwd_sensor_clean WHERE ts = '2026-01-01 00:01:00'"
    ).fetchone()
    assert r_out == (None, "OUTLIER")

    # 缺失值标记 MISSING
    r_miss = conn.execute(
        "SELECT humidity, quality_flag FROM dwd_sensor_clean WHERE ts = '2026-01-01 00:02:00'"
    ).fetchone()
    assert r_miss == (None, "MISSING")

    # 干净行标记 OK
    r_ok = conn.execute(
        "SELECT quality_flag FROM dwd_sensor_clean WHERE ts = '2026-01-01 00:00:00' AND device_id = 2"
    ).fetchone()
    assert r_ok == ("OK",)


def test_clean_no_duplicate_keys():
    """DWD 无重复业务主键。"""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    _insert_raw(
        conn,
        [
            (1, 1, "2026-01-01 00:00:00", 20.0, 50.0, 1000.0, 30.0),
            (1, 1, "2026-01-01 00:00:00", 21.0, 51.0, 1001.0, 31.0),
            (1, 1, "2026-01-01 00:00:00", 22.0, 52.0, 1002.0, 32.0),
        ],
    )
    clean_ods_to_dwd(conn)
    dup = conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT site_id, device_id, ts FROM dwd_sensor_clean "
        "  GROUP BY site_id, device_id, ts HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    assert dup == 0
    assert conn.execute("SELECT COUNT(*) FROM dwd_sensor_clean").fetchone()[0] == 1


def test_clean_boundary_values_kept():
    """边界值（等于上下限）不算越界。"""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    _insert_raw(
        conn,
        [
            (1, 1, "2026-01-01 00:00:00", -30.0, 0.0, 870.0, 0.0),
            (1, 1, "2026-01-01 00:01:00", 50.0, 100.0, 1085.0, 500.0),
        ],
    )
    report = clean_ods_to_dwd(conn)
    assert report.outlier_count == 0
    assert report.missing_count == 0
    v = conn.execute(
        "SELECT temp FROM dwd_sensor_clean WHERE ts = '2026-01-01 00:00:00'"
    ).fetchone()[0]
    assert v == -30.0
