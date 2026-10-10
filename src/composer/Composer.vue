<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import areaLib from "../../shared/areas.js";

const { dig, exampleAreas, metrics, rect } = areaLib;
import TreeNode from "./TreeNode.vue";
import "../styles.css";

const SOURCE = {
  blank: { label: "空白", color: "#6b7480" },
  text: { label: "纯文字", color: "#5dcaa5" },
  image: { label: "纯图片", color: "#e89ab0" },
  api: { label: "接接口", color: "#5b9be8" },
};
const EFFECT = {
  text: { label: "文字" },
  list: { label: "列表" },
  image: { label: "图片" },
  bar: { label: "进度条" },
  fields: { label: "字段组" },
};
const PRESETS = ["1920,1080", "2560,1440", "3840,2160"];
const displays = ref([]);

const missingApi = ref(false);
const status = ref("正在读取配置…");
const bad = ref(false);
const busy = ref(false);
const mode = ref("grid");
const taskOpen = ref(false);
const log = ref("");
const preview = ref("");
const scale = ref(1);
const selectedId = ref(null);
const bind = ref(null);
const openShow = ref(null);
function fitSoon() {
  nextTick(() => {
    if (wrapEl.value) void wrapEl.value.offsetHeight;
    fit();
  });
}
watch(selectedId, () => {
  openShow.value = null;
  fitSoon();
});
watch(mode, fitSoon);
const dirty = ref(false);
const probes = reactive({});
const raw = ref(null);
const resolution = ref([2560, 1440]);
const grid = reactive({ cols: 12, rows: 8, gap: 20, margin: 40, taskbar: 48 });
const areas = ref([]);
const schedule = reactive({ daily_time: "06:00", task_name: "DailyWallpaper" });
const taskInfo = ref("正在查询计划任务…");
const preset = ref("2560,1440");
const stageEl = ref(null);
const wrapEl = ref(null);
let offLog = () => {};

const examples = computed(() => (raw.value ? exampleAreas(raw.value) : []));
const resolutionOptions = computed(() => {
  const options = [];
  const seen = new Set();
  for (const display of displays.value) {
    const value = `${display.width},${display.height}`;
    const label = `${display.width} × ${display.height}${display.primary ? "（当前屏幕）" : "（另一块屏幕）"}`;
    if (seen.has(value)) {
      if (display.primary) {
        const existing = options.find((item) => item.value === value);
        if (existing) existing.label = label;
      }
      continue;
    }
    seen.add(value);
    options.push({ value, label });
  }
  for (const value of PRESETS) {
    if (seen.has(value)) continue;
    options.push({ value, label: value.replace(",", " × ") });
  }
  options.push({ value: "custom", label: "自定义" });
  return options;
});
const g = computed(() => metrics(grid, resolution.value));
const selected = computed(() => areas.value.find((item) => item.id === selectedId.value) || null);
watch(() => selected.value && selected.value.source, fitSoon);
const activeShow = computed(() => {
  const area = selected.value;
  if (!area || openShow.value == null) return null;
  return area.shows[openShow.value] || null;
});
const cellCount = computed(() => g.value.cols * g.value.rows);

function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

function setStatus(text, isBad = false) {
  status.value = text;
  bad.value = isBad;
}

function markDirty() {
  dirty.value = true;
  setStatus("有未保存的修改");
}

function nid() {
  return `b${Math.random().toString(36).slice(2, 8)}`;
}

function hydrate(area) {
  const next = area;
  next.api = next.api || { url: "" };
  if (!next.api.queryRows) {
    const rows = Object.entries(next.api.query || {}).map(([key, value]) => ({ key, value: String(value ?? "") }));
    next.api.queryRows = rows.length ? rows : [{ key: "", value: "" }];
  }
  next.style = {
    size: "m",
    align: "left",
    color: "text",
    showTitle: true,
    ...(next.style || {}),
  };
  next.shows = next.shows || [];
  next.sheet = areaLib.sheetFromShows(next.shows, next.sheet);
  next.shows.forEach((show, index) => {
    if (!show.cell) show.cell = { col: 0, row: index, colSpan: next.sheet.cols, rowSpan: 1 };
    if (!show.look) show.look = { size: 22, align: "left", color: "text" };
  });
  next.content = next.content || "";
  next.image = next.image || "";
  return next;
}

function effectMeta(area) {
  if (!area || !area.source) return { label: "区域", color: "#d7dee8" };
  if (area.source !== "api") return SOURCE[area.source] || SOURCE.blank;
  const first = (area.shows || [])[0];
  return { label: (EFFECT[first && first.effect] || {}).label || SOURCE.api.label, color: SOURCE.api.color };
}

function endpoint(area) {
  if (!area.source) return "先选内容";
  if (area.source === "blank") return "空白";
  if (area.source === "text") return (area.content || "").trim().slice(0, 28) || "纯文字";
  if (area.source === "image") return ((area.image || "").trim().split("/").pop()) || "纯图片";
  let host = "";
  const url = area.api && area.api.url;
  if (url) {
    try { host = new URL(url).host; } catch { host = "地址还不能用"; }
  }
  const names = (area.shows || []).map((show) => EFFECT[show.effect] && EFFECT[show.effect].label).filter(Boolean);
  const kind = names.length ? names.join("、") : "还没选展示";
  return host ? `${host} · ${kind}` : kind;
}

function cardStyle(area) {
  const [x0, y0, x1, y1] = rect(grid, resolution.value, area);
  return {
    left: `${x0}px`,
    top: `${y0}px`,
    width: `${x1 - x0}px`,
    height: `${y1 - y0}px`,
    borderColor: effectMeta(area).color,
    "--title": "36px",
    "--sub": "22px",
  };
}

function overlaps(area) {
  return areas.value.some((other) => {
    if (other.id === area.id) return false;
    return area.col < other.col + other.colSpan
      && other.col < area.col + area.colSpan
      && area.row < other.row + other.rowSpan
      && other.row < area.row + area.rowSpan;
  });
}

function point(ev) {
  const br = stageEl.value.getBoundingClientRect();
  const board = g.value;
  return {
    x: ((ev.clientX - br.left) / br.width) * board.W,
    y: ((ev.clientY - br.top) / br.height) * board.H,
  };
}

