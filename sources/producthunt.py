"""Product Hunt — lansările zilei (feed RSS oficial)."""

from .base import RssSource


class ProductHunt(RssSource):
    name = "producthunt"
    display_name = "Product Hunt"
    priority = 2
    kind = "product"
    feed_candidates = ["https://www.producthunt.com/feed"]
