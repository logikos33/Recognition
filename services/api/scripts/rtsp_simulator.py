#!/usr/bin/env python3
"""
Recognition — RTSP Simulator
Streams a synthetic test video as RTSP using MediaMTX + FFmpeg.
No real camera required. Uses FFmpeg testsrc2 filter for video generation.

Usage:
  python rtsp_simulator.py start    # Start RTSP server + stream
  python rtsp_simulator.py stop     # Stop all processes
  python rtsp_simulator.py status   # Show status
  python rtsp_simulator.py url      # Print stream URL

Stream URL: rtsp://localhost:8554/camera1
"""
import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BIN_DIR = SCRIPT_DIR / "bin"
VIDEO_DIR = SCRIPT_DIR / "test_videos"
MEDIAMTX_BIN = BIN_DIR / "mediamtx"
MEDIAMTX_CFG = BIN_DIR / "mediamtx.yml"
MEDIAMTX_PID = BIN_DIR / "mediamtx.pid"
FFMPEG_PID = BIN_DIR / "ffmpeg.pid"
SAMPLE_VIDEO = VIDEO_DIR / "sample.mp4"

RTSP_PORT = 8554
CAMERA_PATH = "camera1"
STREAM_URL = f"rtsp://localhost:{RTSP_PORT}/{CAMERA_PATH}"

# MediaMTX release: https://github.com/bluenviron/mediamtx/releases
MEDIAMTX_VERSION = "1.9.1"

_ARCH_MAP = {
    ("Darwin", "arm64"): f"mediamtx_v{MEDIAMTX_VERSION}_darwin_arm64.tar.gz",
    ("Darwin", "x86_64"): f"mediamtx_v{MEDIAMTX_VERSION}_darwin_amd64.tar.gz",
    ("Linux", "x86_64"): f"mediamtx_v{MEDIAMTX_VERSION}_linux_amd64.tar.gz",
    ("Linux", "aarch64"): f"mediamtx_v{MEDIAMTX_VERSION}_linux_arm64.tar.gz",
}

_MEDIAMTX_CFG_CONTENT = f"""\
# MediaMTX minimal config for Recognition RTSP simulator
logLevel: warn
rtspAddress: :{RTSP_PORT}
webrtc: false
hls: false
srt: false
paths:
  all:
    source: publisher
"""


def _platform_key():
    return (platform.system(), platform.machine())


def _download_mediamtx():
    key = _platform_key()
    filename = _ARCH_MAP.get(key)
    if not filename:
        print(f"❌ Plataforma não suportada: {key}", file=sys.stderr)
        sys.exit(1)

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    url = (
        f"https://github.com/bluenviron/mediamtx/releases/download/"
        f"v{MEDIAMTX_VERSION}/{filename}"
    )
    archive = BIN_DIR / filename

    print(f"  Baixando MediaMTX {MEDIAMTX_VERSION} ({key[1]})...")
    urllib.request.urlretrieve(url, archive)

    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(BIN_DIR)
    archive.unlink(missing_ok=True)
    MEDIAMTX_BIN.chmod(0o755)
    print(f"  ✅ MediaMTX instalado em {MEDIAMTX_BIN}")


def _ensure_mediamtx():
    if not MEDIAMTX_BIN.exists():
        print("MediaMTX não encontrado. Baixando...")
        _download_mediamtx()

    MEDIAMTX_CFG.write_text(_MEDIAMTX_CFG_CONTENT)


