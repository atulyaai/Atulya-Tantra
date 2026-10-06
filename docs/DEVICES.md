# Devices: how Atulya controls things

Say what you want ("turn off the TV", "volume up 5 on the TV", "set the desk lamp brightness to 40"). Atulya matches
the words to a device you have added and to something that device can do. There is no list of brands in the code:
each device brings its own list of abilities, and new ones are added as data.

## Four ways to connect (use whichever your device supports)

| Way | Covers | You need |
|---|---|---|
| **Profile** (HTTP) | Anything controlled over HTTP on your network. Included: Roku, Kodi, Tasmota, WLED, Shelly (gen 1). Others can be added by writing or teaching a profile | The device and Atulya on the same network |
| **ADB** | Android phones, tablets, Android TV, Fire TV | `adb` installed, and wireless/network debugging switched on in the device |
| **Wake-on-LAN** | Switching on PCs, consoles and TVs that support it | The device's MAC address |
| **Home Assistant** | Thousands of brands (Samsung, LG, Sonos, Hue, Matter, Zigbee, Z-Wave, Tuya …) | A Home Assistant server; `HOME_ASSISTANT_URL` and `HOME_ASSISTANT_TOKEN` in `.env` |

**Honest limits.** "Any device in the world" is not literally possible. A device must offer some way in. Not covered
directly: Samsung/LG TVs (use Home Assistant, or ADB if it is Android TV), Chromecast/AirPlay, iPhones (Apple allows very little;
Home Assistant's companion app can do some of it), Bluetooth and infrared gadgets (Home Assistant with a Broadlink or ESPHome box
covers IR). The built-in profiles were written from the public protocol descriptions and tested against simulated devices, **not
against real hardware yet**.

## Your own devices (what to do for each)

Phones and computers paired through **Your devices** are associated with the signed-in account that issued the pairing code. They keep their device permission level and never gain admin access. Telegram accounts can share that profile after the owner creates a Telegram link code in the pairing panel and the allowlisted sender sends `/link CODE` to the bot. To unlink Telegram, use the same panel; the sender's separate Telegram chat history is kept.

| Device | How | One-time setup |
|---|---|---|
| **Samsung Smart TV** (2014 and newer) | `samsung` driver (built in) | Same Wi-Fi as the PC. Say "scan for devices", add it, then press a key; the TV shows "Allow Atulya?" once. "Turn on" needs Wake-on-LAN (add the TV's MAC as a `wol` device) and the TV's "Power on with mobile" setting |
| **Old Samsung plasma without Smart Hub** | Not possible over the network | These sets have no network port; they need an infrared blaster (not built) |
| **CloudWalker TV** | If it runs Android TV / Google TV (most recent models): `adb` driver | Settings > About: tap Build number 7 times, then Developer options > Network debugging (or USB debugging over Wi-Fi) on. Use the TV's IP address |
| **Xiaomi (Mi / Redmi / POCO) phone** | `adb` driver | Developer options (tap MIUI version 7 times) > Wireless debugging; on the PC run `adb pair IP:PORT` once with the code the phone shows, then Atulya can connect. Xiaomi also needs "USB debugging (Security settings)" for some actions such as typing and taps |

Not tried on any of these real devices yet; the Samsung driver is tested against a simulated TV that speaks the same websocket protocol.

## Using it

1. **Find devices:** say "scan for devices", or open **Action engine → Smart home hub → Scan network for devices**. This only looks.
2. **Add one:** say "add number 1 as living room TV", or press **Add**.
3. **Use it:** just speak. Or open the Smart home tile for buttons.
4. **Phone (Android):** switch on Wireless debugging, connect once with `adb pair` / `adb connect`, scan, add.
5. **A PC:** `device_add_manual` with driver `wol` and its MAC address.

## Teaching Atulya a device it doesn't know

Say "learn the device at 192.168.1.50" (add notes or paste its API instructions if you have them). Atulya looks at what the device
says, drafts a **profile**, and keeps it as a *proposal*. Read what it would send, then say "approve proposal a1b2c3". A profile can
only send HTTP requests to that one device on your own network, and any PUT/DELETE it drafts asks for a yes every time.

A profile is a small JSON file in `data/devices/profiles/` (see `atulya/device_profiles.json` for examples).

## Safety

- Only addresses on your own network are ever contacted (private ranges, `.local`). Public addresses are refused.
- Scanning is read-only.
- Anything a profile marks risky (unlock, restart, typing on a device) asks first, by voice or on screen.
- No raw shell is exposed for Android: only fixed actions, with every value checked.
- A parameter in a request is URL-encoded, so it can't change which path or query is sent.
