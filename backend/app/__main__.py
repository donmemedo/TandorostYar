"""`python -m app` is the supported way to run the API: it pins the uvicorn settings that matter for security.

proxy_headers=False is the important one. The app resolves the client IP itself (TRUSTED_PROXY_HOPS); if uvicorn also rewrote it
from X-Forwarded-For, a client on the same host as a proxy could pick its own IP and walk around every rate limit.
One worker on purpose: the rate limiter and the snapshot cache live in process memory."""
import os

import uvicorn

if __name__ == "__main__":
    os.umask(0o077)  # the database, its WAL and any file the app writes are owner-only
    uvicorn.run(
        "app.main:create_app", factory=True, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8330")),
        proxy_headers=False, server_header=False, access_log=False, timeout_keep_alive=5, limit_concurrency=200,
        reload=os.getenv("RELOAD") == "1",
    )
