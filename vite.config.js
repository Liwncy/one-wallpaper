import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import esbuild from "esbuild";

function sharedForDev() {
  return {
    name: "shared-cjs",
    enforce: "pre",
    async transform(code, id) {
      const file = id.split("?")[0].replaceAll("\\", "/");
      if (!file.endsWith("/shared/areas.js")) return null;
      const result = await esbuild.transform(code, { format: "esm", loader: "js", sourcefile: file });
      return { code: result.code, map: result.map || null };
    },
  };
}

export default defineConfig({
  plugins: [sharedForDev(), vue()],
  base: "./",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
