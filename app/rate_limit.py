import time
from collections import defaultdict, deque

REQUEST_WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 10

_requests = defaultdict(deque)


def is_rate_limited(client_id: str) -> bool:
    now = time.time()
    bucket = _requests[client_id]

    while bucket and (now - bucket[0]) > REQUEST_WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= MAX_REQUESTS_PER_WINDOW:
        return True

    bucket.append(now)
    return False