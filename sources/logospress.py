"""Logos-Press — presă de business din Moldova."""

from .base import RssSource


class LogosPress(RssSource):
    name = "logospress"
    display_name = "Logos-Press"
    priority = 8
    feed_candidates = [
        "https://logos-pres.md/feed/",
        "https://logos-press.md/feed/",
        "https://logos-pres.md/rss",
    ]
    listing_url = "https://logos-pres.md/"
    listing_pattern = r"logos-pres[s]?\.md/[a-z0-9-]{15,}"
