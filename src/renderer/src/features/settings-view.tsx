import type { EngineSettings } from '@/types'

type SettingsViewProps = {
  settings: EngineSettings
  notice: string
  saving: boolean
  onChange: (settings: EngineSettings) => void
  onSave: () => void
}

export function SettingsView({ settings, notice, saving, onChange, onSave }: SettingsViewProps): JSX.Element {
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
        <PreferenceSection title="Exportação">
          <Toggle label="Fechar espaços entre legendas" checked={settings.close_gaps} onChange={(checked) => set('close_gaps', checked)} />
          <Toggle label="Exportar SRT" checked={settings.export_srt} onChange={(checked) => set('export_srt', checked)} />
          <Toggle label="Exportar ASS" checked={settings.export_ass} onChange={(checked) => set('export_ass', checked)} />
          <Toggle label="Abrir pasta ao concluir" checked={settings.open_folder} onChange={(checked) => set('open_folder', checked)} />
        </PreferenceSection>
        <div className="flex items-center justify-between gap-4 border-t border-border/70 px-7 py-4">
          <span className="text-xs text-muted-foreground">{notice}</span>
          <button onClick={onSave} disabled={saving} className="h-9 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground shadow-glow transition-all hover:brightness-110 active:scale-[.98] disabled:opacity-60">
            {saving ? 'Salvando…' : 'Salvar alterações'}
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
        <input value={value} type="number" step="any" onChange={(event) => onChange(Number(event.target.value))} className="min-w-0 flex-1 bg-transparent text-sm outline-none" />
        <span className="text-xs text-muted-foreground">{suffix}</span>
      </span>
    </label>
  )
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }): JSX.Element {
  return (
    <label className="mb-3 flex cursor-pointer items-center justify-between last:mb-0">
      <span className="text-sm">{label}</span>
      <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className={['relative h-6 w-11 rounded-full transition-colors', checked ? 'bg-primary' : 'bg-muted'].join(' ')}>
        <span className={['absolute top-1 h-4 w-4 rounded-full bg-white shadow transition-transform', checked ? 'translate-x-6' : 'translate-x-1'].join(' ')} />
      </button>
    </label>
  )
}
