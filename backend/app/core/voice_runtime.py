from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib import request


def get_voice_runtime_status() -> dict[str, Any]:
    stt_provider = str(os.getenv("MYAI_STT_PROVIDER", "none")).strip().lower() or "none"
    tts_provider = str(os.getenv("MYAI_TTS_PROVIDER", "none")).strip().lower() or "none"
    return {
        "stt": {
            "provider": stt_provider,
            "configured": _is_stt_configured(stt_provider),
            "language_default": os.getenv("MYAI_STT_LANGUAGE", "en"),
            "model": os.getenv("MYAI_STT_MODEL", os.getenv("MYAI_STT_WHISPER_CPP_MODEL", "")),
            "supported_controls": ["language"],
        },
        "tts": {
            "provider": tts_provider,
            "configured": _is_tts_configured(tts_provider),
            "voice_default": os.getenv("MYAI_TTS_VOICE", "default"),
            "model": os.getenv("MYAI_TTS_MODEL", os.getenv("MYAI_TTS_PIPER_MODEL", "")),
            "format_default": os.getenv("MYAI_TTS_FORMAT", "wav"),
            "supported_controls": ["voice", "speed", "pitch", "gain_db", "tone", "cadence", "stability", "similarity_boost", "style"],
        },
    }


def _is_stt_configured(provider: str) -> bool:
    if provider == "whisper_cpp":
        return bool(os.getenv("MYAI_STT_WHISPER_CPP_BIN", "").strip()) and bool(
            os.getenv("MYAI_STT_WHISPER_CPP_MODEL", "").strip()
        )
    if provider == "command":
        return bool(os.getenv("MYAI_STT_COMMAND_TEMPLATE", "").strip())
    return False


def _is_tts_configured(provider: str) -> bool:
    if provider == "piper":
        return bool(os.getenv("MYAI_TTS_PIPER_BIN", "").strip()) and bool(
            os.getenv("MYAI_TTS_PIPER_MODEL", "").strip()
        )
    if provider == "elevenlabs":
        return bool(os.getenv("MYAI_TTS_ELEVENLABS_API_KEY", "").strip()) and bool(
            os.getenv("MYAI_TTS_ELEVENLABS_VOICE_ID", "").strip()
        )
    if provider == "command":
        return bool(os.getenv("MYAI_TTS_COMMAND_TEMPLATE", "").strip())
    return False


def transcribe_audio(*, audio_bytes: bytes, filename: str, language: str | None = None) -> dict[str, Any]:
    provider = str(os.getenv("MYAI_STT_PROVIDER", "none")).strip().lower() or "none"
    if provider == "whisper_cpp":
        return _transcribe_whisper_cpp(audio_bytes=audio_bytes, filename=filename, language=language)
    if provider == "command":
        return _transcribe_command(audio_bytes=audio_bytes, filename=filename, language=language)
    raise RuntimeError("STT provider is not configured.")


def synthesize_speech(
    *,
    text: str,
    voice: str | None = None,
    output_format: str = "wav",
    speed: float | None = None,
    pitch: float | None = None,
    gain_db: float | None = None,
    tone: str | None = None,
    cadence: str | None = None,
    stability: float | None = None,
    similarity_boost: float | None = None,
    style: float | None = None,
) -> tuple[bytes, str, str]:
    provider = str(os.getenv("MYAI_TTS_PROVIDER", "none")).strip().lower() or "none"
    if provider == "piper":
        return _synthesize_piper(
            text=text,
            voice=voice,
            output_format=output_format,
            speed=speed,
            pitch=pitch,
            gain_db=gain_db,
        )
    if provider == "elevenlabs":
        return _synthesize_elevenlabs(
            text=text,
            voice=voice,
            output_format=output_format,
            speed=speed,
            pitch=pitch,
            gain_db=gain_db,
            tone=tone,
            cadence=cadence,
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
        )
    if provider == "command":
        return _synthesize_command(
            text=text,
            voice=voice,
            output_format=output_format,
            speed=speed,
            pitch=pitch,
            gain_db=gain_db,
        )
    raise RuntimeError("TTS provider is not configured.")


def _transcribe_whisper_cpp(*, audio_bytes: bytes, filename: str, language: str | None) -> dict[str, Any]:
    bin_path = os.getenv("MYAI_STT_WHISPER_CPP_BIN", "").strip()
    model_path = os.getenv("MYAI_STT_WHISPER_CPP_MODEL", "").strip()
    if not bin_path or not model_path:
        raise RuntimeError("whisper.cpp STT is not configured.")
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / (filename or "input.wav")
        output_base = Path(tmpdir) / "transcript"
        input_path.write_bytes(audio_bytes)
        cmd = [bin_path, "-m", model_path, "-f", str(input_path), "-oj", "-of", str(output_base)]
        if language or os.getenv("MYAI_STT_LANGUAGE", "").strip():
            cmd.extend(["-l", language or os.getenv("MYAI_STT_LANGUAGE", "en")])
        completed = subprocess.run(cmd, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "whisper.cpp transcription failed")
        json_path = Path(f"{output_base}.json")
        if not json_path.exists():
            raise RuntimeError("whisper.cpp did not produce a JSON transcript.")
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        text = str(payload.get("text", "")).strip()
        return {
            "text": text,
            "provider": "whisper_cpp",
            "language": language or os.getenv("MYAI_STT_LANGUAGE", "en"),
            "segments": payload.get("segments", []),
            "raw": payload,
        }


