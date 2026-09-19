import { BookOpen, Keyboard, Sparkles } from 'lucide-react'

type HelpViewProps = {
  appVersion: string
  engineVersion: string
  shortcutMerge: string
  shortcutSplit: string
}

export function HelpView({ appVersion, engineVersion, shortcutMerge, shortcutSplit }: HelpViewProps): JSX.Element {
  const steps = [
    'Na aba Criar, escolha (ou arraste) o áudio da narração.',
    'Cole no campo Roteiro exatamente o texto que deve aparecer no vídeo.',
    'Clique em Gerar legendas — o LegendAI descobre o tempo de cada palavra e salva o SRT/ASS ao lado do áudio.',
    'Só na primeira geração ele baixa o modelo de alinhamento (cerca de 1,2 GB, guardado pela metade em disco). Daí em diante trabalha sem internet.',
    'Use a aba Ajustar para mesclar ou dividir blocos e salve o arquivo.',
    'Importe o SRT no DaVinci Resolve, Premiere ou CapCut.'
  ]

  const shortcuts = [
    { keys: shortcutMerge, action: 'Mesclar as legendas selecionadas' },
    { keys: shortcutSplit, action: 'Dividir a legenda selecionada' },
    { keys: 'Ctrl+Z', action: 'Desfazer a última edição' },
    { keys: 'Ctrl+Y  ou  Ctrl+Shift+Z', action: 'Refazer' },
    { keys: 'Ctrl+S', action: 'Salvar o SRT aberto' },
    { keys: 'Ctrl+O', action: 'Abrir um SRT' },
    { keys: 'Clique', action: 'Selecionar uma legenda' },
    { keys: 'Shift+Clique', action: 'Selecionar um intervalo de legendas' },
    { keys: 'Clique no texto', action: 'Editar a legenda e posicionar o corte' },
    { keys: 'Esc', action: 'Limpar a seleção' }
  ]

  return (
    <section className="mx-auto w-full max-w-[980px] py-5">
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Ajuda</h1>
        <p className="mt-1 text-sm text-muted-foreground">Como usar o LegendAI e todos os atalhos de teclado.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="panel rounded-3xl p-6">
          <SectionTitle icon={<Sparkles className="h-4 w-4" />} title="Como funciona" />
          <ol className="mt-4 space-y-3">
            {steps.map((step, index) => (
              <li key={step} className="flex gap-3 text-sm leading-6 text-muted-foreground">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-primary/10 text-[11px] font-semibold text-primary">{index + 1}</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="panel rounded-3xl p-6">
          <SectionTitle icon={<Keyboard className="h-4 w-4" />} title="Atalhos de teclado" />
          <p className="mt-2 text-xs text-muted-foreground">Válidos na aba Ajustar. Os dois primeiros são configuráveis.</p>
          <ul className="mt-4 space-y-2">
            {shortcuts.map((shortcut) => (
              <li key={shortcut.keys} className="flex items-center justify-between gap-4">
                <span className="text-sm text-muted-foreground">{shortcut.action}</span>
                <kbd className="shrink-0 rounded-md border border-border bg-surface-elevated px-2 py-1 font-mono text-[11px] text-foreground">{shortcut.keys}</kbd>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="panel mt-4 flex flex-wrap items-center justify-between gap-4 rounded-3xl px-6 py-5">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary"><BookOpen className="h-4 w-4" /></span>
          <div>
            <p className="text-sm font-medium">LegendAI</p>
            <p className="mt-0.5 text-xs text-muted-foreground">Sincronização local — nada do seu roteiro sai da máquina.</p>
          </div>
        </div>
        <div className="text-right">
          <p className="font-mono text-sm">v{appVersion}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">motor {engineVersion}</p>
        </div>
      </div>
    </section>
  )
}

function SectionTitle({ icon, title }: { icon: JSX.Element; title: string }): JSX.Element {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-elevated text-muted-foreground">{icon}</span>
      <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
    </div>
  )
}
