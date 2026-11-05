import json

from open_ai.gpt import get_openai_client
from core.config import app_settings
from log.logger import get_app_logger

logger = get_app_logger(__name__)

def _artist_model() -> str:
    return app_settings.openai_artist_model or app_settings.openai_text_model

def summarize_artist(name: str, event_lines: list[str], co_performers: list[str]) -> str | None:
    """Persian summary of the artist's event history: event types, instruments,
    and frequent co-performers. Derived ONLY from the supplied local data."""
    client = get_openai_client()
    events_block = "\n".join(event_lines)
    co_block = "، ".join(co_performers) if co_performers else ""
    prompt = f"""
Based ONLY on the following recorded events of the music artist "{name}", write a
short summary in Persian (۲-۳ جمله) about:
- the type of events/concerts they usually participate in,
- the instruments or role they play (if inferable),
- the artists they often perform with.

Events (title | date | location | performers):
{events_block}
{"Known co-performers: " + co_block if co_block else ""}

Rules:

* Use only the information above; do not invent or add outside knowledge.
* Natural, friendly Persian prose (no markdown, no bullet lists, no headings).
* If the events are too few to say anything meaningful, still write one short sentence.
Return ONLY the summary text.
"""
    try:
        response = client.chat.completions.create(
            model=_artist_model(),
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        logger.error(f"Artist summary call failed for name={name!r}",exc_info=True)
        return None
    summary = (response.choices[0].message.content or "").strip()
    if not summary:
        logger.warning(f"Artist summary returned empty output for name={name!r}")
        return None
    return summary

def normalize_artist_names(names: list[str]) -> dict[str, str] | None:
    """Map each performer name to its Latin (English) spelling: the official
    spelling when the artist is known, else a faithful transliteration.
    Empty value = not a plausible artist/performer name (OCR noise etc.).
    One chat completion for the whole chunk; None when the call failed."""

    if not names:
        return {}
    client = get_openai_client()
    listing = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(names))
    prompt = f"""
Below is a numbered list of performer names taken from Persian independent-music
event posters. They may be in Persian script or garbled OCR text.

For EACH name return its Latin (English) spelling:
* the spelling the artist is officially known by, if you recognize the artist;
* otherwise a faithful transliteration of the Persian name;
* an EMPTY string "" if the text is not a plausible performer or band name
  (instrument words, parenthesized fragments, venue names, dates, noise).

Return ONLY a JSON object mapping the list number (as a string) to the result, e.g.
{{"1": "Mohammad Reza", "2": "", "3": "Sun Spots Band"}}

Names:
{listing}
"""
    try:
        response = client.chat.completions.create(
            model=_artist_model(),
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        logger.error(f"Artist name normalization call failed for {len(names)} names",exc_info=True)
        return None
    raw = (response.choices[0].message.content or "").strip()
    if not raw:
        logger.warning("Artist name normalization returned empty output")
        return None
    try:
        text = raw
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        numbered = json.loads(text)
    except Exception:
        logger.error(f"Can't decode normalization output.\noutput: {raw}",exc_info=True)
        return None
    result: dict[str, str] = {}
    for i, name in enumerate(names):
        value = numbered.get(str(i + 1)) or numbered.get(name) or ""
        result[name] = str(value).strip()
    return result

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