from models.event import EventCreate

def format_event_for_telegram(event:EventCreate) -> str:
    msg = f"""
    🎤 {event.title}
    🗓️ زمان: {event.datetime}
    📍 [لینک گوگل مپ](https://www.google.com/maps?q={event.location})
    👥 هنرمندان: {event.performers}
    🎟️ نحوه خرید بلیط: {event.ticket_info}
    📸 [لینک اینستاگرام]({event.instagram_link})
    📅 [افزودن به تقویم گوگل]({event.google_calendar_link})
    """
    return msg
