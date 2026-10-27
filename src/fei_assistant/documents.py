from io import BytesIO
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


RESUME_SUFFIXES = {".pdf", ".docx", ".txt"}
AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg"}


def validate_upload(filename: str, data: bytes, kind: str, max_bytes: int) -> str:
    suffix = Path(filename).suffix.lower()
    allowed = RESUME_SUFFIXES if kind == "resume" else AUDIO_SUFFIXES
    if suffix not in allowed:
        raise ValueError(f"unsupported {kind} file type: {suffix or 'none'}")
    if not data:
        raise ValueError("empty file")
    if len(data) > max_bytes:
        raise ValueError("file too large")
    signatures = {
        ".pdf": data.startswith(b"%PDF-"),
        ".docx": data.startswith(b"PK"),
        ".mp3": data.startswith(b"ID3") or data.startswith(b"\xff"),
        ".wav": data.startswith(b"RIFF") and data[8:12] == b"WAVE",
        ".m4a": len(data) > 8 and data[4:8] == b"ftyp",
        ".aac": data.startswith(b"\xff"),
        ".flac": data.startswith(b"fLaC"),
        ".ogg": data.startswith(b"OggS"),
    }
    if suffix in signatures and not signatures[suffix]:
        raise ValueError("file content does not match its extension")
    return suffix


def extract_resume_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        return data.decode("utf-8-sig")
    if suffix == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
    if suffix == ".docx":
        document = DocxDocument(BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    raise ValueError(f"unsupported resume file type: {suffix}")
