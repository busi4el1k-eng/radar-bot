"""Startarium — articole din secțiunea Explore (nu are RSS clasic)."""

from .base import RawItem, Source


class Startarium(Source):
    name = "startarium"
    display_name = "Startarium"
    priority = 4

    listing_candidates = [
        "https://startarium.com/explore/articles",
        "https://www.startarium.ro/explore/articles",
        "https://startarium.ro/explore/articles",
    ]

    async def fetch(self) -> list[RawItem]:
        for url in self.listing_candidates:
            items = await self.fetch_listing(url, r"/explore/articles/[a-z0-9-]{5,}")
            if items:
                return items
        return []
