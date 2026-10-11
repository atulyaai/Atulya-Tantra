---
name: daily-briefing
description: Prepare a short daily briefing from current weather and news when the user asks what is happening today or requests a daily briefing.
---

# Daily briefing

## Required tools

- `weather(city)` from the Atulya MCP server.
- `news_headlines(limit)` from the Atulya MCP server.

## Workflow

1. If the user's location is not known from the current conversation, ask which city to use. Do not infer a precise location.
2. Fetch weather and up to five headlines concurrently when possible.
3. Present the weather first, followed by a concise list of headlines. Keep the source names and any supplied links.
4. If one tool fails, report that section as unavailable and still return the other result. Never fabricate current conditions or news.

## Permissions and privacy

- This workflow is read-only and sends only the requested city to Open-Meteo.
- Do not include calendar, email, or private account details; those tools are not part of this skill.
- If the MCP server or required tool is unavailable, say so and offer a general, non-current fallback only if the user wants one.

## Example triggers

- "Give me my daily briefing."
- "What's the weather and news today?"
