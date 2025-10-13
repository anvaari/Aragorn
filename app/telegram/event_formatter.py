from models.event import EventCreate
import re

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

    📸 [لینک اینستاگرام]({event.instagram_link})

    📅 [افزودن به تقویم گوگل]({event.google_calendar_link})
    """
    msg_escaped = msg.replace('_','\\_')
    return msg_escaped
