# Deploy the tested functional fixes

The ZIP is a selective source bundle, not an installer or a copy of private server data. It includes file hashes and test evidence. The current workspace has incomplete Git metadata, so no commit, push, PR or production update has been performed.

1. Apply/review the changed source in the actual repository. Preserve concurrent changes from other contributors. This bundle must not overwrite the server's `.env`, `data/`, `models/`, signing keys or connection credentials.
2. Install the music dependency on the server through the project manifest:

   ```sh
   .venv/bin/python -m pip install -e '.[music,mcp]'
   .venv/bin/python -m pip check
   ```

   The new music extra pins the version used for the successful live metadata search. The legacy deploy script only installs the existing lock file, so this extra needs to be installed explicitly or added to the server's regenerated lock before deployment. No media or model download is required for metadata search.
3. Back up the running server and deploy through the existing controlled process. The patched deployment script now rolls back when the functional selftest fails, even if `/api/health` returns HTTP 200. Its shell behavior test requires a POSIX runner; it is skipped on this Windows environment because no POSIX shell is installed.
4. Run the application selftest, then inspect authenticated `/api/readiness` and test each real connection. A healthy public endpoint alone is insufficient.
5. Verify this PC in Devices with a ping receipt. Connect/test the owner's Google service scopes through Connections. Test music by song name, select a result, and inspect the player receipt. Enable proactive proposals only when wanted; faults are checked every five minutes, AI proposals/alerts are limited to changed findings at most hourly.
6. Verify the installed Android APK and Telegram separately. This change bundle does not add Android background AgentHub execution and does not claim physical playback, phone sound/vibration, email recipient delivery or a successful calendar mutation without a real receipt.

The local setup window and PC companion can pair with the existing live pairing API before the server UI changes are deployed. Start with `ping` and `battery_status`; grant additional abilities only when needed. See `CONNECT-AND-VERIFY.md`.
