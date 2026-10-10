"use strict";

const SOURCES = ["blank", "text", "image", "api"];
const EFFECTS = ["text", "list", "image", "bar", "fields"];
const LEGACY = {
  wife: "image",
  image: "image",
  quote: "text",
  text: "text",
  news: "list",
  list: "list",
  calendar: "fields",
  weather: "fields",
  zodiac: "fields",
  fields: "fields",
  bar: "bar",
};

const DEFAULT_GRID = { cols: 12, rows: 8, gap: 20, margin: 40, taskbar: 48 };

const LEGACY_ROWS = {
  calendar: [
    ["农历月", "data.date.lunar.monthCN"],
    ["农历日", "data.date.lunar.dayCN"],
    ["干支", "data.date.lunar.yearGanZhi"],
    ["节气", "data.today.solarTerm"],
    ["下一假期", "data.nextHoliday.name"],
    ["一句", "data.moyuQuote"],
  ],
  weather: [
    ["城市", "data.location.name"],
    ["天气", "data.daily_forecast.0.day_condition"],
    ["最高", "data.daily_forecast.0.max_temperature"],
    ["最低", "data.daily_forecast.0.min_temperature"],
    ["空气", "data.daily_forecast.0.air_quality"],
    ["日出", "data.sunrise_sunset.0.sunrise_desc"],
  ],
  zodiac: [
    ["短评", "data.shortcomment"],
    ["全文", "data.alltext"],
    ["幸运色", "data.luckycolor"],
    ["幸运数字", "data.luckynumber"],
    ["健康", "data.health"],
    ["讨论", "data.discuss"],
  ],
};

const TITLES = {
  wife: "立绘",
  calendar: "日期",
  weather: "天气",
  news: "资讯",
  quote: "一句话",
  zodiac: "星座",
};

function asNumber(value) {
  const number = Number(String(value ?? "").trim());
  if (!Number.isFinite(number)) return null;
  return number === Math.trunc(number) ? Math.trunc(number) : number;
}

function rowsOf(pairs) {
  return pairs.map(([label, path]) => ({ label, path }));
}

function legacyName(area) {
  const typ = area && area.type;
  const display = String((area && area.display) || "").trim();
  if (["wife", "calendar", "weather", "news", "quote", "zodiac"].includes(typ)) return typ;
  if (["calendar", "weather", "news", "quote", "zodiac"].includes(display)) return display;
  return "";
}

function effectOf(area) {
  if (fillsWithImage(area)) return "image";
  const shows = (area && area.shows) || [];
  if (shows.length === 1 && EFFECTS.includes(shows[0].effect)) return shows[0].effect;
  const display = String((area && area.display) || "").trim();
  if (EFFECTS.includes(display)) return display;
  return LEGACY[display] || LEGACY[area && area.type] || "text";
}

function fillsWithImage(area) {
  if (!area) return false;
  if (area.source === "image") return true;
  const shows = area.shows || [];
  return area.source === "api" && shows.length === 1 && shows[0].effect === "image";
}

const TYPE_SIZES = [18, 22, 28, 34, 52];

