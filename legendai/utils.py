"""Funções utilitárias: tempo, sistema de arquivos e verificação de ambiente."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Resolve um recurso empacotado, no fonte ou no executável congelado."""
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent
    return root.joinpath(*parts)


def bundled_ffmpeg_dir() -> Path | None:
    """Retorna o diretório com FFmpeg embutido, quando disponível."""
    path = resource_path("vendor", "ffmpeg")
    if (path / "ffmpeg.exe").exists() and (path / "ffprobe.exe").exists():
        return path
    return None


def ffmpeg_executable(name: str) -> str | None:
    """Resolve um binário do FFmpeg, priorizando a versão do LegendAI."""
    bundled = bundled_ffmpeg_dir()
    if bundled is not None:
        candidate = bundled / f"{name}.exe"
        if candidate.exists():
            return str(candidate)
    return shutil.which(name)


def prepare_runtime_environment() -> None:
    """Configura recursos locais para executar sem instalações externas."""
    ffmpeg_dir = bundled_ffmpeg_dir()
    if ffmpeg_dir is not None:
        current_path = os.environ.get("PATH", "")
        ffmpeg_path = str(ffmpeg_dir)
        if ffmpeg_path.casefold() not in current_path.casefold():
            os.environ["PATH"] = ffmpeg_path + os.pathsep + current_path

    nltk_data = resource_path("vendor", "nltk_data")
    if nltk_data.exists():
        os.environ["NLTK_DATA"] = str(nltk_data)


def ffmpeg_available() -> bool:
    return ffmpeg_executable("ffmpeg") is not None


def open_folder(path: Path) -> None:
    """Abre a pasta no Explorer (ou equivalente da plataforma)."""
    folder = path if path.is_dir() else path.parent
    if sys.platform == "win32":
        os.startfile(str(folder))  # noqa: S606 - ação explícita do usuário
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])


def normalize_word(word: str) -> str:
    """Normaliza para comparação: minúsculas, sem pontuação nas bordas."""
    stripped = word.strip().casefold()
    return stripped.strip(".,;:!?…\"'()[]{}«»“”‘’-–—")


def strip_special_characters(text: str, keep: str = '":') -> str:
    """Remove caracteres especiais do roteiro.

    Preserva letras (com acento), dígitos, espaços/quebras de linha e os
    caracteres listados em ``keep`` — por padrão aspas e dois-pontos. Espaços
    criados pela remoção são colapsados para não gerar tokens vazios.
    """
    allowed = set(keep)
    cleaned = "".join(
        char for char in text
        if char.isalnum() or char.isspace() or char in allowed
    )
    return re.sub(r"[^\S\n]{2,}", " ", cleaned).strip()


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def srt_timestamp(seconds: float) -> str:
    """00:00:00,000 — formato SRT."""
    total_ms = max(0, round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def srt_time_to_seconds(stamp: str) -> float:
    """Converte 'HH:MM:SS,mmm' (ou com ponto decimal) em segundos.

    É o inverso de :func:`srt_timestamp`. Aceita horas/milissegundos com
    dígitos faltando e usa ',' ou '.' como separador decimal.
    """
    match = re.search(r"(\d{1,3}):(\d{1,2}):(\d{1,2})[,.](\d{1,3})", stamp)
    if not match:
        raise ValueError(f"Timestamp SRT inválido: {stamp!r}")
    hours, minutes, secs, frac = match.groups()
    millis = int(frac.ljust(3, "0")[:3])
    return int(hours) * 3600 + int(minutes) * 60 + int(secs) + millis / 1000


def ass_timestamp(seconds: float) -> str:
    """0:00:00.00 — formato ASS (centésimos)."""
    total_cs = max(0, round(seconds * 100))
    hours, rem = divmod(total_cs, 360_000)
    minutes, rem = divmod(rem, 6_000)
    secs, cs = divmod(rem, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{cs:02d}"


def audio_duration_seconds(path: Path) -> float | None:
    """Duração via ffprobe; None se indisponível."""
    ffprobe = ffmpeg_executable("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return float(out.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        return None
