"""ADS→JSON 导出：站点小时趋势 + 站点汇总对比。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..config import METRIC_LABELS, SENSORS


def export_dashboard_data(conn: sqlite3.Connection, out_path: Path) -> None:
    """ADS→JSON（站点小时趋势 + 站点汇总对比），写入 out_path。"""
    metrics = [
        {"key": s.key, "label": METRIC_LABELS[s.key], "unit": s.unit} for s in SENSORS
    ]

    site_rows = conn.execute(
        "SELECT site_id, site_name, region, lat, lon FROM ods_site ORDER BY site_id"
    ).fetchall()
    site_names = {row[0]: row[1] for row in site_rows}

    trends = []
    for row in site_rows:
        site_id = row[0]
        points = []
        for r in conn.execute(
            "SELECT hour_start, temp_mean, humidity_mean, pressure_mean, pm25_mean "
            "FROM ads_dashboard WHERE site_id = ? ORDER BY hour_start",
            (site_id,),
        ):
            points.append(
                {
                    "hour": r[0],
                    "temp": r[1],
                    "humidity": r[2],
                    "pressure": r[3],
                    "pm25": r[4],
                }
            )
        trends.append({"site_id": site_id, "site_name": row[1], "points": points})

    summary = []
    for r in conn.execute(
        "SELECT site_id, AVG(temp_mean), AVG(humidity_mean), AVG(pressure_mean), AVG(pm25_mean) "
        "FROM ads_dashboard GROUP BY site_id ORDER BY site_id"
    ):
        summary.append(
            {
                "site_id": r[0],
                "site_name": site_names[r[0]],
                "temp": r[1],
                "humidity": r[2],
                "pressure": r[3],
                "pm25": r[4],
            }
        )

    data = {
        "metrics": metrics,
        "sites": [
            {"site_id": r[0], "site_name": r[1], "region": r[2], "lat": r[3], "lon": r[4]}
            for r in site_rows
        ],
        "trends": trends,
        "summary": summary,
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
