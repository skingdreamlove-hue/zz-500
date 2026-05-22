const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    startBackend: () => ipcRenderer.invoke('start-backend'),
    readFile: (fileName) => ipcRenderer.invoke('read-file', fileName)
});