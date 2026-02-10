"""Notification & Alert System - Proactive assistance and reminders"""

import logging
import threading
from typing import Callable, Dict, List, Optional
from datetime import datetime, timedelta
import heapq

logger = logging.getLogger(__name__)


class Notification:
    """Single notification/alert"""
    
    def __init__(self, title: str, message: str, priority: str = "normal", 
                 notify_time: Optional[datetime] = None):
        self.title = title
        self.message = message
        self.priority = priority  # low, normal, high, urgent
        self.notify_time = notify_time or datetime.now()
        self.created_at = datetime.now()
        self.read = False
        self.id = hash((title, self.created_at))
    
    def __lt__(self, other):
        """Enable heap priority sorting"""
        priority_order = {"low": 3, "normal": 2, "high": 1, "urgent": 0}
        return (priority_order[self.priority], self.notify_time) < \
               (priority_order[other.priority], other.notify_time)
    
    def __repr__(self):
        return f"[{self.priority.upper()}] {self.title}: {self.message}"


class NotificationManager:
    """Manages notifications and alerts for JARVIS"""
    
    def __init__(self):
        self.notifications: List[Notification] = []
        self.handlers: Dict[str, List[Callable]] = {}
        self.reminders: Dict[str, Notification] = {}
        self.running = False
        self.check_thread = None
        
        logger.info("NotificationManager initialized")
    
    def add_notification(self, title: str, message: str, priority: str = "normal",
                         notify_time: Optional[datetime] = None) -> Notification:
        """Add a notification"""
        notification = Notification(title, message, priority, notify_time)
        self.notifications.append(notification)
        heapq.heapify(self.notifications)
        
        logger.info(f"Notification added: {notification}")
        self._trigger_handlers("notification_added", notification)
        
        return notification
    
    def add_reminder(self, reminder_key: str, title: str, message: str, 
                     remind_at: datetime) -> Notification:
        """Add a reminder (notification at specific time)"""
        notification = Notification(title, message, "normal", remind_at)
        self.reminders[reminder_key] = notification
        
        logger.info(f"Reminder set: {reminder_key} at {remind_at}")
        return notification
    
    def get_pending_notifications(self, high_priority_first: bool = True) -> List[Notification]:
        """Get unread notifications"""
        pending = [n for n in self.notifications if not n.read]
        
        if high_priority_first:
            pending.sort()
        
        return pending
    
    def mark_as_read(self, notification_id):
        """Mark notification as read"""
        for notif in self.notifications:
            if notif.id == notification_id:
                notif.read = True
                logger.info(f"Notification marked as read: {notif.title}")
                self._trigger_handlers("notification_read", notif)
    
    def register_handler(self, event: str, handler: Callable):
        """Register callback for event"""
        if event not in self.handlers:
            self.handlers[event] = []
        self.handlers[event].append(handler)
    
    def _trigger_handlers(self, event: str, data):
        """Trigger registered handlers"""
        if event in self.handlers:
            for handler in self.handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
    
    def get_briefing(self, user_name: str = "Sir") -> str:
        """Get notification briefing"""
        pending = self.get_pending_notifications()
        
        if not pending:
            return f"All clear, {user_name}. No pending notifications."
        
        briefing = f"You have {len(pending)} pending notification(s), {user_name}:\n\n"
        for notif in pending[:5]:  # Show first 5
            briefing += f"• [{notif.priority.upper()}] {notif.title}\n"
            briefing += f"  {notif.message}\n\n"
        
        return briefing
    
    def start_monitoring(self):
        """Start background monitoring for reminders"""
        if self.running:
            return
        
        self.running = True
        self.check_thread = threading.Thread(target=self._monitor_reminders, daemon=True)
        self.check_thread.start()
        logger.info("Notification monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.running = False
        logger.info("Notification monitoring stopped")
    
    def _monitor_reminders(self):
        """Background thread monitoring reminders"""
        while self.running:
            now = datetime.now()
            due_reminders = []
            
            for key, reminder in list(self.reminders.items()):
                if not reminder.read and reminder.notify_time <= now:
                    due_reminders.append((key, reminder))
                    reminder.read = True
            
            for key, reminder in due_reminders:
                logger.info(f"Reminder triggered: {key}")
                self._trigger_handlers("reminder_due", reminder)
            
            # Check every 30 seconds
            import time
            time.sleep(30)
    
    def generate_morning_briefing(self, user_name: str = "Sir") -> List[str]:
        """Generate morning briefing messages"""
        briefings = [
            f"Good morning, {user_name}.",
            f"It is {datetime.now().strftime('%A, %B %d at %I:%M %p')}."
        ]
        
        # Add pending notifications
        pending = self.get_pending_notifications()
        if pending:
            briefings.append(f"You have {len(pending)} pending notification(s).")
            for notif in pending[:3]:
                briefings.append(f"• {notif.title}")
        
        # Add any reminders for today
        today_reminders = [r for r in self.reminders.values() 
                          if r.notify_time.date() == datetime.now().date()]
        if today_reminders:
            briefings.append(f"You have {len(today_reminders)} reminder(s) today.")
        
        briefings.append("Shall I provide additional details, Sir?")
        return briefings
    
    def get_summary(self) -> str:
        """Get notification system summary"""
        return f"""
Notification System Status:
- Total Notifications: {len(self.notifications)}
- Unread: {len(self.get_pending_notifications())}
- Reminders Set: {len(self.reminders)}
- Monitoring: {'Active' if self.running else 'Inactive'}

Standing by, Sir.
        """
