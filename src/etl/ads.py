"""DWS→ADS：站点 × 小时跨设备聚合宽表，供看板直接消费。"""

from __future__ import annotations

import sqlite3

_INSERT_ADS = """
INSERT INTO ads_dashboard (
    site_id, site_name, hour_start, device_count,
    temp_mean, temp_min, temp_max,
    humidity_mean, humidity_min, humidity_max,
    pressure_mean, pressure_min, pressure_max,
    pm25_mean, pm25_min, pm25_max
)
SELECT
    h.site_id, s.site_name, h.period_start, COUNT(DISTINCT h.device_id),
    AVG(h.temp_mean), MIN(h.temp_min), MAX(h.temp_max),
    AVG(h.humidity_mean), MIN(h.humidity_min), MAX(h.humidity_max),
    AVG(h.pressure_mean), MIN(h.pressure_min), MAX(h.pressure_max),
    AVG(h.pm25_mean), MIN(h.pm25_min), MAX(h.pm25_max)
FROM dws_sensor_hourly h
JOIN ods_site s ON s.site_id = h.site_id
GROUP BY h.site_id, h.period_start
"""


def build_ads(conn: sqlite3.Connection) -> int:
    """DWS→ads_dashboard：站点 × 小时跨设备聚合宽表。返回宽表行数。"""
    cur = conn.cursor()
    cur.execute("DELETE FROM ads_dashboard")
    cur.execute(_INSERT_ADS)
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM ads_dashboard").fetchone()[0]
