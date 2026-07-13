from .base import *  # noqa

# Local dev hosts. The container binds 0.0.0.0 and probes (e.g. MCP OAuth
# discovery at /.well-known/...) hit it with Host "0.0.0.0:8099", which isn't
# auto-allowed even under DEBUG and floods the logs with DisallowedHost
# tracebacks. Allow the local hosts explicitly (extends any from the env).
ALLOWED_HOSTS = list(ALLOWED_HOSTS) + ["localhost", "127.0.0.1", "0.0.0.0", "[::1]"]  # noqa

# # MEDIA
# ------------------------------------------------------------------------------
MEDIA_ROOT = str(ROOT_DIR("media"))  # noqa
MEDIA_URL = "/media/"
