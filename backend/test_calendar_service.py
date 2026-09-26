from app.db.session import SessionLocal
from app.services.calendar_service import CalendarService

session = SessionLocal()

try:
    service = CalendarService(session)

    removed_event = service.remove_event(3)

    session.commit()

    print("✓ Calendar event removed successfully")
    print(f"  Local CalendarEvent ID: {removed_event.id}")
    print(f"  Google Event ID: {removed_event.google_event_id}")
    print(f"  Title: {removed_event.title}")

except Exception as e:
    session.rollback()
    print("✗ Calendar event removal failed")
    print(e)

finally:
    session.close()
