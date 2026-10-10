"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("wallpaper", {
  getConfig: () => ipcRenderer.invoke("config:get"),
  saveConfig: (payload) => ipcRenderer.invoke("config:save", payload),
  probe: (area) => ipcRenderer.invoke("probe", area),
  generate: (options) => ipcRenderer.invoke("generate", options || {}),
  onLog: (callback) => {
    const handler = (_event, line) => callback(line);
    ipcRenderer.on("generate:log", handler);
    return () => ipcRenderer.removeListener("generate:log", handler);
  },
  taskStatus: () => ipcRenderer.invoke("task:status"),
  taskInstall: (dailyTime) => ipcRenderer.invoke("task:install", dailyTime),
  taskRemove: () => ipcRenderer.invoke("task:remove"),
  previewUrl: () => ipcRenderer.invoke("preview:url"),
  getRenderPayload: () => ipcRenderer.invoke("render:payload"),
  wallpaperReady: () => ipcRenderer.send("wallpaper:ready"),
});
