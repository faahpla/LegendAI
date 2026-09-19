"""Prepara o FFmpeg, que é grande demais para ser versionado no Git.

O modelo de alinhamento já morou aqui. Ele saiu porque eram 1,2 GB dentro do
instalador, baixados na máquina de quem compila para serem entregues a todo
mundo: agora quem o busca é o próprio aplicativo, na primeira geração, e em
metade do tamanho (ver `legendai/model_store.py`).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = PROJECT_ROOT / "vendor"
FFMPEG_DIR = VENDOR_DIR / "ffmpeg"
FFMPEG_ARCHIVE = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z"


def find_7zip() -> str:
    for command in ("7z", "7za"):
        executable = shutil.which(command)
        if executable:
            return executable
    raise RuntimeError("O 7-Zip é necessário para preparar o FFmpeg.")


def ensure_ffmpeg() -> None:
    ffmpeg = FFMPEG_DIR / "ffmpeg.exe"
    ffprobe = FFMPEG_DIR / "ffprobe.exe"
    if ffmpeg.exists() and ffprobe.exists():
        print("FFmpeg já disponível.")
        return

    print("Baixando o FFmpeg para Windows...")
    FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="legendai-ffmpeg-") as temp_dir:
        temp_path = Path(temp_dir)
        archive = temp_path / "ffmpeg.7z"
        urllib.request.urlretrieve(FFMPEG_ARCHIVE, archive)
        subprocess.run(
            [find_7zip(), "x", str(archive), f"-o{temp_path / 'extract'}", "-y"],
            check=True,
        )
        extracted_root = temp_path / "extract"
        for file_name in ("ffmpeg.exe", "ffprobe.exe"):
            source = next(extracted_root.rglob(file_name), None)
            if source is None:
                raise RuntimeError(f"{file_name} não foi encontrado no pacote do FFmpeg.")
            shutil.copy2(source, FFMPEG_DIR / file_name)


def main() -> None:
    ensure_ffmpeg()
    print("Recursos offline prontos.")


if __name__ == "__main__":
    main()
