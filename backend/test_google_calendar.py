from app.services.google_calendar import get_calendar_service


service = get_calendar_service()

calendar_list = service.calendarList().list().execute()

print("\n=== GOOGLE CALENDARS ===")

for calendar in calendar_list.get("items", []):
    print(
        f"- {calendar.get('summary')} "
        f"({calendar.get('id')})"
    )