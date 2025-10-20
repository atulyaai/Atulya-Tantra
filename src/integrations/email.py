"""
Atulya Tantra - Email Integration
Version: 2.5.0
Integrates with email services for sending and receiving emails
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import ssl

from src.integrations.base_integration import BaseIntegration

logger = logging.getLogger(__name__)

class EmailIntegration(BaseIntegration):
    """
    Manages email operations including sending and receiving emails
    """
    
    def __init__(self, integration_id: str = "email_integration", config: Optional[Dict] = None):
        super().__init__(
            integration_id=integration_id,
            name="Email Integration",
            description="Manages email operations including sending and receiving emails",
            config=config
        )
        self.requires_auth = True
        self.smtp_server = None
        self.imap_server = None
        self.smtp_port = self.config.get("smtp_port", 587)
        self.imap_port = self.config.get("imap_port", 993)
        self.smtp_host = self.config.get("smtp_host", "smtp.gmail.com")
        self.imap_host = self.config.get("imap_host", "imap.gmail.com")
        self.use_tls = self.config.get("use_tls", True)
        self.use_ssl = self.config.get("use_ssl", True)
        
        logger.info("EmailIntegration initialized")
    
    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize the email integration
        """
        logger.info("Initializing Email Integration...")
        
        # Check if email is enabled in config
        if not self.config.get("enabled", False):
            return {"status": "info", "message": "Email Integration is disabled in config"}
        
        # Validate configuration
        required_config = ["smtp_host", "smtp_port", "imap_host", "imap_port"]
        missing_config = [key for key in required_config if not self.config.get(key)]
        
        if missing_config:
            return {
                "status": "error",
                "message": f"Missing required configuration: {', '.join(missing_config)}"
            }
        
        self.is_enabled = True
        logger.info("Email Integration initialized successfully")
        return {"status": "success", "message": "Email Integration initialized"}
    
    async def authenticate(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authenticate with email services
        
        Args:
            credentials: Dictionary containing email credentials
                - email: Email address
                - password: Email password or app password
                - smtp_host: SMTP server host (optional)
                - imap_host: IMAP server host (optional)
        """
        logger.info("Authenticating Email Integration...")
        
        try:
            email_address = credentials.get("email")
            password = credentials.get("password")
            
            if not email_address or not password:
                return {
                    "status": "error",
                    "message": "Email address and password are required"
                }
            
            # Test SMTP connection
            smtp_host = credentials.get("smtp_host", self.smtp_host)
            smtp_port = credentials.get("smtp_port", self.smtp_port)
            
            if self.use_tls:
                smtp_server = smtplib.SMTP(smtp_host, smtp_port)
                smtp_server.starttls()
            else:
                smtp_server = smtplib.SMTP_SSL(smtp_host, smtp_port)
            
            smtp_server.login(email_address, password)
            smtp_server.quit()
            
            # Test IMAP connection
            imap_host = credentials.get("imap_host", self.imap_host)
            imap_port = credentials.get("imap_port", self.imap_port)
            
            if self.use_ssl:
                imap_server = imaplib.IMAP4_SSL(imap_host, imap_port)
            else:
                imap_server = imaplib.IMAP4(imap_host, imap_port)
            
            imap_server.login(email_address, password)
            imap_server.logout()
            
            self.is_authenticated = True
            self.email_address = email_address
            self.password = password
            
            logger.info("Email Integration authenticated successfully")
            return {"status": "success", "message": "Email Integration authenticated"}
            
        except Exception as e:
            logger.error(f"Email authentication failed: {e}")
            return {"status": "error", "message": f"Authentication failed: {str(e)}"}
    
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send an email
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)
            attachments: List of attachment dictionaries with 'filename' and 'content'
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
        """
        if not self.is_enabled or not self.is_authenticated:
            return {"status": "error", "message": "Email Integration is not enabled or authenticated"}
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_address
            msg['To'] = to
            msg['Subject'] = subject
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            # Add plain text body
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)
            
            # Add HTML body if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                msg.attach(html_part)
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    filename = attachment.get('filename')
                    content = attachment.get('content')
                    
                    if filename and content:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(content)
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {filename}'
                        )
                        msg.attach(part)
            
            # Send email
            if self.use_tls:
                smtp_server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                smtp_server.starttls()
            else:
                smtp_server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            
            smtp_server.login(self.email_address, self.password)
            
            # Prepare recipients
            recipients = [to]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            smtp_server.send_message(msg, to_addrs=recipients)
            smtp_server.quit()
            
            logger.info(f"Email sent successfully to {to}")
            return {
                "status": "success",
                "message": "Email sent successfully",
                "recipients": recipients
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"status": "error", "message": f"Failed to send email: {str(e)}"}
    
    async def receive_emails(
        self,
        folder: str = "INBOX",
        limit: int = 10,
        unread_only: bool = False
    ) -> Dict[str, Any]:
        """
        Receive emails from the specified folder
        
        Args:
            folder: Email folder to read from
            limit: Maximum number of emails to retrieve
            unread_only: Only retrieve unread emails
        """
        if not self.is_enabled or not self.is_authenticated:
            return {"status": "error", "message": "Email Integration is not enabled or authenticated"}
        
        try:
            # Connect to IMAP server
            if self.use_ssl:
                imap_server = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            else:
                imap_server = imaplib.IMAP4(self.imap_host, self.imap_port)
            
            imap_server.login(self.email_address, self.password)
            imap_server.select(folder)
            
            # Search for emails
            if unread_only:
                status, messages = imap_server.search(None, 'UNSEEN')
            else:
                status, messages = imap_server.search(None, 'ALL')
            
            if status != 'OK':
                imap_server.logout()
                return {"status": "error", "message": "Failed to search emails"}
            
            email_ids = messages[0].split()
            email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
            
            emails = []
            for email_id in email_ids:
                status, msg_data = imap_server.fetch(email_id, '(RFC822)')
                
                if status == 'OK':
                    email_message = email.message_from_bytes(msg_data[0][1])
                    
                    # Extract email information
                    email_info = {
                        "id": email_id.decode(),
                        "from": email_message.get('From'),
                        "to": email_message.get('To'),
                        "subject": email_message.get('Subject'),
                        "date": email_message.get('Date'),
                        "body": self._extract_email_body(email_message),
                        "attachments": self._extract_attachments(email_message)
                    }
                    
                    emails.append(email_info)
            
            imap_server.logout()
            
            logger.info(f"Retrieved {len(emails)} emails from {folder}")
            return {
                "status": "success",
                "emails": emails,
                "count": len(emails),
                "folder": folder
            }
            
        except Exception as e:
            logger.error(f"Failed to receive emails: {e}")
            return {"status": "error", "message": f"Failed to receive emails: {str(e)}"}
    
    def _extract_email_body(self, email_message) -> str:
        """Extract email body from email message"""
        body = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body = part.get_payload(decode=True).decode()
                    break
                elif content_type == "text/html" and "attachment" not in content_disposition and not body:
                    body = part.get_payload(decode=True).decode()
        else:
            body = email_message.get_payload(decode=True).decode()
        
        return body
    
    def _extract_attachments(self, email_message) -> List[Dict[str, Any]]:
        """Extract attachments from email message"""
        attachments = []
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_disposition = str(part.get("Content-Disposition"))
                
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        content = part.get_payload(decode=True)
                        attachments.append({
                            "filename": filename,
                            "content": content,
                            "size": len(content)
                        })
        
        return attachments
    
    async def mark_email_as_read(self, email_id: str, folder: str = "INBOX") -> Dict[str, Any]:
        """
        Mark an email as read
        
        Args:
            email_id: ID of the email to mark as read
            folder: Email folder containing the email
        """
        if not self.is_enabled or not self.is_authenticated:
            return {"status": "error", "message": "Email Integration is not enabled or authenticated"}
        
        try:
            # Connect to IMAP server
            if self.use_ssl:
                imap_server = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            else:
                imap_server = imaplib.IMAP4(self.imap_host, self.imap_port)
            
            imap_server.login(self.email_address, self.password)
            imap_server.select(folder)
            
            # Mark email as read
            imap_server.store(email_id, '+FLAGS', '\\Seen')
            imap_server.logout()
            
            logger.info(f"Marked email {email_id} as read")
            return {"status": "success", "message": "Email marked as read"}
            
        except Exception as e:
            logger.error(f"Failed to mark email as read: {e}")
            return {"status": "error", "message": f"Failed to mark email as read: {str(e)}"}
    
    async def delete_email(self, email_id: str, folder: str = "INBOX") -> Dict[str, Any]:
        """
        Delete an email
        
        Args:
            email_id: ID of the email to delete
            folder: Email folder containing the email
        """
        if not self.is_enabled or not self.is_authenticated:
            return {"status": "error", "message": "Email Integration is not enabled or authenticated"}
        
        try:
            # Connect to IMAP server
            if self.use_ssl:
                imap_server = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            else:
                imap_server = imaplib.IMAP4(self.imap_host, self.imap_port)
            
            imap_server.login(self.email_address, self.password)
            imap_server.select(folder)
            
            # Delete email
            imap_server.store(email_id, '+FLAGS', '\\Deleted')
            imap_server.expunge()
            imap_server.logout()
            
            logger.info(f"Deleted email {email_id}")
            return {"status": "success", "message": "Email deleted"}
            
        except Exception as e:
            logger.error(f"Failed to delete email: {e}")
            return {"status": "error", "message": f"Failed to delete email: {str(e)}"}
    
    async def get_folders(self) -> Dict[str, Any]:
        """
        Get list of email folders
        """
        if not self.is_enabled or not self.is_authenticated:
            return {"status": "error", "message": "Email Integration is not enabled or authenticated"}
        
        try:
            # Connect to IMAP server
            if self.use_ssl:
                imap_server = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            else:
                imap_server = imaplib.IMAP4(self.imap_host, self.imap_port)
            
            imap_server.login(self.email_address, self.password)
            
            # List folders
            status, folders = imap_server.list()
            
            if status == 'OK':
                folder_list = []
                for folder in folders:
                    folder_info = folder.decode().split(' "/" ')
                    if len(folder_info) >= 2:
                        folder_list.append(folder_info[1].strip('"'))
                
                imap_server.logout()
                
                return {
                    "status": "success",
                    "folders": folder_list
                }
            else:
                imap_server.logout()
                return {"status": "error", "message": "Failed to list folders"}
                
        except Exception as e:
            logger.error(f"Failed to get folders: {e}")
            return {"status": "error", "message": f"Failed to get folders: {str(e)}"}
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the email integration
        """
        return {
            "email_integration": True,
            "enabled": self.is_enabled,
            "authenticated": self.is_authenticated,
            "smtp_host": self.smtp_host,
            "imap_host": self.imap_host,
            "use_tls": self.use_tls,
            "use_ssl": self.use_ssl
        }