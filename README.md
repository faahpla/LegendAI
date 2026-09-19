# LegendAI

Aplicativo Windows para sincronizar um roteiro já pronto com uma narração.
O roteiro é sempre a fonte da verdade: o WhisperX é usado apenas para obter os
tempos das palavras, nunca para substituir, corrigir ou transcrever o texto.

## O que entrega

- Entrada de áudio e roteiro final.
- Alinhamento temporal local com WhisperX. O modelo é baixado na primeira
  geração e guardado em `%APPDATA%/LegendAI/models`; depois disso o aplicativo
  trabalha sem internet.
- Legend Engine com regras de leitura, duração, margens e ausência de
  sobreposição.
- Exportação SRT e ASS em UTF-8.
- Editor de SRT com operações de mesclar e dividir.
- Interface Electron para Windows, com arrastar e soltar.

## Desenvolvimento

Pré-requisitos: Python 3.12, Node.js 20+, FFmpeg e as dependências descritas
em `requirements.txt`.

```bat
npm ci
python -m pip install -r requirements.txt pyinstaller
run_electron_dev.bat
```

## Atualizações automáticas

As versões instaladas consultam o GitHub Releases ao abrir. Quando houver uma
versão mais nova, ela é baixada em segundo plano e instalada quando o aplicativo
for fechado.

O repositório de releases deve permanecer público para que os usuários recebam
atualizações sem precisar de token do GitHub.

## Publicar uma nova versão

1. Atualize o código e valide com `npm run typecheck` e
   `python tests\test_engine.py`.
2. Crie a versão e a tag:

   ```bat
   npm version patch
   git push --follow-tags
   ```

3. A ação `Publicar LegendAI` no GitHub compila o motor, gera o instalador
   Windows e publica a Release. Os aplicativos instalados recebem a nova versão
   automaticamente.

Use `minor` ou `major` no lugar de `patch` quando apropriado.

## Estrutura

```text
src/                 Interface Electron/React
legendai/            Motor Python, alinhamento e exportação
assets/              Logo e ícone do aplicativo
.github/workflows/   Publicação automática de releases
```
