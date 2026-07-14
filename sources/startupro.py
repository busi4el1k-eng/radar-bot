"""start-up.ro — știri și articole despre ecosistemul de startup-uri din România."""

from .base import RssSource


class StartUpRo(RssSource):
    name = "startupro"
    display_name = "start-up.ro"
    priority = 3
    feed_candidates = [
        "https://start-up.ro/feed/",
        "https://start-up.ro/feed",
        "https://start-up.ro/rss",
    ]
    listing_url = "https://start-up.ro/"
    listing_pattern = r"start-up\.ro/[a-z0-9-]{15,}"
