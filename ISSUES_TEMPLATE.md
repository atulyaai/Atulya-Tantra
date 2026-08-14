# Atulya-Tantra Issue Tracker

## Current Status
- **Local-first AI workspace** with NP-DNA architecture
- **Modular design** - atulya/, brain/, yantra/, drishti/, tantra/, config/
- **Active development** - multiple product lines and AI components

## Recently Fixed (Local Context)
- Code quality improvements in core modules
- Error handling improvements in CLI and provider systems
- Production readiness check enhancements

## Product Line Assessment
### Core AI/Ecosystem (NEeded)
- **Atulya-Cpanel** - Operational foundation for Atulya Tantra framework
  - Monitors Tantra-LLM health, tracks token burn
  - Synchronizes modular nervous system components (Trace, Smriti, Raksha)
  - Explicitly described as "the operational foundation of the Atulya Tantra framework"

- **Tantra-Kosha** - Modular nervous system component
  - Reference in Cpanel for system architecture synchronization

### Separate Product Lines (Not needed for AI core)
- **Atulya-Accounting-ERP** - Business accounting/ERP system
- **Atulya-Automation-Hub** - Workflow automation platform
- **Atulya-Office** - Office automation tools (Excel, Word, Outlook, PowerPoint)
- **Atulya-HR-Suite** - HR and payroll workflow suite
- **Atulya-Data-Scruber** - Data cleaning tool
- **Atulya-All-File-Converter** - File conversion utility
- **Atulya-GST-Suite** - GST compliance toolkit

### Related but Distinct
- **Atulya-Launch** - Self-hosted server management panel
  - Useful for infrastructure management but distinct from AI focus

## Roadmap & New Tech Opportunities

### atulya/ Module Improvements
1. **Provider Router enhancements** - Add more fallback providers and better failover logic
2. **LLM bridge improvements** - Better integration with various LLM APIs
3. **Session management** - Enhanced chat history persistence and cross-device sync

### yantra/ Module Improvements
1. **Capabilities system** - Expand gated tools and workflow browser/voice integration
2. **MCP server/client** - Improve Model Context Protocol implementation
3. **Self-improvement bridge** - Unify self-improvement and self-repair mechanisms

### drishti/ Module Improvements
1. **WebUI enhancements** - Better frontend/backend API integration
2. **Dashboard APIs** - Enhanced monitoring and control endpoints
3. **Mobile/desktop experience** - Live mode and chat improvements

### config/ Module Improvements
1. **Environment management** - Better .env handling and default configuration
2. **MCP server config** - Enhanced OAuth and credential management

### Gateway/Integration Improvements
1. **NP-DNA network integration** - Better coordination between Tantra, Yantra, Drishti
2. **Local deployment scripts** - Enhanced automation for local-first setup
3. **Dashboard and automation APIs** - Unified endpoint for all components

## Test Coverage Gaps
- Add unit tests for `_merge_env_defaults()` in cli.py
- Add integration tests for ProviderRouter fallback chain
- Add tests for session management (_load_session, _save_session)
- Add tests for production readiness checks

## Contributing
See the project structure and guidelines in the respective README files. Contributions should enhance the free-first, local-first philosophy of Atulya OS.