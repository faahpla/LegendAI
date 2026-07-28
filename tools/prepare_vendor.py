"""Prepara os recursos grandes que não devem ser versionados no Git."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from huggingface_hub import snapshot_download


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = PROJECT_ROOT / "vendor"
MODEL_DIR = VENDOR_DIR / "models" / "pt"
FFMPEG_DIR = VENDOR_DIR / "ffmpeg"
MODEL_REPOSITORY = "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese"
FFMPEG_ARCHIVE = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z"
MODEL_FILES = [
    "config.json",
    "preprocessor_config.json",
    "pytorch_model.bin",
    "special_tokens_map.json",
    "vocab.json",
]


def ensure_model() -> None:
    if all((MODEL_DIR / file_name).exists() for file_name in MODEL_FILES):
        print("Modelo de alinhamento já disponível.")
        return

    print("Baixando o modelo de alinhamento em português...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_REPOSITORY,
        local_dir=MODEL_DIR,
        allow_patterns=MODEL_FILES,
    )
    shutil.rmtree(MODEL_DIR / ".cache", ignore_errors=True)


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
    ensure_model()
    ensure_ffmpeg()
    print("Recursos offline prontos.")


if __name__ == "__main__":
    main()
