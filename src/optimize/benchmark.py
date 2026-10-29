"""SQL 优化对比：朴素查询 vs 索引 + 重写查询（REQ-07）。

典型场景：「某站点近 7 天 PM2.5 每小时均值」。
朴素 SQL 用 ``NOT INDEXED`` 强制全表 SCAN；优化 SQL 走复合索引 (site_id, ts)
范围扫描（SEARCH）。输出 EXPLAIN QUERY PLAN 与多轮计时均值。
"""

from __future__ import annotations

import sqlite3
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

SCENARIO = "某站点近 7 天 PM2.5 每小时均值"

_INDEX_NAME = "idx_dwd_site_ts"

_BASELINE_SQL = (
    "SELECT substr(ts, 1, 13) || ':00:00' AS hour, AVG(pm25) AS pm25_avg "
    "FROM dwd_sensor_clean NOT INDEXED "
    "WHERE site_id = ? AND ts >= ? "
    "GROUP BY hour ORDER BY hour"
)

_OPTIMIZED_SQL = (
    "SELECT substr(ts, 1, 13) || ':00:00' AS hour, AVG(pm25) AS pm25_avg "
    f"FROM dwd_sensor_clean INDEXED BY {_INDEX_NAME} "
    "WHERE site_id = ? AND ts >= ? "
    "GROUP BY hour ORDER BY hour"
)


@dataclass
class QueryResult:
    """单条查询的对比结果。"""

    name: str           # "baseline" | "optimized"
    sql: str
    explain: list[str]  # EXPLAIN QUERY PLAN 输出
    times: list[float]  # 多轮计时（秒）
    mean_time: float


def _ensure_index(conn: sqlite3.Connection) -> None:
    conn.execute(f"CREATE INDEX IF NOT EXISTS {_INDEX_NAME} ON dwd_sensor_clean(site_id, ts)")
    conn.commit()


def _explain(conn: sqlite3.Connection, sql: str, params: tuple) -> list[str]:
    rows = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    return [row[-1] for row in rows]


def _time_query(conn: sqlite3.Connection, sql: str, params: tuple, rounds: int) -> list[float]:
    times: list[float] = []
    for _ in range(rounds):
        start = time.perf_counter()
        conn.execute(sql, params).fetchall()
        times.append(time.perf_counter() - start)
    return times


def run_benchmark(conn: sqlite3.Connection, rounds: int = 5) -> dict:
    """典型场景「某站点近 7 天 PM2.5 每小时均值」的朴素 vs 优化对比。

    返回含 ``baseline`` / ``optimized``（均为 QueryResult）及 speedup 的 dict，
    由调用方落盘为 JSON。
    """
    _ensure_index(conn)

    site_id = conn.execute("SELECT MIN(site_id) FROM dwd_sensor_clean").fetchone()[0]
    max_ts = conn.execute("SELECT MAX(ts) FROM dwd_sensor_clean").fetchone()[0]
    start_ts = (
        datetime.strptime(max_ts, "%Y-%m-%d %H:%M:%S") - timedelta(days=7)
    ).strftime("%Y-%m-%d %H:%M:%S")
    params = (site_id, start_ts)

    baseline = QueryResult(
        name="baseline",
        sql=_BASELINE_SQL,
        explain=_explain(conn, _BASELINE_SQL, params),
        times=[],
        mean_time=0.0,
    )
    optimized = QueryResult(
        name="optimized",
        sql=_OPTIMIZED_SQL,
        explain=_explain(conn, _OPTIMIZED_SQL, params),
        times=[],
        mean_time=0.0,
    )

    baseline.times = _time_query(conn, _BASELINE_SQL, params, rounds)
    optimized.times = _time_query(conn, _OPTIMIZED_SQL, params, rounds)
    baseline.mean_time = statistics.mean(baseline.times)
    optimized.mean_time = statistics.mean(optimized.times)

    speedup = baseline.mean_time / optimized.mean_time if optimized.mean_time > 0 else 0.0

    return {
        "scenario": SCENARIO,
        "site_id": site_id,
        "start_ts": start_ts,
        "rounds": rounds,
        "baseline": baseline,
        "optimized": optimized,
        "speedup": speedup,
    }
