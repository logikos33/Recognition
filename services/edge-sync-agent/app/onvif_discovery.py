"""WS-Discovery scanner — finds ONVIF cameras on the edge's isolated LAN (task-096).

C-04 investigation (full version in the task-096 PR description): no ONVIF
*discovery* code existed anywhere in this repo before this task. The only
ONVIF code that exists is `onvif_recorder_client.py` (task-091) — it speaks
ONVIF Profile G to a NVR/gravador whose host is *already known* (from
RECORDER_HOST env). WS-Discovery is a different protocol entirely: a
multicast UDP probe (239.255.255.250:3702) that ANY ONVIF device on the
subnet may answer, used to find devices whose IP is not known in advance —
exactly the "no IP hard-coded" requirement of ADR-0020/task-096. This module
is greenfield; it reuses `RTSPUrlValidator` (task-091's port) rather than
duplicating SSRF/command-injection logic, and reuses the same
"regex-over-DOM" parsing discipline as `onvif_recorder_client.py` (see
`_parse_probe_matches` docstring for why).

Threat model (risk:security — read before touching parsing logic):
ANY device on the LAN can answer the multicast probe, including a spoofed or
malicious one — this is UDP, unauthenticated, unencrypted. So:
  - Parsing is defensive: a malformed/truncated/non-UTF-8 datagram is logged
    and skipped, never raises out of `discover_devices` (one bad responder
    must not abort discovery of the rest).
  - `max_responses` caps how many datagrams are processed per scan — bounds
    the cost of a flood of spoofed UDP replies (DoS resistance).
  - `timeout_seconds` bounds total wall-clock time — `discover_devices` never
    blocks indefinitely waiting for a response that may never come.
  - Every address that ends up in a *suggested* RTSP URL — whether the UDP
    packet's source IP or a XAddr string reported inside the packet body —
    is passed through `RTSPUrlValidator` before being handed back. Network
    content is never trusted enough to build a URL without validation
    (`build_suggested_rtsp_url`, `fetch_device_information`).

PENDÊNCIA (same discipline as task-090/091's onvif_recorder_client.py): no
call in this module has been exercised against a real ONVIF camera or real
multicast traffic — no camera hardware/isolated subnet available in this
environment (task-096 depends on task-095, blocked on hardware — see
tools/agent-driver/queue-hardware.txt). Tests use an injectable
socket-like object (`sock_factory`), never a real UDP socket. Validate
against RVB's real cameras once the MikroTik + subnet exist (task-095/097).
"""

from __future__ import annotations

import logging
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

import httpx

from .recorder_client import RecorderError
from .rtsp_validator import RTSPUrlValidator

logger = logging.getLogger(__name__)

_WSD_MULTICAST_ADDR = "239.255.255.250"
_WSD_MULTICAST_PORT = 3702
_DEFAULT_TIMEOUT_SECONDS = 3.0
_DEFAULT_MAX_RESPONSES = 50
_DEFAULT_RTSP_PORT = 554
_DEFAULT_HTTP_TIMEOUT_SECONDS = 5.0
_MAX_DATAGRAM_SIZE = 65535  # UDP theoretical max — bounds a single recvfrom() read


class OnvifDiscoveryError(Exception):
    """Raised only for setup-time failures (e.g. socket creation). Never
    raised mid-scan for a single bad responder — see module docstring."""


@dataclass(frozen=True)
class DiscoveredDevice:
    """One WS-Discovery ProbeMatch, defensively parsed.

    `source_ip` is what the OS reports as the UDP packet's origin — harder
    to spoof from an off-path attacker than the packet's *content*, but
    still passed through RTSPUrlValidator before use (see module docstring).
    `xaddrs`/`types`/`scopes`/`endpoint_reference` are attacker-controlled
    packet content and are surfaced as-is for *display* only — never used to
    build a URL that reaches ffmpeg/DeepStream without separate validation.
    """

    source_ip: str
    xaddrs: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    endpoint_reference: str | None = None


@dataclass(frozen=True)
class DeviceInformation:
    """Result of a GetDeviceInformation call against a discovered device's XAddr."""

    manufacturer: str | None
    model: str | None
    firmware_version: str | None
    serial_number: str | None
    hardware_id: str | None


def _default_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return sock


