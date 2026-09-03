"""Сравнение двух снимков: вычисление изменений.

Чистые функции без I/O — легко тестировать.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PriceChange:
    title: str
    url: str
    old: float | None
    new: float | None


@dataclass
class Diff:
    added: list[dict] = field(default_factory=list)          # появились в текущем
    removed: list[dict] = field(default_factory=list)        # были в прошлом, исчезли
    price_changes: list[PriceChange] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.added) + len(self.removed) + len(self.price_changes)


def index_by_url(snapshot: list[dict]) -> dict[str, dict]:
    return {item["url"]: item for item in snapshot}


def diff_snapshots(prev: list[dict], curr: list[dict]) -> Diff:
    """Сравнить прошлый и текущий снимок по url и цене."""
    prev_map = index_by_url(prev)
    curr_map = index_by_url(curr)

    diff = Diff()
    for url, item in curr_map.items():
        if url not in prev_map:
            diff.added.append(item)

    for url, item in prev_map.items():
        if url not in curr_map:
            diff.removed.append(item)

    for url in prev_map.keys() & curr_map.keys():
        old_price = prev_map[url]["price"]
        new_price = curr_map[url]["price"]
        if old_price != new_price:
            diff.price_changes.append(
                PriceChange(
                    title=curr_map[url]["title"],
                    url=url,
                    old=old_price,
                    new=new_price,
                )
            )
    return diff
