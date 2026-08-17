"""Backend HTTP local usado pela interface Electron do LegendAI."""

from __future__ import annotations

import argparse
import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .aligner import WhisperXAligner
from .engine import Cue
from .merge_split import CaptionMergeSplit
from .pipeline import generate_subtitles
from .settings import Settings
from .utils import open_folder, prepare_runtime_environment

log = logging.getLogger("legendai.server")


def cue_to_data(cue: Cue) -> dict[str, Any]:
    return {"text": cue.text, "start": cue.start, "end": cue.end}


def cues_from_data(raw_cues: object) -> list[Cue]:
    if not isinstance(raw_cues, list):
        raise ValueError("Legenda inválida.")
    cues: list[Cue] = []
    for raw in raw_cues:
        if not isinstance(raw, dict):
            raise ValueError("Legenda inválida.")
        cues.append(
            Cue(
                text=str(raw["text"]),
                start=float(raw["start"]),
                end=float(raw["end"]),
            )
        )
    return cues


class GenerationCancelled(RuntimeError):
    """Sinaliza que o usuário pediu para abortar a geração."""


@dataclass
class Job:
    """Estado serializável de uma geração em segundo plano."""

    id: str
    status: str = "queued"
    progress: float = 0.0
    message: str = "Preparando geração..."
    files: list[str] = field(default_factory=list)
    output_folder: str | None = None
    error: str | None = None
    # Cancelamento cooperativo: o pipeline chama `progress` em vários pontos e
    # é ali que a flag é observada — não dá para matar a thread do WhisperX.
    cancel_requested: bool = False

    def to_data(self) -> dict[str, Any]:
        return asdict(self)