def _build_probe_message(message_id: str) -> str:
    """Minimal WS-Discovery Probe, scoped to ONVIF NetworkVideoTransmitter.

    Same envelope shape used by the ONVIF Discovery spec (WS-Discovery 1.1
    profile) and by common ONVIF discovery tooling — a bare `<d:Probe/>`
    with no `<d:Types>`/`<d:Scopes>` would also work (broader match) but
    scoping to NetworkVideoTransmitter avoids waking up unrelated ONVIF
    devices (NVRs, encoders) that also answer WS-Discovery.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
        'xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
        'xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
        "<e:Header>"
        f"<w:MessageID>uuid:{message_id}</w:MessageID>"
        '<w:To e:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>'
        '<w:Action e:mustUnderstand="1">'
        "http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe"
        "</w:Action>"
        "</e:Header>"
        "<e:Body>"
        "<d:Probe>"
        "<d:Types>dn:NetworkVideoTransmitter</d:Types>"
        "</d:Probe>"
        "</e:Body>"
        "</e:Envelope>"
    )


def discover_devices(
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    max_responses: int = _DEFAULT_MAX_RESPONSES,
    multicast_addr: str = _WSD_MULTICAST_ADDR,
    multicast_port: int = _WSD_MULTICAST_PORT,
    sock_factory: Callable[[], Any] = _default_socket,
) -> list[DiscoveredDevice]:
    """Sends one WS-Discovery Probe and collects ProbeMatch replies.

    Bounded on two independent axes (both required — either alone is
    insufficient against a hostile subnet): `timeout_seconds` (wall clock)
    and `max_responses` (datagram count, DoS cap). A malformed datagram is
    logged and skipped, never raised — see module docstring.

    `sock_factory` is injectable for tests (defaults to a real UDP socket) —
    same DI style as `rtsp_clip_stream.stream_rtsp_clip`'s injectable
    `popen`. The fake used in tests only needs `settimeout`, `sendto`,
    `recvfrom`, and `close`.
    """
    if timeout_seconds <= 0:
        raise OnvifDiscoveryError("timeout_seconds deve ser positivo")
    if max_responses <= 0:
        raise OnvifDiscoveryError("max_responses deve ser positivo")

    try:
        sock = sock_factory()
    except OSError as exc:
        raise OnvifDiscoveryError(f"não foi possível criar socket UDP: {exc}") from exc

    message_id = str(uuid4())
    probe = _build_probe_message(message_id)

    devices: list[DiscoveredDevice] = []
    try:
        try:
            sock.settimeout(timeout_seconds)
            sock.sendto(probe.encode("utf-8"), (multicast_addr, multicast_port))
        except OSError as exc:
            raise OnvifDiscoveryError(f"falha ao enviar probe WS-Discovery: {exc}") from exc

        deadline = time.monotonic() + timeout_seconds
        responses_seen = 0
        while responses_seen < max_responses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                sock.settimeout(remaining)
                data, addr = sock.recvfrom(_MAX_DATAGRAM_SIZE)
            except socket.timeout:
                break
            except OSError as exc:
                logger.warning("onvif_discovery_recv_error err=%s", exc)
                break

            responses_seen += 1
            source_ip = addr[0] if addr else ""
            try:
                devices.extend(_parse_probe_matches(data, source_ip))
            except Exception as exc:  # noqa: BLE001 — one bad datagram must not abort the scan
                logger.warning(
                    "onvif_discovery_parse_error source_ip=%s err=%s", source_ip, exc
                )
                continue
    finally:
        sock.close()

    logger.info(
        "onvif_discovery_scan_complete devices_found=%d",
        len(devices),
    )
    return devices


# ── defensive parsing ─────────────────────────────────────────────────────
#
# Regex-over-DOM, not xml.etree/lxml — same discipline as
# onvif_recorder_client.py's SOAP response parsing:
#   1. ONVIF/WS-Discovery responses vary namespace prefixes by vendor
#      (wsd:/d:/none) — matching leaf elements by regex tolerates that
#      without an exact-namespace match.
#   2. It sidesteps XXE by construction: no DOM/SAX parser is ever invoked
#      on attacker-supplied bytes, so there is no DOCTYPE/ENTITY expansion
#      surface to disable in the first place.
_PROBE_MATCH_BLOCK = re.compile(
    r"<(?:\w+:)?ProbeMatch>(.*?)</(?:\w+:)?ProbeMatch>", re.DOTALL
)
_XADDRS_RE = re.compile(r"<(?:\w+:)?XAddrs>([^<]*)</(?:\w+:)?XAddrs>")
_TYPES_RE = re.compile(r"<(?:\w+:)?Types>([^<]*)</(?:\w+:)?Types>")
_SCOPES_RE = re.compile(r"<(?:\w+:)?Scopes>([^<]*)</(?:\w+:)?Scopes>")
_ADDRESS_RE = re.compile(r"<(?:\w+:)?Address>([^<]*)</(?:\w+:)?Address>")


def _parse_probe_matches(data: bytes, source_ip: str) -> list[DiscoveredDevice]:
    """Extracts every ProbeMatch in one WS-Discovery envelope.

    Returns an empty list (never raises) for anything that isn't a
    recognizable ProbeMatch envelope — non-UTF-8 bytes, garbage, an
    unrelated WS-Discovery message type (Hello/Bye/ResolveMatches). A
    single malformed ProbeMatch block inside an otherwise valid envelope is
    skipped, not fatal to the rest.
    """
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — decode() with errors="replace" shouldn't raise, defensive anyway
        return []

    devices: list[DiscoveredDevice] = []
    for block in _PROBE_MATCH_BLOCK.findall(text):
        xaddrs_match = _XADDRS_RE.search(block)
        xaddrs = xaddrs_match.group(1).split() if xaddrs_match else []
        types_match = _TYPES_RE.search(block)
        types = types_match.group(1).split() if types_match else []
        scopes_match = _SCOPES_RE.search(block)
        scopes = scopes_match.group(1).split() if scopes_match else []
        address_match = _ADDRESS_RE.search(block)
        endpoint_reference = address_match.group(1).strip() if address_match else None

        devices.append(
            DiscoveredDevice(
                source_ip=source_ip,
                xaddrs=xaddrs,
                types=types,
                scopes=scopes,
                endpoint_reference=endpoint_reference,
            )
        )
    return devices


# ── suggested RTSP URL (validated before ever leaving this module) ────────


def build_suggested_rtsp_url(
    source_ip: str, port: int = _DEFAULT_RTSP_PORT
) -> str | None:
    """Builds a bare `rtsp://host:port/` suggestion from a discovered device's
    source IP, validated by RTSPUrlValidator before being returned.

    Returns None (never raises) when validation fails — e.g. a spoofed
    source IP claiming to be loopback/link-local/multicast/reserved. A
    discovery API caller MUST treat None as "do not offer this device for
    cadastro", not silently fall back to the unvalidated IP (ADR-0017: no
    silent fallback).

    Deliberately does not attempt to guess a manufacturer-specific RTSP path
    (`/cam/realmonitor?...`, `/Streaming/Channels/1`, ...) — WS-Discovery
    alone does not tell us the manufacturer or channel layout; the existing
    `manufacturer_profiles.py` (monolith, `probe_camera`) already owns that
    logic and is applied once the operator confirms the manufacturer during
    cadastro. This function only proves "this host is safe to point a RTSP
    client at", not "this is the exact stream path".
    """
    candidate = f"rtsp://{source_ip}:{port}/"
    try:
        return RTSPUrlValidator.validate(candidate)
    except RecorderError as exc:
        logger.warning(
            "onvif_discovery_rtsp_suggestion_rejected source_ip=%s err=%s", source_ip, exc
        )
        return None


# ── optional enrichment: GetDeviceInformation ──────────────────────────────


def fetch_device_information(
    xaddr: str,
    http_client: Any = None,
    timeout: float = _DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> DeviceInformation | None:
    """Best-effort ONVIF GetDeviceInformation call against a discovered XAddr.

    Returns None (never raises) on ANY failure: invalid/unsafe XAddr
    (RTSPUrlValidator rejects it — SSRF guard, same as
    onvif_recorder_client._post_soap), network error, or a response that
    doesn't parse. A camera that failed to answer this optional enrichment
    call must not remove the device from the discovery result — the caller
    still has source_ip/xaddrs/suggested_rtsp_url to work with.
    """
    try:
        validated_xaddr = RTSPUrlValidator.validate(xaddr)
    except RecorderError as exc:
        logger.warning("onvif_discovery_xaddr_rejected xaddr_host=%s err=%s", xaddr, exc)
        return None

    client = http_client if http_client is not None else httpx.Client(timeout=timeout)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
        "<s:Body>"
        '<tds:GetDeviceInformation xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>'
        "</s:Body>"
        "</s:Envelope>"
    )
    try:
        resp = client.post(
            validated_xaddr,
            content=body,
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            timeout=timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("onvif_discovery_device_info_failed err=%s", exc)
        return None

    return _parse_device_information(resp.text)


def _parse_device_information(xml_text: str) -> DeviceInformation | None:
    """Regex extraction of GetDeviceInformationResponse fields — same
    defensive-parsing discipline as `_parse_probe_matches`. Returns None if
    the response isn't recognizable as a GetDeviceInformationResponse at
    all (no leaf matched)."""

    def _leaf(tag: str) -> str | None:
        match = re.search(rf"<(?:\w+:)?{tag}>([^<]*)</(?:\w+:)?{tag}>", xml_text)
        return match.group(1).strip() if match else None

    manufacturer = _leaf("Manufacturer")
    model = _leaf("Model")
    firmware_version = _leaf("FirmwareVersion")
    serial_number = _leaf("SerialNumber")
    hardware_id = _leaf("HardwareId")

    if not any((manufacturer, model, firmware_version, serial_number, hardware_id)):
        return None

    return DeviceInformation(
        manufacturer=manufacturer,
        model=model,
        firmware_version=firmware_version,
        serial_number=serial_number,
        hardware_id=hardware_id,
    )
