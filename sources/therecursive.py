"""The Recursive — doar articolele despre România.

Preferă feed-ul dedicat pe tag (deja filtrat); dacă dispare, cade pe feedul
general cu filtrare după tag/link.
"""

from .base import RawItem, RssSource

TAG_FEED = "https://www.therecursive.com/tag/romania/feed/"


class TheRecursive(RssSource):
    name = "therecursive"
    display_name = "The Recursive"
    priority = 1
    feed_candidates = ["https://therecursive.com/feed/"]
    listing_url = "https://therecursive.com/country/romania/"
    listing_pattern = r"therecursive\.com/[a-z0-9-]{15,}/?$"

    def item_filter(self, entry) -> bool:
        haystack = " ".join(
            [entry.get("link", "")]
            + [tag.get("term", "") for tag in entry.get("tags", []) or []]
        ).lower()
        return "romania" in haystack or "românia" in haystack

    async def fetch(self) -> list[RawItem]:
        # feed-ul pe tag e deja filtrat pe România — nu mai aplicăm item_filter
        entries = await self.fetch_feed(TAG_FEED)
        if entries:
            items = [self.entry_to_item(entry) for entry in entries[: self.MAX_ITEMS]]
            return [item for item in items if item]
        return await super().fetch()
