"use strict";

const { app, BrowserWindow, ipcMain, protocol, net, screen } = require("electron");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");
const areas = require("../shared/areas.js");
const present = require("../shared/present.cjs");
const fetchData = require("../shared/fetch.cjs");
const schedule = require("./schedule.cjs");

const DEV_URL = process.env.ELECTRON_RENDERER_URL || "http://127.0.0.1:5173";
const headless = process.argv.includes("--generate");

protocol.registerSchemesAsPrivileged([
  {
    scheme: "media",
    privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true },
  },
]);

let composer = null;
let pendingRender = null;
let generating = false;

function projectRoot() {
  if (app.isPackaged) return process.resourcesPath;
  const fromApp = app.getAppPath();
  if (fs.existsSync(path.join(fromApp, "package.json"))) return fromApp;
  return path.resolve(fromApp, "..");
}

function appPaths() {
  const user = app.getPath("userData");
  const root = projectRoot();
  return {
    user,
    root,
    config: path.join(user, "config.json"),
    output: path.join(user, "output"),
    cache: path.join(user, "cache"),
    png: path.join(user, "output", "today.png"),
    ps1: path.join(root, "set_wallpaper.ps1"),
    seed: path.join(root, "config.json"),
  };
}

function readConfig() {
  const store = appPaths();
  fs.mkdirSync(store.output, { recursive: true });
  fs.mkdirSync(store.cache, { recursive: true });
  if (!fs.existsSync(store.config)) {
    const seed = JSON.parse(fs.readFileSync(store.seed, "utf8"));
    fs.writeFileSync(store.config, `${JSON.stringify(areas.normalizeConfig(seed), null, 2)}\n`);
  }
  return areas.normalizeConfig(JSON.parse(fs.readFileSync(store.config, "utf8")));
}

function writeConfig(cfg) {
  fs.writeFileSync(appPaths().config, `${JSON.stringify(cfg, null, 2)}\n`);
}

function saveIncoming(incoming) {
  const current = readConfig();
  const cleaned = (incoming.areas || []).map(areas.cleanArea);
  const grid = areas.gridOf({ grid: incoming.grid });
  const resolution = (incoming.resolution || current.resolution || [2560, 1440]).map(Number);
  const errors = areas.validate(grid, cleaned, resolution);
  const daily = String((incoming.schedule && incoming.schedule.daily_time) || "");
  if (daily && !/^([01]\d|2[0-3]):[0-5]\d$/.test(daily)) errors.push("计划时间要写成 06:00 这样");
  if (errors.length) return { ok: false, errors };
  current.resolution = resolution;
  current.grid = {
    cols: grid.cols,
    rows: grid.rows,
    gap: Math.round(grid.gap),
    margin: Math.round(grid.margin),
    taskbar: grid.taskbar,
  };
  current.areas = cleaned;
  current.schedule = {
    daily_time: daily || (current.schedule && current.schedule.daily_time) || "06:00",
    task_name: (incoming.schedule && incoming.schedule.task_name) || (current.schedule && current.schedule.task_name) || "DailyWallpaper",
  };
  writeConfig(current);
  return { ok: true, config: areas.normalizeConfig(current) };
}

function sendLog(line) {
  if (composer && !composer.isDestroyed()) composer.webContents.send("generate:log", line);
}

function launchCommand() {
  if (app.isPackaged) return { execute: process.execPath, args: "--generate" };
  return { execute: process.execPath, args: `"${projectRoot()}" --generate` };
}

function applyCommand() {
  const store = appPaths();
  const root = process.env.SystemRoot || "C:\\Windows";
  const powershell = path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
  return {
    execute: powershell,
    args: `-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "${store.ps1}" -Path "${store.png}" -Style Fill`,
  };
}

