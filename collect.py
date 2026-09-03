"""Сбор «снимка» каталога для мониторинга изменений.

Снимок — это слепок текущего состояния (url → цена/наличие). Сравнивая два
снимка во времени, получаем отчёт о том, что изменилось (новые/исчезнувшие
позиции, изменение цен). Модуль сети/парсинга не привязан к конкретному сайту.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, asdict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0 Safari/537.36"
    ),
}

SELECTORS = {
    "card": "article.product_pod",
    "title": "h3 a",
    "price": "p.price_color",
    "stock": "p.instock.availability",
    "rating": "p.star-rating",
}

RATING_ORDER = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


class MonitorError(RuntimeError):
    """Ошибка сбора данных для мониторинга."""


@dataclass
class Product:
    title: str
    price: float | None
    currency: str
    in_stock: bool
    rating: int
    url: str


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def _apply_encoding(resp: requests.Response) -> None:
    content_type = resp.headers.get("Content-Type", "").lower()
    if "charset" not in content_type:
        resp.encoding = resp.apparent_encoding or "utf-8"


def fetch_page(session: requests.Session, url: str, *, timeout: int = 15,
               retries: int = 3, backoff: float = 1.0) -> str:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("Запрос %s: попытка %s/%s (%s)", url, attempt, retries, exc)
        else:
            if resp.status_code == 200:
                _apply_encoding(resp)
                return resp.text
            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = MonitorError(f"HTTP {resp.status_code} на {url}")
                logger.warning("HTTP %s на %s, попытка %s/%s",
                               resp.status_code, url, attempt, retries)
            else:
                raise MonitorError(f"HTTP {resp.status_code} на {url}")
        if attempt < retries:
            time.sleep(backoff * attempt)
    raise MonitorError(f"Не удалось получить {url}: {last_error}")


def parse_price(raw: str | None) -> tuple[float | None, str]:
    if not raw:
        return None, ""
    text = raw.strip()
    currency = re.sub(r"[0-9.,\s]", "", text)
    body = re.sub(r"[^\d.,]", "", text)
    if "," in body and "." in body:
        if body.rfind(",") > body.rfind("."):
            body = body.replace(".", "").replace(",", ".")
        else:
            body = body.replace(",", "")
    elif "," in body:
        body = body.replace(",", ".")
    elif body.count(".") > 1:
        body = body.replace(".", "")
    try:
        return float(body), currency
    except ValueError:
        return None, currency


def parse_products(html: str, page_url: str) -> list[Product]:
    soup = BeautifulSoup(html, "lxml")
    products: list[Product] = []
    for card in soup.select(SELECTORS["card"]):
        title_el = card.select_one(SELECTORS["title"])
        if title_el is None:
            continue
        title = " ".join((title_el.get("title") or title_el.get_text(" ", strip=True)).split())
        price_el = card.select_one(SELECTORS["price"])
        price, currency = parse_price(price_el.get_text(" ", strip=True) if price_el else None)
        stock_el = card.select_one(SELECTORS["stock"])
        in_stock = stock_el is not None and "In stock" in stock_el.get_text(" ", strip=True)
        rating = 0
        rating_el = card.select_one(SELECTORS["rating"])
        if rating_el is not None:
            for token in (rating_el.get("class") or []):
                if token in RATING_ORDER:
                    rating = RATING_ORDER[token]
        href = title_el.get("href", "")
        url = href if href.startswith("http") else urljoin(page_url, href)
        products.append(Product(title=title, price=price, currency=currency,
                                in_stock=in_stock, rating=rating, url=url))
    return products


def collect_snapshot(session: requests.Session, page_template: str, pages: int, *,
                     delay: float = 0.6, timeout: int = 15) -> list[dict]:
    """Собрать снимок каталога: список записей {url, title, price, ...}."""
    seen: dict[str, dict] = {}
    for page in range(1, pages + 1):
        url = page_template.format(page=page)
        html = fetch_page(session, url, timeout=timeout)
        for product in parse_products(html, url):
            seen.setdefault(product.url, asdict(product))
        logger.info("Страница %s/%s: всего позиций %s", page, pages, len(seen))
        if page < pages:
            time.sleep(delay)
    return list(seen.values())
