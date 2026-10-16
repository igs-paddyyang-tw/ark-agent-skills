// ============================================================
//  [ark-game-proto stage] 啟動流程：建立畫面（Pixi）→ 建立 GameService → 載入素材 → 建立遊戲模組 → 點擊開始
//  共用除錯分頁沿用 Proto 試玩模板：設定檢查、演出測試、演出記錄、素材替換；另加「服務」分頁（來源、seed、錄製 / 重播、連線統計）
//  結果來源由網址參數決定（預設 local）：
//    ?service=local&seed=123[&rng=go]  瀏覽器內引擎（LocalService；rng=go → Go math/rand Float64 數學流）
//    ?service=http&base=https://…&game=<id>&token=…&dev=1   slot-bot server（HttpService）
//    重播：除錯「服務」分頁載入 .trace.json（ReplayService）
//  演出亂數（Timeline 的 random 步驟、粒子、震屏）一律用 app.rng = fx 流，不碰數學流
// ============================================================
(function () {
  'use strict';
  const Proto = window.Proto;
  const h = (...a) => Proto.h(...a);

  function params() {
    const q = new URLSearchParams(location.search);
    const o = {};
    for (const [k, v] of q) o[k] = v;
    return o;
  }

  Proto.createService = function (config, q = params()) {
    const S = Proto.svc;
    const kind = q.service || (config.service && config.service.kind) || 'local';
    if (kind === 'http') {
      const c = config.service || {};
      return new S.HttpService({ base: q.base || c.base || '', gameId: q.game || c.gameId || config.slug || 'game', token: q.token || c.token, dev: q.dev === '1' || !!c.dev });
    }
    const seed = q.seed !== undefined ? Number(q.seed) : config.seed;
    return new S.LocalService(config.spec, { seed, rng: q.rng === 'go' ? 'go' : undefined, balance: (config.presentation || {}).startBalance ?? 100000 });
  };

  function message(app, text) {
    const el = h('div', { class: 'stage-msg' }, text);
    app.stage.dom.appendChild(el);
    return el;
  }

  Proto.start = async function () {
    const config = Proto.config;
    if (!config) { document.body.textContent = '找不到遊戲設定：game.js 裡要呼叫 Proto.game({...})'; return; }
    const Module = Proto.modules[config.type];
    if (!Module) { document.body.textContent = `不認識的遊戲類型「${config.type}」，目前支援：${Object.keys(Proto.modules).join('、')}`; return; }
    document.title = config.name || document.title;

    const app = (Proto.app = { config, events: new Proto.Emitter() });
    app.ui = new Proto.UI(app);
    app.stage = new Proto.Stage(app.ui.stageWrap, config.stage);
    try { await app.stage.init(); } catch (e) {
      app.ui.stageWrap.append(h('div', { class: 'proto-overlay' }, h('div', { class: 'proto-overlay-title' }, '無法啟動 WebGL'), h('div', { class: 'proto-overlay-note' }, String(e && e.message || e))));
      return;
    }
    app.assets = new Proto.Assets(config.assets, app.events);
    app.audio = new Proto.AudioManager(app.assets);
    const vol = config.volume || {};
    if (vol.master !== undefined) app.audio.master = vol.master;
    for (const ch of ['bgm', 'se', 'voice']) if (vol[ch] !== undefined) app.audio.channels[ch] = vol[ch];
    app.stage.assets = app.assets;
    app.stage.audio = app.audio;

    // 結果來源
    app.service = new Proto.svc.Recorder(Proto.createService(config));
    try { app.info = await app.service.init(); } catch (e) { message(app, `無法連線遊戲服務：${e.code || ''} ${e.message || e}`); return; }
    const fxSeed = (((app.info.seed ?? Math.floor(Math.random() * 4294967296)) ^ Proto.svc.FX_XOR) >>> 0);
    app.rng = Proto.createRng(fxSeed);   // 演出流（Timeline random 等）
    app.timeline = new Proto.Timeline(app);

    app.ui.showLoading();
    await app.assets.load((d, t) => app.ui.progress(d, t));
    if (app.assets.fileProtocolBlocked && app.assets.missing().some((a) => a.kind === 'image')) {
      message(app, '以 file:// 直接開啟時，瀏覽器不允許 WebGL 讀取本機圖片。\n\n請改用：\n  python stage_build.py … --serve（本機 http 服務）\n或建置內嵌版：--inline-assets\n\n（點此以佔位圖繼續）').onclick = function () { this.remove(); };
    }

    app.module = new Module(app);
    if (app.module.init) await app.module.init();

    app.ui.addTab('設定檢查', (el) => renderIssues(app, el));
    app.ui.addTab('演出測試', (el) => renderPerfTest(app, el));
    app.ui.addTab('演出記錄', (el) => renderLog(app, el));
    app.ui.addTab('素材替換', (el) => renderAssetSwap(app, el));
    app.ui.addTab('服務', (el) => renderService(app, el), { live: true });
    for (const tab of (app.module.debugTabs && app.module.debugTabs()) || []) app.ui.addTab(tab.title, tab.render, tab);

    const issues = Proto.validate(app);
    app.issues = issues;
    await app.ui.waitStart(app.assets.missing().length);
    if (issues.some((i) => i.level === 'error')) console.warn('設定檢查發現問題：', issues);
    if (app.module.start) app.module.start();
    app.events.emit('started');
  };

  // ---------- 服務：結果來源、錄製 / 重播、連線統計、效能 ----------
  function renderService(app, el) {
    const s = app.service.svc || app.service;
    const rec = app.service;
    const file = h('input', { type: 'file', accept: '.json', hidden: true });
    file.onchange = async () => {
      const f = file.files[0];
      if (!f) return;
      const tr = JSON.parse(await f.text());
      app.service = new Proto.svc.Recorder(new Proto.svc.ReplayService(tr));
      app.info = await app.service.init();
      app.events.emit('service-changed', app.info);
      app.ui.renderTab();
    };
    const fps = app.stage.fps ? app.stage.fps().toFixed(0) : '—';
    const r = app.stage.renderer;
    el.append(
      h('p', { class: 'proto-note' }, '演出層只向 GameService 要結果（SpinResult）。錄下來的軌跡可以在任何時候用「載入軌跡」重播，演出完全相同。'),
      Proto.table(['項目', '值'], [
        ['來源', s.kind], ['seed', s.seed ?? '—'], ['已錄局數', rec.results ? rec.results.length : 0],
        ['餘額（Service）', Proto.fmt.int(app.module && app.module.state ? app.module.state.balance : 0)],
        ['Http 呼叫 / 重試', s.stats ? `${s.stats.calls} / ${s.stats.retries}（上次 ${s.stats.lastMs} ms）` : '—'],
        ['Http 錯誤', s.stats ? JSON.stringify(s.stats.errors) : '—'],
        ['FPS', fps], ['補間數', Proto.tween.count()], ['Renderer', r ? r.name || r.type : '—'],
      ]),
      h('div', { class: 'proto-row' },
        h('button', { onclick: () => rec.trace && Proto.download(`${app.config.name || 'stage'}.trace.json`, JSON.stringify(rec.trace()), 'application/json') }, '下載軌跡（.trace.json）'),
        h('button', { onclick: () => { file.value = ''; file.click(); } }, '載入軌跡（重播）')),
      file,
    );
  }

  // ---------- 設定檢查 ----------
  Proto.validate = function (app) {
    const issues = [];
    const cfg = app.config;
    const perfs = cfg.performances || {};
    const refs = { perfs: new Set(), images: new Set(), videos: new Set(), sounds: new Set() };
    for (const steps of Object.values(perfs)) Proto.Timeline.collectRefs(steps, refs);
    const modRefs = (app.module.references && app.module.references()) || {};
    for (const k of Object.keys(refs)) for (const x of modRefs[k] || []) refs[k].add(x);

    for (const p of refs.perfs) if (!perfs[p]) issues.push({ level: 'error', text: `用到了演出「${p}」，但 performances 裡沒有定義` });
    for (const [kind, label] of [['images', '圖片'], ['videos', '影片'], ['sounds', '音效']]) {
      for (const id of refs[kind]) if (!app.assets[kind][id]) issues.push({ level: 'error', text: `用到了${label}代號「${id}」，但 assets.${kind} 裡沒有登記` });
    }
    for (const a of app.assets.missing()) issues.push({ level: 'warn', text: `素材缺檔：${a.id} → ${a.src}` });
    for (const [kind, label] of [['images', '圖片'], ['videos', '影片'], ['sounds', '音效']]) {
      for (const id of Object.keys(app.assets[kind])) if (!refs[kind].has(id)) issues.push({ level: 'info', text: `${label}「${id}」有登記，但目前沒有演出用到` });
    }
    for (const name of Object.keys(perfs)) if (!refs.perfs.has(name)) issues.push({ level: 'info', text: `演出「${name}」有定義，但沒有被使用` });
    for (const i of (app.module.validate && app.module.validate()) || []) issues.push(i);
    return issues;
  };

  function renderIssues(app, el) {
    const issues = Proto.validate(app);
    const count = (lv) => issues.filter((i) => i.level === lv).length;
    el.append(h('p', { class: 'proto-note' }, `錯誤 ${count('error')}、警告 ${count('warn')}、提示 ${count('info')}`));
    if (!issues.length) el.append(h('p', {}, '沒有發現問題 👍'));
    const icon = { error: '❌', warn: '⚠️', info: 'ℹ️' };
    const order = { error: 0, warn: 1, info: 2 };
    el.append(Proto.table(['', '內容'], issues.sort((a, b) => order[a.level] - order[b.level]).map((i) => [icon[i.level], i.text])));
  }

  // ---------- 演出測試：直接播放任何一個演出 ----------
  function renderPerfTest(app, el) {
    const ctxInput = h('input', { type: 'text', value: app.lastTestCtx || 'hit=true', style: { width: '100%' } });
    el.append(
      h('p', { class: 'proto-note' }, '直接播放單一演出，用來檢查節奏和素材。下面可以設定條件變數，格式：hit=true, mode=rush'),
      ctxInput,
    );
    const parseCtx = () => {
      app.lastTestCtx = ctxInput.value;
      const ctx = {};
      for (const part of ctxInput.value.split(',')) {
        const [k, v] = part.split('=').map((s) => s && s.trim());
        if (!k) continue;
        ctx[k] = v === undefined ? true : v === 'true' ? true : v === 'false' ? false : Number.isNaN(Number(v)) ? v : Number(v);
      }
      return ctx;
    };
    const rows = Object.keys(app.config.performances || {}).map((name) => [
      name,
      h('button', { onclick: () => app.timeline.play(name, parseCtx()) }, '▶ 播放'),
    ]);
    el.append(
      h('div', { class: 'proto-row' }, h('button', { onclick: () => { app.timeline.cancelAll(); app.audio.stopAll({ keepBgm: true }); app.stage.clear('effect'); app.stage.clear('video'); } }, '■ 停止所有演出')),
      Proto.table(['演出', ''], rows),
    );
  }

  // ---------- 素材替換：美術直接換圖看效果（只在這次開啟有效，重新整理就還原） ----------
  function replaceImage(app, a, file) {
    return app.assets.swap(a.id, URL.createObjectURL(file), file.name);   // Stage：熱替換 → asset-swap 事件
  }

  function renderAssetSwap(app, el) {
    const imgs = Object.values(app.assets.images);
    const base = (s) => String(s).split(/[\\/]/).pop().replace(/\.[^.]+$/, '');
    const done = (ids) => { app.events.emit('assets-changed', ids); app.ui.renderTab(); };
    const one = h('input', { type: 'file', accept: 'image/*', hidden: true });
    const many = h('input', { type: 'file', accept: 'image/*', multiple: true, hidden: true });
    let target = null;
    one.onchange = async () => {
      if (!one.files[0] || !target) return;
      await replaceImage(app, target, one.files[0]);
      done([target.id]);
    };
    many.onchange = async () => {
      const hit = [];
      const miss = [];
      for (const f of many.files) {
        const name = base(f.name);
        const a = imgs.find((x) => x.id === name || base(x.origSrc || x.src) === name);
        if (!a) { miss.push(f.name); continue; }
        await replaceImage(app, a, f);
        hit.push(a.id);
      }
      done(hit);
      if (miss.length) alert(`以下檔案對不到任何素材（檔名要等於代號或原檔名）：\n${miss.join('\n')}`);
    };
    el.append(
      h('p', { class: 'proto-note' }, '點「替換」換單張；「批次替換」一次選多個檔案，檔名（不含副檔名）等於代號或原本的檔名就會對上。只在這次開啟有效，重新整理就還原，不會改到檔案。'),
      h('div', { class: 'proto-row' },
        h('button', { onclick: () => { many.value = ''; many.click(); } }, '批次替換'),
        h('button', { onclick: async () => {
          const ids = [];
          for (const a of imgs) if (a.origSrc) { a.src = a.origSrc; a.origSrc = null; a.replacedBy = null; await app.assets.loadImage(a); ids.push(a.id); }
          done(ids);
        } }, '全部還原')),
      one, many,
      Proto.table(['', '代號', '檔案', ''], imgs.map((a) => [
        a.ok ? h('img', { src: a.src, style: { width: '44px', height: '44px', objectFit: 'contain', background: '#222' } }) : h('span', { class: 'proto-bad' }, '缺'),
        a.id,
        a.replacedBy ? h('span', { class: 'proto-good' }, `→ ${a.replacedBy}`) : base(a.src),
        h('button', { onclick: () => { target = a; one.value = ''; one.click(); } }, '替換'),
      ])),
    );
  }

  // ---------- 演出記錄：每個步驟實際執行的時間點 ----------
  const TYPE_LABEL = { perf: '演出開始', 'perf-end': '演出結束', sound: '音效', bgm: 'BGM', stopSound: '停止音效', video: '影片', image: '圖片', text: '文字', flash: '閃光', shake: '震動', emit: '事件', label: '標記', random: '隨機', missing: '缺演出', unknown: '錯誤步驟' };

  function logRows(app) {
    return app.timeline.log.map((e) => [e.t.toFixed(2), TYPE_LABEL[e.type] || e.type, e.name, e.len ? Number(e.len).toFixed(2) : '', e.perf, e.note || '']);
  }

  function renderLog(app, el) {
    const headers = ['秒', '類型', '名稱', '長度', '所在演出', '備註'];
    const rows = logRows(app);
    el.append(
      h('p', { class: 'proto-note' }, '時間已換算成 1 倍速，倍速測試時記下的時間點也正確。'),
      h('div', { class: 'proto-row' },
        h('button', { onclick: () => { app.ui.renderTab(); } }, '↻ 重新整理'),
        h('button', { onclick: () => { app.timeline.log = []; app.ui.renderTab(); } }, '清除'),
        h('button', { onclick: () => Proto.download(`${app.config.name || '原型'}_演出記錄.csv`, [headers, ...logRows(app)].map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n'), 'text/csv') }, '下載 CSV'),
        h('button', { onclick: () => {
          const md = [`| ${headers.join(' | ')} |`, `|${headers.map(() => '---').join('|')}|`, ...logRows(app).map((r) => `| ${r.join(' | ')} |`)].join('\n');
          navigator.clipboard.writeText(md).then(() => alert('已複製 Markdown 表格'));
        } }, '複製 Markdown')),
      h('p', { class: 'proto-note' }, `共 ${rows.length} 筆，顯示最後 300 筆`),
      Proto.table(headers, rows.slice(-300).reverse()),
    );
  }
})();
