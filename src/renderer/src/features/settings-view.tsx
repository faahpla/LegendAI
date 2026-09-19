import type { EngineSettings } from '@/types'

/** Taxas mais comuns; NTSC (23,976 / 29,97 / 59,94) o motor converte para a fração exata. */
const FPS_PRESETS = [
  { value: 0, label: 'Desligado' },
  { value: 23.976, label: '23,976' },
  { value: 24, label: '24' },
  { value: 25, label: '25' },
  { value: 29.97, label: '29,97' },
  { value: 30, label: '30' },
  { value: 50, label: '50' },
  { value: 59.94, label: '59,94' },
  { value: 60, label: '60' }
]

type SettingsViewProps = {
  settings: EngineSettings
  notice: string
  saving: boolean
  loaded: boolean
  onChange: (settings: EngineSettings) => void
  onSave: () => void
}

export function SettingsView({ settings, notice, saving, loaded, onChange, onSave }: SettingsViewProps): JSX.Element {
  const set = <K extends keyof EngineSettings>(key: K, value: EngineSettings[K]): void => {
    onChange({ ...settings, [key]: value })
  }

  return (
    <section className="mx-auto w-full max-w-[760px] py-5">
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Configurações</h1>
        <p className="mt-1 text-sm text-muted-foreground">Defina como o Legend Engine prepara as suas legendas.</p>
      </div>
      <div className="panel overflow-hidden rounded-3xl">
        <PreferenceSection title="Como as legendas são montadas">
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              label="Palavras por legenda"
              suffix="palavras"
              value={settings.max_words}
              hint="Quantas palavras podem dividir a mesma legenda, se couberem no limite de caracteres. 1 = uma palavra por vez."
              onChange={(value) => set('max_words', Math.max(Math.round(value), 1))}
            />
            <NumberField
              label="Caracteres máximos"
              suffix="letras"
              value={settings.max_chars}
              hint="Limite de letras por legenda, contando os espaços. Uma palavra maior que isso fica sozinha e nunca é cortada."
              onChange={(value) => set('max_chars', Math.max(Math.round(value), 1))}
            />
          </div>
          <p className="mt-3 rounded-lg border border-border bg-surface-elevated/40 px-3 py-2 text-[11px] leading-5 text-muted-foreground">
            <strong className="text-foreground">Exemplo</strong> com 2 palavras e 12 letras:{' '}
            <span className="font-mono">as tropas</span> (9 letras) ficam juntas ·{' '}
            <span className="font-mono">subordinadas</span> (12) fica sozinha ·{' '}
            <span className="font-mono">demônios primordiais</span> (20) é separada em duas. O
            artigo nunca fecha uma legenda: em “Quatro dos guardas” o corte cai antes de{' '}
            <span className="font-mono">dos</span>, não depois.
          </p>
        </PreferenceSection>
        <PreferenceSection title="Tempo na tela">
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              label="Tempo mínimo"
              suffix="seg"
              value={settings.min_duration}
              hint="Menor tempo que uma legenda fica visível. Evita palavras que piscam rápido demais para ler."
              onChange={(value) => set('min_duration', value)}
            />
            <NumberField
              label="Tempo máximo"
              suffix="seg"
              value={settings.max_duration}
              hint="Maior tempo que uma legenda fica visível, mesmo que a pausa na narração seja longa."
              onChange={(value) => set('max_duration', value)}
            />
            <NumberField
              label="Antecipar a entrada"
              suffix="seg"
              value={settings.margin_start}
              hint="Faz a legenda aparecer um pouco antes da palavra ser falada, quando há espaço livre. Dá conforto de leitura."
              onChange={(value) => set('margin_start', value)}
            />
            <NumberField
              label="Atrasar a saída"
              suffix="seg"
              value={settings.margin_end}
              hint="Mantém a legenda um instante depois da palavra terminar, quando há espaço livre."
              onChange={(value) => set('margin_end', value)}
            />
          </div>
        </PreferenceSection>
        <PreferenceSection title="Compatibilidade com o editor">
          <Toggle
            label="Emendar legendas para não piscar"
            hint="Sem isso, a legenda desaparece por um instante entre as palavras. Ligado, o fim de uma encosta no início da seguinte."
            checked={settings.close_gaps}
            onChange={(checked) => set('close_gaps', checked)}
          />
          {settings.close_gaps && (
            <div className="mt-3 max-w-[240px]">
              <NumberField
                label="Emendar pausas de até"
                suffix="seg"
                value={settings.max_gap}
                hint="Pausas menores que isso são emendadas. Pausas maiores são preservadas, porque são silêncios reais da narração — aumente se não quiser nenhum espaço."
                onChange={(value) => set('max_gap', value)}
              />
            </div>
          )}
          <div className="mt-3">
            <span className="mb-2 block text-xs text-muted-foreground">Alinhar aos quadros</span>
            <div className="flex flex-wrap gap-1.5">
              {FPS_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  type="button"
                  onClick={() => set('snap_fps', preset.value)}
                  className={[
                    'rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors',
                    Math.abs(settings.snap_fps - preset.value) < 0.001
                      ? 'border-primary bg-primary/15 text-foreground'
                      : 'border-border bg-surface-elevated text-muted-foreground hover:bg-surface-hover'
                  ].join(' ')}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11px] leading-4 text-muted-foreground/80">
              Use o FPS do <strong>seu</strong> projeto — editores por quadro (CapCut)
              podem abrir um piscado de um quadro quando o tempo cai no meio de um.
              Cada pessoa gera o próprio SRT com o próprio FPS: as grades de 23,976 e
              30 só coincidem a cada 33 s, então não existe arquivo único que sirva
              para os dois. 25 e 50 ficam exatos no SRT; as demais têm erro de ~1 ms,
              imperceptível.
            </p>
          </div>
        </PreferenceSection>
        <PreferenceSection title="Texto do roteiro">
          <Toggle
            label="Remover caracteres especiais"
            hint="Mantém letras, números, espaços e os caracteres listados abaixo."
            checked={settings.strip_special_chars}
            onChange={(checked) => set('strip_special_chars', checked)}
          />
          {settings.strip_special_chars && (
            <TextField
              label="Caracteres preservados"
              hint='Padrão: aspas e dois-pontos. Adicione .,!? se quiser manter a pontuação.'
              value={settings.keep_characters}
              onChange={(value) => set('keep_characters', value)}
            />
          )}
        </PreferenceSection>
        <PreferenceSection title="Verificação">
          <Toggle
            label="Avisar quando o áudio não corresponder ao roteiro"
            hint="Interrompe a geração em vez de produzir legendas sem sentido."
            checked={settings.check_alignment}
            onChange={(checked) => set('check_alignment', checked)}
          />
        </PreferenceSection>
        <PreferenceSection title="Atalhos do editor">
          <div className="grid grid-cols-2 gap-4">
            <TextField label="Mesclar" value={settings.shortcut_merge} onChange={(value) => set('shortcut_merge', value)} />
            <TextField label="Dividir" value={settings.shortcut_split} onChange={(value) => set('shortcut_split', value)} />
          </div>
        </PreferenceSection>
        <PreferenceSection title="Exportação">
          <Toggle label="Exportar SRT" checked={settings.export_srt} onChange={(checked) => set('export_srt', checked)} />
          <Toggle label="Exportar ASS" checked={settings.export_ass} onChange={(checked) => set('export_ass', checked)} />
          <Toggle label="Abrir pasta ao concluir" checked={settings.open_folder} onChange={(checked) => set('open_folder', checked)} />
        </PreferenceSection>
        <div className="flex items-center justify-between gap-4 border-t border-border/70 px-7 py-4">
          <span className="text-xs text-muted-foreground">{notice}</span>
          <button onClick={onSave} disabled={saving || !loaded} className="h-9 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground shadow-glow transition-all hover:brightness-110 active:scale-[.98] disabled:opacity-60">
            {saving ? 'Salvando…' : loaded ? 'Salvar alterações' : 'Carregando…'}
          </button>
        </div>
      </div>
    </section>
  )
}

