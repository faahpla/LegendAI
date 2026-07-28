"""Interface gráfica do LegendAI (CustomTkinter, tema escuro, minimalista)."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
from tkinter import ttk
from pathlib import Path

import customtkinter as ctk

from . import APP_NAME, __version__
from .merge_split import CaptionMergeSplit
from .settings import Settings
from .utils import (
    audio_duration_seconds,
    ffmpeg_available,
    open_folder,
    resource_path,
    srt_timestamp,
)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    _DnDBase = TkinterDnD.DnDWrapper
except Exception:  # noqa: BLE001 - biblioteca opcional; app degrada para só-botão
    DND_FILES = None
    TkinterDnD = None
    _DnDBase = object

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

# --- Paleta / design tokens -------------------------------------------------
# Dark sóbrio. As superfícies quase se fundem ao fundo; cor fica só nas ações.
BG = "#0B0C10"
SURFACE = "#12141B"
SURFACE_2 = "#191C25"
BORDER = "#282C38"

ACCENT = "#8B5CF6"
ACCENT_HOVER = "#7C4DE8"
ACCENT_SOFT = "#201C32"

BLUE = "#3B82F6"        # secundário (Split)
BLUE_HOVER = "#2E6FE0"

TEXT = "#F8F9FC"
MUTED = "#A7ADBC"
FAINT = "#72798A"
SUCCESS = "#34D399"
ERROR = "#F87171"

log = logging.getLogger("legendai")

try:
    from PIL import Image

    def _load_logo(size: int) -> "ctk.CTkImage | None":
        path = resource_path("assets", "legendai.png")
        if not path.exists():
            return None
        try:
            image = Image.open(path)
            return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
        except Exception:  # noqa: BLE001 - logo é cosmético
            return None
except Exception:  # noqa: BLE001 - Pillow ausente: app segue sem logo
    def _load_logo(size: int) -> None:
        return None


def _fmt_duration(seconds: float) -> str:
    """Segundos -> 'MM:SS' (ou 'HH:MM:SS' quando passa de uma hora)."""
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _apply_app_icon(window) -> None:
    """Aplica o ícone do LegendAI a uma janela (raiz ou Toplevel).

    O CustomTkinter redefine o ícone ~200 ms após criar a janela, então
    reaplicamos com atraso para que a barra de título use o ícone do app.
    """
    icon = resource_path("assets", "legendai.ico")
    if not icon.exists():
        return

    def apply() -> None:
        try:
            window.iconbitmap(str(icon))
        except Exception:  # noqa: BLE001 - ícone é cosmético
            pass

    apply()
    window.after(300, apply)


class QueueLogHandler(logging.Handler):
    """Encaminha registros de log para a fila consumida pela janela de log."""

    def __init__(self, target: "queue.Queue[str]") -> None:
        super().__init__()
        self.target = target
        self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        self.target.put(self.format(record))


class LogWindow(ctk.CTkToplevel):
    def __init__(self, master: ctk.CTk) -> None:
        super().__init__(master)
        self.title(f"{APP_NAME} — Log")
        self.geometry("560x360")
        self.attributes("-topmost", False)
        self.configure(fg_color=BG)
        _apply_app_icon(self)
        self.textbox = ctk.CTkTextbox(
            self, font=("Consolas", 12), wrap="word", corner_radius=12,
            fg_color=SURFACE, border_width=1, border_color=BORDER,
        )
        self.textbox.pack(fill="both", expand=True, padx=12, pady=12)
        self.textbox.configure(state="disabled")

    def append(self, line: str) -> None:
        self.textbox.configure(state="normal")
        self.textbox.insert("end", line + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")


class SettingsWindow(ctk.CTkToplevel):
    """Tela de configurações persistidas em JSON."""

    def __init__(self, master: "LegendAIApp", settings: Settings) -> None:
        super().__init__(master)
        self.title(f"{APP_NAME} — Configurações")
        self.geometry("640x720")
        self.minsize(600, 650)
        self.configure(fg_color=BG)
        _apply_app_icon(self)
        self.settings = settings
        self._build()

    def _build_legacy(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 4))
        ctk.CTkLabel(
            header, text="⚙  Configurações", anchor="w", text_color=TEXT,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left")

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=(8, 20))

        self.entries: dict[str, ctk.CTkEntry] = {}
        numeric_fields = [
            ("Tempo mínimo (s)", "min_duration"),
            ("Tempo máximo (s)", "max_duration"),
            ("Caracteres máximos", "max_chars"),
            ("Margem inicial (s)", "margin_start"),
            ("Margem final (s)", "margin_end"),
            ("Fechar vãos até (s)", "max_gap"),
        ]
        for label_text, attr in numeric_fields:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=6)
            ctk.CTkLabel(row, text=label_text, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=110, justify="center")
            entry.insert(0, str(getattr(self.settings, attr)))
            entry.pack(side="right")
            self.entries[attr] = entry

        self.switches: dict[str, ctk.CTkSwitch] = {}
        switch_fields = [
            ("Fechar vãos entre legendas (sem flicker)", "close_gaps"),
            ("Exportar SRT", "export_srt"),
            ("Exportar ASS", "export_ass"),
            ("Abrir pasta automaticamente", "open_folder"),
        ]
        for label_text, attr in switch_fields:
            switch = ctk.CTkSwitch(frame, text=label_text, progress_color=ACCENT)
            if getattr(self.settings, attr):
                switch.select()
            switch.pack(anchor="w", pady=8)
            self.switches[attr] = switch

        self.shortcut_entries: dict[str, ctk.CTkEntry] = {}
        shortcut_fields = [
            ("Atalho Merge", "shortcut_merge"),
            ("Atalho Split", "shortcut_split"),
        ]
        for label_text, attr in shortcut_fields:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=6)
            ctk.CTkLabel(row, text=label_text, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=140, justify="center")
            entry.insert(0, str(getattr(self.settings, attr)))
            entry.pack(side="right")
            self.shortcut_entries[attr] = entry

        self.feedback = ctk.CTkLabel(frame, text="", text_color=MUTED)
        self.feedback.pack(pady=(10, 0))
        ctk.CTkButton(
            frame, text="💾  Salvar", height=44, corner_radius=12,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._save,
        ).pack(fill="x", pady=(14, 0))

    def _build(self) -> None:
        """Um painel de preferências único, sem cartões em cascata."""
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=28, pady=(22, 20))

        header = ctk.CTkFrame(root, fg_color="transparent")
        header.pack(fill="x", pady=(0, 18))
        ctk.CTkLabel(header, text="Configurações", text_color=TEXT,
                     font=ctk.CTkFont(size=23, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text="Defina o ritmo das legendas e os arquivos de saída.",
                     text_color=MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(5, 0))

        panel = ctk.CTkFrame(root, fg_color=SURFACE, corner_radius=14,
                             border_width=1, border_color=BORDER)
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_columnconfigure(1, weight=1)

        self._settings_section(panel, "LEITURA E TEMPO", 0)
        self.entries = {}
        fields = [
            ("Tempo mínimo", "min_duration", "s"),
            ("Tempo máximo", "max_duration", "s"),
            ("Caracteres máximos", "max_chars", "caracteres"),
            ("Fechar vãos até", "max_gap", "s"),
            ("Margem inicial", "margin_start", "s"),
            ("Margem final", "margin_end", "s"),
        ]
        for index, (label, attr, unit) in enumerate(fields):
            cell = ctk.CTkFrame(panel, fg_color="transparent")
            cell.grid(row=index // 2 + 1, column=index % 2, sticky="ew", padx=18, pady=5)
            ctk.CTkLabel(cell, text=label, text_color=MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")
            line = ctk.CTkFrame(cell, fg_color="transparent")
            line.pack(fill="x", pady=(4, 0))
            entry = ctk.CTkEntry(line, height=32, fg_color=SURFACE_2, border_color=BORDER,
                                 text_color=TEXT, justify="center")
            entry.insert(0, str(getattr(self.settings, attr)))
            entry.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(line, text=unit, text_color=FAINT, width=54,
                         font=ctk.CTkFont(size=10)).pack(side="right")
            self.entries[attr] = entry

        self._settings_divider(panel, 4)
        self._settings_section(panel, "EXPORTAÇÃO", 5)
        self.switches = {}
        for index, (label, attr) in enumerate((
            ("Fechar vãos entre legendas", "close_gaps"),
            ("Exportar arquivo SRT", "export_srt"),
            ("Exportar arquivo ASS", "export_ass"),
            ("Abrir a pasta ao concluir", "open_folder"),
        )):
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.grid(row=index + 6, column=0, columnspan=2, sticky="ew", padx=18, pady=2)
            ctk.CTkLabel(row, text=label, text_color=TEXT,
                         font=ctk.CTkFont(size=12)).pack(side="left")
            switch = ctk.CTkSwitch(row, text="", width=38, height=20,
                                   progress_color=ACCENT, button_color=TEXT,
                                   button_hover_color=TEXT)
            if getattr(self.settings, attr):
                switch.select()
            switch.pack(side="right")
            self.switches[attr] = switch

        self._settings_divider(panel, 10)
        self._settings_section(panel, "ATALHOS", 11)
        self.shortcut_entries = {}
        for index, (label, attr) in enumerate((("Mesclar", "shortcut_merge"), ("Dividir", "shortcut_split"))):
            cell = ctk.CTkFrame(panel, fg_color="transparent")
            cell.grid(row=12, column=index, sticky="ew", padx=18, pady=(2, 16))
            ctk.CTkLabel(cell, text=label, text_color=MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")
            entry = ctk.CTkEntry(cell, height=32, fg_color=SURFACE_2, border_color=BORDER,
                                 text_color=TEXT, justify="center")
            entry.insert(0, str(getattr(self.settings, attr)))
            entry.pack(fill="x", pady=(4, 0))
            self.shortcut_entries[attr] = entry

        footer = ctk.CTkFrame(root, fg_color="transparent")
        footer.pack(fill="x", pady=(16, 0))
        self.feedback = ctk.CTkLabel(footer, text="", text_color=MUTED,
                                     anchor="w", font=ctk.CTkFont(size=11))
        self.feedback.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            footer, text="Salvar", width=112, height=38, corner_radius=9,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"), command=self._save,
        ).pack(side="right")

    @staticmethod
    def _settings_section(parent, title: str, row: int) -> None:
        ctk.CTkLabel(parent, text=title, text_color=FAINT,
                     font=ctk.CTkFont(size=10, weight="bold")).grid(
                         row=row, column=0, columnspan=2, sticky="w", padx=18, pady=(14, 7)
                     )

    @staticmethod
    def _settings_divider(parent, row: int) -> None:
        ctk.CTkFrame(parent, height=1, fg_color=BORDER).grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=18, pady=(11, 1)
        )

    @staticmethod
    def _settings_card(parent, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=14,
                            border_width=1, border_color=BORDER)
        ctk.CTkLabel(card, text=title, text_color=MUTED,
                     font=ctk.CTkFont(size=10, weight="bold")).grid(
                         row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(13, 4)
                     )
        return card

    def _save(self) -> None:
        try:
            self.settings.min_duration = float(self.entries["min_duration"].get())
            self.settings.max_duration = float(self.entries["max_duration"].get())
            self.settings.max_chars = int(self.entries["max_chars"].get())
            self.settings.margin_start = float(self.entries["margin_start"].get())
            self.settings.margin_end = float(self.entries["margin_end"].get())
            self.settings.max_gap = float(self.entries["max_gap"].get())
        except ValueError:
            self.feedback.configure(text="Valores numéricos inválidos.", text_color=ERROR)
            return
        for attr, switch in self.switches.items():
            setattr(self.settings, attr, bool(switch.get()))
        for attr, entry in self.shortcut_entries.items():
            value = entry.get().strip()
            if value:
                setattr(self.settings, attr, value)
        self.settings.save()
        self.feedback.configure(
            text="Configurações salvas. Reabra o Merge & Split para aplicar atalhos.",
            text_color=SUCCESS,
        )


def to_tk_binding(shortcut: str) -> str:
    """Converte 'Ctrl+Shift+M' no formato de binding do Tk '<Control-Shift-M>'."""
    aliases = {
        "ctrl": "Control", "control": "Control", "shift": "Shift",
        "alt": "Alt", "cmd": "Command", "command": "Command", "meta": "Command",
        "super": "Super", "win": "Super",
    }
    keys = []
    for part in (p.strip() for p in shortcut.split("+")):
        if not part:
            continue
        keys.append(aliases.get(part.lower(), part.upper() if len(part) == 1 else part))
    return "<" + "-".join(keys) + ">"


class SplitDialog(ctk.CTkToplevel):
    """Modal de divisão: o cursor entre duas palavras define o ponto de quebra.

    O ``on_confirm`` recebe ``(texto, posição_do_cursor)`` e devolve uma
    mensagem de erro (ou ``None`` em caso de sucesso).
    """

    def __init__(self, master: "MergeSplitWindow", text: str, on_confirm) -> None:
        super().__init__(master)
        self.title(f"{APP_NAME} — Dividir legenda")
        self.geometry("520x320")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        _apply_app_icon(self)
        self._on_confirm = on_confirm
        self._build(text)
        self.transient(master)
        self.after(50, self._grab)

    def _grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _build(self, text: str) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=18)

        ctk.CTkLabel(frame, text="Texto atual:", anchor="w").pack(fill="x")
        ctk.CTkLabel(
            frame, text=text, anchor="w", justify="left", wraplength=460,
            text_color=MUTED,
        ).pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(
            frame, text="Clique entre duas palavras e pressione Dividir:", anchor="w"
        ).pack(fill="x")
        self.editor = ctk.CTkTextbox(
            frame, height=80, font=ctk.CTkFont(size=15), wrap="word",
            corner_radius=10, fg_color=SURFACE, border_width=1, border_color=BORDER,
        )
        self.editor.pack(fill="x", pady=(4, 4))
        self.editor.insert("1.0", text)
        # Posiciona o cursor na fronteira de palavra mais próxima do meio, para
        # que um Enter imediato já produza uma divisão sensata.
        self.editor.mark_set("insert", f"1.0+{self._default_offset(text)}c")
        self.editor.focus_set()

        self.feedback = ctk.CTkLabel(frame, text="", text_color=ERROR)
        self.feedback.pack(fill="x")

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(
            buttons, text="Cancelar", fg_color="transparent", border_width=1,
            border_color=MUTED, text_color=MUTED, command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            buttons, text="✂️  Dividir", corner_radius=10, fg_color=ACCENT,
            hover_color=ACCENT_HOVER, font=ctk.CTkFont(size=13, weight="bold"),
            command=self._confirm,
        ).pack(side="right")
        # Enter confirma sem inserir quebra de linha; Esc cancela.
        self.editor.bind("<Return>", self._on_return)
        self.bind("<Escape>", lambda _e: self.destroy())

    @staticmethod
    def _default_offset(text: str) -> int:
        """Offset da fronteira entre palavras mais próxima do meio do texto."""
        spaces = [i for i, ch in enumerate(text) if ch == " "]
        if not spaces:
            return len(text) // 2
        middle = len(text) // 2
        return min(spaces, key=lambda i: abs(i - middle))

    def _on_return(self, _event) -> str:
        self._confirm()
        return "break"  # impede a inserção de uma quebra de linha no campo

    def _confirm(self) -> None:
        text = self.editor.get("1.0", "end-1c")
        position = len(self.editor.get("1.0", "insert"))
        error = self._on_confirm(text, position)
        if error:
            self.feedback.configure(text=error)
        else:
            self.destroy()


class MergeSplitWindow(ctk.CTkToplevel):
    """Editor rápido de SRT: mesclar e dividir legendas sem sair do LegendAI."""

    def __init__(self, master: "LegendAIApp", settings: Settings) -> None:
        super().__init__(master)
        self.app = master
        self.settings = settings
        self.tool = CaptionMergeSplit()
        self.srt_path: Path | None = None
        self._dirty = False
        self.title(f"{APP_NAME} — Merge & Split")
        self.geometry("860x660")
        self.minsize(720, 540)
        _apply_app_icon(self)
        self._build()
        self._bind_shortcuts()
        self._register_srt_drop()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    def _build_legacy(self) -> None:
        self.configure(fg_color=BG)

        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=22, pady=18)

        # --- Barra de ferramentas -----------------------------------------
        top = ctk.CTkFrame(root, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkButton(
            top, text="📂  Abrir SRT", width=128, height=40, corner_radius=11,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._open_srt,
        ).pack(side="left")
        ctk.CTkButton(
            top, text="💾  Salvar", width=110, height=40, corner_radius=11,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=SURFACE, hover_color=SURFACE_2, text_color=TEXT,
            border_width=1, border_color=BORDER, command=self._save_srt,
        ).pack(side="left", padx=(8, 0))
        self.file_check = ctk.CTkLabel(top, text="", text_color=SUCCESS,
                                       font=ctk.CTkFont(size=14, weight="bold"))
        self.file_check.pack(side="right")
        self.file_label = ctk.CTkLabel(top, text="Nenhum SRT aberto", text_color=MUTED)
        self.file_label.pack(side="right", padx=(0, 6))

        # --- Tabela de legendas -------------------------------------------
        self.list_frame = ctk.CTkFrame(
            root, fg_color=SURFACE, corner_radius=14,
            border_width=1, border_color=BORDER,
        )
        self.list_frame.pack(fill="both", expand=True, pady=14)
        self._style_tree()
        columns = ("check", "idx", "start", "end", "text")
        self.tree = ttk.Treeview(
            self.list_frame, columns=columns, show="headings",
            selectmode="extended", style="MS.Treeview",
        )
        for col, title, width, anchor, stretch in (
            ("check", "", 44, "center", False),
            ("idx", "#", 52, "center", False),
            ("start", "Início", 130, "w", False),
            ("end", "Fim", 130, "w", False),
            ("text", "Legenda", 320, "w", True),
        ):
            self.tree.heading(col, text=title, anchor="w" if anchor == "w" else "center")
            self.tree.column(col, width=width, anchor=anchor, stretch=stretch)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar = ctk.CTkScrollbar(self.list_frame, command=self.tree.yview)
        scrollbar.pack(side="right", fill="y", padx=(2, 8), pady=10)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _e: self._on_split())

        # --- Cartão de resumo da seleção ----------------------------------
        summary = ctk.CTkFrame(root, fg_color=SURFACE, corner_radius=12,
                               border_width=1, border_color=BORDER)
        summary.pack(fill="x")
        badge = ctk.CTkFrame(summary, width=40, height=40, corner_radius=20,
                             fg_color=ACCENT_SOFT)
        badge.pack(side="left", padx=(14, 12), pady=12)
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="🎬", font=ctk.CTkFont(size=17)).pack(expand=True)
        sel_col = ctk.CTkFrame(summary, fg_color="transparent")
        sel_col.pack(side="left", pady=10)
        self.sel_title = ctk.CTkLabel(sel_col, text="Nenhuma legenda selecionada",
                                      text_color=TEXT, anchor="w",
                                      font=ctk.CTkFont(size=13, weight="bold"))
        self.sel_title.pack(anchor="w")
        self.sel_range = ctk.CTkLabel(sel_col, text="—", text_color=MUTED, anchor="w",
                                      font=ctk.CTkFont(size=12))
        self.sel_range.pack(anchor="w")
        total_col = ctk.CTkFrame(summary, fg_color="transparent")
        total_col.pack(side="right", padx=(0, 18), pady=10)
        ctk.CTkLabel(total_col, text="Duração total", text_color=MUTED, anchor="e",
                     font=ctk.CTkFont(size=11)).pack(anchor="e")
        self.sel_total = ctk.CTkLabel(total_col, text="00:00:00,000", text_color=TEXT,
                                      anchor="e", font=ctk.CTkFont(size=15, weight="bold"))
        self.sel_total.pack(anchor="e")

        # --- Botões de ação -----------------------------------------------
        actions = ctk.CTkFrame(root, fg_color="transparent")
        actions.pack(fill="x", pady=(12, 0))
        self._action_button(
            actions, "🔗", "Merge", self.settings.shortcut_merge,
            "Mesclar legendas selecionadas", ACCENT, ACCENT_HOVER, self._on_merge,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._action_button(
            actions, "✂️", "Split", self.settings.shortcut_split,
            "Dividir legenda selecionada", BLUE, BLUE_HOVER, self._on_split,
        ).pack(side="left", expand=True, fill="x", padx=(6, 0))

        # --- Rodapé --------------------------------------------------------
        footer = ctk.CTkFrame(root, fg_color="transparent")
        footer.pack(fill="x", pady=(12, 0))
        self.count_label = ctk.CTkLabel(footer, text="Nenhuma legenda carregada",
                                        text_color=MUTED, font=ctk.CTkFont(size=12))
        self.count_label.pack(side="left")
        self.status = ctk.CTkLabel(
            footer, text="Dica: use Ctrl ou Shift para selecionar múltiplas legendas",
            text_color=FAINT, font=ctk.CTkFont(size=12),
        )
        self.status.pack(side="right")

    def _build(self) -> None:
        self.configure(fg_color=BG)

        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=20, pady=18)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(root, fg_color=SURFACE, corner_radius=16,
                              border_width=1, border_color=BORDER)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.grid_columnconfigure(1, weight=1)
        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=16, pady=13)
        ctk.CTkLabel(brand, text="Ajustar legendas", text_color=TEXT,
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(brand, text="Mescle ou divida blocos sem sair do LegendAI.", text_color=MUTED,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(3, 0))
        tools = ctk.CTkFrame(header, fg_color="transparent")
        tools.grid(row=0, column=1, sticky="e", padx=14, pady=18)
        ctk.CTkButton(
            tools, text="Salvar SRT", width=98, height=34, corner_radius=9,
            fg_color=SURFACE_2, hover_color=ACCENT_SOFT, text_color=TEXT,
            command=self._save_srt,
        ).pack(side="right")
        ctk.CTkButton(
            tools, text="Abrir SRT", width=98, height=34, corner_radius=9,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"), command=self._open_srt,
        ).pack(side="right", padx=(0, 8))

        source = ctk.CTkFrame(root, fg_color=SURFACE, corner_radius=14,
                               border_width=1, border_color=BORDER)
        source.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        source.grid_columnconfigure(1, weight=1)
        self.file_check = ctk.CTkLabel(source, text="", text_color=SUCCESS,
                                       font=ctk.CTkFont(size=12, weight="bold"))
        self.file_check.grid(row=0, column=0, sticky="w", padx=(16, 7), pady=13)
        self.file_label = ctk.CTkLabel(source, text="Nenhum arquivo SRT aberto", text_color=MUTED,
                                       anchor="w", font=ctk.CTkFont(size=12))
        self.file_label.grid(row=0, column=1, sticky="w", pady=13)
        ctk.CTkLabel(source, text="Arraste um SRT para a tabela ou use Abrir SRT.", text_color=FAINT,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=2, sticky="e", padx=16, pady=13)

        self.list_frame = ctk.CTkFrame(root, fg_color=SURFACE, corner_radius=14,
                                        border_width=1, border_color=BORDER)
        self.list_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        self._style_tree()
        columns = ("check", "idx", "start", "end", "text")
        self.tree = ttk.Treeview(self.list_frame, columns=columns, show="headings",
                                 selectmode="extended", style="MS.Treeview")
        for col, title, width, anchor, stretch in (
            ("check", "", 42, "center", False),
            ("idx", "#", 48, "center", False),
            ("start", "Início", 130, "w", False),
            ("end", "Fim", 130, "w", False),
            ("text", "Legenda", 360, "w", True),
        ):
            self.tree.heading(col, text=title, anchor="w" if anchor == "w" else "center")
            self.tree.column(col, width=width, anchor=anchor, stretch=stretch)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar = ctk.CTkScrollbar(self.list_frame, command=self.tree.yview)
        scrollbar.pack(side="right", fill="y", padx=(3, 8), pady=10)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _e: self._on_split())

        selection = ctk.CTkFrame(root, fg_color=SURFACE, corner_radius=14,
                                  border_width=1, border_color=BORDER)
        selection.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        selection.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(selection, text="SELEÇÃO", text_color=MUTED,
                     font=ctk.CTkFont(size=10, weight="bold")).grid(
                         row=0, column=0, sticky="w", padx=16, pady=(12, 2)
                     )
        self.sel_title = ctk.CTkLabel(selection, text="Nenhuma legenda selecionada", text_color=TEXT,
                                      anchor="w", font=ctk.CTkFont(size=13, weight="bold"))
        self.sel_title.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))
        self.sel_range = ctk.CTkLabel(selection, text="—", text_color=MUTED,
                                      font=ctk.CTkFont(size=11))
        self.sel_range.grid(row=1, column=1, sticky="w", padx=12, pady=(0, 12))
        total = ctk.CTkFrame(selection, fg_color="transparent")
        total.grid(row=0, column=2, rowspan=2, sticky="e", padx=16, pady=10)
        ctk.CTkLabel(total, text="DURAÇÃO", text_color=MUTED,
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="e")
        self.sel_total = ctk.CTkLabel(total, text="00:00:00,000", text_color=TEXT,
                                      font=ctk.CTkFont(size=14, weight="bold"))
        self.sel_total.pack(anchor="e", pady=(2, 0))

        footer = ctk.CTkFrame(root, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew")
        self.count_label = ctk.CTkLabel(footer, text="Nenhuma legenda carregada", text_color=MUTED,
                                        font=ctk.CTkFont(size=12))
        self.count_label.pack(side="left")
        self.status = ctk.CTkLabel(footer, text="Use Ctrl ou Shift para selecionar várias legendas.",
                                   text_color=FAINT, font=ctk.CTkFont(size=11))
        self.status.pack(side="left", padx=18)
        ctk.CTkButton(
            footer, text="Dividir", width=94, height=38, corner_radius=9,
            fg_color=SURFACE_2, hover_color=BLUE_HOVER, text_color=TEXT,
            command=self._on_split,
        ).pack(side="right")
        ctk.CTkButton(
            footer, text="Mesclar selecionadas", width=166, height=38, corner_radius=9,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"), command=self._on_merge,
        ).pack(side="right", padx=(0, 8))

    def _style_tree(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "MS.Treeview", background=SURFACE, fieldbackground=SURFACE,
            foreground="#C9CEDA", rowheight=32, borderwidth=0, relief="flat",
            bordercolor=SURFACE, lightcolor=SURFACE, darkcolor=SURFACE,
            font=("Segoe UI", 11),
        )
        style.map(
            "MS.Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "white")],
        )
        style.configure(
            "MS.Treeview.Heading", background=SURFACE_2, foreground=MUTED,
            relief="flat", borderwidth=0, font=("Segoe UI", 10, "bold"),
        )
        style.map("MS.Treeview.Heading", background=[("active", SURFACE_2)])
        # Remove a moldura branca nativa do Treeview (elemento 'field'),
        # deixando apenas a área das linhas.
        style.layout("MS.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def _action_button(self, parent, icon, title, shortcut, subtitle,
                       color, hover, command) -> ctk.CTkFrame:
        """Botão-cartão com ícone, título, atalho e subtítulo (com hover)."""
        card = ctk.CTkFrame(parent, fg_color=color, corner_radius=13, height=64)
        card.pack_propagate(False)
        head = ctk.CTkLabel(
            card, text=f"{icon}   {title}    ({shortcut})", text_color="white",
            anchor="w", font=ctk.CTkFont(size=15, weight="bold"),
        )
        head.pack(anchor="w", padx=16, pady=(12, 0))
        sub = ctk.CTkLabel(card, text=subtitle, text_color="#EAEAF6", anchor="w",
                           font=ctk.CTkFont(size=11))
        sub.pack(anchor="w", padx=16, pady=(0, 12))
        for widget in (card, head, sub):
            widget.bind("<Button-1>", lambda _e: command())
            widget.bind("<Enter>", lambda _e: card.configure(fg_color=hover))
            widget.bind("<Leave>", lambda _e: card.configure(fg_color=color))
        return card

    def _bind_shortcuts(self) -> None:
        for shortcut, handler in (
            (self.settings.shortcut_merge, self._on_merge),
            (self.settings.shortcut_split, self._on_split),
        ):
            try:
                self.bind(to_tk_binding(shortcut), lambda _e, h=handler: h())
            except tk.TclError:
                log.warning("Atalho inválido ignorado: %s", shortcut)

    # ------------------------------------------------------------------
    # Drag-and-drop: reaproveita o tkdnd já carregado pela janela principal.
    # ------------------------------------------------------------------
    def _register_srt_drop(self) -> None:
        if DND_FILES is None or not getattr(self.app, "_dnd_ok", False):
            return
        for widget in (self.list_frame, self.tree):
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_srt_drop)
                widget.dnd_bind("<<DropEnter>>", lambda _e: self._highlight_drop(True))
                widget.dnd_bind("<<DropLeave>>", lambda _e: self._highlight_drop(False))
            except Exception:  # noqa: BLE001 - DnD é opcional; segue só-botão
                pass

    def _highlight_drop(self, active: bool) -> None:
        self.list_frame.configure(border_color=ACCENT if active else BORDER)

    def _on_srt_drop(self, event) -> None:
        self._highlight_drop(False)
        paths = LegendAIApp._split_drop_paths(event.data)
        if paths:
            self._load_srt_path(Path(paths[0]))

    # ------------------------------------------------------------------
    def _open_srt(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Abrir legenda SRT",
            filetypes=[("Legenda SRT", "*.srt"), ("Todos", "*.*")],
        )
        if chosen:
            self._load_srt_path(Path(chosen))

    def _load_srt_path(self, path: Path) -> None:
        """Carrega um SRT (via botão ou arraste), validando a extensão."""
        if path.suffix.lower() != ".srt":
            self._set_status(f"Selecione um arquivo .srt (recebido: {path.suffix}).", ERROR)
            return
        try:
            content = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            self._set_status(f"Não foi possível abrir: {exc}", ERROR)
            return
        self.tool = CaptionMergeSplit.from_srt(content)
        self.srt_path = path
        self._dirty = False
        self.file_label.configure(text=path.name, text_color=TEXT)
        self.file_check.configure(text="✓")
        self._refresh()
        if self.tool.cues:
            self._set_status(
                "Dica: use Ctrl ou Shift para selecionar múltiplas legendas", FAINT
            )
        else:
            self._set_status("Nenhuma legenda encontrada no arquivo.", ERROR)

    def _save_srt(self) -> None:
        if not self.tool.cues:
            self._set_status("Nada para salvar.", ERROR)
            return
        target = self.srt_path
        if target is None:
            chosen = filedialog.asksaveasfilename(
                title="Salvar legenda SRT", defaultextension=".srt",
                filetypes=[("Legenda SRT", "*.srt")],
            )
            if not chosen:
                return
            target = Path(chosen)
        try:
            target.write_text(self.tool.to_srt(), encoding="utf-8-sig")
        except OSError as exc:
            self._set_status(f"Falha ao salvar: {exc}", ERROR)
            return
        self.srt_path = target
        self._dirty = False
        self.file_label.configure(text=target.name, text_color=TEXT)
        self.file_check.configure(text="✓")
        self._set_status(f"Salvo em {target.name}.", SUCCESS)

    # ------------------------------------------------------------------
    def _selected_indices(self) -> list[int]:
        return sorted(int(iid) for iid in self.tree.selection())

    def _on_merge(self) -> None:
        indices = self._selected_indices()
        if len(indices) < 2:
            self._set_status("Selecione duas ou mais legendas para mesclar.", ERROR)
            return
        try:
            self.tool.merge(indices)
        except (ValueError, IndexError) as exc:
            self._set_status(str(exc), ERROR)
            return
        self._dirty = True
        self._refresh(select=[min(indices)])
        self._set_status("Legendas mescladas.", SUCCESS)

    def _on_split(self) -> None:
        indices = self._selected_indices()
        if len(indices) != 1:
            self._set_status("Selecione exatamente uma legenda para dividir.", ERROR)
            return
        index = indices[0]
        original = self.tool.cues[index]
        preview = " ".join(original.text.split())

        def confirm(text: str, position: int) -> str | None:
            try:
                new_cues = self.tool.split_at(index, text, position)
            except (ValueError, IndexError) as exc:
                return str(exc)
            self._dirty = True
            self._refresh(select=list(range(index, index + len(new_cues))))
            self._set_status("Legenda dividida.", SUCCESS)
            return None

        SplitDialog(self, preview, confirm)

    # ------------------------------------------------------------------
    def _refresh(self, select: list[int] | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for position, cue in enumerate(self.tool.cues):
            text = " ".join(cue.text.split())
            self.tree.insert(
                "", "end", iid=str(position),
                values=("☐", position + 1, srt_timestamp(cue.start),
                        srt_timestamp(cue.end), text),
            )
        if select:
            ids = [str(i) for i in select if 0 <= i < len(self.tool.cues)]
            self.tree.selection_set(ids)
            if ids:
                self.tree.see(ids[0])
        self._update_checks()
        self._update_summary()
        self._update_footer()

    def _on_select(self, _event=None) -> None:
        self._update_checks()
        self._update_summary()

    def _update_checks(self) -> None:
        selected = set(self.tree.selection())
        for iid in self.tree.get_children():
            values = list(self.tree.item(iid, "values"))
            glyph = "☑" if iid in selected else "☐"
            if values[0] != glyph:
                values[0] = glyph
                self.tree.item(iid, values=values)

    def _update_summary(self) -> None:
        indices = self._selected_indices()
        if not indices:
            self.sel_title.configure(text="Nenhuma legenda selecionada")
            self.sel_range.configure(text="—")
            self.sel_total.configure(text="00:00:00,000")
            return
        cues = [self.tool.cues[i] for i in indices]
        start = min(c.start for c in cues)
        end = max(c.end for c in cues)
        count = len(indices)
        plural = "legenda selecionada" if count == 1 else "legendas selecionadas"
        self.sel_title.configure(text=f"{count} {plural}")
        self.sel_range.configure(text=f"{srt_timestamp(start)} → {srt_timestamp(end)}")
        self.sel_total.configure(text=srt_timestamp(max(end - start, 0.0)))

    def _update_footer(self) -> None:
        total = len(self.tool.cues)
        if total == 0:
            self.count_label.configure(text="Nenhuma legenda carregada")
        else:
            self.count_label.configure(text=f"{total} legendas carregadas")

    def _set_status(self, text: str, color: str) -> None:
        self.status.configure(text=text, text_color=color)

    def _on_close(self) -> None:
        self.destroy()


class LegendAIApp(ctk.CTk, _DnDBase):
    """Janela principal."""

    WIDTH, HEIGHT = 1040, 740

    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title(APP_NAME)
        self._center_window()
        self._set_app_icon()
        self._dnd_ok = self._init_dnd()

        self.settings = Settings.load()
        self.audio_path: Path | None = None
        self.output_folder: Path | None = None
        self._busy = False
        self._aligner = None  # reutilizado entre gerações: carrega o modelo só uma vez

        self._progress_queue: queue.Queue[tuple[str, float]] = queue.Queue()
        self._log_queue: queue.Queue[str] = queue.Queue()
        self._log_window: LogWindow | None = None
        self._settings_window: SettingsWindow | None = None
        self._merge_split_window: MergeSplitWindow | None = None
        self._help_window: ctk.CTkToplevel | None = None
        self._log_buffer: list[str] = []

        self._setup_logging()
        self._build_layout()
        self.after(100, self._poll_queues)
        if not ffmpeg_available():
            self._set_status("FFmpeg não disponível. Reinstale o LegendAI.", ERROR)

    # ------------------------------------------------------------------
    def _center_window(self) -> None:
        x = (self.winfo_screenwidth() - self.WIDTH) // 2
        y = (self.winfo_screenheight() - self.HEIGHT) // 2
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        self.minsize(900, 660)

    def _set_app_icon(self) -> None:
        _apply_app_icon(self)

    def _setup_logging(self) -> None:
        log.setLevel(logging.INFO)
        log.addHandler(QueueLogHandler(self._log_queue))

    def _init_dnd(self) -> bool:
        """Carrega a extensão tkdnd; retorna False se indisponível."""
        if TkinterDnD is None:
            return False
        try:
            self.TkdndVersion = TkinterDnD._require(self)
            return True
        except Exception:  # noqa: BLE001 - sem tkdnd o app segue só-botão
            log.warning("Drag-and-drop indisponível (tkdnd não carregou).")
            return False

    # ------------------------------------------------------------------
    def _build_legacy_layout(self) -> None:
        self.configure(fg_color=BG)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True)

        # ---- Cabeçalho ----------------------------------------------------
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.pack(fill="x", padx=26, pady=(20, 8))
        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left")
        head_logo = _load_logo(42)
        if head_logo is not None:
            ctk.CTkLabel(brand, text="", image=head_logo).pack(side="left", padx=(0, 12))
        titles = ctk.CTkFrame(brand, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(
            titles, text=APP_NAME, anchor="w", text_color=TEXT,
            font=ctk.CTkFont(size=23, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            titles, text="Sincronize seu roteiro com a narração", anchor="w",
            text_color=MUTED, font=ctk.CTkFont(size=12),
        ).pack(anchor="w")

        ctk.CTkButton(
            header, text="⚙", width=42, height=42, corner_radius=11,
            fg_color=SURFACE, hover_color=SURFACE_2, text_color=MUTED,
            border_width=1, border_color=BORDER, command=self._open_settings,
        ).pack(side="right")
        ctk.CTkButton(
            header, text="💡  Ajuda", width=96, height=42, corner_radius=11,
            font=ctk.CTkFont(size=13), fg_color=SURFACE, hover_color=SURFACE_2,
            text_color=MUTED, border_width=1, border_color=BORDER,
            command=self._open_help,
        ).pack(side="right", padx=(0, 10))
        ctk.CTkButton(
            header, text="🔀  Merge & Split", width=170, height=42, corner_radius=11,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._open_merge_split,
        ).pack(side="right", padx=(0, 10))

        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=26, pady=(6, 22))

        # ---- Card: arquivo (compacto) -------------------------------------
        card_file = self._card(content, "Arquivo de áudio ou vídeo")
        card_file.pack(fill="x", pady=(0, 14))
        body = ctk.CTkFrame(card_file, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(8, 16))

        self.file_row = ctk.CTkFrame(
            body, fg_color=SURFACE_2, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        self.file_row.pack(side="left", fill="both", expand=True)
        drop_inner = ctk.CTkFrame(self.file_row, fg_color="transparent")
        drop_inner.pack(anchor="w", padx=16, pady=14)
        badge = ctk.CTkFrame(drop_inner, width=46, height=46, corner_radius=23,
                             fg_color=ACCENT)
        badge.pack(side="left", padx=(0, 14))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="🎵", font=ctk.CTkFont(size=18)).pack(expand=True)
        col = ctk.CTkFrame(drop_inner, fg_color="transparent")
        col.pack(side="left")
        drop_hint = "Arraste e solte seu arquivo aqui" if self._dnd_ok \
            else "Selecione seu arquivo de áudio"
        ctk.CTkLabel(col, text=drop_hint, text_color=MUTED, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(anchor="w")
        ctk.CTkButton(
            col, text="Selecionar arquivo", width=160, height=34, corner_radius=9,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._select_file,
        ).pack(anchor="w", pady=(8, 0))
        self._register_drop_target(self.file_row)

        info = ctk.CTkFrame(body, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=(18, 0))
        self.file_check = ctk.CTkLabel(
            info, text="", text_color=SUCCESS, anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.file_check.pack(anchor="w", pady=(4, 2))
        self.file_label = ctk.CTkLabel(
            info, text="Nenhum arquivo selecionado", text_color=MUTED,
            anchor="w", justify="left", wraplength=260, font=ctk.CTkFont(size=13),
        )
        self.file_label.pack(anchor="w")
        self.file_duration = ctk.CTkLabel(
            info, text="", text_color=MUTED, anchor="w", font=ctk.CTkFont(size=12),
        )
        self.file_duration.pack(anchor="w", pady=(6, 0))

        # ---- Card: roteiro -------------------------------------------------
        card_script = self._card(content, "Roteiro")
        card_script.pack(fill="both", expand=True, pady=(0, 16))
        self.script_box = ctk.CTkTextbox(
            card_script, fg_color=SURFACE_2, corner_radius=12, border_width=0,
            font=ctk.CTkFont(size=14), wrap="word",
        )
        self.script_box.pack(fill="both", expand=True, padx=18, pady=(12, 18))

        # ---- Ação principal + progresso -----------------------------------
        self.generate_button = ctk.CTkButton(
            content, text="✨   GERAR LEGENDA", height=54, corner_radius=14,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._on_generate,
        )
        self.generate_button.pack(fill="x")

        prow = ctk.CTkFrame(content, fg_color="transparent")
        prow.pack(fill="x", pady=(14, 8))
        self.progress = ctk.CTkProgressBar(
            prow, progress_color=ACCENT, fg_color=SURFACE_2, height=8, corner_radius=4,
        )
        self.progress.set(0)
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress_label = ctk.CTkLabel(
            prow, text="0%", text_color=MUTED, width=44, font=ctk.CTkFont(size=12),
        )
        self.progress_label.pack(side="right", padx=(12, 0))

        srow = ctk.CTkFrame(content, fg_color="transparent")
        srow.pack(fill="x")
        self.status_dot = ctk.CTkLabel(
            srow, text="●", text_color=SUCCESS, font=ctk.CTkFont(size=12),
        )
        self.status_dot.pack(side="left", padx=(0, 7))
        self.status_label = ctk.CTkLabel(
            srow, text="Pronto para gerar legendas!", text_color=MUTED, anchor="w",
        )
        self.status_label.pack(side="left")

        self.open_folder_button = ctk.CTkButton(
            content, text="📂  Abrir pasta", height=40, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=SUCCESS,
            text_color=SUCCESS, hover_color=ACCENT_SOFT,
            command=self._open_output_folder,
        )

    def _build_layout(self) -> None:
        """Workspace principal inspirado na linguagem visual do Focus HUB."""
        self.configure(fg_color=BG)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=18)

        header = ctk.CTkFrame(
            main, height=58, fg_color=SURFACE, corner_radius=16,
            border_width=1, border_color=BORDER,
        )
        header.pack(fill="x", pady=(0, 16))
        header.pack_propagate(False)

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left", padx=16, pady=10)
        head_logo = _load_logo(34)
        if head_logo is not None:
            ctk.CTkLabel(brand, text="", image=head_logo).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(
            brand, text=APP_NAME, text_color=TEXT,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")
        ctk.CTkLabel(
            brand, text="  /  sincronização local", text_color=MUTED,
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

        local_badge = ctk.CTkFrame(header, fg_color=ACCENT_SOFT, corner_radius=10)
        local_badge.pack(side="left", padx=(14, 0), pady=15)
        ctk.CTkLabel(
            local_badge, text="  ENGINE LOCAL  ", text_color=ACCENT,
            font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(pady=4)

        ctk.CTkButton(
            header, text="Configurações", width=118, height=34, corner_radius=10,
            fg_color="transparent", hover_color=SURFACE_2, text_color=MUTED,
            command=self._open_settings,
        ).pack(side="right", padx=(0, 10))
        ctk.CTkButton(
            header, text="Ajuda", width=68, height=34, corner_radius=10,
            fg_color="transparent", hover_color=SURFACE_2, text_color=MUTED,
            command=self._open_help,
        ).pack(side="right")
        ctk.CTkButton(
            header, text="Ajustar legendas", width=142, height=34, corner_radius=10,
            font=ctk.CTkFont(size=12, weight="bold"), fg_color=SURFACE_2,
            hover_color=ACCENT_SOFT, text_color=TEXT, command=self._open_merge_split,
        ).pack(side="right", padx=(0, 6))

        workspace = ctk.CTkFrame(main, fg_color="transparent")
        workspace.pack(fill="both", expand=True)
        editor = ctk.CTkFrame(workspace, fg_color="transparent")
        editor.pack(side="left", fill="both", expand=True, padx=(0, 14))
        sidebar = ctk.CTkFrame(workspace, width=254, fg_color="transparent")
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)

        intro = ctk.CTkFrame(editor, fg_color="transparent")
        intro.pack(fill="x", pady=(2, 14))
        ctk.CTkLabel(
            intro, text="Novo alinhamento", text_color=TEXT,
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            intro,
            text="Envie a narração e cole o roteiro final. O texto nunca é alterado.",
            text_color=MUTED, font=ctk.CTkFont(size=13),
        ).pack(anchor="w", pady=(3, 0))

        card_file = self._card(editor, "01  FONTE")
        card_file.pack(fill="x", pady=(0, 12))
        body = ctk.CTkFrame(card_file, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(10, 16))

        self.file_row = ctk.CTkFrame(
            body, height=94, fg_color=SURFACE_2, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        self.file_row.pack(fill="x")
        self.file_row.pack_propagate(False)
        drop_inner = ctk.CTkFrame(self.file_row, fg_color="transparent")
        drop_inner.pack(side="left", fill="y", padx=16)
        badge = ctk.CTkFrame(
            drop_inner, width=42, height=42, corner_radius=12, fg_color=ACCENT_SOFT,
        )
        badge.pack(side="left", padx=(0, 12), pady=26)
        badge.pack_propagate(False)
        ctk.CTkLabel(
            badge, text="AUDIO", text_color=ACCENT,
            font=ctk.CTkFont(size=9, weight="bold"),
        ).pack(expand=True)
        col = ctk.CTkFrame(drop_inner, fg_color="transparent")
        col.pack(side="left", pady=18)
        drop_hint = "Arraste o áudio aqui" if self._dnd_ok else "Selecione o áudio da narração"
        ctk.CTkLabel(
            col, text=drop_hint, text_color=TEXT, anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            col, text="MP3, WAV, M4A, AAC, FLAC ou OGG", text_color=MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", pady=(3, 0))
        ctk.CTkButton(
            self.file_row, text="Escolher arquivo", width=126, height=34, corner_radius=9,
            font=ctk.CTkFont(size=12, weight="bold"), fg_color=ACCENT,
            hover_color=ACCENT_HOVER, command=self._select_file,
        ).pack(side="right", padx=16, pady=30)
        self._register_drop_target(self.file_row)

        info = ctk.CTkFrame(card_file, fg_color="transparent")
        info.pack(fill="x", padx=18, pady=(0, 15))
        self.file_check = ctk.CTkLabel(
            info, text="", text_color=SUCCESS, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.file_check.pack(side="left")
        self.file_label = ctk.CTkLabel(
            info, text="Nenhum áudio selecionado", text_color=MUTED,
            anchor="w", justify="left", font=ctk.CTkFont(size=12),
        )
        self.file_label.pack(side="left", padx=(8, 0))
        self.file_duration = ctk.CTkLabel(
            info, text="", text_color=MUTED, anchor="e", font=ctk.CTkFont(size=12),
        )
        self.file_duration.pack(side="right")

        card_script = self._card(editor, "02  ROTEIRO FINAL")
        card_script.pack(fill="both", expand=True, pady=(0, 12))
        ctk.CTkLabel(
            card_script, text="Cole exatamente o texto que deve aparecer no vídeo.",
            text_color=MUTED, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=18, pady=(5, 8))
        self.script_box = ctk.CTkTextbox(
            card_script, fg_color=SURFACE_2, corner_radius=12, border_width=1,
            border_color=BORDER, font=ctk.CTkFont(size=14), wrap="word", text_color=TEXT,
        )
        self.script_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        action = ctk.CTkFrame(
            editor, fg_color=SURFACE, corner_radius=15, border_width=1, border_color=BORDER,
        )
        action.pack(fill="x")
        self.generate_button = ctk.CTkButton(
            action, text="GERAR LEGENDAS", width=204, height=46, corner_radius=11,
            font=ctk.CTkFont(size=14, weight="bold"), fg_color=ACCENT,
            hover_color=ACCENT_HOVER, command=self._on_generate,
        )
        self.generate_button.pack(side="left", padx=12, pady=12)

        status_area = ctk.CTkFrame(action, fg_color="transparent")
        status_area.pack(side="left", fill="x", expand=True, padx=(4, 12))
        srow = ctk.CTkFrame(status_area, fg_color="transparent")
        srow.pack(fill="x", pady=(12, 5))
        self.status_dot = ctk.CTkLabel(
            srow, text="●", text_color=SUCCESS, font=ctk.CTkFont(size=13),
        )
        self.status_dot.pack(side="left", padx=(0, 7))
        self.status_label = ctk.CTkLabel(
            srow, text="Pronto para criar suas legendas.", text_color=MUTED,
            anchor="w", font=ctk.CTkFont(size=12),
        )
        self.status_label.pack(side="left")

        prow = ctk.CTkFrame(status_area, fg_color="transparent")
        prow.pack(fill="x", pady=(0, 12))
        self.progress = ctk.CTkProgressBar(
            prow, progress_color=ACCENT, fg_color=SURFACE_2, height=8, corner_radius=4,
        )
        self.progress.set(0)
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress_label = ctk.CTkLabel(
            prow, text="0%", text_color=MUTED, width=44, font=ctk.CTkFont(size=12),
        )
        self.progress_label.pack(side="right", padx=(12, 0))

        self.open_folder_button = ctk.CTkButton(
            editor, text="Abrir pasta de saída", height=40, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=SUCCESS,
            text_color=SUCCESS, hover_color=ACCENT_SOFT, command=self._open_output_folder,
        )
        self._build_sidebar(sidebar)

    def _build_sidebar(self, sidebar: ctk.CTkFrame) -> None:
        flow = self._card(sidebar, "PIPELINE")
        flow.pack(fill="x", pady=(42, 12))
        steps = [
            ("01", "Áudio", "arquivo de origem"),
            ("02", "WhisperX", "alinhamento local"),
            ("03", "Legend Engine", "regras e exportação"),
        ]
        for index, title, subtitle in steps:
            row = ctk.CTkFrame(flow, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=8)
            number = ctk.CTkLabel(
                row, text=index, width=28, height=28, corner_radius=8,
                fg_color=ACCENT_SOFT, text_color=ACCENT,
                font=ctk.CTkFont(size=10, weight="bold"),
            )
            number.pack(side="left", padx=(0, 10))
            labels = ctk.CTkFrame(row, fg_color="transparent")
            labels.pack(side="left")
            ctk.CTkLabel(
                labels, text=title, text_color=TEXT, font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(anchor="w")
            ctk.CTkLabel(
                labels, text=subtitle, text_color=MUTED, font=ctk.CTkFont(size=10),
            ).pack(anchor="w")

        output = self._card(sidebar, "SAÍDA")
        output.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            output, text="Arquivos prontos para edição", text_color=MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=16, pady=(5, 10))
        chips = ctk.CTkFrame(output, fg_color="transparent")
        chips.pack(fill="x", padx=16, pady=(0, 16))
        for text in ("SRT", "ASS", "UTF-8"):
            ctk.CTkLabel(
                chips, text=f"  {text}  ", fg_color=SURFACE_2, text_color=TEXT,
                corner_radius=7, font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(side="left", padx=(0, 6))

        note = ctk.CTkFrame(sidebar, fg_color=ACCENT_SOFT, corner_radius=14)
        note.pack(fill="x")
        ctk.CTkLabel(
            note, text="Seu roteiro é a fonte da verdade.", text_color=ACCENT,
            font=ctk.CTkFont(size=11, weight="bold"), wraplength=190, justify="left",
        ).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            note, text="O modelo encontra apenas os tempos de cada palavra.",
            text_color=MUTED, font=ctk.CTkFont(size=10), wraplength=194, justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 12))

    def _build_layout(self) -> None:
        """Compositor único com hierarquia visual inspirada em Raycast e Linear."""
        self.configure(fg_color=BG)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=28, pady=(18, 22))
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, minsize=820)
        main.grid_columnconfigure(2, weight=1)
        main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(main, height=38, fg_color="transparent")
        header.grid(row=0, column=1, sticky="ew", pady=(0, 24))
        header.grid_propagate(False)
        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left")
        logo = _load_logo(27)
        if logo is not None:
            ctk.CTkLabel(brand, text="", image=logo).pack(side="left", padx=(0, 9))
        ctk.CTkLabel(brand, text=APP_NAME, text_color=TEXT,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")

        ctk.CTkButton(
            header, text="Configurações", width=108, height=30, corner_radius=8,
            fg_color="transparent", hover_color=SURFACE, text_color=MUTED,
            command=self._open_settings,
        ).pack(side="right")
        ctk.CTkButton(
            header, text="Ajuda", width=56, height=30, corner_radius=8,
            fg_color="transparent", hover_color=SURFACE, text_color=MUTED,
            command=self._open_help,
        ).pack(side="right", padx=(0, 4))
        ctk.CTkButton(
            header, text="Ajustar legendas", width=136, height=30, corner_radius=8,
            fg_color=SURFACE, hover_color=SURFACE_2, text_color=TEXT,
            font=ctk.CTkFont(size=12, weight="bold"), command=self._open_merge_split,
        ).pack(side="right", padx=(0, 8))

        workspace = ctk.CTkFrame(
            main, fg_color=SURFACE, corner_radius=18,
            border_width=1, border_color=BORDER,
        )
        workspace.grid(row=1, column=1, sticky="nsew")
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_rowconfigure(3, weight=1)

        audio = ctk.CTkFrame(workspace, fg_color="transparent")
        audio.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 0))
        audio.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(audio, text="Áudio", text_color=TEXT,
                     font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(audio, text="Narração que será sincronizada.", text_color=MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=1, sticky="e")

        self.file_row = ctk.CTkFrame(
            audio, height=76, fg_color=SURFACE_2, corner_radius=11,
            border_width=1, border_color=BORDER,
        )
        self.file_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.file_row.grid_columnconfigure(0, weight=1)
        self.file_row.grid_propagate(False)
        hint = "Arraste seu áudio aqui" if self._dnd_ok else "Selecione o áudio da narração"
        copy = ctk.CTkFrame(self.file_row, fg_color="transparent")
        copy.grid(row=0, column=0, sticky="w", padx=16, pady=16)
        ctk.CTkLabel(copy, text=hint, text_color=TEXT,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(copy, text="MP3, WAV, M4A, AAC, FLAC ou OGG", text_color=MUTED,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(3, 0))
        ctk.CTkButton(
            self.file_row, text="Escolher arquivo", width=122, height=34, corner_radius=8,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"), command=self._select_file,
        ).grid(row=0, column=1, padx=14, pady=20)
        self._register_drop_target(self.file_row)

        file_info = ctk.CTkFrame(audio, fg_color="transparent")
        file_info.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        file_info.grid_columnconfigure(1, weight=1)
        self.file_check = ctk.CTkLabel(file_info, text="", text_color=SUCCESS,
                                       font=ctk.CTkFont(size=11, weight="bold"))
        self.file_check.grid(row=0, column=0, sticky="w")
        self.file_label = ctk.CTkLabel(file_info, text="Nenhum arquivo selecionado", text_color=MUTED,
                                       anchor="w", font=ctk.CTkFont(size=11))
        self.file_label.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.file_duration = ctk.CTkLabel(file_info, text="", text_color=MUTED,
                                          font=ctk.CTkFont(size=11))
        self.file_duration.grid(row=0, column=2, sticky="e")

        ctk.CTkFrame(workspace, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=24, pady=(20, 18)
        )

        script = ctk.CTkFrame(workspace, fg_color="transparent")
        script.grid(row=2, column=0, sticky="ew", padx=24)
        script.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(script, text="Roteiro", text_color=TEXT,
                     font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(script, text="O texto será mantido exatamente como você escreveu.",
                     text_color=MUTED, font=ctk.CTkFont(size=11)).grid(row=0, column=1, sticky="e")

        self.script_box = ctk.CTkTextbox(
            workspace, fg_color=SURFACE_2, corner_radius=11, border_width=1,
            border_color=BORDER, text_color=TEXT, font=ctk.CTkFont(size=14), wrap="word",
        )
        self.script_box.grid(row=3, column=0, sticky="nsew", padx=24, pady=(10, 18))

        footer = ctk.CTkFrame(workspace, height=64, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 14))
        footer.grid_columnconfigure(0, weight=1)
        self.status_dot = ctk.CTkLabel(footer, text="●", text_color=SUCCESS,
                                       font=ctk.CTkFont(size=10))
        self.status_dot.grid(row=0, column=0, sticky="w", padx=(2, 7), pady=14)
        self.status_label = ctk.CTkLabel(footer, text="Pronto para gerar.", text_color=MUTED,
                                         font=ctk.CTkFont(size=12))
        self.status_label.grid(row=0, column=0, sticky="w", padx=(17, 0), pady=14)
        self.progress = ctk.CTkProgressBar(footer, width=112, height=5, corner_radius=3,
                                           progress_color=ACCENT, fg_color=SURFACE_2)
        self.progress.set(0)
        self.progress.grid(row=0, column=1, padx=(0, 8), pady=14)
        self.progress.grid_remove()
        self.progress_label = ctk.CTkLabel(footer, text="", text_color=FAINT,
                                           font=ctk.CTkFont(size=11))
        self.progress_label.grid(row=0, column=2, padx=(0, 12), pady=14)
        self.progress_label.grid_remove()
        self.generate_button = ctk.CTkButton(
            footer, text="Gerar legendas", width=148, height=38, corner_radius=9,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"), command=self._on_generate,
        )
        self.generate_button.grid(row=0, column=3, padx=(0, 10), pady=12)
        self.open_folder_button = ctk.CTkButton(
            footer, text="Abrir pasta", width=104, height=36, corner_radius=9,
            fg_color="transparent", border_width=1, border_color=SUCCESS,
            text_color=SUCCESS, hover_color=ACCENT_SOFT, command=self._open_output_folder,
        )
        self.open_folder_button.grid(row=0, column=4, pady=13)
        self.open_folder_button.grid_remove()

    def _build_process_panel(self, parent: ctk.CTkFrame) -> None:
        flow = self._card(parent, "PROCESSO")
        flow.pack(fill="x", pady=(42, 12))
        for number, title, detail in (
            ("01", "Áudio", "arquivo de origem"),
            ("02", "WhisperX", "alinhamento temporal"),
            ("03", "Legend Engine", "regras e exportação"),
        ):
            row = ctk.CTkFrame(flow, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=8)
            ctk.CTkLabel(
                row, text=number, width=28, height=28, corner_radius=8,
                fg_color=ACCENT_SOFT, text_color=ACCENT,
                font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(side="left", padx=(0, 10))
            copy = ctk.CTkFrame(row, fg_color="transparent")
            copy.pack(side="left")
            ctk.CTkLabel(copy, text=title, text_color=TEXT,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(copy, text=detail, text_color=MUTED,
                         font=ctk.CTkFont(size=10)).pack(anchor="w")

        output = self._card(parent, "SAÍDA")
        output.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(output, text="Arquivos prontos para edição", text_color=MUTED,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16, pady=(5, 10))
        formats = ctk.CTkFrame(output, fg_color="transparent")
        formats.pack(fill="x", padx=16, pady=(0, 16))
        for name in ("SRT", "ASS", "UTF-8"):
            ctk.CTkLabel(formats, text=f"  {name}  ", fg_color=SURFACE_2, text_color=TEXT,
                         corner_radius=7, font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(0, 6))

        note = ctk.CTkFrame(parent, fg_color=ACCENT_SOFT, corner_radius=14)
        note.pack(fill="x")
        ctk.CTkLabel(note, text="Seu roteiro é a fonte da verdade.", text_color=ACCENT,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(note, text="O modelo usa apenas os tempos de cada palavra.",
                     text_color=MUTED, wraplength=194, justify="left",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", padx=14, pady=(0, 12))

    @staticmethod
    def _workspace_card(parent, title: str) -> ctk.CTkFrame:
        """Cria um cartão para conteúdos posicionados com grid."""
        card = ctk.CTkFrame(
            parent, fg_color=SURFACE, corner_radius=16,
            border_width=1, border_color=BORDER,
        )
        ctk.CTkLabel(
            card, text=title, anchor="w", text_color=MUTED,
            font=ctk.CTkFont(size=10, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(15, 0))
        return card

    @staticmethod
    def _card(parent, title: str) -> ctk.CTkFrame:
        """Cria um cartão com título e devolve o frame para preencher o corpo."""
        card = ctk.CTkFrame(
            parent, fg_color=SURFACE, corner_radius=16,
            border_width=1, border_color=BORDER,
        )
        ctk.CTkLabel(
            card, text=title, anchor="w", text_color=MUTED,
            font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(fill="x", padx=18, pady=(15, 0))
        return card

    def _open_help(self) -> None:
        if getattr(self, "_help_window", None) is not None and self._help_window.winfo_exists():
            self._help_window.focus()
            return
        win = ctk.CTkToplevel(self)
        win.title(f"{APP_NAME} — Ajuda")
        win.geometry("480x460")
        win.configure(fg_color=BG)
        _apply_app_icon(win)
        self._help_window = win
        ctk.CTkLabel(
            win, text="Como usar o LegendAI", text_color=TEXT,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(20, 8))
        tips = ctk.CTkTextbox(
            win, fg_color=SURFACE, corner_radius=12, border_width=1,
            border_color=BORDER, font=ctk.CTkFont(size=13), wrap="word",
        )
        tips.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        tips.insert("1.0", (
            "1. Selecione (ou arraste) o áudio da narração.\n\n"
            "2. Cole o roteiro no campo 'Roteiro'.\n\n"
            "3. Clique em GERAR LEGENDA — o LegendAI sincroniza o texto com a "
            "fala e salva o SRT/ASS ao lado do áudio.\n\n"
            "4. Use MERGE & SPLIT para ajustar as legendas:\n"
            "   • Merge (Ctrl+Shift+M): junta 2+ legendas seguidas.\n"
            "   • Split (Ctrl+Shift+S): divide uma legenda no cursor.\n\n"
            "5. Salve e reimporte o SRT no DaVinci Resolve."
        ))
        tips.configure(state="disabled")

    # ------------------------------------------------------------------
    def _select_file(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Selecione o áudio da narração",
            filetypes=[("Áudio", "*.mp3 *.wav *.m4a *.aac *.flac"), ("Todos", "*.*")],
        )
        if chosen:
            self._set_audio(Path(chosen))

    def _set_audio(self, path: Path) -> None:
        """Valida e registra o áudio escolhido (por botão ou arraste)."""
        if path.suffix.lower() not in AUDIO_EXTS:
            self._set_status(f"Formato de áudio não suportado: {path.suffix}", ERROR)
            return
        if not path.exists():
            self._set_status("Arquivo não encontrado.", ERROR)
            return
        self.audio_path = path
        self.file_check.configure(text="✓  Arquivo selecionado")
        self.file_label.configure(text=path.name, text_color=TEXT)
        seconds = audio_duration_seconds(path)
        self.file_duration.configure(
            text=f"Duração: {_fmt_duration(seconds)}" if seconds else ""
        )
        self._set_status("Pronto para gerar legendas!", MUTED)

    # ------------------------------------------------------------------
    def _register_drop_target(self, widget: ctk.CTkBaseClass) -> None:
        if not self._dnd_ok:
            return
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", self._on_drop)
        widget.dnd_bind("<<DropEnter>>", lambda _e: self._highlight_drop(True))
        widget.dnd_bind("<<DropLeave>>", lambda _e: self._highlight_drop(False))

    def _highlight_drop(self, active: bool) -> None:
        self.file_row.configure(border_color=ACCENT if active else BORDER)

    def _on_drop(self, event) -> None:
        self._highlight_drop(False)
        paths = self._split_drop_paths(event.data)
        if paths:
            self._set_audio(Path(paths[0]))

    @staticmethod
    def _split_drop_paths(data: str) -> list[str]:
        """Separa os caminhos de um evento de drop do tkdnd.

        Não usa tk.splitlist: no Windows as barras invertidas seriam tratadas
        como escapes Tcl e corromperiam o caminho. O tkdnd envolve em chaves
        apenas os caminhos que contêm espaços; vários arquivos vêm separados
        por espaço.
        """
        paths: list[str] = []
        data = data.strip()
        while data:
            if data[0] == "{":
                end = data.find("}")
                if end == -1:
                    paths.append(data[1:])
                    break
                paths.append(data[1:end])
                data = data[end + 1:].strip()
            else:
                parts = data.split(None, 1)
                paths.append(parts[0])
                data = parts[1].strip() if len(parts) > 1 else ""
        return paths

    def _on_generate(self) -> None:
        if self._busy:
            return
        if self.audio_path is None:
            self._set_status("Selecione um arquivo MP3 primeiro.", ERROR)
            return
        script = self.script_box.get("1.0", "end").strip()
        if not script:
            self._set_status("Cole o roteiro antes de gerar.", ERROR)
            return
        self._busy = True
        self.generate_button.configure(state="disabled", text="Gerando...")
        self.open_folder_button.grid_remove()
        self.progress.set(0.02)
        threading.Thread(
            target=self._worker, args=(self.audio_path, script), daemon=True
        ).start()

    def _worker(self, audio_path: Path, script: str) -> None:
        from .aligner import WhisperXAligner
        from .pipeline import generate_subtitles

        def progress(message: str, fraction: float) -> None:
            log.info(message)
            self._progress_queue.put((message, fraction))

        try:
            if self._aligner is None or self._aligner.language != self.settings.language:
                self._aligner = WhisperXAligner(language=self.settings.language)
            result = generate_subtitles(
                audio_path, script, self.settings, progress, aligner=self._aligner
            )
            self._progress_queue.put(("__done__", 1.0))
            self.output_folder = audio_path.parent
            if self.settings.open_folder and result.files:
                open_folder(result.files[0])
        except Exception as exc:  # noqa: BLE001 - erro exibido ao usuário
            log.exception("Falha ao gerar legenda")
            self._progress_queue.put((f"__error__{exc}", 0.0))

    # ------------------------------------------------------------------
    def _poll_queues(self) -> None:
        while not self._log_queue.empty():
            line = self._log_queue.get_nowait()
            self._log_buffer.append(line)
            if self._log_window is not None and self._log_window.winfo_exists():
                self._log_window.append(line)
        while not self._progress_queue.empty():
            message, fraction = self._progress_queue.get_nowait()
            self._handle_progress(message, fraction)
        self.after(100, self._poll_queues)

    def _handle_progress(self, message: str, fraction: float) -> None:
        if message == "__done__":
            self._finish(success=True)
        elif message.startswith("__error__"):
            self._finish(success=False, error=message.removeprefix("__error__"))
        else:
            self._set_progress(fraction)
            self._set_status(message, MUTED)

    def _finish(self, success: bool, error: str = "") -> None:
        self._busy = False
        self.generate_button.configure(state="normal", text="Gerar legendas")
        if success:
            self._set_progress(1.0)
            self._set_status("Legenda gerada com sucesso.", SUCCESS)
            self.open_folder_button.grid()
        else:
            self._set_progress(0)
            self._set_status(f"Erro: {error}", ERROR)

    def _set_progress(self, fraction: float) -> None:
        self.progress.grid()
        self.progress_label.grid()
        self.progress.set(fraction)
        self.progress_label.configure(text=f"{fraction:.0%}")

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.configure(text=text, text_color=color)
        self.status_dot.configure(text_color=ERROR if color == ERROR else SUCCESS)

    # ------------------------------------------------------------------
    def _open_output_folder(self) -> None:
        if self.output_folder is not None:
            open_folder(self.output_folder)

    def _open_log(self) -> None:
        if self._log_window is None or not self._log_window.winfo_exists():
            self._log_window = LogWindow(self)
            for line in self._log_buffer:
                self._log_window.append(line)
        self._log_window.focus()

    def _open_settings(self) -> None:
        if self._settings_window is None or not self._settings_window.winfo_exists():
            self._settings_window = SettingsWindow(self, self.settings)
        self._settings_window.focus()

    def _open_merge_split(self) -> None:
        if self._merge_split_window is None or not self._merge_split_window.winfo_exists():
            self._merge_split_window = MergeSplitWindow(self, self.settings)
        self._merge_split_window.focus()
