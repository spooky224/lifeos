from app.services.google_calendar import get_upcoming_events


events = get_upcoming_events()

print("\n=== UPCOMING GOOGLE CALENDAR EVENTS ===")

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
    print(f"  Start: {start}")
    print(f"  End:   {end}")