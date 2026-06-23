---
name: email
description: Send, read, and manage emails
tools: [configure_email, send_email, fetch_emails]
---
# Email Skill

You can help the user manage their email. When the user asks about email:
1. If not configured, suggest they configure email first
2. Use `fetch_emails(limit)` to read recent emails
3. Use `send_email(to, subject, body)` to send
4. Summarize email content naturally
