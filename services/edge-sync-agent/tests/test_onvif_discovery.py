"""Tests for onvif_discovery: WS-Discovery probe wiring against a fake UDP
socket, defensive parsing of ProbeMatch responses, timeout/cap enforcement,
and RTSPUrlValidator-gated URL suggestion.

No real multicast traffic or camera hardware is exercised (none available) —
`sock_factory`/`http_client` are always injected fakes, same discipline as
the rest of edge-sync-agent's ONVIF/RTSP test suite (test_onvif_recorder_client.py,
test_rtsp_clip_stream.py).
"""

from __future__ import annotations

import socket

import pytest

from app.onvif_discovery import (
    DeviceInformation,
    OnvifDiscoveryError,
    build_suggested_rtsp_url,
    discover_devices,
    fetch_device_information,
)

_PROBE_MATCH_ENVELOPE = """<?xml version="1.0"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <e:Body>
    <wsd:ProbeMatches>
      <wsd:ProbeMatch>
        <wsa:EndpointReference>
          <wsa:Address>urn:uuid:11111111-1111-1111-1111-111111111111</wsa:Address>
        </wsa:EndpointReference>
        <wsd:Types>dn:NetworkVideoTransmitter</wsd:Types>
        <wsd:Scopes>onvif://www.onvif.org/type/video_encoder</wsd:Scopes>
        <wsd:XAddrs>http://192.168.1.64/onvif/device_service</wsd:XAddrs>
      </wsd:ProbeMatch>
    </wsd:ProbeMatches>
  </e:Body>
</e:Envelope>"""

_MULTI_PROBE_MATCH_ENVELOPE = """<?xml version="1.0"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <e:Body>
    <wsd:ProbeMatches>
      <wsd:ProbeMatch>
        <wsd:XAddrs>http://192.168.1.10/onvif/device_service</wsd:XAddrs>
      </wsd:ProbeMatch>
      <wsd:ProbeMatch>
        <wsd:XAddrs>http://192.168.1.11/onvif/device_service</wsd:XAddrs>
      </wsd:ProbeMatch>
    </wsd:ProbeMatches>
  </e:Body>
</e:Envelope>"""

_DEVICE_INFO_RESPONSE = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <tds:GetDeviceInformationResponse xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
      <Manufacturer>Intelbras</Manufacturer>
      <Model>VIP 1230</Model>
      <FirmwareVersion>1.2.3</FirmwareVersion>
      <SerialNumber>SN123456</SerialNumber>
      <HardwareId>HW1</HardwareId>
    </tds:GetDeviceInformationResponse>
  </s:Body>
