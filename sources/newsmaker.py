"""NewsMaker.md (secțiunea în română) — filtrul de relevanță elimină politica."""

from .base import RssSource


class NewsMaker(RssSource):
    name = "newsmaker"
    display_name = "NewsMaker.md"
    priority = 7
    feed_candidates = [
        "https://newsmaker.md/ro/feed/",
        "https://newsmaker.md/feed/",
    ]
    listing_url = "https://newsmaker.md/ro/"
    listing_pattern = r"newsmaker\.md/ro/[a-z0-9-]{15,}"
