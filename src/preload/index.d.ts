declare global {
  interface Window {
    legendAI: {
      pickAudio(): Promise<string | null>
      filePath(file: File): string
      pickSrt(): Promise<string | null>
      saveSrt(defaultPath: string): Promise<string | null>
      openPath(path: string): Promise<string>
      request<T>(path: string, method?: string, data?: unknown): Promise<T>
      minimize(): void
      toggleMaximize(): void
      close(): void
    }
  }
}

export {}
