import json
from open_ai.gpt import get_openai_client
from core.config import app_settings
from models.event import EventCreate
from log.logger import get_app_logger
from jdatetime import date as jdate

logger = get_app_logger(__name__)

def extract_event_from_ig_text(ig_text:str) -> EventCreate:
    client = get_openai_client()
    response = client.chat.completions.create(
        model=app_settings.openai_model,
        messages=[
            {
                "role": "system", 
                "content": f"""
                Extract music event info from Persian text and return it as a JSON with these fields: 
                    title 
                        (str), 
                    date 
                        (in Shamsi calendar and YYYY-MM-DD, use {jdate.today().year} if no year specified)
                        (If there is two day, pick only one and mention it in description), 
                    time 
                        (HH:MM)
                        (If there is two time, pick only one and mention it in description),
                    location 
                        (str), 
                    performers
                        (comma separated str name with instrument in parenthesis), 
                    ticket_info 
                        (str) 
                        (information about how to buy a ticket) 
                        (phone number, whatsapp,telegram ,web link, ...), 
                    instagram_link
                        (str),
                    description
                        (str)
                        (Extra explain about event)
                        (empty string if no description needed)
                    
                If a field is missing, only use an empty string.
                """
            },
            {
                "role": "user", 
                "content": ig_text
            }
        ],
        temperature=0.2
    )
    gpt_output = response.choices[0].message.content

    if not gpt_output:
        raise ValueError(f"Output of gpt is None.\nig_text was:{ig_text}")
    
    try:
        event_dict = json.loads(gpt_output)
    except:
        # TODO: Better error handling
        logger.critical(f"Can't decode output of gpt into json.\ngpt_output: {gpt_output}",exc_info=True)
        raise ValueError(f"Can't decode output of gpt into json.\ngpt_output: {gpt_output}")
    
    try:
        event = EventCreate(**event_dict)
    except:
        logger.critical(f"Can't make event out of gpt output dict.\ngpt output dict:{event_dict}",exc_info=True)
        raise ValueError(f"Can't make event out of gpt output dict.\ngpt output dict:{event_dict}")

    return event