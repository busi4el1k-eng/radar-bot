"""EU-Startups — articolele cu tag-ul „Romania-Startups”.

Feed-ul per categorie și paginile HTML sunt blocate de Cloudflare, dar feedul
general funcționează; filtrăm după tag-urile de țară.
"""

from .base import RssSource


class EuStartups(RssSource):
    name = "eustartups"
    display_name = "EU-Startups"
    priority = 5
    feed_candidates = [
        "https://www.eu-startups.com/category/romania/feed/",
        "https://www.eu-startups.com/feed/",
        "http://feeds.feedburner.com/eu-startups",
    ]
    listing_url = "https://www.eu-startups.com/category/romania/"
    listing_pattern = r"eu-startups\.com/\d{4}/\d{2}/[a-z0-9-]{10,}"

    def item_filter(self, entry) -> bool:
        haystack = " ".join(
            [entry.get("link", "")]
            + [tag.get("term", "") for tag in entry.get("tags", []) or []]
        ).lower()
        return "romania" in haystack or "moldova" in haystack