function cellAt(ev) {
  const board = g.value;
  const { x, y } = point(ev);
  return {
    col: clamp(Math.floor((x - board.margin) / (board.cellW + board.gap)), 0, board.cols - 1),
    row: clamp(Math.floor((y - board.margin) / (board.cellH + board.gap)), 0, board.rows - 1),
  };
}

function blankCustom(slot) {
  return hydrate({
    id: nid(),
    type: "custom",
    source: "",
    title: "",
    enabled: true,
    col: slot.col,
    row: slot.row,
    colSpan: slot.colSpan || 1,
    rowSpan: slot.rowSpan || 1,
    bleed: false,
    api: { url: "", query: {}, queryRows: [{ key: "", value: "" }] },
    shows: [],
  });
}

function findSlot(colSpan, rowSpan) {
  const board = g.value;
  const w = Math.min(colSpan, board.cols);
  const h = Math.min(rowSpan, board.rows);
  for (let row = 0; row <= board.rows - h; row += 1) {
    for (let col = 0; col <= board.cols - w; col += 1) {
      const trial = { id: "_", col, row, colSpan: w, rowSpan: h };
      if (!overlaps(trial)) return trial;
    }
  }
  return null;
}

function select(id) {
  selectedId.value = id;
  mode.value = "grid";
}

function addCustom() {
  const slot = findSlot(1, 1);
  if (!slot) {
    setStatus("网格上没有空位了", true);
    return;
  }
  const area = blankCustom(slot);
  areas.value.push(area);
  markDirty();
  select(area.id);
}

function addExample(sample) {
  const slot = findSlot(sample.colSpan || 4, sample.rowSpan || 2);
  if (!slot) {
    setStatus(`${sample.label} 放不下了，先腾出 ${sample.colSpan}×${sample.rowSpan} 的空位`, true);
    return;
  }
  const area = hydrate(JSON.parse(JSON.stringify(sample)));
  delete area.label;
  delete area.color;
  area.id = nid();
  area.col = slot.col;
  area.row = slot.row;
  areas.value.push(area);
  markDirty();
  select(area.id);
  setStatus(`已放入「${sample.label}」。点保存后才会写入。`);
}

function loadExamples() {
  if (!examples.value.length) return;
  if (areas.value.length && !window.confirm("当前区块会换成六块示例。")) return;
  if (grid.cols < 12) grid.cols = 12;
  if (grid.rows < 8) grid.rows = 8;
  areas.value = examples.value.map((item) => hydrate(JSON.parse(JSON.stringify(item))));
  selectedId.value = areas.value[0] ? areas.value[0].id : null;
  mode.value = "grid";
  markDirty();
  setStatus("已载入六块示例。点「只保存」后，计划任务才会用这份布局。");
}

function removeArea(area) {
  areas.value = areas.value.filter((item) => item.id !== area.id);
  selectedId.value = null;
  if (bind.value && bind.value.id === area.id) bind.value = null;
  markDirty();
}

function setSource(area, source) {
  if (area.source === source) return;
  area.source = source;
  if (source === "api") area.api = area.api || { url: "", queryRows: [{ key: "", value: "" }] };
  bind.value = null;
  markDirty();
}

function dropQuery(area, index) {
  area.api.queryRows.splice(index, 1);
  if (!area.api.queryRows.length) area.api.queryRows.push({ key: "", value: "" });
  syncQuery(area);
  markDirty();
}

function syncQuery(area) {
  const query = {};
  for (const row of area.api.queryRows || []) {
    const key = String(row.key || "").trim();
    const value = String(row.value ?? "").trim();
    if (key && value) query[key] = value;
  }
  area.api.query = query;
}

const suffixOpen = ref(new Set());

function suffixKey(showIndex, rowIndex) {
  return rowIndex == null ? `s${showIndex}` : `s${showIndex}r${rowIndex}`;
}

function suffixVisible(owner, showIndex, rowIndex) {
  return !!(owner.after && String(owner.after).length) || suffixOpen.value.has(suffixKey(showIndex, rowIndex));
}

function openSuffix(showIndex, rowIndex) {
  const key = suffixKey(showIndex, rowIndex);
  const next = new Set(suffixOpen.value);
  next.add(key);
  suffixOpen.value = next;
  nextTick(() => {
    document.querySelector(`[data-suffix="${key}"]`)?.focus();
  });
}

function closeSuffixIfEmpty(owner, showIndex, rowIndex) {
  if (owner.after && String(owner.after).length) return;
  const next = new Set(suffixOpen.value);
  next.delete(suffixKey(showIndex, rowIndex));
  suffixOpen.value = next;
}

const SIZES = [18, 22, 28, 34, 52];
const NAMED_HEX = {
  text: "#EAEDF3",
  dim: "#9AA4B5",
  hint: "#6B7480",
  accent: "#5B9BE8",
  warn: "#E8B04B",
  ok: "#5DCAA5",
};

