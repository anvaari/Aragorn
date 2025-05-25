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

    @property
    def datetime(self):
        """
        Returns the event's date and time as a single concatenated string.
        """
        return f"{self.date} {self.time}"
    
    @property
    def google_calendar_link(self):
        """
        Generates a Google Calendar event link for the event.
        
        Returns:
            A URL string that allows users to add the event to their Google Calendar, using the event's datetime, title, and location.
        """
        return event_to_google_calendar_link(self.datetime,self.title,self.location)