class LegendApi:
    """Casos de uso expostos à interface, sem lógica HTTP acoplada."""

    HISTORY_LIMIT = 50

    def __init__(self) -> None:
        self.settings = Settings.load()
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._aligner: WhisperXAligner | None = None
        self.history: list[dict[str, Any]] = self._load_history()

    # ------------------------------------------------------------------
    # Histórico de gerações (JSON ao lado das configurações)
    # ------------------------------------------------------------------
    @property
    def history_path(self) -> Path:
        return self.settings.path.parent / "history.json"

    def _load_history(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return raw if isinstance(raw, list) else []

    def _save_history(self) -> None:
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(
                json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            log.warning("Não foi possível gravar o histórico.", exc_info=True)

    def history_data(self) -> dict[str, Any]:
        return {"entries": self.history}

    def clear_history(self) -> dict[str, Any]:
        self.history = []
        self._save_history()
        return self.history_data()

    def _record_history(self, audio: Path, script: str, result: Any) -> None:
        entry = {
            "id": uuid.uuid4().hex,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "audio_path": str(audio),
            "audio_name": audio.name,
            "script_preview": " ".join(script.split())[:160],
            "files": [str(path) for path in result.files],
            "output_folder": str(audio.parent),
            "cue_count": len(result.cues),
            "duration": result.audio_duration,
            "confidence": result.confidence,
        }
        with self._lock:
            self.history.insert(0, entry)
            del self.history[self.HISTORY_LIMIT:]
        self._save_history()

    def settings_data(self) -> dict[str, Any]:
        return asdict(self.settings)

    def save_settings(self, raw: dict[str, Any]) -> dict[str, Any]:
        numeric_fields = {
            "min_duration": float,
            "max_duration": float,
            "max_chars": int,
            "max_words": int,
            "margin_start": float,
            "margin_end": float,
            "max_gap": float,
            "min_alignment_score": float,
            "snap_fps": float,
        }
        boolean_fields = {
            "close_gaps", "export_srt", "export_ass", "open_folder",
            "strip_special_chars", "check_alignment",
        }
        string_fields = {
            "language", "shortcut_merge", "shortcut_split", "keep_characters",
        }

        for key, converter in numeric_fields.items():
            if key in raw:
                setattr(self.settings, key, converter(raw[key]))
        for key in boolean_fields:
            if key in raw:
                setattr(self.settings, key, bool(raw[key]))
        for key in string_fields:
            if key in raw:
                setattr(self.settings, key, str(raw[key]))
        if "small_words" in raw and isinstance(raw["small_words"], list):
            self.settings.small_words = [str(word) for word in raw["small_words"]]

        self.settings.save()
        return self.settings_data()

    def start_generation(self, audio_path: str, script: str) -> Job:
        audio = Path(audio_path)
        if not audio.exists():
            raise FileNotFoundError("Arquivo de áudio não encontrado.")
        if not script.strip():
            raise ValueError("Cole o roteiro antes de gerar a legenda.")
        with self._lock:
            if any(job.status in {"queued", "running"} for job in self.jobs.values()):
                raise RuntimeError("Já existe uma geração em andamento.")
            job = Job(id=uuid.uuid4().hex)
            self.jobs[job.id] = job

        thread = threading.Thread(
            target=self._run_generation, args=(job, audio, script), daemon=True
        )
        thread.start()
        return job

    def get_job(self, job_id: str) -> Job:
        try:
            return self.jobs[job_id]
        except KeyError as exc:
            raise ValueError("Geração não encontrada.") from exc

    def cancel_generation(self, job_id: str) -> Job:
        """Pede o cancelamento; efetivado no próximo ponto de progresso."""
        job = self.get_job(job_id)
        if job.status in {"queued", "running"}:
            job.cancel_requested = True
            job.message = "Cancelando..."
        return job

    def _run_generation(self, job: Job, audio: Path, script: str) -> None:
        job.status = "running"

        def progress(message: str, fraction: float) -> None:
            if job.cancel_requested:
                raise GenerationCancelled()
            job.message = message
            job.progress = max(0.0, min(1.0, fraction))

        try:
            if self._aligner is None or self._aligner.language != self.settings.language:
                self._aligner = WhisperXAligner(language=self.settings.language)
            result = generate_subtitles(
                audio, script, self.settings, progress, aligner=self._aligner
            )
            job.files = [str(path) for path in result.files]
            job.output_folder = str(audio.parent)
            job.message = "Legenda gerada com sucesso."
            job.progress = 1.0
            job.status = "completed"
            self._record_history(audio, script, result)
            if self.settings.open_folder and result.files:
                open_folder(result.files[0])
        except GenerationCancelled:
            log.info("Geração cancelada pelo usuário.")
            job.status = "cancelled"
            job.progress = 0.0
            job.message = "Geração cancelada."
        except Exception as exc:  # noqa: BLE001 - enviado à UI como falha da tarefa
            log.exception("Falha ao gerar legendas")
            job.status = "failed"
            job.error = str(exc)
            job.message = "Não foi possível gerar as legendas."

    @staticmethod
    def open_srt(path_text: str) -> dict[str, Any]:
        path = Path(path_text)
        if not path.exists():
            raise FileNotFoundError("Arquivo SRT não encontrado.")
        tool = CaptionMergeSplit.from_srt(path.read_text(encoding="utf-8-sig"))
        return {"path": str(path), "cues": [cue_to_data(cue) for cue in tool.cues]}

    @staticmethod
    def merge_srt(raw_cues: object, raw_indices: object) -> dict[str, Any]:
        if not isinstance(raw_indices, list):
            raise ValueError("Seleção inválida.")
        tool = CaptionMergeSplit(cues_from_data(raw_cues))
        tool.merge([int(index) for index in raw_indices])
        return {"cues": [cue_to_data(cue) for cue in tool.cues]}

    @staticmethod
    def split_srt(raw_cues: object, raw_index: object, text: object, position: object) -> dict[str, Any]:
        tool = CaptionMergeSplit(cues_from_data(raw_cues))
        tool.split_at(int(raw_index), str(text), int(position))
        return {"cues": [cue_to_data(cue) for cue in tool.cues]}

    @staticmethod
    def save_srt(path_text: str, raw_cues: object) -> dict[str, Any]:
        path = Path(path_text)
        tool = CaptionMergeSplit(cues_from_data(raw_cues))
        path.write_text(tool.to_srt(), encoding="utf-8-sig")
        return {"path": str(path)}


class ApiRequestHandler(BaseHTTPRequestHandler):
    """Adaptador JSON/HTTP fino para o :class:`LegendApi`."""

    api: LegendApi

    def log_message(self, format: str, *args: object) -> None:
        log.debug(format, *args)

    def do_OPTIONS(self) -> None:  # noqa: N802 - assinatura exigida pelo stdlib
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:  # noqa: N802 - assinatura exigida pelo stdlib
        path = urlparse(self.path).path
        try:
            if path == "/health":
                self._send_json(HTTPStatus.OK, {"ok": True})
            elif path == "/version":
                self._send_json(HTTPStatus.OK, {"version": __version__})
            elif path == "/settings":
                self._send_json(HTTPStatus.OK, self.api.settings_data())
            elif path == "/history":
                self._send_json(HTTPStatus.OK, self.api.history_data())
            elif path.startswith("/jobs/"):
                job = self.api.get_job(path.rsplit("/", 1)[-1])
                self._send_json(HTTPStatus.OK, job.to_data())
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")
        except (ValueError, FileNotFoundError) as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except Exception as exc:  # noqa: BLE001 - proteção da ponte local
            log.exception("Falha na requisição GET")
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def do_POST(self) -> None:  # noqa: N802 - assinatura exigida pelo stdlib
        path = urlparse(self.path).path
        try:
            data = self._read_json()
            if path == "/settings":
                self._send_json(HTTPStatus.OK, self.api.save_settings(data))
            elif path == "/generate":
                job = self.api.start_generation(str(data["audio_path"]), str(data["script"]))
                self._send_json(HTTPStatus.ACCEPTED, job.to_data())
            elif path == "/jobs/cancel":
                job = self.api.cancel_generation(str(data["id"]))
                self._send_json(HTTPStatus.OK, job.to_data())
            elif path == "/history/clear":
                self._send_json(HTTPStatus.OK, self.api.clear_history())
            elif path == "/srt/open":
                self._send_json(HTTPStatus.OK, self.api.open_srt(str(data["path"])))
            elif path == "/srt/merge":
                self._send_json(HTTPStatus.OK, self.api.merge_srt(data["cues"], data["indices"]))
            elif path == "/srt/split":
                self._send_json(
                    HTTPStatus.OK,
                    self.api.split_srt(data["cues"], data["index"], data["text"], data["position"]),
                )
            elif path == "/srt/save":
                self._send_json(HTTPStatus.OK, self.api.save_srt(str(data["path"]), data["cues"]))
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")
        except (KeyError, TypeError, ValueError, FileNotFoundError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except RuntimeError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except Exception as exc:  # noqa: BLE001 - proteção da ponte local
            log.exception("Falha na requisição POST")
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _read_json(self) -> dict[str, Any]:
        size = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(size).decode("utf-8")
        data = json.loads(raw or "{}")
        if not isinstance(data, dict):
            raise ValueError("Corpo da requisição inválido.")
        return data

    def _send_json(self, status: HTTPStatus, data: dict[str, Any]) -> None:
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if status != HTTPStatus.NO_CONTENT:
            self.wfile.write(content)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend local do LegendAI")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    prepare_runtime_environment()
    ApiRequestHandler.api = LegendApi()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ApiRequestHandler)
    print(f"LegendAI backend listening on {args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
