import { contextBridge, ipcRenderer, webUtils } from 'electron'

const api = {
  pickAudio: (): Promise<string | null> => ipcRenderer.invoke('dialog:pick-audio'),
  filePath: (file: File): string => webUtils.getPathForFile(file),
  pickSrt: (): Promise<string | null> => ipcRenderer.invoke('dialog:pick-srt'),
  saveSrt: (defaultPath: string): Promise<string | null> =>
    ipcRenderer.invoke('dialog:save-srt', defaultPath),
  openPath: (path: string): Promise<string> => ipcRenderer.invoke('shell:open-path', path),
  request: <T>(path: string, method = 'GET', data?: unknown): Promise<T> =>
    ipcRenderer.invoke('backend:request', { path, method, data }),
  minimize: (): void => ipcRenderer.send('window:minimize'),
  toggleMaximize: (): void => ipcRenderer.send('window:toggle-maximize'),
  close: (): void => ipcRenderer.send('window:close'),
  appVersion: (): Promise<string> => ipcRenderer.invoke('app:version'),
  currentUpdate: <T>(): Promise<T> => ipcRenderer.invoke('updater:current'),
  installUpdate: (): Promise<void> => ipcRenderer.invoke('updater:install'),
  onUpdateState: (listener: (state: unknown) => void): (() => void) => {
    const handler = (_event: unknown, state: unknown): void => listener(state)
    ipcRenderer.on('updater:state', handler)
    return () => ipcRenderer.removeListener('updater:state', handler)
  }
}

contextBridge.exposeInMainWorld('legendAI', api)
