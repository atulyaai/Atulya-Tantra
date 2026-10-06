#!/data/data/com.termux/files/usr/bin/bash
# Optional Termux companion. Grant Android permissions only for features you use.
set -euo pipefail

SERVER=${ATULYA_SERVER:-${ATULYA_SERVER_URL:-}}
TOKEN=${ATULYA_DEVICE_TOKEN:-}
POLL_SECONDS=${ATULYA_POLL_SECONDS:-15}
RINGTONE=${ATULYA_RINGTONE:-}

usage() {
  printf 'Usage: %s [listen|sync|sms|notifications|location|ring]\n' "$0" >&2
}

ring_local() {
  command -v termux-media-player >/dev/null || { echo 'Install Termux:API with: pkg install termux-api' >&2; return 1; }
  command -v termux-vibrate >/dev/null && termux-vibrate -d 1000 -f || true
  local ring_file=$RINGTONE candidate
  if [[ ! -r "$ring_file" ]]; then
    ring_file=''
    for candidate in /system/media/audio/alarms/*.ogg /system/media/audio/ringtones/*.ogg /system/media/audio/notifications/*.ogg; do
      if [[ -r "$candidate" ]]; then ring_file=$candidate; break; fi
    done
  fi
  [[ -n "$ring_file" ]] || { echo 'No readable ringtone found; set ATULYA_RINGTONE to an audio file.' >&2; return 1; }
  termux-media-player play "$ring_file"
  sleep 10
  termux-media-player stop || true
}

if [[ "${1:-}" == ring ]]; then
  ring_local
  exit $?
fi
case "${1:-}" in
  ''|listen|sync|sms|notifications|location) ;;
  *) usage; exit 2 ;;
esac

if [[ "$SERVER" != https://* ]]; then
  echo "Set ATULYA_SERVER to where your own Atulya runs, e.g. https://your-server.example.com" >&2
  exit 2
fi
for command in curl jq; do
  command -v "$command" >/dev/null || { echo "Install $command with pkg install $command" >&2; exit 2; }
done

TOKEN_FILE="$HOME/.config/atulya/device-token"
if [[ -z "$TOKEN" && -r "$TOKEN_FILE" ]]; then TOKEN=$(<"$TOKEN_FILE"); fi
if [[ -z "$TOKEN" ]]; then
  PAIR_CODE=${ATULYA_PAIR_CODE:-}
  if [[ -z "$PAIR_CODE" ]]; then read -r -p "One-time pairing code from Atulya: " PAIR_CODE; fi
  pairing=$(curl --fail --silent --show-error --max-time 20 -H 'Content-Type: application/json' \
    --data "$(jq -cn --arg code "$PAIR_CODE" '{code:$code,name:"Termux phone",kind:"phone"}')" \
    "$SERVER/api/pairing/enroll") || { echo "Pairing failed. Check the code and server address." >&2; exit 2; }
  TOKEN=$(jq -er '.token' <<<"$pairing")
  mkdir -p "$(dirname "$TOKEN_FILE")"
  (umask 077; printf '%s' "$TOKEN" > "$TOKEN_FILE")
  chmod 600 "$TOKEN_FILE"
  unset pairing PAIR_CODE
fi

curl_auth() { curl --config <(printf 'header = "X-Atulya-Token: %s"\n' "$TOKEN") "$@"; }

post_items() {
  local kind=$1 json=$2
  curl_auth --fail --silent --show-error --max-time 20 \
    -H 'Content-Type: application/json' --data-binary @- "$SERVER/api/phone/$kind" <<<"$json"
}

sync_sms() {
  local payload
  payload=$(termux-sms-list -l 100 | jq -c '{items: [.[] | {address, body, date, type}]}')
  post_items sms "$payload"
}

sync_notifications() {
  local payload
  payload=$(termux-notification-list | jq -c '{items: [.[]? | {packageName:(.packageName // "" | tostring | .[0:100]), id, title:(.title // "" | tostring | .[0:500]), content:(.content // "" | tostring | .[0:2500]), postedTime}] | .[:100]}')
  post_items notifications "$payload"
}

sync_location() {
  local payload
  payload=$(termux-location -p network -r once | jq -c '{items: [. | {latitude, longitude, accuracy, altitude, bearing, speed, elapsedMs, provider}]}')
  post_items location "$payload"
}

run_command() {
  local action=$1 result='{"ok":true}'
  case "$action" in
    ring)
      ring_local || true
      ;;
    locate)
      sync_location >/dev/null
      ;;
    *) result='{"ok":false,"error":"unsupported command"}' ;;
  esac
  jq -cn --argjson r "$result" '{result:$r}' | curl_auth --fail --silent --show-error --max-time 20 -X POST \
    -H 'Content-Type: application/json' --data-binary @- \
    "$SERVER/api/phone/commands/$COMMAND_ID/result"
}

echo "Termux phone companion connected. Press Ctrl+C to stop."
case "${1:-listen}" in
  sms) sync_sms; exit $? ;;
  notifications) sync_notifications; exit $? ;;
  location) sync_location; exit $? ;;
  sync) sync_sms; sync_notifications; sync_location; exit $? ;;
esac
while true; do
  for feature in sms notifications location; do
    case "$feature" in
      sms) [[ ${ATULYA_SYNC_SMS:-off} == on ]] && sync_sms || true ;;
      notifications) [[ ${ATULYA_SYNC_NOTIFICATIONS:-off} == on ]] && sync_notifications || true ;;
      location) [[ ${ATULYA_SYNC_LOCATION:-off} == on ]] && sync_location || true ;;
    esac
  done
  commands=$(curl_auth --fail --silent --show-error --max-time 20 "$SERVER/api/phone/commands") || { sleep "$POLL_SECONDS"; continue; }
  while IFS=$'\t' read -r COMMAND_ID action; do
    [[ -n "$COMMAND_ID" ]] && run_command "$action"
  done < <(jq -r '.commands[]? | [.id,.action] | @tsv' <<<"$commands")
  sleep "$POLL_SECONDS"
done
