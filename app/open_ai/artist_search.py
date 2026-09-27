import json

from open_ai.gpt import get_openai_client
from core.config import app_settings
from log.logger import get_app_logger

logger = get_app_logger(__name__)

def _artist_model() -> str:
    return app_settings.openai_artist_model or app_settings.openai_text_model

def search_artist_web(name: str) -> dict | None:
    """Resolve a performer name to a canonical identity via LLM + web search.

    Returns {"name", "name_en", "ig_handle", "bio", "source_url", "confidence"}
    (confidence 0..1), or None when the call itself failed.
    """
    client = get_openai_client()
    prompt = f"""
Search the web to identify the music artist "{name}". The name may be Persian or
English and may contain OCR errors; they perform independent music, likely in Iran.

Return ONLY a JSON object with exactly these fields:

{{
"name": "canonical name as the artist is officially known (Persian if Persian-speaking)",
"name_en": "official latin spelling if determinable, else \\"\\"",
"ig_handle": "instagram username if confidently found, else \\"\\"",
"bio": "one short sentence in Persian describing the artist and their music, else \\"\\"",
"source_url": "URL of the page you relied on, else \\"\\"",
"confidence": 0.0
}}

Rules:

* Many independent Iranian artists have little or no web presence. If you cannot
  confidently identify THIS artist, return confidence <= 0.3 and empty fields.
* Do not guess from the name alone. Only claim identity if search results clearly match.
* Never merge two different artists with similar names; when in doubt, low confidence.
* confidence must be a number between 0 and 1.
"""
    try:
        response = client.responses.create(
            model=_artist_model(),
            tools=[{"type": "web_search"}],
            input=[{"role": "user", "content": prompt}],
        )
    except Exception:
        logger.error(f"Artist web search call failed for name={name!r}",exc_info=True)
        return None

    raw = response.output_text
    if not raw:
        logger.warning(f"Artist web search returned empty output for name={name!r}")
        return None
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
    except Exception:
        logger.error(f"Can't decode artist search output for name={name!r}.\noutput: {raw}",exc_info=True)
        return None
    try:
        result["confidence"] = float(result.get("confidence") or 0)
    except (TypeError, ValueError):
        result["confidence"] = 0
    return result