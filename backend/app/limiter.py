# --- File: app/limiter.py ---

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create a shared limiter instance.
# This will import the instance into both main.py and route files.
limiter = Limiter(key_func=get_remote_address)