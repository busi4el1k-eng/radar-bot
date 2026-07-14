"""Infrastructura comună a surselor: clasa Source, RawItem și clientul HTTP.

Reguli de politețe: max 1 request/secundă per domeniu, robots.txt respectat,
timeout și User-Agent setate. Orice eroare de rețea e izolată — o sursă căzută
nu oprește restul.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# UA de browser: unele surse (ex. EU-Startups) răspund 403 la UA-uri de bot.
# Rămânem politicoși prin rate limit (1 req/s/domeniu) și robots.txt.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class RawItem:
    source: str
    title: str
    url: str
    published_at: datetime | None = None
    summary: str = ""
    image_url: str | None = None
    extra_urls: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)  # ex: stars, languages, homepage


class HttpClient:
    """Client HTTP partajat de toate sursele într-un pull."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}

    async def close(self) -> None:
        await self._client.aclose()

    async def _throttle(self, host: str) -> None:
        while True:
            now = time.monotonic()
            wait = 1.0 - (now - self._last_request.get(host, 0.0))
            if wait <= 0:
                self._last_request[host] = now
                return
            await asyncio.sleep(wait)

    async def _get_robots(self, scheme: str, host: str) -> RobotFileParser | None:
        if host in self._robots:
            return self._robots[host]
        rp = None
        try:
            await self._throttle(host)
            resp = await self._client.get(f"{scheme or 'https'}://{host}/robots.txt")
            if resp.status_code == 200:
                rp = RobotFileParser()
                rp.parse(resp.text.splitlines())
        except httpx.HTTPError:
            rp = None  # robots.txt inaccesibil → nu blocăm
        self._robots[host] = rp
        return rp

    async def get(self, url: str) -> httpx.Response | None:
        parsed = urlparse(url)
        rp = await self._get_robots(parsed.scheme, parsed.netloc)
        if rp is not None and not rp.can_fetch(USER_AGENT, url):
            logger.info("robots.txt interzice accesul la %s", url)
            return None
        await self._throttle(parsed.netloc)
        try:
            return await self._client.get(url)
        except httpx.HTTPError as exc:
            logger.warning("Cerere eșuată către %s: %s", url, exc)
            return None


def strip_html(text: str) -> str:
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


class Source:
    """Clasa de bază. O sursă nouă = un fișier nou care o moștenește
    (sau moștenește RssSource) + o linie în ACTIVE_SOURCES din __init__.py."""

    name = "base"          # slug, salvat în DB
    display_name = "Base"  # numele afișat în postare („Sursa: ...”)
    priority = 99          # mai mic = câștigă la deduplicare
    kind = "news"          # "news" (articole de presă) sau "product" (produsul în sine)

    MAX_ITEMS = 30

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    async def fetch(self) -> list[RawItem]:
        raise NotImplementedError

    # ── utilitare comune ────────────────────────────────────────────────────

    async def fetch_feed(self, feed_url: str) -> list:
        resp = await self.http.get(feed_url)
        if resp is None or resp.status_code != 200:
            return []
        parsed = feedparser.parse(resp.content)
        return list(parsed.entries)

    def entry_to_item(self, entry) -> RawItem | None:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            return None
        summary = strip_html(entry.get("summary") or entry.get("description") or "")[:1000]
        published = None
        parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed_time:
            published = datetime(*parsed_time[:6], tzinfo=timezone.utc)
        image = None
        for media in entry.get("media_content", []) or []:
            if media.get("url"):
                image = media["url"]
                break
        for link_info in entry.get("links", []) or []:
            if link_info.get("rel") == "enclosure" and str(
                link_info.get("type", "")
            ).startswith("image"):
                image = link_info.get("href")
        return RawItem(
            source=self.name,
            title=title,
            url=link,
            published_at=published,
            summary=summary,
            image_url=image,
        )

    async def fetch_listing(self, page_url: str, link_pattern: str) -> list[RawItem]:
        """Fallback fără RSS: extrage linkurile de articole dintr-o pagină de listing."""
        resp = await self.http.get(page_url)
        if resp is None or resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        found: dict[str, str] = {}
        for anchor in soup.find_all("a", href=True):
            href = urljoin(page_url, anchor["href"]).split("#")[0]
            if not re.search(link_pattern, href):
                continue
            title = anchor.get_text(" ", strip=True)
            # păstrăm cel mai lung text de ancoră pentru același link
            # (evită „Citește mai mult” în locul titlului)
            if len(title) >= 15 and len(title) > len(found.get(href, "")):
                found[href] = title
        return [
            RawItem(source=self.name, title=title, url=url)
            for url, title in list(found.items())[: self.MAX_ITEMS]
        ]


class RssSource(Source):
    """Sursă RSS standard: încearcă pe rând feed-urile candidate,
    iar dacă niciunul nu merge, cade pe parsarea paginii de listing."""

    feed_candidates: list[str] = []
    listing_url: str | None = None
    listing_pattern: str = ""

    def item_filter(self, entry) -> bool:
        return True

    async def fetch(self) -> list[RawItem]:
        for feed_url in self.feed_candidates:
            entries = await self.fetch_feed(feed_url)
            if entries:
                items = [
                    self.entry_to_item(entry)
                    for entry in entries[: self.MAX_ITEMS]
                    if self.item_filter(entry)
                ]
                return [item for item in items if item]
        if self.listing_url and self.listing_pattern:
            logger.info(
                "Sursa %s: niciun feed RSS funcțional, folosesc parsarea listing-ului",
                self.name,
            )
            return await self.fetch_listing(self.listing_url, self.listing_pattern)
        return []
