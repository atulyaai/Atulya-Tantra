# Restricted server operations

The operations worker is a separate unprivileged process. It accepts only approved restarts of `atulya.service`; it does not accept shell text, arbitrary services, source changes or file paths. A request is queued after owner approval, claimed once, and settled from service-manager and HTTP-health results. Uncertain jobs are not replayed. This worker is not a general code-repair or deployment agent.

## Installation on the existing Ubuntu host

Review `tools/atulya-operations.service` against the actual user, repository and data paths. The supplied unit targets the existing `/home/ubuntu/Atulya-Tantra` installation. Install it only after the server code is updated and tests pass:

```sh
sudo install -m 644 tools/atulya-operations.service /etc/systemd/system/atulya-operations.service
sudo systemctl daemon-reload
sudo systemctl enable --now atulya-operations.service
```

The worker's user needs permission to invoke the exact command `sudo -n systemctl restart atulya.service`. Do not grant a wildcard systemctl rule or general shell/sudo access for this feature. An administrator must inspect the executable's resolved path and existing sudo policy before installing an exact-command rule. Without that permission the operation returns a failed receipt. Existing deployment privileges must not be broadened merely to get a green result.

The worker does not load model, Google, Telegram or SSH credentials. It uses only the explicit data directory, local systemd and loopback health endpoint. Its service uses a process lock so duplicate workers cannot overlap restarts.

## Verification

1. `Server operations` should show a fresh worker heartbeat.
2. Ask Atulya to restart its service; verify that an approval is requested and no job runs beforehand.
3. Approve once, expect a brief web disconnect, then refresh the operations page.
4. Accept success only when the receipt states both systemd active and local health passed.
5. Denied, expired, crashed and unconfirmed requests must not be automatically replayed.

## Monitoring

The worker records transitions for the Atulya service and critical disk/memory usage (95%). Normal unchanged readings are quiet. The application delivers recorded alerts using the existing owner Telegram notification path and stores provider acceptance, not device delivery. Muting suppresses pending alerts and avoids replaying muted events when unmuted. Events older than a day expire. If the web service is down, alert delivery is delayed until it recovers; independent out-of-process delivery is not implemented.

Use `Server operations` to inspect jobs, alerts and mute state. Stop the worker with `sudo systemctl disable --now atulya-operations.service` to disconnect execution without changing other tools.
