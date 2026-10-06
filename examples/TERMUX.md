# Termux phone companion

The companion uses the phone device token issued by Atulya's pairing screen. It stores that token in Termux's private config directory after first pairing. Never paste the token into this repository or a chat.

1. Install Termux and Termux:API from the same trusted source. In Termux run `pkg install termux-api curl jq`. **PASS:** `termux-sms-list -l 1` runs after granting the SMS permission. **FAIL:** install the matching Termux:API app and grant only the permissions for features you plan to use.
2. In Atulya, open the Devices or Pairing screen and create a one-time phone pairing code. **PASS:** a short-lived code is shown. **FAIL:** sign in as the admin and check that device pairing is enabled.
3. In Termux, set the server address and pairing code, then start the helper:
   `export ATULYA_SERVER=https://your-server.example.com`
   `export ATULYA_PAIR_CODE='your-one-time-code'`
   `bash examples/termux_phone.sh`
   **PASS:** it reports that the companion is connected and saves its token under `$HOME/.config/atulya/`. **FAIL:** check the server URL, code expiry, and network connection; create a fresh pairing code if needed.
4. Forward only the categories you want. In a second Termux session, set `ATULYA_SYNC_SMS=on`, `ATULYA_SYNC_NOTIFICATIONS=on`, and/or `ATULYA_SYNC_LOCATION=on`, then run the helper again. SMS and notifications may contain private information; grant those permissions only if you want those items sent to your Atulya server. **PASS:** the admin Phone inbox shows received items. **FAIL:** check that the corresponding Android permission was granted and the phone token has read access.
5. To make the phone ring from Atulya, pair it with full phone permission and keep the companion running. Request `ring` from the Atulya device controls. **PASS:** Termux vibrates and plays an available system alert sound. **FAIL:** check full permission, Android battery restrictions, and Termux:API notification/audio permissions.

For manual use, the helper also accepts `sync`, `sms`, `notifications`, or `location` to send once and exit. `bash examples/termux_phone.sh ring` rings locally without contacting the server; set `ATULYA_RINGTONE` to choose an audio file. `ATULYA_SERVER_URL` remains supported as an alias for `ATULYA_SERVER`.

To stop forwarding, stop the Termux process or turn the `ATULYA_SYNC_*` values off. Revoke a paired device token from Atulya's device management screen if the phone is lost.
