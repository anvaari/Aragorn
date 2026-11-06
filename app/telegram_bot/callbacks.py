from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="menu"):
    action: str  # "events" | "reminders"


class DayCB(CallbackData, prefix="day"):
    offset: int  # day_offset from today (digest_timezone)


class EventCB(CallbackData, prefix="evt"):
    event_id: int


class RemindSetCB(CallbackData, prefix="remset"):
    event_id: int


class RemindHoursCB(CallbackData, prefix="remh"):
    event_id: int
    hours: int  # 2, 24, or 0 = both


class RemindDelCB(CallbackData, prefix="remd"):
    reminder_id: int


class ArtistReviewCB(CallbackData, prefix="artrev"):
    artist_id: int
    revision: int  # the profile revision the admin saw
    approve: bool