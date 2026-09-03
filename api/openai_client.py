from __future__ import annotations
import importlib
import os
from openai import OpenAI
import config

_client = None

# Long enough for image generation, which runs about a minute and can take
# two on a high-quality render.
_HTTP_TIMEOUT = 600.0


def _proxy_http_client(proxy: str):
    """An HTTP client bound to `proxy`, whichever SDK generation is installed.

    Handing the proxy over explicitly is not optional. openai 3.x ships its own
    fork, httpx2, whose client does not read HTTPS_PROXY from the environment,
    so setting the variable looks like it works and is silently ignored: every
    request fails with a bare "Connection error" while curl through the same
    proxy succeeds. openai 2.x used httpx, and the keyword moved from proxies=
    to proxy= somewhere in between, so try the combinations rather than pin a
    version the machines do not agree on.
    """
    for module_name in ("httpx2", "httpx"):
        try:
            mod = importlib.import_module(module_name)
        except ImportError:
            continue
        for kwargs in ({"proxy": proxy}, {"proxies": proxy}):
            try:
                return mod.Client(timeout=_HTTP_TIMEOUT, **kwargs)
            except TypeError:
                continue
    return None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        key = config.load_api_key()
        if not key:
            raise RuntimeError(
                "OpenAI API key not found. Set the OPENAI_API_KEY environment "
                "variable or add {\"openai_api_key\": \"sk-...\"} to config.json"
            )

        proxy = config.load_proxy()
        http_client = _proxy_http_client(proxy) if proxy else None
        if proxy:
            # Belt and braces for anything else in the process that does read
            # the environment.
            os.environ.setdefault("HTTPS_PROXY", proxy)
            os.environ.setdefault("https_proxy", proxy)

        if http_client is not None:
            _client = OpenAI(api_key=key, http_client=http_client)
        else:
            _client = OpenAI(api_key=key)
    return _client
