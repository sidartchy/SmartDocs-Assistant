from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
import json

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False
    print("Google Calendar API not available. Install google-auth, google-auth-oauthlib, google-auth-httplib2, google-api-python-client")


class CalendarEvent(BaseModel):
    event_id: str = Field(description="Unique identifier for the calendar event")
    title: str = Field(description="Event title")
    start_time: datetime = Field(description="Event start time")
    end_time: datetime = Field(description="Event end time")
    meeting_link: Optional[str] = Field(description="Video meeting link if applicable")
    calendar_url: Optional[str] = Field(description="Link to view event in calendar")
    success: bool = Field(description="Whether event creation was successful")
    error_message: Optional[str] = Field(description="Error message if creation failed")


class GoogleCalendarService:
    """Google Calendar API service for creating and managing events."""
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    def __init__(self):
        self.service = None
        self.calendar_id = 'primary'  # Use primary calendar
        
    def authenticate(self) -> bool:
        """Authenticate with Google Calendar API."""
        if not GOOGLE_CALENDAR_AVAILABLE:
            return False
            
        creds = None
        token_path = os.getenv('GOOGLE_TOKEN_PATH', 'token.json')
        credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
        
        # Load existing token
        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
            except Exception as e:
                print(f"Error loading token: {e}")
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(credentials_path):
                    print(f"Credentials file not found at {credentials_path}")
                    print("Please download credentials.json from Google Cloud Console")
                    return False
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                    
                    # Save credentials for next run
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    print(f"Error during authentication: {e}")
                    return False
        
        try:
            self.service = build('calendar', 'v3', credentials=creds)
            return True
        except Exception as e:
            print(f"Error building calendar service: {e}")
            return False
    
    def create_event(
        self,
        title: str,
        start_time: datetime,
        duration_minutes: int = 30,
        description: Optional[str] = None,
        attendee_email: Optional[str] = None,
        attendee_name: Optional[str] = None,
    ) -> CalendarEvent:
        """Create a calendar event using Google Calendar API."""
        
        if not self.service and not self.authenticate():
            return CalendarEvent(
                event_id="",
                title=title,
                start_time=start_time,
                end_time=start_time + timedelta(minutes=duration_minutes),
                meeting_link=None,
                calendar_url=None,
                success=False,
                error_message="Google Calendar API not available or authentication failed"
            )
        
        try:
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            # Prepare event body
            event_body = {
                'summary': title,
                'description': description or f"Meeting with {attendee_name or attendee_email}",
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"meet_{int(start_time.timestamp())}",
                        'conferenceSolutionKey': {
                            'type': 'hangoutsMeet'
                        }
                    }
                }
            }
            
            # Add attendee if provided
            if attendee_email:
                event_body['attendees'] = [{'email': attendee_email}]
            
            # Create the event
            event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event_body,
                conferenceDataVersion=1
            ).execute()
            
            # Extract meeting link
            meeting_link = None
            if 'conferenceData' in event and 'entryPoints' in event['conferenceData']:
                for entry_point in event['conferenceData']['entryPoints']:
                    if entry_point['entryPointType'] == 'video':
                        meeting_link = entry_point['uri']
                        break
            
            return CalendarEvent(
                event_id=event['id'],
                title=event['summary'],
                start_time=datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')),
                end_time=datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00')),
                meeting_link=meeting_link,
                calendar_url=event.get('htmlLink'),
                success=True,
                error_message=None
            )
            
        except HttpError as e:
            error_details = json.loads(e.content.decode())
            return CalendarEvent(
                event_id="",
                title=title,
                start_time=start_time,
                end_time=start_time + timedelta(minutes=duration_minutes),
                meeting_link=None,
                calendar_url=None,
                success=False,
                error_message=f"Google Calendar API error: {error_details.get('error', {}).get('message', str(e))}"
            )
        except Exception as e:
            return CalendarEvent(
                event_id="",
                title=title,
                start_time=start_time,
                end_time=start_time + timedelta(minutes=duration_minutes),
                meeting_link=None,
                calendar_url=None,
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def get_availability(
        self,
        date: datetime,
        duration_minutes: int = 30,
        business_hours: tuple = (9, 17)  # 9 AM to 5 PM
    ) -> Dict[str, Any]:
        """Get available time slots for a given date."""
        
        if not self.service and not self.authenticate():
            return {
                "date": date.date().isoformat(),
                "duration_minutes": duration_minutes,
                "available_slots": [],
                "error": "Google Calendar API not available"
            }
        
        try:
            # Get events for the date
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_of_day.isoformat() + 'Z',
                timeMax=end_of_day.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Generate time slots during business hours
            start_hour, end_hour = business_hours
            available_slots = []
            
            for hour in range(start_hour, end_hour):
                for minute in [0, 30]:  # 30-minute intervals
                    slot_start = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    slot_end = slot_start + timedelta(minutes=duration_minutes)
                    
                    if slot_end.hour <= end_hour:
                        # Check if slot conflicts with existing events
                        is_available = True
                        for event in events:
                            event_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                            event_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                            
                            # Check for overlap
                            if (slot_start < event_end and slot_end > event_start):
                                is_available = False
                                break
                        
                        available_slots.append({
                            "start_time": slot_start.isoformat(),
                            "end_time": slot_end.isoformat(),
                            "available": is_available
                        })
            
            return {
                "date": date.date().isoformat(),
                "duration_minutes": duration_minutes,
                "available_slots": available_slots
            }
            
        except Exception as e:
            return {
                "date": date.date().isoformat(),
                "duration_minutes": duration_minutes,
                "available_slots": [],
                "error": f"Error getting availability: {str(e)}"
            }


# Global instance
_calendar_service = None

def get_calendar_service() -> GoogleCalendarService:
    """Get or create the global calendar service instance."""
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = GoogleCalendarService()
    return _calendar_service


def create_calendar_event(
    title: str,
    start_time: datetime,
    duration_minutes: int = 30,
    description: Optional[str] = None,
    attendee_email: Optional[str] = None,
    attendee_name: Optional[str] = None,
) -> CalendarEvent:
    """Create a calendar event using Google Calendar API."""
    service = get_calendar_service()
    return service.create_event(
        title=title,
        start_time=start_time,
        duration_minutes=duration_minutes,
        description=description,
        attendee_email=attendee_email,
        attendee_name=attendee_name
    )


def get_calendar_availability(
    date: datetime,
    duration_minutes: int = 30,
    business_hours: tuple = (9, 17)  # 9 AM to 5 PM
) -> Dict[str, Any]:
    """Get available time slots for a given date."""
    service = get_calendar_service()
    return service.get_availability(
        date=date,
        duration_minutes=duration_minutes,
        business_hours=business_hours
    )
