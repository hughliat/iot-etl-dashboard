"""集中管理规模参数、种子、传感器定义与落盘路径。

本项目运行时零第三方依赖，仅使用 Python 标准库。
所有随机行为仅依赖 ``random.Random(seed)``，同参数同种子可复现。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SensorSpec:
    """单个传感器字段的定义。"""

    key: str   # 字段名，如 "temp"
    unit: str  # 国际单位，如 "℃"
    lo: float  # 合理值下限
    hi: float  # 合理值上限


@dataclass(frozen=True)
class ScaleConfig:
    """采集模拟的规模参数。"""

    sites: int
    devices_per_site: int
    interval_seconds: int
    days: int
    seed: int

    @property
    def total_rows(self) -> int:
        """理论行数（不含脏数据重复行）。"""
        points_per_device = (self.days * 86400) // self.interval_seconds
        return self.sites * self.devices_per_site * points_per_device


# 四类传感器：温度 / 湿度 / 气压 / PM2.5，含单位与合理值范围。
SENSORS: tuple[SensorSpec, ...] = (
    SensorSpec(key="temp", unit="℃", lo=-30.0, hi=50.0),
    SensorSpec(key="humidity", unit="%RH", lo=0.0, hi=100.0),
    SensorSpec(key="pressure", unit="hPa", lo=870.0, hi=1085.0),
    SensorSpec(key="pm25", unit="μg/m³", lo=0.0, hi=500.0),
)

# 传感器字段中文名（看板展示用）。
METRIC_LABELS: dict[str, str] = {
    "temp": "温度",
    "humidity": "湿度",
    "pressure": "气压",
    "pm25": "PM2.5",
}

# 默认规模：5 站点 × 3 设备，60 秒采样，30 天，约 65 万行。
DEFAULT_SCALE = ScaleConfig(sites=5, devices_per_site=3, interval_seconds=60, days=30, seed=42)
# 压测规模：10 站点 × 5 设备，30 秒采样，30 天，约 432 万行（百万行级，供 SQL 优化对比）。
STRESS_SCALE = ScaleConfig(sites=10, devices_per_site=5, interval_seconds=30, days=30, seed=42)

# 落盘路径（默认输出目录为项目根下的 output/）。
OUTPUT_DIR = Path("output")
DB_PATH = OUTPUT_DIR / "iot_etl.db"
DASHBOARD_DATA_PATH = OUTPUT_DIR / "dashboard_data.json"
DASHBOARD_HTML_PATH = OUTPUT_DIR / "dashboard.html"
SQL_REPORT_PATH = OUTPUT_DIR / "sql_optimization_report.json"
QUALITY_REPORT_PATH = OUTPUT_DIR / "data_quality_report.json"