def _generate_test_video():
    """Generate synthetic 60s test video with FFmpeg testsrc2 overlay."""
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    if SAMPLE_VIDEO.exists():
        return

    print("  Gerando vídeo de teste sintético (60s)...")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "testsrc2=size=640x360:rate=25",
        "-f", "lavfi",
        "-i", "sine=frequency=1000",
        "-t", "60",
        "-vf", (
            "drawtext=text='Recognition Test':fontsize=24:fontcolor=white"
            ":box=1:boxcolor=black@0.5:x=(w-tw)/2:y=10,"
            "drawtext=text='%{pts\\:hms}':fontsize=18:fontcolor=yellow"
            ":box=1:boxcolor=black@0.5:x=10:y=40"
        ),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        str(SAMPLE_VIDEO),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback: simpler video without text overlay (no libfreetype)
        cmd_simple = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "testsrc2=size=640x360:rate=25",
            "-t", "60",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-an",
            str(SAMPLE_VIDEO),
        ]
        subprocess.run(cmd_simple, check=True, capture_output=True)
    print(f"  ✅ Vídeo de teste: {SAMPLE_VIDEO}")


def _pid_alive(pid_file: Path) -> int | None:
    """Return PID if process alive, else None."""
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        pid_file.unlink(missing_ok=True)
        return None


def _kill_pid(pid_file: Path, name: str):
    pid = _pid_alive(pid_file)
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass
        pid_file.unlink(missing_ok=True)
        print(f"  ⏹  {name} parado (PID {pid})")
    else:
        print(f"  ℹ  {name} não estava rodando")


def cmd_start():
    print("🚀 Iniciando RTSP Simulator...")
    _ensure_mediamtx()
    _generate_test_video()

    # Start MediaMTX
    if _pid_alive(MEDIAMTX_PID):
        print("  ℹ  MediaMTX já em execução")
    else:
        proc = subprocess.Popen(
            [str(MEDIAMTX_BIN), str(MEDIAMTX_CFG)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        MEDIAMTX_PID.write_text(str(proc.pid))
        time.sleep(1)
        if _pid_alive(MEDIAMTX_PID):
            print(f"  ✅ MediaMTX iniciado (PID {proc.pid}, porta {RTSP_PORT})")
        else:
            print("  ❌ MediaMTX falhou ao iniciar", file=sys.stderr)
            sys.exit(1)

    # Start FFmpeg stream loop
    if _pid_alive(FFMPEG_PID):
        print("  ℹ  Stream FFmpeg já em execução")
    else:
        ffmpeg_cmd = [
            "ffmpeg",
            "-re",
            "-stream_loop", "-1",
            "-i", str(SAMPLE_VIDEO),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-c:a", "aac",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            STREAM_URL,
        ]
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        FFMPEG_PID.write_text(str(proc.pid))
        time.sleep(2)
        if _pid_alive(FFMPEG_PID):
            print(f"  ✅ Stream iniciado (PID {proc.pid})")
        else:
            print("  ❌ FFmpeg stream falhou", file=sys.stderr)
            sys.exit(1)

    print(f"\n✅ RTSP Simulator ONLINE")
    print(f"   Stream: {STREAM_URL}")
    print(f"   Vídeo:  {SAMPLE_VIDEO}")
    print("\n  Para testar:  ffplay rtsp://localhost:8554/camera1")
    print("  Para parar:   python rtsp_simulator.py stop")


def cmd_stop():
    print("⏹  Parando RTSP Simulator...")
    _kill_pid(FFMPEG_PID, "FFmpeg stream")
    _kill_pid(MEDIAMTX_PID, "MediaMTX")
    print("✅ Parado.")


def cmd_status():
    mtx = _pid_alive(MEDIAMTX_PID)
    ffm = _pid_alive(FFMPEG_PID)
    print("📊 Status RTSP Simulator")
    print(f"  MediaMTX:  {'🟢 rodando (PID ' + str(mtx) + ')' if mtx else '🔴 parado'}")
    print(f"  FFmpeg:    {'🟢 rodando (PID ' + str(ffm) + ')' if ffm else '🔴 parado'}")
    if mtx and ffm:
        print(f"\n  Stream URL: {STREAM_URL}")


def cmd_url():
    print(STREAM_URL)


def main():
    parser = argparse.ArgumentParser(
        description="Recognition RTSP Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Stream URL: {STREAM_URL}",
    )
    parser.add_argument(
        "command",
        choices=["start", "stop", "status", "url"],
        help="Comando",
    )
    args = parser.parse_args()

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "url": cmd_url,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
