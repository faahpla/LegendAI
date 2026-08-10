import type { EngineSettings } from '@/types'

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
        <PreferenceSection title="Leitura e tempo">
          <div className="grid grid-cols-2 gap-4">
            <NumberField label="Tempo mínimo" suffix="seg" value={settings.min_duration} onChange={(value) => set('min_duration', value)} />
            <NumberField label="Tempo máximo" suffix="seg" value={settings.max_duration} onChange={(value) => set('max_duration', value)} />
            <NumberField label="Caracteres máximos" suffix="chars" value={settings.max_chars} onChange={(value) => set('max_chars', value)} />
            <NumberField label="Fechar vãos até" suffix="seg" value={settings.max_gap} onChange={(value) => set('max_gap', value)} />
            <NumberField label="Margem inicial" suffix="seg" value={settings.margin_start} onChange={(value) => set('margin_start', value)} />
            <NumberField label="Margem final" suffix="seg" value={settings.margin_end} onChange={(value) => set('margin_end', value)} />
          </div>
        </PreferenceSection>
        <PreferenceSection title="Compatibilidade com o editor">
          <Toggle
            label="Fechar espaços entre legendas"
            hint={`Emenda pausas de até ${settings.max_gap}s. Aumente "Fechar vãos até" para eliminar também as pausas longas.`}
            checked={settings.close_gaps}
            onChange={(checked) => set('close_gaps', checked)}
          />
          <div className="mt-3 max-w-[240px]">
            <NumberField
              label="Alinhar aos quadros (FPS)"
              suffix="fps"
              value={settings.snap_fps}
              onChange={(value) => set('snap_fps', value)}
            />
            <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground/80">
              Use o FPS do seu projeto. Editores por quadro (CapCut) podem abrir um
              piscado de um quadro quando o tempo cai no meio de um. 0 desliga.
              25 e 50 fps ficam exatos no SRT; 30 e 60 têm erro de ~1 ms.
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
          {settings.check_alignment && (
            <div className="mt-3 max-w-[220px]">
              <NumberField label="Confiança mínima" suffix="0–1" value={settings.min_alignment_score} onChange={(value) => set('min_alignment_score', Math.min(value, 1))} />
            </div>
          )}
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

function NumberField({ label, suffix, value, onChange }: { label: string; suffix: string; value: number; onChange: (value: number) => void }): JSX.Element {
  return (
    <label>
      <span className="mb-2 block text-xs text-muted-foreground">{label}</span>
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
