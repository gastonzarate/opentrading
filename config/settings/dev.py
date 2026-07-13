from .base import *  # noqa

# Local dev hosts. The container binds 0.0.0.0 and probes (e.g. MCP OAuth
# discovery at /.well-known/...) hit it with Host "0.0.0.0:8099", which isn't
# auto-allowed even under DEBUG and floods the logs with DisallowedHost
# tracebacks. Allow the local hosts explicitly (extends any from the env).
# The leading-dot entries are Django wildcards that match a domain and all its
# subdomains, so exposing the dashboard through a dev tunnel (Cloudflare Quick
# Tunnel, ngrok) works without re-adding the random hostname each run.
ALLOWED_HOSTS = list(ALLOWED_HOSTS) + [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "[::1]",
    ".trycloudflare.com",
    ".ngrok-free.app",
    ".ngrok.io",
    ".ngrok.app",
]  # noqa

# # MEDIA
# ------------------------------------------------------------------------------
MEDIA_ROOT = str(ROOT_DIR("media"))  # noqa
MEDIA_URL = "/media/"