function normalizeHex(raw) {
  let text = String(raw || "").trim();
  if (!text) return "";
  if (!text.startsWith("#")) text = `#${text}`;
  if (/^#[0-9a-fA-F]{3}$/.test(text)) {
    const [r, g, b] = text.slice(1);
    text = `#${r}${r}${g}${g}${b}${b}`;
  }
  if (/^#[0-9a-fA-F]{8}$/.test(text)) return text.toUpperCase();
  return /^#[0-9a-fA-F]{6}$/.test(text) ? text.toUpperCase() : "";
}

function colorHex(show) {
  const color = show && show.look && show.look.color;
  return normalizeHex(color) || NAMED_HEX[color] || "#EAEDF3";
}

function setLookColor(show, raw, event) {
  const next = normalizeHex(raw);
  if (!next) {
    if (event && event.target) event.target.value = colorHex(show);
    return;
  }
  show.look.color = next;
  markDirty();
}

function emptyShow(effect) {
  const base = { cell: { col: 0, row: 0, colSpan: 1, rowSpan: 1 }, look: { size: 22, align: "left", color: "text" } };
  if (effect === "list") return { effect, items: "", item: "", limit: 7, ...base };
  if (effect === "fields") return { effect, rows: [{ label: "", path: "" }], ...base };
  if (effect === "bar") return { effect, path: "", max: 100, label: "", ...base };
  if (effect === "image") return { effect, path: "", ...base };
  return { effect: "text", path: "", ...base };
}

function showSummary(show) {
  if (!show) return "";
  const cell = show.cell || {};
  const place = `${(Number(cell.col) || 0) + 1},${(Number(cell.row) || 0) + 1}`;
  const size = show.look && show.look.size ? `${show.look.size}` : "";
  const head = [place, size].filter(Boolean).join(" · ");
  if (show.effect === "fields") {
    const ready = (show.rows || []).filter((row) => String(row.path || "").trim()).length;
    return `${head} · ${ready ? `${ready} 个字段` : "还没填字段"}`;
  }
  if (show.effect === "list") {
    const where = String(show.items || "").trim() || "整段数组";
    const item = String(show.item || "").trim();
    return `${head} · ${item ? `${where} · ${item}` : where}`;
  }
  const path = String(show.path || "").trim();
  if (show.effect === "text") {
    const bits = [path || "整段文字"];
    if (show.form === "date") bits.push("日期");
    if (show.after) bits.push(show.after);
    return `${head} · ${bits.join(" · ")}`;
  }
  if (show.effect === "image") return `${head} · ${path || "直接用返回的图片"}`;
  if (show.effect === "bar") return `${head} · ${[show.label, path || "还没填路径"].filter(Boolean).join(" · ")}`;
  return head;
}

function setCell(show, key, raw, area) {
  const sheet = area.sheet || { cols: 1, rows: 1 };
  const span = key === "colSpan" || key === "rowSpan";
  const max = key === "col" || key === "colSpan" ? sheet.cols : sheet.rows;
  let number = Math.trunc(Number(raw));
  if (!Number.isFinite(number)) number = span ? 1 : 1;
  if (span) number = Math.max(1, Math.min(max, number));
  else number = Math.max(0, Math.min(max - 1, number - 1));
  show.cell[key] = number;
  if (key === "col") show.cell.colSpan = Math.min(show.cell.colSpan || 1, sheet.cols - show.cell.col);
  if (key === "row") show.cell.rowSpan = Math.min(show.cell.rowSpan || 1, sheet.rows - show.cell.row);
  markDirty();
}

function clampSheet(area) {
  area.sheet.cols = Math.max(1, Math.min(8, Math.trunc(Number(area.sheet.cols) || 1)));
  area.sheet.rows = Math.max(1, Math.min(12, Math.trunc(Number(area.sheet.rows) || 1)));
  for (const show of area.shows || []) {
    if (!show.cell) show.cell = { col: 0, row: 0, colSpan: 1, rowSpan: 1 };
    show.cell.col = Math.max(0, Math.min(area.sheet.cols - 1, show.cell.col || 0));
    show.cell.row = Math.max(0, Math.min(area.sheet.rows - 1, show.cell.row || 0));
    show.cell.colSpan = Math.max(1, Math.min(area.sheet.cols - show.cell.col, show.cell.colSpan || 1));
    show.cell.rowSpan = Math.max(1, Math.min(area.sheet.rows - show.cell.row, show.cell.rowSpan || 1));
  }
  markDirty();
}

function changeEffect(area, index, effect) {
  const prev = area.shows[index];
  const next = emptyShow(effect);
  next.cell = prev.cell || next.cell;
  next.look = prev.look || next.look;
  if (prev.path && (effect === "text" || effect === "image" || effect === "bar")) next.path = prev.path;
  area.shows.splice(index, 1, next);
  bind.value = null;
  markDirty();
}

function moveShow(area, index, dir) {
  const next = index + dir;
  const [item] = area.shows.splice(index, 1);
  area.shows.splice(next, 0, item);
  if (openShow.value === index) openShow.value = next;
  else if (openShow.value === next) openShow.value = index;
  bind.value = null;
  markDirty();
}

function dropShow(area, index) {
  area.shows.splice(index, 1);
  bind.value = null;
  if (openShow.value === index) openShow.value = null;
  else if (openShow.value > index) openShow.value -= 1;
  markDirty();
}

function showAt(area, col, row) {
  return (area.shows || []).findIndex((show) => {
    const cell = show.cell || {};
    const spanC = cell.colSpan || 1;
    const spanR = cell.rowSpan || 1;
    return col >= (cell.col || 0) && col < (cell.col || 0) + spanC
      && row >= (cell.row || 0) && row < (cell.row || 0) + spanR;
  });
}

function pickSlot(area, index) {
  const cols = area.sheet.cols;
  const col = index % cols;
  const row = Math.floor(index / cols);
  const found = showAt(area, col, row);
  if (found >= 0) {
    openShow.value = found;
    return;
  }
  if ((area.shows || []).length >= 8) {
    setStatus("一块区域最多 8 条展示", true);
    return;
  }
  const show = emptyShow("text");
  show.cell = { col, row, colSpan: 1, rowSpan: 1 };
  area.shows.push(show);
  openShow.value = area.shows.length - 1;
  markDirty();
}

function slotStyle(area, index) {
  const cols = area.sheet.cols || 1;
  return {
    gridColumn: (index % cols) + 1,
    gridRow: Math.floor(index / cols) + 1,
  };
}

function miniStyle(show) {
  const cell = show.cell || { col: 0, row: 0, colSpan: 1, rowSpan: 1 };
  return {
    gridColumn: `${(cell.col || 0) + 1} / span ${cell.colSpan || 1}`,
    gridRow: `${(cell.row || 0) + 1} / span ${cell.rowSpan || 1}`,
  };
}

function cellLabel(show) {
  if (show.effect === "bar") return show.label || "进度条";
  if (show.effect === "fields") return "字段";
  if (show.effect === "list") return "列表";
  if (show.effect === "image") return "图片";
  const path = String(show.path || "").trim();
  return path ? path.split(".").pop() : "文字";
}

function addShow(area) {
  const show = emptyShow("text");
  if (!area.sheet) area.sheet = { cols: 1, rows: 1 };
  const row = area.shows.length;
  if (row >= area.sheet.rows && area.sheet.rows < 12) area.sheet.rows = row + 1;
  show.cell = { col: 0, row: Math.min(row, area.sheet.rows - 1), colSpan: area.sheet.cols, rowSpan: 1 };
  area.shows.push(show);
  openShow.value = area.shows.length - 1;
  markDirty();
}

function toggleBind(area, index, field, row = null) {
  const on = bind.value
    && bind.value.id === area.id
    && bind.value.index === index
    && bind.value.field === field
    && bind.value.row === row;
  bind.value = on ? null : { id: area.id, index, field, row };
}

function bindingOn(area, index, field, row = null) {
  return !!(bind.value
    && bind.value.id === area.id
    && bind.value.index === index
    && bind.value.field === field
    && bind.value.row === row);
}

function itemPath(items, path) {
  const base = (items || "").trim();
  if (base && (path === base || path.startsWith(`${base}.`))) {
    const rest = path.slice(base.length + 1).replace(/^\d+\./, "");
    return rest || path.split(".").pop();
  }
  return path.split(".").pop() || path;
}

function applyPath(path) {
  const area = selected.value;
  const spec = bind.value;
  if (!spec || !area || spec.id !== area.id) {
    setStatus("先点某条展示里的「点选」", true);
    return;
  }
  const show = area.shows[spec.index];
  if (!show) return;
  if (spec.field === "item") show.item = itemPath(show.items, path);
  else if (spec.field === "row" && show.rows && show.rows[spec.row]) show.rows[spec.row].path = path;
  else if (spec.field === "max") show.max = path || 100;
  else show[spec.field] = path;
  markDirty();
}

function sampleOf(area, path) {
  const probe = probes[area.id];
  if (!probe || probe.kind !== "json") return "";
  const value = path ? dig(probe.body, path) : probe.body;
  if (value === undefined) return "这次返回里没有这一项";
  if (value === null) return "空";
  if (typeof value === "string") return value.length > 60 ? `${value.slice(0, 60)}…` : value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return `数组 ${value.length} 项`;
  if (value && typeof value === "object") return "对象";
  return String(value);
}

function setMax(show, value) {
  const number = Number(value);
  show.max = value !== "" && Number.isFinite(number) && String(number) === value ? number : value;
  markDirty();
}

async function probeArea(area) {
  syncQuery(area);
  probes[area.id] = { status: "wait" };
  try {
    probes[area.id] = await window.wallpaper.probe(JSON.parse(JSON.stringify(area)));
  } catch (err) {
    probes[area.id] = { status: "fail", kind: "error", message: String(err) };
  }
}

function fit() {
  const board = g.value;
  const wrap = wrapEl.value;
  if (!wrap || !board.W || !board.H) return;
  scale.value = Math.min(wrap.clientWidth / board.W, wrap.clientHeight / board.H) * 0.92 || 1;
}

function onGridInput() {
  grid.cols = clamp(Number(grid.cols) || 12, 4, 24);
  grid.rows = clamp(Number(grid.rows) || 8, 4, 24);
  grid.gap = clamp(Number(grid.gap) || 0, 0, 80);
  grid.margin = clamp(Number(grid.margin) || 0, 0, 240);
  grid.taskbar = clamp(Number(grid.taskbar) || 0, 0, 200);
  const board = metrics(grid, resolution.value);
  for (const area of areas.value) {
    area.colSpan = clamp(area.colSpan, 1, board.cols);
    area.rowSpan = clamp(area.rowSpan, 1, board.rows);
    area.col = clamp(area.col, 0, board.cols - area.colSpan);
    area.row = clamp(area.row, 0, board.rows - area.rowSpan);
  }
  markDirty();
  fit();
}

function onPreset() {
  if (preset.value === "custom") return;
  resolution.value = preset.value.split(",").map(Number);
  const picked = displays.value.find((item) => item.primary && `${item.width},${item.height}` === preset.value)
    || displays.value.find((item) => `${item.width},${item.height}` === preset.value);
  if (picked && picked.taskbar > 0 && picked.taskbar <= 200) grid.taskbar = picked.taskbar;
  markDirty();
  fit();
}

function onCustomRes() {
  resolution.value = [
    clamp(Number(resolution.value[0]) || 2560, 800, 7680),
    clamp(Number(resolution.value[1]) || 1440, 600, 4320),
  ];
  markDirty();
  fit();
}

function startDrag(ev, area, dragMode) {
  if (ev.button !== 0) return;
  ev.preventDefault();
  ev.stopPropagation();
  selectedId.value = area.id;
  const origin = { col: area.col, row: area.row, colSpan: area.colSpan, rowSpan: area.rowSpan };
  const start = cellAt(ev);
  const move = (e) => {
    const cell = cellAt(e);
    const board = g.value;
    if (dragMode === "move") {
      area.col = clamp(origin.col + cell.col - start.col, 0, board.cols - area.colSpan);
      area.row = clamp(origin.row + cell.row - start.row, 0, board.rows - area.rowSpan);
    } else {
      area.colSpan = clamp(cell.col - origin.col + 1, 1, board.cols - origin.col);
      area.rowSpan = clamp(cell.row - origin.row + 1, 1, board.rows - origin.row);
    }
    area._bad = overlaps(area);
  };
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    const changed = area.col !== origin.col || area.row !== origin.row
      || area.colSpan !== origin.colSpan || area.rowSpan !== origin.rowSpan;
    if (area._bad) Object.assign(area, origin);
    else if (changed) markDirty();
    delete area._bad;
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function startBox(ev) {
  if (mode.value !== "grid" || ev.button !== 0) return;
  const start = cellAt(ev);
  const area = blankCustom(start);
  areas.value.push(area);
  selectedId.value = area.id;
  const move = (e) => {
    const cell = cellAt(e);
    area.col = Math.min(start.col, cell.col);
    area.row = Math.min(start.row, cell.row);
    area.colSpan = Math.abs(cell.col - start.col) + 1;
    area.rowSpan = Math.abs(cell.row - start.row) + 1;
    area._bad = overlaps(area);
  };
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    delete area._bad;
    if (overlaps(area)) {
      areas.value = areas.value.filter((item) => item.id !== area.id);
      selectedId.value = null;
      setStatus("这块和已有区域重叠了", true);
    } else markDirty();
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

async function save() {
  for (const area of areas.value) {
    if (area.source === "api") syncQuery(area);
  }
  const result = await window.wallpaper.saveConfig({
    resolution: resolution.value.map(Number),
    grid: { ...grid },
    areas: JSON.parse(JSON.stringify(areas.value)),
    schedule: { daily_time: schedule.daily_time, task_name: schedule.task_name },
  });
  if (!result.ok) {
    setStatus((result.errors || ["保存失败"]).join("；"), true);
    return false;
  }
  raw.value = result.config;
  areas.value = result.config.areas.map((item) => hydrate(item));
  schedule.daily_time = result.config.schedule.daily_time;
  schedule.task_name = result.config.schedule.task_name;
  dirty.value = false;
  setStatus("已保存。到点的计划任务会用这份布局。");
  return true;
}

async function generate() {
  const ok = await save();
  if (!ok) return;
  busy.value = true;
  log.value = "";
  setStatus("正在生成…");
  const result = await window.wallpaper.generate({ setWallpaper: true });
  busy.value = false;
  if (result.ok) {
    preview.value = result.preview;
    mode.value = "preview";
    setStatus("已设为桌面壁纸");
  } else {
    setStatus(result.error || "生成失败。右边是日志。", true);
  }
}

async function installTask() {
  const ok = await save();
  if (!ok) return;
  const info = await window.wallpaper.taskInstall(schedule.daily_time);
  if (!info.ok) setStatus(info.error || "安装计划任务失败", true);
  else {
    setStatus("计划任务已更新");
    showTask(info);
  }
}

async function removeTask() {
  const info = await window.wallpaper.taskRemove();
  if (!info.ok) setStatus(info.error || "删除计划任务失败", true);
  else {
    setStatus("计划任务已删除");
    showTask(info);
  }
}

async function runNow() {
  if (!window.confirm("现在跑一次会按已保存的配置重新出图，并换成桌面壁纸。")) return;
  taskOpen.value = false;
  await generate();
}

function showTask(info) {
  if (!info || info.error && !info.installed) {
    taskInfo.value = info && info.error ? info.error : "这台电脑上还没有每日任务。";
    return;
  }
  if (!info.installed) {
    taskInfo.value = "这台电脑上还没有每日任务。";
    return;
  }
  taskInfo.value = `${info.name} · ${info.state} · 下次 ${info.next || "—"}`;
}

function onKey(ev) {
  if (ev.key === "Escape" && taskOpen.value) {
    taskOpen.value = false;
    return;
  }
  if (ev.target.closest("input, textarea, select")) return;
  const area = selected.value;
  if (!area) return;
  const board = g.value;
  const prev = { col: area.col, row: area.row };
  if (ev.key === "ArrowLeft") area.col = clamp(area.col - 1, 0, board.cols - area.colSpan);
  if (ev.key === "ArrowRight") area.col = clamp(area.col + 1, 0, board.cols - area.colSpan);
  if (ev.key === "ArrowUp") area.row = clamp(area.row - 1, 0, board.rows - area.rowSpan);
  if (ev.key === "ArrowDown") area.row = clamp(area.row + 1, 0, board.rows - area.rowSpan);
  if (area.col === prev.col && area.row === prev.row) return;
  if (overlaps(area)) Object.assign(area, prev);
  else markDirty();
  ev.preventDefault();
}

function onDocClick(ev) {
  if (!taskOpen.value) return;
  if (ev.target.closest(".task-panel") || ev.target.closest("#task-open")) return;
  taskOpen.value = false;
}

function beforeUnload(ev) {
  if (!dirty.value) return;
  ev.preventDefault();
  ev.returnValue = "";
}

function syncPreset() {
  const key = resolution.value.join(",");
  preset.value = resolutionOptions.value.some((item) => item.value === key) ? key : "custom";
}

onMounted(async () => {
  window.addEventListener("keydown", onKey);
  window.addEventListener("resize", fit);
  document.addEventListener("click", onDocClick);
  window.addEventListener("beforeunload", beforeUnload);
  if (!window.wallpaper) {
    missingApi.value = true;
    setStatus("请用 Electron 打开这个配置台。", true);
    return;
  }
  offLog = window.wallpaper.onLog((line) => { log.value += `${line}\n`; });
  let cfg;
  try {
    cfg = await window.wallpaper.getConfig();
  } catch (err) {
    setStatus(String(err.message || err), true);
    return;
  }
  raw.value = cfg;
  displays.value = cfg.displays || [];
  resolution.value = cfg.resolution.map(Number);
  Object.assign(grid, cfg.grid);
  areas.value = (cfg.areas || []).map((item) => hydrate(item));
  schedule.daily_time = cfg.schedule.daily_time;
  schedule.task_name = cfg.schedule.task_name;
  const savedKey = resolution.value.join(",");
  const primary = displays.value.find((item) => item.primary);
  const matchesScreen = displays.value.some((item) => `${item.width},${item.height}` === savedKey);
  if (primary && !matchesScreen) {
    resolution.value = [primary.width, primary.height];
    if (primary.taskbar > 0 && primary.taskbar <= 200) grid.taskbar = primary.taskbar;
    dirty.value = true;
    syncPreset();
    setStatus(`分辨率 ${savedKey.replace(",", "×")} 和屏幕对不上，已改成当前屏幕 ${primary.width}×${primary.height}。点「设为壁纸」才会换上。`);
  } else {
    syncPreset();
    setStatus(areas.value.length
      ? "选中一块区域，改来源和展示。保存后才会写入配置。"
      : "在画布上拖出一块区域，或从示例里放一块。");
  }
  preview.value = await window.wallpaper.previewUrl();
  fit();
  showTask(await window.wallpaper.taskStatus());
  new ResizeObserver(fit).observe(wrapEl.value);
});

onUnmounted(() => {
  window.removeEventListener("keydown", onKey);
  window.removeEventListener("resize", fit);
  document.removeEventListener("click", onDocClick);
  window.removeEventListener("beforeunload", beforeUnload);
  offLog();
});
</script>

<template>
  <div class="shell">
    <header>
      <div class="brand">壁纸配置</div>
      <p id="status" :class="{ bad }">{{ status }}</p>
      <button id="task-open" type="button" :aria-expanded="taskOpen" @click="taskOpen = !taskOpen">计划任务</button>
      <button class="quiet" type="button" :disabled="busy || missingApi" @click="save">只保存</button>
      <button class="primary" type="button" :disabled="busy || missingApi" @click="generate">设为壁纸</button>
      <div v-show="taskOpen" class="task-panel">
        <h2>每日更新</h2>
        <p class="hint">到点启动本程序，不打开窗口，按已保存的配置设壁纸。</p>
        <label class="block">时间 <input v-model="schedule.daily_time" type="time" @change="markDirty"></label>
        <p class="hint">{{ taskInfo }}</p>
        <div class="row-buttons">
          <button type="button" :disabled="busy || missingApi" @click="installTask">安装 / 更新</button>
          <button type="button" :disabled="busy || missingApi" @click="runNow">现在跑一次</button>
          <button class="danger-text" type="button" :disabled="missingApi" @click="removeTask">删除</button>
        </div>
      </div>
    </header>
    <main>
      <aside class="side">
        <section>
          <h2>区块</h2>
          <button class="primary pal-add" type="button" @click="addCustom">添加区块</button>
        </section>
        <section>
          <h2>示例</h2>
          <p class="hint">在画布上拖出一块区域，再选空白、纯文字、纯图片或接接口。示例只是事先填好的配置。</p>
          <button v-for="sample in examples" :key="sample.id" class="pal-item" type="button" @click="addExample(sample)">
            <i :style="{ background: sample.color }"></i>{{ sample.label }}
          </button>
          <button id="load-example" class="text-btn" type="button" @click="loadExamples">载入全部示例</button>
        </section>
        <section>
          <h2>画面</h2>
          <label class="block">分辨率
            <select v-model="preset" @change="onPreset">
              <option v-for="item in resolutionOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <div v-show="preset === 'custom'" class="fields">
            <label>宽 <input v-model.number="resolution[0]" type="number" min="800" max="7680" @change="onCustomRes"></label>
            <label>高 <input v-model.number="resolution[1]" type="number" min="600" max="4320" @change="onCustomRes"></label>
          </div>
          <label class="block">任务栏高度 <input v-model.number="grid.taskbar" type="number" min="0" max="200" @change="onGridInput"></label>
          <details>
            <summary>更多</summary>
            <div class="fields">
              <label>列 <input v-model.number="grid.cols" type="number" min="4" max="24" @change="onGridInput"></label>
              <label>行 <input v-model.number="grid.rows" type="number" min="4" max="24" @change="onGridInput"></label>
              <label>间距 <input v-model.number="grid.gap" type="number" min="0" max="80" @change="onGridInput"></label>
              <label>边距 <input v-model.number="grid.margin" type="number" min="0" max="240" @change="onGridInput"></label>
            </div>
          </details>
        </section>
      </aside>
      <div class="board-col" :class="{ focus: mode === 'grid' && selected && selected.source === 'api' }">
      <div ref="wrapEl" class="stage-wrap">
        <div class="modes">
          <button type="button" :class="{ on: mode === 'grid' }" @click="mode = 'grid'">布局</button>
          <button type="button" :class="{ on: mode === 'preview' }" @click="mode = 'preview'">成图</button>
        </div>
        <div
          id="stage"
          ref="stageEl"
          :style="{ width: g.W + 'px', height: g.H + 'px', transform: `translate(-50%, -50%) scale(${scale})` }"
        >
          <div
            v-show="mode === 'grid'"
            id="cells"
            :style="{ left: g.margin + 'px', top: g.margin + 'px', width: g.innerW + 'px', height: g.innerH + 'px', gridTemplateColumns: `repeat(${g.cols}, 1fr)`, gridTemplateRows: `repeat(${g.rows}, 1fr)`, gap: g.gap + 'px' }"
            @pointerdown="startBox"
          >
            <div v-for="index in cellCount" :key="index" class="cell"></div>
          </div>
          <div v-show="mode === 'grid'" id="cards">
            <div
              v-for="area in areas"
              :key="area.id"
              class="card"
              :class="{ on: area.id === selectedId, off: area.enabled === false, bad: area._bad }"
              :style="cardStyle(area)"
              @pointerdown="startDrag($event, area, 'move')"
            >
              <b :style="{ fontSize: 'var(--title)' }">{{ area.title || effectMeta(area).label }}</b>
              <span :style="{ fontSize: 'var(--sub)' }">{{ endpoint(area) }}</span>
              <div class="handle" @pointerdown="startDrag($event, area, 'resize')"></div>
            </div>
          </div>
          <div
            v-show="mode === 'grid'"
            id="taskbar-mask"
            :style="{ top: g.safe + 'px', height: g.taskbar + 'px' }"
          >{{ g.taskbar ? `任务栏 ${g.taskbar}px，这里不会出现在屏幕上` : "" }}</div>
          <img v-show="mode === 'preview'" id="shot" :src="preview" alt="最近一次生成的壁纸">
        </div>
      </div>
      <section v-show="mode === 'grid'" class="dock">
        <template v-if="!selected">
          <p class="hint dock-empty">选中画布上的一块区域，在这里选类型，并配置它里面的栅格。</p>
        </template>
        <template v-else>
          <div class="dock-bar">
            <h2>{{ selected.title || "这块区域" }}</h2>
            <div class="source-choices">
              <button
                v-for="(meta, key) in SOURCE"
                :key="key"
                type="button"
                :class="{ on: selected.source === key }"
                @click="setSource(selected, key)"
              >{{ meta.label }}</button>
            </div>
            <div v-if="selected.source === 'api'" class="sheet-size">
              <label>列 <input v-model.number="selected.sheet.cols" type="number" min="1" max="8" @change="clampSheet(selected)"></label>
              <label>行 <input v-model.number="selected.sheet.rows" type="number" min="1" max="12" @change="clampSheet(selected)"></label>
            </div>
          </div>
          <p v-if="selected.source !== 'api'" class="hint">{{ selected.source === "blank" ? "空白只占格子。" : "文字和图片在右侧填写。接接口后，才能在栅格里分格展示。" }}</p>
          <div v-if="selected.source === 'api'" class="dock-body">
          <div class="dock-sheet">
            <div
              class="mini-sheet"
              :style="{ gridTemplateColumns: `repeat(${selected.sheet.cols}, minmax(0, 1fr))`, gridTemplateRows: `repeat(${selected.sheet.rows}, minmax(0, 1fr))` }"
            >
              <button
                v-for="index in selected.sheet.cols * selected.sheet.rows"
                :key="'slot' + index"
                class="mini-slot"
                type="button"
                :style="slotStyle(selected, index - 1)"
                :aria-label="`第 ${index} 格`"
                @click="pickSlot(selected, index - 1)"
              ></button>
              <button
                v-for="(show, index) in selected.shows"
                :key="'show' + index"
                class="mini-show"
                type="button"
                :class="{ on: openShow === index }"
                :style="miniStyle(show)"
                @click="openShow = index"
              >{{ cellLabel(show) }}</button>
            </div>
          </div>
          <div v-if="selected.source === 'api'" class="dock-edit">
            <p v-if="!activeShow" class="hint">点一格，设置这一格的字号、对齐、颜色和内容。空格会新加一条文字。</p>
            <template v-else>
              <div class="show-head">
                <select :value="activeShow.effect" aria-label="展示类型" @change="changeEffect(selected, openShow, $event.target.value)">
                  <option v-for="(meta, key) in EFFECT" :key="key" :value="key">{{ meta.label }}</option>
                </select>
                <button class="mini" type="button" @click="dropShow(selected, openShow)">去掉这一格</button>
              </div>
              <div class="cell-fields">
                <label>列 <input :value="activeShow.cell.col + 1" type="number" min="1" :max="selected.sheet.cols" @change="setCell(activeShow, 'col', $event.target.value, selected)"></label>
                <label>行 <input :value="activeShow.cell.row + 1" type="number" min="1" :max="selected.sheet.rows" @change="setCell(activeShow, 'row', $event.target.value, selected)"></label>
                <label>宽 <input :value="activeShow.cell.colSpan" type="number" min="1" :max="selected.sheet.cols" @change="setCell(activeShow, 'colSpan', $event.target.value, selected)"></label>
                <label>高 <input :value="activeShow.cell.rowSpan" type="number" min="1" :max="selected.sheet.rows" @change="setCell(activeShow, 'rowSpan', $event.target.value, selected)"></label>
              </div>
              <div class="look-fields">
                <label>字号
                  <select v-model.number="activeShow.look.size" @change="markDirty">
                    <option v-for="size in SIZES" :key="size" :value="size">{{ size }}</option>
                  </select>
                </label>
                <label>对齐
                  <select v-model="activeShow.look.align" @change="markDirty">
                    <option value="left">靠左</option>
                    <option value="center">居中</option>
                    <option value="right">靠右</option>
                  </select>
                </label>
                <label>颜色
                  <span class="color-pick">
                    <input type="color" :value="colorHex(activeShow).slice(0, 7)" aria-label="选颜色" @input="setLookColor(activeShow, $event.target.value)">
                    <input :value="colorHex(activeShow)" type="text" spellcheck="false" maxlength="9" aria-label="色号" @change="setLookColor(activeShow, $event.target.value, $event)">
                  </span>
                </label>
              </div>
              <template v-if="activeShow.effect === 'text' || activeShow.effect === 'image' || activeShow.effect === 'bar'">
                <div class="line">
                  <input v-model="activeShow.path" type="text" spellcheck="false" :aria-label="activeShow.effect === 'image' ? '图片路径' : '取值路径'" :placeholder="activeShow.effect === 'text' ? '路径，纯文本留空' : (activeShow.effect === 'image' ? '路径，直接返回图片就留空' : '路径，如 data.progress')" :title="sampleOf(selected, activeShow.path)" @input="markDirty">
                  <button class="mini" type="button" :class="{ on: bindingOn(selected, openShow, 'path') }" @click="toggleBind(selected, openShow, 'path')">
                    {{ bindingOn(selected, openShow, "path") ? "点选中" : "点选" }}
                  </button>
                </div>
                <p v-if="activeShow.path && sampleOf(selected, activeShow.path)" class="sample-line">{{ sampleOf(selected, activeShow.path) }}</p>
              </template>
              <template v-if="activeShow.effect === 'text'">
                <div class="line" :class="{ lead: !suffixVisible(activeShow, openShow) }">
                  <input v-if="suffixVisible(activeShow, openShow)" v-model="activeShow.after" type="text" placeholder="后缀，如 °" aria-label="后缀" :data-suffix="suffixKey(openShow)" @input="markDirty" @blur="closeSuffixIfEmpty(activeShow, openShow)">
                  <button v-else class="mini" type="button" @click="openSuffix(openShow)">加后缀</button>
                  <select :value="activeShow.form || ''" aria-label="写法" @change="activeShow.form = $event.target.value; markDirty()">
                    <option value="">原样</option>
                    <option value="date">显示成日期</option>
                  </select>
                </div>
              </template>
              <template v-if="activeShow.effect === 'bar'">
                <div class="line spread">
                  <input v-model="activeShow.label" type="text" placeholder="名称" aria-label="名称" @input="markDirty">
                  <input :value="activeShow.max" type="text" placeholder="最大值，100 或另一条路径" aria-label="最大值" @input="setMax(activeShow, $event.target.value)">
                  <button class="mini" type="button" :class="{ on: bindingOn(selected, openShow, 'max') }" @click="toggleBind(selected, openShow, 'max')">
                    {{ bindingOn(selected, openShow, "max") ? "点选中" : "点选" }}
                  </button>
                </div>
              </template>
              <template v-if="activeShow.effect === 'list'">
                <div class="line">
                  <input v-model="activeShow.items" type="text" placeholder="列表路径，数组本身就留空" aria-label="列表路径" spellcheck="false" @input="markDirty">
                  <button class="mini" type="button" :class="{ on: bindingOn(selected, openShow, 'items') }" @click="toggleBind(selected, openShow, 'items')">
                    {{ bindingOn(selected, openShow, "items") ? "点选中" : "点选" }}
                  </button>
                </div>
                <div class="line trio">
                  <input v-model="activeShow.item" type="text" placeholder="每条里的文字，如 title" aria-label="每条里的文字" spellcheck="false" @input="markDirty">
                  <input v-model.number="activeShow.limit" class="limit" type="number" min="1" max="20" aria-label="最多条数" @input="markDirty">
                  <button class="mini" type="button" :class="{ on: bindingOn(selected, openShow, 'item') }" @click="toggleBind(selected, openShow, 'item')">
                    {{ bindingOn(selected, openShow, "item") ? "点选中" : "点选" }}
                  </button>
                </div>
              </template>
              <template v-if="activeShow.effect === 'fields'">
                <div class="colhead"><span>名称</span><span>路径</span></div>
                <div v-for="(row, rowIndex) in activeShow.rows" :key="rowIndex" class="line fields-line">
                  <input v-model="row.label" type="text" placeholder="名称" aria-label="名称" @input="markDirty">
                  <input v-model="row.path" type="text" placeholder="路径" aria-label="路径" spellcheck="false" :title="sampleOf(selected, row.path)" @input="markDirty">
                  <button class="mini" type="button" :class="{ on: bindingOn(selected, openShow, 'row', rowIndex) }" @click="toggleBind(selected, openShow, 'row', rowIndex)">
                    {{ bindingOn(selected, openShow, "row", rowIndex) ? "点选中" : "点选" }}
                  </button>
                  <input v-if="suffixVisible(row, openShow, rowIndex)" v-model="row.after" class="suffix" type="text" placeholder="后缀" aria-label="后缀" :data-suffix="suffixKey(openShow, rowIndex)" @input="markDirty" @blur="closeSuffixIfEmpty(row, openShow, rowIndex)">
                  <button v-else class="mini" type="button" @click="openSuffix(openShow, rowIndex)">后缀</button>
                </div>
                <button v-if="activeShow.rows.length < 8" class="text-btn" type="button" @click="activeShow.rows.push({ label: '', path: '' }); markDirty()">加一个字段</button>
              </template>
            </template>
          </div>
          </div>
        </template>
      </section>
      </div>
      <aside class="inspector">
        <section id="inspector">
          <template v-if="!selected">
            <h2>这块区域</h2>
            <p class="hint">在画布上拖一块区域，再选它放什么。</p>
          </template>
          <template v-else>
            <h2>{{ selected.title || effectMeta(selected).label }}</h2>
            <p class="hint">{{ selected.source === "api" ? "接口在这里配。展示点画布下方的格子。" : "类型在画布下方选。" }}</p>
            <label v-if="selected.source === 'text'" class="block">文字
              <textarea v-model="selected.content" rows="4" placeholder="写在壁纸上的字" @input="markDirty"></textarea>
            </label>
            <label v-else-if="selected.source === 'image'" class="block">图片
              <input v-model="selected.image" type="text" placeholder="https://... 或项目里的相对路径" spellcheck="false" @input="markDirty">
            </label>
            <p v-else-if="selected.source === 'blank'" class="hint">空白只占格子，不画内容，也不请求接口。</p>
            <template v-else-if="selected.source === 'api'">
              <label class="block">接口地址
                <input v-model="selected.api.url" type="text" placeholder="https://...  可用 {date}" spellcheck="false" @input="markDirty">
              </label>
              <p class="hint">参数加在地址后面，值里可以用 {date}。</p>
              <div v-for="(row, index) in selected.api.queryRows" :key="index" class="line spread">
                <input v-model="row.key" type="text" placeholder="参数名" aria-label="参数名" spellcheck="false" @input="syncQuery(selected); markDirty()">
                <input v-model="row.value" type="text" placeholder="参数值" aria-label="参数值" spellcheck="false" @input="syncQuery(selected); markDirty()">
                <button
                  v-if="selected.api.queryRows.length > 1 || row.key || row.value"
                  class="mini"
                  type="button"
                  @click="dropQuery(selected, index)"
                >去掉</button>
              </div>
              <button v-if="selected.api.queryRows.length < 8" class="query-add" type="button" @click="selected.api.queryRows.push({ key: '', value: '' })">加一个参数</button>
              <button class="probe" type="button" :disabled="probes[selected.id] && probes[selected.id].status === 'wait'" @click="probeArea(selected)">
                {{ probes[selected.id] && probes[selected.id].status === "wait" ? "正在请求…" : "测试接口" }}
              </button>
              <p v-if="probes[selected.id] && probes[selected.id].kind === 'json'" class="hint">
                {{ probes[selected.id].truncated ? "返回过长，已截断。点一段，填进正在点选的展示。" : "点一段，填进正在点选的展示。" }}
              </p>
              <div v-if="probes[selected.id] && probes[selected.id].kind === 'json'" class="tree">
                <TreeNode :value="probes[selected.id].body" path="" :depth="0" @pick="applyPath" />
              </div>
              <template v-else-if="probes[selected.id] && probes[selected.id].kind === 'text'">
                <p class="hint">{{ probes[selected.id].truncated ? "纯文本过长，已截断。文字展示的路径留空就用整段。" : "纯文本。文字展示的路径留空就用整段。" }}</p>
                <pre class="probe-text">{{ probes[selected.id].body }}</pre>
              </template>
              <p v-else-if="probes[selected.id] && probes[selected.id].status !== 'wait'" class="hint" :class="{ bad: probes[selected.id].kind === 'error' || probes[selected.id].status === 'fail' }">
                {{ probes[selected.id].message || "没有返回" }}
              </p>
            </template>
            <label v-if="selected.source && selected.source !== 'blank'" class="check"><input v-model="selected.style.showTitle" type="checkbox" @change="markDirty">显示标题</label>
            <label class="block">标题（留空用默认）
              <input v-model="selected.title" type="text" @input="markDirty">
            </label>
            <label class="check"><input :checked="selected.enabled !== false" type="checkbox" @change="selected.enabled = $event.target.checked; markDirty()">启用</label>
            <label class="check"><input v-model="selected.bleed" type="checkbox" @change="markDirty">贴边（靠着屏幕边缘的一侧铺满）</label>
            <button class="danger-text" type="button" @click="removeArea(selected)">从网格移除</button>
          </template>
        </section>
        <pre v-show="log" id="log">{{ log }}</pre>
      </aside>
    </main>
  </div>
</template>