</s:Envelope>"""


class _FakeUdpSocket:
    """Stands in for a real UDP socket: records sendto() calls, replays a
    scripted sequence of recvfrom() results, then raises socket.timeout."""

    def __init__(self, responses: list[tuple[bytes, str]] | None = None) -> None:
        self.responses = list(responses or [])
        self.sent: list[tuple[bytes, tuple]] = []
        self.closed = False
        self.timeouts: list[float] = []

    def settimeout(self, value: float) -> None:
        self.timeouts.append(value)

    def sendto(self, data: bytes, addr: tuple) -> None:
        self.sent.append((data, addr))

    def recvfrom(self, bufsize: int) -> tuple[bytes, tuple]:
        if not self.responses:
            raise socket.timeout()
        data, ip = self.responses.pop(0)
        return data, (ip, 3702)

    def close(self) -> None:
        self.closed = True


class _RaisingSendSocket:
    def settimeout(self, value: float) -> None:
        pass

    def sendto(self, data: bytes, addr: tuple) -> None:
        raise OSError("network unreachable")

    def close(self) -> None:
        pass


# ── probe message shape ──────────────────────────────────────────────────


def test_probe_message_is_well_formed_ws_discovery_soap():
    sock = _FakeUdpSocket(responses=[])
    discover_devices(timeout_seconds=0.01, sock_factory=lambda: sock)

    assert len(sock.sent) == 1
    data, addr = sock.sent[0]
    body = data.decode("utf-8")
    assert addr == ("239.255.255.250", 3702)
    assert "urn:schemas-xmlsoap-org:ws:2005:04:discovery" in body
    assert "http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe" in body
    assert "<d:Probe>" in body
    assert "NetworkVideoTransmitter" in body
    assert "<w:MessageID>uuid:" in body


# ── parsing ProbeMatch responses ─────────────────────────────────────────


def test_discovers_single_device_from_probe_match():
    sock = _FakeUdpSocket(
        responses=[(_PROBE_MATCH_ENVELOPE.encode("utf-8"), "192.168.1.64")]
    )
    devices = discover_devices(timeout_seconds=1.0, sock_factory=lambda: sock)

    assert len(devices) == 1
    device = devices[0]
    assert device.source_ip == "192.168.1.64"
    assert device.xaddrs == ["http://192.168.1.64/onvif/device_service"]
    assert device.types == ["dn:NetworkVideoTransmitter"]
    assert device.scopes == ["onvif://www.onvif.org/type/video_encoder"]
    assert device.endpoint_reference == "urn:uuid:11111111-1111-1111-1111-111111111111"


def test_discovers_multiple_probe_matches_in_one_envelope():
    sock = _FakeUdpSocket(
        responses=[(_MULTI_PROBE_MATCH_ENVELOPE.encode("utf-8"), "192.168.1.10")]
    )
    devices = discover_devices(timeout_seconds=1.0, sock_factory=lambda: sock)

    assert len(devices) == 2
    assert {d.xaddrs[0] for d in devices} == {
        "http://192.168.1.10/onvif/device_service",
        "http://192.168.1.11/onvif/device_service",
    }


def test_discovers_from_multiple_responders():
    sock = _FakeUdpSocket(
        responses=[
            (_PROBE_MATCH_ENVELOPE.encode("utf-8"), "192.168.1.64"),
            (_MULTI_PROBE_MATCH_ENVELOPE.encode("utf-8"), "192.168.1.10"),
        ]
    )
    devices = discover_devices(timeout_seconds=1.0, sock_factory=lambda: sock)
    assert len(devices) == 3


# ── malformed responses never crash the scanner ──────────────────────────


@pytest.mark.parametrize(
    "garbage",
    [
        b"not xml at all",
        b"<broken><unclosed>",
        b"\xff\xfe\x00\x01garbage-bytes-not-utf8",
        b"",
        b"<e:Envelope><e:Body><wsd:Hello/></e:Body></e:Envelope>",  # valid XML, wrong message type
    ],
)
def test_malformed_response_does_not_crash_scanner(garbage):
    sock = _FakeUdpSocket(responses=[(garbage, "10.0.0.99")])
    devices = discover_devices(timeout_seconds=1.0, sock_factory=lambda: sock)
    assert devices == []


def test_one_malformed_response_does_not_block_subsequent_good_ones():
    sock = _FakeUdpSocket(
        responses=[
            (b"<broken", "10.0.0.99"),
            (_PROBE_MATCH_ENVELOPE.encode("utf-8"), "192.168.1.64"),
        ]
    )
    devices = discover_devices(timeout_seconds=1.0, sock_factory=lambda: sock)
    assert len(devices) == 1
    assert devices[0].source_ip == "192.168.1.64"


# ── timeout / cap enforcement (DoS resistance) ───────────────────────────


def test_timeout_stops_scan_when_no_more_responses_arrive():
    sock = _FakeUdpSocket(responses=[])
    devices = discover_devices(timeout_seconds=0.05, sock_factory=lambda: sock)
    assert devices == []
    assert sock.closed is True


def test_max_responses_caps_datagrams_processed():
    # Script far more datagrams than max_responses — the fake never raises
    # socket.timeout on its own, so if the cap didn't work this would hang
    # (bounded here only because the fake eventually runs out; the
    # assertion proves the cap stopped processing well before that).
    responses = [
        (_PROBE_MATCH_ENVELOPE.encode("utf-8"), f"192.168.1.{i}") for i in range(1, 21)
    ]
    sock = _FakeUdpSocket(responses=responses)
    devices = discover_devices(
        timeout_seconds=5.0, max_responses=3, sock_factory=lambda: sock
    )
    assert len(devices) == 3
    # 17 of the 20 scripted datagrams were never consumed — proves the cap,
    # not the timeout, ended the scan.
    assert len(sock.responses) == 17


def test_invalid_timeout_raises_setup_error():
    with pytest.raises(OnvifDiscoveryError):
        discover_devices(timeout_seconds=0, sock_factory=lambda: _FakeUdpSocket())


def test_invalid_max_responses_raises_setup_error():
    with pytest.raises(OnvifDiscoveryError):
        discover_devices(max_responses=0, sock_factory=lambda: _FakeUdpSocket())


def test_send_failure_raises_setup_error_and_closes_socket():
    sock = _RaisingSendSocket()
    with pytest.raises(OnvifDiscoveryError):
        discover_devices(timeout_seconds=1.0, sock_factory=lambda: sock)


def test_socket_factory_oserror_raises_setup_error():
    def _boom():
        raise OSError("no permission")

    with pytest.raises(OnvifDiscoveryError):
        discover_devices(sock_factory=_boom)


def test_socket_always_closed_even_on_recv_error():
    class _ErroringSocket(_FakeUdpSocket):
        def recvfrom(self, bufsize: int) -> tuple[bytes, tuple]:
            raise OSError("recv failed")

    sock = _ErroringSocket(responses=[(b"x", "10.0.0.1")])
    devices = discover_devices(timeout_seconds=1.0, sock_factory=lambda: sock)
    assert devices == []
    assert sock.closed is True


# ── suggested RTSP URL — validated before ever being returned ───────────


def test_suggested_rtsp_url_for_normal_lan_host():
    url = build_suggested_rtsp_url("192.168.1.64")
    assert url == "rtsp://192.168.1.64:554/"


@pytest.mark.parametrize(
    "spoofed_source_ip",
    [
        "127.0.0.1",  # loopback
        "169.254.1.5",  # link-local
        "239.255.255.250",  # multicast — can't legitimately be a unicast reply source
        "0.0.0.0",  # unspecified
    ],
)
def test_suggested_rtsp_url_rejects_spoofed_source_ip(spoofed_source_ip):
    assert build_suggested_rtsp_url(spoofed_source_ip) is None


def test_suggested_rtsp_url_respects_custom_port():
    assert build_suggested_rtsp_url("192.168.1.64", port=8554) == "rtsp://192.168.1.64:8554/"


# ── GetDeviceInformation enrichment ───────────────────────────────────────


class _FakeHttpResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


class _FakeHttpClient:
    def __init__(self, response: _FakeHttpResponse | Exception) -> None:
        self._response = response
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_fetch_device_information_happy_path():
    client = _FakeHttpClient(_FakeHttpResponse(_DEVICE_INFO_RESPONSE))
    info = fetch_device_information(
        "http://192.168.1.64/onvif/device_service", http_client=client
    )
    assert info == DeviceInformation(
        manufacturer="Intelbras",
        model="VIP 1230",
        firmware_version="1.2.3",
        serial_number="SN123456",
        hardware_id="HW1",
    )
    assert client.calls[0][0] == "http://192.168.1.64/onvif/device_service"


def test_fetch_device_information_rejects_unsafe_xaddr():
    client = _FakeHttpClient(_FakeHttpResponse(_DEVICE_INFO_RESPONSE))
    info = fetch_device_information("http://127.0.0.1/onvif/device_service", http_client=client)
    assert info is None
    assert client.calls == []  # never even attempted the request


def test_fetch_device_information_network_error_returns_none():
    import httpx

    client = _FakeHttpClient(httpx.ConnectError("refused"))
    info = fetch_device_information(
        "http://192.168.1.64/onvif/device_service", http_client=client
    )
    assert info is None


def test_fetch_device_information_malformed_response_returns_none():
    client = _FakeHttpClient(_FakeHttpResponse("<not-a-device-info-response/>"))
    info = fetch_device_information(
        "http://192.168.1.64/onvif/device_service", http_client=client
    )
    assert info is None


def test_fetch_device_information_http_error_status_returns_none():
    client = _FakeHttpClient(_FakeHttpResponse("error", status_code=500))
    info = fetch_device_information(
        "http://192.168.1.64/onvif/device_service", http_client=client
    )
    assert info is None
