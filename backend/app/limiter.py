
from slowapi import Limiter
from slowapi.util import get_remote_address

# Create a shared limiter instance.
# This is for Rate Limiting
limiter = Limiter(key_func=get_remote_address)