def _transcribe_command(*, audio_bytes: bytes, filename: str, language: str | None) -> dict[str, Any]:
    template = os.getenv("MYAI_STT_COMMAND_TEMPLATE", "").strip()
    if not template:
        raise RuntimeError("STT command template is not configured.")
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / (filename or "input.wav")
        output_path = Path(tmpdir) / "transcript.txt"
        input_path.write_bytes(audio_bytes)
        cmd = template.format(input=str(input_path), output=str(output_path), language=(language or "en"))
        completed = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "STT command failed")
        if not output_path.exists():
            raise RuntimeError("STT command did not produce output.")
        return {
            "text": output_path.read_text(encoding="utf-8").strip(),
            "provider": "command",
            "language": language or "en",
            "segments": [],
            "raw": {},
        }


def _synthesize_piper(
    *, text: str, voice: str | None, output_format: str, speed: float | None, pitch: float | None, gain_db: float | None
) -> tuple[bytes, str, str]:
    bin_path = os.getenv("MYAI_TTS_PIPER_BIN", "").strip()
    model_path = os.getenv("MYAI_TTS_PIPER_MODEL", "").strip()
    if not bin_path or not model_path:
        raise RuntimeError("Piper TTS is not configured.")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_name = f"speech.{output_format or 'wav'}"
        output_path = Path(tmpdir) / out_name
        cmd = [bin_path, "--model", model_path, "--output_file", str(output_path)]
        selected_voice = voice or os.getenv("MYAI_TTS_VOICE", "").strip()
        if selected_voice:
            cmd.extend(["--speaker", selected_voice])
        if speed and speed > 0:
            cmd.extend(["--length_scale", str(max(0.1, 1.0 / speed))])
        if pitch and pitch > 0:
            cmd.extend(["--noise_scale_w", str(pitch)])
        completed = subprocess.run(cmd, input=text, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Piper synthesis failed")
        if not output_path.exists():
            raise RuntimeError("Piper did not produce an output file.")
        mime = "audio/wav" if output_format == "wav" else "application/octet-stream"
        return output_path.read_bytes(), mime, out_name


def _synthesize_command(
    *, text: str, voice: str | None, output_format: str, speed: float | None, pitch: float | None, gain_db: float | None
) -> tuple[bytes, str, str]:
    template = os.getenv("MYAI_TTS_COMMAND_TEMPLATE", "").strip()
    if not template:
        raise RuntimeError("TTS command template is not configured.")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_name = f"speech.{output_format or 'wav'}"
        output_path = Path(tmpdir) / out_name
        cmd = template.format(
            output=str(output_path),
            voice=(voice or "default"),
            format=(output_format or "wav"),
            speed=(speed if speed is not None else 1.0),
            pitch=(pitch if pitch is not None else 1.0),
            gain_db=(gain_db if gain_db is not None else 0.0),
        )
        completed = subprocess.run(cmd, input=text, shell=True, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "TTS command failed")
        if not output_path.exists():
            raise RuntimeError("TTS command did not produce an output file.")
        mime = "audio/wav" if output_format == "wav" else "application/octet-stream"
        return output_path.read_bytes(), mime, out_name


def _synthesize_elevenlabs(
    *,
    text: str,
    voice: str | None,
    output_format: str,
    speed: float | None,
    pitch: float | None,
    gain_db: float | None,
    tone: str | None,
    cadence: str | None,
    stability: float | None,
    similarity_boost: float | None,
    style: float | None,
) -> tuple[bytes, str, str]:
    api_key = os.getenv("MYAI_TTS_ELEVENLABS_API_KEY", "").strip()
    voice_id = (voice or os.getenv("MYAI_TTS_ELEVENLABS_VOICE_ID", "").strip()).strip()
    model_id = os.getenv("MYAI_TTS_ELEVENLABS_MODEL", "eleven_turbo_v2_5").strip()
    if not api_key or not voice_id:
        raise RuntimeError("ElevenLabs TTS is not configured.")
    base = os.getenv("MYAI_TTS_ELEVENLABS_BASE_URL", "https://api.elevenlabs.io").rstrip("/")
    fmt = output_format or "mp3"
    url = f"{base}/v1/text-to-speech/{voice_id}?output_format={fmt}"
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability if stability is not None else float(os.getenv("MYAI_TTS_ELEVENLABS_STABILITY", "0.5") or 0.5),
            "similarity_boost": similarity_boost if similarity_boost is not None else float(os.getenv("MYAI_TTS_ELEVENLABS_SIMILARITY_BOOST", "0.75") or 0.75),
            "style": style if style is not None else float(os.getenv("MYAI_TTS_ELEVENLABS_STYLE", "0.0") or 0.0),
            "use_speaker_boost": True,
        },
    }
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg" if fmt == "mp3" else "audio/wav",
        },
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            audio = resp.read()
    except Exception as error:
        raise RuntimeError(f"ElevenLabs TTS request failed: {error}") from error
    mime = "audio/mpeg" if fmt == "mp3" else "audio/wav"
    filename = f"speech.{fmt}"
    return audio, mime, filename
