"""OnvifRecorderClient — real ONVIF Profile G RecorderClient (task-091).

C-04 investigation (full version in the task-091 PR description): a mature
ONVIF Profile G client already exists at
services/api/app/infrastructure/nvr/onvif_client.py, built for a different
consumer (WS-B1 cloud-side training-frame replay, ADR-0034) — same SOAP
envelopes (GetSystemDateAndTime / FindRecordings+GetRecordingSearchResults /
GetReplayUri), same "never validated against real hardware" caveat. This
module ports that logic rather than importing it, because services/api and
services/edge-sync-agent are independently deployed processes (separate
requirements.txt, separate containers) with no existing precedent in this
repo for sharing *protocol/I/O logic* across services/* — the one shared
package that does exist (shared/python/recognition_shared) holds only
pydantic DTOs with zero networking code, which is a different kind of
sharing (data contract, not implementation). Keeping two copies in sync by
hand is the accepted trade-off; see the PR for the full reasoning.

Adapted for the RecorderClient Protocol (task-090's edge-side contract,
recorder_client.py) rather than the monolith's NvrClient:
  - "channel" (ONVIF's addressing unit) is resolved from `camera_id` via an
    explicit channel_map — no guessing (ADR-0017 discipline: unmapped
    camera_id is a hard RecorderError, never a silent default channel).
  - RecordingSegment (start marker + assumed end = requested window end,
    same simplification as the monolith original) is surfaced as one
    RecorderEvent per marker found, event_type="recording".
  - stream_clip resolves a playback RTSP URL via GetReplayUri, then pulls
    bytes through rtsp_clip_stream.stream_rtsp_clip (ffmpeg remux,
    no disk).
  - capture_frame (Onda 2, task-092) resolves a LIVE stream URL via Media
    GetStreamUri — a different ONVIF service than GetReplayUri, addressed
    by the same channel_map — then grabs one frame through
    rtsp_frame_capture.capture_still_frame (ffmpeg -frames:v 1, no disk).

AUTENTICAÇÃO (achado ao validar a ADR-0052 em hardware real — Intelbras iNVD
3032): `_post_soap` nunca implementou nenhuma autenticação. C-04 investigado
antes de escrever isto: nenhum código WS-Security/UsernameToken/PasswordDigest
existia em nenhum lugar do monorepo (`rg -in 'UsernameToken|PasswordDigest|
wsse'` vazio), nem no Jetson (`~/onvif-validation/`, scaffolding da sessão de
2026-07-16 que validou `onvif_discovery.py` contra rede real) — aquela sessão
exercitou só WS-Discovery (UDP multicast, não autenticado por especificação;
ver `onvif_discovery.py`), nunca uma chamada ONVIF SOAP autenticada contra o
gravador (ficou "inconclusiva" — câmera com ONVIF desligado de fábrica,
`docs/edge/STATUS_2026-07-16_jetson_handson.md`). Greenfield: implementado
aqui com stdlib (`hashlib`/`base64`/`secrets`), seguindo o padrão ONVIF/WS-
Security UsernameToken Profile 1.0 (PasswordDigest): `Digest = Base64(SHA1(
nonce + created + password))`, nonce aleatório novo a cada request (defesa
contra replay) — ver `_password_digest`/`_ws_security_header` abaixo.

PENDÊNCIA (same as the monolith source): no call in this module has been
validated against a real ONVIF device — no hardware available in this
environment. Coverage is via mocked SOAP responses, envelopes built from the
public ONVIF Core/Profile G specification. Validate against a real NVR
before go-live (task-095/task-097).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import secrets
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from xml.sax.saxutils import escape as _xml_escape

import httpx

from .recorder_client import RecorderError, RecorderEvent, RecorderHealth
from .rtsp_clip_stream import stream_rtsp_clip
from .rtsp_frame_capture import capture_still_frame
from .rtsp_validator import RTSPUrlValidator

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 15.0
_SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"

_WSSE_SECEXT_NS = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
)
_WSU_UTILITY_NS = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
)
_WSSE_PASSWORD_DIGEST_TYPE = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0"
    "#PasswordDigest"
)
_WSSE_NONCE_ENCODING_TYPE = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0"
    "#Base64Binary"
)
_NONCE_BYTES = 16


def _fmt(dt: datetime) -> str:
    """ISO 8601 UTC timestamp format required by ONVIF (xs:dateTime)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _password_digest(nonce: bytes, created: str, password: str) -> str:
    """WS-Security UsernameToken Profile 1.0 PasswordDigest — the ONVIF-mandated
    auth scheme (ONVIF Core Spec, Security section): every SOAP request over
    plain HTTP carries a `wsse:UsernameToken` whose password is never sent in
    the clear, only this digest.

    Digest = Base64(SHA1(nonce_octets + created_utf8 + password_utf8))

    `nonce` is the RAW octets (not base64) — the base64 form only appears in
    the XML `<wsse:Nonce>` element. Cross-checked against an independent
    openssl computation (sha1+base64 of the same concatenation) during
    development — see the known-vector unit test in
    tests/test_onvif_recorder_client.py.
    """
    sha1 = hashlib.sha1()
    sha1.update(nonce)
    sha1.update(created.encode("utf-8"))
    sha1.update(password.encode("utf-8"))
    return base64.b64encode(sha1.digest()).decode("ascii")


