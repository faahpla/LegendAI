import { useEffect, useRef, type DragEvent, type MutableRefObject } from 'react'
import { Check, ChevronRight, FolderOpen, Merge, Redo2, Save, Scissors, Undo2 } from 'lucide-react'
import type { Cue } from '@/types'

type EditorViewProps = {
  path: string | null
  cues: Cue[]
  selected: number[]
  splitPosition: number | null
  notice: string
  busy: boolean
  canUndo: boolean
  canRedo: boolean
  shortcutMerge: string
  shortcutSplit: string
  onOpen: () => void
  onDropSrt: (event: DragEvent<HTMLElement>) => void
  onSave: () => void
  onSaveAs: () => void
  onToggle: (index: number, extend?: boolean) => void
  onSplitPositionChange: (position: number | null) => void
  onTextChange: (index: number, text: string) => void
  onTextCommit: () => void
  editingIndex: number | null
  onStartEditing: (index: number) => void
  scrollRef: MutableRefObject<number>
  onMerge: () => void
  onSplit: () => void
  onUndo: () => void
  onRedo: () => void
}

export function EditorView({
  path,
  cues,
  selected,
  splitPosition,
  notice,
  busy,
  canUndo,
  canRedo,
  shortcutMerge,
  shortcutSplit,
  onOpen,
  onDropSrt,
  onSave,
  onSaveAs,
  onToggle,
  onSplitPositionChange,
  onTextChange,
  onTextCommit,
  editingIndex,
  onStartEditing,
  scrollRef,
  onMerge,
  onSplit,
  onUndo,
  onRedo
}: EditorViewProps): JSX.Element {
  // A aba é desmontada ao trocar de view; devolvemos a lista para onde estava.
  const listRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const list = listRef.current
    if (list) list.scrollTop = scrollRef.current
  }, [scrollRef])

  const splitTarget = selected.length === 1 ? cues[selected[0]]?.text ?? '' : ''
  // As duas metades precisam ter texto após aparar espaços — mesma regra do motor.
  const canSplit = splitPosition !== null
    && Boolean(splitTarget.slice(0, splitPosition).trim())
    && Boolean(splitTarget.slice(splitPosition).trim())
  const editorHint = editingIndex !== null
    ? canSplit ? 'Ponto de corte selecionado.' : 'Clique entre as palavras para posicionar o corte.'
    : selected.length === 1
    ? 'Clique no texto para editar ou marcar onde dividir.'
    : selected.length > 1
      ? `${selected.length} legendas em sequência — prontas para mesclar.`
      : notice || 'Clique para selecionar; Shift+clique marca um intervalo.'

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
          {path && (
            <div className="mr-1 flex items-center gap-1">
              <button onClick={onUndo} disabled={!canUndo} title="Desfazer (Ctrl+Z)" className="icon-button disabled:opacity-30"><Undo2 className="h-4 w-4" /></button>
              <button onClick={onRedo} disabled={!canRedo} title="Refazer (Ctrl+Y)" className="icon-button disabled:opacity-30"><Redo2 className="h-4 w-4" /></button>
            </div>
          )}
          <button onClick={onOpen} className="inline-flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-elevated px-3 text-sm font-medium transition-colors hover:bg-surface-hover">
            <FolderOpen className="h-3.5 w-3.5" /> Abrir SRT
          </button>
          {path && (
            <>
              <button onClick={onSaveAs} disabled={busy} title="Salvar em outro arquivo" className="inline-flex h-9 items-center rounded-xl border border-border bg-surface-elevated px-3 text-sm font-medium transition-colors hover:bg-surface-hover disabled:opacity-60">
                Salvar como…
              </button>
              <button onClick={onSave} disabled={busy} title={`Sobrescrever ${fileName(path)} (Ctrl+S)`} className="inline-flex h-9 items-center gap-2 rounded-xl bg-primary px-3 text-sm font-medium text-primary-foreground shadow-glow disabled:opacity-60">
                <Save className="h-3.5 w-3.5" /> Salvar
              </button>
            </>
          )}
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
          <div
            ref={listRef}
            onScroll={(event) => { scrollRef.current = event.currentTarget.scrollTop }}
            className="max-h-[420px] overflow-y-auto p-2 scrollbar-thin"
          >
            {cues.map((cue, index) => (
              <div key={`${cue.start}-${cue.end}-${index}`}>
              <div
                onClick={(event) => onToggle(index, event.shiftKey)}
                role="button"
                tabIndex={0}
                className={['flex w-full items-center gap-4 rounded-xl px-3 py-3 text-left transition-colors', selected.includes(index) ? 'bg-primary/10 text-foreground' : 'hover:bg-surface-hover'].join(' ')}
              >
                <span className={['flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors', selected.includes(index) ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-surface-elevated'].join(' ')}>
                  {selected.includes(index) && <Check className="h-3.5 w-3.5" />}
                </span>
                <span className="w-28 shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">{formatTime(cue.start)} — {formatTime(cue.end)}</span>
                {editingIndex === index ? (
                  <input
                    autoFocus
                    value={cue.text}
                    aria-label="Edite o texto ou clique entre as palavras para posicionar o corte"
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => {
                      onTextChange(index, event.target.value)
                      onSplitPositionChange(event.target.selectionStart)
                    }}
                    onBlur={onTextCommit}
                    onSelect={(event) => onSplitPositionChange(event.currentTarget.selectionStart)}
                    onKeyUp={(event) => onSplitPositionChange(event.currentTarget.selectionStart)}
                    className="min-w-0 flex-1 cursor-text rounded-md bg-surface-elevated/60 px-2 py-1 text-sm outline-none ring-1 ring-inset ring-border focus:ring-primary/60 selection:bg-primary/35"
                  />
                ) : (
                  <span
                    onClick={(event) => { event.stopPropagation(); onStartEditing(index) }}
                    title="Clique no texto para editar"
                    className="min-w-0 flex-1 cursor-text truncate rounded-md px-2 py-1 text-sm transition-colors hover:bg-surface-elevated/70 hover:ring-1 hover:ring-inset hover:ring-border"
                  >
                    {cue.text}
                  </span>
                )}
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </div>
              {editingIndex === index && <SplitPreview cue={cue} position={splitPosition} />}
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between gap-4 border-t border-border/70 px-6 py-4">
            <span className="truncate text-xs text-muted-foreground">{editorHint}</span>
            <div className="flex shrink-0 gap-2">
              <button onClick={onMerge} disabled={busy || selected.length < 2} title={`Mesclar (${shortcutMerge})`} className="inline-flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-elevated px-3 text-sm font-medium transition-colors hover:bg-surface-hover disabled:opacity-40"><Merge className="h-3.5 w-3.5" /> Mesclar</button>
              <button onClick={onSplit} disabled={busy || !canSplit} title={`Dividir (${shortcutSplit})`} className="inline-flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-elevated px-3 text-sm font-medium transition-colors hover:bg-surface-hover disabled:opacity-40"><Scissors className="h-3.5 w-3.5" /> Dividir</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

/**
 * Mostra onde o corte vai cair antes de confirmar: o texto com um marcador na
 * posição do cursor e as duas legendas que sairão, já com os tempos.
 *
 * O rateio do tempo espelha `CaptionMergeSplit.distribute` no motor —
 * proporcional aos caracteres que não são espaço.
 */
function SplitPreview({ cue, position }: { cue: Cue; position: number | null }): JSX.Element | null {
  if (position === null) return null

  const before = cue.text.slice(0, position)
  const after = cue.text.slice(position)
  const left = before.trim()
  const right = after.trim()

  if (!left || !right) {
    return (
      <div className="mx-3 mb-2 rounded-lg border border-dashed border-border bg-surface-elevated/40 px-3 py-2">
        <p className="text-[11px] text-muted-foreground">
          Posicione o cursor entre duas palavras — os dois lados precisam ter texto.
        </p>
      </div>
    )
  }

  const weight = (text: string): number => Math.max(text.replace(/\s/g, '').length, 1)
  const share = weight(left) / (weight(left) + weight(right))
  const middle = cue.start + Math.max(cue.end - cue.start, 0) * share

  return (
    <div className="mx-3 mb-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2.5">
      <p className="font-mono text-xs leading-5">
        <span className="text-foreground">{before}</span>
        <span className="mx-px inline-block w-0.5 self-stretch bg-primary align-middle" style={{ height: '1.05em' }} />
        <span className="text-foreground">{after}</span>
      </p>
      <div className="mt-2 grid gap-1">
        <PreviewPart order={1} text={left} start={cue.start} end={middle} />
        <PreviewPart order={2} text={right} start={middle} end={cue.end} />
      </div>
    </div>
  )
}

function PreviewPart({ order, text, start, end }: { order: number; text: string; start: number; end: number }): JSX.Element {
  return (
    <div className="flex items-center gap-2.5 text-[11px]">
      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded bg-primary/20 font-semibold text-primary">{order}</span>
      <span className="shrink-0 font-mono tabular-nums text-muted-foreground">{formatTime(start)} — {formatTime(end)}</span>
      <span className="min-w-0 truncate text-muted-foreground">{text}</span>
    </div>
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
