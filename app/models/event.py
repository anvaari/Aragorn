from pydantic import BaseModel
from utils.google_calendar import event_to_google_calendar_link
class EventCreate(BaseModel):
    title: str
    date: str
    time: str
    location: str
    performers: str
    ticket_info: str
    instagram_link: str
    datetime: str = ""
    google_calendar_link: str = ""

    def model_post_init(self, __context):
        self.datetime = f"{self.date} {self.time}"
        self.google_calendar_link = event_to_google_calendar_link(self.datetime,self.title,self.location)
