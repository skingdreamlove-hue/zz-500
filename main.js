const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess = null;
let backendPort = 5001;

function findPython() {
    const hardcoded = 'C:\\Users\\MY\\AppData\\Local\\Programs\\Python\\Python313\\python.exe';
    if (fs.existsSync(hardcoded)) return hardcoded;
    try {
        const { execSync } = require('child_process');
        const found = execSync('where python 2>nul', { encoding: 'utf8' }).trim().split('\n')[0].trim();
        if (found && fs.existsSync(found)) return found;
    } catch (e) {}
    return 'python';
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        title: '中证500量化系统'
    });

    mainWindow.loadFile('index.html');
}

function readPortFile() {
    try {
        const portFile = path.join(__dirname, '.server_port');
        if (fs.existsSync(portFile)) {
            const port = parseInt(fs.readFileSync(portFile, 'utf8').trim());
            if (port > 0 && port < 65536) {
                backendPort = port;
                console.log(`读取到后端端口: ${backendPort}`);
            }
        }
    } catch (e) {
        console.error('读取端口文件失败:', e);
    }
}

function waitForBackend(maxRetries, callback) {
    let retries = 0;
    const http = require('http');

    function tryConnect() {
        const req = http.get(`http://127.0.0.1:${backendPort}/api/health`, (res) => {
            if (res.statusCode === 200 || res.statusCode === 500) {
                callback(true);
            } else {
                retry();
            }
        });
        req.on('error', () => {
            retry();
        });
        req.setTimeout(3000, () => {
            req.destroy();
            retry();
        });
    }

    function retry() {
        retries++;
        if (retries < maxRetries) {
            setTimeout(tryConnect, 2000);
        } else {
            callback(false);
        }
    }

    tryConnect();
}

ipcMain.handle('start-backend', async () => {
    if (pythonProcess) {
        return { success: true, port: backendPort };
    }

    return new Promise((resolve, reject) => {
        const backendScript = path.join(__dirname, 'app.py');
        pythonProcess = spawn(findPython(), [backendScript], {
            cwd: __dirname,
            stdio: ['pipe', 'pipe', 'pipe']
        });

        pythonProcess.stdout.on('data', (data) => {
            const text = data.toString();
            console.log('[Backend]', text);
        });

        pythonProcess.stderr.on('data', (data) => {
            const text = data.toString();
            console.error('[Backend Error]', text);
        });

        pythonProcess.on('close', (code) => {
            console.log(`后端服务已退出，代码: ${code}`);
            pythonProcess = null;
        });

        pythonProcess.on('error', (err) => {
            console.error('启动后端服务失败:', err);
            pythonProcess = null;
            reject({ success: false, message: `启动失败: ${err.message}` });
        });

        setTimeout(() => {
            readPortFile();
            waitForBackend(15, (ok) => {
                if (ok) {
                    resolve({ success: true, port: backendPort });
                } else {
                    resolve({ success: false, port: backendPort });
                }
            });
        }, 3000);
    });
});

ipcMain.handle('read-file', async (event, fileName) => {
    try {
        const filePath = path.resolve(__dirname, fileName);
        if (!filePath.startsWith(path.resolve(__dirname) + path.sep) && filePath !== path.resolve(__dirname)) {
            console.error('路径遍历攻击被阻止:', fileName);
            return '';
        }
        const content = fs.readFileSync(filePath, 'utf8');
        return content;
    } catch (e) {
        console.error('读取文件失败:', e);
        return '';
    }
});

app.commandLine.appendSwitch('disable-gpu-shader-disk-cache');

app.whenReady().then(createWindow);

function killBackend() {
    if (pythonProcess) {
        try {
            pythonProcess.kill();
        } catch (e) {}
        pythonProcess = null;
    }
}

app.on('window-all-closed', () => {
    killBackend();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

process.on('exit', killBackend);
process.on('SIGINT', () => { killBackend(); process.exit(0); });
process.on('SIGTERM', () => { killBackend(); process.exit(0); });

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});