"""建表 DDL 与索引 DDL。

通过表名前缀体现 ODS / DWD / DWS / ADS 四层中台结构，
不上真实数仓引擎，仅用 SQLite schema 命名体现。
"""

from __future__ import annotations

import sqlite3

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS ods_site (
    site_id   INTEGER PRIMARY KEY,
    site_name TEXT NOT NULL,
    region    TEXT NOT NULL,
    lat       REAL NOT NULL,
    lon       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ods_device (
    device_id   INTEGER PRIMARY KEY,
    site_id     INTEGER NOT NULL,
    device_name TEXT NOT NULL,
    device_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ods_sensor_raw (
    id       INTEGER PRIMARY KEY,
    site_id  INTEGER NOT NULL,
    device_id INTEGER NOT NULL,
    ts       TEXT NOT NULL,
    temp     REAL,
    humidity REAL,
    pressure REAL,
    pm25     REAL
);

CREATE TABLE IF NOT EXISTS dwd_sensor_clean (
    site_id      INTEGER NOT NULL,
    device_id    INTEGER NOT NULL,
    ts           TEXT NOT NULL,
    temp         REAL,
    humidity     REAL,
    pressure     REAL,
    pm25         REAL,
    quality_flag TEXT NOT NULL,
    PRIMARY KEY (site_id, device_id, ts)
);

CREATE TABLE IF NOT EXISTS dws_sensor_hourly (
    site_id        INTEGER NOT NULL,
    device_id      INTEGER NOT NULL,
    period_start   TEXT NOT NULL,
    temp_mean      REAL, temp_max REAL, temp_min REAL, temp_std REAL,
    humidity_mean  REAL, humidity_max REAL, humidity_min REAL, humidity_std REAL,
    pressure_mean  REAL, pressure_max REAL, pressure_min REAL, pressure_std REAL,
    pm25_mean      REAL, pm25_max REAL, pm25_min REAL, pm25_std REAL,
    PRIMARY KEY (site_id, device_id, period_start)
);

CREATE TABLE IF NOT EXISTS dws_sensor_daily (
    site_id        INTEGER NOT NULL,
    device_id      INTEGER NOT NULL,
    period_start   TEXT NOT NULL,
    temp_mean      REAL, temp_max REAL, temp_min REAL, temp_std REAL,
    humidity_mean  REAL, humidity_max REAL, humidity_min REAL, humidity_std REAL,
    pressure_mean  REAL, pressure_max REAL, pressure_min REAL, pressure_std REAL,
    pm25_mean      REAL, pm25_max REAL, pm25_min REAL, pm25_std REAL,
    PRIMARY KEY (site_id, device_id, period_start)
);

CREATE TABLE IF NOT EXISTS ads_dashboard (
    site_id       INTEGER NOT NULL,
    site_name     TEXT NOT NULL,
    hour_start    TEXT NOT NULL,
    device_count  INTEGER NOT NULL,
    temp_mean     REAL, temp_min REAL, temp_max REAL,
    humidity_mean REAL, humidity_min REAL, humidity_max REAL,
    pressure_mean REAL, pressure_min REAL, pressure_max REAL,
    pm25_mean     REAL, pm25_min REAL, pm25_max REAL,
    PRIMARY KEY (site_id, hour_start)
);
"""

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_dwd_site_ts ON dwd_sensor_clean(site_id, ts);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """创建 ODS / DWD / DWS / ADS 全部表。幂等（IF NOT EXISTS）。"""
    conn.executescript(_CREATE_TABLES)
    conn.commit()


def create_indexes(conn: sqlite3.Connection) -> None:
    """创建 SQL 优化对比所需的复合索引 (site_id, ts)（REQ-07）。"""
    conn.executescript(_CREATE_INDEXES)
    conn.commit()
