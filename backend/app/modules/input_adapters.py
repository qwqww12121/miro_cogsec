"""Adapters for text/file/audio inputs entering the CogSec mainline."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from .session.file_ingestor import ingest_file
from ..config import Config
from ..utils.file_parser import FileParser


class InputAdapterError(ValueError):
    """A client-provided input cannot be adapted safely."""


class SpeechTranscriptionUnavailable(RuntimeError):
    """No configured speech provider is available for the uploaded audio."""


@dataclass
class AdaptedInput:
    kind: str
    filename: str
    text: str = ""
    content_type: str = ""
    byte_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "filename": self.filename,
            "content_type": self.content_type,
            "byte_size": self.byte_size,
            "text_chars": len(self.text),
            "metadata": dict(self.metadata),
        }


TEXT_EXTENSIONS = frozenset({"txt", "md", "markdown", "pdf", "json", "csv"})
AUDIO_EXTENSIONS = frozenset({"webm", "wav", "mp3", "m4a", "mp4", "mpeg", "mpga", "ogg", "oga"})
MAX_TEXT_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024


def _extension(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def adapt_text_file(filename: str, content: bytes, content_type: str = "") -> AdaptedInput:
    """Reuse the project's existing FileParser/session ingestor for documents."""
    if not filename:
        raise InputAdapterError("文件名不能为空")
    if len(content) > MAX_TEXT_UPLOAD_BYTES:
        raise InputAdapterError("文件不能超过 10 MB")

    ext = _extension(filename)
    if ext not in TEXT_EXTENSIONS:
        raise InputAdapterError(
            f"不支持的文件格式: .{ext or 'unknown'}；允许 PDF、TXT、MD、JSON、CSV"
        )

    if ext in {"pdf", "txt", "md", "markdown"}:
        # FileParser already provides PDF/PyMuPDF and encoding fallback support.
        suffix = f".{ext}"
        import os
        import tempfile
        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            text = FileParser.extract_text(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    else:
        # Reuse the canonical session parser so JSON/CSV semantics stay aligned
        # with /api/cogsec/session/<id>/turn.
        turns = ingest_file(filename, content)
        text = "\n\n".join(turn.content for turn in turns if turn.content.strip())

    if not text.strip():
        raise InputAdapterError(f"文件没有可分析的文本内容: {filename}")

    return AdaptedInput(
        kind="file",
        filename=filename,
        text=text.strip(),
        content_type=content_type,
        byte_size=len(content),
        metadata={"extension": ext, "parser": "FileParser/session.ingest_file"},
    )


def _speech_provider() -> str:
    return str(getattr(Config, "MIRO_SPEECH_PROVIDER", "auto") or "auto").lower()


def transcribe_audio(
    filename: str,
    content: bytes,
    content_type: str = "",
    language: Optional[str] = None,
) -> AdaptedInput:
    """Transcribe audio through an OpenAI-compatible endpoint or local Whisper.

    The browser uses MediaRecorder, while this adapter keeps the server contract
    compatible with Whisper/OpenAI-style transcription APIs.  A local
    ``faster-whisper`` installation is optional; no model is downloaded by the
    server unless that provider is explicitly configured.
    """
    if not filename:
        filename = "recording.webm"
    if len(content) > MAX_AUDIO_UPLOAD_BYTES:
        raise InputAdapterError("音频不能超过 25 MB")

    ext = _extension(filename)
    if ext not in AUDIO_EXTENSIONS:
        raise InputAdapterError(
            f"不支持的音频格式: .{ext or 'unknown'}；允许 webm、wav、mp3、m4a、ogg"
        )

    provider = _speech_provider()
    if provider in {"auto", "remote", "openai", "openai_compatible"}:
        api_key = getattr(Config, "MIRO_SPEECH_API_KEY", None)
        if api_key:
            return _transcribe_remote(filename, content, content_type, language)
        if provider not in {"auto"}:
            raise SpeechTranscriptionUnavailable(
                "语音转写未完成：请配置 ASR 服务（MIRO_SPEECH_API_KEY），"
                "或切换到本地 faster-whisper。"
            )

    if provider in {"auto", "local", "faster_whisper"}:
        try:
            return _transcribe_local(filename, content, content_type, language)
        except ImportError as exc:
            raise SpeechTranscriptionUnavailable(
                "语音转写未完成：请配置 ASR 服务（MIRO_SPEECH_API_KEY），"
                "或安装本地 faster-whisper；也可使用浏览器原生语音识别。"
            ) from exc

    raise SpeechTranscriptionUnavailable(f"未知语音识别提供方: {provider}")


def _transcribe_remote(
    filename: str,
    content: bytes,
    content_type: str,
    language: Optional[str],
) -> AdaptedInput:
    from openai import OpenAI, Timeout

    api_key = Config.MIRO_SPEECH_API_KEY
    base_url = Config.MIRO_SPEECH_BASE_URL or None
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=Timeout(
            connect=Config.MIRO_SPEECH_CONNECT_TIMEOUT_SEC,
            read=Config.MIRO_SPEECH_READ_TIMEOUT_SEC,
            write=60.0,
            pool=10.0,
        ),
        max_retries=0,
    )
    file_payload = (filename, BytesIO(content), content_type or "application/octet-stream")
    kwargs: Dict[str, Any] = {
        "model": Config.MIRO_SPEECH_MODEL,
        "file": file_payload,
    }
    spoken_language = language or Config.MIRO_SPEECH_LANGUAGE
    if spoken_language:
        kwargs["language"] = spoken_language
    response = client.audio.transcriptions.create(**kwargs)
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        raise SpeechTranscriptionUnavailable("语音识别服务返回了空文本")
    return AdaptedInput(
        kind="audio",
        filename=filename,
        text=text,
        content_type=content_type,
        byte_size=len(content),
        metadata={
            "provider": "openai_compatible",
            "model": Config.MIRO_SPEECH_MODEL,
            "language": spoken_language,
        },
    )


