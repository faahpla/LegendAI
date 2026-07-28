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
  close: (): void => ipcRenderer.send('window:close')
}

contextBridge.exposeInMainWorld('legendAI', api)
