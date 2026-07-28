import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import { autoUpdater } from 'electron-updater'
import { spawn, type ChildProcess } from 'node:child_process'
import { appendFileSync, existsSync } from 'node:fs'
import { createServer } from 'node:net'
import { join } from 'node:path'

let mainWindow: BrowserWindow | null = null
let backendProcess: ChildProcess | null = null
let backendUrl = ''

function configureAutoUpdates(): void {
  if (!app.isPackaged || process.platform !== 'win32') return

  autoUpdater.autoDownload = true
  autoUpdater.autoInstallOnAppQuit = true
  autoUpdater.on('error', (error) => {
    console.warn('Update check failed:', error.message)
  })
  void autoUpdater.checkForUpdatesAndNotify().catch((error: Error) => {
    console.warn('Update check failed:', error.message)
  })
}

function appIconPath(): string {
  const root = app.isPackaged ? process.resourcesPath : process.cwd()
  return join(root, 'assets', 'legendai.ico')
}

function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer()
    server.unref()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      if (!address || typeof address === 'string') {
        reject(new Error('Não foi possível reservar uma porta local.'))
        return
      }
      server.close((error) => (error ? reject(error) : resolve(address.port)))
    })
  })
}

async function startBackend(): Promise<void> {
  const port = await findFreePort()
  const packagedEngine = join(process.resourcesPath, 'engine', 'LegendAIEngine.exe')
  const hasPackagedEngine = app.isPackaged && existsSync(packagedEngine)
  const command = hasPackagedEngine ? packagedEngine : 'python'
  const args = hasPackagedEngine
    ? ['--port', String(port)]
    : ['-m', 'legendai.server', '--port', String(port)]

  backendProcess = spawn(command, args, {
    cwd: app.isPackaged ? process.resourcesPath : process.cwd(),
    windowsHide: true,
    stdio: 'ignore'
  })
  backendUrl = `http://127.0.0.1:${port}`
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 780,
    minWidth: 960,
    minHeight: 680,
    show: false,
    frame: false,
    backgroundColor: '#0c0c12',
    icon: appIconPath(),
    title: 'LegendAI',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
    configureAutoUpdates()
  })
  if (process.env.ELECTRON_RENDERER_URL) {
    void mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    void mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(async () => {
  app.setAppUserModelId('com.faah.legendai')
  await startBackend()
  createWindow()

  ipcMain.handle('dialog:pick-audio', async () => {
    const result = await dialog.showOpenDialog(mainWindow!, {
      title: 'Selecionar áudio da narração',
      properties: ['openFile'],
      filters: [
        { name: 'Áudio', extensions: ['mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg'] },
        { name: 'Todos os arquivos', extensions: ['*'] }
      ]
    })
    return result.canceled ? null : result.filePaths[0]
  })
  ipcMain.handle('dialog:pick-srt', async () => {
    const result = await dialog.showOpenDialog(mainWindow!, {
      title: 'Abrir legenda SRT',
      properties: ['openFile'],
      filters: [{ name: 'Legenda SRT', extensions: ['srt'] }]
    })
    return result.canceled ? null : result.filePaths[0]
  })
  ipcMain.handle('dialog:save-srt', async (_event, defaultPath: string) => {
    const result = await dialog.showSaveDialog(mainWindow!, {
      title: 'Salvar legenda SRT',
      defaultPath,
      filters: [{ name: 'Legenda SRT', extensions: ['srt'] }]
    })
    return result.canceled ? null : result.filePath
  })
  ipcMain.handle('shell:open-path', (_event, path: string) => shell.openPath(path))
  ipcMain.handle(
    'backend:request',
    async (_event, request: { path: string; method?: string; data?: unknown }) => {
      const response = await fetch(`${backendUrl}${request.path}`, {
        method: request.method ?? 'GET',
        headers: request.data === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: request.data === undefined ? undefined : JSON.stringify(request.data)
      })
      const data = (await response.json()) as { error?: string }
      if (!response.ok) throw new Error(data.error ?? 'Falha na comunicação com o motor.')
      return data
    }
  )
  ipcMain.on('window:minimize', () => mainWindow?.minimize())
  ipcMain.on('window:toggle-maximize', () => {
    if (mainWindow?.isMaximized()) mainWindow.unmaximize()
    else mainWindow?.maximize()
  })
  ipcMain.on('window:close', () => mainWindow?.close())

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
}).catch((error: unknown) => {
  const detail = error instanceof Error ? (error.stack ?? error.message) : String(error)
  try {
    appendFileSync(
      join(app.getPath('userData'), 'startup-error.log'),
      `${new Date().toISOString()}\n${detail}\n\n`
    )
  } catch {
    // Nothing else can safely be done if the diagnostic file cannot be written.
  }
  dialog.showErrorBox('LegendAI', `O LegendAI não conseguiu iniciar.\n\n${detail}`)
  app.exit(1)
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => backendProcess?.kill())
