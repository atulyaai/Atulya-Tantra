"""Find devices on your own network. Read-only: nothing is changed on any device, and nothing leaves your network.

Four ways, all at once:
  * profile probing: ask each address the questions each profile uses to recognise its device,
  * SSDP/UPnP: devices announce themselves (TVs, speakers, consoles, routers),
  * ADB: Android devices you have already connected or plugged in,
  * Home Assistant: every device it manages.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from atulya.devices import adb as adbmod
from atulya.devices.base import DeviceError, is_lan_host
from atulya.devices.ha import KIND, HomeAssistantDriver
from atulya.devices.profile_driver import load_profiles

SSDP_ADDR = ("239.255.255.250", 1900)


@dataclass
class Candidate:
    host: str
    driver: str                       # profile | adb | homeassistant | unknown
    label: str
    kind: str = "device"
    evidence: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def __post_init__(self) -> None:
        self.id = hashlib.sha1(f"{self.driver}|{self.host}|{sorted(self.config.items())}".encode()).hexdigest()[:8]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def local_subnet_hosts() -> list[str]:
    """Every address in this computer's /24 (never more than 254), or [] if we are not on a private network."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))     # picks the outgoing interface; sends nothing
            me = s.getsockname()[0]
    except OSError:
        return []
    ip = ipaddress.ip_address(me)
    if not ip.is_private:
        return []
    net = ipaddress.ip_network(f"{me}/24", strict=False)
    return [str(h) for h in net.hosts() if str(h) != me]


async def _probe(client: httpx.AsyncClient, host: str, profile: dict[str, Any], port: int) -> Candidate | None:
    scheme = profile.get("scheme", "http")
    for rule in profile.get("detect", []):
        try:
            resp = await client.get(f"{scheme}://{host}:{port}{rule['path']}")
        except (httpx.HTTPError, OSError):
            return None
        if resp.status_code >= 400 or rule.get("contains", "") not in resp.text:
            return None
    if not profile.get("detect"):
        return None
    return Candidate(host=host, driver="profile", label=profile.get("label", profile["id"]), kind=profile.get("kind", "device"),
                     evidence=f"answered like a {profile.get('label', profile['id'])}", config={"profile": profile["id"], "port": port})


async def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        _r, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except (OSError, asyncio.TimeoutError):
        return False
    w.close()
    return True


async def probe_hosts(hosts: list[str], profiles: dict[str, dict[str, Any]], timeout: float = 1.5) -> list[Candidate]:
    """Quick check of which (address, port) pairs answer at all, then ask only those the profile questions."""
    lan = [h for h in hosts if is_lan_host(h)]
    ports = sorted({int(p.get("port", 80)) for p in profiles.values()})
    sem = asyncio.Semaphore(256)

    async def check(host: str, port: int) -> tuple[str, int] | None:
        async with sem:
            return (host, port) if await _port_open(host, port) else None

    open_pairs = {x for x in await asyncio.gather(*(check(h, p) for h in lan for p in ports)) if x}
    found: list[Candidate] = []
    async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=False) as client:
        async def one(host: str, profile: dict[str, Any]) -> None:
            hit = await _probe(client, host, profile, int(profile.get("port", 80)))
            if hit:
                found.append(hit)
        await asyncio.gather(*(one(h, p) for h in lan for p in profiles.values() if (h, int(p.get("port", 80))) in open_pairs))
    return found


def parse_ssdp(data: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in data.decode("utf-8", "replace").split("\r\n")[1:]:
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
    return headers


async def ssdp_search(timeout: float = 2.0, target: tuple[str, int] = SSDP_ADDR) -> list[tuple[str, dict[str, str]]]:
    """Ask the network who is there; returns (ip, headers) for each reply."""
    msg = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 1\r\nST: ssdp:all\r\n\r\n").encode()
    loop = asyncio.get_running_loop()

    def listen() -> list[tuple[str, dict[str, str]]]:
        out: list[tuple[str, dict[str, str]]] = []
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.4)
                s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
                s.sendto(msg, target)
                end = loop.time() + timeout
                while loop.time() < end:
                    try:
                        data, addr = s.recvfrom(4096)
                    except socket.timeout:
                        continue
                    out.append((addr[0], parse_ssdp(data)))
        except OSError:
            return out
        return out
    return await asyncio.to_thread(listen)


def _match_ssdp(replies: list[tuple[str, dict[str, str]]], profiles: dict[str, dict[str, Any]]) -> list[Candidate]:
    seen: dict[str, Candidate] = {}
    for ip, h in replies:
        if not is_lan_host(ip) or ip in seen:
            continue
        banner = " ".join(h.get(k, "") for k in ("server", "st", "usn", "location")).lower()
        profile = next((p for p in profiles.values() if p.get("ssdp", {}).get("contains", "\0") in banner), None)
        if profile:
            seen[ip] = Candidate(ip, "profile", profile.get("label", profile["id"]), profile.get("kind", "device"),
                                 f"announced itself: {h.get('server', '')[:60]}", {"profile": profile["id"], "port": int(profile.get("port", 80))})
        else:
            seen[ip] = Candidate(ip, "unknown", (h.get("server") or h.get("st") or "Network device")[:60], "device",
                                 f"announced itself ({h.get('st', '')[:40]}); no profile yet. Say “learn this device” to teach me.", {})
    return list(seen.values())


async def adb_devices() -> list[Candidate]:
    if not adbmod.adb_path():
        return []
    try:
        out = await adbmod.run_adb("devices", "-l", timeout=6)
    except DeviceError:
        return []
    found = []
    for line in str(out).splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            model = next((p.split(":", 1)[1] for p in parts if p.startswith("model:")), "Android device")
            host = parts[0].split(":")[0]
            found.append(Candidate(host, "adb", model.replace("_", " "), "phone", "connected through adb", {"serial": parts[0]}))
    return found


async def discover(hosts: list[str] | None = None, profiles: dict[str, dict[str, Any]] | None = None, *, ssdp: bool = True,
                   ssdp_target: tuple[str, int] = SSDP_ADDR, ha: HomeAssistantDriver | None = None, use_adb: bool = True) -> list[Candidate]:
    """Everything findable right now, best evidence first, one entry per (driver, host, thing)."""
    profiles = profiles if profiles is not None else load_profiles()
    hosts = hosts if hosts is not None else local_subnet_hosts()
    tasks: list[Any] = [probe_hosts(hosts, profiles)]
    if ssdp:
        tasks.append(ssdp_search(target=ssdp_target))
    if use_adb:
        tasks.append(adb_devices())
    results = await asyncio.gather(*tasks, return_exceptions=True)
    found: list[Candidate] = []
    probed = results[0] if not isinstance(results[0], BaseException) else []
    found += probed
    if ssdp and not isinstance(results[1], BaseException):
        have = {c.host for c in probed}
        found += [c for c in _match_ssdp(results[1], profiles) if c.host not in have]
    if use_adb and not isinstance(results[-1], BaseException):
        found += results[-1]
    driver = ha if ha is not None else HomeAssistantDriver()
    if driver.configured:
        try:
            found += [Candidate(driver.url, "homeassistant", e["name"], KIND.get(e["domain"], "device"), f"Home Assistant {e['domain']}",
                                {"entity": e["entity"]}) for e in await driver.entities()]
        except DeviceError:
            pass
    return found
