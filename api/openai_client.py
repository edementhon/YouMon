from __future__ import annotations
import os
from openai import OpenAI
import config

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        key = config.load_api_key()
        if not key:
            raise RuntimeError(
                "OpenAI API key not found. Set the OPENAI_API_KEY environment "
                "variable or add {\"openai_api_key\": \"sk-...\"} to config.json"
            )
        # Applied to the environment rather than passed to httpx, because the
        # keyword for this changed between httpx versions (proxies= then
        # proxy=) and the machines this runs on do not share a version.
        # httpx reads the environment when a client is constructed.
        proxy = config.load_proxy()
        if proxy:
            os.environ.setdefault("HTTPS_PROXY", proxy)
            os.environ.setdefault("https_proxy", proxy)
        _client = OpenAI(api_key=key)
    return _client
