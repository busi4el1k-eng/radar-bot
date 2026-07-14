"""SeedBlink — campanii live de equity crowdfunding (fiecare campanie = un startup).

Site-ul e o aplicație JavaScript, deci parsarea HTML e best-effort: dacă
pagina nu expune linkuri în HTML-ul servit, sursa întoarce 0 iteme și atât.
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RawItem, Source

CAMPAIGN_RE = re.compile(r"seedblink\.com/.*(opportunit|campaign|deal)[a-z]*/[a-z0-9-]{3,}", re.I)


class SeedBlink(Source):
    name = "seedblink"
    display_name = "SeedBlink"
    priority = 9

    listing_candidates = [
        "https://seedblink.com/opportunities",
        "https://www.seedblink.com/opportunities",
        "https://seedblink.com/en/opportunities",
    ]

    async def fetch(self) -> list[RawItem]:
        for page_url in self.listing_candidates:
            resp = await self.http.get(page_url)
            if resp is None or resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            items: list[RawItem] = []
            seen: set[str] = set()
            for anchor in soup.find_all("a", href=True):
                href = urljoin(page_url, anchor["href"]).split("#")[0]
                if not CAMPAIGN_RE.search(href) or href in seen:
                    continue
                title = anchor.get_text(" ", strip=True)
                if len(title) < 3:
                    continue
                seen.add(href)
                items.append(
                    RawItem(
                        source=self.name,
                        title=title[:200],
                        url=href,
                        summary="Campanie live de equity crowdfunding pe SeedBlink.",
                    )
                )
            if items:
                return items[: self.MAX_ITEMS]
        return []
