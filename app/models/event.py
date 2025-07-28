from pydantic import BaseModel
from utils.google_calendar import event_to_google_calendar_link
class EventCreate(BaseModel):
    title: str
    date: str
    time: str
    description: str
    location: str
    performers: str
    ticket_info: str
    instagram_link: str

    @property
    def datetime(self):
        return f"{self.date} {self.time}"
    
    @property
    def google_calendar_link(self):
        return event_to_google_calendar_link(self.datetime,self.title,self.location)