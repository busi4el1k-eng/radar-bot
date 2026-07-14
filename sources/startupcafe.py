"""StartupCafe.ro — știri despre antreprenoriat și startup-uri românești."""

from .base import RssSource


class StartupCafe(RssSource):
    name = "startupcafe"
    display_name = "StartupCafe.ro"
    priority = 2
    feed_candidates = [
        "https://www.startupcafe.ro/rss",
        "https://www.startupcafe.ro/feed",
        "https://www.startupcafe.ro/feed/",
        "https://startupcafe.ro/rss",
    ]
    listing_url = "https://www.startupcafe.ro/"
    listing_pattern = r"startupcafe\.ro/[a-z0-9-]+/[a-z0-9-]{15,}"
