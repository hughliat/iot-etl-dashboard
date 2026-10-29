"""DWD→DWS 聚合：按小时 / 天粒度输出均值、最大、最小、标准差。"""

from __future__ import annotations

import sqlite3

_FIELDS = ("temp", "humidity", "pressure", "pm25")


def _agg_select(field: str) -> str:
    """单字段聚合表达式：均值 / 最大 / 最小 / 样本标准差（NULL 自动排除）。

    标准差用公式 sqrt((sum(x^2) - sum(x)^2/n) / (n-1))，n < 2 时置 NULL。
    """
    return (
        f"AVG({field}) AS {field}_mean, "
        f"MAX({field}) AS {field}_max, "
        f"MIN({field}) AS {field}_min, "
        f"CASE WHEN COUNT({field}) > 1 "
        f"THEN SQRT((SUM({field}*{field}) - SUM({field})*SUM({field})/COUNT({field})) "
        f"/ (COUNT({field}) - 1)) ELSE NULL END AS {field}_std"
    )


def _column_list() -> str:
    cols = []
    for f in _FIELDS:
        cols.extend([f"{f}_mean", f"{f}_max", f"{f}_min", f"{f}_std"])
    return ", ".join(cols)


def _aggregate(conn: sqlite3.Connection, table: str, period_expr: str) -> int:
    """通用聚合：DWD 按 period_expr 分组写入目标表，返回聚合行数。"""
    agg_parts = ", ".join(_agg_select(f) for f in _FIELDS)
    sql = (
        f"INSERT INTO {table} "
        f"(site_id, device_id, period_start, {_column_list()}) "
        f"SELECT site_id, device_id, {period_expr} AS period_start, {agg_parts} "
        f"FROM dwd_sensor_clean "
        f"GROUP BY site_id, device_id, period_start"
    )
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table}")
    cur.execute(sql)
    conn.commit()
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def aggregate_hourly(conn: sqlite3.Connection) -> int:
    """DWD→dws_sensor_hourly：每站点每设备每小时 mean/max/min/std。返回聚合行数。"""
    return _aggregate(conn, "dws_sensor_hourly", "substr(ts, 1, 13) || ':00:00'")


def aggregate_daily(conn: sqlite3.Connection) -> int:
    """DWD→dws_sensor_daily：每站点每设备每天 mean/max/min/std。返回聚合行数。"""
    return _aggregate(conn, "dws_sensor_daily", "substr(ts, 1, 10)")
