from db import crud_artist
from log.logger import get_app_logger
from open_ai.artist_search import search_artist_web

logger = get_app_logger(__name__)

_MAX_ATTEMPTS = 3
_CONFIDENCE_THRESHOLD = 0.5

def link_event_artists(event_id: int, performer_names: list[str]) -> None:
    """Find-or-create artist rows for each performer name and link them to the event."""
    for raw_name in performer_names:
        raw_name = raw_name.strip()
        if not raw_name:
            continue
        try:
            normalized = crud_artist.normalize_name(raw_name)
            artist_id = crud_artist.find_artist_by_normalized_name(normalized)
            if artist_id is None:
                artist_id = crud_artist.create_artist(raw_name)
            if artist_id is None:
                continue
            crud_artist.link_event_artist(event_id, artist_id, raw_name)
        except Exception:
            logger.error(f"Can't link performer {raw_name!r} to event {event_id}",exc_info=True)

def enrich_pending_artists(batch_size: int = 5) -> dict:
    """Resolve unresolved artist names via web search (cached: each artist once ever).

    Rows that fail repeatedly stay unresolved and are skipped by the sweep once
    their attempts reach the cap.
    """
    pending = crud_artist.get_unresolved_artists(limit=batch_size)
    resolved, failed = 0, 0
    for artist in pending:
        if artist["attempts"] >= _MAX_ATTEMPTS:
            continue
        result = search_artist_web(artist["name"])
        if (result
                and result.get("source_url")
                and result.get("name")
                and result.get("confidence", 0) >= _CONFIDENCE_THRESHOLD):
            crud_artist.update_artist_resolution(
                artist["id"],
                name=result["name"],
                name_en=result.get("name_en") or "",
                ig_handle=result.get("ig_handle") or "",
                bio=result.get("bio") or "",
                source_url=result["source_url"],
            )
            resolved += 1
            logger.info(f"Artist resolved: {artist['name']!r} -> {result['name']!r} (source: {result['source_url']})")
        else:
            crud_artist.increment_artist_attempts(artist["id"])
            failed += 1
            logger.info(f"Artist unresolved (attempt {artist['attempts'] + 1}/{_MAX_ATTEMPTS}): {artist['name']!r}")
    return {"pending": len(pending), "resolved": resolved, "failed": failed}