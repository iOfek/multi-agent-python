from datetime import datetime
import pytz

# Israel timezone
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

def is_within_working_hours() -> bool:
    """
    Check if current time is within working hours:
    - Sunday to Thursday (weekdays 0-4)
    - 08:00 to 22:00 (8 AM to 10 PM)
    """
    now = datetime.now(ISRAEL_TZ)
    
    # Check if it's Sunday to Thursday (weekday 0-4, where Monday=0, Sunday=6)
    # Convert to Sunday=0, Monday=1, ..., Thursday=4, Friday=5, Saturday=6
    weekday = (now.weekday() + 1) % 7  # This makes Sunday=0, Monday=1, etc.
    
    # Check if it's Sunday to Thursday (weekday 0-4)
    if weekday > 4:  # Friday (5) or Saturday (6)
        print(f"❌ Outside working days: {now.strftime('%A')} (weekday {weekday})")
        return False
    
    # Check if it's within working hours (08:00-22:00)
    current_hour = now.hour
    if current_hour < 8 or current_hour >= 22:
        print(f"❌ Outside working hours: {now.strftime('%H:%M')} (current hour: {current_hour})")
        return False
    
    print(f"✅ Within working hours: {now.strftime('%A %H:%M')}")
    return True 