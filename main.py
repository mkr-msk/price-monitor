"""CLI: снимок каталога и отчёт об изменениях между снимками.

Пример:
    python main.py snapshot --pages 3            # первый снимок
    python main.py report  --output data/report.xlsx   # сравнить 2 последних снимка
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from collect import _make_session, collect_snapshot
from diffing import Diff, diff_snapshots
from report import write_report

PAGE_TEMPLATE = "https://books.toscrape.com/catalogue/page-{page}.html"
SNAPSHOTS_DIR = Path(__file__).resolve().parent / "data" / "snapshots"


def _load_snapshots() -> list[tuple[Path, list[dict]]]:
    files = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
    loaded = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            loaded.append((f, json.load(fh)))
    return loaded


def cmd_snapshot(args: argparse.Namespace) -> int:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    session = _make_session()
    records = collect_snapshot(
        session, page_template=PAGE_TEMPLATE, pages=args.pages, delay=args.delay
    )
    if not records:
        print("Пустой снимок — проверьте сеть или селекторы.")
        return 1
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = SNAPSHOTS_DIR / f"snapshot_{stamp}.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=1)
    print(f"Снимок: {len(records)} позиций → {out}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    loaded = _load_snapshots()
    if len(loaded) < 2:
        print(f"Нужно минимум 2 снимка (сделайте {len(loaded)} раз snapshot).")
        return 1
    (prev_path, prev), (curr_path, curr) = loaded[-2], loaded[-1]
    diff = diff_snapshots(prev, curr)
    out = write_report(diff, args.output)
    print(f"Сравнение: {prev_path.name} → {curr_path.name}")
    print(f"Новые: {len(diff.added)} | Исчезли: {len(diff.removed)} | Цена: {len(diff.price_changes)}")
    print(f"Отчёт: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Мониторинг изменений каталога")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="собрать снимок каталога")
    snap.add_argument("--pages", type=int, default=3)
    snap.add_argument("--delay", type=float, default=0.6)
    snap.set_defaults(func=cmd_snapshot)

    rep = sub.add_parser("report", help="отчёт об изменениях между снимками")
    rep.add_argument("--output", default="data/report.xlsx")
    rep.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
