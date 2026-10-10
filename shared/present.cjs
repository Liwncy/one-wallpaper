"use strict";

const areas = require("./areas.js");

function asText(value) {
  if (value == null) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function asNumber(value) {
  if (typeof value === "boolean" || value == null) return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const text = String(value).trim().replace(/%$/, "");
  const number = Number(text);
  return Number.isFinite(number) ? number : null;
}

function styleOf(area) {
  const raw = (area && area.style) || {};
  return {
    size: raw.size === "s" || raw.size === "l" ? raw.size : "m",
    align: raw.align === "center" ? "center" : "left",
    color: ["accent", "warn", "ok"].includes(raw.color) ? raw.color : "text",
    showTitle: raw.showTitle !== false,
  };
}

function shapeText(text, show) {
  let next = String(text || "");
  if (show && show.form === "date") {
    const iso = next.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) next = `${Number(iso[2])}月${Number(iso[3])}日`;
  }
  return `${next}${show && show.after ? show.after : ""}`;
}

function listLines(body, show) {
  const itemsPath = String(show.items || "").trim();
  let items = areas.dig(body, itemsPath);
  if (Array.isArray(body) && !itemsPath) items = body;
  if (items === undefined) return null;
  if (!Array.isArray(items)) return [];
  const key = String(show.item || "").trim();
  const lines = [];
  for (const item of items) {
    let text = "";
    if (key && item && typeof item === "object" && !Array.isArray(item)) text = asText(areas.dig(item, key));
    else text = asText(item);
    if (text) lines.push(text);
  }
  const limit = Math.max(1, Math.min(20, Number(show.limit) || 7));
  return lines.slice(0, limit);
}

function barPct(body, show) {
  const value = asNumber(areas.dig(body, show.path));
  if (value === null) return null;
  const rawMax = show.max === undefined || show.max === "" ? 100 : show.max;
  const maxValue = typeof rawMax === "string" && asNumber(rawMax) === null
    ? asNumber(areas.dig(body, rawMax))
    : asNumber(rawMax);
  const max = maxValue || 100;
  return Math.max(0, Math.min(100, (value / max) * 100));
}

function textShow(block, show) {
  const path = String(show.path || "").trim();
  if (show.staticText !== undefined) return { text: shapeText(show.staticText, show), missing: false, path };
  const body = block && block.json;
  if (path) {
    if (body == null) return { text: "", missing: true, path };
    const value = areas.dig(body, path);
    if (value === undefined || value === null || value === "") return { text: "", missing: true, path };
    return { text: shapeText(asText(value), show), missing: false, path };
  }
  if (block && block.text != null) return { text: shapeText(asText(block.text), show), missing: false, path };
  if (typeof body === "string") return { text: shapeText(body.trim(), show), missing: false, path };
  return { text: "", missing: false, path };
}

function imageUrl(block, show) {
  const path = String((show && show.path) || "").trim();
  const images = (block && block.images) || {};
  if (path) return images[path] || "";
  return (block && block.imageUrl) || images[""] || "";
}

function presentArea(area, block) {
  const style = styleOf(area);
  const view = {
    id: area.id,
    title: String(area.title || "").trim() || "区块",
    style,
    fill: false,
    image: "",
    shows: [],
    error: (block && block.error) || "",
  };
  if (area.source === "blank") return { ...view, skip: true };
  if (view.error) return view;
  if (areas.fillsWithImage(area)) {
    view.fill = true;
    view.image = area.source === "image" ? (block && block.imageUrl) || "" : imageUrl(block, (area.shows || [])[0] || {});
    return view;
  }
  let shows = area.shows || [];
  if (area.source === "text") shows = [{ effect: "text", path: "", staticText: (area.content || (block && block.text) || ""), cell: { col: 0, row: 0, colSpan: 1, rowSpan: 1 }, look: { size: 34, align: "left", color: "text" } }];
  view.sheet = areas.sheetFromShows(shows, area.sheet);
  for (const show of shows) {
    const place = {
      cell: show.cell || { col: 0, row: view.shows.length, colSpan: view.sheet.cols, rowSpan: 1 },
      look: show.look || { size: 22, align: "left", color: "text" },
    };
    if (show.effect === "text") {
      const got = textShow(block, show);
      view.shows.push({ effect: "text", path: got.path || "", ...got, ...place });
    } else if (show.effect === "list") {
      const lines = listLines(block && block.json, show);
      view.shows.push({
        effect: "list",
        missing: lines === null,
        lines: lines || [],
        ...place,
      });
    } else if (show.effect === "image") {
      const url = imageUrl(block, show);
      view.shows.push({ effect: "image", url, missing: !url, ...place });
    } else if (show.effect === "bar") {
      const pct = String(show.path || "").trim() ? barPct(block && block.json, show) : null;
      view.shows.push({
        effect: "bar",
        label: show.label || "",
        pct,
        missing: pct === null,
        ...place,
      });
    } else if (show.effect === "fields") {
      const rows = [];
      for (const row of show.rows || []) {
        if (!row.path && !row.label) continue;
        let value = asText(areas.dig(block && block.json, row.path));
        if (!value || value === "—" || value === "null") continue;
        if (row.after) value += String(row.after);
        rows.push({ label: row.label || "", value });
      }
      view.shows.push({ effect: "fields", rows, missing: !rows.length, ...place });
    }
  }
  return view;
}

function presentWallpaper(cfg, blocks) {
  const grid = areas.gridOf(cfg);
  const resolution = cfg.resolution;
  const placed = [];
  for (const area of cfg.areas || []) {
    if (area.enabled === false) continue;
    const block = (blocks && blocks[area.id]) || {};
    const view = presentArea(area, block);
    if (view.skip) continue;
    const [x0, y0, x1, y1] = areas.rect(grid, resolution, area);
    view.box = { left: x0, top: y0, width: Math.max(1, x1 - x0), height: Math.max(1, y1 - y0) };
    placed.push(view);
  }
  placed.sort((a, b) => Number(b.fill) - Number(a.fill));
  const theme = cfg.theme || {};
  const width = Number(resolution[0]);
  const height = Number(resolution[1]);
  const taskbar = Number(grid.taskbar) || 0;
  const fit = Math.min(width / 2560, height / 1440);
  const content = placed.filter((item) => !item.fill);
  let footer = null;
  if (placed.length && content.length) {
    const lowest = Math.max(...content.map((item) => item.box.top + item.box.height));
    const left = Math.min(...content.map((item) => item.box.left));
    const right = Math.max(...content.map((item) => item.box.left + item.box.width));
    footer = {
      left,
      width: right - left,
      top: Math.min(lowest + Math.round(8 * fit), height - taskbar - Math.round(22 * fit)),
      sources: placed
        .slice()
        .sort((a, b) => a.box.top - b.box.top || a.box.left - b.box.left)
        .map((view) => ({ name: view.title, ok: !view.error })),
    };
  }
  return {
    width,
    height,
    taskbar,
    fit,
    theme: {
      bg: theme.bg || "#0D1015",
      text: theme.text || "#EAEDF3",
      dim: theme.text_dim || "#9AA4B5",
      hint: theme.text_hint || "#6B7480",
      accent: theme.accent || "#5B9BE8",
      warn: theme.warn || "#E8B04B",
      ok: theme.ok || "#5DCAA5",
      danger: theme.danger || "#E87B6B",
    },
    backdrop: (placed.find((item) => item.fill && item.image) || {}).image || "",
    footer,
    areas: placed,
  };
}

module.exports = { presentArea, presentWallpaper };
