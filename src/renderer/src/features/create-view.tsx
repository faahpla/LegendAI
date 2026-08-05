import type { DragEvent } from 'react'
import { ChevronRight, FileAudio, FileText, FolderOpen, LoaderCircle, Sparkles, UploadCloud, X } from 'lucide-react'

type CreateViewProps = {
  audioName?: string
  script: string
  status: string
  progress: number | null
  isGenerating: boolean
  isCancelling: boolean
  outputFolder: string | null
  onChooseAudio: () => void
  onDropAudio: (event: DragEvent<HTMLElement>) => void
  onScriptChange: (value: string) => void
  onGenerate: () => void
  onCancel: () => void
  onOpenOutput: () => void
}

export function CreateView({
  audioName,
  script,
  status,
  progress,
  isGenerating,
  isCancelling,
  outputFolder,
  onChooseAudio,
  onDropAudio,
  onScriptChange,
  onGenerate,
  onCancel,
  onOpenOutput
}: CreateViewProps): JSX.Element {
  return (
    <section
      className="mx-auto flex h-full w-full max-w-[760px] items-center py-2"
      onDragEnter={(event) => event.preventDefault()}
      onDragOver={(event) => event.preventDefault()}
      onDrop={onDropAudio}
    >
      <div className="panel w-full overflow-hidden rounded-3xl">
        <div className="border-b border-border/70 px-6 py-4">
          <p className="text-[13px] font-semibold tracking-tight">Sincronizar roteiro</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Seu texto é a fonte da verdade. O LegendAI encontra apenas o tempo de cada palavra.
          </p>
        </div>

        <div className="space-y-5 px-6 py-5">
          <FieldLabel
            icon={<FileAudio className="h-4 w-4" />}
            title="Narração"
            description="Escolha o áudio que será usado como referência."
          />
          <button
            onClick={onChooseAudio}
            onDragEnter={(event) => event.preventDefault()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={onDropAudio}
            className="group flex w-full items-center gap-4 rounded-2xl border border-dashed border-border bg-surface-elevated/45 px-5 py-4 text-left transition-all duration-150 hover:border-primary/45 hover:bg-surface-hover"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary transition-transform duration-150 group-hover:scale-105">
              <UploadCloud className="h-5 w-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-foreground">
                {audioName ?? 'Arraste o áudio ou clique para selecionar'}
              </span>
              <span className="mt-1 block text-xs text-muted-foreground">
                {audioName ? 'Arquivo pronto para sincronização' : 'MP3, WAV, M4A, AAC, FLAC ou OGG'}
              </span>
            </span>
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
          </button>

          <div className="h-px bg-border/70" />

          <div>
            <FieldLabel
              icon={<FileText className="h-4 w-4" />}
              title="Roteiro"
              description="Cole exatamente o texto que deve aparecer no vídeo."
            />
            <textarea
              value={script}
              onChange={(event) => onScriptChange(event.target.value)}
              placeholder="Cole seu roteiro aqui…"
              className="control scrollbar-thin mt-3 min-h-[150px] w-full resize-none px-4 py-3 leading-6 placeholder:text-muted-foreground/55"
            />
          </div>
        </div>

        <div className="flex items-center justify-between gap-5 border-t border-border/70 px-6 py-3">
          <div className="min-w-0">
            <p className="truncate text-xs text-muted-foreground">{status}</p>
            {progress !== null && (
              <div className="mt-2 h-1.5 w-40 overflow-hidden rounded-full bg-muted/70">
                <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${progress * 100}%` }} />
              </div>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {outputFolder && !isGenerating && (
              <button onClick={onOpenOutput} className="inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-surface-elevated px-3 text-xs font-medium transition-colors hover:bg-surface-hover">
                <FolderOpen className="h-3.5 w-3.5" /> Abrir pasta
              </button>
            )}
            {isGenerating && (
              <button
                onClick={onCancel}
                disabled={isCancelling}
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-surface-elevated px-3 text-xs font-medium transition-colors hover:border-destructive/60 hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
              >
                <X className="h-3.5 w-3.5" /> {isCancelling ? 'Cancelando…' : 'Cancelar'}
              </button>
            )}
            <button
              onClick={onGenerate}
              disabled={isGenerating}
              className="inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground shadow-glow transition-all duration-150 hover:brightness-110 active:scale-[.98] disabled:cursor-wait disabled:opacity-60"
            >
              {isGenerating ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              {isGenerating ? 'Gerando…' : 'Gerar legendas'}
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}

function FieldLabel({ icon, title, description }: { icon: JSX.Element; title: string; description: string }): JSX.Element {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-elevated text-muted-foreground">{icon}</span>
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  )
}
