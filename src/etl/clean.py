"""ODS→DWD 清洗：去重、越界值置空并标记、字段规范化。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..config import SENSORS

_BATCH_SIZE = 5000

# 去重：按业务主键 (site_id, device_id, ts) 保留首条（最小 id）。
_DEDUP_SQL = """
SELECT o.site_id, o.device_id, o.ts, o.temp, o.humidity, o.pressure, o.pm25
FROM ods_sensor_raw o
JOIN (
    SELECT site_id, device_id, ts, MIN(id) AS min_id
    FROM ods_sensor_raw
    GROUP BY site_id, device_id, ts
) d ON o.id = d.min_id
ORDER BY o.id
"""

_INSERT_DWD = """
INSERT INTO dwd_sensor_clean
    (site_id, device_id, ts, temp, humidity, pressure, pm25, quality_flag)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


@dataclass
class QualityReport:
    """数据质量报告（REQ-11）。"""

    before_rows: int
    after_rows: int
    duplicates_removed: int
    outlier_count: int
    missing_count: int


def clean_ods_to_dwd(conn: sqlite3.Connection) -> QualityReport:
    """ODS→DWD：去重、越界值置空并标记、字段规范化，返回 QualityReport。

    越界值置 NULL 并标记 OUTLIER；原始缺失值标记 MISSING；不静默丢弃任何行。
    """
    before_rows = conn.execute("SELECT COUNT(*) FROM ods_sensor_raw").fetchone()[0]

    cur = conn.cursor()
    cur.execute("DELETE FROM dwd_sensor_clean")

    outlier_count = 0
    missing_count = 0
    batch: list[tuple] = []

    for site_id, device_id, ts, temp, humidity, pressure, pm25 in conn.execute(_DEDUP_SQL):
        fields = [temp, humidity, pressure, pm25]
        cleaned = list(fields)
        has_outlier = False
        has_missing = False
        for i, (val, spec) in enumerate(zip(fields, SENSORS)):
            if val is None:
                has_missing = True
            elif val < spec.lo or val > spec.hi:
                has_outlier = True
                cleaned[i] = None

        if has_outlier:
            flag = "OUTLIER"
            outlier_count += 1
        elif has_missing:
            flag = "MISSING"
            missing_count += 1
        else:
            flag = "OK"

        batch.append((site_id, device_id, ts, cleaned[0], cleaned[1], cleaned[2], cleaned[3], flag))
        if len(batch) >= _BATCH_SIZE:
            cur.executemany(_INSERT_DWD, batch)
            batch.clear()

    if batch:
        cur.executemany(_INSERT_DWD, batch)

    conn.commit()

    after_rows = conn.execute("SELECT COUNT(*) FROM dwd_sensor_clean").fetchone()[0]
    return QualityReport(
        before_rows=before_rows,
        after_rows=after_rows,
        duplicates_removed=before_rows - after_rows,
        outlier_count=outlier_count,
        missing_count=missing_count,
    )
