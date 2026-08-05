import { Clock, FileAudio, FolderOpen, Trash2 } from 'lucide-react'
import type { HistoryEntry } from '@/types'

type HistoryViewProps = {
  entries: HistoryEntry[]
  onOpenFolder: (path: string) => void
  onClear: () => void
}

export function HistoryView({ entries, onOpenFolder, onClear }: HistoryViewProps): JSX.Element {
  return (
    <section className="mx-auto w-full max-w-[980px] py-5">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Histórico</h1>
          <p className="mt-1 text-sm text-muted-foreground">As últimas legendas que você gerou neste computador.</p>
        </div>
        {entries.length > 0 && (
          <button onClick={onClear} className="inline-flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-elevated px-3 text-sm font-medium transition-colors hover:bg-surface-hover">
            <Trash2 className="h-3.5 w-3.5" /> Limpar
          </button>
        )}
      </div>

      {entries.length === 0 ? (
        <div className="panel flex min-h-[280px] flex-col items-center justify-center rounded-3xl p-8 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><Clock className="h-5 w-5" /></span>
          <h2 className="mt-4 text-base font-semibold tracking-tight">Nada por aqui ainda</h2>
          <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">Assim que você gerar sua primeira legenda, ela aparece nesta lista com atalho para a pasta de saída.</p>
        </div>
      ) : (
        <div className="panel divide-y divide-border/70 overflow-hidden rounded-3xl">
          {entries.map((entry) => (
            <div key={entry.id} className="flex items-center gap-4 px-6 py-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <FileAudio className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{entry.audio_name}</p>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">{entry.script_preview}</p>
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground/80">
                  <span>{formatDate(entry.created_at)}</span>
                  <span>·</span>
                  <span>{entry.cue_count} legendas</span>
                  <span>·</span>
                  <span>{formatDuration(entry.duration)}</span>
                  {entry.confidence !== null && (
                    <>
                      <span>·</span>
                      <span>confiança {Math.round(entry.confidence * 100)}%</span>
                    </>
                  )}
                </p>
              </div>
              <button
                onClick={() => onOpenFolder(entry.output_folder)}
                title="Abrir pasta"
                className="inline-flex h-9 shrink-0 items-center gap-2 rounded-xl border border-border bg-surface-elevated px-3 text-xs font-medium transition-colors hover:bg-surface-hover"
              >
                <FolderOpen className="h-3.5 w-3.5" /> Abrir
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '—'
  const total = Math.round(seconds)
  const minutes = Math.floor(total / 60)
  return `${String(minutes).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
