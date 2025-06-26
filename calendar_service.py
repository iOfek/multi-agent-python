import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv
import pytz

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from agents.common_functions import convert_datetime_to_speech

# Configure logging
logger = logging.getLogger(__name__)
load_dotenv()

# Google Calendar configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/oauth2callback')
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]

# Single user for calendar access
CALENDAR_USER_ID = "lawyer_gal"
TOKEN_FILE_PATH = "calendar_token.json"

# Timezone for Israel
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')


class CalendarService:
    """Google Calendar service wrapper"""
    
    def __init__(self):
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize the Google Calendar service"""
        token_data = self._load_calendar_token()
        
        if not token_data:
            logger.warning("No calendar token found. Please authorize first.")
            return None
        
        try:
            creds = Credentials(
                token=token_data['token'],
                refresh_token=token_data['refresh_token'],
                token_uri=token_data['token_uri'],
                client_id=token_data['client_id'],
                client_secret=token_data['client_secret'],
                scopes=token_data['scopes']
            )
            
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(GoogleRequest())
                    # Update stored credentials
                    self._save_calendar_token(creds)
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}")
                    return None
            
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Calendar service initialized successfully")
            
        except Exception as e:
            logger.error(f"Error creating calendar service: {e}")
            self.service = None
    
    def get_service(self):
        """Get the calendar service instance"""
        if not self.service:
            self._initialize_service()
        return self.service
    
    def is_authorized(self) -> bool:
        """Check if calendar is authorized"""
        return self.service is not None
    
    def get_available_slots(self, preference: str, days_ahead: int = 7, duration_minutes: int = 15) -> List[Dict]:
        """
        Get available time slots based on preference (בוקר/צהריים/ערב)
        """
        if not self.service:
            return []
        
        # Define time ranges for preferences
        time_ranges = {
            "בוקר": {"start": "09:00", "end": "12:00"},
            "צהריים": {"start": "12:00", "end": "17:00"},
            "ערב": {"start": "17:00", "end": "20:00"}
        }
        
        if preference not in time_ranges:
            return []
        
        range_config = time_ranges[preference]
        
        # Get calendar events for the next N days
        now = datetime.now(ISRAEL_TZ)
        end_date = now + timedelta(days=days_ahead)
        logger.info(f"Getting available slots for {preference} from {now} to {end_date}")
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now.isoformat(),
                timeMax=end_date.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Generate available slots
            available_slots = []
            current_date = now.date()
            
            for day_offset in range(days_ahead):
                target_date = current_date + timedelta(days=day_offset)
                
                # Skip Friday and Saturday
                if target_date.weekday() == 4 or target_date.weekday() == 5:  # Friday = 4, Saturday = 5
                    continue
                
                # Get busy times for this day
                day_start = ISRAEL_TZ.localize(datetime.combine(target_date, datetime.min.time()))
                day_end = ISRAEL_TZ.localize(datetime.combine(target_date, datetime.max.time()))
                
                day_events = [e for e in events if 
                             day_start <= datetime.fromisoformat(e['start']['dateTime'].replace('Z', '+00:00')).replace(tzinfo=pytz.UTC).astimezone(ISRAEL_TZ) <= day_end]
                
                # Generate time slots
                slots = self._generate_time_slots(
                    target_date, 
                    range_config, 
                    day_events, 
                    duration_minutes
                )
                
                available_slots.extend(slots)
            
            return available_slots[:6]  # Return max 6 slots
            
        except HttpError as error:
            logger.error(f"Error fetching calendar events: {error}")
            return []
    
    def _generate_time_slots(self, date: datetime.date, time_range: dict, events: list, duration_minutes: int) -> List[Dict]:
        """Generate available time slots for a specific day"""
        slots = []
        
        # Parse time range
        start_time = datetime.strptime(time_range["start"], "%H:%M").time()
        end_time = datetime.strptime(time_range["end"], "%H:%M").time()
        
        # Get current time in Israel timezone
        now = datetime.now(ISRAEL_TZ)
        
        # If this is today, adjust start time to be at least 30 minutes from now
        if date == now.date():
            # Add 30 minutes to current time to allow for booking time
            min_start_time = (now + timedelta(minutes=30)).time()
            if min_start_time > start_time:
                start_time = min_start_time
                logger.info(f"Adjusted start time to {start_time} for today")
        
        # Create busy time ranges
        busy_ranges = []
        for event in events:
            event_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')).replace(tzinfo=pytz.UTC).astimezone(ISRAEL_TZ)
            event_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00')).replace(tzinfo=pytz.UTC).astimezone(ISRAEL_TZ)
            
            if event_start.date() == date:
                busy_ranges.append((event_start.time(), event_end.time()))
        
        # Generate slots
        current_time = start_time
        while current_time < end_time:
            slot_end = (datetime.combine(date, current_time) + 
                       timedelta(minutes=duration_minutes)).time()
            
            # Check if slot conflicts with any busy time
            is_available = True
            for busy_start, busy_end in busy_ranges:
                if (current_time < busy_end and slot_end > busy_start):
                    is_available = False
                    break
            
            if is_available:
                date_str = date.strftime('%d.%m.%Y')
                time_str = current_time.strftime('%H:%M')
                
                # Debug logging
                logger.info(f"Creating slot for date: {date_str}, time: {time_str}")
                
                spoken_text = convert_datetime_to_speech(date_str, time_str)
                logger.info(f"Converted to spoken: {spoken_text}")
                
                slots.append({
                    "slotId": f"{date.strftime('%Y%m%d')}_{current_time.strftime('%H%M')}",
                    # "date": date.strftime('%d.%m.%Y'),
                    # "time": current_time.strftime('%H:%M'),
                    "spoken": spoken_text
                })
            
            # Move to next slot
            current_time = (datetime.combine(date, current_time) + 
                          timedelta(minutes=duration_minutes)).time()
        
        return slots
    
    def book_slot(self, date: str, time: str, client_phone: str) -> Dict:
        """
        Book a calendar slot
        """
        if not self.service:
            logger.error("Calendar service not initialized - no service available")
            raise Exception("Calendar not authorized")
        
        try:
            # Parse slot_id to get date and time
            
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            time_obj = datetime.strptime(time, '%H:%M').time()
            
            # Create timezone-aware datetime
            start_datetime = ISRAEL_TZ.localize(datetime.combine(date_obj, time_obj))
            end_datetime = start_datetime + timedelta(minutes=15)
            
            logger.info(f"Attempting to create event for {date} at {time} (start: {start_datetime}, end: {end_datetime})")
            
            # Create calendar event
            event = {
                'summary': f'ייעוץ משפטי ',
                'description': f'פגישת ייעוץ עם \nטלפון: {client_phone}',
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'Asia/Jerusalem',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'Asia/Jerusalem',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 30},
                    ],
                },
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"meet-{start_datetime.strftime('%Y%m%d-%H%M')}-{client_phone}",
                        'conferenceSolutionKey': {
                            'type': 'hangoutsMeet'
                        }
                    }
                }
            }
            
            logger.info(f"Creating calendar event for {date} at {time} for client {client_phone}")
            logger.info(f"Event data: {event}")
            
            try:
                event_result = self.service.events().insert(
                    calendarId='primary', 
                    body=event,
                    conferenceDataVersion=1
                ).execute()
                
                logger.info(f"Calendar event created successfully with ID: {event_result.get('id')}")
                logger.info(f"Full event result: {event_result}")
                
            except HttpError as http_error:
                logger.error(f"HTTP Error during event creation: {http_error}")
                logger.error(f"Error details: {http_error.error_details}")
                logger.error(f"Error status: {http_error.status_code}")
                logger.error(f"Error reason: {http_error.reason}")
                raise Exception(f"HTTP Error creating calendar event: {http_error}")
            except Exception as api_error:
                logger.error(f"API Error during event creation: {api_error}")
                logger.error(f"Error type: {type(api_error)}")
                raise Exception(f"API Error creating calendar event: {api_error}")
            
            # Extract Google Meet link from the response
            meet_link = None
            if 'conferenceData' in event_result and 'entryPoints' in event_result['conferenceData']:
                for entry_point in event_result['conferenceData']['entryPoints']:
                    if entry_point.get('entryPointType') == 'video':
                        meet_link = entry_point.get('uri')
                        break
            
            # Fallback to conferenceData.uri if entryPoints not available
            if not meet_link and 'conferenceData' in event_result:
                meet_link = event_result['conferenceData'].get('uri')
            
            # Throw error if no valid meet link was found
            if not meet_link:
                logger.error(f"No meet link found in event result: {event_result}")
                raise Exception("Failed to generate Google Meet link for the calendar event")
            
            logger.info(f"Google Meet link generated: {meet_link}")
            
            # Return comprehensive event details
            return {
                'success': True,
                'event_id': event_result.get('id'),
                'meet_link': meet_link,
                'start_time': start_datetime.isoformat(),
                'end_time': end_datetime.isoformat(),
                'summary': event_result.get('summary'),
                'html_link': event_result.get('htmlLink')
            }
            
        except Exception as e:
            logger.error(f"Calendar booking error: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to book slot: {str(e)}")
    
    def _load_calendar_token(self) -> Optional[Dict]:
        """Load calendar token from file"""
        try:
            if os.path.exists(TOKEN_FILE_PATH):
                with open(TOKEN_FILE_PATH, 'r') as f:
                    token_data = json.load(f)
                    logger.info(f"Loaded calendar token from {TOKEN_FILE_PATH}")
                    return token_data
        except Exception as e:
            logger.error(f"Error loading calendar token: {e}")
        return None
    
    def _save_calendar_token(self, credentials: Credentials) -> bool:
        """Save calendar token to file"""
        try:
            token_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            with open(TOKEN_FILE_PATH, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            logger.info(f"Saved calendar token to {TOKEN_FILE_PATH}")
            return True
        except Exception as e:
            logger.error(f"Error saving calendar token: {e}")
            return False
    
    def get_available_slots_by_day(self, day: str, preference: str = None, weeks_ahead: int = 4, duration_minutes: int = 15) -> List[Dict]:
        """
        Get available time slots for a specific day of the week
        Args:
            day: Day of the week (Sunday, Monday, Tuesday, Wednesday, Thursday, Friday, Saturday)
            preference: Time preference - "בוקר", "צהריים", "ערב" (optional)
            weeks_ahead: Number of weeks to look ahead (default: 4)
            duration_minutes: Duration of each slot in minutes (default: 15)
        Returns:
            List of available time slots for the specified day of the week
        """
        if not self.service:
            return []
        
        # Day mapping
        day_mapping = {
            "sunday": 6, "ראשון": 6, "א": 6,
            "monday": 0, "שני": 0, "ב": 0,
            "tuesday": 1, "שלישי": 1, "ג": 1,
            "wednesday": 2, "רביעי": 2, "ד": 2,
            "thursday": 3, "חמישי": 3, "ה": 3,
            "friday": 4, "שישי": 4, "ו": 4,
            "saturday": 5, "שבת": 5, "ז": 5
        }
        
        # Time preference mapping
        time_ranges = {
            "בוקר": {"start": "09:00", "end": "12:00"},
            "צהריים": {"start": "12:00", "end": "17:00"},
            "ערב": {"start": "17:00", "end": "20:00"}
        }
        
        day_lower = day.lower()
        if day_lower not in day_mapping:
            logger.error(f"Invalid day: {day}. Expected: Sunday, Monday, Tuesday, Wednesday, Thursday, Friday, Saturday")
            return []
        
        # Validate preference if provided
        if preference and preference not in time_ranges:
            logger.error(f"Invalid preference: {preference}. Expected: בוקר, צהריים, ערב")
            return []
        
        target_weekday = day_mapping[day_lower]
        
        # Skip Friday and Saturday (weekend)
        if target_weekday in [4, 5]:  # Friday = 4, Saturday = 5
            logger.info(f"Day {day} is on weekend (Friday/Saturday), no slots available")
            return []
        
        try:
            # Get calendar events for the next N weeks
            now = datetime.now(ISRAEL_TZ)
            end_date = now + timedelta(weeks=weeks_ahead)
            
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now.isoformat(),
                timeMax=end_date.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Generate available slots for the target day of the week
            available_slots = []
            current_date = now.date()
            
            for week_offset in range(weeks_ahead):
                for day_offset in range(7):
                    target_date = current_date + timedelta(days=day_offset + (week_offset * 7))
                    
                    # Check if this is the target day of the week
                    if target_date.weekday() == target_weekday:
                        # Get busy times for this day
                        day_start = ISRAEL_TZ.localize(datetime.combine(target_date, datetime.min.time()))
                        day_end = ISRAEL_TZ.localize(datetime.combine(target_date, datetime.max.time()))
                        
                        day_events = [e for e in events if 
                                     day_start <= datetime.fromisoformat(e['start']['dateTime'].replace('Z', '+00:00')).replace(tzinfo=pytz.UTC).astimezone(ISRAEL_TZ) <= day_end]
                        
                        # Use preference time range or full business hours
                        if preference:
                            time_range = time_ranges[preference]
                        else:
                            time_range = {"start": "09:00", "end": "20:00"}
                        
                        # Generate time slots
                        slots = self._generate_time_slots(
                            target_date, 
                            time_range, 
                            day_events, 
                            duration_minutes
                        )
                        
                        available_slots.extend(slots)
            
            return available_slots[:6]  # Return max 6 slots
            
        except HttpError as error:
            logger.error(f"Error fetching calendar events: {error}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting slots for {day}: {e}")
            return []


class CalendarOAuth:
    """Google Calendar OAuth2 flow handler"""
    
    def __init__(self):
        self.redirect_uri = GOOGLE_REDIRECT_URI
        self.scopes = GOOGLE_SCOPES
    
    def get_authorization_url(self) -> str:
        """
        Get authorization URL for OAuth2 flow
        """
        if not os.path.exists('credentials.json'):
            raise Exception("credentials.json file not found")
        
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', 
            self.scopes,
            redirect_uri=self.redirect_uri
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        return authorization_url
    
    def handle_callback(self, code: str) -> Dict:
        """
        Handle OAuth2 callback and exchange code for credentials
        """
        if not code:
            raise Exception("No authorization code received")
        
        try:
            # Check if credentials.json exists
            if not os.path.exists('credentials.json'):
                raise Exception("credentials.json file not found")
            
            # Create OAuth flow
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', 
                self.scopes,
                redirect_uri=self.redirect_uri
            )
            
            # Exchange code for credentials
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Save the credentials
            calendar_service = CalendarService()
            if calendar_service._save_calendar_token(credentials):
                return {
                    "success": True,
                    "message": f"Calendar access granted for {CALENDAR_USER_ID}",
                    "user_id": CALENDAR_USER_ID
                }
            else:
                raise Exception("Failed to save calendar token")
            
        except Exception as e:
            logger.error(f"OAuth callback error: {e}")
            raise Exception(f"Failed to complete OAuth: {str(e)}")
    
    def get_setup_instructions(self) -> Dict:
        """Get setup instructions for Google Calendar API"""
        return {
            "1": "Go to Google Cloud Console (https://console.cloud.google.com/)",
            "2": "Create a new project or select existing one",
            "3": "Enable Google Calendar API",
            "4": "Go to APIs & Services > Credentials",
            "5": "Create OAuth 2.0 Client ID (Web application)",
            "6": f"Add redirect URIs: {self.redirect_uri}",
            "7": "Download credentials and save as 'credentials.json' in project root"
        }
    
    def get_status(self) -> Dict:
        """Get calendar authorization status"""
        token_data = CalendarService()._load_calendar_token()
        credentials_exist = os.path.exists('credentials.json')
        
        status = {
            "credentials_file_exists": credentials_exist,
            "authorized": token_data is not None,
            "user_id": CALENDAR_USER_ID,
            "token_file": TOKEN_FILE_PATH
        }
        
        if not credentials_exist:
            status["setup_required"] = True
            status["setup_instructions"] = self.get_setup_instructions()
        
        return status


# Global instances
calendar_service = CalendarService()
calendar_oauth = CalendarOAuth()


# Convenience functions for backward compatibility
def get_calendar_service():
    """Get or create Google Calendar service instance"""
    return calendar_service.get_service()

def get_available_slots(service, preference: str, days_ahead: int = 7, duration_minutes: int = 15):
    """Get available time slots based on preference"""
    return calendar_service.get_available_slots(preference, days_ahead, duration_minutes)

def load_calendar_token():
    """Load calendar token from file"""
    return calendar_service._load_calendar_token()

def save_calendar_token(credentials: Credentials):
    """Save calendar token to file"""
    return calendar_service._save_calendar_token(credentials) 