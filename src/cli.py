"""统一入口：编排全链路（对应 make run），并解析命令行参数。"""

from __future__ import annotations

import argparse
import dataclasses
import json
import random
import sqlite3
import sys
from pathlib import Path

from .config import (
    DB_PATH,
    DASHBOARD_DATA_PATH,
    DASHBOARD_HTML_PATH,
    DEFAULT_SCALE,
    OUTPUT_DIR,
    QUALITY_REPORT_PATH,
    SQL_REPORT_PATH,
    STRESS_SCALE,
    ScaleConfig,
)
from .dashboard.export import export_dashboard_data
from .dashboard.render import render_html
from .etl.ads import build_ads
from .etl.aggregate import aggregate_daily, aggregate_hourly
from .etl.clean import QualityReport, clean_ods_to_dwd
from .generate.loader import load_ods
from .generate.schema import create_indexes, create_schema
from .optimize.benchmark import QueryResult, run_benchmark


def _resolve_scale(args: argparse.Namespace) -> ScaleConfig:
    """根据 --scale 与各覆盖参数解析最终规模配置。"""
    base = STRESS_SCALE if getattr(args, "scale", None) == "stress" else DEFAULT_SCALE
    return ScaleConfig(
        sites=args.sites if args.sites is not None else base.sites,
        devices_per_site=(
            args.devices_per_site if args.devices_per_site is not None else base.devices_per_site
        ),
        interval_seconds=args.interval if args.interval is not None else base.interval_seconds,
        days=args.days if args.days is not None else base.days,
        seed=args.seed if args.seed is not None else base.seed,
    )


def _paths(output_dir: Path) -> dict[str, Path]:
    return {
        "db": output_dir / DB_PATH.name,
        "data": output_dir / DASHBOARD_DATA_PATH.name,
        "html": output_dir / DASHBOARD_HTML_PATH.name,
        "sql_report": output_dir / SQL_REPORT_PATH.name,
        "quality": output_dir / QUALITY_REPORT_PATH.name,
    }


def _fresh_db(db_path: Path) -> sqlite3.Connection:
    if db_path.exists():
        db_path.unlink()
    return sqlite3.connect(str(db_path))


def _write_json(obj: dict, path: Path) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _serialize_benchmark(report: dict) -> dict:
    return {
        "scenario": report["scenario"],
        "site_id": report["site_id"],
        "start_ts": report["start_ts"],
        "rounds": report["rounds"],
        "speedup": report["speedup"],
        "baseline": dataclasses.asdict(report["baseline"]),
        "optimized": dataclasses.asdict(report["optimized"]),
    }


def run_pipeline(cfg: ScaleConfig, output_dir: Path, rounds: int = 5) -> None:
    """编排：建库 → 采集 → 清洗 → 聚合 → 优化对比 → 看板输出。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = _paths(output_dir)
    conn = _fresh_db(paths["db"])
    rng = random.Random(cfg.seed)
    try:
        create_schema(conn)
        load_ods(conn, cfg, rng)

        quality = clean_ods_to_dwd(conn)
        _write_json(dataclasses.asdict(quality), paths["quality"])

        aggregate_hourly(conn)
        aggregate_daily(conn)
        build_ads(conn)

        create_indexes(conn)
        report = run_benchmark(conn, rounds=rounds)
        _write_json(_serialize_benchmark(report), paths["sql_report"])

        export_dashboard_data(conn, paths["data"])
        render_html(paths["data"], paths["html"])
    finally:
        conn.close()


def _cmd_run(args: argparse.Namespace) -> int:
    cfg = _resolve_scale(args)
    output_dir = Path(args.output_dir) if getattr(args, "output_dir", None) else OUTPUT_DIR
    run_pipeline(cfg, output_dir, rounds=args.rounds)
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    cfg = _resolve_scale(args)
    output_dir = Path(args.output_dir) if getattr(args, "output_dir", None) else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = _paths(output_dir)
    conn = _fresh_db(paths["db"])
    rng = random.Random(cfg.seed)
    try:
        create_schema(conn)
        load_ods(conn, cfg, rng)
        clean_ods_to_dwd(conn)
        create_indexes(conn)
        report = run_benchmark(conn, rounds=args.rounds)
        _write_json(_serialize_benchmark(report), paths["sql_report"])
    finally:
        conn.close()
    return 0


def _cmd_clean(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir) if getattr(args, "output_dir", None) else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = _paths(output_dir)
    if not paths["db"].exists():
        run_pipeline(DEFAULT_SCALE, output_dir)
        return 0
    conn = sqlite3.connect(str(paths["db"]))
    try:
        quality = clean_ods_to_dwd(conn)
        _write_json(dataclasses.asdict(quality), paths["quality"])
    finally:
        conn.close()
    return 0


def _add_scale_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scale", choices=["default", "stress"], default=None,
                        help="规模预设：default（约 65 万行）或 stress（约 432 万行）")
    parser.add_argument("--sites", type=int, default=None, help="站点数")
    parser.add_argument("--devices-per-site", type=int, default=None, help="每站点设备数")
    parser.add_argument("--interval", type=int, default=None, help="采样间隔（秒）")
    parser.add_argument("--days", type=int, default=None, help="时长（天）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="src.cli",
        description="IoT 传感器数据 ETL 与可视化项目：一键跑通采集→清洗→聚合→看板。",
    )
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="一键跑通全链路（默认子命令）")
    _add_scale_args(run)
    run.add_argument("--rounds", type=int, default=5, help="SQL 优化对比计时轮数")
    run.add_argument("--output-dir", type=str, default=None, help="输出目录")

    bench = sub.add_parser("benchmark", help="仅运行 SQL 优化对比（压测规模）")
    _add_scale_args(bench)
    bench.add_argument("--rounds", type=int, default=5, help="计时轮数")
    bench.add_argument("--output-dir", type=str, default=None, help="输出目录")

    clean = sub.add_parser("clean", help="对已有 ODS 数据执行清洗并输出质量报告")
    clean.add_argument("--output-dir", type=str, default=None, help="输出目录")

    return parser


def main(argv: list[str] | None = None) -> int:
    """argparse 入口。子命令：run（默认）/ benchmark / clean。返回退出码。"""
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        argv = ["run"]
    args = parser.parse_args(argv)

    if args.command == "benchmark":
        return _cmd_benchmark(args)
    if args.command == "clean":
        return _cmd_clean(args)
    # run 为默认子命令
    return _cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
