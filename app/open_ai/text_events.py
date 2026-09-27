import json
import difflib
from datetime import timedelta
from open_ai.gpt import get_openai_client
from core.config import app_settings
from models.event import EventCreate
from log.logger import get_app_logger
from jdatetime import date as jdate

logger = get_app_logger(__name__)

# jdatetime weekday numbers: Saturday=0 ... Friday=6
_WEEKDAY_NUMBERS = {
    "شنبه": 0,
    "یکشنبه": 1,
    "دوشنبه": 2,
    "سهشنبه": 3,
    "چهارشنبه": 4,
    "پنجشنبه": 5,
    "جمعه": 6,
}

def _resolve_weekday_date(value:str) -> str:
    """Replace a bare Persian weekday name in the date field with the Shamsi
    date of its next occurrence (today counts as a match). Fuzzy matching
    absorbs OCR errors like چهارشنیه, Arabic ي/ك, and spaced forms like
    "پنج شنبه". Values that don't look like a weekday are returned unchanged.
    """
    if not value or any(ch.isdigit() for ch in value):
        return value
    token = value.replace("ي", "ی").replace("ك", "ک").replace("‌", "").replace(" ", "").strip()
    match = difflib.get_close_matches(token, _WEEKDAY_NUMBERS.keys(), n=1, cutoff=0.7)
    if not match:
        return value
    days_ahead = (_WEEKDAY_NUMBERS[match[0]] - jdate.today().weekday()) % 7
    return (jdate.today() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

def extract_event_from_ig_text(ig_text:str) -> EventCreate:
    client = get_openai_client()
    response = client.chat.completions.create(
        model=app_settings.openai_text_model,
        messages=[
            {
                "role": "system", 
                "content": f"""
Extract the music event information from the provided Persian text and return ONLY a JSON object matching the required schema.

The text may have been extracted from an Instagram image, poster, or flyer using OCR. It may contain OCR errors, Persian/Arabic characters, Persian digits, missing punctuation, duplicated text, emojis, hashtags, and irrelevant promotional text.

Your job is to identify the actual music event information from the text. Do not invent or infer information that is not supported by the text.

## General rules

* Extract information only from the provided text.
* Do not hallucinate missing information.
* If a field cannot be determined from the text, return an empty string `""`.
* Normalize Persian and Arabic digits to Western digits where appropriate.
* Ignore hashtags, emojis, decorative text, and unrelated promotional content unless they contain useful event information.
* Preserve proper names as they appear in the text, but normalize obvious OCR mistakes when the intended name is clear.
* Do not translate Persian names or event titles into English.
* Do not add information based on general knowledge.
* If information is ambiguous, prefer the interpretation directly supported by the text.

## Fields

### title

Generate a short, appropriate title for the music event.

Rules:

* Use the event/concert name if explicitly provided.
* Otherwise, construct a natural title using the main performer(s) and type of event.
* Do not include the date, time, ticket price, or unnecessary promotional phrases in the title.
* Do not invent a name for the event.

Type: string

### date

Return the event date in the Persian Shamsi (Jalali) calendar using exactly:

`YYYY-MM-DD`

Rules:

* Use the Shamsi/Jalali calendar, not the Gregorian calendar.
* If the year is not explicitly mentioned, use `{jdate.today().year}`.
* If the month is not explicitly mentioned but can be determined from the surrounding date information, use that month.
* If the month is genuinely missing, use `{jdate.today().month}`.
* If the day of the month is missing but a Persian weekday name (e.g. شنبه, چهارشنبه) is the only date clue in the text, return that weekday name in Persian as the value of `date` (for example `"چهارشنبه"`). Do NOT try to convert it to a calendar date yourself.
* Convert Persian and Arabic digits to Western digits.
* If the text contains multiple event dates, select ONE date according to these rules:

  1. Prefer the date explicitly associated with the performance/event.
  2. If several dates clearly represent multiple performances of the same event, select the first performance date.
  3. Mention the other date(s) in `description`.
* Do not include multiple dates in this field.
* If no date can be determined, return `""`.

Type: string

### time

Return the event start time using exactly:

`HH:MM`

Rules:

* Convert Persian/Arabic digits to Western digits.
* Use 24-hour format.
* If AM/PM or Persian equivalents are explicitly stated, convert them appropriately.
* If multiple times are present, select the performance/start time.
* Do not use ticket-sale time, doors-open time, or unrelated times when a performance time is available.
* If multiple performance times are given, select the first performance time and mention the other time(s) in `description`.
* If the event time cannot be found, return `00:01` and explicitly mention in `description` that the event time was not found in the provided text.

Type: string

### location

Extract the location/venue where the music performance takes place.

Rules:

* Prefer the venue name.
* Include useful location details when explicitly provided, such as hall name, theater name, cultural center, or address.
* Do not confuse the ticket-sales location with the performance location.
* Do not invent or normalize an address that is not present in the text.
* If the performance location cannot be determined, return `""`.

Type: string

### performers

Return the performers as a comma-separated string.

Rules:

* Include singers, musicians, bands, DJs, ensembles, or other explicitly identified performers.
* If an instrument is explicitly associated with a performer, use:
  `Name (Instrument)`
* If an instrument is not explicitly stated, use only:
  `Name`
* NEVER infer an instrument from the performer's profession, name, band role, or general knowledge.
* Do not invent instruments.
* Do not include organizers, sponsors, presenters, photographers, venue staff, or ticket sellers as performers unless the text explicitly identifies them as performers.
* Preserve multiple performers in the order they appear in the text.

Example:
`Ali X (Guitar), Sara Y (Vocals), ABC Band`

Type: string

### ticket_info

Extract information about how to purchase or reserve tickets.

Include information such as:

* Ticket website or URL
* Ticketing platform
* Phone number
* WhatsApp
* Telegram
* Instagram contact
* In-person ticket purchase information
* Reservation instructions
* Explicit ticket price if it is directly connected to purchasing the ticket

Rules:

* Preserve URLs when present.
* Preserve phone numbers when present.
* Do not confuse the event's Instagram page with ticket information unless the text explicitly says tickets can be purchased/contacted there.
* If there is no ticket purchasing information, return `""`.

Type: string

### instagram_link

Identify the Instagram page associated with the event.

Rules:

* The Instagram username is usually located near the beginning of the text, but do not assume that every username is the event's Instagram page.
* Look for explicit Instagram handles, `@username`, Instagram URLs, or clearly identified page/account names.
* If a username is found, return it as:
  `https://instagram.com/username`
* Remove `@` from the username when constructing the URL.
* If an Instagram URL is already present, normalize it to:
  `https://instagram.com/username`
* Do not include query parameters, trailing `/`, or unrelated Instagram URLs.
* If no event-related Instagram account can be identified, return `""`.

Type: string

### description

Provide additional useful information about the event that does not belong in the other fields.

Rules:

* Keep it concise.
* Do not simply repeat the other fields.
* Include important information such as:

  * Additional event dates
  * Additional performance times
  * Time not found
  * Important ticket/reservation instructions not suitable for `ticket_info`
  * Special event information explicitly stated in the text
* If there is nothing useful to add, return `""`.

Do not invent information for the description.

## Important ambiguity rules

When the text contains multiple possible values:

* Select only ONE `date`.
* Select only ONE `time`.
* Put the additional relevant date/time information in `description`.
* Prefer values explicitly associated with the performance itself.
* Never combine unrelated dates or times.
* Never guess when the text does not provide enough information.

## Output

Return ONLY the JSON object.

The JSON must contain exactly these fields:

{{
"title": "",
"date": "",
"time": "",
"location": "",
"performers": "",
"ticket_info": "",
"instagram_link": "",
"description": ""
}}                           
"""
            },
            {
                "role": "user", 
                "content": ig_text
            }
        ]
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

    event_dict["date"] = _resolve_weekday_date(event_dict.get("date", ""))

    try:
        event = EventCreate(**event_dict)
    except:
        logger.critical(f"Can't make event out of gpt output dict.\ngpt output dict:{event_dict}",exc_info=True)
        raise ValueError(f"Can't make event out of gpt output dict.\ngpt output dict:{event_dict}")

    return event