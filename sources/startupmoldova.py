"""Startup Moldova — știri din ecosistemul de startup-uri moldovenesc."""

from .base import RssSource


class StartupMoldova(RssSource):
    name = "startupmoldova"
    display_name = "Startup Moldova"
    priority = 6
    feed_candidates = [
        "https://www.startupmoldova.digital/feed/",
        "https://startupmoldova.digital/feed/",
    ]
    listing_url = "https://www.startupmoldova.digital/"
    listing_pattern = r"startupmoldova\.digital/[a-z0-9-]{10,}"
