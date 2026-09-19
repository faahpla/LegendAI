# LegendAI

Sincroniza um roteiro já pronto com uma narração. Exporta SRT e ASS em UTF-8,
com editor de mesclar e dividir legendas.

## Regra central

**O roteiro é sempre a fonte da verdade.** O WhisperX é usado apenas para obter
os tempos das palavras — nunca para substituir, corrigir ou transcrever o texto.

**O modelo não mora no instalador.** São 1,2 GB de wav2vec2 que chegam na
primeira geração e ficam em `%APPDATA%/LegendAI/models/<idioma>`, regravados em
float16 — metade do disco. O float16 é do arquivo, não da conta: o
`from_pretrained` monta tudo em float32 na memória, e é isso que mantém o
alinhamento rodando na CPU, onde meia precisão tem operação faltando.

**O artigo manda no corte.** Artigo, preposição e contração nunca fecham uma
legenda: descem junto com a palavra que apresentam ("Quatro | dos guardas",
nunca "Quatro dos | guardas"). A regra vence o limite de caracteres, como já
acontecia com a palavra longa demais. A lista vive em `DEFAULT_LINKING_WORDS`.

## Layout

Dois lados no mesmo repo:

| pasta | o que é |
|---|---|
| `legendai/` | motor Python: alinhamento, regras e exportação |
| `legendai/model_store.py` | busca o modelo de alinhamento na 1ª geração |
| `src/main`, `src/preload`, `src/renderer/src` | app Electron |
| `engine_entry.py` | entrada do motor empacotado pelo PyInstaller |
| `tests/` | `test_engine.py`, `test_engine_options.py`, `test_merge_split.py` |

## Comandos

```bash
npm run dev                         # app inteiro, sobe o motor junto
.venv\Scripts\python.exe -m legendai.server --port 8765   # só o motor
npm run typecheck
npm run build:engine                # PyInstaller (LegendAIEngine.spec)
npm run pack:win                    # instalador NSIS
```

## Armadilha do torch — leia antes de mexer no requirements

O `whisperx` puxa o `pyannote-audio`, que fixa `torch 2.8.0` e reinstala a build
**CPU** por cima da CUDA. Não dá erro: só fica lento demais. E
`pip install torch==2.8.0` **não conserta** — o pip aceita a build CPU como já
satisfeita, porque a versão base é a mesma. A correção é desinstalar e pinar a
variante local:

```bash
.venv\Scripts\python.exe -m pip uninstall -y torch torchaudio torchvision
.venv\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cu128 torch==2.8.0+cu128 torchaudio==2.8.0+cu128 torchvision==0.23.0+cu128
```

Confira sempre depois:

```bash
.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Estado bom (09/09/2026): `2.8.0+cu128`, CUDA True, RTX 3060.
