// 極簡 JSON Schema 驗證器（測試用，零相依）：type、required、const、enum、pattern、minimum、exclusiveMinimum、minItems、items、properties、
// additionalProperties（schema）、oneOf、$ref（同目錄檔名）。只涵蓋 stage/schema 用到的關鍵字。
'use strict';
const fs = require('fs');
const path = require('path');
const DIR = path.join(__dirname, '..', 'schema');
const cache = {};
const load = (f) => (cache[f] = cache[f] || JSON.parse(fs.readFileSync(path.join(DIR, f), 'utf8')));
const typeOf = (v) => (v === null ? 'null' : Array.isArray(v) ? 'array' : Number.isInteger(v) ? 'integer' : typeof v);
function validate(schema, v, p = '$', errs = []) {
  if (typeof schema === 'string') schema = load(schema);
  if (schema.$ref) return validate(load(schema.$ref), v, p, errs);
  if (schema.oneOf) {
    const ok = schema.oneOf.filter((s) => validate(s, v, p, []).length === 0).length;
    if (ok !== 1) errs.push(`${p}: oneOf 命中 ${ok} 個`);
    return errs;
  }
  if (schema.const !== undefined && v !== schema.const) errs.push(`${p}: 應為 ${schema.const}`);
  if (schema.enum && !schema.enum.includes(v)) errs.push(`${p}: 不在 ${schema.enum}`);
  if (schema.type) {
    const ts = [].concat(schema.type), t = typeOf(v);
    if (!ts.includes(t) && !(t === 'integer' && ts.includes('number'))) { errs.push(`${p}: 型別 ${t} 不是 ${ts}`); return errs; }
  }
  if (typeof v === 'string' && schema.pattern && !new RegExp(schema.pattern).test(v)) errs.push(`${p}: 不符 ${schema.pattern}`);
  if (typeof v === 'number') {
    if (schema.minimum !== undefined && v < schema.minimum) errs.push(`${p}: < ${schema.minimum}`);
    if (schema.exclusiveMinimum !== undefined && v <= schema.exclusiveMinimum) errs.push(`${p}: ≤ ${schema.exclusiveMinimum}`);
  }
  if (Array.isArray(v)) {
    if (schema.minItems && v.length < schema.minItems) errs.push(`${p}: 少於 ${schema.minItems} 項`);
    if (schema.items) v.forEach((x, i) => validate(schema.items, x, `${p}[${i}]`, errs));
  }
  if (v && typeof v === 'object' && !Array.isArray(v)) {
    for (const k of schema.required || []) if (!(k in v)) errs.push(`${p}.${k}: 必填`);
    for (const [k, s] of Object.entries(schema.properties || {})) if (k in v) validate(s, v[k], `${p}.${k}`, errs);
    if (schema.additionalProperties && typeof schema.additionalProperties === 'object')
      for (const [k, x] of Object.entries(v)) if (!(schema.properties || {})[k]) validate(schema.additionalProperties, x, `${p}.${k}`, errs);
  }
  return errs;
}
module.exports = { validate };
