"""Тесты сравнения снимков (без сети)."""
from diffing import diff_snapshots


def _item(url, title="T", price=10.0):
    return {"title": title, "price": price, "currency": "£", "url": url, "in_stock": True}


def test_diff_identical_is_empty():
    snap = [_item("u1"), _item("u2", price=5.0)]
    d = diff_snapshots(snap, snap)
    assert d.total == 0


def test_diff_added_and_removed():
    prev = [_item("u1"), _item("u2")]
    curr = [_item("u2"), _item("u3")]
    d = diff_snapshots(prev, curr)
    assert [x["url"] for x in d.added] == ["u3"]
    assert [x["url"] for x in d.removed] == ["u1"]
    assert len(d.price_changes) == 0


def test_diff_price_change():
    prev = [_item("u1", price=10.0)]
    curr = [_item("u1", price=12.5)]
    d = diff_snapshots(prev, curr)
    assert len(d.price_changes) == 1
    change = d.price_changes[0]
    assert change.old == 10.0 and change.new == 12.5


def test_diff_mixed():
    prev = [_item("a", price=1), _item("b", price=2)]
    curr = [_item("b", price=3), _item("c", price=4)]
    d = diff_snapshots(prev, curr)
    assert len(d.added) == 1          # c
    assert len(d.removed) == 1        # a
    assert len(d.price_changes) == 1  # b: 2 → 3
    assert d.total == 3
