"""Ponto de entrada do LegendAI."""

import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

if getattr(sys, "frozen", False):
    bundle_root = Path(sys._MEIPASS)
    tcl_root = bundle_root / "_tcl_data"
    tk_root = bundle_root / "_tk_data"
else:
    python_root = Path(sys.base_prefix)
    project_root = Path(__file__).resolve().parent
    dev_runtime = project_root / "dist" / "LegendAI" / "_internal"
    bundled_tcl = dev_runtime / "_tcl_data"
    bundled_tk = dev_runtime / "_tk_data"

    # Reaproveita o runtime validado do app empacotado durante o desenvolvimento.
    if bundled_tcl.exists() and bundled_tk.exists():
        tcl_root = bundled_tcl
        tk_root = bundled_tk
        os.environ["PATH"] = f"{dev_runtime}{os.pathsep}{os.environ.get('PATH', '')}"
    else:
        tcl_root = python_root / "tcl" / "tcl8.6"
        tk_root = python_root / "tcl" / "tk8.6"

if tcl_root.exists() and tk_root.exists():
    os.environ["TCL_LIBRARY"] = str(tcl_root)
    os.environ["TK_LIBRARY"] = str(tk_root)

from legendai.utils import prepare_runtime_environment

prepare_runtime_environment()


def _selftest(argv: list[str]) -> int:
    """Executa o pipeline headless: LegendAI.exe --selftest <mp3> <roteiro>.

    Serve para validar a geração de legenda dentro do executável congelado,
    sem abrir a interface. Retorna 0 em caso de sucesso.
    """
    from pathlib import Path

    from legendai.pipeline import generate_subtitles
    from legendai.settings import Settings

    audio, script = Path(argv[0]), argv[1]
    result = generate_subtitles(
        audio, script, Settings(), lambda m, f: print(f"[{f:.0%}] {m}")
    )
    print(f"OK: {len(result.cues)} legendas geradas")
    for path in result.files:
        print(f"  -> {path}")
    return 0


def main() -> None:
    if "--selftest" in sys.argv:
        idx = sys.argv.index("--selftest")
        raise SystemExit(_selftest(sys.argv[idx + 1: idx + 3]))
    from legendai.ui import LegendAIApp

    app = LegendAIApp()
    app.mainloop()


if __name__ == "__main__":
    main()
