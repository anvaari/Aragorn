from models.event import EventCreate
from log.logger import get_app_logger
import re

logger = get_app_logger(__name__)

LOC_PATTERN = r'^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?),\s*[-+]?(180(\.0+)?|((1[0-7]\d)|(\d{1,2}))(\.\d+)?)$'

UNKNOWN_TIME = "00:01"
DIGEST_MAX_CHARS = 4000  # headroom under Telegram's 4096 hard limit

def _escape_md(text: str) -> str:
    return text.replace('_','\\_')

def format_event_for_telegram(event:EventCreate) -> str:
    loc_pattern = r'^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?),\s*[-+]?(180(\.0+)?|((1[0-7]\d)|(\d{1,2}))(\.\d+)?)$'
    if re.match(loc_pattern,event.location):
        loc = f"*[لینک گوگل مپ](https://www.google.com/maps?q={event.location})*"
    else: 
        loc = f"""*محل برگزاری*: 
            {event.location}"""
    
    if event.description:
        desc = f"""📝 *توضیحات:*
                    {event.description}"""
    else:
        desc = ""
    
    if event.instagram_link:
        insta_link = f"📸 [لینک اینستاگرام]({event.instagram_link})"
    else:
        insta_link = ""
    
    msg = f"""
    🎤 *{event.title}*


    🗓️ *زمان:* 
        {event.datetime}
    {"\n"+desc+"\n" if desc else ""}
    📍 {loc}

    👥 *هنرمندان*: 
        {event.performers}

    🎟️ *نحوه خرید بلیط*: 
        {event.ticket_info}

    📅 [افزودن به تقویم گوگل]({event.google_calendar_link})
    {"\n"+insta_link if insta_link else ""}
    """
    msg_escaped = msg.replace('_','\\_')
    return msg_escaped


def _title_line(event: EventCreate, link: str | None) -> str:
    title = _escape_md(event.title)
    if link:
        # Legacy Markdown (V1) cannot nest entities: bold around [text](url)
        # renders the raw brackets instead of a link -> no bold on linked titles.
        link_text = re.sub(r"[\[\]()]", "", title)  # legacy-Markdown [] delimiter safety
        return f"🎤 [{link_text}]({link})\n"
    return f"🎤 *{title}*\n"

def format_events_digest(events: list[EventCreate], day_label: str,
                         post_links: list[str | None] | None = None) -> str:
    post_links = list(post_links or [])
    post_links += [None] * (len(events) - len(post_links))
    event_blocks = []
    for event, link in zip(events, post_links):
        time_part = "ساعت نامشخص" if event.time == UNKNOWN_TIME else f"ساعت {event.time}"
        if re.match(LOC_PATTERN, event.location):
            location = f"[لینک گوگل مپ](https://www.google.com/maps?q={event.location})"
        else:
            location = _escape_md(event.location)
        block = _title_line(event, link)
        block += f"🕐 {time_part} | 📍 {location}\n"
        if event.instagram_link:
            block += f"📸 [لینک اینستاگرام]({event.instagram_link})\n"
        event_blocks.append(block)

    header = f"🗓️ *رویدادهای {day_label}*\n"
    text = header
    included = 0
    for block in event_blocks:
        if included and len(text) + len(block) + 1 > DIGEST_MAX_CHARS:
            break
        text += "\n" + block
        included += 1

    omitted = len(events) - included
    if omitted > 0:
        logger.warning(f"Digest truncated: {omitted} of {len(events)} events omitted (4096 char limit)")
        text += f"\n… و {omitted} رویداد دیگر\n"
    return text
