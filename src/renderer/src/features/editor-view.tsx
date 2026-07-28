import type { DragEvent } from 'react'
import { Check, ChevronRight, FolderOpen, Merge, Save, Scissors } from 'lucide-react'
import type { Cue } from '@/types'

type EditorViewProps = {
  path: string | null
  cues: Cue[]
  selected: number[]
  splitPosition: number | null
  notice: string
  busy: boolean
  onOpen: () => void
  onDropSrt: (event: DragEvent<HTMLElement>) => void
  onSave: () => void
  onToggle: (index: number) => void
  onSplitPositionChange: (position: number | null) => void
  onMerge: () => void
  onSplit: () => void
}

export function EditorView({
  path,
  cues,
  selected,
  splitPosition,
  notice,
  busy,
  onOpen,
  onDropSrt,
  onSave,
  onToggle,
  onSplitPositionChange,
  onMerge,
  onSplit
}: EditorViewProps): JSX.Element {
  const canSplit = selected.length === 1
    && splitPosition !== null
    && splitPosition > 0
    && splitPosition < (cues[selected[0]]?.text.length ?? 0)
  const editorHint = selected.length === 1
    ? canSplit ? 'Ponto de corte selecionado.' : 'Clique entre as palavras para posicionar o corte.'
    : notice

  return (
    <section
      className="mx-auto w-full max-w-[980px] py-5"
      onDragEnter={(event) => event.preventDefault()}
      onDragOver={(event) => event.preventDefault()}
      onDrop={onDropSrt}
    >
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Ajustar legendas</h1>
          <p className="mt-1 text-sm text-muted-foreground">Mescle ou divida blocos sem sair do LegendAI.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onOpen} className="inline-flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-elevated px-3 text-sm font-medium transition-colors hover:bg-surface-hover">
            <FolderOpen className="h-3.5 w-3.5" /> Abrir SRT
          </button>
          {path && <button onClick={onSave} disabled={busy} className="inline-flex h-9 items-center gap-2 rounded-xl bg-primary px-3 text-sm font-medium text-primary-foreground shadow-glow disabled:opacity-60"><Save className="h-3.5 w-3.5" /> Salvar</button>}
        </div>
      </div>

      {!path ? (
        <EmptyEditor onOpen={onOpen} />
      ) : (
        <div className="panel overflow-hidden rounded-3xl">
          <div className="flex items-center justify-between border-b border-border/70 px-6 py-4">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{fileName(path)}</p>
              <p className="mt-1 text-xs text-muted-foreground">{cues.length} legendas carregadas</p>
            </div>
            <span className="rounded-full border border-border bg-surface-elevated px-2.5 py-1 text-xs text-muted-foreground">{selected.length} selecionada{selected.length === 1 ? '' : 's'}</span>
          </div>
          <div className="max-h-[420px] overflow-y-auto p-2 scrollbar-thin">
            {cues.map((cue, index) => (
              <div
                key={`${cue.start}-${cue.end}-${index}`}
                onClick={() => onToggle(index)}
                role="button"
                tabIndex={0}
                className={['flex w-full items-center gap-4 rounded-xl px-3 py-3 text-left transition-colors', selected.includes(index) ? 'bg-primary/10 text-foreground' : 'hover:bg-surface-hover'].join(' ')}
              >
                <span className={['flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors', selected.includes(index) ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-surface-elevated'].join(' ')}>
                  {selected.includes(index) && <Check className="h-3.5 w-3.5" />}
                </span>
                <span className="w-28 shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">{formatTime(cue.start)} — {formatTime(cue.end)}</span>
                {selected.length === 1 && selected[0] === index ? (
                  <input
                    readOnly
                    value={cue.text}
                    aria-label="Clique entre as palavras para posicionar o corte"
                    onClick={(event) => event.stopPropagation()}
                    onSelect={(event) => onSplitPositionChange(event.currentTarget.selectionStart)}
                    onKeyUp={(event) => onSplitPositionChange(event.currentTarget.selectionStart)}
                    className="min-w-0 flex-1 cursor-text bg-transparent text-sm outline-none selection:bg-primary/35"
                  />
                ) : <span className="min-w-0 flex-1 truncate text-sm">{cue.text}</span>}
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between gap-4 border-t border-border/70 px-6 py-4">
            <span className="truncate text-xs text-muted-foreground">{editorHint}</span>
            <div className="flex shrink-0 gap-2">
              <button onClick={onMerge} disabled={busy || selected.length < 2} className="inline-flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-elevated px-3 text-sm font-medium transition-colors hover:bg-surface-hover disabled:opacity-40"><Merge className="h-3.5 w-3.5" /> Mesclar</button>
              <button onClick={onSplit} disabled={busy || !canSplit} className="inline-flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-elevated px-3 text-sm font-medium transition-colors hover:bg-surface-hover disabled:opacity-40"><Scissors className="h-3.5 w-3.5" /> Dividir</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function EmptyEditor({ onOpen }: { onOpen: () => void }): JSX.Element {
  return <div className="panel flex min-h-[320px] flex-col items-center justify-center rounded-3xl p-8 text-center"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><Scissors className="h-5 w-5" /></span><h2 className="mt-4 text-base font-semibold tracking-tight">Abra uma legenda SRT</h2><p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">Arraste um SRT para esta área ou abra um arquivo. Depois selecione linhas para mesclar ou dividir.</p><button onClick={onOpen} className="mt-6 inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground shadow-glow"><FolderOpen className="h-4 w-4" /> Abrir arquivo SRT</button></div>
}

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.round(seconds * 1000))
  const hours = Math.floor(total / 3_600_000)
  const minutes = Math.floor((total % 3_600_000) / 60_000)
  const secs = Math.floor((total % 60_000) / 1000)
  const milliseconds = total % 1000
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(milliseconds).padStart(3, '0')}`
}

function fileName(path: string): string {
  return path.split(/[/\\]/).pop() ?? path
}
