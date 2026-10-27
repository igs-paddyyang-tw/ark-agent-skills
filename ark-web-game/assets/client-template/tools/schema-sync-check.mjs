// 契約同步檢查（兩軌共用 schema）：schemas/*.json 的 sha256 必須等於 SOURCE.json 登記值；
// 給 --source <aidev schema 目錄> 時另比對正本（CI 在同時取得 aidev 時使用）。不一致 exit 1。
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = join(dirname(fileURLToPath(import.meta.url)), '..', 'schemas');
const src = JSON.parse(readFileSync(join(root, 'SOURCE.json'), 'utf8'));
const i = process.argv.indexOf('--source');
const upstream = i > 0 ? process.argv[i + 1] : null;
const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex');
const errs = [];
for (const f of readdirSync(root).filter((x) => x.endsWith('.schema.json'))) {
  const h = sha(join(root, f));
  if (src.sha256[f] !== h) errs.push(`${f}：與 SOURCE.json 登記不同（改了 schema 要同步正本並升版號）`);
  if (upstream) {
    const u = join(upstream, f);
    if (!existsSync(u)) errs.push(`${f}：正本沒有這個檔`);
    else if (sha(u) !== h) errs.push(`${f}：與正本 ${u} 不同`);
  }
}
for (const f of Object.keys(src.sha256)) if (!existsSync(join(root, f))) errs.push(`${f}：登記了但檔案不在`);
console.log(errs.length ? `❌ schema 同步：\n  ${errs.join('\n  ')}` : `✅ schema 同步：${Object.keys(src.sha256).length} 份一致${upstream ? '（含正本）' : ''}`);
process.exit(errs.length ? 1 : 0);
