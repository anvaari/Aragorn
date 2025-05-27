from models.event import EventCreate
import re

def format_event_for_telegram(event:EventCreate) -> str:
    """
    Formats an event as a Markdown message suitable for Telegram.
    
    The returned string includes the event's title, date and time, location (as a Google Maps link if coordinates are provided, otherwise as plain text), performers, ticket information, Instagram link, and Google Calendar link, all formatted for Telegram's Markdown display.
    
    Args:
        event: The event data to format.
    
    Returns:
        A Markdown-formatted string representing the event for Telegram messages.
    """
    loc_pattern = r'^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?),\s*[-+]?(180(\.0+)?|((1[0-7]\d)|(\d{1,2}))(\.\d+)?)$'
    if re.match(loc_pattern,event.location):
        loc = f"*[لینک گوگل مپ](https://www.google.com/maps?q={event.location})*"
    else: 
        loc = f"""*محل برگزاری*: 
            {event.location}"""
    
    msg = f"""
    🎤 *{event.title}*


    🗓️ *زمان:* 
        {event.datetime}

    📍 {loc}

    👥 *هنرمندان*: 
        {event.performers}

    🎟️ *نحوه خرید بلیط*: 
        {event.ticket_info}

    📸 [لینک اینستاگرام]({event.instagram_link})

    📅 [افزودن به تقویم گوگل]({event.google_calendar_link})
    """
    return msg