def _ws_security_header(username: str, password: str) -> str:
    """Builds the `<s:Header>` WS-Security UsernameToken block (PasswordDigest).

    A FRESH nonce (`secrets.token_bytes` — CSPRNG, not `random`) and a fresh
    `Created` timestamp are generated on every call: reusing a nonce is
    exactly what PasswordDigest's replay defense exists to catch, and some
    NVR firmwares (Profile G search among them) reject a repeated nonce
    outright. Never logged — see `_post_soap` (this header carries the
    digest, never the password itself, so it's low-sensitivity, but the
    convention in this module is to never log SOAP bodies at INFO/WARNING).
    """
    nonce = secrets.token_bytes(_NONCE_BYTES)
    created = _fmt(datetime.now(timezone.utc))
    digest = _password_digest(nonce, created, password)
    nonce_b64 = base64.b64encode(nonce).decode("ascii")
    return (
        "<s:Header>"
        f'<wsse:Security xmlns:wsse="{_WSSE_SECEXT_NS}" s:mustUnderstand="1">'
        f'<wsse:UsernameToken xmlns:wsu="{_WSU_UTILITY_NS}">'
        f"<wsse:Username>{_xml_escape(username)}</wsse:Username>"
        f'<wsse:Password Type="{_WSSE_PASSWORD_DIGEST_TYPE}">{digest}</wsse:Password>'
        f'<wsse:Nonce EncodingType="{_WSSE_NONCE_ENCODING_TYPE}">{nonce_b64}</wsse:Nonce>'
        f"<wsu:Created>{created}</wsu:Created>"
        "</wsse:UsernameToken>"
        "</wsse:Security>"
        "</s:Header>"
    )


def _soap_envelope(body: str, security_header: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<s:Envelope xmlns:s="{_SOAP_ENV_NS}">'
        f"{security_header}"
        f"<s:Body>{body}</s:Body>"
        "</s:Envelope>"
    )


