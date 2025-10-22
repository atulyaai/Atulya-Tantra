"""
Scheduling Action Handler
Handles scheduling-related actions like appointments, meetings, reminders, and calendar management
"""

import json
import os
from typing import Dict, Any, List
from datetime import datetime, timedelta
from ..assistant_core import ActionRequest, ConversationContext

class SchedulingActionHandler:
    """
    Handles scheduling-related actions
    """
    
    def __init__(self):
        self.supported_actions = {
            'schedule_appointment': self._handle_schedule_appointment,
            'schedule_meeting': self._handle_schedule_meeting,
            'set_reminder': self._handle_set_reminder,
            'view_calendar': self._handle_view_calendar,
            'cancel_event': self._handle_cancel_event,
            'reschedule_event': self._handle_reschedule_event
        }
        
        # Calendar storage (in production, this would be a database)
        self.calendar_file = "calendar_events.json"
        self.calendar_events = self._load_calendar_events()
    
    def execute(self, action_request: ActionRequest, context: ConversationContext) -> Dict[str, Any]:
        """
        Execute scheduling action
        """
        action_type = action_request.command
        parameters = action_request.parameters
        
        if action_type in self.supported_actions:
            try:
                result = self.supported_actions[action_type](parameters)
                return {
                    "success": True,
                    "action": action_type,
                    "result": result,
                    "message": f"Successfully executed {action_type}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "action": action_type,
                    "error": str(e),
                    "message": f"Failed to execute {action_type}: {str(e)}"
                }
        else:
            return {
                "success": False,
                "action": action_type,
                "error": f"Unsupported action: {action_type}",
                "message": f"Action {action_type} is not supported"
            }
    
    def _handle_schedule_appointment(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle appointment scheduling
        """
        title = parameters.get('title', 'Appointment')
        date = parameters.get('date', '')
        time = parameters.get('time', '')
        duration = parameters.get('duration', 60)  # Default 60 minutes
        location = parameters.get('location', '')
        notes = parameters.get('notes', '')
        
        if not date or not time:
            raise ValueError("Appointment requires 'date' and 'time' parameters")
        
        # Create appointment event
        appointment = {
            "id": self._generate_event_id(),
            "type": "appointment",
            "title": title,
            "date": date,
            "time": time,
            "duration": duration,
            "location": location,
            "notes": notes,
            "created_at": datetime.now().isoformat(),
            "status": "scheduled"
        }
        
        # Add to calendar
        self.calendar_events.append(appointment)
        self._save_calendar_events()
        
        return {
            "action": "schedule_appointment",
            "status": "Appointment scheduled",
            "event": appointment
        }
    
    def _handle_schedule_meeting(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle meeting scheduling
        """
        title = parameters.get('title', 'Meeting')
        date = parameters.get('date', '')
        time = parameters.get('time', '')
        duration = parameters.get('duration', 60)
        location = parameters.get('location', '')
        attendees = parameters.get('attendees', [])
        agenda = parameters.get('agenda', '')
        
        if not date or not time:
            raise ValueError("Meeting requires 'date' and 'time' parameters")
        
        # Create meeting event
        meeting = {
            "id": self._generate_event_id(),
            "type": "meeting",
            "title": title,
            "date": date,
            "time": time,
            "duration": duration,
            "location": location,
            "attendees": attendees,
            "agenda": agenda,
            "created_at": datetime.now().isoformat(),
            "status": "scheduled"
        }
        
        # Add to calendar
        self.calendar_events.append(meeting)
        self._save_calendar_events()
        
        return {
            "action": "schedule_meeting",
            "status": "Meeting scheduled",
            "event": meeting
        }
    
    def _handle_set_reminder(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle reminder setting
        """
        title = parameters.get('title', 'Reminder')
        date = parameters.get('date', '')
        time = parameters.get('time', '')
        message = parameters.get('message', '')
        priority = parameters.get('priority', 'medium')
        
        if not date or not time:
            raise ValueError("Reminder requires 'date' and 'time' parameters")
        
        # Create reminder event
        reminder = {
            "id": self._generate_event_id(),
            "type": "reminder",
            "title": title,
            "date": date,
            "time": time,
            "message": message,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }
        
        # Add to calendar
        self.calendar_events.append(reminder)
        self._save_calendar_events()
        
        return {
            "action": "set_reminder",
            "status": "Reminder set",
            "event": reminder
        }
    
    def _handle_view_calendar(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle calendar viewing
        """
        date = parameters.get('date', '')
        view_type = parameters.get('view_type', 'day')  # day, week, month
        
        if date:
            # Filter events for specific date
            filtered_events = [event for event in self.calendar_events if event.get('date') == date]
        else:
            # Show all events
            filtered_events = self.calendar_events
        
        # Sort events by date and time
        filtered_events.sort(key=lambda x: (x.get('date', ''), x.get('time', '')))
        
        return {
            "action": "view_calendar",
            "status": "Calendar retrieved",
            "events": filtered_events,
            "total_events": len(filtered_events)
        }
    
    def _handle_cancel_event(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle event cancellation
        """
        event_id = parameters.get('event_id', '')
        title = parameters.get('title', '')
        
        if not event_id and not title:
            raise ValueError("Cancel event requires 'event_id' or 'title' parameter")
        
        # Find and cancel event
        cancelled_events = []
        for event in self.calendar_events:
            if (event.get('id') == event_id or event.get('title') == title) and event.get('status') != 'cancelled':
                event['status'] = 'cancelled'
                event['cancelled_at'] = datetime.now().isoformat()
                cancelled_events.append(event)
        
        if cancelled_events:
            self._save_calendar_events()
            return {
                "action": "cancel_event",
                "status": "Event(s) cancelled",
                "cancelled_events": cancelled_events
            }
        else:
            return {
                "action": "cancel_event",
                "status": "No events found to cancel",
                "cancelled_events": []
            }
    
    def _handle_reschedule_event(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle event rescheduling
        """
        event_id = parameters.get('event_id', '')
        new_date = parameters.get('new_date', '')
        new_time = parameters.get('new_time', '')
        
        if not event_id or not new_date or not new_time:
            raise ValueError("Reschedule event requires 'event_id', 'new_date', and 'new_time' parameters")
        
        # Find and reschedule event
        rescheduled_events = []
        for event in self.calendar_events:
            if event.get('id') == event_id and event.get('status') != 'cancelled':
                old_date = event.get('date')
                old_time = event.get('time')
                event['date'] = new_date
                event['time'] = new_time
                event['rescheduled_at'] = datetime.now().isoformat()
                event['old_date'] = old_date
                event['old_time'] = old_time
                rescheduled_events.append(event)
        
        if rescheduled_events:
            self._save_calendar_events()
            return {
                "action": "reschedule_event",
                "status": "Event rescheduled",
                "rescheduled_events": rescheduled_events
            }
        else:
            return {
                "action": "reschedule_event",
                "status": "No events found to reschedule",
                "rescheduled_events": []
            }
    
    def _generate_event_id(self) -> str:
        """
        Generate unique event ID
        """
        return f"event_{int(datetime.now().timestamp())}"
    
    def _load_calendar_events(self) -> List[Dict[str, Any]]:
        """
        Load calendar events from file
        """
        try:
            if os.path.exists(self.calendar_file):
                with open(self.calendar_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Error loading calendar events: {e}")
            return []
    
    def _save_calendar_events(self):
        """
        Save calendar events to file
        """
        try:
            with open(self.calendar_file, 'w') as f:
                json.dump(self.calendar_events, f, indent=2)
        except Exception as e:
            print(f"Error saving calendar events: {e}")
