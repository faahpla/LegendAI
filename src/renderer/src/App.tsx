import { useEffect, useMemo, useState } from 'react'
import { HelpCircle, Maximize2, Minus, Settings2, Sparkles, X } from 'lucide-react'
import logoUrl from './assets/legendai-logo.png'
import { CreateView } from '@/features/create-view'
import { EditorView } from '@/features/editor-view'
import { SettingsView } from '@/features/settings-view'
import { request } from '@/lib/backend'
import type { Cue, EngineSettings, GenerationJob, View } from '@/types'
import { fallbackSettings } from '@/types'

type OpenSrtResult = { path: string; cues: Cue[] }
type CuesResult = { cues: Cue[] }

export default function App(): JSX.Element {
  const [view, setView] = useState<View>('create')
  const [audioPath, setAudioPath] = useState<string | null>(null)
  const [script, setScript] = useState('')
  const [job, setJob] = useState<GenerationJob | null>(null)
  const [createNotice, setCreateNotice] = useState('Pronto para começar.')
  const [settings, setSettings] = useState<EngineSettings>(fallbackSettings)
  const [settingsNotice, setSettingsNotice] = useState('Carregando configurações…')
  const [savingSettings, setSavingSettings] = useState(false)
  const [srtPath, setSrtPath] = useState<string | null>(null)
  const [cues, setCues] = useState<Cue[]>([])
  const [selected, setSelected] = useState<number[]>([])
  const [splitPosition, setSplitPosition] = useState<number | null>(null)
  const [editorNotice, setEditorNotice] = useState('Abra um SRT para começar.')
  const [editorBusy, setEditorBusy] = useState(false)

  const audioName = useMemo(() => fileName(audioPath), [audioPath])

  useEffect(() => {
    let cancelled = false
    let attempts = 0
    const loadSettings = async (): Promise<void> => {
      try {
        const loaded = await request<EngineSettings>('/settings')
        if (cancelled) return
        setSettings(loaded)
        setSettingsNotice('Configurações salvas localmente.')
      } catch (error) {
        attempts += 1
        if (attempts < 7 && !cancelled) {
          window.setTimeout(() => void loadSettings(), 300)
          return
        }
        if (!cancelled) setSettingsNotice(messageFrom(error))
      }
    }
    void loadSettings()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return
    let cancelled = false
    const poll = async (): Promise<void> => {
      try {
        const current = await request<GenerationJob>(`/jobs/${job.id}`)
        if (cancelled) return
        setJob(current)
        setCreateNotice(current.error ?? current.message)
      } catch (error) {
        if (!cancelled) {
          setJob(null)
          setCreateNotice(messageFrom(error))
        }
      }
    }
    const timer = window.setInterval(() => void poll(), 550)
    void poll()
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [job?.id, job?.status])

  async function selectAudio(): Promise<void> {
    const path = await window.legendAI.pickAudio()
    if (!path) return
    setAudioPath(path)
    setCreateNotice('Áudio selecionado.')
  }

  function dropAudio(event: React.DragEvent<HTMLElement>): void {
    event.preventDefault()
    event.stopPropagation()
    const file = event.dataTransfer.files[0] as File & { path?: string }
    if (!file) return
    try {
      const path = file.path || window.legendAI.filePath(file)
      if (!path) throw new Error('Caminho do arquivo não disponível.')
      setAudioPath(path)
      setCreateNotice('Áudio selecionado.')
    } catch (error) {
      setCreateNotice(`Não foi possível importar o áudio: ${messageFrom(error)}`)
    }
  }

  async function generate(): Promise<void> {
    if (job && ['queued', 'running'].includes(job.status)) return
    if (!audioPath) return setCreateNotice('Selecione um áudio para continuar.')
    if (!script.trim()) return setCreateNotice('Cole o roteiro antes de gerar.')
    try {
      const started = await request<GenerationJob>('/generate', 'POST', {
        audio_path: audioPath,
        script
      })
      setJob(started)
      setCreateNotice(started.message)
    } catch (error) {
      setCreateNotice(messageFrom(error))
    }
  }

  async function saveSettings(): Promise<void> {
    setSavingSettings(true)
    try {
      const saved = await request<EngineSettings>('/settings', 'POST', settings)
      setSettings(saved)
      setSettingsNotice('Configurações salvas.')
    } catch (error) {
      setSettingsNotice(messageFrom(error))
    } finally {
      setSavingSettings(false)
    }
  }

  async function openSrt(pathOverride?: string): Promise<void> {
    const path = pathOverride ?? await window.legendAI.pickSrt()
    if (!path) return
    setEditorBusy(true)
    try {
      const result = await request<OpenSrtResult>('/srt/open', 'POST', { path })
      setSrtPath(result.path)
      setCues(result.cues)
      setSelected([])
      setSplitPosition(null)
      setEditorNotice(`${result.cues.length} legendas carregadas.`)
    } catch (error) {
      setEditorNotice(messageFrom(error))
    } finally {
      setEditorBusy(false)
    }
  }

  function dropSrt(event: React.DragEvent<HTMLElement>): void {
    event.preventDefault()
    event.stopPropagation()
    const file = event.dataTransfer.files[0] as File & { path?: string }
    if (!file) return
    try {
      const path = file.path || window.legendAI.filePath(file)
      if (!path.toLowerCase().endsWith('.srt')) {
        setEditorNotice('Arraste um arquivo .srt para editar.')
        return
      }
      void openSrt(path)
    } catch (error) {
      setEditorNotice(`Não foi possível abrir o SRT: ${messageFrom(error)}`)
    }
  }

  function toggleCue(index: number): void {
    setSelected((current) => current.includes(index)
      ? current.filter((item) => item !== index)
      : [...current, index].sort((left, right) => left - right))
    setSplitPosition(null)
  }

  async function mergeCues(): Promise<void> {
    if (selected.length < 2) return
    setEditorBusy(true)
    try {
      const result = await request<CuesResult>('/srt/merge', 'POST', { cues, indices: selected })
      setCues(result.cues)
      setSelected([])
      setSplitPosition(null)
      setEditorNotice('Legendas mescladas.')
    } catch (error) {
      setEditorNotice(messageFrom(error))
    } finally {
      setEditorBusy(false)
    }
  }

  async function splitCue(): Promise<void> {
    if (selected.length !== 1) return
    const position = splitPosition
    const cue = cues[selected[0]]
    if (position === null || position < 1 || position >= cue.text.length) {
      setEditorNotice('Clique entre duas palavras antes de dividir.')
      return
    }
    setEditorBusy(true)
    try {
      const result = await request<CuesResult>('/srt/split', 'POST', {
        cues,
        index: selected[0],
        text: cue.text,
        position
      })
      setCues(result.cues)
      setSelected([])
      setSplitPosition(null)
      setEditorNotice('Legenda dividida.')
    } catch (error) {
      setEditorNotice(messageFrom(error))
    } finally {
      setEditorBusy(false)
    }
  }

  async function saveSrt(): Promise<void> {
    if (!srtPath) return
    const path = await window.legendAI.saveSrt(srtPath)
    if (!path) return
    setEditorBusy(true)
    try {
      await request<{ path: string }>('/srt/save', 'POST', { path, cues })
      setSrtPath(path)
      setEditorNotice('Legenda salva.')
    } catch (error) {
      setEditorNotice(messageFrom(error))
    } finally {
      setEditorBusy(false)
    }
  }

  return (
    <div className="app-background flex h-full flex-col overflow-hidden">
      <TitleBar />
      <header className="no-drag mx-auto flex w-full max-w-[980px] items-center justify-between px-8 pb-3 pt-1">
        <button onClick={() => setView('create')} className="flex items-center gap-2.5 rounded-lg text-left">
          <img src={logoUrl} alt="LegendAI" className="h-8 w-8 object-contain drop-shadow-[0_0_9px_hsl(var(--primary)/.3)]" />
          <span className="text-sm font-semibold tracking-tight">LegendAI</span>
        </button>
        <nav className="flex items-center gap-1">
          <NavButton active={view === 'create'} onClick={() => setView('create')}>Criar</NavButton>
          <NavButton active={view === 'editor'} onClick={() => setView('editor')}>Ajustar</NavButton>
          <button onClick={() => setCreateNotice('Selecione um áudio, cole o roteiro e gere suas legendas.')} className="icon-button" title="Ajuda"><HelpCircle className="h-4 w-4" /></button>
          <button className="icon-button" title="Configurações" onClick={() => setView('settings')}><Settings2 className="h-4 w-4" /></button>
        </nav>
      </header>

      <main className="no-drag min-h-0 flex-1 overflow-y-auto px-8 pb-5">
        {view === 'create' && <CreateView audioName={audioName} script={script} status={createNotice} progress={job?.status === 'completed' ? 1 : job?.progress ?? null} isGenerating={Boolean(job && ['queued', 'running'].includes(job.status))} outputFolder={job?.status === 'completed' ? job.output_folder : null} onChooseAudio={() => void selectAudio()} onDropAudio={dropAudio} onScriptChange={setScript} onGenerate={() => void generate()} onOpenOutput={() => { if (job?.output_folder) void window.legendAI.openPath(job.output_folder) }} />}
        {view === 'editor' && <EditorView path={srtPath} cues={cues} selected={selected} splitPosition={splitPosition} notice={editorNotice} busy={editorBusy} onOpen={() => void openSrt()} onDropSrt={dropSrt} onSave={() => void saveSrt()} onToggle={toggleCue} onSplitPositionChange={setSplitPosition} onMerge={() => void mergeCues()} onSplit={() => void splitCue()} />}
        {view === 'settings' && <SettingsView settings={settings} notice={settingsNotice} saving={savingSettings} onChange={setSettings} onSave={() => void saveSettings()} />}
      </main>
    </div>
  )
}

function TitleBar(): JSX.Element {
  return <div className="drag flex h-10 shrink-0 items-center justify-between px-3"><div className="flex items-center gap-2 text-xs font-medium text-muted-foreground/80"><span className="h-2 w-2 rounded-full bg-primary shadow-glow" />LegendAI</div><div className="no-drag flex items-center gap-1"><button className="icon-button" onClick={() => window.legendAI.minimize()}><Minus className="h-3.5 w-3.5" /></button><button className="icon-button" onClick={() => window.legendAI.toggleMaximize()}><Maximize2 className="h-3.5 w-3.5" /></button><button className="icon-button hover:!bg-destructive hover:!text-white" onClick={() => window.legendAI.close()}><X className="h-4 w-4" /></button></div></div>
}

function NavButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }): JSX.Element {
  return <button onClick={onClick} className={['rounded-lg px-3 py-1.5 text-xs font-medium transition-colors', active ? 'bg-surface-elevated text-foreground shadow-soft' : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground'].join(' ')}>{children}</button>
}

function fileName(path: string | null): string | undefined {
  return path?.split(/[/\\]/).pop()
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : 'Ocorreu um erro inesperado.'
}
