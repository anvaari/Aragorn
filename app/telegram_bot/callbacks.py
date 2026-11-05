from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="menu"):
    action: str  # "events" | "artists" | "reminders"


class DayCB(CallbackData, prefix="day"):
    offset: int  # day_offset from today (digest_timezone)


class EventCB(CallbackData, prefix="evt"):
    event_id: int


class RemindSetCB(CallbackData, prefix="remset"):
    event_id: int


class RemindHoursCB(CallbackData, prefix="remh"):
    event_id: int
    hours: int  # 2, 24, or 0 = both


class ArtistsOfCB(CallbackData, prefix="earts"):
    event_id: int


class ArtistCB(CallbackData, prefix="art"):
    artist_id: int


class FollowCB(CallbackData, prefix="fol"):
    artist_id: int


class FollowPrefCB(CallbackData, prefix="folp"):
    artist_id: int
    mode: str  # "new" | "pre" | "both"


class RemindDelCB(CallbackData, prefix="remd"):
    reminder_id: int


class UnfollowCB(CallbackData, prefix="unfol"):
    follow_id: int


class NormPageCB(CallbackData, prefix="normpg"):
    page: int  # pending-proposal review page (0-based)


class NormDecisionCB(CallbackData, prefix="normd"):
    proposal_id: int
    approve: int  # 1 = approve, 0 = reject
    page: int  # page to re-render after the decision


class NormBulkCB(CallbackData, prefix="normbulk"):
    scope: str  # "page" | "all"
    page: int