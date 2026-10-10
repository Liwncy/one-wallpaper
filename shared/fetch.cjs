"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const areas = require("./areas.js");

function tag(text) {
  return crypto.createHash("sha1").update(String(text)).digest("hex").slice(0, 10);
}

function isImage(buf) {
  if (!buf || buf.length < 8) return false;
  if (buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return true;
  if (buf.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) return true;
  const head = buf.subarray(0, 6).toString("ascii");
  return head === "GIF87a" || head === "GIF89a";
}

function extOf(buf, contentType) {
  const type = String(contentType || "");
  if (type.includes("png") || (buf[0] === 0x89)) return "png";
  if (type.includes("gif")) return "gif";
  return "jpg";
}

function capValue(obj, depth = 0) {
  let truncated = false;
  if (depth > 8) return { value: "…", truncated: true };
  if (typeof obj === "string") {
    if (obj.length > 500) return { value: `${obj.slice(0, 500)}…`, truncated: true };
    return { value: obj, truncated: false };
  }
  if (obj == null || typeof obj === "number" || typeof obj === "boolean") return { value: obj, truncated: false };
  if (Array.isArray(obj)) {
    if (obj.length > 20) truncated = true;
    const items = [];
    for (const item of obj.slice(0, 20)) {
      const next = capValue(item, depth + 1);
      items.push(next.value);
      truncated = truncated || next.truncated;
    }
    return { value: items, truncated };
  }
  if (typeof obj === "object") {
    let keys = Object.keys(obj);
    if (keys.length > 40) {
      truncated = true;
      keys = keys.slice(0, 40);
    }
    const out = {};
    for (const key of keys) {
      const next = capValue(obj[key], depth + 1);
      out[key] = next.value;
      truncated = truncated || next.truncated;
    }
    return { value: out, truncated };
  }
  const text = String(obj);
  return { value: text.length > 200 ? `${text.slice(0, 200)}…` : text, truncated: text.length > 200 };
}

function requestUrl(area, stamp) {
  const api = area.api || {};
  const raw = areas.subst(String(api.url || "").trim(), stamp);
  if (!raw) return "";
  const url = new URL(raw);
  for (const [key, value] of Object.entries(api.query || {})) {
    const name = String(key).trim();
    const text = areas.subst(value, stamp).trim();
    if (name && text) url.searchParams.set(name, text);
  }
  return url.href;
}

async function fetchBuffer(url, userAgent, timeoutMs) {
  const res = await fetch(url, {
    headers: { "User-Agent": userAgent || "one-wallpaper" },
    signal: AbortSignal.timeout(timeoutMs || 20000),
    redirect: "follow",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  return { buf, contentType: res.headers.get("content-type") || "" };
}

function saveImage(cacheDir, buf, contentType, name) {
  fs.mkdirSync(cacheDir, { recursive: true });
  const file = path.join(cacheDir, `${name}.${extOf(buf, contentType)}`);
  fs.writeFileSync(file, buf);
  return `media://cache/${path.basename(file)}`;
}

async function downloadImage(url, cacheDir, userAgent, timeoutMs) {
  const { buf, contentType } = await fetchBuffer(url, userAgent, timeoutMs);
  if (!isImage(buf) && !String(contentType).startsWith("image/")) throw new Error("不是图片");
  return saveImage(cacheDir, buf, contentType, `img_${tag(url)}`);
}

function localImageUrl(ref, root) {
  const text = String(ref || "").trim().replaceAll("\\", "/");
  if (!text || text.split("/").includes("..")) return "";
  const full = path.resolve(root, text);
  const base = path.resolve(root);
  if (full !== base && !full.startsWith(base + path.sep)) return "";
  if (!fs.existsSync(full) || !fs.statSync(full).isFile()) return "";
  return `media://local/?path=${encodeURIComponent(text)}`;
}

async function fetchArea(area, options) {
  const stamp = options.stamp;
  const source = area.source;
  if (source === "blank") return { ok: true };
  if (source === "text") return { ok: true, text: String(area.content || "") };
  if (source === "image") {
    const ref = String(area.image || "").trim();
    if (!ref) return { ok: false, error: "未填写图片" };
    try {
      if (/^https?:\/\//.test(ref)) {
        const imageUrl = await downloadImage(areas.subst(ref, stamp), options.cacheDir, options.userAgent, options.timeoutMs);
        return { ok: true, imageUrl };
      }
      const imageUrl = localImageUrl(ref, options.root);
      if (!imageUrl) return { ok: false, error: "找不到图片" };
      return { ok: true, imageUrl };
    } catch (err) {
      return { ok: false, error: `图片下载失败 ${err.message || err}` };
    }
  }
  if (source !== "api") return { ok: false, error: "还没有选择内容来源" };
  const url = (() => {
    try {
      return requestUrl(area, stamp);
    } catch {
      return "";
    }
  })();
  if (!url) return { ok: false, error: "未填写接口" };
  let got;
  try {
    got = await fetchBuffer(url, options.userAgent, options.timeoutMs);
  } catch (err) {
    return { ok: false, error: `请求失败 ${err.name || ""} ${err.message || err}`.trim() };
  }
  if (isImage(got.buf) || String(got.contentType).startsWith("image/")) {
    const imageUrl = saveImage(options.cacheDir, got.buf, got.contentType, `raw_${tag(url)}_${stamp}`);
    return { ok: true, imageUrl, images: { "": imageUrl } };
  }
  const text = got.buf.toString("utf8").trim();
  try {
    const json = JSON.parse(text);
    const images = {};
    if (!options.probe) {
      for (const show of area.shows || []) {
        if (show.effect !== "image") continue;
        const imagePath = String(show.path || "").trim();
        if (!imagePath || images[imagePath]) continue;
        const imageRef = areas.dig(json, imagePath);
        if (typeof imageRef === "string" && /^https?:\/\//.test(imageRef)) {
          try {
            images[imagePath] = await downloadImage(imageRef, options.cacheDir, options.userAgent, options.timeoutMs);
          } catch {
            /* 单张图片失败时，这条展示稍后显示占位 */
          }
        }
      }
    }
    const block = { ok: true, json, images };
    if (areas.fillsWithImage(area)) {
      const only = (area.shows || [])[0] || {};
      block.imageUrl = images[String(only.path || "").trim()] || images[""] || "";
    }
    return block;
  } catch {
    return { ok: true, text: text.slice(0, 8000) };
  }
}

function probeView(block) {
  if (!block || block.error || block.ok === false) {
    return { status: "fail", kind: "error", message: (block && block.error) || "请求失败", truncated: false };
  }
  if (block.json !== undefined) {
    const capped = capValue(block.json);
    return { status: "ok", kind: "json", body: capped.value, truncated: capped.truncated };
  }
  if (block.imageUrl && block.json === undefined) {
    return { status: "ok", kind: "image", message: "接口直接返回了一张图片。图片展示的路径留空即可。", truncated: false };
  }
  if (block.text != null) {
    const text = String(block.text);
    return { status: "ok", kind: "text", body: text.slice(0, 8000), truncated: text.length > 8000 };
  }
  return { status: "ok", kind: "empty", message: "响应是空的", truncated: false };
}

module.exports = { fetchArea, probeView, requestUrl };
