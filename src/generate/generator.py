"""确定性随机生成传感器时序数据，并按小比例注入脏数据。

确定性保证：所有随机点（正常值、注入位置、注入类型）均从同一个
``random.Random(seed)`` 流按固定顺序消费，同参数同种子多次运行逐行一致。
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Iterator

from ..config import SENSORS, ScaleConfig

# 采集基准时间（UTC），固定起点保证跨环境一致。
_EPOCH = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# 脏数据注入比例（固定小比例）。
P_MISSING = 0.003    # 缺失 ≈0.3%
P_OUTLIER = 0.003    # 越界 ≈0.3%
P_DUPLICATE = 0.005  # 重复 ≈0.5%

# 注入类型常量。
CLEAN = "clean"
MISSING = "missing"
OUTLIER = "outlier"
DUPLICATE = "duplicate"


def _clamp(value: float, lo: float, hi: float) -> float:
    """将正常值约束在合理范围内（越界脏数据由 inject_dirty 单独注入）。"""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _precompute_time(cfg: ScaleConfig) -> tuple[list[str], list[float], list[float]]:
    """预计算时间戳字符串与三角函数因子，避免内层循环重复计算。"""
    total = (cfg.days * 86400) // cfg.interval_seconds
    ts_strs: list[str] = []
    sin_day: list[float] = []
    sin_pressure: list[float] = []
    for i in range(total):
        dt = _EPOCH + timedelta(seconds=i * cfg.interval_seconds)
        ts_strs.append(dt.strftime("%Y-%m-%d %H:%M:%S"))
        hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
        sin_day.append(math.sin(2.0 * math.pi * (hour - 6.0) / 24.0))
        sin_pressure.append(math.sin(2.0 * math.pi * dt.day / 28.0))
    return ts_strs, sin_day, sin_pressure


def _normal_value(spec_index: int, site_id: int, sd: float, sp: float, rng: random.Random) -> float:
    """生成单字段正常值：确定性基线（日周期 + 站点偏移）+ 随机噪声，裁剪到合理范围。"""
    spec = SENSORS[spec_index]
    if spec_index == 0:  # 温度
        base = 18.0 + 8.0 * sd + (site_id - 1) * 2.5
        val = base + rng.uniform(-2.0, 2.0)
    elif spec_index == 1:  # 湿度
        base = 55.0 - 15.0 * sd + (site_id % 3) * 4.0
        val = base + rng.uniform(-5.0, 5.0)
    elif spec_index == 2:  # 气压
        base = 1013.0 + 2.0 * sp + (site_id - 1) * 0.8
        val = base + rng.uniform(-1.5, 1.5)
    else:  # PM2.5
        base = 55.0 + 15.0 * sd + (site_id - 1) * 5.0
        val = base + rng.uniform(-8.0, 8.0)
    return _clamp(val, spec.lo, spec.hi)


def inject_dirty(row: tuple, rng: random.Random) -> tuple:
    """对单条正常记录按小比例决定注入类型，返回 (记录, 类型)。

    类型：``outlier``（某字段越界值）、``missing``（某字段置 None）、
    ``duplicate``（返回原记录，由调用方重复写入形成重复主键）、``clean``。
    纯函数，可单测；随机点从同一 rng 流按固定顺序消费。
    """
    roll = rng.random()
    if roll < P_MISSING:
        idx = rng.randrange(len(SENSORS))
        row = list(row)
        row[3 + idx] = None
        return tuple(row), MISSING
    if roll < P_MISSING + P_OUTLIER:
        idx = rng.randrange(len(SENSORS))
        spec = SENSORS[idx]
        # 生成明显超出合理范围的值（高于上限或低于下限）。
        if rng.random() < 0.5:
            val = spec.hi + rng.uniform(1.0, 50.0)
        else:
            val = spec.lo - rng.uniform(1.0, 50.0)
        row = list(row)
        row[3 + idx] = val
        return tuple(row), OUTLIER
    if roll < P_MISSING + P_OUTLIER + P_DUPLICATE:
        return row, DUPLICATE
    return row, CLEAN


def generate_records(cfg: ScaleConfig, rng: random.Random) -> Iterator[tuple]:
    """流式产出 ``(site_id, device_id, ts, temp, humidity, pressure, pm25)``。

    确定性：仅依赖 rng（由 cfg.seed 构造）；按比例注入重复 / 越界 / 缺失。
    """
    ts_strs, sin_day, sin_pressure = _precompute_time(cfg)
    n = len(ts_strs)
    for site_id in range(1, cfg.sites + 1):
        for device_id in range(1, cfg.devices_per_site + 1):
            for i in range(n):
                sd = sin_day[i]
                sp = sin_pressure[i]
                row = (
                    site_id,
                    device_id,
                    ts_strs[i],
                    _normal_value(0, site_id, sd, sp, rng),
                    _normal_value(1, site_id, sd, sp, rng),
                    _normal_value(2, site_id, sd, sp, rng),
                    _normal_value(3, site_id, sd, sp, rng),
                )
                new_row, kind = inject_dirty(row, rng)
                yield new_row
                if kind == DUPLICATE:
                    # 重复写入同一条记录，形成重复业务主键 (site_id, device_id, ts)。
                    yield new_row
