"""SQL 优化对比：朴素 SCAN vs 索引 SEARCH（REQ-07）。"""

from __future__ import annotations

import sqlite3

from src.generate.schema import create_schema
from src.optimize.benchmark import run_benchmark


def _insert_dwd(conn: sqlite3.Connection) -> None:
    rows = [
        (1, 1, "2026-01-01 00:00:00", 20.0, 50.0, 1000.0, 30.0),
        (1, 1, "2026-01-01 01:00:00", 20.0, 50.0, 1000.0, 40.0),
        (1, 2, "2026-01-02 00:00:00", 20.0, 50.0, 1000.0, 50.0),
        (2, 1, "2026-01-03 00:00:00", 20.0, 50.0, 1000.0, 60.0),
    ]
    conn.executemany(
        "INSERT INTO dwd_sensor_clean "
        "(site_id, device_id, ts, temp, humidity, pressure, pm25, quality_flag) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'OK')",
        rows,
    )
    conn.commit()


def test_benchmark_scan_to_search():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    _insert_dwd(conn)

    report = run_benchmark(conn, rounds=3)

    baseline_explain = "\n".join(report["baseline"].explain)
    optimized_explain = "\n".join(report["optimized"].explain)

    assert report["baseline"].name == "baseline"
    assert report["optimized"].name == "optimized"
    # 朴素查询强制全表扫描
    assert "SCAN" in baseline_explain
    # 优化查询走复合索引范围扫描
    assert "SEARCH" in optimized_explain
    assert "idx_dwd_site_ts" in optimized_explain

    assert len(report["baseline"].times) == 3
    assert len(report["optimized"].times) == 3
    assert report["baseline"].mean_time >= 0
    assert report["optimized"].mean_time >= 0
    assert report["speedup"] >= 0


def test_benchmark_query_returns_rows():
    """典型场景查询能返回 PM2.5 每小时均值结果。"""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    _insert_dwd(conn)
    report = run_benchmark(conn, rounds=2)
    # 复用优化查询验证有实际结果行
    rows = conn.execute(report["optimized"].sql, (1, "2020-01-01 00:00:00")).fetchall()
    assert len(rows) > 0
    # 结果两列：小时、PM2.5 均值
    assert len(rows[0]) == 2
