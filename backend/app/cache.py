# app/cache.py
from cachetools import TTLCache

# Cache up to 1024 items, with each item expiring after 60 seconds
cache = TTLCache(maxsize=1024, ttl=60)