def _transcribe_local(
    filename: str,
    content: bytes,
    content_type: str,
    language: Optional[str],
) -> AdaptedInput:
    from faster_whisper import WhisperModel

    import tempfile

    model = WhisperModel(
        Config.MIRO_SPEECH_LOCAL_MODEL,
        device=Config.MIRO_SPEECH_LOCAL_DEVICE,
        compute_type=Config.MIRO_SPEECH_LOCAL_COMPUTE_TYPE,
    )
    suffix = f".{_extension(filename) or 'webm'}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as handle:
        handle.write(content)
        handle.flush()
        segments, info = model.transcribe(handle.name, language=language or Config.MIRO_SPEECH_LANGUAGE)
        text = "".join(segment.text for segment in segments).strip()
    if not text:
        raise SpeechTranscriptionUnavailable("本地 Whisper 未识别到有效文本")
    return AdaptedInput(
        kind="audio",
        filename=filename,
        text=text,
        content_type=content_type,
        byte_size=len(content),
        metadata={
            "provider": "faster_whisper",
            "model": Config.MIRO_SPEECH_LOCAL_MODEL,
            "language": getattr(info, "language", None),
        },
    )


def build_adapted_scenario(
    text: str,
    documents: list[AdaptedInput],
    audio: list[AdaptedInput],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge all inputs while preserving source provenance for CanonicalCase."""
    parts: list[str] = []
    fragments: list[dict[str, Any]] = []
    adapters: list[dict[str, Any]] = []
    if text.strip():
        parts.append(text.strip())
        fragments.append({"role": "user", "content": text.strip(), "source": "chat"})
    for item in [*documents, *audio]:
        parts.append(f"[{item.kind}:{item.filename}]\n{item.text}")
        fragments.append({
            "role": "file_excerpt" if item.kind == "file" else "user",
            "content": item.text,
            "source": f"{item.kind}:{item.filename}",
            "metadata": item.metadata,
        })
        adapters.append(item.to_dict())
    return "\n\n".join(parts).strip(), fragments, adapters
