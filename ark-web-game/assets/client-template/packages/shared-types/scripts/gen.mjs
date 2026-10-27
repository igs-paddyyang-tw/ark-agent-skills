// 由 schemas/*.schema.json 產 TypeScript 型別（src/generated/）。型別不手寫：改契約 → 改正本 schema → 同步 → 重產。
import { compileFromFile } from 'json-schema-to-typescript';
import { writeFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const schemas = join(here, '..', '..', '..', 'schemas');
const out = join(here, '..', 'src', 'generated');
const names = { 'spin-result.schema.json': 'spin-result.ts', 'game-info.schema.json': 'game-info.ts', 'release-manifest.schema.json': 'release-manifest.ts' };
for (const f of readdirSync(schemas).filter((x) => names[x])) {
  const ts = await compileFromFile(join(schemas, f), { cwd: schemas, bannerComment: `/* 由 schemas/${f} 產生（pnpm gen:types），勿手改 */`, additionalProperties: true, style: { singleQuote: true } });
  writeFileSync(join(out, names[f]), ts);
  console.log('gen', names[f]);
}