function PreferenceSection({ title, children }: { title: string; children: React.ReactNode }): JSX.Element {
  return <section className="border-b border-border/70 px-7 py-6"><h2 className="mb-5 text-sm font-semibold tracking-tight">{title}</h2>{children}</section>
}

function NumberField({ label, suffix, value, hint, onChange }: { label: string; suffix: string; value: number; hint?: string; onChange: (value: number) => void }): JSX.Element {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-medium text-foreground/90">{label}</span>
      <span className="control flex h-10 items-center px-3">
        <input
          value={value}
          type="number"
          step="any"
          min="0"
          onChange={(event) => {
            // Campo vazio/inválido vira NaN -> null no JSON -> TypeError no motor.
            const parsed = Number(event.target.value)
            onChange(Number.isFinite(parsed) && parsed >= 0 ? parsed : 0)
          }}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
        <span className="text-xs text-muted-foreground">{suffix}</span>
      </span>
      {hint && <span className="mt-1.5 block text-[11px] leading-4 text-muted-foreground/80">{hint}</span>}
    </label>
  )
}

function TextField({ label, hint, value, onChange }: { label: string; hint?: string; value: string; onChange: (value: string) => void }): JSX.Element {
  return (
    <label className="mt-3 block first:mt-0">
      <span className="mb-2 block text-xs text-muted-foreground">{label}</span>
      <span className="control flex h-10 items-center px-3">
        <input value={value} onChange={(event) => onChange(event.target.value)} spellCheck={false} className="min-w-0 flex-1 bg-transparent font-mono text-sm outline-none" />
      </span>
      {hint && <span className="mt-1.5 block text-[11px] leading-4 text-muted-foreground/80">{hint}</span>}
    </label>
  )
}

function Toggle({ label, hint, checked, onChange }: { label: string; hint?: string; checked: boolean; onChange: (checked: boolean) => void }): JSX.Element {
  return (
    <label className="mb-3 flex cursor-pointer items-center justify-between gap-4 last:mb-0">
      <span>
        <span className="block text-sm">{label}</span>
        {hint && <span className="mt-0.5 block text-[11px] leading-4 text-muted-foreground/80">{hint}</span>}
      </span>
      <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className={['relative h-6 w-11 shrink-0 rounded-full transition-colors', checked ? 'bg-primary' : 'bg-muted'].join(' ')}>
        <span className={['absolute top-1 h-4 w-4 rounded-full bg-white shadow transition-transform', checked ? 'translate-x-6' : 'translate-x-1'].join(' ')} />
      </button>
    </label>
  )
}
