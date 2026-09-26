from datetime import datetime

from app.services.google_calendar import get_events
from app.services.calendar_availability import calculate_available_slots

start_date = datetime(2026, 9, 19)
end_date = datetime(2026, 9, 19)

events = get_events(
    start_datetime=start_date,
    end_datetime=end_date,
    max_results=50,
)


slots = calculate_available_slots(
    events=events,
    start_date=start_date,
    end_date=end_date,
)

print("\n=== REAL CALENDAR EVENTS ===")

for event in events:
    start = event.get("start", {}).get(
        "dateTime",
        event.get("start", {}).get("date"),
    )

    end = event.get("end", {}).get(
        "dateTime",
        event.get("end", {}).get("date"),
    )

    print(f"- {event.get('summary', '(No title)')}")
    print(f"  {start} → {end}")


print("\n=== CALCULATED AVAILABLE SLOTS ===")

for slot in slots:
    print(
        f"- {slot['start']} → {slot['end']}"
    )