export type View = 'create' | 'editor' | 'settings'

export type Cue = {
  text: string
  start: number
  end: number
}

export type GenerationJob = {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  message: string
  files: string[]
  output_folder: string | null
  error: string | null
}

export type EngineSettings = {
  min_duration: number
  max_duration: number
  max_chars: number
  margin_start: number
  margin_end: number
  close_gaps: boolean
  max_gap: number
  export_srt: boolean
  export_ass: boolean
  open_folder: boolean
  language: string
  shortcut_merge: string
  shortcut_split: string
  small_words: string[]
}

export const fallbackSettings: EngineSettings = {
  min_duration: 0.45,
  max_duration: 2,
  max_chars: 10,
  margin_start: 0.03,
  margin_end: 0.03,
  close_gaps: true,
  max_gap: 0.5,
  export_srt: true,
  export_ass: true,
  open_folder: true,
  language: 'pt',
  shortcut_merge: 'Ctrl+Shift+M',
  shortcut_split: 'Ctrl+Shift+S',
  small_words: []
}
