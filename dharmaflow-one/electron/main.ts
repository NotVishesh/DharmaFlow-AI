import { app, BrowserWindow, ipcMain } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

function startPythonBackend() {
  const backendDir = path.join(__dirname, '..', '..', 'backend');
  const pythonExecutable = process.platform === 'win32'
    ? path.join(__dirname, '..', '..', '..', '.venv', 'Scripts', 'python.exe')
    : 'python3';

  try {
    pythonProcess = spawn(
      pythonExecutable,
      ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000'],
      {
        cwd: path.join(__dirname, '..', '..'),
        windowsHide: true,
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
      }
    );

    pythonProcess.stdout?.on('data', (data) => {
      console.log(`[Python Backend]: ${data}`);
    });

    pythonProcess.stderr?.on('data', (data) => {
      console.error(`[Python Backend Err]: ${data}`);
    });

    pythonProcess.on('error', (err) => console.error('Backend failed to start:', err));
    pythonProcess.on('close', (code) => {
      console.log(`Python process exited with code ${code}`);
    });
  } catch (err) {
    console.error('Failed to spawn Python backend:', err);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1366,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    title: 'DharmaFlow One',
  });

  const isDev = process.env.NODE_ENV === 'development';
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', '..', 'frontend', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
