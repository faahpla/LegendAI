export type View = 'create' | 'editor' | 'settings' | 'history' | 'help'

export type Cue = {
  text: string
  start: number
  end: number
}

export type GenerationJob = {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  message: string
  files: string[]
  output_folder: string | null
  error: string | null
  cancel_requested: boolean
}

export type HistoryEntry = {
  id: string
  created_at: string
  audio_path: string
  audio_name: string
  script_preview: string
  files: string[]
  output_folder: string
  cue_count: number
  duration: number
  confidence: number | null
}

export type UpdateInfo = {
  status: 'idle' | 'available' | 'downloading' | 'downloaded' | 'error'
  version?: string
  percent?: number
  message?: string
}

export type EngineSettings = {
  min_duration: number
  max_duration: number
  max_chars: number
  max_words: number
  margin_start: number
  margin_end: number
  close_gaps: boolean
  max_gap: number
  snap_fps: number
  export_srt: boolean
  export_ass: boolean
  open_folder: boolean
  language: string
  shortcut_merge: string
  shortcut_split: string
  strip_special_chars: boolean
  keep_characters: string
  check_alignment: boolean
  min_alignment_score: number
  linking_words: string[]
}

export const fallbackSettings: EngineSettings = {
  min_duration: 0.45,
  max_duration: 2,
  max_chars: 10,
  max_words: 1,
  margin_start: 0.03,
  margin_end: 0.03,
  close_gaps: true,
  max_gap: 0.5,
  snap_fps: 30,
  export_srt: true,
  export_ass: true,
  open_folder: true,
  language: 'pt',
  shortcut_merge: 'Ctrl+Shift+M',
  shortcut_split: 'Ctrl+Shift+S',
  strip_special_chars: false,
  keep_characters: '":',
  check_alignment: true,
  min_alignment_score: 0.35,
  linking_words: []
}
