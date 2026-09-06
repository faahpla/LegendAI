import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Clock, Download, HelpCircle, Maximize2, Minus, Settings2, X } from 'lucide-react'
import logoUrl from './assets/legendai-logo.png'
import { CreateView } from '@/features/create-view'
import { EditorView } from '@/features/editor-view'
import { HelpView } from '@/features/help-view'
import { HistoryView } from '@/features/history-view'
import { SettingsView } from '@/features/settings-view'
import { request } from '@/lib/backend'
import type { Cue, EngineSettings, GenerationJob, HistoryEntry, UpdateInfo, View } from '@/types'
import { fallbackSettings } from '@/types'

type OpenSrtResult = { path: string; cues: Cue[] }
type CuesResult = { cues: Cue[] }

/** Mesmas extensões oferecidas pelo seletor de arquivos do processo principal. */
const AUDIO_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg']

export default function App(): JSX.Element {
  const [view, setView] = useState<View>('create')
  const [audioPath, setAudioPath] = useState<string | null>(null)
  const [script, setScript] = useState('')
  const [job, setJob] = useState<GenerationJob | null>(null)
  const [createNotice, setCreateNotice] = useState('Pronto para começar.')
  const [settings, setSettings] = useState<EngineSettings>(fallbackSettings)
  const [settingsNotice, setSettingsNotice] = useState('Carregando configurações…')
  const [savingSettings, setSavingSettings] = useState(false)
  // Enquanto o disco não foi lido, `settings` é só o fallback: salvar aqui
  // apagaria as preferências reais do usuário.
  const [settingsLoaded, setSettingsLoaded] = useState(false)
  const [srtPath, setSrtPath] = useState<string | null>(null)
  const [cues, setCues] = useState<Cue[]>([])
  const [selected, setSelected] = useState<number[]>([])
  const [splitPosition, setSplitPosition] = useState<number | null>(null)
  const [editorNotice, setEditorNotice] = useState('Abra um SRT para começar.')
  const [editorBusy, setEditorBusy] = useState(false)
  // Pilhas de desfazer/refazer do editor: cada entrada é um retrato das legendas.
  const [past, setPast] = useState<Cue[][]>([])
  const [future, setFuture] = useState<Cue[][]>([])
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [update, setUpdate] = useState<UpdateInfo>({ status: 'idle' })
  const [appVersion, setAppVersion] = useState('—')
  const [engineVersion, setEngineVersion] = useState('—')
  // Retrato das legendas antes da sessão de edição de texto em andamento.
  const editAnchorRef = useRef<Cue[] | null>(null)
  // Linha cujo texto está aberto para edição (só ao clicar no próprio texto).
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  // Rolagem da lista guardada fora do estado: a aba é desmontada ao trocar de
  // view, e usar estado aqui provocaria re-render a cada evento de scroll.
  const editorScrollRef = useRef(0)
  // Incrementa a cada SRT aberto: é o sinal para a lista voltar ao topo, já
  // que trocar de arquivo não remonta o componente.
  const [loadToken, setLoadToken] = useState(0)
  // Geração já levada para o editor, para não reabrir a cada sondagem do job.
  const autoOpenedJobRef = useRef<string | null>(null)

  const audioName = useMemo(() => fileName(audioPath), [audioPath])
  const isGenerating = Boolean(job && ['queued', 'running'].includes(job.status))
  // A geração pode exportar SRT e ASS; para o editor só o SRT interessa.
  const generatedSrt = useMemo(
    () => (job?.status === 'completed'
      ? job.files.find((file) => file.toLowerCase().endsWith('.srt')) ?? null
      : null),
    [job?.status, job?.files]
  )

  // O processo principal já segura a requisição até o motor responder, então
  // aqui basta uma tentativa — o que chegar é o estado real do disco.
  useEffect(() => {
    let cancelled = false
    const loadSettings = async (): Promise<void> => {
      try {
        const loaded = await request<EngineSettings>('/settings')
        if (cancelled) return
        setSettings(loaded)
        setSettingsLoaded(true)
        setSettingsNotice('Configurações salvas localmente.')
      } catch (error) {
        if (!cancelled) setSettingsNotice(messageFrom(error))
      }
    }
    void loadSettings()
    return () => { cancelled = true }
  }, [])

  // Versão do app (Electron) e do motor (Python), exibidas na Ajuda.
  useEffect(() => {
    void window.legendAI.appVersion().then(setAppVersion).catch(() => undefined)
    void request<{ version: string }>('/version')
      .then((data) => setEngineVersion(data.version))
      .catch(() => undefined)
  }, [])

  // Estado do auto-update: pega o atual e escuta as mudanças.
  useEffect(() => {
    void window.legendAI.currentUpdate<UpdateInfo>().then(setUpdate).catch(() => undefined)
    return window.legendAI.onUpdateState((state) => setUpdate(state as UpdateInfo))
  }, [])

  const loadHistory = useCallback(async (): Promise<void> => {
    try {
      const data = await request<{ entries: HistoryEntry[] }>('/history')
      setHistory(data.entries)
    } catch {
      // histórico é acessório: silenciar falha de leitura
    }
  }, [])

  useEffect(() => {
    void loadHistory()
  }, [loadHistory])

  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return
    let cancelled = false
    const poll = async (): Promise<void> => {
      try {
        const current = await request<GenerationJob>(`/jobs/${job.id}`)
        if (cancelled) return
        setJob(current)
        setCreateNotice(current.error ?? current.message)
        if (current.status === 'completed') void loadHistory()
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
      // O backend só confere se o arquivo existe; sem esta validação um vídeo
      // ou texto solto viraria uma geração que falha lá no fundo do alinhador.
      if (!AUDIO_EXTENSIONS.some((extension) => path.toLowerCase().endsWith(extension))) {
        setCreateNotice(`Formato não suportado. Use ${AUDIO_EXTENSIONS.join(', ')}.`)
        return
      }
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

  // Terminou de gerar: leva direto para o editor com o arquivo já carregado.
  useEffect(() => {
    if (!job || job.status !== 'completed' || !generatedSrt) return
    if (autoOpenedJobRef.current === job.id) return
    autoOpenedJobRef.current = job.id
    void adjustGenerated()
  }, [job?.id, job?.status, generatedSrt])

  /** Abre a legenda recém-gerada na aba Ajustar, sem procurar arquivo. */
  async function adjustGenerated(): Promise<void> {
    if (!generatedSrt) return
    await openSrt(generatedSrt)
    setView('editor')
  }

  async function cancelGeneration(): Promise<void> {
    if (!job) return
    try {
      setJob(await request<GenerationJob>('/jobs/cancel', 'POST', { id: job.id }))
      setCreateNotice('Cancelando a geração...')
    } catch (error) {
      setCreateNotice(messageFrom(error))
    }
  }

  async function clearHistory(): Promise<void> {
    try {
      const data = await request<{ entries: HistoryEntry[] }>('/history/clear', 'POST', {})
      setHistory(data.entries)
    } catch (error) {
      setCreateNotice(messageFrom(error))
    }
  }

  function pushHistory(snapshot: Cue[]): void {
    setPast((stack) => [...stack.slice(-49), snapshot])
    setFuture([])
  }

  /** Aplica um novo conjunto de legendas guardando o anterior para o Ctrl+Z. */
  function commitCues(next: Cue[], notice: string): void {
    pushHistory(cues)
    setCues(next)
    setSelected([])
    setSplitPosition(null)
    setEditingIndex(null)
    setEditorNotice(notice)
  }

  /**
   * Edição do texto de uma legenda. O retrato anterior é guardado uma única vez
   * por sessão de edição, para o Ctrl+Z desfazer a frase inteira e não letra
   * por letra; a sessão fecha quando o campo perde o foco.
   */
  function changeCueText(index: number, text: string): void {
    if (editAnchorRef.current === null) editAnchorRef.current = cues
    setCues((current) => current.map((cue, position) =>
      position === index ? { ...cue, text } : cue))
  }

  function commitCueText(): void {
    const snapshot = editAnchorRef.current
    editAnchorRef.current = null
    if (snapshot && snapshot !== cues) {
      pushHistory(snapshot)
      setEditorNotice('Texto da legenda atualizado.')
    }
  }

  /** Abre o texto para edição — disparado ao clicar sobre o próprio texto. */
  function startEditingCue(index: number): void {
    setSelected([index])
    setEditingIndex(index)
    setSplitPosition(null)
  }

  function stopEditingCue(): void {
    commitCueText()
    setEditingIndex(null)
  }

  function undo(): void {
    // Ctrl+Z durante a digitação deve desfazer a edição de texto em curso.
    commitCueText()
    setPast((stack) => {
      if (stack.length === 0) return stack
      const previous = stack[stack.length - 1]
      setFuture((forward) => [cues, ...forward])
      setCues(previous)
      setSelected([])
      setSplitPosition(null)
      setEditorNotice('Alteração desfeita.')
      return stack.slice(0, -1)
    })
  }

  function redo(): void {
    setFuture((stack) => {
      if (stack.length === 0) return stack
      const [next, ...rest] = stack
      setPast((backward) => [...backward, cues])
      setCues(next)
      setSelected([])
      setSplitPosition(null)
      setEditorNotice('Alteração refeita.')
      return rest
    })
  }

  async function saveSettings(): Promise<void> {
    if (!settingsLoaded) {
      setSettingsNotice('Aguarde o motor terminar de carregar antes de salvar.')
      return
    }
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
      setPast([])
      setFuture([])
      setEditingIndex(null)
      editAnchorRef.current = null
      setLoadToken((value) => value + 1)
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

  /**
   * Alterna a seleção mantendo-a sempre contígua — mesclar só aceita legendas
   * consecutivas, então nem deixamos o usuário montar um conjunto inválido.
   *
   * - Shift+clique: seleciona o intervalo inteiro a partir da âncora.
   * - Clique vizinho ao bloco atual: estende o bloco.
   * - Clique nas bordas do bloco: encolhe.
   * - Clique longe (ou no meio do bloco): recomeça a seleção ali.
   */
  function toggleCue(index: number, extend = false): void {
    // Trocar de linha desmonta o campo de edição sem garantia de `blur`;
    // fechamos a sessão aqui para o Ctrl+Z não perder o retrato anterior.
    commitCueText()
    setEditingIndex(null)
    setSelected((current) => {
      if (extend && current.length > 0) {
        const anchor = current[0]
        const [low, high] = anchor <= index ? [anchor, index] : [index, anchor]
        return Array.from({ length: high - low + 1 }, (_, offset) => low + offset)
      }
      if (current.length === 0) return [index]
      const first = current[0]
      const last = current[current.length - 1]
      if (index === first && current.length === 1) return []
      if (index === first) return current.slice(1)
      if (index === last) return current.slice(0, -1)
      if (index === first - 1 || index === last + 1) {
        return [...current, index].sort((left, right) => left - right)
      }
      return [index]
    })
    setSplitPosition(null)
  }

  async function mergeCues(): Promise<void> {
    if (selected.length < 2) return
    commitCueText()
    setEditorBusy(true)
    try {
      const result = await request<CuesResult>('/srt/merge', 'POST', { cues, indices: selected })
      commitCues(result.cues, 'Legendas mescladas.')
    } catch (error) {
      setEditorNotice(messageFrom(error))
    } finally {
      setEditorBusy(false)
    }
  }

  async function splitCue(): Promise<void> {
    if (selected.length !== 1) return
    commitCueText()
    const position = splitPosition
    const cue = cues[selected[0]]
    // Espelha a regra do motor: as duas metades precisam sobrar com texto real,
    // senão um corte dentro de um espaço passaria daqui e quebraria no backend.
    if (position === null || !cue.text.slice(0, position).trim() || !cue.text.slice(position).trim()) {
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
      commitCues(result.cues, 'Legenda dividida.')
    } catch (error) {
      setEditorNotice(messageFrom(error))
    } finally {
      setEditorBusy(false)
    }
  }

  /** Grava direto no arquivo aberto, sem diálogo — comportamento de Ctrl+S. */
  async function saveSrt(): Promise<void> {
    if (!srtPath) return
    stopEditingCue()
    await writeSrt(srtPath, `Salvo em ${fileName(srtPath)}.`)
  }

  /** Escolhe outro destino, preservando o arquivo original. */
  async function saveSrtAs(): Promise<void> {
    if (!srtPath) return
    stopEditingCue()
    const path = await window.legendAI.saveSrt(srtPath)
    if (!path) return
    await writeSrt(path, `Salvo em ${fileName(path)}.`)
  }

  async function writeSrt(path: string, notice: string): Promise<void> {
    setEditorBusy(true)
    try {
      await request<{ path: string }>('/srt/save', 'POST', { path, cues })
      setSrtPath(path)
      setEditorNotice(notice)
    } catch (error) {
      setEditorNotice(messageFrom(error))
    } finally {
      setEditorBusy(false)
    }
  }

  // Os atalhos leem as ações por ref para não capturarem estado velho — os
  // handlers são recriados a cada render, o listener é registrado uma vez.
  const actionsRef = useRef({ undo, redo, mergeCues, splitCue, saveSrt, openSrt, stopEditingCue })
  actionsRef.current = { undo, redo, mergeCues, splitCue, saveSrt, openSrt, stopEditingCue }

  useEffect(() => {
    if (view !== 'editor') return undefined
    const handler = (event: KeyboardEvent): void => {
      const target = event.target as HTMLElement | null
      const typing = target?.tagName === 'TEXTAREA'
        || (target?.tagName === 'INPUT' && (target as HTMLInputElement).type !== 'button')
      const actions = actionsRef.current
      const combo = (key: string): boolean =>
        (event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === key

      if (combo('z') && !event.shiftKey) {
        event.preventDefault()
        actions.undo()
      } else if (combo('y') || (combo('z') && event.shiftKey)) {
        event.preventDefault()
        actions.redo()
      } else if (combo('s')) {
        event.preventDefault()
        void actions.saveSrt()
      } else if (combo('o')) {
        event.preventDefault()
        void actions.openSrt()
      } else if (event.key === 'Escape') {
        actions.stopEditingCue()
        setSelected([])
        setSplitPosition(null)
      } else if (matchesShortcut(event, settings.shortcut_merge)) {
        event.preventDefault()
        void actions.mergeCues()
      } else if (matchesShortcut(event, settings.shortcut_split)) {
        // O corte usa a posição do cursor dentro do campo: não bloqueamos a
        // digitação, mas o atalho continua valendo mesmo com o campo focado.
        event.preventDefault()
        void actions.splitCue()
      } else if (typing) {
        return
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [view, settings.shortcut_merge, settings.shortcut_split])

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
          <button className={navIconClass(view === 'history')} title="Histórico" onClick={() => setView('history')}><Clock className="h-4 w-4" /></button>
          <button className={navIconClass(view === 'help')} title="Ajuda" onClick={() => setView('help')}><HelpCircle className="h-4 w-4" /></button>
          <button className={navIconClass(view === 'settings')} title="Configurações" onClick={() => setView('settings')}><Settings2 className="h-4 w-4" /></button>
        </nav>
      </header>

      <UpdateBanner update={update} onInstall={() => void window.legendAI.installUpdate()} />

      <main className="no-drag min-h-0 flex-1 overflow-y-auto px-8 pb-5">
        {view === 'create' && <CreateView audioName={audioName} script={script} status={createNotice} progress={job?.status === 'completed' ? 1 : job?.progress ?? null} isGenerating={isGenerating} isCancelling={Boolean(job?.cancel_requested)} outputFolder={job?.status === 'completed' ? job.output_folder : null} onChooseAudio={() => void selectAudio()} onDropAudio={dropAudio} onScriptChange={setScript} onGenerate={() => void generate()} onCancel={() => void cancelGeneration()} generatedSrt={generatedSrt} onAdjust={() => void adjustGenerated()} onOpenOutput={() => { if (job?.output_folder) void window.legendAI.openPath(job.output_folder) }} />}
        {view === 'editor' && <EditorView path={srtPath} cues={cues} selected={selected} splitPosition={splitPosition} notice={editorNotice} busy={editorBusy} canUndo={past.length > 0} canRedo={future.length > 0} shortcutMerge={settings.shortcut_merge} shortcutSplit={settings.shortcut_split} onOpen={() => void openSrt()} onDropSrt={dropSrt} onSave={() => void saveSrt()} onToggle={toggleCue} onSplitPositionChange={setSplitPosition} onTextChange={changeCueText} onTextCommit={stopEditingCue} editingIndex={editingIndex} onStartEditing={startEditingCue} scrollRef={editorScrollRef} loadToken={loadToken} onSaveAs={() => void saveSrtAs()} onMerge={() => void mergeCues()} onSplit={() => void splitCue()} onUndo={undo} onRedo={redo} />}
        {view === 'history' && <HistoryView entries={history} onOpenFolder={(path) => void window.legendAI.openPath(path)} onClear={() => void clearHistory()} />}
        {view === 'help' && <HelpView appVersion={appVersion} engineVersion={engineVersion} shortcutMerge={settings.shortcut_merge} shortcutSplit={settings.shortcut_split} />}
        {view === 'settings' && <SettingsView settings={settings} notice={settingsNotice} saving={savingSettings} loaded={settingsLoaded} onChange={setSettings} onSave={() => void saveSettings()} />}
      </main>
    </div>
  )
}

function TitleBar(): JSX.Element {
  return <div className="drag flex h-10 shrink-0 items-center justify-between px-3"><div className="flex items-center gap-2 text-xs font-medium text-muted-foreground/80"><span className="h-2 w-2 rounded-full bg-primary shadow-glow" />LegendAI</div><div className="no-drag flex items-center gap-1"><button className="icon-button" onClick={() => window.legendAI.minimize()}><Minus className="h-3.5 w-3.5" /></button><button className="icon-button" onClick={() => window.legendAI.toggleMaximize()}><Maximize2 className="h-3.5 w-3.5" /></button><button className="icon-button hover:!bg-destructive hover:!text-white" onClick={() => window.legendAI.close()}><X className="h-4 w-4" /></button></div></div>
}

function navIconClass(active: boolean): string {
  return ['icon-button', active ? 'bg-surface-elevated text-foreground shadow-soft' : ''].join(' ')
}

/** Aviso de atualização; some quando não há nada a informar. */
function UpdateBanner({ update, onInstall }: { update: UpdateInfo; onInstall: () => void }): JSX.Element | null {
  if (update.status === 'idle' || update.status === 'error') return null

  const ready = update.status === 'downloaded'
  const text = update.status === 'available'
    ? `Atualização ${update.version ?? ''} disponível — baixando…`
    : update.status === 'downloading'
      ? `Baixando atualização… ${update.percent ?? 0}%`
      : `Atualização ${update.version ?? ''} pronta para instalar.`

  return (
    <div className="no-drag mx-auto w-full max-w-[980px] px-8 pb-3">
      <div className="flex items-center gap-3 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-2.5">
        <Download className="h-4 w-4 shrink-0 text-primary" />
        <span className="min-w-0 flex-1 truncate text-xs text-foreground">{text}</span>
        {ready && (
          <button onClick={onInstall} className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-all hover:brightness-110">
            Reiniciar e instalar
          </button>
        )}
      </div>
    </div>
  )
}

function NavButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }): JSX.Element {
  return <button onClick={onClick} className={['rounded-lg px-3 py-1.5 text-xs font-medium transition-colors', active ? 'bg-surface-elevated text-foreground shadow-soft' : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground'].join(' ')}>{children}</button>
}

function fileName(path: string | null): string | undefined {
  return path?.split(/[/\\]/).pop()
}

/**
 * Compara um atalho configurável ("Ctrl+Shift+M") com o evento do teclado.
 * Aceita Cmd no lugar de Ctrl para quem usa teclado de Mac.
 */
function matchesShortcut(event: KeyboardEvent, shortcut: string): boolean {
  const parts = shortcut.toLowerCase().split('+').map((part) => part.trim()).filter(Boolean)
  if (parts.length === 0) return false
  const key = parts[parts.length - 1]
  const wantsCtrl = parts.includes('ctrl') || parts.includes('control') || parts.includes('cmd')
  const wantsShift = parts.includes('shift')
  const wantsAlt = parts.includes('alt')
  return event.key.toLowerCase() === key
    && (event.ctrlKey || event.metaKey) === wantsCtrl
    && event.shiftKey === wantsShift
    && event.altKey === wantsAlt
}

function messageFrom(error: unknown): string {
  if (!(error instanceof Error)) return 'Ocorreu um erro inesperado.'
  // O IPC do Electron prefixa a mensagem original ("Error invoking remote
  // method 'backend:request': Error: ..."); mostramos só o texto útil.
  return error.message
    .replace(/^Error invoking remote method '[^']*':\s*/, '')
    .replace(/^Error:\s*/, '')
    .trim() || 'Ocorreu um erro inesperado.'
}
