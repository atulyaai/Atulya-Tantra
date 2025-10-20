"""
Atulya Tantra - Calendar Integration
Version: 2.5.0
Calendar integration for Google Calendar, Outlook, and other calendar services
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import uuid
from src.integrations.base_integration import BaseIntegration, IntegrationType, IntegrationStatus

logger = logging.getLogger(__name__)


class CalendarProvider(Enum):
    """Calendar providers"""
    GOOGLE = "google"
    OUTLOOK = "outlook"
    APPLE = "apple"
    CALDAV = "caldav"


@dataclass
class CalendarEvent:
    """Calendar event"""
    event_id: str
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    location: Optional[str]
    attendees: List[str]
    calendar_id: str
    provider: CalendarProvider
    metadata: Dict[str, Any]


@dataclass
class Calendar:
    """Calendar"""
    calendar_id: str
    name: str
    description: Optional[str]
    provider: CalendarProvider
    color: str
    timezone: str
    metadata: Dict[str, Any]


class CalendarIntegration:
    """Calendar integration for various providers"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.integration_id = "calendar_integration"
        self.name = "Calendar Integration"
        self.type = IntegrationType.CALENDAR
        self.status = IntegrationStatus.DISCONNECTED
        
        # Calendar providers
        self.providers = {
            CalendarProvider.GOOGLE: self._google_calendar_client,
            CalendarProvider.OUTLOOK: self._outlook_calendar_client,
            CalendarProvider.APPLE: self._apple_calendar_client,
            CalendarProvider.CALDAV: self._caldav_calendar_client
        }
        
        # Connected calendars
        self.connected_calendars = {}  # calendar_id -> Calendar
        
        logger.info("CalendarIntegration initialized")
    
    async def connect(self, credentials: Dict[str, Any]) -> bool:
        """Connect to calendar service"""
        
        try:
            provider = credentials.get("provider", "google")
            provider_enum = CalendarProvider(provider)
            
            # Connect to provider
            client = await self.providers[provider_enum](credentials)
            
            if client:
                self.status = IntegrationStatus.CONNECTED
                logger.info(f"Connected to {provider} calendar")
                return True
            else:
                self.status = IntegrationStatus.ERROR
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to calendar: {e}")
            self.status = IntegrationStatus.ERROR
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from calendar service"""
        
        try:
            self.connected_calendars.clear()
            self.status = IntegrationStatus.DISCONNECTED
            logger.info("Disconnected from calendar service")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disconnect from calendar: {e}")
            return False
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the calendar connection"""
        
        if self.status != IntegrationStatus.CONNECTED:
            return {"status": "disconnected", "message": "Not connected to calendar service"}
        
        try:
            # Test by getting calendars
            calendars = await self.get_calendars()
            
            return {
                "status": "connected",
                "message": "Calendar connection is working",
                "calendars_count": len(calendars)
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Connection test failed: {e}"}
    
    async def get_calendars(self) -> List[Calendar]:
        """Get list of available calendars"""
        
        if self.status != IntegrationStatus.CONNECTED:
            return []
        
        try:
            # Simulate getting calendars
            calendars = [
                Calendar(
                    calendar_id="primary",
                    name="Primary Calendar",
                    description="Main calendar",
                    provider=CalendarProvider.GOOGLE,
                    color="#4285f4",
                    timezone="UTC",
                    metadata={}
                ),
                Calendar(
                    calendar_id="work",
                    name="Work Calendar",
                    description="Work-related events",
                    provider=CalendarProvider.GOOGLE,
                    color="#ea4335",
                    timezone="UTC",
                    metadata={}
                )
            ]
            
            # Store connected calendars
            for calendar in calendars:
                self.connected_calendars[calendar.calendar_id] = calendar
            
            return calendars
            
        except Exception as e:
            logger.error(f"Failed to get calendars: {e}")
            return []
    
    async def get_events(
        self,
        calendar_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[CalendarEvent]:
        """Get events from a calendar"""
        
        if self.status != IntegrationStatus.CONNECTED:
            return []
        
        try:
            # Default to next 7 days if no time range specified
            if not start_time:
                start_time = datetime.now()
            if not end_time:
                end_time = start_time + timedelta(days=7)
            
            # Simulate getting events
            events = [
                CalendarEvent(
                    event_id=str(uuid.uuid4()),
                    title="Team Meeting",
                    description="Weekly team sync",
                    start_time=start_time + timedelta(hours=1),
                    end_time=start_time + timedelta(hours=2),
                    location="Conference Room A",
                    attendees=["team@example.com"],
                    calendar_id=calendar_id,
                    provider=CalendarProvider.GOOGLE,
                    metadata={}
                ),
                CalendarEvent(
                    event_id=str(uuid.uuid4()),
                    title="Project Review",
                    description="Review project progress",
                    start_time=start_time + timedelta(days=1, hours=2),
                    end_time=start_time + timedelta(days=1, hours=3),
                    location="Virtual",
                    attendees=["manager@example.com", "team@example.com"],
                    calendar_id=calendar_id,
                    provider=CalendarProvider.GOOGLE,
                    metadata={}
                )
            ]
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []
    
    async def create_event(
        self,
        calendar_id: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None
    ) -> CalendarEvent:
        """Create a new calendar event"""
        
        if self.status != IntegrationStatus.CONNECTED:
            raise ValueError("Not connected to calendar service")
        
        try:
            # Create event
            event = CalendarEvent(
                event_id=str(uuid.uuid4()),
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                location=location,
                attendees=attendees or [],
                calendar_id=calendar_id,
                provider=CalendarProvider.GOOGLE,
                metadata={"created_at": datetime.now().isoformat()}
            )
            
            # Simulate creating event
            logger.info(f"Created event: {title} in calendar {calendar_id}")
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            raise
    
    async def update_event(
        self,
        event_id: str,
        updates: Dict[str, Any]
    ) -> CalendarEvent:
        """Update an existing calendar event"""
        
        if self.status != IntegrationStatus.CONNECTED:
            raise ValueError("Not connected to calendar service")
        
        try:
            # Simulate updating event
            # In production, this would update the actual event
            
            logger.info(f"Updated event: {event_id}")
            
            # Return updated event (simulated)
            return CalendarEvent(
                event_id=event_id,
                title=updates.get("title", "Updated Event"),
                description=updates.get("description"),
                start_time=updates.get("start_time", datetime.now()),
                end_time=updates.get("end_time", datetime.now() + timedelta(hours=1)),
                location=updates.get("location"),
                attendees=updates.get("attendees", []),
                calendar_id=updates.get("calendar_id", "primary"),
                provider=CalendarProvider.GOOGLE,
                metadata={"updated_at": datetime.now().isoformat()}
            )
            
        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            raise
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event"""
        
        if self.status != IntegrationStatus.CONNECTED:
            raise ValueError("Not connected to calendar service")
        
        try:
            # Simulate deleting event
            logger.info(f"Deleted event: {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return False
    
    async def find_free_time(
        self,
        calendar_id: str,
        duration_minutes: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Find free time slots in calendar"""
        
        if self.status != IntegrationStatus.CONNECTED:
            return []
        
        try:
            # Default to next 7 days if no time range specified
            if not start_time:
                start_time = datetime.now()
            if not end_time:
                end_time = start_time + timedelta(days=7)
            
            # Get existing events
            events = await self.get_events(calendar_id, start_time, end_time)
            
            # Find free time slots
            free_slots = []
            current_time = start_time
            
            # Sort events by start time
            events.sort(key=lambda e: e.start_time)
            
            for event in events:
                # Check if there's free time before this event
                if current_time < event.start_time:
                    time_diff = (event.start_time - current_time).total_seconds() / 60
                    if time_diff >= duration_minutes:
                        free_slots.append({
                            "start_time": current_time,
                            "end_time": event.start_time,
                            "duration_minutes": int(time_diff)
                        })
                
                # Move current time to end of this event
                current_time = max(current_time, event.end_time)
            
            # Check for free time after last event
            if current_time < end_time:
                time_diff = (end_time - current_time).total_seconds() / 60
                if time_diff >= duration_minutes:
                    free_slots.append({
                        "start_time": current_time,
                        "end_time": end_time,
                        "duration_minutes": int(time_diff)
                    })
            
            return free_slots
            
        except Exception as e:
            logger.error(f"Failed to find free time: {e}")
            return []
    
    async def schedule_meeting(
        self,
        calendar_id: str,
        title: str,
        duration_minutes: int,
        attendees: List[str],
        description: Optional[str] = None,
        location: Optional[str] = None,
        preferred_times: Optional[List[datetime]] = None
    ) -> CalendarEvent:
        """Schedule a meeting with attendees"""
        
        if self.status != IntegrationStatus.CONNECTED:
            raise ValueError("Not connected to calendar service")
        
        try:
            # Find free time
            free_slots = await self.find_free_time(calendar_id, duration_minutes)
            
            if not free_slots:
                raise ValueError("No free time slots available")
            
            # Use first available slot or preferred time
            if preferred_times:
                # Find best time from preferred times
                start_time = preferred_times[0]
            else:
                start_time = free_slots[0]["start_time"]
            
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            # Create meeting event
            meeting = await self.create_event(
                calendar_id=calendar_id,
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                location=location,
                attendees=attendees
            )
            
            logger.info(f"Scheduled meeting: {title} with {len(attendees)} attendees")
            
            return meeting
            
        except Exception as e:
            logger.error(f"Failed to schedule meeting: {e}")
            raise
    
    async def get_upcoming_events(self, calendar_id: str, hours: int = 24) -> List[CalendarEvent]:
        """Get upcoming events in the next N hours"""
        
        if self.status != IntegrationStatus.CONNECTED:
            return []
        
        try:
            start_time = datetime.now()
            end_time = start_time + timedelta(hours=hours)
            
            events = await self.get_events(calendar_id, start_time, end_time)
            
            # Filter to only upcoming events
            upcoming_events = [
                event for event in events
                if event.start_time > start_time
            ]
            
            return upcoming_events
            
        except Exception as e:
            logger.error(f"Failed to get upcoming events: {e}")
            return []
    
    async def get_capabilities(self) -> List[str]:
        """Get integration capabilities"""
        
        return [
            "get_calendars",
            "get_events",
            "create_event",
            "update_event",
            "delete_event",
            "find_free_time",
            "schedule_meeting",
            "get_upcoming_events"
        ]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check integration health"""
        return {
            "calendar_integration": True,
            "status": self.status.value,
            "connected_calendars": len(self.connected_calendars),
            "providers_supported": len(self.providers),
            "capabilities": len(await self.get_capabilities())
        }
    
    # Provider-specific clients (simulated)
    
    async def _google_calendar_client(self, credentials: Dict[str, Any]):
        """Google Calendar client"""
        # Simulate Google Calendar client
        return {"provider": "google", "authenticated": True}
    
    async def _outlook_calendar_client(self, credentials: Dict[str, Any]):
        """Outlook Calendar client"""
        # Simulate Outlook Calendar client
        return {"provider": "outlook", "authenticated": True}
    
    async def _apple_calendar_client(self, credentials: Dict[str, Any]):
        """Apple Calendar client"""
        # Simulate Apple Calendar client
        return {"provider": "apple", "authenticated": True}
    
    async def _caldav_calendar_client(self, credentials: Dict[str, Any]):
        """CalDAV Calendar client"""
        # Simulate CalDAV Calendar client
        return {"provider": "caldav", "authenticated": True}
