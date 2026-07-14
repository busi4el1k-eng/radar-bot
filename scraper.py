"""Pipeline-ul agregatorului: fetch → deduplicare → filtrare → îmbogățire → DB.

Rulat manual cu /pull sau automat de APScheduler. Un lock previne rulările
simultane. Nicio publicare automată — itemele ajung doar în inbox.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup
from rapidfuzz import fuzz

import ai_filter
import db
from sources import ACTIVE_SOURCES, SOURCE_KINDS, SOURCE_PRIORITIES, HttpClient, RawItem
from sources.base import strip_html

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 85  # % similaritate de titlu peste care două iteme sunt duplicat

_pull_lock = asyncio.Lock()


@dataclass
class PullReport:
    new: int = 0
    filtered: int = 0
    duplicates: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    per_source: dict[str, int] = field(default_factory=dict)


def normalize_url(url: str) -> str:
    """Fără utm_*/fbclid, fără fragment, fără trailing slash, host lowercase."""
    parsed = urlparse(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query)
        if not key.startswith("utm_") and key not in ("fbclid", "gclid", "ref")
    ]
    path = parsed.path.rstrip("/")
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc.lower(),
            path,
            "",
            urlencode(query),
            "",
        )
    )


async def _enrich(http: HttpClient, item: RawItem) -> str:
    """Fetch pe pagina articolului: og:image pentru poză, og:description /
    primul paragraf pentru draft. Întoarce descrierea găsită (poate fi "")."""
    resp = await http.get(item.url)
    if resp is None or resp.status_code != 200:
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")

    og_image = soup.find("meta", property="og:image") or soup.find(
        "meta", attrs={"name": "og:image"}
    )
    if og_image and og_image.get("content"):
        item.image_url = og_image["content"].strip()

    og_desc = soup.find("meta", property="og:description") or soup.find(
        "meta", attrs={"name": "description"}
    )
    if og_desc and og_desc.get("content"):
        return og_desc["content"].strip()
    first_p = soup.find("p")
    if first_p:
        return strip_html(str(first_p))[:500]
    return ""


def _truncate(text: str, limit: int = 300) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


async def run_pull(only: set[str] | None = None) -> PullReport | None:
    """Rulează un pull complet. Întoarce None dacă un pull e deja în curs.
    `only` (set de sluguri) limitează sursele — util la teste."""
    if _pull_lock.locked():
        return None
    async with _pull_lock:
        http = HttpClient()
        report = PullReport()
        try:
            await _do_pull(http, report, only)
        finally:
            await http.close()
        logger.info(
            "Pull încheiat: %d noi, %d filtrate, %d duplicate, %d erori de sursă.",
            report.new,
            report.filtered,
            report.duplicates,
            len(report.errors),
        )
        return report


async def _do_pull(http: HttpClient, report: PullReport, only: set[str] | None) -> None:
    sources = [
        cls(http) for cls in ACTIVE_SOURCES if only is None or cls.name in only
    ]

    results = await asyncio.gather(
        *(source.fetch() for source in sources), return_exceptions=True
    )
    all_items: list[RawItem] = []
    for source, result in zip(sources, results):
        if isinstance(result, BaseException):
            logger.error("Sursa %s a eșuat: %s", source.name, result)
            report.errors[source.display_name] = str(result)[:200] or type(result).__name__
        else:
            logger.info("Sursa %s: %d iteme brute", source.name, len(result))
            all_items.extend(result)

    for item in all_items:
        item.url = normalize_url(item.url)

    # 1. URL-uri deja văzute
    known = await db.scraped_known_urls([item.url for item in all_items])
    fresh = []
    seen_in_batch: set[str] = set()
    for item in all_items:
        if item.url in known or item.url in seen_in_batch:
            report.duplicates += 1
            continue
        seen_in_batch.add(item.url)
        fresh.append(item)

    # 2. Deduplicare fuzzy în interiorul batch-ului (câștigă sursa prioritară)
    fresh.sort(key=lambda item: SOURCE_PRIORITIES.get(item.source, 99))
    kept: list[RawItem] = []
    for item in fresh:
        duplicate_of = next(
            (
                existing
                for existing in kept
                if fuzz.token_set_ratio(
                    ai_filter._fold(existing.title), ai_filter._fold(item.title)
                )
                >= FUZZY_THRESHOLD
            ),
            None,
        )
        if duplicate_of is not None:
            duplicate_of.extra_urls.append(item.url)
            report.duplicates += 1
        else:
            kept.append(item)

    # 3. Deduplicare fuzzy față de itemele din DB (ultimele 30 de zile)
    recent = await db.recent_scraped_titles(days=30)
    survivors: list[RawItem] = []
    for item in kept:
        db_duplicate = next(
            (
                row
                for row in recent
                if fuzz.token_set_ratio(
                    ai_filter._fold(row["title"]), ai_filter._fold(item.title)
                )
                >= FUZZY_THRESHOLD
            ),
            None,
        )
        if db_duplicate is not None:
            await db.append_extra_urls(db_duplicate["id"], [item.url] + item.extra_urls)
            report.duplicates += 1
        else:
            survivors.append(item)

    # 4. Filtrare relevanță → îmbogățire → (AI) → insert
    for item in survivors:
        kind = SOURCE_KINDS.get(item.source, "news")
        score = ai_filter.score_for(kind, item.title, item.summary)
        if score < ai_filter.THRESHOLD:
            report.filtered += 1
            logger.info(
                "Filtrat (scor %.1f < %.1f): [%s] %s",
                score,
                ai_filter.THRESHOLD,
                item.source,
                item.title,
            )
            continue

        # sursele "product" vin de regulă cu imagine și rezumat gata puse
        og_description = ""
        if not item.image_url or not item.summary:
            og_description = await _enrich(http, item)
        base_text = item.summary or og_description

        draft = None
        if ai_filter.ai_enabled():
            relevant, draft = await ai_filter.ai_evaluate(item.title, base_text, kind)
            if not relevant:
                report.filtered += 1
                logger.info("Filtrat de AI: [%s] %s", item.source, item.title)
                continue
        if not draft:
            draft = _truncate(og_description or item.summary or item.title)

        new_id = await db.insert_scraped_item(
            source=item.source,
            title=item.title,
            url=item.url,
            extra_urls=json.dumps(item.extra_urls),
            published_at=item.published_at,
            summary=item.summary or og_description,
            draft_description=draft,
            image_url=item.image_url,
            relevance_score=score,
            meta=json.dumps(item.meta),
        )
        if new_id is None:  # conflict pe URL (inserat între timp)
            report.duplicates += 1
            continue
        report.new += 1
        report.per_source[item.source] = report.per_source.get(item.source, 0) + 1
        logger.info("Item nou #%d în inbox: [%s] %s", new_id, item.source, item.title)