function loadPage(win, hash) {
  const distIndex = path.join(__dirname, "../dist/index.html");
  const useFile = app.isPackaged || (headless && fs.existsSync(distIndex));
  if (!useFile) return win.loadURL(`${DEV_URL}/${hash}`);
  return win.loadFile(distIndex, { hash: hash.replace(/^#/, "") });
}

function registerMedia() {
  const store = appPaths();
  protocol.handle("media", (request) => {
    const url = new URL(request.url);
    let full = "";
    if (url.hostname === "cache") {
      full = path.join(store.cache, path.basename(decodeURIComponent(url.pathname)));
    } else if (url.hostname === "output") {
      full = path.join(store.output, path.basename(decodeURIComponent(url.pathname)));
    } else if (url.hostname === "local") {
      const rel = String(url.searchParams.get("path") || "").replaceAll("\\", "/");
      if (!rel || rel.split("/").includes("..")) return new Response("bad path", { status: 400 });
      full = path.resolve(store.root, rel);
      const base = path.resolve(store.root);
      if (full !== base && !full.startsWith(`${base}${path.sep}`)) return new Response("bad path", { status: 400 });
    } else return new Response("not found", { status: 404 });
    if (!fs.existsSync(full)) return new Response("missing", { status: 404 });
    return net.fetch(pathToFileURL(full).href);
  });
}

async function collect(cfg) {
  const store = appPaths();
  const stamp = areas.stampToday();
  const request = cfg.request || {};
  const blocks = {};
  for (const area of cfg.areas || []) {
    if (area.enabled === false) continue;
    const name = area.title || area.id;
    sendLog(`→ ${name}`);
    const block = await fetchData.fetchArea(area, {
      stamp,
      cacheDir: store.cache,
      root: store.root,
      userAgent: request.user_agent,
      timeoutMs: Number(request.timeout || 20) * 1000,
    });
    if (block.ok === false) {
      sendLog(`  ✗ ${block.error}`);
      blocks[area.id] = { error: block.error };
    } else {
      sendLog("  ✓");
      blocks[area.id] = block;
    }
  }
  return blocks;
}

function capture(payload) {
  pendingRender = payload;
  const display = screen.getPrimaryDisplay();
  const dipW = Math.max(1, display.workAreaSize.width);
  const dipH = Math.max(1, display.workAreaSize.height);
  const win = new BrowserWindow({
    show: false,
    frame: false,
    useContentSize: true,
    width: dipW,
    height: dipH,
    backgroundColor: payload.theme.bg || "#0D1015",
    webPreferences: {
      offscreen: true,
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("截图超时"));
    }, 30000);
    const cleanup = () => {
      clearTimeout(timer);
      ipcMain.removeListener("wallpaper:ready", finish);
      if (!win.isDestroyed()) win.destroy();
    };
    const finish = async () => {
      if (win.isDestroyed()) return;
      try {
        await new Promise((done) => setTimeout(done, 160));
        const box = await win.webContents.executeJavaScript(`(() => {
          const node = document.querySelector(".board");
          const rect = node.getBoundingClientRect();
          return { left: rect.left, top: rect.top, width: rect.width, height: rect.height, viewW: window.innerWidth, viewH: window.innerHeight };
        })()`);
        const image = await win.webContents.capturePage();
        const size = image.getSize();
        const scaleX = size.width / box.viewW;
        const scaleY = size.height / box.viewH;
        const x = Math.max(0, Math.round(box.left * scaleX));
        const y = Math.max(0, Math.round(box.top * scaleY));
        const width = Math.max(1, Math.min(size.width - x, Math.round(box.width * scaleX)));
        const height = Math.max(1, Math.min(size.height - y, Math.round(box.height * scaleY)));
        const cropped = image.crop({ x, y, width, height });
        const png = cropped.resize({ width: payload.width, height: payload.height, quality: "best" }).toPNG();
        cleanup();
        resolve(png);
      } catch (err) {
        cleanup();
        reject(err);
      }
    };
    ipcMain.once("wallpaper:ready", finish);
    loadPage(win, "#/wallpaper").catch((err) => {
      cleanup();
      reject(err);
    });
  });
}

async function generate(setWallpaperFlag) {
  if (generating) return { ok: false, error: "正在生成" };
  generating = true;
  try {
    const cfg = readConfig();
    sendLog("开始抓取");
    const blocks = await collect(cfg);
    sendLog("开始绘制");
    const payload = present.presentWallpaper(cfg, blocks);
    const png = await capture(payload);
    const store = appPaths();
    fs.mkdirSync(store.output, { recursive: true });
    const dated = path.join(store.output, `wallpaper_${new Date().toISOString().slice(0, 10)}.png`);
    fs.writeFileSync(store.png, png);
    fs.writeFileSync(dated, png);
    sendLog(`已写出 ${store.png}`);
    if (setWallpaperFlag) {
      const style = (cfg.output && cfg.output.wallpaper_style) || "Fill";
      const set = await schedule.setWallpaper(store.ps1, store.png, style);
      if (!set.ok) {
        sendLog(set.error);
        return { ok: false, error: set.error, preview: previewUrl() };
      }
      sendLog("已设为桌面壁纸");
    }
    return { ok: true, preview: previewUrl() };
  } catch (err) {
    sendLog(String(err && err.message || err));
    return { ok: false, error: String(err && err.message || err) };
  } finally {
    generating = false;
    pendingRender = null;
  }
}

function previewUrl() {
  const png = appPaths().png;
  if (!fs.existsSync(png)) return "";
  return `media://output/today.png?t=${Date.now()}`;
}

function createComposer() {
  composer = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: "壁纸配置",
    backgroundColor: "#101318",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  loadPage(composer, "#/");
  composer.on("closed", () => { composer = null; });
}

function displayList() {
  const primaryId = screen.getPrimaryDisplay().id;
  return screen.getAllDisplays().map((display) => {
    const factor = display.scaleFactor || 1;
    const width = Math.round(display.size.width * factor);
    const height = Math.round(display.size.height * factor);
    const workH = Math.round(display.workAreaSize.height * factor);
    return {
      width,
      height,
      primary: display.id === primaryId,
      taskbar: Math.max(0, height - workH),
    };
  });
}

function registerIpc() {
  ipcMain.handle("config:get", () => ({ ...readConfig(), displays: displayList() }));
  ipcMain.handle("config:save", (_event, payload) => saveIncoming(payload));
  ipcMain.handle("probe", async (_event, area) => {
    const cfg = readConfig();
    const request = cfg.request || {};
    const normalized = areas.normalizeArea(area);
    if (normalized.source !== "api") {
      return { status: "fail", kind: "error", message: "只有接接口的区域可以测试", truncated: false };
    }
    const block = await fetchData.fetchArea(normalized, {
      stamp: areas.stampToday(),
      cacheDir: appPaths().cache,
      root: appPaths().root,
      userAgent: request.user_agent,
      timeoutMs: Number(request.timeout || 20) * 1000,
      probe: true,
    });
    return fetchData.probeView(block);
  });
  ipcMain.handle("generate", (_event, options) => generate(!!(options && options.setWallpaper)));
  ipcMain.handle("task:status", () => schedule.taskStatus((readConfig().schedule || {}).task_name || "DailyWallpaper"));
  ipcMain.handle("task:install", async (_event, dailyTime) => {
    const cfg = readConfig();
    if (dailyTime && /^([01]\d|2[0-3]):[0-5]\d$/.test(dailyTime)) {
      cfg.schedule.daily_time = dailyTime;
      writeConfig(cfg);
    }
    return schedule.taskInstall(cfg.schedule.task_name, cfg.schedule.daily_time, launchCommand(), applyCommand());
  });
  ipcMain.handle("task:remove", () => schedule.taskRemove((readConfig().schedule || {}).task_name || "DailyWallpaper"));
  ipcMain.handle("preview:url", () => previewUrl());
  ipcMain.handle("render:payload", () => pendingRender);
}

app.whenReady().then(async () => {
  registerMedia();
  registerIpc();
  if (headless) {
    const result = await generate(true);
    if (!result.ok) console.error(result.error || "生成失败");
    app.exit(result.ok ? 0 : 1);
    return;
  }
  createComposer();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createComposer();
  });
});

app.on("window-all-closed", () => {
  if (!headless) app.quit();
});
