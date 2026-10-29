"""将生成的传感器时序数据批量写入 ODS 层，并写入站点 / 设备元数据。"""

from __future__ import annotations

import random
import sqlite3

from ..config import ScaleConfig
from .generator import generate_records

_BATCH_SIZE = 5000

# 站点区域（循环取用，覆盖任意站点数）。
_REGIONS = ("华东", "华北", "华南", "西南")

_INSERT_RAW = """
INSERT INTO ods_sensor_raw (site_id, device_id, ts, temp, humidity, pressure, pm25)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_SITE = "INSERT INTO ods_site (site_id, site_name, region, lat, lon) VALUES (?, ?, ?, ?, ?)"
_INSERT_DEVICE = "INSERT INTO ods_device (device_id, site_id, device_name, device_type) VALUES (?, ?, ?, ?)"


def _site_name(site_id: int) -> str:
    """站点名：园区A、园区B……（站点数超过 26 时回退为数字编号）。"""
    if 1 <= site_id <= 26:
        return f"园区{chr(64 + site_id)}"
    return f"园区{site_id}"


def _load_metadata(conn: sqlite3.Connection, cfg: ScaleConfig) -> None:
    """写入站点与设备元数据表（REQ-10）。"""
    site_rows = []
    device_rows = []
    device_id = 1
    for site_id in range(1, cfg.sites + 1):
        site_rows.append(
            (
                site_id,
                _site_name(site_id),
                _REGIONS[(site_id - 1) % len(_REGIONS)],
                20.0 + (site_id - 1) * 3.0,
                100.0 + (site_id - 1) * 3.5,
            )
        )
        for _ in range(1, cfg.devices_per_site + 1):
            device_rows.append((device_id, site_id, f"节点{device_id:04d}", "集成传感器节点"))
            device_id += 1
    conn.executemany(_INSERT_SITE, site_rows)
    conn.executemany(_INSERT_DEVICE, device_rows)


def load_ods(conn: sqlite3.Connection, cfg: ScaleConfig, rng: random.Random) -> int:
    """生成并批量写入 ods_sensor_raw，返回写入行数（含脏数据重复行）。"""
    _load_metadata(conn, cfg)
    cur = conn.cursor()
    batch: list[tuple] = []
    count = 0
    for row in generate_records(cfg, rng):
        batch.append(row)
        if len(batch) >= _BATCH_SIZE:
            cur.executemany(_INSERT_RAW, batch)
            count += len(batch)
            batch.clear()
    if batch:
        cur.executemany(_INSERT_RAW, batch)
        count += len(batch)
    conn.commit()
    return count