function cleanColor(value) {
  const raw = String(value || "").trim();
  if (/^#[0-9a-fA-F]{8}$/.test(raw)) return raw.toUpperCase();
  if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw.toUpperCase();
  if (/^#[0-9a-fA-F]{3}$/.test(raw)) {
    const [r, g, b] = raw.slice(1);
    return `#${r}${r}${g}${g}${b}${b}`.toUpperCase();
  }
  if (["text", "dim", "hint", "accent", "warn", "ok"].includes(raw)) return raw;
  return "text";
}

function cleanLook(raw) {
  const style = raw || {};
  const size = TYPE_SIZES.includes(Number(style.size)) ? Number(style.size) : 22;
  const align = style.align === "center" || style.align === "right" ? style.align : "left";
  const color = cleanColor(style.color);
  return { size, align, color };
}

function cleanSheet(raw, showCount) {
  if (!raw || typeof raw !== "object") {
    return { cols: 1, rows: Math.max(1, Math.min(12, Number(showCount) || 1)) };
  }
  return {
    cols: Math.max(1, Math.min(8, Math.trunc(Number(raw.cols) || 1))),
    rows: Math.max(1, Math.min(12, Math.trunc(Number(raw.rows) || 1))),
  };
}

function sheetFromShows(shows, raw) {
  let cols = 1;
  let rows = 1;
  for (const show of shows || []) {
    const cell = show && show.cell;
    if (!cell || typeof cell !== "object") continue;
    cols = Math.max(cols, (Number(cell.col) || 0) + Math.max(1, Number(cell.colSpan) || 1));
    rows = Math.max(rows, (Number(cell.row) || 0) + Math.max(1, Number(cell.rowSpan) || 1));
  }
  const given = raw && typeof raw === "object" ? raw : {};
  return cleanSheet({
    cols: Math.max(Number(given.cols) || 0, cols),
    rows: Math.max(Number(given.rows) || 0, rows),
  });
}

function cleanCell(raw, index, sheet) {
  const has = raw && typeof raw === "object";
  const cols = sheet.cols;
  const rows = sheet.rows;
  let col = has ? Math.trunc(Number(raw.col) || 0) : 0;
  let row = has ? Math.trunc(Number(raw.row) || 0) : index;
  let colSpan = has ? Math.trunc(Number(raw.colSpan) || cols) : cols;
  let rowSpan = has ? Math.trunc(Number(raw.rowSpan) || 1) : 1;
  if (!has) colSpan = cols;
  col = Math.max(0, Math.min(cols - 1, col));
  row = Math.max(0, Math.min(rows - 1, row));
  colSpan = Math.max(1, Math.min(cols - col, colSpan));
  rowSpan = Math.max(1, Math.min(rows - row, rowSpan));
  return { col, row, colSpan, rowSpan };
}

function cleanShow(show, index = 0, sheet = null) {
  if (!show || typeof show !== "object") return null;
  const effect = show.effect;
  if (!EFFECTS.includes(effect)) return null;
  const grid = sheet || cleanSheet(null, index + 1);
  const out = { effect };
  if (effect === "text" || effect === "image") {
    out.path = String(show.path || "").trim();
    if (effect === "text") {
      if (show.form === "date") out.form = "date";
      const after = String(show.after ?? "");
      if (after) out.after = after;
    }
  } else if (effect === "list") {
    out.items = String(show.items || "").trim();
    out.item = String(show.item || "").trim();
    if (show.limit !== undefined && show.limit !== "") {
      const number = asNumber(show.limit);
      if (number !== null) out.limit = Math.max(1, Math.min(20, Math.trunc(number)));
    }
  } else if (effect === "bar") {
    out.path = String(show.path || "").trim();
    out.label = String(show.label || "").trim();
    const rawMax = show.max === undefined || show.max === "" ? 100 : show.max;
    const number = asNumber(rawMax);
    out.max = number === null ? (String(rawMax).trim() || 100) : number;
  } else if (effect === "fields") {
    out.rows = [];
    for (const row of (show.rows || []).slice(0, 8)) {
      if (!row || typeof row !== "object") continue;
      const rowOut = {
        label: String(row.label ?? ""),
        path: String(row.path || "").trim(),
      };
      const after = String(row.after ?? "");
      if (after) rowOut.after = after;
      out.rows.push(rowOut);
    }
  }
  out.cell = cleanCell(show.cell, index, grid);
  out.look = cleanLook(show.look);
  return out;
}

function showFromPick(display, pick, api) {
  pick = pick || {};
  api = api || {};
  let show;
  if (display === "image") show = { effect: "image", path: pick.image || "" };
  else if (display === "list") {
    show = { effect: "list", items: pick.items || "", item: pick.item || "" };
    if (api.limit !== undefined && api.limit !== "") show.limit = api.limit;
  } else if (display === "fields") show = { effect: "fields", rows: pick.rows || [] };
  else if (display === "bar") {
    show = {
      effect: "bar",
      path: pick.path || pick.text || "",
      max: pick.max === undefined ? 100 : pick.max,
      label: pick.label || "",
    };
  } else show = { effect: "text", path: pick.text || "" };
  return cleanShow(show);
}

function finishModern(src) {
  const source = SOURCES.includes(src.source) ? src.source : "";
  src.type = "custom";
  src.source = source;
  delete src.display;
  delete src.pick;
  if (source === "text") src.content = String(src.content || "");
  else if (source === "image") src.image = String(src.image || "").trim();
  if (source === "api") {
    src.api = src.api || {};
    const pending = (src.shows || []).slice(0, 8);
    src.sheet = sheetFromShows(pending, src.sheet);
    const shows = [];
    pending.forEach((show, index) => {
      const cleaned = cleanShow(show, index, src.sheet);
      if (cleaned) shows.push(cleaned);
    });
    src.shows = shows;
  } else {
    delete src.sheet;
    src.shows = [];
  }
  return src;
}

function migrate(src, display, api, pick) {
  src.type = "custom";
  src.source = "api";
  src.api = api;
  const show = showFromPick(display, pick, api);
  src.shows = show ? [show] : [];
  delete src.display;
  delete src.pick;
  return src;
}

function normalizeArea(area) {
  const src = JSON.parse(JSON.stringify(area || {}));
  const name = legacyName(src);
  if (!name && Object.prototype.hasOwnProperty.call(src, "source")) return finishModern(src);
  const api = { ...(src.api || {}) };
  const pick = { ...(src.pick || {}) };
  let display;
  if (name === "wife") {
    display = "image";
    if (!pick.image) pick.image = "data.image_url";
    if ((api.id_mode || "today") === "today") {
      api.query = { ...(api.query || {}), id: (api.query || {}).id || "{date}" };
    }
    delete api.id_mode;
  } else if (name === "news") {
    display = "list";
    if (!pick.items) pick.items = "data.models_and_releases";
    if (!pick.item) pick.item = "title";
  } else if (name === "quote") {
    display = "text";
    if (pick.text === undefined) pick.text = "";
  } else if (LEGACY_ROWS[name]) {
    display = "fields";
    pick.rows = pick.rows && pick.rows.length ? pick.rows : rowsOf(LEGACY_ROWS[name]);
  } else display = effectOf(src);
  if (name && !String(src.title || "").trim()) src.title = TITLES[name];
  return migrate(src, EFFECTS.includes(display) ? display : "text", api, pick);
}

function gridOf(cfg) {
  const raw = (cfg && cfg.grid) || {};
  const grid = { ...DEFAULT_GRID };
  for (const key of Object.keys(DEFAULT_GRID)) {
    if (raw[key] !== undefined && raw[key] !== null) grid[key] = raw[key];
  }
  grid.cols = Number(grid.cols);
  grid.rows = Number(grid.rows);
  grid.gap = Number(grid.gap);
  grid.margin = Number(grid.margin);
  grid.taskbar = Number(grid.taskbar);
  return grid;
}

function normalizeConfig(cfg) {
  const out = JSON.parse(JSON.stringify(cfg || {}));
  out.resolution = Array.isArray(out.resolution) ? out.resolution.map(Number) : [2560, 1440];
  out.grid = gridOf(out);
  out.areas = (out.areas || []).map(normalizeArea);
  out.schedule = {
    daily_time: (out.schedule && out.schedule.daily_time) || "06:00",
    task_name: (out.schedule && out.schedule.task_name) || "DailyWallpaper",
  };
  return out;
}

function cleanStyle(style) {
  const raw = style || {};
  const out = {};
  if (raw.size === "s" || raw.size === "l") out.size = raw.size;
  if (raw.align === "center") out.align = "center";
  if (["accent", "warn", "ok"].includes(raw.color)) out.color = raw.color;
  if (raw.showTitle === false) out.showTitle = false;
  return out;
}

function cleanQuery(query) {
  const out = {};
  for (const [key, value] of Object.entries(query || {})) {
    const name = String(key).trim();
    const text = String(value ?? "").trim();
    if (name && text) out[name] = text;
  }
  return out;
}

function cleanArea(area) {
  const src = normalizeArea(area);
  const item = {
    id: String(src.id || "block"),
    type: "custom",
    source: src.source || "",
    title: String(src.title || "").trim(),
    enabled: src.enabled !== false,
    col: Number(src.col) || 0,
    row: Number(src.row) || 0,
    colSpan: Number(src.colSpan) || 1,
    rowSpan: Number(src.rowSpan) || 1,
    bleed: !!src.bleed,
  };
  if (item.source === "text") item.content = String(src.content || "");
  else if (item.source === "image") item.image = String(src.image || "").trim();
  else if (item.source === "api") {
    const api = { url: String((src.api && src.api.url) || "").trim() };
    const query = cleanQuery(src.api && src.api.query);
    if (Object.keys(query).length) api.query = query;
    const path = String((src.api && src.api.path) || "").trim();
    if (path) api.path = path;
    item.api = api;
    item.shows = src.shows || [];
    if (src.sheet) item.sheet = src.sheet;
  }
  const style = cleanStyle(src.style);
  if (Object.keys(style).length) item.style = style;
  return item;
}

function metrics(grid, resolution) {
  const width = Number(resolution[0]);
  const height = Number(resolution[1]);
  const cols = Number(grid.cols);
  const rows = Number(grid.rows);
  const gap = Number(grid.gap);
  const margin = Number(grid.margin);
  const taskbar = Number(grid.taskbar);
  const safe = height - taskbar;
  const innerW = width - 2 * margin;
  const innerH = safe - 2 * margin;
  return {
    W: width,
    H: height,
    cols,
    rows,
    gap,
    margin,
    taskbar,
    safe,
    innerW,
    innerH,
    cellW: (innerW - (cols - 1) * gap) / cols,
    cellH: (innerH - (rows - 1) * gap) / rows,
  };
}

function rect(grid, resolution, area) {
  const width = Number(resolution[0]);
  const height = Number(resolution[1]);
  const cols = Number(grid.cols);
  const rows = Number(grid.rows);
  const gap = Number(grid.gap);
  const margin = Number(grid.margin);
  const taskbar = Number(grid.taskbar);
  const safeBottom = height - taskbar;
  const innerW = width - 2 * margin;
  const innerH = safeBottom - 2 * margin;
  const cellW = (innerW - (cols - 1) * gap) / cols;
  const cellH = (innerH - (rows - 1) * gap) / rows;
  const col = Math.max(0, Math.min(cols - 1, Number(area.col) || 0));
  const row = Math.max(0, Math.min(rows - 1, Number(area.row) || 0));
  const spanC = Math.max(1, Math.min(Number(area.colSpan) || 1, cols - col));
  const spanR = Math.max(1, Math.min(Number(area.rowSpan) || 1, rows - row));
  let x0 = margin + col * (cellW + gap);
  let y0 = margin + row * (cellH + gap);
  let x1 = x0 + spanC * cellW + (spanC - 1) * gap;
  let y1 = y0 + spanR * cellH + (spanR - 1) * gap;
  if (area.bleed) {
    if (col === 0) x0 = 0;
    if (row === 0) y0 = 0;
    if (col + spanC >= cols) x1 = width;
    if (row + spanR >= rows) y1 = safeBottom;
  }
  return [Math.round(x0), Math.round(y0), Math.round(x1), Math.round(y1)];
}

function validate(grid, areas, resolution) {
  const errors = [];
  const cols = Number(grid.cols);
  const rows = Number(grid.rows);
  const gap = Number(grid.gap);
  const margin = Number(grid.margin);
  const taskbar = Number(grid.taskbar);
  if (!(cols >= 4 && cols <= 24 && rows >= 4 && rows <= 24)) errors.push("列数和行数要在 4 到 24 之间");
  if (!(gap >= 0 && gap <= 80 && margin >= 0 && margin <= 240 && taskbar >= 0 && taskbar <= 200)) {
    errors.push("间距、边距或任务栏高度超出范围");
  }
  const width = Number(resolution && resolution[0]);
  const height = Number(resolution && resolution[1]);
  if (!(width >= 800 && width <= 7680 && height >= 600 && height <= 4320)) errors.push("分辨率无效");
  if (taskbar >= height / 2) errors.push("任务栏高度过大，内容区会被挤没");
  const occupied = new Map();
  const labels = new Map();
  const reported = new Set();
  for (const area of areas) {
    const name = String(area.title || "").trim() || "区块";
    const col = Number(area.col);
    const row = Number(area.row);
    const spanC = Number(area.colSpan);
    const spanR = Number(area.rowSpan);
    if ([col, row, spanC, spanR].some((n) => !Number.isFinite(n))) {
      errors.push(`${name} 的位置无效`);
      continue;
    }
    if (spanC < 1 || spanR < 1) errors.push(`${name} 至少占 1 格`);
    if (col < 0 || row < 0 || col + spanC > cols || row + spanR > rows) {
      errors.push(`${name} 超出了网格`);
      continue;
    }
    if (!SOURCES.includes(area.source)) errors.push(`${name} 还没有选择内容来源`);
    const url = String((area.api && area.api.url) || "").trim();
    if (area.source === "api" && url && !/^https?:\/\//.test(url)) {
      errors.push(`${name} 的接口地址要以 http:// 或 https:// 开头`);
    }
    const image = area.source === "image" ? String(area.image || "").trim() : "";
    if (image.includes("://") && !/^https?:\/\//.test(image)) {
      errors.push(`${name} 的图片地址要以 http:// 或 https:// 开头`);
    }
    if (area.enabled === false) continue;
    for (let x = col; x < col + spanC; x += 1) {
      for (let y = row; y < row + spanR; y += 1) {
        const key = `${x},${y}`;
        const other = occupied.get(key);
        const pair = [String(area.id), String(other)].sort().join("|");
        if (other && !reported.has(pair)) {
          errors.push(`${name} 和 ${labels.get(other) || "另一块"} 重叠了`);
          reported.add(pair);
        }
        occupied.set(key, area.id);
        labels.set(area.id, name);
      }
    }
  }
  if (!areas.some((area) => area.enabled !== false)) errors.push("至少启用一块区域");
  return errors;
}

function dig(obj, path) {
  const text = String(path || "").trim();
  if (!text) return obj;
  let cur = obj;
  for (const part of text.split(".")) {
    if (cur == null) return undefined;
    if (Array.isArray(cur)) {
      const index = Number(part);
      if (!Number.isInteger(index) || index < 0 || index >= cur.length) return undefined;
      cur = cur[index];
    } else if (typeof cur === "object") {
      if (!Object.prototype.hasOwnProperty.call(cur, part)) return undefined;
      cur = cur[part];
    } else return undefined;
  }
  return cur;
}

function slot(show, col, row, colSpan, rowSpan, size, color, align) {
  return {
    ...show,
    cell: { col, row, colSpan, rowSpan },
    look: { size, align: align || "left", color: color || "text" },
  };
}

function presetSheet(kind) {
  return {
    date: { cols: 4, rows: 5 },
    weather: { cols: 4, rows: 4 },
    news: { cols: 1, rows: 1 },
    quote: { cols: 1, rows: 1 },
    zodiac: { cols: 4, rows: 7 },
  }[kind] || null;
}

function presetShows(kind, limit) {
  if (kind === "date") {
    return [
      slot({ effect: "text", path: "data.date.gregorian", form: "date" }, 0, 0, 3, 2, 52),
      slot({ effect: "text", path: "data.date.weekday" }, 3, 0, 1, 2, 28, "text"),
      slot({ effect: "fields", rows: [
        { label: "农历", path: "data.date.lunar.monthCN" },
        { label: "", path: "data.date.lunar.dayCN" },
        { label: " · ", path: "data.date.lunar.yearGanZhi" },
        { label: "年 ", path: "data.date.lunar.zodiac" },
        { label: " · ", path: "data.today.solarTerm" },
        { label: "距", path: "data.nextHoliday.name" },
        { label: " ", path: "data.nextHoliday.until", after: " 天" },
      ] }, 0, 2, 4, 1, 18, "text"),
      slot({ effect: "bar", label: "本周", path: "data.progress.week.percentage", max: 100 }, 0, 3, 1, 2, 18, "accent"),
      slot({ effect: "bar", label: "本月", path: "data.progress.month.percentage", max: 100 }, 1, 3, 1, 2, 18, "ok"),
      slot({ effect: "bar", label: "今年", path: "data.progress.year.percentage", max: 100 }, 2, 3, 2, 2, 18, "warn"),
    ];
  }
  if (kind === "weather") {
    return [
      slot({ effect: "text", path: "data.hourly_forecast.0.temperature", after: "°" }, 0, 0, 2, 2, 52, "accent"),
      slot({ effect: "text", path: "data.hourly_forecast.0.condition" }, 2, 0, 1, 2, 28),
      slot({ effect: "text", path: "data.location.name" }, 3, 0, 1, 2, 18, "text", "right"),
      slot({ effect: "fields", rows: [
        { label: "", path: "data.daily_forecast.1.min_temperature", after: "°" },
        { label: " ~ ", path: "data.daily_forecast.1.max_temperature", after: "°" },
        { label: " · ", path: "data.hourly_forecast.0.wind_direction" },
        { label: "", path: "data.hourly_forecast.0.wind_power", after: "级" },
        { label: "日出 ", path: "data.sunrise_sunset.0.sunrise_desc" },
        { label: "日落 ", path: "data.sunrise_sunset.0.sunset_desc" },
        { label: "AQI ", path: "data.daily_forecast.1.aqi" },
        { label: " ", path: "data.daily_forecast.1.air_quality" },
      ] }, 0, 2, 4, 2, 18, "text"),
    ];
  }
  if (kind === "news") {
    return [slot({ effect: "list", items: "data.models_and_releases", item: "title", limit: Math.max(1, Math.min(20, Number(limit) || 7)) }, 0, 0, 1, 1, 28)];
  }
  if (kind === "quote") return [slot({ effect: "text", path: "" }, 0, 0, 1, 1, 34)];
  if (kind === "zodiac") {
    return [
      slot({ effect: "text", path: "xz", after: "座" }, 0, 0, 2, 2, 34),
      slot({ effect: "text", path: "data.shortcomment" }, 2, 0, 2, 2, 22, "accent"),
      slot({ effect: "text", path: "data.time" }, 0, 2, 4, 1, 18, "text"),
      slot({ effect: "text", path: "data.alltext" }, 0, 3, 4, 2, 22, "text"),
      slot({ effect: "bar", label: "健康", path: "data.health", max: 100 }, 0, 5, 2, 1, 18, "accent"),
      slot({ effect: "bar", label: "讨论", path: "data.discuss", max: 100 }, 2, 5, 2, 1, 18, "ok"),
      slot({ effect: "fields", rows: [
        { label: "幸运色", path: "data.luckycolor" },
        { label: "幸运数字", path: "data.luckynumber" },
        { label: "幸运星座", path: "data.luckyconstellation" },
      ] }, 0, 6, 4, 1, 18, "text"),
    ];
  }
  return [];
}

function exampleAreas(cfg) {
  const source = cfg || {};
  const apis = source.apis || {};
  const sixty = source.sixty_s || {};
  const paths = sixty.paths || {};
  const instances = (sixty.instances || [])
    .map((item) => String(item || "").trim().replace(/\/$/, ""))
    .filter(Boolean);
  const host = instances[0] || "https://60s.crystelf.top";
  const city = source.city || "潍坊";
  const zodiac = source.zodiac || "处女";
  const wifeQuery = (source.wife_id_mode || "today") === "today" ? { id: "{date}" } : {};
  const specs = [
    ["wife", "立绘", "#e89ab0", 0, 0, 4, 8, true, { url: apis.today_wife || "", query: wifeQuery }, [{ effect: "image", path: "data.image_url" }]],
    ["date", "日期", "#e8b04b", 4, 0, 4, 2, false, { url: host + (paths.moyu || "/v2/moyu") }, presetShows("date")],
    ["weather", "天气", "#5b9be8", 8, 0, 4, 2, false, { url: host + (paths.weather || "/v2/weather/forecast"), query: { query: city, days: String(source.weather_forecast_days || 3) } }, presetShows("weather")],
    ["news", "资讯", "#8fa6c4", 4, 2, 8, 3, false, { url: apis.ai_news || "" }, presetShows("news", source.ai_news_count)],
    ["quote", "一句话", "#5dcaa5", 4, 5, 4, 3, false, { url: apis.dujitang || "" }, presetShows("quote")],
    ["zodiac", "星座", "#c58be8", 8, 5, 4, 3, false, { url: apis.xzys || "", query: { xz: zodiac } }, presetShows("zodiac")],
  ];
  return specs.map(([id, label, color, col, row, colSpan, rowSpan, bleed, api, shows]) => ({
    id,
    type: "custom",
    source: "api",
    label,
    color,
    title: label,
    enabled: true,
    col,
    row,
    colSpan,
    rowSpan,
    bleed,
    api,
    shows,
    sheet: presetSheet(id) || undefined,
  }));
}

function stampToday(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}${m}${d}`;
}

function subst(text, stamp) {
  return String(text ?? "").replaceAll("{date}", stamp);
}

module.exports = {
  SOURCES,
  EFFECTS,
  DEFAULT_GRID,
  normalizeArea,
  normalizeConfig,
  cleanArea,
  gridOf,
  metrics,
  rect,
  validate,
  dig,
  fillsWithImage,
  effectOf,
  exampleAreas,
  presetShows,
  presetSheet,
  sheetFromShows,
  stampToday,
  subst,
};