class OnvifRecorderClient:
    """RecorderClient backend that talks ONVIF Profile G to the site's NVR/DVR."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        channel_map: dict[str, int],
        http_client: Any = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not username or not password:
            # Defesa em profundidade: recorder_factory.py já falha-rápido antes
            # de chegar aqui quando RECORDER_PROTOCOL=onvif está ligado sem
            # credencial (ADR-0017 — sem fallback silencioso). Este client
            # também não aceita ser construído sem credencial diretamente —
            # ONVIF Profile G não tem modo anônimo aqui, e um digest calculado
            # com senha vazia seria uma auth "que parece funcionar" mas não
            # autentica nada.
            raise RecorderError(
                "OnvifRecorderClient requer username e password não vazios "
                "(WS-Security UsernameToken/PasswordDigest é obrigatório em "
                "todo request ONVIF deste client) — configure RECORDER_USERNAME "
                "e RECORDER_PASSWORD."
            )
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._channel_map = dict(channel_map)
        self._timeout = timeout
        self._http = http_client if http_client is not None else httpx.Client(timeout=timeout)
        self._device_url = f"http://{host}:{port}/onvif/device_service"
        self._search_url = f"http://{host}:{port}/onvif/search_service"
        self._replay_url = f"http://{host}:{port}/onvif/replay_service"
        self._media_url = f"http://{host}:{port}/onvif/media_service"

    # ── camera_id → ONVIF channel ────────────────────────────────────────────

    def _channel_for(self, camera_id: str) -> int:
        if camera_id in self._channel_map:
            return self._channel_map[camera_id]
        raise RecorderError(
            f"camera_id={camera_id!r} sem canal ONVIF mapeado em RECORDER_CHANNEL_MAP "
            "— sem fallback silencioso (ADR-0017)."
        )

    # ── SOAP transport ───────────────────────────────────────────────────────

    def _post_soap(self, url: str, body: str) -> str:
        RTSPUrlValidator.validate(url)
        security_header = _ws_security_header(self._username, self._password)
        try:
            resp = self._http.post(
                url,
                content=_soap_envelope(body, security_header),
                headers={"Content-Type": "application/soap+xml; charset=utf-8"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RecorderError(f"onvif_soap_request_failed host={self._host} err={exc}") from exc
        return resp.text

    # ── RecorderClient protocol ──────────────────────────────────────────────

    def health(self) -> RecorderHealth:
        try:
            body = '<tds:GetSystemDateAndTime xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>'
            self._post_soap(self._device_url, body)
            return RecorderHealth(reachable=True, detail="onvif ok")
        except RecorderError as exc:
            logger.warning("onvif_health_check_failed host=%s err=%s", self._host, exc)
            return RecorderHealth(reachable=False, detail=str(exc))

    def list_events(
        self, camera_id: str, start: datetime, end: datetime
    ) -> list[RecorderEvent]:
        channel = self._channel_for(camera_id)

        search_token = f"recognition-{uuid4().hex[:12]}"
        find_body = (
            '<tse:FindRecordings xmlns:tse="http://www.onvif.org/ver10/search/wsdl">'
            "<Scope>"
            "<IncludedSources/>"
            f"<IncludedRecordings><Token>{channel}</Token></IncludedRecordings>"
            "</Scope>"
            "<KeepAliveTime>PT30S</KeepAliveTime>"
            "</tse:FindRecordings>"
        )
        find_resp = self._post_soap(self._search_url, find_body)
        search_token = self._extract_search_token(find_resp) or search_token

        results_body = (
            '<tse:GetRecordingSearchResults xmlns:tse="http://www.onvif.org/ver10/search/wsdl">'
            f"<SearchToken>{search_token}</SearchToken>"
            "<MinResults>1</MinResults><MaxResults>64</MaxResults>"
            "</tse:GetRecordingSearchResults>"
        )
        results_resp = self._post_soap(self._search_url, results_body)
        return self._parse_recording_results(camera_id, results_resp, start, end)

    def stream_clip(
        self, camera_id: str, start: datetime, end: datetime
    ) -> Iterator[bytes]:
        channel = self._channel_for(camera_id)
        playback_url = self._get_replay_uri(channel)
        duration_seconds = (end - start).total_seconds()
        yield from stream_rtsp_clip(playback_url, duration_seconds)

    def capture_frame(self, camera_id: str) -> bytes:
        channel = self._channel_for(camera_id)
        live_url = self._get_stream_uri(channel)
        return capture_still_frame(live_url)

    # ── parsing / playback URL resolution ────────────────────────────────────

    @staticmethod
    def _extract_search_token(xml_text: str) -> "str | None":
        match = re.search(r"<(?:\w+:)?SearchToken>([^<]+)</(?:\w+:)?SearchToken>", xml_text)
        return match.group(1) if match else None

    def _parse_recording_results(
        self,
        camera_id: str,
        xml_text: str,
        requested_start: datetime,
        requested_end: datetime,
    ) -> list[RecorderEvent]:
        """Extracts (Time) markers from each RecordingInformation entry.

        Parsed via regex (not ElementTree): ONVIF responses vary namespace
        prefixes by vendor (tse:/tt:/none) — matching leaf elements by regex
        is more robust here than an exact-namespace match (same rationale as
        the monolith original).

        Same known simplification as the monolith source: each <Time> marker
        becomes one event whose ended_at is the *requested* window end, not a
        real segment end — ONVIF Profile G's FindRecordings/
        GetRecordingSearchResults doesn't expose a clean segment-end marker
        in this minimal (non-WSDL) implementation. Acceptable for locating
        "is there a recording in this window", not for a byte-exact segment
        boundary — the actual boundary is whatever GetReplayUri's playback
        stream returns.
        """
        events: list[RecorderEvent] = []
        for m in re.finditer(
            r"<(?:\w+:)?RecordingInformation>.*?<(?:\w+:)?Time>([^<]+)</(?:\w+:)?Time>",
            xml_text,
            re.DOTALL,
        ):
            try:
                # "Z" suffix is always UTC (xs:dateTime per ONVIF spec) — tag it
                # tz-aware so this compares safely against tz-aware start/end
                # (evidence_api.py's _parse_window always produces tz-aware
                # datetimes via fromisoformat). A bare strptime (as in the
                # monolith source this was ported from) yields a naive
                # datetime and raises TypeError against an aware operand —
                # fixed here rather than reproduced.
                ts = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
            if requested_start <= ts <= requested_end:
                events.append(
                    RecorderEvent(
                        event_id=f"onvif:{camera_id}:{ts.isoformat()}",
                        camera_id=camera_id,
                        started_at=ts,
                        ended_at=requested_end,
                        event_type="recording",
                    )
                )
        return events

    def _get_replay_uri(self, channel: int) -> str:
        body = (
            '<trp:GetReplayUri xmlns:trp="http://www.onvif.org/ver10/replay/wsdl">'
            "<StreamSetup>"
            '<Stream xmlns="http://www.onvif.org/ver10/schema">RTP-Unicast</Stream>'
            '<Transport xmlns="http://www.onvif.org/ver10/schema">'
            "<Protocol>RTSP</Protocol></Transport>"
            "</StreamSetup>"
            f"<RecordingToken>{channel}</RecordingToken>"
            "</trp:GetReplayUri>"
        )
        resp = self._post_soap(self._replay_url, body)
        match = re.search(r"<(?:\w+:)?Uri>([^<]+)</(?:\w+:)?Uri>", resp)
        if not match:
            raise RecorderError("GetReplayUri não retornou Uri")
        return RTSPUrlValidator.validate(match.group(1))

    def _get_stream_uri(self, channel: int) -> str:
        """Resolves the LIVE (not replay) stream URL via ONVIF Media GetStreamUri.

        Reuses the same channel_map as list_events/stream_clip, i.e. assumes
        the NVR's Media ProfileToken scheme lines up with the Profile G
        RecordingToken/channel numbering (common for NVRs that expose one
        numbered profile per input channel, not guaranteed by spec). Same
        "not hardware-validated" caveat as the rest of this module — RVB's
        actual gravador speaks the RTSP fallback dialect
        (RtspTimestampRecorderClient), not ONVIF, so this path is untested
        against real hardware (recorder_factory.py).
        """
        body = (
            '<trt:GetStreamUri xmlns:trt="http://www.onvif.org/ver10/media/wsdl">'
            "<StreamSetup>"
            '<Stream xmlns="http://www.onvif.org/ver10/schema">RTP-Unicast</Stream>'
            '<Transport xmlns="http://www.onvif.org/ver10/schema">'
            "<Protocol>RTSP</Protocol></Transport>"
            "</StreamSetup>"
            f"<ProfileToken>{channel}</ProfileToken>"
            "</trt:GetStreamUri>"
        )
        resp = self._post_soap(self._media_url, body)
        match = re.search(r"<(?:\w+:)?Uri>([^<]+)</(?:\w+:)?Uri>", resp)
        if not match:
            raise RecorderError("GetStreamUri não retornou Uri")
        return RTSPUrlValidator.validate(match.group(1))
