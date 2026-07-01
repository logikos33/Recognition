"""
Recognition — Perfis de fabricante para geração de URLs RTSP (task-046).

Cada perfil define template de URL de main/substream e porta padrão.
Subtype 0 = main stream (alta qualidade); subtype 1 = sub stream (detecção).
"""

PROFILES: dict[str, dict] = {
    "intelbras": {
        "name": "Intelbras",
        "rtsp_main": "rtsp://{user}:{password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype=0",
        "rtsp_sub": "rtsp://{user}:{password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype=1",
        "default_port": 554,
    },
    "hikvision": {
        "name": "Hikvision",
        "rtsp_main": "rtsp://{user}:{password}@{host}:{port}/Streaming/Channels/{channel}01",
        "rtsp_sub": "rtsp://{user}:{password}@{host}:{port}/Streaming/Channels/{channel}02",
        "default_port": 554,
    },
    "dahua": {
        "name": "Dahua",
        "rtsp_main": "rtsp://{user}:{password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype=0",
        "rtsp_sub": "rtsp://{user}:{password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype=1",
        "default_port": 554,
    },
    "generic": {
        "name": "Genérico / ONVIF",
        "rtsp_main": "rtsp://{user}:{password}@{host}:{port}/stream1",
        "rtsp_sub": "rtsp://{user}:{password}@{host}:{port}/stream2",
        "default_port": 554,
    },
}
