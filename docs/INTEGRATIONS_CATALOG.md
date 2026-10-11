# Atulya integration catalog and build order

This catalog orders capabilities by how broadly useful they are for a personal assistant. The order is **common first, medium next, rare last**. A row is a candidate, not a claim that the integration is installed or working. Check `INTEGRATION_STATUS.md` and the TODO before using one.

## Common — build first

| Capability | Plugin (`tools/plugins/`) | MCP tools (`tools/mcp/`) | Skill (`tools/skills/`) | Initial approach |
| --- | --- | --- | --- | --- |
| General information | Keep existing weather/news plugins | Read-only forecast and headlines, then web search/fetch | Daily briefing, research with sources | Existing Open-Meteo and BBC RSS; add search/fetch with bounded results |
| Local files and documents | Add scoped file/document plugin | Search/read within configured roots; document metadata | Find, summarize, compare, and answer from selected files | Local first; never expose whole-disk access by default |
| Calendar and reminders | Extend existing productivity plugin | List/create/update events in Atulya calendar; later CalDAV | Day plan, meeting preparation, reminders | Keep current SQLite calendar; add standard CalDAV support later |
| Email | Add separate mail plugin | IMAP search/read; SMTP draft/send as separately authorized actions | Inbox triage and draft-only replies | Read-only first; require confirmation before sending/deleting |
| Coding and source control | Add Git/project plugin | Scoped repository status, diff, search; guarded edits later | Code change, review, explain, and release workflows | Existing local project tools first; no arbitrary shell MCP tool |
| Notes and personal knowledge | Extend explicit memory / add notes plugin | Search/create/update only in selected notebook or local store | Capture note, retrieve facts, summarize notes | Explicitly saved information; provide inspect/export/delete |

## Medium — add after common workflows are stable

| Capability | Plugin | MCP | Skill | Initial approach |
| --- | --- | --- | --- | --- |
| Smart home / IoT | Home Assistant adapter | Entity state and allowlisted service calls; MQTT events via configured broker | Routines such as arrive, leave, and bedtime | Prefer Home Assistant's API; MQTT requires broker/device configuration and careful topic ACLs |
| Messaging | Per-service channel adapters | Search/read and draft/send with explicit scopes | Summarize conversations and prepare replies | Add one service at a time; private credentials and consent required |
| Cloud files and office suites | Nextcloud/compatible storage adapters | Scoped search/read/write operations | Prepare a document, spreadsheet, or presentation | Prefer self-hosted Nextcloud/WebDAV; add vendor-specific connections only when requested |
| Workflow automation | Webhook/automation adapters | Trigger named, preapproved workflows | Multi-step routine and troubleshooting | Use local scripts or a self-hosted open-source orchestrator; keep dangerous workflow triggers behind confirmation |
| Media production | Local image/audio/video plugins | Narrow generation/conversion tools | Create/edit media with user constraints | Reuse local runtimes where practical; record model license and hardware requirements |
| Contacts and address books | Local or CardDAV plugin | Scoped contact lookup/edit | Contact-aware scheduling and follow-up | CardDAV-compatible service; explicit permission before sending or sharing contact data |

## Rare — add only for a concrete user need

| Capability | Candidate direction | Guardrail |
| --- | --- | --- |
| Industrial/vehicle/energy systems | Protocol-specific adapters such as Modbus, OPC UA, CAN, or vendor APIs | Read-only first; commissioning, safety controls, and physical interlocks remain outside AI authority |
| Robotics and physical actuation | ROS 2 or device-vendor adapter | Simulated environment first; bounded commands and physical emergency stop required |
| Enterprise systems | Self-hosted ERP/CRM/ticketing adapters | Least-privilege account, tenant scoping, audit trail, and confirmation for writes |
| Finance, banking, or purchases | Provider-approved read-only APIs where available | Never collect banking passwords; no autonomous trades, purchases, or money movement |
| Identity, biometrics, and access control | Defer unless explicitly required | Never treat face/voice recognition as authentication; keep passkey security boundary |
| Specialty research / lab equipment | Purpose-built plugin and MCP tools | Validate data provenance and equipment-specific safety constraints |

## Shared implementation rules

1. **Plugin** owns the replaceable implementation and declares configuration, dependencies, capabilities, and health.
2. **MCP** exposes only a narrow allowlist of plugin operations; tools use typed inputs, bounded outputs, timeouts, authorization, and sanitized errors.
3. **Skill** describes when and how to combine available tools. It cannot install a plugin, obtain consent, or grant access.
4. Every capability needs one user-visible end-to-end path: clean setup, discoverability, successful operation, unavailable-service behavior, disable/remove, and regression checks.
5. Automate setup for local components where safe. OAuth consent, credentials, passkey enrollment, browser device permissions, and physical hardware may require user action; surface that state clearly instead of pretending setup is zero-touch.
6. Prefer open standards and self-hostable projects. Review upstream maintenance, license, authentication, and data flow before selecting an implementation. Optional integrations must not block core startup.

## Candidate open-source ecosystem

- [Home Assistant MQTT integration](https://www.home-assistant.io/integrations/mqtt.html) for smart-home entities and MQTT messaging.
- [Nextcloud Calendar developer documentation](https://github.com/nextcloud/calendar/wiki/Developer-Resources) for standards-based calendar interoperability, including CalDAV.
- [n8n documentation](https://docs.n8n.io/) describes a self-hostable automation product, but n8n is fair-code rather than OSI open source; evaluate its license and fit before adopting it as an Atulya dependency.

These are references for evaluation, not bundled dependencies or current integrations. The first implementation milestone is the **common** section above.
