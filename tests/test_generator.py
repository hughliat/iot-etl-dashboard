"""采集模拟：确定性随机与脏数据注入（REQ-01）。"""

from __future__ import annotations

import random
from datetime import datetime

from src.config import SENSORS, ScaleConfig
from src.generate.generator import (
    CLEAN,
    DUPLICATE,
    MISSING,
    OUTLIER,
    generate_records,
    inject_dirty,
)


def _small_cfg() -> ScaleConfig:
    return ScaleConfig(sites=2, devices_per_site=2, interval_seconds=3600, days=2, seed=7)


def test_generate_records_deterministic():
    """同参数同种子多次运行逐行一致（REQ-01 验收）。"""
    cfg = _small_cfg()
    g1 = list(generate_records(cfg, random.Random(cfg.seed)))
    g2 = list(generate_records(cfg, random.Random(cfg.seed)))
    assert g1 == g2
    assert len(g1) > 0


def test_generate_records_structure():
    """记录为 7 元组，站点 / 设备 / 时间戳字段合法。"""
    cfg = ScaleConfig(sites=2, devices_per_site=1, interval_seconds=3600, days=1, seed=3)
    for row in generate_records(cfg, random.Random(cfg.seed)):
        assert len(row) == 7
        site_id, device_id, ts = row[0], row[1], row[2]
        assert 1 <= site_id <= cfg.sites
        assert 1 <= device_id <= cfg.devices_per_site
        datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")


def test_record_count_within_scale():
    """行数 ≥ 理论行数，且重复行增量不超过注入比例上界。"""
    cfg = _small_cfg()
    rows = list(generate_records(cfg, random.Random(cfg.seed)))
    assert len(rows) >= cfg.total_rows
    # 重复约 0.5%，留足余量
    assert len(rows) <= cfg.total_rows + int(cfg.total_rows * 0.02) + 5


def test_inject_dirty_invariants():
    """inject_dirty 各类注入的字段级不变量。"""
    rng = random.Random(99)
    row = (3, 2, "2026-01-05 08:30:00", 25.0, 60.0, 1010.0, 45.0)
    seen = set()
    for _ in range(5000):
        new_row, kind = inject_dirty(row, rng)
        seen.add(kind)
        assert len(new_row) == 7
        assert new_row[:3] == row[:3]
        if kind in (CLEAN, DUPLICATE):
            assert new_row == row
        elif kind == MISSING:
            nulls = [i for i in range(3, 7) if new_row[i] is None]
            assert len(nulls) == 1
            for i in range(3, 7):
                if i not in nulls:
                    assert new_row[i] == row[i]
        elif kind == OUTLIER:
            changed = [i for i in range(3, 7) if new_row[i] != row[i]]
            assert len(changed) == 1
            spec = SENSORS[changed[0] - 3]
            assert new_row[changed[0]] < spec.lo or new_row[changed[0]] > spec.hi
    assert seen == {CLEAN, MISSING, OUTLIER, DUPLICATE}


def test_dirty_ratio_presence():
    """大样本下三类脏数据均出现，且干净数据占绝大多数。"""
    rng = random.Random(123)
    row = (1, 1, "2026-01-01 00:00:00", 20.0, 50.0, 1000.0, 30.0)
    counts = {CLEAN: 0, MISSING: 0, OUTLIER: 0, DUPLICATE: 0}
    n = 20000
    for _ in range(n):
        _, kind = inject_dirty(row, rng)
        counts[kind] += 1
    assert counts[MISSING] > 0
    assert counts[OUTLIER] > 0
    assert counts[DUPLICATE] > 0
    assert counts[CLEAN] > 0.9 * n
    # 松散比例校验（缺失 / 越界 ≈0.3%，重复 ≈0.5%）
    assert 30 <= counts[MISSING] <= 90
    assert 30 <= counts[OUTLIER] <= 90
    assert 60 <= counts[DUPLICATE] <= 140
