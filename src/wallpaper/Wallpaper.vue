<script setup>
import { nextTick, onMounted, ref } from "vue";

const payload = ref(null);

function pad(value) {
  return String(value).padStart(2, "0");
}

function fieldText(rows) {
  return fieldParts(rows).join("  ·  ");
}

function sheetStyle(area) {
  const sheet = area.sheet || { cols: 1, rows: 1 };
  return {
    gridTemplateColumns: `repeat(${sheet.cols}, minmax(0, 1fr))`,
    gridTemplateRows: `repeat(${sheet.rows}, minmax(0, 1fr))`,
  };
}

function paintColor(color) {
  if (/^#[0-9a-fA-F]{3,8}$/.test(color || "")) return color;
  if (color && color !== "text") return `var(--${color})`;
  return "var(--text)";
}

function cellStyle(show) {
  const cell = show.cell || { col: 0, row: 0, colSpan: 1, rowSpan: 1 };
  const look = show.look || { size: 22, align: "left", color: "text" };
  return {
    gridColumn: `${cell.col + 1} / span ${cell.colSpan}`,
    gridRow: `${cell.row + 1} / span ${cell.rowSpan}`,
    fontSize: `calc(${look.size || 22}px * var(--mul))`,
    textAlign: look.align || "left",
    color: paintColor(look.color),
  };
}

function isGlue(label) {
  if (!label) return true;
  if (/^[\s·•.,，、°]/.test(label)) return true;
  return label.length <= 2 && /\s$/.test(label);
}

function fieldParts(rows) {
  const parts = [];
  for (const row of rows) {
    const value = String(row.value || "");
    if (!value) continue;
    const label = row.label || "";
    if (!label) {
      if (parts.length) parts[parts.length - 1] += value;
      else parts.push(value);
      continue;
    }
    if (isGlue(label) && parts.length) parts[parts.length - 1] += `${label}${value}`;
    else if (!label) parts.push(value);
    else if (label.length <= 2 || /\s$/.test(label)) parts.push(`${label}${value}`);
    else parts.push(`${label} ${value}`);
  }
  return parts;
}

function areaStyle(area) {
  const fit = payload.value.fit || Math.min(payload.value.width / 2560, payload.value.height / 1440);
  return {
    left: `${area.box.left}px`,
    top: `${area.box.top}px`,
    width: `${area.box.width}px`,
    height: `${area.box.height}px`,
    "--mul": String(fit),
  };
}

function boardStyle() {
  const theme = payload.value.theme;
  const fit = payload.value.fit || 1;
  return {
    width: `${payload.value.width}px`,
    height: `${payload.value.height}px`,
    background: theme.bg,
    color: theme.text,
    "--text": theme.text,
    "--dim": theme.dim,
    "--hint": theme.hint,
    "--accent": theme.accent,
    "--warn": theme.warn,
    "--ok": theme.ok,
    "--danger": theme.danger,
    "--mul": String(fit),
  };
}

onMounted(async () => {
  payload.value = await window.wallpaper.getRenderPayload();
  await nextTick();
  const board = document.querySelector(".board");
  if (board) {
    const fit = Math.min(window.innerWidth / payload.value.width, window.innerHeight / payload.value.height);
    board.style.transformOrigin = "top left";
    board.style.transform = `scale(${fit})`;
  }
  await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  await Promise.all([...document.images].map((img) => (img.complete
    ? Promise.resolve()
    : new Promise((done) => { img.onload = img.onerror = done; }))));
  await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
  window.wallpaper.wallpaperReady();
});
</script>

<template>
  <div v-if="payload" class="board" :style="boardStyle()">
    <img v-if="payload.backdrop" class="back" :src="payload.backdrop" alt="" />
    <div v-if="payload.backdrop" class="dim"></div>
    <article
      v-for="area in payload.areas"
      :key="area.id"
      class="panel"
      :class="{ fill: area.fill, stack: !area.fill }"
      :style="areaStyle(area)"
    >
      <p v-if="area.error" class="miss">{{ area.error }}</p>
      <template v-else-if="area.fill">
        <div v-if="area.image" class="fill-stage">
          <img class="fill-bleed" :src="area.image" alt="" />
          <img class="cover" :src="area.image" alt="" />
        </div>
        <p v-else class="miss">没有图片</p>
      </template>
      <template v-else>
        <div v-if="area.style.showTitle" class="topline">
          <span class="kicker">{{ area.title }}</span>
        </div>
        <div class="sheet" :style="sheetStyle(area)">
          <div v-for="(show, index) in area.shows" :key="index" v-show="!show.missing" class="cell" :style="cellStyle(show)">
            <p v-if="show.effect === 'text' && show.text">{{ show.text }}</p>
            <p v-else-if="show.effect === 'fields' && fieldText(show.rows)">{{ fieldText(show.rows) }}</p>
            <ol v-else-if="show.effect === 'list' && show.lines.length">
              <li v-for="(line, lineIndex) in show.lines" :key="lineIndex">
                <span>{{ pad(lineIndex + 1) }}</span>
                <em>{{ line }}</em>
              </li>
            </ol>
            <img v-else-if="show.effect === 'image' && show.url" class="inline" :src="show.url" alt="" />
            <div v-else-if="show.effect === 'bar' && show.pct != null" class="meter">
              <span>{{ show.label }}</span>
              <b>{{ Math.round(show.pct) }}%</b>
              <i><s :style="{ width: Math.max(0, Math.min(100, show.pct)) + '%' }"></s></i>
            </div>
          </div>
        </div>
      </template>
    </article>
    <footer
      v-if="payload.footer"
      class="sources"
      :style="{ left: payload.footer.left + 'px', top: payload.footer.top + 'px', width: payload.footer.width + 'px' }"
    >
      <span>数据源</span>
      <ul>
        <li v-for="item in payload.footer.sources" :key="item.name" :class="{ bad: !item.ok }">
          <i></i>{{ item.name }}
        </li>
      </ul>
    </footer>
  </div>
</template>

<style scoped>
:global(html),
:global(body),
:global(#app) {
  margin: 0;
  padding: 0;
  overflow: hidden;
  background: #0d1015;
}
.board {
  position: absolute;
  left: 0;
  top: 0;
  overflow: hidden;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}
.back {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: blur(28px);
  transform: scale(1.08);
}
.dim { position: absolute; inset: 0; background: rgba(8, 10, 14, .55); }
.panel {
  position: absolute;
  box-sizing: border-box;
  overflow: hidden;
  border-radius: calc(22px * var(--mul));
  padding: calc(22px * var(--mul)) calc(36px * var(--mul)) calc(18px * var(--mul));
  background: rgba(255, 255, 255, .07);
  border: 1px solid rgba(255, 255, 255, .14);
}
.panel.fill { padding: 0; border: 0; background: transparent; border-radius: 0; }
.stack { display: flex; flex-direction: column; }
.fill-stage { position: absolute; inset: 0; overflow: hidden; }
.fill-bleed, .cover {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center bottom;
}
.fill-bleed { transform: scale(1.05); }
.topline { display: flex; align-items: baseline; min-height: calc(28px * var(--mul)); }
.kicker { color: var(--hint); font-size: calc(18px * var(--mul)); font-weight: 700; letter-spacing: .16em; }
.sheet {
  flex: 1;
  min-height: 0;
  display: grid;
  gap: calc(8px * var(--mul));
}
.cell { min-width: 0; min-height: 0; overflow: hidden; display: flex; flex-direction: column; justify-content: center; line-height: 1.35; }
.cell p { margin: 0; }
.cell ol {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  margin: 0;
  padding: 0;
  list-style: none;
  min-height: 0;
}
.cell li { display: flex; align-items: baseline; gap: .4em; min-width: 0; }
.cell li span { flex: none; width: 2em; opacity: .55; font-weight: 700; }
.cell li em {
  min-width: 0;
  overflow: hidden;
  color: inherit;
  font-size: 1em;
  font-style: normal;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meter { width: 100%; display: grid; grid-template-columns: auto 1fr; gap: .2em .6em; align-items: baseline; }
.meter span, .meter b { font-size: 1em; color: inherit; background: transparent; }
.meter b { justify-self: end; }
.meter i { grid-column: 1 / -1; display: block; height: calc(7px * var(--mul)); border-radius: 99px; background: color-mix(in srgb, currentColor 22%, transparent); overflow: hidden; }
.meter s { display: block; height: 100%; background: currentColor; }
.inline { display: block; max-width: 100%; max-height: 8em; object-fit: contain; margin-top: .3em; }
.miss { margin: 0; color: var(--dim); }
.sources {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: rgba(255, 255, 255, .42);
  font-size: calc(18px * var(--mul));
}
.sources ul { display: flex; gap: calc(16px * var(--mul)); margin: 0; padding: 0; list-style: none; }
.sources i {
  display: inline-block;
  width: calc(8px * var(--mul));
  height: calc(8px * var(--mul));
  margin-right: calc(6px * var(--mul));
  border-radius: 50%;
  background: var(--ok);
  vertical-align: middle;
}
.sources .bad { color: var(--danger); }
.sources .bad i { background: var(--danger); }
</style>
