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
        _client = OpenAI(api_key=key)
    return _client
