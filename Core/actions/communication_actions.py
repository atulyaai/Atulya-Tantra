"""
Communication Action Handler
Handles communication-related actions like emails, messages, and notifications
"""

import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List
from datetime import datetime
from ..assistant_core import ActionRequest, ConversationContext

class CommunicationActionHandler:
    """
    Handles communication-related actions
    """
    
    def __init__(self):
        self.supported_actions = {
            'email': self._handle_email,
            'message': self._handle_message,
            'notification': self._handle_notification,
            'send_file': self._handle_send_file
        }
        
        # Email configuration (would be loaded from config in production)
        self.email_config = {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'username': '',  # Would be loaded from environment variables
            'password': ''   # Would be loaded from environment variables
        }
    
    def execute(self, action_request: ActionRequest, context: ConversationContext) -> Dict[str, Any]:
        """
        Execute communication action
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
    
    def _handle_email(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle email sending
        """
        to_email = parameters.get('to', '')
        subject = parameters.get('subject', '')
        body = parameters.get('body', '')
        from_email = parameters.get('from', self.email_config['username'])
        
        if not to_email or not subject or not body:
            raise ValueError("Email requires 'to', 'subject', and 'body' parameters")
        
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body to email
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email (simplified version - in production, use proper authentication)
            # For now, just simulate sending
            email_data = {
                "to": to_email,
                "subject": subject,
                "body": body,
                "from": from_email,
                "timestamp": datetime.now().isoformat()
            }
            
            # In a real implementation, you would:
            # 1. Connect to SMTP server
            # 2. Authenticate
            # 3. Send the email
            # 4. Handle errors appropriately
            
            return {
                "action": "email",
                "status": "Email prepared (simulation mode)",
                "data": email_data
            }
        
        except Exception as e:
            raise Exception(f"Failed to send email: {str(e)}")
    
    def _handle_message(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle message sending (SMS, instant messaging, etc.)
        """
        message_type = parameters.get('type', 'sms')
        recipient = parameters.get('recipient', '')
        content = parameters.get('content', '')
        
        if not recipient or not content:
            raise ValueError("Message requires 'recipient' and 'content' parameters")
        
        # This is a simplified version - in production, you'd integrate with actual messaging services
        message_data = {
            "type": message_type,
            "recipient": recipient,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "action": "message",
            "status": "Message prepared (simulation mode)",
            "data": message_data
        }
    
    def _handle_notification(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle system notifications
        """
        title = parameters.get('title', 'Notification')
        message = parameters.get('message', '')
        notification_type = parameters.get('type', 'info')
        
        if not message:
            raise ValueError("Notification requires 'message' parameter")
        
        # This is a simplified version - in production, you'd use actual notification services
        notification_data = {
            "title": title,
            "message": message,
            "type": notification_type,
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "action": "notification",
            "status": "Notification prepared (simulation mode)",
            "data": notification_data
        }
    
    def _handle_send_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle file sending (email attachments, file sharing, etc.)
        """
        file_path = parameters.get('file_path', '')
        recipient = parameters.get('recipient', '')
        method = parameters.get('method', 'email')
        
        if not file_path or not recipient:
            raise ValueError("File sending requires 'file_path' and 'recipient' parameters")
        
        # This is a simplified version - in production, you'd handle actual file operations
        file_data = {
            "file_path": file_path,
            "recipient": recipient,
            "method": method,
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "action": "send_file",
            "status": "File sending prepared (simulation mode)",
            "data": file_data
        }
