from pathlib import Path
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime
from zoneinfo import ZoneInfo

SCOPES = [
    "https://www.googleapis.com/auth/calendar"
]

BASE_DIR = Path(__file__).resolve().parents[3]

CREDENTIALS_FILE = BASE_DIR / "client_secret_971531000181-4isesv3tika4vf59ctfju1l54h85bdcd.apps.googleusercontent.com.json"
TOKEN_FILE = BASE_DIR / "token.json"

LIFEOS_TIMEZONE = ZoneInfo("Africa/Tunis")


def _ensure_timezone(value: datetime) -> datetime:
    """
    Ensure a datetime is timezone-aware and normalized
    to the LIFEOS timezone.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=LIFEOS_TIMEZONE)

    return value.astimezone(LIFEOS_TIMEZONE)

def get_calendar_service():
    """
    Authenticate with Google and return a Calendar API service.
    """

    credentials = None

    # Reuse an existing authorized token if available.
    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES,
        )

    # Refresh an expired token when possible.
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    # Start OAuth flow if we don't have valid credentials.
    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE,
            SCOPES,
        )

        credentials = flow.run_local_server(
            port=0
        )

        TOKEN_FILE.write_text(
            credentials.to_json()
        )

    return build(
        "calendar",
        "v3",
        credentials=credentials,
    )
    
def create_event(
    title: str,
    start: str,
    end: str,
    calendar_id: str = "primary",
    recurrence: list[str] | None = None,
):
    """
    Create a real event in Google Calendar.

    If recurrence is provided, Google Calendar creates
    a recurring event series.
    """

    service = get_calendar_service()

    event = {
        "summary": title,
        "start": {
            "dateTime": start,
            "timeZone": "Africa/Tunis",
        },
        "end": {
            "dateTime": end,
            "timeZone": "Africa/Tunis",
        },
    }

    if recurrence:
        event["recurrence"] = recurrence

    created_event = (
        service.events()
        .insert(
            calendarId=calendar_id,
            body=event,
        )
        .execute()
    )

    return created_event

def delete_event(
    event_id: str,
    calendar_id: str = "primary",
) -> None:
    """
    Delete a real event from Google Calendar.
    """

    service = get_calendar_service()

    service.events().delete(
        calendarId=calendar_id,
        eventId=event_id,
    ).execute()
    
def update_event(
    event_id: str,
    title: str,
    start: str,
    end: str,
    calendar_id: str = "primary",
) -> dict:
    service = get_calendar_service()

    event = service.events().get(
        calendarId=calendar_id,
        eventId=event_id,
    ).execute()

    event["summary"] = title
    event["start"] = {
        "dateTime": start,
        "timeZone": "Africa/Tunis",
    }
    event["end"] = {
        "dateTime": end,
        "timeZone": "Africa/Tunis",
    }

    updated_event = service.events().update(
        calendarId=calendar_id,
        eventId=event_id,
        body=event,
    ).execute()

    return {
        "event_id": updated_event["id"],
        "html_link": updated_event.get("htmlLink"),
    }

def get_events(
    start_datetime: datetime,
    end_datetime: datetime,
    calendar_id: str = "primary",
    max_results: int = 100,
):
    """
    Retrieve Google Calendar events inside a specific
    scheduling window.
    """

    service = get_calendar_service()

    start_datetime = _ensure_timezone(start_datetime)
    end_datetime = _ensure_timezone(end_datetime)

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_datetime.isoformat(),
            timeMax=end_datetime.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return events_result.get("items", [])

def get_upcoming_events(
    days_ahead: int = 7,
    calendar_id: str = "primary",
    max_results: int = 100,
):
    """
    Retrieve upcoming Google Calendar events.

    By default, returns events occurring from now
    through the next 7 days.
    """

    now = datetime.now(LIFEOS_TIMEZONE)

    end_datetime = now + timedelta(days=days_ahead)

    return get_events(
        start_datetime=now,
        end_datetime=end_datetime,
        calendar_id=calendar_id,
        max_results=max_results,
    )