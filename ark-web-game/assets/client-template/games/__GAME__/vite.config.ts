import { defineConfig } from 'vite';
// 素材：wg_pack_assets 輸出到 <aidev>/output/web-game/huffnpuff（內含 assets/）；PGP_ASSETS_DIR 指到該資料夾時，開發伺服器與建置都會帶上 ./assets/
const assetsDir = process.env.PGP_ASSETS_DIR;
// 資料夾版：base './' 讓 dist/ 可放在任何子路徑；pixi 獨立 chunk（快取與分包）
export default defineConfig({
  base: './',
  publicDir: assetsDir || 'public',
  // source map：正式 build 不產（上線前資安 CLIENT-2／DEP-6：.map 會公開原始碼）；要除錯建置結果時 PGP_SOURCEMAP=1。vite dev server 本來就有 source map
  build: { assetsDir: 'js', target: 'es2022', sourcemap: process.env.PGP_SOURCEMAP === '1', rollupOptions: { output: { manualChunks: { pixi: ['pixi.js'] } } } },
  test: { environment: 'node', include: ['test/**/*.test.ts'] },
});
