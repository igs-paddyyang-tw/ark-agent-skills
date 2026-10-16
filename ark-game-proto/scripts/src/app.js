/* app — 驗證台（L1 精算 / L2 模擬 / 規格缺口 / 單局）＋ PixiJS 演出層
 * 演出層只讀 SpinResult；任何「強制情境」都是搜尋真實 seed，不改結果。
 */
(async function () {
  'use strict';
  const cfg = window.GAME_CONFIG;
  const T = cfg.targets, TS = T.summary;
  let C = SlotCore.compile(cfg);
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const f = (x, d = 2) => (x == null || !isFinite(x) ? '—' : Number(x).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const credits = (x) => Number(x).toLocaleString('en-US');
  const BET = C.bet;

  // ───────── 判定 ─────────
  const TOL = TS.tol || 0.2;
  function vPP(a, b, tol = TOL) { if (a == null || b == null) return 'info'; const d = Math.abs(a - b); return d <= tol ? 'pass' : d <= 2 * tol ? 'warn' : 'fail'; }
  function vRel(a, b, r = 0.01) { if (a == null || b == null || !b) return 'info'; const d = Math.abs(a / b - 1); return d <= r ? 'pass' : d <= 3 * r ? 'warn' : 'fail'; }
  function vCI(a, b, ci) { if (a == null || b == null) return 'info'; const d = Math.abs(a - b); return d <= ci ? 'pass' : d <= 2 * ci ? 'warn' : 'fail'; }
  const LBL = { pass: 'PASS', warn: 'WARN', fail: 'FAIL', info: '—' };
  const badge = (v, t) => `<span class="v ${v}">${v === 'pass' ? '✓' : v === 'fail' ? '✗' : v === 'warn' ? '!' : ''} ${t || LBL[v]}</span>`;

  // ───────── header ─────────
  $('#chipSrc').innerHTML = `來源 <b>${esc(cfg.source.md)}</b> · sha <b>${cfg.source.sha16.slice(0, 8)}</b>`;
  $('#chipMode').innerHTML = `${esc(cfg.source.mode)} 模式 · verdict <b>${esc(cfg.source.verdict)}</b> · ${esc(cfg.source.date)}`;
  const session = { n: 0, bet: 0, win: 0, balance: BET * 1000 };
  function sessionChip() {
    $('#chipSession').innerHTML = `本次 <b>${session.n}</b> 局 · RTP <b>${session.bet ? f((100 * session.win) / session.bet) + '%' : '—'}</b>`;
  }
  sessionChip();

  // ───────── tabs ─────────
  document.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('.tabs button').forEach((x) => x.classList.toggle('on', x === b));
    document.querySelectorAll('.pane').forEach((p) => p.classList.toggle('on', p.id === 'pane-' + b.dataset.tab));
  }));

  // ═════════ L1 精算 ═════════
  const CL = C.model === 'coin-lock';
  const HC = C.model === 'house-collect';
  const exactOf = (c) => SlotCore.exact(c, HC ? { bonusN: 8000, mgN: 120000 } : { bonusN: 40000 });
  let E = exactOf(C);
  const groupDetail = T.fg_group_detail || {}, bonusSpec = T.bonus || {};
  const TX2 = T.bonus || {};                       // house：§2 三變體 + Free（adapter targets_extra）
  const houseAvg = (T.house_avg || {});
  const VLABEL = { Free: 'Free（SC 觸發）', mega_hat: '大帽子 Mega Hat', buzz_saw: '推土機 Buzz Saw', mansions: '豪宅 Mansions' };
  function renderL1House() {
    E = exactOf(C);
    const freeSpec = TX2.Free || {}, bonusTot = TX2.BonusTotal || {};
    const rtpFreeSpec = T.rtp_breakdown ? T.rtp_breakdown.free : (freeSpec.rtp != null ? freeSpec.rtp : TS.rtp_free);
    const rtpBonusSpec = T.rtp_breakdown ? T.rtp_breakdown.bonus : (bonusTot.rtp != null ? bonusTot.rtp : null);
    const rtpMainSpec = T.rtp_breakdown ? T.rtp_breakdown.main : TS.rtp_main;
    const rtpTotSpec = T.rtp_breakdown ? T.rtp_breakdown.total : TS.rtp_total;
    const rows = [
      ['主遊戲 RTP', rtpMainSpec, E.rtp_main, '%', vPP(E.rtp_main, rtpMainSpec, Math.max(TOL, 0.5)), '抽樣（含雙神秘圖騰替換，無解析解）'],
      ['免費遊戲 RTP（SC 觸發 Free）', rtpFreeSpec, E.rtp_free, '%', vPP(E.rtp_free, rtpFreeSpec, Math.max(TOL, 0.5)), 'house-collect 整場抽樣'],
      ['大轉盤 RTP（三變體合計）', rtpBonusSpec, E.rtp_bonus, '%', vPP(E.rtp_bonus, rtpBonusSpec, Math.max(TOL, 1)), 'BS≥3 分流三變體'],
      ['FG 觸發率（SC+大轉盤合計）', TS.fg_rate, E.fg_rate, '%', vRel(E.fg_rate, TS.fg_rate, 0.03), 'SC≥6 進 FG、BS≥3 進大轉盤（解析卷積）'],
      ['總 RTP', rtpTotSpec, E.rtp_total, '%', vPP(E.rtp_total, rtpTotSpec, Math.max(TOL, 1)), '容許放寬（抽樣 + Python MT 非 Go）'],
    ];
    const tot = rows[rows.length - 1];
    $('#chipL1').innerHTML = `L1 精算總 RTP <b>${f(E.rtp_total, 2)}%</b> / 規格 ${f(rtpTotSpec, 2)}% ${badge(tot[4])}`;
    let h = `<h3>一表看完：規格 §2 vs 引擎精算（house-collect）</h3>
      <p class="note">房子三階升級收集＋溢出轉移＋全盤 15 棟換池是路徑相依，<b>無解析解</b> → L1 以固定 seed 抽樣整場 FG（每變體約 ${credits(E.bonusN)} 場）估期望、附 95% CI；MG 含雙神秘圖騰替換也以抽樣估。
      ⚠️ 本款快測引擎是 <b>Python Mersenne Twister（非 Go）</b>，proto 招牌的「Go 同 seed 逐局對照」用不上（G-TP-PARITY），驗證強度為 L1 精算 + L2 模擬對 §2，容許放寬並標註。</p>
      <div class="kpis">
        <div class="kpi"><div class="l">總 RTP（精算）</div><div class="n">${f(E.rtp_total, 2)}%</div><div class="s">規格 ${f(rtpTotSpec, 2)}% · Δ ${f(E.rtp_total - rtpTotSpec, 2)} pp</div></div>
        <div class="kpi"><div class="l">免費遊戲 RTP</div><div class="n">${f(E.rtp_free, 2)}%</div><div class="s">規格 ${f(rtpFreeSpec, 2)}%</div></div>
        <div class="kpi"><div class="l">大轉盤 RTP</div><div class="n">${f(E.rtp_bonus, 2)}%</div><div class="s">規格 ${f(rtpBonusSpec, 2)}%</div></div>
      </div>
      <table><tr><th>指標</th><th>規格 §2</th><th>精算</th><th>差</th><th>判定</th></tr>
      ${rows.map((r) => `<tr title="${esc(r[5])}"><td>${r[0]}</td><td class="num">${f(r[1], 3)}${r[3]}</td><td class="num">${f(r[2], 3)}${r[3]}</td><td class="num">${f(r[2] - r[1], 3)}</td><td>${badge(r[4])}</td></tr>`).join('')}</table>`;
    // 四變體明細
    h += `<h3>四變體：觸發率 / 均倍 / 平均手數 / RTP / 房子均棟（規格 §2 vs 精算）</h3>
      <div style="overflow-x:auto"><table><tr><th>變體</th><th>每幾局 規/算</th><th>均倍 規/算 ±CI</th><th>平均手數 規/算</th><th>RTP 規/算</th><th>草/木/磚 規/算</th><th>判定</th></tr>
      ${C.G.map((g) => { const x = E.groups[g] || {}, s = TX2[g] || {}, ha = houseAvg[g] || {};
        if (!x.n) return `<tr><td>${esc(VLABEL[g] || g)}</td><td colspan="6" class="num">—（抽樣 0 場）</td></tr>`;
        const freqSpec = s.freq, avgSpec = s.multi, rtpSpec = s.rtp;
        const v = [vRel(100 / x.rate, freqSpec, 0.05), vCI(x.avg_win, avgSpec, 3 * (x.avg_ci || 0) + 0.08 * (avgSpec || 1))];
        const worst = v.includes('fail') ? 'fail' : v.includes('warn') ? 'warn' : 'pass';
        return `<tr><td>${esc(VLABEL[g] || g)}</td><td class="num">${f(freqSpec, 0)} / ${f(100 / x.rate, 0)}</td><td class="num">${f(avgSpec)} / ${f(x.avg_win)} ±${f(x.avg_ci)}</td><td class="num">${s.avg_spin != null ? f(s.avg_spin) : (g === 'Free' ? f(freeSpec.avg_spin) : '—')} / ${f(x.spins)}</td><td class="num">${f(rtpSpec)}% / ${f(x.rtp)}%</td><td class="num">${f(ha.grass, 1)}/${f(ha.wood, 1)}/${f(ha.stone, 1)} · ${f(x.grass, 1)}/${f(x.wood, 1)}/${f(x.stone, 1)}</td><td>${badge(worst)}</td></tr>`; }).join('')}</table></div>
      <p class="note">房子均棟（草/木/磚）直接驗 SC 落格升級＋溢出轉移的路徑是否正確（G-TP-2）；對得上代表框升級邏輯忠實。stone15 換池門檻見 G-TP-3。</p>`;
    $('#pane-l1').innerHTML = h;
  }
  function renderL1() {
    if (HC) { renderL1House(); return; }
    E = exactOf(C);
    const rows = CL ? [
      ['主遊戲 RTP', TS.rtp_main, E.rtp_main, '%', vPP(E.rtp_main, TS.rtp_main, Math.min(TOL, 0.5)), '輪帶 × Odds × 倍數 WILD（解析解）'],
      ['Bonus 觸發率（合計）', TS.fg_rate, E.fg_rate, '%', vRel(E.fg_rate, TS.fg_rate, 0.02), 'G-TD-3 觸發規則（解析解）'],
      ['Bonus 平均倍率', TS.fg_avg, E.fg_avg, '倍', vRel(E.fg_avg, TS.fg_avg, 0.05), 'Bonus 直接抽樣 ' + credits(E.bonusN) + ' 次 / 種'],
      ['免費遊戲 RTP', TS.rtp_free, E.rtp_free, '%', vPP(E.rtp_free, TS.rtp_free), ''],
      ['總 RTP', TS.rtp_total, E.rtp_total, '%', vPP(E.rtp_total, TS.rtp_total), '容許 ±' + TOL + ' pp'],
    ] : [
      ['主遊戲 RTP', TS.rtp_main, E.rtp_main, '%', vPP(E.rtp_main, TS.rtp_main), '表 M-1 × Strip × Pay table'],
      ['FG 觸發率', TS.fg_rate, E.fg_rate, '%', vRel(E.fg_rate, TS.fg_rate), 'G-1 SC+SS ≥ ' + C.trigMin],
      ['FG 平均倍率', TS.fg_avg, E.fg_avg, '倍', vRel(E.fg_avg, TS.fg_avg), 'F-1 / F-2 / M-3 / M-5'],
      ['平均初始基底', T.fg_detail?.base_avg, E.fg_base, '倍', vRel(E.fg_base, T.fg_detail?.base_avg), 'M-5 + G-2'],
      ['平均總乘倍', T.fg_detail?.avg_mult, E.avg_mult, '×', vRel(E.avg_mult, T.fg_detail?.avg_mult), 'F-2 金龍 ×1 / 彩龍 ×2'],
      ['免費遊戲 RTP', TS.rtp_free, E.rtp_free, '%', vPP(E.rtp_free, TS.rtp_free), ''],
      ['總 RTP', TS.rtp_total, E.rtp_total, '%', vPP(E.rtp_total, TS.rtp_total), '容許 ±' + TOL + ' pp'],
    ];
    const tot = rows[rows.length - 1];
    $('#chipL1').innerHTML = `L1 精算總 RTP <b>${f(E.rtp_total, 3)}%</b> / 規格 ${f(TS.rtp_total, 3)}% ${badge(tot[4])}`;
    let h = `<h3>一表看完：規格 §2 vs 引擎精算</h3>
      <p class="note">${CL ? `主遊戲與觸發率逐停點解析（不抽樣）；三種 Bonus 以固定 seed 直接抽樣估期望（含 MaxWin ${credits(C.maxWin)} 倍封頂）。§2 是 ${credits(TS.spins)} 手快測，本身有抽樣誤差，故容許 ±${TOL} pp。`
        : `${C.maxWin ? `MaxWin 封頂 ${credits(C.maxWin)} 倍（${esc(cfg.board.max_win_src || '規格書')}）只在 L2 / 遊玩生效，精算不含封頂（影響極小）。` : ''}精算＝對輪帶每個停點逐一計算期望值（All Ways 解析解 + 觸發顆數二維卷積 + F-2 期望），與蒙地卡羅無關。`}
      同一份規格表若算不回快測數字，代表規格書缺規則或引擎讀錯表。</p>
      <div class="kpis">
        <div class="kpi"><div class="l">總 RTP（精算）</div><div class="n">${f(E.rtp_total, 2)}%</div><div class="s">規格 ${f(TS.rtp_total, 2)}% · Δ ${f(E.rtp_total - TS.rtp_total, 3)} pp</div></div>
        <div class="kpi"><div class="l">主遊戲 RTP</div><div class="n">${f(E.rtp_main, 2)}%</div><div class="s">規格 ${f(TS.rtp_main, 2)}%</div></div>
        <div class="kpi"><div class="l">${CL ? 'Bonus' : '免費遊戲'} RTP</div><div class="n">${f(E.rtp_free, 2)}%</div><div class="s">規格 ${f(TS.rtp_free, 2)}%</div></div>
      </div>
      ${CL ? '' : `<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
        <span class="small" style="font-size:12px;color:var(--ink3)">G-2 SS「*k」語意</span>
        <span class="seg" id="ssMode"><button data-m="sc_sum">*k 乘 SC 總和</button><button data-m="total">*k 乘全部基底</button></span></div>`}
      <table><tr><th>指標</th><th>規格 §2</th><th>精算</th><th>差</th><th>判定</th></tr>
      ${rows.map((r) => `<tr title="${esc(r[5])}"><td>${r[0]}</td><td class="num">${f(r[1], 4)}${r[3]}</td><td class="num">${f(r[2], 4)}${r[3]}</td><td class="num">${f(r[2] - r[1], 4)}</td><td>${badge(r[4])}</td></tr>`).join('')}
      ${TS.golden ? `<tr><td>golden（M-1 加權 TOTAL）</td><td class="num">${f(TS.golden, 2)}%</td><td class="num">${f(E.rtp_total, 2)}%</td><td class="num">${f(E.rtp_total - TS.golden, 3)}</td><td>${badge('info', '參考')}</td></tr>` : ''}</table>`;
    h += `<h3>輪帶組：主遊戲 RTP 逐組精算</h3>
      <p class="note">${CL ? 'R1–R5 欄 = 每軸用第幾組輪帶。' : '規格欄 = M-1 的 TOTAL RTP − FG RTP（xlsx 理論值）。旗標 0 = Reels_0、1 = Reels_1。'}</p>
      <table><tr><th>組</th><th>R1–R5</th><th>權重</th><th>規格 MG</th><th>精算 MG</th><th>觸發率</th><th>判定</th></tr>
      ${E.reelsets.map((r) => `<tr><td>#${r.idx}</td><td class="num">${C.reelsets[r.idx].use.join('')}</td><td class="num">${r.w}</td><td class="num">${r.spec_mg == null ? '—' : f(r.spec_mg, 2) + '%'}</td><td class="num">${f(r.mg_rtp, 2)}%</td><td class="num">${f(r.trig, 3)}%</td><td>${r.spec_mg == null ? badge('info') : badge(vPP(r.mg_rtp, r.spec_mg, 0.2))}</td></tr>`).join('')}</table>`;
    if (CL) {
      h += `<h3>三種 Bonus（§2 的 Ultra / Strong / Normal 列 = Tiger / Dragon / Tiger&amp;Dragon，見 G-TD-7）</h3>
        <div style="overflow-x:auto"><table><tr><th>Bonus</th><th>每幾局觸發 規格/精算</th><th>均倍 規格/精算 ±CI</th><th>平均局數 規格/精算</th><th>RTP 規格/精算</th><th>判定</th></tr>
        ${C.G.map((g) => { const x = E.groups[g], s = bonusSpec[g] || {};
          const v = [vRel(100 / x.rate, s.freq, 0.03), vCI(x.avg_win, s.avg_win, 3 * x.avg_ci + 0.02 * s.avg_win), vRel(x.spins, s.spins, 0.03)];
          const worst = v.includes('fail') ? 'fail' : v.includes('warn') ? 'warn' : 'pass';
          return `<tr><td>${esc(g)}</td><td class="num">${f(s.freq, 0)} / ${f(100 / x.rate, 0)}</td><td class="num">${f(s.avg_win)} / ${f(x.avg_win)} ±${f(x.avg_ci)}</td><td class="num">${f(s.spins)} / ${f(x.spins)}</td><td class="num">${f(s.rtp)}% / ${f(x.rtp)}%</td><td>${badge(worst)}</td></tr>`; }).join('')}</table></div>
        <p class="note">JACKPOT（T&amp;D 累計 ${C.jackpot.threshold} 顆）發生率：${f(E.groups[C.G[2]].jp_rate, 2)}% / 次 Tiger&amp;Dragon。</p>`;
    } else {
      h += `<h3>FG 強中弱（表 F-1 / F-2 / M-3 / M-5）</h3>
        <table><tr><th>組別</th><th>機率</th><th>均基底 規格/精算</th><th>均乘倍 規格/精算</th><th>均贏分 規格/精算</th><th>判定</th></tr>
        ${C.G.map((g) => { const x = E.groups[g], s = groupDetail[g] || {}; return `<tr><td>${g}</td><td class="num">${f(100 * x.p, 1)}%</td><td class="num">${f(s['均基底'])} / ${f(x.base)}</td><td class="num">${f(s['均乘倍'])} / ${f(x.mult)}</td><td class="num">${f(s['均贏分'])} / ${f(x.avg_win)}</td><td>${badge(vRel(x.avg_win, s['均贏分']))}</td></tr>`; }).join('')}</table>`;
      const keys = Object.keys(E.entry).map(Number).sort((a, b) => a - b).filter((k) => E.entry[k].share > 0.005);
      h += `<h3>進場 SC 顆數 → 平均 FG 倍率（G-2 的鑑別表）</h3>
        <p class="note">SC 少 = SS 多；這張表最能分辨 SS「*k」到底乘在哪裡。</p>
        <table><tr><th>SC</th><th>佔比 規格/精算</th><th>均 FG 倍率 規格/精算</th><th>判定</th></tr>
        ${keys.map((k) => { const s = (T.entry_sc || {})[k] || {}, e = E.entry[k]; return `<tr><td>${k} 顆</td><td class="num">${f(s.share)} / ${f(e.share)}</td><td class="num">${f(s.avg_win)} / ${f(e.avg_win)}</td><td>${badge(vRel(e.avg_win, s.avg_win, 0.02))}</td></tr>`; }).join('')}</table>`;
      const tk = Object.keys(E.trig).map(Number).sort((a, b) => a - b).filter((k) => E.trig[k] > 0.005);
      h += `<h3>觸發面：進場特殊符號顆數</h3>
        <table><tr><th>顆數</th><th>規格</th><th>精算</th></tr>${tk.map((k) => `<tr><td>${k}</td><td class="num">${f((T.trigger_specials || {})[k])}%</td><td class="num">${f(E.trig[k])}%</td></tr>`).join('')}</table>`;
    }
    $('#pane-l1').innerHTML = h;
    document.querySelectorAll('#ssMode button').forEach((b) => {
      b.classList.toggle('on', b.dataset.m === C.ssMode);
      b.onclick = () => { cfg.fg.ss_mul_mode = b.dataset.m; C = SlotCore.compile(cfg); renderL1(); renderGaps(); };
    });
  }

  // ═════════ 規格缺口 ═════════
  function renderGaps() {
    // 自動回驗（gap.auto 指定檢查種類；玩法無關的檢查放這裡）
    const AUTO = {
      fg_rate: () => vRel(E.fg_rate, TS.fg_rate) === 'pass' ? ['pass', '精算觸發率 ' + f(E.fg_rate, 4) + '% ≈ 規格 ' + f(TS.fg_rate, 4) + '%'] : ['fail', '觸發率對不上'],
      fg_base: () => {
        if (!cfg.fg.ss_mul_mode) return ['info', ''];
        const alt = SlotCore.exact(SlotCore.compile({ ...cfg, fg: { ...cfg.fg, ss_mul_mode: C.ssMode === 'sc_sum' ? 'total' : 'sc_sum' } }));
        const b = T.fg_detail?.base_avg || 0, errNow = Math.abs(E.fg_base - b), errAlt = Math.abs(alt.fg_base - b);
        return errNow <= errAlt && vRel(E.fg_base, b, 0.02) === 'pass' ? ['pass', `「${C.ssMode === 'sc_sum' ? '*k 乘 SC 總和' : '*k 乘全部基底'}」重現均基底 ${f(E.fg_base)}（另一解 ${f(alt.fg_base)}）`] : ['warn', '目前語意非最佳解：切換 L1 的 G-2 開關比較'];
      },
      fg_groups: () => C.G.every((g) => vRel(E.groups[g].avg_win, (groupDetail[g] || {})['均贏分']) !== 'fail') ? ['pass', '各組均贏分皆在 1–3% 內'] : ['fail', '組別均贏分對不上'],
      mg_rtp: () => { const v = vPP(E.rtp_main, TS.rtp_main, Math.min(TOL, 0.5)); return [v === 'warn' ? 'pass' : v, `精算 MG ${f(E.rtp_main, 3)}% vs 規格 ${f(TS.rtp_main, 3)}%`]; },
      trig_split: () => { const ok = C.G.every((g) => vRel(100 / E.groups[g].rate, (bonusSpec[g] || {}).freq, 0.03) !== 'fail');
        return [ok ? 'pass' : 'fail', C.G.map((g) => `${g} 1/${f(100 / E.groups[g].rate, 0)}（規格 1/${f((bonusSpec[g] || {}).freq, 0)}）`).join('；')]; },
      bonus_split: () => { const ok = C.G.every((g) => { const x = E.groups[g], s = bonusSpec[g] || {}; return vCI(x.avg_win, s.avg_win, 3 * x.avg_ci + 0.02 * s.avg_win) !== 'fail' && vRel(x.spins, s.spins, 0.03) !== 'fail'; });
        return [ok ? 'pass' : 'fail', C.G.map((g) => `${g} 均 ${f(E.groups[g].avg_win)} 倍 / ${f(E.groups[g].spins)} 局`).join('；')]; },
    };
    const par = (cfg.go_parity || []).filter((x) => !x.mismatch);
    const parTxt = par.length ? `；逐局對照 ${par.map((x) => credits(x.spins) + ' 手').join(' + ')} 0 差異` : '';
    $('#pane-gaps').innerHTML = `<h3>規格缺口與推定（${cfg.gaps.length}）</h3>
      <p class="note">雛型必須「能跑」才看得出規格書哪裡沒寫清楚。每條推定兩道驗證：L1 精算對 §2 數字（自動）＋ Go 快測原始碼證據（adapter 記錄）。都過的應回寫規格書 §3 流程補充 / §6 隱性規則。</p>
      ${cfg.gaps.map((g) => {
        const a = g.auto && AUTO[g.auto] ? AUTO[g.auto]() : ['info', ''];
        const st = g.go && a[0] !== 'fail' ? ['pass', 'Go 已證'] : a[0] === 'pass' ? ['pass', '已回驗'] : a[0] === 'fail' ? ['fail', '不符'] : ['warn', '待確認'];
        return `<div class="gap"><div class="h"><b>${g.id}　${esc(g.what)}</b>${badge(st[0], st[1])}</div>
        <dl><dt>規格</dt><dd>${esc(g.spec)}</dd><dt>推定</dt><dd>${esc(g.assume)}</dd><dt>回驗</dt><dd>${esc(g.check)}</dd>
        ${a[1] ? `<dt>精算</dt><dd>${esc(a[1])}</dd>` : ''}${g.go ? `<dt>Go</dt><dd style="font-family:var(--mono);font-size:11px;word-break:break-all">${esc(g.go)}${esc(parTxt)}</dd>` : ''}</dl></div>`; }).join('')}`;
  }

  // ═════════ Go 對照 ═════════
  function renderGo() {
    const gc = cfg.go_check, gp = cfg.go_parity || [];
    if (!gc && !gp.length) { $('#pane-go').innerHTML = '<p class="note">建置時加 <code>--go-config &lt;設定檔.json&gt;</code>（逐鍵對照）與 <code>--go-parity &lt;parity.json&gt;</code>（逐局對照結果）即顯示。</p>'; return; }
    let h = '';
    if (gp.length) {
      h += `<h3>逐局對照（同 seed，Go math/rand 逐位元移植）</h3>
        <p class="note">Go 端 <code>goparity/&lt;model&gt;_trace.go</code> 輸出每局 輪帶組 / MG / FG / 封頂後總贏分 / 組別 / 觸發顆數；JS 端以同一條 RNG 流逐局重算比對。0 差異 = 雛型引擎與 Go 快測是同一套規則。</p>
        <table><tr><th>seed</th><th>手數</th><th>FG</th><th>封頂局</th><th>差異</th><th>判定</th></tr>
        ${gp.map((x) => `<tr><td class="num">${x.seed}</td><td class="num">${credits(x.spins)}</td><td class="num">${credits(x.fg)}</td><td class="num">${x.capped}</td><td class="num">${x.mismatch}</td><td>${badge(x.mismatch ? 'fail' : 'pass')}</td></tr>`).join('')}</table>`;
    }
    if (gc) {
      h += `<h3>規格書 ⇄ Go 設定檔（${esc(gc.path)} · sha ${gc.sha16.slice(0, 8)}）</h3>
        <p class="note">一致 ${gc.match} · 不一致 ${gc.mismatch} · 規格書缺 ${gc.gap}${gc.filled.length ? `（已以 Go 值補：${gc.filled.join(', ')}，標示來源）` : ''}</p>
        <table><tr><th>鍵</th><th>判定</th></tr>${gc.rules.map((r) => `<tr title="規格：${esc(JSON.stringify(r.spec))}
Go：${esc(JSON.stringify(r.go))}"><td style="white-space:normal">${esc(r.key)}</td><td>${badge(r.ok === true ? 'pass' : r.ok === false ? 'fail' : 'warn', r.ok === true ? '一致' : r.ok === false ? '不一致' : '規格書缺')}</td></tr>`).join('')}</table>`;
    }
    $('#pane-go').innerHTML = h;
  }

  // ═════════ L2 蒙地卡羅 ═════════
  const L2 = { workers: [], st: null, curve: [], target: 0, t0: 0, running: false, seedBase: 20261014 };
  const workerSrc = document.getElementById('core-src').textContent + `
    self.onmessage = (e) => { const { cfg, seed0, n, chunk } = e.data; const C = SlotCore.compile(cfg); let done = 0;
      (function step() { const k = Math.min(chunk, n - done); const st = SlotCore.simulate(C, (seed0 + done) >>> 0, k); done += k;
        self.postMessage({ st, done, final: done >= n }); if (done < n) setTimeout(step, 0); })(); };`;
  const workerURL = URL.createObjectURL(new Blob([workerSrc], { type: 'text/javascript' }));
  function l2Shell() {
    $('#pane-l2').innerHTML = `<h3>蒙地卡羅（Web Worker，seed 可重現）</h3>
      <p class="note">驗證「引擎實作 = 精算」且「引擎 = 快測報表」；判定用 95% 信賴區間。seed 起點 <span class="num">${L2.seedBase}</span>，第 k 支 worker 用不重疊的 seed 區段。</p>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px">
        <button data-n="200000">20 萬手</button><button data-n="2000000">200 萬手</button><button data-n="20000000">2,000 萬手</button><button id="l2stop" disabled>停止</button>
      </div>
      <div class="bar"><i id="l2bar"></i></div><div id="l2status" class="note">尚未執行</div>
      <div class="legend"><span><i style="background:var(--s1)"></i>總 RTP</span><span><i style="background:var(--s2)"></i>主遊戲 RTP</span><span><i style="background:var(--ink3);height:0;border-top:2px dashed var(--ink3)"></i>規格 §2</span></div>
      <svg id="chart" viewBox="0 0 460 220" preserveAspectRatio="none" role="img" aria-label="RTP 收斂曲線"></svg>
      <div id="l2body"></div>`;
    document.querySelectorAll('#pane-l2 button[data-n]').forEach((b) => (b.onclick = () => runL2(+b.dataset.n)));
    $('#l2stop').onclick = stopL2;
  }
  function stopL2() { L2.workers.forEach((w) => w.terminate()); L2.workers = []; L2.running = false; document.querySelectorAll('#pane-l2 button[data-n]').forEach((b) => (b.disabled = false)); $('#l2stop').disabled = true; }
  function runL2(n) {
    stopL2();
    const k = Math.max(1, Math.min(4, (navigator.hardwareConcurrency || 2) - 1));
    L2.st = SlotCore.newStats(C); L2.curve = []; L2.target = n; L2.t0 = performance.now(); L2.running = true;
    document.querySelectorAll('#pane-l2 button[data-n]').forEach((b) => (b.disabled = true)); $('#l2stop').disabled = false;
    const per = Math.ceil(n / k); let finished = 0, dirty = false;
    for (let i = 0; i < k; i++) {
      const w = new Worker(workerURL);
      w.onmessage = (e) => { SlotCore.merge(L2.st, e.data.st); dirty = true; if (e.data.final && ++finished === k) { L2.running = false; dirty = false; renderL2(true); stopL2(); } };
      w.postMessage({ cfg, seed0: (L2.seedBase + i * per) >>> 0, n: per, chunk: 50000 });
      L2.workers.push(w);
    }
    (function loop() { if (dirty) { dirty = false; renderL2(false); } if (L2.running) requestAnimationFrame(loop); })();
  }
  function renderL2(final) {
    const st = L2.st, r = SlotCore.report(C, st), N = st.spins;
    L2.curve.push({ n: N, t: r.rtp_total, m: r.rtp_main });
    const secs = (performance.now() - L2.t0) / 1000;
    $('#l2bar').style.width = Math.min(100, (100 * N) / L2.target) + '%';
    $('#l2status').textContent = `${credits(N)} / ${credits(L2.target)} 手 · ${f(N / secs / 1e6, 2)} M 手/秒${final ? ' · 完成' : ''}`;
    const pfg = st.fgN / N, ciFg = 196 * Math.sqrt((pfg * (1 - pfg)) / N);
    const mb = st.fgN ? st.fgBase / st.fgN : 0, ciBase = st.fgN ? (1.96 * Math.sqrt(Math.max(st.fgBase2 / st.fgN - mb * mb, 0) / st.fgN)) / BET : null;
    const mfg = st.fgN ? st.fgWin / st.fgN : 0, ciAvg = st.fgN ? (1.96 * Math.sqrt(Math.max(st.fgWin2 / st.fgN - mfg * mfg, 0) / st.fgN)) / BET : 0;
    const rows = [
      ['總 RTP', TS.rtp_total, E.rtp_total, r.rtp_total, r.rtp_total_ci, '%'],
      ['主遊戲 RTP', TS.rtp_main, E.rtp_main, r.rtp_main, r.rtp_main_ci, '%'],
      ['主遊戲命中率', TS.mg_hit, null, r.mg_hit, 196 * Math.sqrt((r.mg_hit / 100) * (1 - r.mg_hit / 100) / N), '%'],
      ['FG 觸發率', TS.fg_rate, E.fg_rate, r.fg_rate, ciFg, '%'],
      ['FG 平均倍率', TS.fg_avg, E.fg_avg, r.fg_avg, ciAvg, '倍'],
      ...(CL || HC ? [] : [['平均初始基底', T.fg_detail?.base_avg, E.fg_base, r.fg_base, ciBase, '倍'],
        ['全放 888 佔 FG', T.fg_detail?.all888_rate, null, r.all888_rate, st.fgN ? 196 * Math.sqrt((r.all888_rate / 100) * (1 - r.all888_rate / 100) / st.fgN) : null, '%']]),
      ...(C.maxWin ? [['MaxWin 封頂局', null, null, r.cap_rate, null, '%']] : []),
    ];
    let h = `<div class="kpis">
      <div class="kpi"><div class="l">總 RTP（模擬）</div><div class="n">${f(r.rtp_total)}%</div><div class="s">±${f(r.rtp_total_ci)} pp（95%）</div></div>
      <div class="kpi"><div class="l">主遊戲 RTP</div><div class="n">${f(r.rtp_main)}%</div><div class="s">±${f(r.rtp_main_ci)} pp</div></div>
      <div class="kpi"><div class="l">${CL ? 'Bonus' : 'FG'} 次數</div><div class="n">${credits(st.fgN)}</div><div class="s">最大 ${f(r.fg_max, 0)} 倍</div></div></div>
      <table><tr><th>指標</th><th>規格</th><th>精算</th><th>模擬 ±CI</th><th>判定</th></tr>
      ${rows.map((x) => { const ref = x[2] ?? x[1]; const v = x[4] != null ? vCI(x[3], ref, Math.max(x[4], 1e-9)) : vRel(x[3], ref, 0.02);
        return `<tr><td>${x[0]}</td><td class="num">${f(x[1], 3)}${x[5]}</td><td class="num">${x[2] == null ? '—' : f(x[2], 3) + x[5]}</td><td class="num">${f(x[3], 3)}${x[4] != null ? ' ±' + f(x[4], 3) : ''}</td><td>${badge(v)}</td></tr>`; }).join('')}</table>
      <p class="note">判定基準：有精算值時比「模擬 vs 精算」（驗引擎實作）；無精算值時比「模擬 vs 規格」。手數少時 FG 相關指標 CI 很寬，屬正常。</p>
      ${HC ? `<h3>四變體（模擬）</h3><table><tr><th>變體</th><th>佔 FG</th><th>每幾局</th><th>均倍 ±CI</th><th>平均手數</th><th>草/木/磚</th><th>規格均倍</th></tr>
      ${C.G.map((g) => { const x = r.groups[g] || {}; return `<tr><td>${esc(VLABEL[g] || g)}</td><td class="num">${f(x.share)}%</td><td class="num">${x.n ? f(100 / x.rate, 0) : '—'}</td><td class="num">${f(x.avg_win)}${x.n ? ' ±' + f(x.avg_ci) : ''}</td><td class="num">${f(x.spins)}</td><td class="num">${f(x.grass, 1)}/${f(x.wood, 1)}/${f(x.stone, 1)}</td><td class="num">${f((TX2[g] || {}).multi)}</td></tr>`; }).join('')}</table>`
      : CL ? `<h3>三種 Bonus（模擬）</h3><table><tr><th>Bonus</th><th>每幾局</th><th>均倍 ±CI</th><th>平均局數</th><th>JACKPOT</th><th>規格均倍</th></tr>
      ${C.G.map((g) => { const x = r.groups[g] || {}; return `<tr><td>${esc(g)}</td><td class="num">${x.n ? f(100 / x.rate, 0) : '—'}</td><td class="num">${f(x.avg_win)}${x.n ? ' ±' + f(x.avg_ci) : ''}</td><td class="num">${f(x.spins)}</td><td class="num">${f(x.jp_rate)}%</td><td class="num">${f((bonusSpec[g] || {}).avg_win)}</td></tr>`; }).join('')}</table>`
      : `<h3>FG 各組（模擬）</h3><table><tr><th>組別</th><th>佔比</th><th>均基底</th><th>均乘倍</th><th>均贏分</th><th>規格均贏分</th></tr>
      ${C.G.map((g) => { const x = r.groups[g] || {}; return `<tr><td>${g}</td><td class="num">${f(x.share)}%</td><td class="num">${f(x.base)}</td><td class="num">${f(x.mult)}</td><td class="num">${f(x.avg_win)}</td><td class="num">${f((groupDetail[g] || {})['均贏分'])}</td></tr>`; }).join('')}</table>`}
      <h3>贏分分級（M-16 門檻 1/5/10/25/50/100 倍）</h3><table><tr><th>分級</th><th>次數</th><th>每幾手</th></tr>
      ${['LIGHT', 'SMALL', 'BIG', 'MEGA', 'SUPER', 'GOLDEN'].map((k) => `<tr><td>${k}</td><td class="num">${credits(r.tiers[k] || 0)}</td><td class="num">${r.tiers[k] ? f(N / r.tiers[k], 1) : '—'}</td></tr>`).join('')}</table>`;
    $('#l2body').innerHTML = h;
    drawChart();
  }
  function drawChart() {
    const svg = $('#chart'), W = 460, H = 220, P = { l: 40, r: 10, t: 10, b: 22 };
    const pts = L2.curve.filter((p) => p.n > 0);
    if (!pts.length) { svg.innerHTML = ''; return; }
    const ys = pts.flatMap((p) => [p.t, p.m]).concat([TS.rtp_total, TS.rtp_main]);
    let lo = Math.min(...ys), hi = Math.max(...ys); const pad = Math.max(2, (hi - lo) * 0.1); lo -= pad; hi += pad;
    const nMax = pts[pts.length - 1].n;
    const X = (n) => P.l + ((W - P.l - P.r) * n) / nMax, Y = (v) => P.t + ((H - P.t - P.b) * (hi - v)) / (hi - lo);
    const path = (k) => pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.n).toFixed(1)},${Y(p[k]).toFixed(1)}`).join('');
    const ticks = 4; let grid = '';
    for (let i = 0; i <= ticks; i++) { const v = lo + ((hi - lo) * i) / ticks; grid += `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#ffffff12"/><text x="${P.l - 4}" y="${Y(v) + 3}" fill="#8f8377" font-size="9" text-anchor="end">${v.toFixed(0)}%</text>`; }
    const band = `<rect x="${P.l}" width="${W - P.l - P.r}" y="${Y(TS.rtp_total + TOL)}" height="${Math.max(1, Y(TS.rtp_total - TOL) - Y(TS.rtp_total + TOL))}" fill="#3987e522"/>`;
    const ref = (v, lab) => `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#c9bdb0" stroke-dasharray="4 4" stroke-width="1"/><text x="${W - P.r - 2}" y="${Y(v) - 3}" fill="#c9bdb0" font-size="9" text-anchor="end">${lab} ${f(v)}%</text>`;
    const last = pts[pts.length - 1];
    svg.innerHTML = `${grid}${band}${ref(TS.rtp_total, '規格 總')}${ref(TS.rtp_main, '規格 MG')}
      <path d="${path('t')}" fill="none" stroke="#3987e5" stroke-width="2"/><path d="${path('m')}" fill="none" stroke="#d95926" stroke-width="2"/>
      <circle cx="${X(last.n)}" cy="${Y(last.t)}" r="4" fill="#3987e5" stroke="#1d1414" stroke-width="2"/><circle cx="${X(last.n)}" cy="${Y(last.m)}" r="4" fill="#d95926" stroke="#1d1414" stroke-width="2"/>
      <text x="${P.l}" y="${H - 6}" fill="#8f8377" font-size="9">0</text><text x="${W - P.r}" y="${H - 6}" fill="#8f8377" font-size="9" text-anchor="end">${credits(nMax)} 手</text>
      <line id="xh" y1="${P.t}" y2="${H - P.b}" stroke="#ffffff55" visibility="hidden"/><rect x="${P.l}" y="${P.t}" width="${W - P.l - P.r}" height="${H - P.t - P.b}" fill="transparent" id="hit"/>`;
    const tip = $('#tip');
    $('#hit').onmousemove = (ev) => {
      const b = svg.getBoundingClientRect(), x = ((ev.clientX - b.left) / b.width) * W, n = ((x - P.l) / (W - P.l - P.r)) * nMax;
      let p = pts[0]; for (const q of pts) if (Math.abs(q.n - n) < Math.abs(p.n - n)) p = q;
      const xh = $('#xh'); xh.setAttribute('x1', X(p.n)); xh.setAttribute('x2', X(p.n)); xh.setAttribute('visibility', 'visible');
      tip.style.display = 'block'; tip.style.left = ev.clientX + 12 + 'px'; tip.style.top = ev.clientY + 12 + 'px';
      tip.innerHTML = `${credits(p.n)} 手<br>總 RTP ${f(p.t, 3)}%<br>主遊戲 ${f(p.m, 3)}%`;
    };
    $('#hit').onmouseleave = () => { tip.style.display = 'none'; $('#xh').setAttribute('visibility', 'hidden'); };
  }

  // ═════════ 單局 ═════════
  const history = [];
  function renderSpinTab(res) {
    if (!res) { $('#pane-spin').innerHTML = '<p class="note">按 SPIN 後顯示本局 SpinResult 與每一步抽的是哪張表。</p>'; return; }
    const rs = C.reelsets[res.reelset], fg = res.fg;
    const trace = CL ? [
      `輪帶組 #${rs.idx}（權重 ${rs.w}/${C.reelsetT.total}，${esc(rs.src || '')}）各軸用組 ${rs.use.join('')}`,
      `Strip：${rs.use.map((x, i) => `R${i + 1}=組${x}@${res.stops[i]}`).join('、')}`,
      `銅鑼 → 倍數 WILD：${(res.tags || []).length ? res.tags.map((t) => `R${t.r + 1}-${t.y + 1} ×${t.mul}`).join('、') : '無'}（G-TD-2 均勻 ${C.wm.min}～${C.wm.max}）`,
      `243 Ways：${res.ways.length ? res.ways.map((w) => `${w.sym}×${w.len}連 ${w.ways} ways${w.factor ? `（倍數因子和 ${w.factor}）` : ''} × ${w.odds} = ${w.win}`).join('；') : '無連線'} → ${res.mgWin} credit`,
      `虎 ${res.trig.cnt[0]}、龍 ${res.trig.cnt[1]}（G-TD-3）${fg ? ` → ${esc(fg.group)} Bonus${fg.mystery ? '（隨機觸發）' : ''}` : ''}`,
    ] : HC ? [
      `表 M-1 → 輪帶組 #${rs.idx}（權重 ${rs.w}/${C.reelsetT.total}）各軸用帶 ${rs.use.join(',')}`,
      `Strip：${rs.use.map((x, i) => `R${i + 1}=組${x}@${res.stops[i]}`).join('、')}`,
      `雙神秘圖騰替換（MY1→歸零→MY2，全盤換）→ All Ways：${res.ways.length ? res.ways.map((w) => `${w.sym}×${w.len}連 ${w.ways} ways × ${w.odds} = ${w.win}`).join('；') : '無連線'} → ${res.mgWin} credit`,
      `SC ${res.nSC} 顆（≥6 進 FG）· BS ${res.nBS} 顆（≥3 進大轉盤）${fg ? ` → ${VLABEL[fg.variant] || fg.variant}` : ''}`,
    ] : [
      `表 M-1 → 輪帶組 #${rs.idx}（權重 ${rs.w}/${C.reelsetT.total}，${esc(rs.src)}）旗標 ${rs.use.join('')}`,
      `Strip：${rs.use.map((x, i) => `R${i + 1}=Reels_${x}@${res.stops[i]}`).join('、')}`,
      `All Ways：${res.ways.length ? res.ways.map((w) => `${w.sym}×${w.len}連 ${w.ways} ways × ${w.odds} = ${w.win}`).join('；') : '無連線'} → ${res.mgWin} credit`,
      `特殊符號 SC ${res.nSC} + SS ${res.nSS} = ${res.nSC + res.nSS}（G-1 門檻 ${C.trigMin}）${fg ? ' → 進 FG' : ''}`,
    ];
    if (!CL && !fg) trace.push(`盤面 SC/SS 分數牌：表 M-2（演出，不計分）`);
    if (res.tease) trace.push('表 M-4 → 第五輪彩色聽牌（演出）');
    if (fg && CL) {
      const B = C.bonus[fg.type];
      trace.push(`${esc(fg.group)}：${B.reels}×${B.rows}、初始 ${B.spins} 手、${B.reset ? '有金幣落下重置' : '不重置'}、停入率 ${B.coin_rate}/10000 → 實際 ${fg.spins} 手、鎖 ${fg.coins} 顆${fg.type === C.unlock.bonus ? `、解鎖到 ${fg.unlocked} 列` : ''}`);
      trace.push(`結算：${fg.groups.length ? fg.groups.map((g) => `第${g.row + 1}列 ${g.len} 顆 [${g.kinds.map((k, i) => (k === 'arrow' ? '箭頭' : g.raw[i])).join(' ')}]${g.arrowAdd ? ` 箭頭+${g.arrowAdd}` : ''} → ${g.value}`).join('；') : '無相鄰成組'}${fg.jackpot ? `；JACKPOT ${fg.jpWin}` : ''}`);
      trace.push(`Bonus 贏分 ${fg.win}${fg.capped ? `（封頂前 ${fg.raw}）` : ''}（${f(fg.win / BET)} 倍）`);
    } else if (fg && HC) {
      trace.push(`表 F-0 → 強度「${fg.strength}」· 權重組「${fg.variant}_${(fg.strength || '').toUpperCase()}」`);
      trace.push(`FG 迴圈 ${fg.spins} 手（初始 ${C.hSpins} + 本手 SC≥3 加手）· 累計落 SC ${fg.addSc} 顆`);
      trace.push(`框升級結算：草屋 ${fg.houses.grass} · 木屋 ${fg.houses.wood} · 磚屋 ${fg.houses.stone}（磚屋 ${fg.stoneCount} 棟${fg.stoneCount >= C.hStone15 ? `，≥15 換池「${fg.stoneName}」` : ''}）`);
      trace.push(`房子獎 ${credits(fg.score)}${fg.extra ? ` + 全滿額外 ${credits(fg.extra)}` : ''}${fg.lineWin ? ` + 線獎 ${credits(fg.lineWin)}` : ''} = ${credits(fg.win)}（${f(fg.win / BET)} 倍）`);
    } else if (fg) {
      trace.push(`表 F-1 → 組別「${fg.group}」`);
      trace.push(`表 M-3-1 群預告：${fg.preview ? '是' : '否'}；表 M-3-2 全放 888：${fg.all888 ? '是' : '否'}`);
      trace.push(`表 M-5 進場分數：SC [${fg.entry.sc.join(', ')}]；SS [${fg.entry.ss.map((x) => (x.mul ? '*' + x.mul : x.v)).join(', ')}] → 基底 ${fg.base}（${f(fg.base / BET)} 倍）`);
      trace.push(`表 F-2：金幣 ${fg.coins.length} 次 [${fg.coins.join(', ')}]、鯉魚 ${fg.carps.length} 次 [${fg.carps.join(', ')}]、金龍 ${fg.gold}、彩龍 ${fg.color}`);
      trace.push(`G-3：(${fg.base} + ${fg.coins.concat(fg.carps).reduce((a, b) => a + b, 0)}) × ${fg.mult} = ${fg.win}（${f(fg.win / BET)} 倍）`);
      if (fg.revive) trace.push(`表 F-4 復活：保留金龍 ${fg.revive.keepGold}、彩龍 ${fg.revive.keepColor}（演出，不改贏分）`);
    }
    if (res.capped) trace.push(`MaxWin 封頂 ${credits(C.maxWin)} 倍`);
    const grid = res.symGrid || res.grid;
    let g = '<table><tr><th></th>' + grid.map((_, i) => `<th>R${i + 1}</th>`).join('') + '</tr>';
    for (let y = 0; y < C.ROWS; y++) g += `<tr><td>${y + 1}</td>${grid.map((col) => `<td class="num">${esc(col[y])}</td>`).join('')}</tr>`;
    g += '</table>';
    const lite = JSON.parse(JSON.stringify(res)); delete lite.grid; if (lite.fg) delete lite.fg.timeline;
    $('#pane-spin').innerHTML = `<h3>seed ${res.seed} · 總贏分 ${credits(res.totalWin)}（${f(res.totalWin / BET)} 倍 · ${res.winType}）</h3>
      ${g}<h3>抽表軌跡</h3><ol style="margin:0 0 8px;padding-left:18px;font-size:12px;color:var(--ink2)">${trace.map((t) => `<li>${t}</li>`).join('')}</ol>
      <h3>最近 ${history.length} 局（點擊重現）</h3><div class="hist">${history.slice().reverse().map((h) => `<button data-seed="${h.seed}"><span>#${h.seed}</span><span>${h.fg ? 'FG ' + h.fg + ' · ' : ''}${f(h.win / BET)} 倍</span></button>`).join('')}</div>
      <h3>SpinResult（JSON）</h3><pre>${esc(JSON.stringify(lite, null, 1).replace(/\[\s+([^\[\]{}]*?)\s+\]/g, (m, a) => '[' + a.replace(/\s+/g, ' ') + ']'))}</pre>`;
    document.querySelectorAll('#pane-spin .hist button').forEach((b) => (b.onclick = () => playSeed(+b.dataset.seed)));
  }

  renderL1(); renderGaps(); renderGo(); l2Shell(); renderSpinTab(null);

  // ═════════ PixiJS 演出層 ═════════
  const W = 1280, H = 720;
  const app = new PIXI.Application();
  await app.init({ width: W, height: H, background: '#1a0505', antialias: true, resolution: Math.min(window.devicePixelRatio || 1, 2), autoDensity: true });
  $('#game').appendChild(app.canvas);
  const TX = await SlotArt.load(PIXI, 256, [W, H], cfg.art);
  const WILDC = cfg.board.wild || 'WW';
  const SPECIAL = CL ? [cfg.fg.trigger.tiger, cfg.fg.trigger.dragon] : HC ? ['SC', 'BS'] : ['SC', 'SS'];
  const FONT = '"Noto Sans TC","Noto Sans CJK TC","Microsoft JhengHei","PingFang TC",sans-serif';
  const txt = (s, o) => new PIXI.Text({ text: s, style: { fontFamily: FONT, fontSize: 20, fill: '#f3ece4', ...o } });
  const goldTxt = (s, size, o) => txt(s, { fontSize: size, fontWeight: '900', fill: '#ffe08a', stroke: { color: '#5a2a00', width: Math.max(3, size / 8) }, dropShadow: { color: '#000', blur: 6, distance: 2, alpha: 0.6 }, ...o });

  let speed = 1;
  const ease = { out: (t) => 1 - Math.pow(1 - t, 3), inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2), back: (t) => { const c1 = 1.2, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); } };
  function tween(obj, to, ms, e = ease.out) {
    ms = ms * speed;
    const from = {}; for (const k in to) from[k] = obj[k];
    return new Promise((res) => {
      let t = 0;
      const fn = (tk) => { t += tk.deltaMS; const p = Math.min(1, t / ms), q = e(p); for (const k in to) obj[k] = from[k] + (to[k] - from[k]) * q; if (p >= 1) { app.ticker.remove(fn); res(); } };
      if (ms <= 0) { Object.assign(obj, to); res(); } else app.ticker.add(fn);
    });
  }
  const wait = (ms) => new Promise((r) => setTimeout(r, ms * speed));

  // 背景與框
  const bg = new PIXI.Sprite(TX.__bg); bg.width = W; bg.height = H; app.stage.addChild(bg);
  const title = goldTxt(cfg.game, 54, { letterSpacing: 8 }); title.anchor.set(0.5); title.position.set(W / 2, 52); app.stage.addChild(title);
  const sub = txt(`${cfg.board.slot_type === 'WAYS' ? 'All Ways' : 'Lines'} · ${cfg.board.rows}×${cfg.board.reels} · 基本收費 ${BET}`, { fontSize: 15, fill: '#e8cfa0' }); sub.anchor.set(0.5); sub.position.set(W / 2, 92); app.stage.addChild(sub);

  const CW = 150, CH = 136, ROWS = C.ROWS, R = C.R, X0 = (W - R * CW) / 2, Y0 = 122;
  const frame = new PIXI.Graphics()
    .roundRect(X0 - 14, Y0 - 14, R * CW + 28, ROWS * CH + 28, 22).fill({ color: 0x2a0606, alpha: 0.9 }).stroke({ width: 6, color: 0xd9a23a })
    .roundRect(X0 - 4, Y0 - 4, R * CW + 8, ROWS * CH + 8, 14).stroke({ width: 2, color: 0xffe08a, alpha: 0.6 });
  app.stage.addChild(frame);
  for (let r = 1; r < R; r++) app.stage.addChild(new PIXI.Graphics().rect(X0 + r * CW - 1, Y0, 2, ROWS * CH).fill({ color: 0xd9a23a, alpha: 0.25 }));
  const reelLayer = new PIXI.Container(); app.stage.addChild(reelLayer);
  const mask = new PIXI.Graphics().rect(X0, Y0, R * CW, ROWS * CH).fill(0xffffff); app.stage.addChild(mask); reelLayer.mask = mask;
  const fxLayer = new PIXI.Container(); app.stage.addChild(fxLayer);

  function makeCell(sym, tag) {
    const c = new PIXI.Container();
    const s = new PIXI.Sprite(TX[sym] || TX[Object.keys(TX)[0]]); s.anchor.set(0.5); s.width = s.height = 124; c.addChild(s);
    c.sym = sym; c.sprite = s;
    if (tag && (tag.mul != null || tag.v != null)) {
      const label = tag.mul ? '×' + tag.mul : String(tag.v);
      const t = goldTxt(label, tag.v >= 1000 || tag.mul ? 30 : 34, { fill: tag.mul ? '#ffffff' : '#fff2b3' });
      t.anchor.set(0.5); t.y = sym === 'SC' ? 4 : tag.mul && CL ? 40 : 2; c.addChild(t); c.tag = t;
    }
    return c;
  }
  const fakeStrip = cfg.strips.fake || cfg.strips.set0 || cfg.strips.sets[0];
  const randSym = (r) => { const s = fakeStrip[r % fakeStrip.length]; return s[(Math.random() * s.length) | 0]; };
  const reels = [];
  for (let r = 0; r < R; r++) {
    const cont = new PIXI.Container(); cont.x = X0 + r * CW; cont.baseY = Y0; cont.y = Y0; reelLayer.addChild(cont);
    const cells = []; for (let y = 0; y < ROWS; y++) { const c = makeCell(randSym(r)); c.x = CW / 2; c.y = y * CH + CH / 2; cont.addChild(c); cells.push(c); }
    const blur = new PIXI.BlurFilter({ strength: 0, quality: 2 }); blur.strengthX = 0; blur.strengthY = 0; cont.filters = [blur];
    reels.push({ cont, cells, blur });
  }

  async function spinReel(r, finalSyms, tags, n, ms, tease) {
    const R0 = reels[r], cont = R0.cont;
    const tape = [];
    for (let y = 0; y < ROWS; y++) tape.push(makeCell(finalSyms[y], tags[y]));
    for (let i = 0; i < n; i++) tape.push(makeCell(randSym(r)));
    const old = R0.cells;
    cont.removeChildren();
    const all = tape.concat(old);
    all.forEach((c, i) => { c.x = CW / 2; c.y = i * CH + CH / 2; c.alpha = 1; c.scale.set(1); cont.addChild(c); });
    const startY = Y0 - (all.length - ROWS) * CH;
    cont.y = startY;
    const st = { p: 0 };
    let last = 0;
    const blurFn = () => { const v = Math.abs(st.p - last); last = st.p; R0.blur.strengthY = Math.min(18, v * 0.9); };
    app.ticker.add(blurFn);
    const kick = { y: startY };
    // 起步回拉
    await tween(kick, { y: startY - 18 }, 90, ease.out); cont.y = kick.y;
    const prog = { y: kick.y };
    const fn = () => { cont.y = prog.y; st.p = prog.y; };
    app.ticker.add(fn);
    await tween(prog, { y: Y0 }, ms, tease ? ease.inOut : ease.back);
    app.ticker.remove(fn); app.ticker.remove(blurFn); R0.blur.strengthY = 0;
    cont.y = Y0;
    for (let i = ROWS; i < all.length; i++) cont.removeChild(all[i]);
    R0.cells = tape.slice(0, ROWS);
  }

  // 左右資訊板
  const leftP = new PIXI.Container(); leftP.position.set(22, Y0); app.stage.addChild(leftP);
  const rightP = new PIXI.Container(); rightP.position.set(X0 + R * CW + 24, Y0); app.stage.addChild(rightP);
  const panelBg = (w, h) => new PIXI.Graphics().roundRect(0, 0, w, h, 14).fill({ color: 0x000000, alpha: 0.45 }).stroke({ width: 1, color: 0xd9a23a, alpha: 0.5 });
  function drawLeft(res, done) {
    leftP.removeChildren(); leftP.addChild(panelBg(205, ROWS * CH));
    const h = goldTxt(CL ? '輪帶組' : '輪帶組（表 M-1）', 16); h.position.set(12, 10); leftP.addChild(h);
    if (!res) { const t = txt('等待 SPIN', { fontSize: 14, fill: '#c9bdb0' }); t.position.set(12, 44); leftP.addChild(t); return; }
    const rs = C.reelsets[res.reelset];
    const big = goldTxt('#' + rs.idx, 40); big.position.set(12, 34); leftP.addChild(big);
    const w = txt(`權重 ${rs.w} / ${C.reelsetT.total}`, { fontSize: 13, fill: '#e8cfa0' }); w.position.set(84, 46); leftP.addChild(w);
    rs.use.forEach((fl, i) => {
      const b = new PIXI.Graphics().roundRect(12 + i * 37, 96, 32, 40, 6).fill({ color: fl ? 0xb04a12 : 0x1e5a3c }).stroke({ width: 1, color: 0xffe08a, alpha: 0.6 });
      leftP.addChild(b);
      const t = txt(`R${i + 1}\n${CL || HC ? '組' + fl : fl ? '換' : '基'}`, { fontSize: 12, align: 'center', fill: '#fff', lineHeight: 15 }); t.anchor.set(0.5); t.position.set(28 + i * 37, 116); leftP.addChild(t);
    });
    const lines = CL ? [
      `理論 MG ${f(E.reelsets[rs.idx].mg_rtp)}%`,
      `Bonus 觸發 ${f(E.reelsets[rs.idx].trig, 3)}%`,
      ``,
      done ? `虎 ${res.trig.cnt[0]} ＋ 龍 ${res.trig.cnt[1]}` : '虎 ＋ 龍 ＝ …',
      `≥${C.trig.mixed} 混合 / ≥${C.trig.gate} 同種（G-TD-3）`,
      done && res.fg ? `→ ${res.fg.group}${res.fg.mystery ? '（隨機）' : ''}` : '',
    ] : HC ? [
      `MG RTP ${f(E.rtp_main, 1)}%（抽樣）`,
      `觸發率 ${f(E.reelsets[rs.idx].trig, 3)}%`,
      ``,
      done ? `SC ${res.nSC} · BS ${res.nBS}` : 'SC · BS ＝ …',
      `SC≥6 進 FG · BS≥3 進大轉盤`,
      done && res.fg ? `→ ${VLABEL[res.fg.group] || res.fg.group}` : '',
      done && res.fg ? `強度 ${res.fg.strength || '—'}` : '',
      ``,
      `seed ${res.seed}`,
    ] : [
      `理論 MG ${f(E.reelsets[rs.idx].mg_rtp)}%`,
      `觸發率 ${f(E.reelsets[rs.idx].trig, 3)}%`,
      ``,
      done ? `SC ${res.nSC} ＋ SS ${res.nSS} ＝ ${res.nSC + res.nSS}` : 'SC ＋ SS ＝ …',
      `進 FG 門檻 ≥ ${C.trigMin}（G-1）`,
      done && res.fg ? `→ FG 組別「${res.fg.group}」` : '',
      ``,
      `seed ${res.seed}`,
    ];
    const t = txt(lines.join('\n'), { fontSize: 13, fill: '#e9ddcf', lineHeight: 21 }); t.position.set(12, 148); leftP.addChild(t);
  }
  function drawRight(res, hi) {
    rightP.removeChildren(); rightP.addChild(panelBg(205, ROWS * CH));
    const h = goldTxt(CL ? '本局連線（243 Ways）' : '本局連線（All Ways）', 16); h.position.set(12, 10); rightP.addChild(h);
    if (!res) return;
    const ws = res.ways.slice().sort((a, b) => b.win - a.win);
    ws.slice(0, 9).forEach((w, i) => {
      const y = 42 + i * 38;
      if (hi === w) rightP.addChild(new PIXI.Graphics().roundRect(6, y - 4, 193, 34, 6).fill({ color: 0xffe08a, alpha: 0.18 }));
      const s = new PIXI.Sprite(TX[w.sym]); s.width = s.height = 28; s.position.set(10, y - 1); rightP.addChild(s);
      const t = txt(`×${w.len}連 · ${w.ways} ways${w.factor ? ' ·×' + w.factor : ''}`, { fontSize: 12, fill: '#e9ddcf' }); t.position.set(44, y); rightP.addChild(t);
      const v = txt(`${credits(w.win)}`, { fontSize: 14, fill: '#ffe08a', fontWeight: '700' }); v.anchor.set(1, 0); v.position.set(196, y + 6); rightP.addChild(v);
    });
    if (ws.length > 9) { const t = txt(`… 另 ${ws.length - 9} 條`, { fontSize: 12, fill: '#c9bdb0' }); t.position.set(12, 42 + 9 * 38); rightP.addChild(t); }
    if (!ws.length) { const t = txt('無連線', { fontSize: 14, fill: '#c9bdb0' }); t.position.set(12, 46); rightP.addChild(t); }
  }
  drawLeft(null); drawRight(null);

  // 底部列
  const bar = new PIXI.Container(); bar.position.set(0, 572); app.stage.addChild(bar);
  bar.addChild(new PIXI.Graphics().rect(0, 0, W, 148).fill({ color: 0x000000, alpha: 0.55 }).rect(0, 0, W, 2).fill({ color: 0xd9a23a, alpha: 0.7 }));
  const field = (label, x) => { const l = txt(label, { fontSize: 14, fill: '#c9bdb0' }); l.position.set(x, 30); bar.addChild(l); const v = goldTxt('0', 30); v.position.set(x, 52); bar.addChild(v); return v; };
  const balT = field('餘額 credit', 60), betT = field('押注', 330), winT = field('贏分', 880);
  betT.text = credits(BET);
  const winX = txt('', { fontSize: 14, fill: '#e8cfa0' }); winX.position.set(880, 96); bar.addChild(winX);
  const spinBtn = new PIXI.Container(); spinBtn.position.set(W / 2 + 40, 74); bar.addChild(spinBtn);
  const sb = new PIXI.Graphics().circle(0, 0, 54).fill({ color: 0xc0392b }).stroke({ width: 6, color: 0xffe08a }).circle(0, 0, 42).stroke({ width: 2, color: 0xffffff, alpha: 0.5 });
  spinBtn.addChild(sb); const sbt = goldTxt('SPIN', 26); sbt.anchor.set(0.5); spinBtn.addChild(sbt);
  spinBtn.eventMode = 'static'; spinBtn.cursor = 'pointer'; spinBtn.on('pointertap', () => spinOnce());
  function updateBar(win) { balT.text = credits(session.balance); winT.text = credits(win || 0); winX.text = win ? `${f(win / BET)} 倍` : ''; }
  updateBar(0);

  // 橫幅
  async function banner(text, color, ms = 900, size = 56) {
    const t = goldTxt(text, size, color ? { fill: color } : {}); t.anchor.set(0.5); t.position.set(W / 2, Y0 + (ROWS * CH) / 2); t.scale.set(0.3); t.alpha = 0;
    fxLayer.addChild(t);
    await tween(t, { alpha: 1 }, 120); await tween(t.scale, { x: 1, y: 1 }, 260, ease.back);
    await wait(ms); await tween(t, { alpha: 0 }, 200); fxLayer.removeChild(t); t.destroy();
  }
  function persistentBanner(text, y, color) { const t = goldTxt(text, 30, color ? { fill: color } : {}); t.anchor.set(0.5); t.position.set(W / 2, y); fxLayer.addChild(t); return t; }

  function cellsOf(res, pred) { const out = []; for (let r = 0; r < R; r++) for (let y = 0; y < ROWS; y++) if (pred(res.symGrid[r][y], r, y)) out.push(reels[r].cells[y]); return out; }
  function dimAll(a) { reels.forEach((rl) => rl.cells.forEach((c) => (c.alpha = a))); }
  let pulseFns = [];
  function pulse(cells) { const t0 = performance.now(); const fn = () => { const s = 1 + 0.08 * Math.sin((performance.now() - t0) / 120); cells.forEach((c) => c.scale.set(s)); }; app.ticker.add(fn); pulseFns.push([fn, cells]); }
  function stopPulse() { pulseFns.forEach(([fn, cells]) => { app.ticker.remove(fn); cells.forEach((c) => c.scale.set(1)); }); pulseFns = []; }

  async function countUp(target, ms) {
    const o = { v: 0 }; const fn = () => { winT.text = credits(Math.round(o.v)); }; app.ticker.add(fn);
    await tween(o, { v: target }, ms, ease.out); app.ticker.remove(fn); winT.text = credits(target);
  }

  // ═════════ FG 場景 ═════════
  const GROUP_COLOR = { '超強': 0xff3b3b, '強': 0xff8c1a, '中': 0x3d8bff, '弱': 0x8a8a8a };
  // ═════════ coin-lock Bonus 場景（金幣鎖格 → 相鄰成組 → 翻值連讀）═════════
  async function playCoinLock(res) {
    const fg = res.fg, B = C.bonus[fg.type], isTD = fg.type === C.unlock.bonus;
    const L = new PIXI.Container(); app.stage.addChild(L); L.alpha = 0;
    L.addChild(new PIXI.Graphics().rect(0, 0, W, H).fill({ color: 0x050a12, alpha: 0.92 }));
    await tween(L, { alpha: 1 }, 250);
    const head = goldTxt(`${fg.group} Bonus`, 42); head.anchor.set(0.5); head.position.set(W / 2, 44); L.addChild(head);
    const sub2 = txt(`${B.reels}×${B.rows} · 初始 ${B.spins} 手 · ${B.reset ? '有金幣落下 → 次數重置' : '不重置'} · 每格每手停入率 ${f(B.coin_rate / 100, 2)}%${fg.mystery ? ' · 隨機觸發' : ''}`, { fontSize: 14, fill: '#c9d6e8' });
    sub2.anchor.set(0.5); sub2.position.set(W / 2, 82); L.addChild(sub2);
    const cell = Math.min(84, Math.floor(430 / B.rows)), gw = B.reels * cell, gx = W / 2 - gw / 2 - 90, gyB = 540;
    const pos = (c, r) => ({ x: gx + c * cell + cell / 2, y: gyB - r * cell - cell / 2 });
    const gridG = new PIXI.Container(); L.addChild(gridG);
    const shade = [];
    for (let c = 0; c < B.reels; c++) for (let r = 0; r < B.rows; r++) {
      const q = pos(c, r);
      gridG.addChild(new PIXI.Graphics().roundRect(q.x - cell / 2 + 3, q.y - cell / 2 + 3, cell - 6, cell - 6, 8).fill({ color: 0x14243a }).stroke({ width: 1, color: 0x5d7ea8, alpha: 0.6 }));
    }
    for (let r = 0; r < B.rows; r++) {
      if (!isTD || r < C.unlock.base_rows) { shade.push(null); continue; }
      const q = pos(0, r), s = new PIXI.Container();
      s.addChild(new PIXI.Graphics().rect(gx, q.y - cell / 2, gw, cell).fill({ color: 0x000000, alpha: 0.62 }));
      const lt = txt(`鎖定 · 累計 ${C.unlock.thresholds[r - C.unlock.base_rows]} 顆解鎖`, { fontSize: 12, fill: '#8fa6c4' }); lt.anchor.set(0.5); lt.position.set(gx + gw / 2, q.y); s.addChild(lt);
      L.addChild(s); shade.push(s);
    }
    const coinLayer = new PIXI.Container(); L.addChild(coinLayer);
    const info = new PIXI.Container(); info.position.set(gx + gw + 40, 150); L.addChild(info);
    info.addChild(new PIXI.Graphics().roundRect(0, 0, 250, 300, 14).fill({ color: 0x000000, alpha: 0.45 }).stroke({ width: 1, color: 0x5d7ea8, alpha: 0.6 }));
    const lab1 = txt('剩餘手數', { fontSize: 14, fill: '#c9d6e8' }); lab1.position.set(16, 14); info.addChild(lab1);
    const remT = goldTxt(String(B.spins), 56); remT.position.set(16, 34); info.addChild(remT);
    const flash = txt('', { fontSize: 15, fill: '#7fe0ff', fontWeight: '700' }); flash.position.set(16, 104); info.addChild(flash);
    const coinT = txt('', { fontSize: 15, fill: '#ffe9b0', lineHeight: 22 }); coinT.position.set(16, 140); info.addChild(coinT);
    const spinT = txt('', { fontSize: 13, fill: '#8fa6c4' }); spinT.position.set(16, 262); info.addChild(spinT);
    const sprites = {};
    let shown = 0;
    for (let i = 0; i < fg.timeline.length; i++) {
      const st = fg.timeline[i];
      spinT.text = `第 ${i + 1} 手`;
      flash.text = '';
      for (const [c, r] of st.drops) {
        const q = pos(c, r), s = new PIXI.Sprite(TX.COIN || TX.coin); s.anchor.set(0.5); s.width = s.height = cell - 12; s.position.set(q.x, gyB - B.rows * cell - 30); s.alpha = 0;
        coinLayer.addChild(s); sprites[c + ',' + r] = s;
        tween(s, { alpha: 1 }, 80); await tween(s, { y: q.y }, 160, ease.back);
      }
      shown += st.drops.length;
      if (isTD) {
        for (let r = 0; r < B.rows; r++) if (shade[r] && r < st.unlocked && shade[r].alpha > 0.5) { tween(shade[r], { alpha: 0 }, 300); flash.text = `解鎖第 ${r + 1} 列！`; }
        coinT.text = `累計 ${st.coins} 顆\nJACKPOT 門檻 ${C.jackpot.threshold} 顆${st.coins >= C.jackpot.threshold ? '　達成！' : ''}\n已開 ${st.unlocked} / ${B.rows} 列`;
      } else coinT.text = `已鎖 ${shown} 顆`;
      if (st.drops.length && B.reset) flash.text = (flash.text ? flash.text + '　' : '') + `重置為 ${B.spins} 手`;
      remT.text = String(st.remain);
      await wait(st.drops.length ? 300 : 380);
    }
    // 結算
    flash.text = '結算：橫向相鄰 ≥2 顆成組';
    let total = 0;
    const sumT = goldTxt('', 28); sumT.anchor.set(0.5); sumT.position.set(W / 2, 600); L.addChild(sumT);
    const sumSub = txt('', { fontSize: 14, fill: '#c9d6e8' }); sumSub.anchor.set(0.5); sumSub.position.set(W / 2, 636); L.addChild(sumSub);
    if (!fg.groups.length) { sumT.text = '沒有相鄰成組的金幣'; await wait(900); }
    for (const g of fg.groups) {
      const a = pos(g.start, g.row), z = pos(g.start + g.len - 1, g.row);
      const box = new PIXI.Graphics().roundRect(a.x - cell / 2, a.y - cell / 2, z.x - a.x + cell, cell, 10).stroke({ width: 4, color: 0xffe08a }); coinLayer.addChild(box);
      for (let i = 0; i < g.len; i++) {
        const q = pos(g.start + i, g.row);
        if (g.kinds[i] === 'arrow') { const s = new PIXI.Sprite(TX.ARROW); s.anchor.set(0.5); s.width = s.height = cell - 14; s.position.set(q.x, q.y); coinLayer.addChild(s); }
        else { const v = goldTxt(String(g.raw[i]), Math.max(16, cell * 0.38), { fill: '#3a1a00', stroke: { color: '#fff3b0', width: 3 } }); v.anchor.set(0.5); v.position.set(q.x, q.y); coinLayer.addChild(v); }
        await wait(160);
      }
      if (g.arrowAdd) { const q = pos(g.start, g.row); const v = txt(`+${g.arrowAdd}`, { fontSize: 15, fill: '#7fe0ff', fontWeight: '900' }); v.anchor.set(0.5); v.position.set(q.x, q.y - cell / 2 - 10); coinLayer.addChild(v); }
      const n = goldTxt(`= ${credits(g.value)}`, 20); n.anchor.set(0.5, 1); n.position.set((a.x + z.x) / 2, a.y - cell / 2 - 2);
      const pill = new PIXI.Graphics().roundRect(n.x - n.width / 2 - 8, n.y - n.height - 2, n.width + 16, n.height + 4, 8).fill({ color: 0x000000, alpha: 0.7 });
      coinLayer.addChild(pill); coinLayer.addChild(n);
      total += g.value;
      sumT.text = `合計 ${credits(total)} credit　（${f(total / BET)} 倍）`;
      sumSub.text = `連讀：${g.kinds.map((k, i) => (k === 'arrow' ? '箭頭→0' : g.raw[i])).join(' · ')}${g.arrowAdd ? `，箭頭把最左位 +${g.arrowAdd}` : ''}（G-TD-5）`;
      await wait(650);
    }
    if (fg.jackpot) { await banner(`JACKPOT　+${credits(fg.jpWin)}`, '#ffd54f', 900, 60); total += fg.jpWin; sumT.text = `合計 ${credits(total)} credit　（${f(total / BET)} 倍）`; }
    if (fg.capped) { sumSub.text = `MaxWin 封頂：${credits(C.maxWin)} 倍（MG + Bonus 合計）→ Bonus 贏分 ${credits(fg.win)}`; await wait(1000); }
    sumT.text = `Bonus 贏分 ${credits(fg.win)}　（${f(fg.win / BET)} 倍）`;
    const tier = SlotCore.winType(fg.win, BET);
    if (['BIG', 'MEGA', 'SUPER', 'GOLDEN'].includes(tier)) await banner(`${tier} WIN　${f(fg.win / BET)} 倍`, null, 900);
    await wait(900);
    await tween(L, { alpha: 0 }, 300); app.stage.removeChild(L); L.destroy({ children: true });
  }

  async function playFG(res) {
    const fg = res.fg, L = new PIXI.Container(); app.stage.addChild(L);
    const dim = new PIXI.Graphics().rect(0, 0, W, H).fill({ color: 0x0a0202, alpha: 0.88 }); L.addChild(dim); L.alpha = 0;
    await tween(L, { alpha: 1 }, 250);
    const gc = GROUP_COLOR[fg.group] || 0xffffff;
    const head = goldTxt('免費遊戲', 46); head.anchor.set(0.5); head.position.set(W / 2, 54); L.addChild(head);
    const badgeG = new PIXI.Graphics().roundRect(W / 2 - 70, 88, 140, 40, 20).fill({ color: gc }).stroke({ width: 3, color: 0xffe08a }); L.addChild(badgeG);
    const bt = txt(`組別：${fg.group}`, { fontSize: 20, fontWeight: '900', fill: '#fff' }); bt.anchor.set(0.5); bt.position.set(W / 2, 108); L.addChild(bt);
    const src = txt(`表 F-1 ${cfg.fg.group_w[fg.group]}/${C.groupT.total}${fg.preview ? ' · 群預告（M-3-1）' : ''}${fg.all888 ? ' · 全放 888（M-3-2）' : ''}`, { fontSize: 13, fill: '#c9bdb0' }); src.anchor.set(0.5); src.position.set(W / 2, 144); L.addChild(src);
    // 進場分數
    const entry = new PIXI.Container(); entry.position.set(W / 2, 200); L.addChild(entry);
    const tokens = fg.entry.sc.map((v) => ['SC', { v }]).concat(fg.entry.ss.map((x) => ['SS', x]));
    const tw = Math.min(84, 1100 / Math.max(1, tokens.length));
    for (let i = 0; i < tokens.length; i++) {
      const c = makeCell(tokens[i][0], tokens[i][1]); c.scale.set(tw / 136); c.x = (i - (tokens.length - 1) / 2) * tw; c.alpha = 0; entry.addChild(c);
      await tween(c, { alpha: 1 }, 80);
    }
    const scSum = fg.entry.sc.reduce((a, b) => a + b, 0), muls = fg.entry.ss.filter((x) => x.mul).map((x) => x.mul), nums = fg.entry.ss.filter((x) => !x.mul).map((x) => x.v);
    const baseStr = `基底 = Σ SC ${credits(scSum)}${muls.length ? ' × ' + muls.join(' × ') : ''}${nums.length ? ' ＋ SS ' + nums.map(credits).join(' + ') : ''} ＝ ${credits(fg.base)}（${f(fg.base / BET)} 倍）`;
    const bs = txt(baseStr, { fontSize: 17, fill: '#ffe9b0' }); bs.anchor.set(0.5); bs.position.set(W / 2, 262); L.addChild(bs);
    await wait(700);
    // 物件序列
    const grid = new PIXI.Container(); grid.position.set(140, 300); L.addChild(grid);
    const formula = goldTxt('', 30); formula.anchor.set(0.5); formula.position.set(W / 2, 560); L.addChild(formula);
    const fsub = txt('', { fontSize: 15, fill: '#c9bdb0' }); fsub.anchor.set(0.5); fsub.position.set(W / 2, 600); L.addChild(fsub);
    const setF = (acc, mult) => { formula.text = `( ${credits(acc)} ) × ${mult} ＝ ${credits(acc * mult)}`; fsub.text = `基底 ${credits(fg.base)} ＋ 金幣 / 鯉魚加分 ${credits(acc - fg.base)}　·　乘倍 1 ＋ 金龍×1 ＋ 彩龍×2　·　${f((acc * mult) / BET)} 倍`; };
    setF(fg.base, 1);
    const per = 12, cell = 84;
    const NAMES = { coin: '金幣', carp: '鯉魚', gold: '金龍', color: '彩龍' };
    for (let i = 0; i < fg.seq.length; i++) {
      const s = fg.seq[i];
      if (fg.revive && i === fg.revive.at) {
        await banner('龍族復活！', '#ffffff', 600, 64);
        const rb = txt(`表 F-4：贏分 ≥ ${cfg.fg.revive.threshold} 倍 · 保留金龍 ${fg.revive.keepGold} · 彩龍 ${fg.revive.keepColor}`, { fontSize: 15, fill: '#ffe9b0' });
        rb.anchor.set(0.5); rb.position.set(W / 2, 520); L.addChild(rb);
      }
      const c = new PIXI.Container(); c.position.set((i % per) * cell + cell / 2, Math.floor(i / per) * (cell + 18) + cell / 2); grid.addChild(c);
      const sp = new PIXI.Sprite(TX[s.type]); sp.anchor.set(0.5); sp.width = sp.height = 66; c.addChild(sp);
      const lab = txt(s.v != null ? '+' + s.v : '×+' + C.itemMult[s.type], { fontSize: 14, fontWeight: '700', fill: s.v != null ? '#ffe08a' : '#7fe0ff' }); lab.anchor.set(0.5); lab.y = 42; c.addChild(lab);
      if (s.revived) { const g = new PIXI.Graphics().circle(0, 0, 40).stroke({ width: 3, color: 0xffffff, alpha: 0.8 }); c.addChildAt(g, 0); }
      c.scale.set(0.2); c.alpha = 0;
      await Promise.all([tween(c, { alpha: 1 }, 120), tween(c.scale, { x: 1, y: 1 }, 220, ease.back)]);
      setF(s.acc, s.mult);
      await wait(s.type === 'gold' || s.type === 'color' ? 260 : 160);
    }
    if (!fg.seq.length) setF(fg.base, 1);
    const cnt = txt(`金幣 ${fg.coins.length} · 鯉魚 ${fg.carps.length} · 金龍 ${fg.gold} · 彩龍 ${fg.color}（表 F-2；出場順序 F-3-1 為演出）`, { fontSize: 13, fill: '#c9bdb0' }); cnt.anchor.set(0.5); cnt.position.set(W / 2, 640); L.addChild(cnt);
    await wait(500);
    const x = fg.win / BET;
    if (x >= cfg.fg.big_text) {
      const t = goldTxt(`彩字　${f(x)} 倍`, 72, { fill: ['#ff5f6d', '#ffc371', '#47e891', '#4facfe'] });
      t.anchor.set(0.5); t.position.set(W / 2, 440); t.scale.set(0.2); L.addChild(t);
      await tween(t.scale, { x: 1, y: 1 }, 420, ease.back);
      const s2 = txt(`≥ 表 F-5 彩字門檻 ${cfg.fg.big_text} 倍`, { fontSize: 14, fill: '#fff' }); s2.anchor.set(0.5); s2.position.set(W / 2, 490); L.addChild(s2);
      await wait(1400);
    } else await wait(900);
    await tween(L, { alpha: 0 }, 300); app.stage.removeChild(L); L.destroy({ children: true });
  }

  // ═════════ house-collect FG 場景（框升級收集 → 結算抽草/木/磚屋）═════════
  const HOUSE_C = { 0: 0x14243a, 1: 0x3e8e41, 2: 0x8a6a3a, 3: 0xb85c3a };   // 空 / 草 / 木 / 磚
  const HOUSE_LBL = { 1: '草', 2: '木', 3: '磚' };
  async function playHouse(res) {
    const fg = res.fg;
    const L = new PIXI.Container(); app.stage.addChild(L); L.alpha = 0;
    L.addChild(new PIXI.Graphics().rect(0, 0, W, H).fill({ color: 0x0a0502, alpha: 0.9 }));
    await tween(L, { alpha: 1 }, 250);
    const head = goldTxt(fg.variant === 'Free' ? '免費遊戲（SC 觸發）' : (VLABEL[fg.variant] || fg.variant), 42); head.anchor.set(0.5); head.position.set(W / 2, 46); L.addChild(head);
    const sub2 = txt(`強度 ${fg.strength || '—'} · 初始 ${C.hSpins} 手 · 本手 SC≥3 加手不重置 · 框升級 空→草→木→磚（滿級溢出 2>1>0 轉移）`, { fontSize: 14, fill: '#e8cfa0' });
    sub2.anchor.set(0.5); sub2.position.set(W / 2, 82); L.addChild(sub2);
    // 5×3 框盤
    const cell = 92, gw = 5 * cell, gh = 3 * cell, gx = W / 2 - gw / 2 - 110, gy = 150;
    const pos = (c, r) => ({ x: gx + c * cell + cell / 2, y: gy + r * cell + cell / 2 });
    const marks = []; for (let c = 0; c < 5; c++) { marks.push([0, 0, 0]); }
    const tiles = [];
    for (let c = 0; c < 5; c++) { tiles.push([]); for (let r = 0; r < 3; r++) {
      const q = pos(c, r); const g = new PIXI.Graphics(); const t = goldTxt('', 24); t.anchor.set(0.5); t.position.set(q.x, q.y);
      L.addChild(g); L.addChild(t); tiles[c].push({ g, t }); drawTile(g, t, q, 0);
    } }
    function drawTile(g, t, q, lv) { g.clear().roundRect(q.x - cell / 2 + 4, q.y - cell / 2 + 4, cell - 8, cell - 8, 10).fill({ color: HOUSE_C[lv] }).stroke({ width: 2, color: 0xffe08a, alpha: lv ? 0.9 : 0.4 }); t.text = HOUSE_LBL[lv] || ''; }
    // 初始框（mansions/mega_hat/buzz_saw/Free）—— 以第一手前的 marks 推：用 timeline[0] 之前；簡化用 settle 回填初始
    const info = new PIXI.Container(); info.position.set(gx + gw + 36, 160); L.addChild(info);
    info.addChild(new PIXI.Graphics().roundRect(0, 0, 250, 320, 14).fill({ color: 0x000000, alpha: 0.45 }).stroke({ width: 1, color: 0xd9a23a, alpha: 0.5 }));
    const lab1 = txt('剩餘手數', { fontSize: 14, fill: '#e8cfa0' }); lab1.position.set(16, 14); info.addChild(lab1);
    const remT = goldTxt(String(C.hSpins), 52); remT.position.set(16, 34); info.addChild(remT);
    const flash = txt('', { fontSize: 15, fill: '#7fe0a0', fontWeight: '700', wordWrap: true, wordWrapWidth: 220 }); flash.position.set(16, 100); info.addChild(flash);
    const spinT = txt('', { fontSize: 13, fill: '#c9bdb0' }); spinT.position.set(16, 288); info.addChild(spinT);
    // 逐手演出
    for (let i = 0; i < fg.timeline.length; i++) {
      const st = fg.timeline[i];
      spinT.text = `第 ${i + 1} 手 · 組 [${st.combo.join(',')}]`;
      flash.text = st.scPos.length ? `落 ${st.scPos.length} 顆 SC → 框升級` : '本手無 SC';
      // 用 timeline 的 marks 快照更新整盤（含溢出轉移後結果）
      for (let c = 0; c < 5; c++) for (let r = 0; r < 3; r++) { const lv = st.marks[c][r]; if (lv !== marks[c][r]) { marks[c][r] = lv; const q = pos(c, r); drawTile(tiles[c][r].g, tiles[c][r].t, q, lv); const tl = tiles[c][r]; tl.g.scale.set(1); } }
      remT.text = String(st.remain);
      await wait(st.scPos.length ? 420 : 300);
    }
    // 結算
    flash.text = `結算：磚屋 ${fg.stoneCount} 棟${fg.stoneCount >= C.hStone15 ? `（≥15 換池「${fg.stoneName}」）` : ''}`;
    let total = 0;
    const sumT = goldTxt('', 30); sumT.anchor.set(0.5); sumT.position.set(W / 2, gy + gh + 60); L.addChild(sumT);
    const sumSub = txt(`草屋 ${fg.houses.grass} · 木屋 ${fg.houses.wood} · 磚屋 ${fg.houses.stone}${fg.extra ? ` · 全滿額外 +${credits(fg.extra)}` : ''}${fg.lineWin ? ` · 線獎 +${credits(fg.lineWin)}` : ''}`, { fontSize: 14, fill: '#e8cfa0' }); sumSub.anchor.set(0.5); sumSub.position.set(W / 2, gy + gh + 96); L.addChild(sumSub);
    for (const s of (fg.settle || [])) {
      const q = pos(s.c, s.r); const tl = tiles[s.c][s.r];
      await tween(tl.g.scale, { x: 1.14, y: 1.14 }, 90, ease.out); tween(tl.g.scale, { x: 1, y: 1 }, 160);
      if (s.win > 0) { const v = goldTxt('+' + credits(s.win), 18); v.anchor.set(0.5); v.position.set(q.x, q.y - cell / 2 - 6); L.addChild(v); }
      total += s.win; sumT.text = `合計 ${credits(total + fg.extra + fg.lineWin)}（${f((total + fg.extra + fg.lineWin) / BET)} 倍）`;
      await wait(90);
    }
    sumT.text = `FG 贏分 ${credits(fg.win)}（${f(fg.win / BET)} 倍）`;
    const tier = SlotCore.winType(fg.win, BET);
    if (['BIG', 'MEGA', 'SUPER', 'GOLDEN'].includes(tier)) await banner(`${tier} WIN　${f(fg.win / BET)} 倍`, null, 900);
    await wait(900);
    await tween(L, { alpha: 0 }, 300); app.stage.removeChild(L); L.destroy({ children: true });
  }

  // ═════════ 一局 ═════════
  let busy = false, autoLeft = 0;
  const randSeed = () => (crypto.getRandomValues(new Uint32Array(1))[0] >>> 0) || 1;
  async function play(res) {
    busy = true; spinBtn.alpha = 0.5; stopPulse(); fxLayer.removeChildren();
    session.balance -= BET; updateBar(0);
    drawLeft(res); drawRight(null);
    let pre = null;
    if (res.fg && res.fg.preview) { pre = goldTxt('群 預 告', 72, { fill: '#ff6b5b', letterSpacing: 12 }); pre.anchor.set(0.5); pre.position.set(W / 2, Y0 + (ROWS * CH) / 2); pre.alpha = 0.92; fxLayer.addChild(pre); }
    const turbo = speed < 1;
    const jobs = [];
    for (let r = 0; r < R; r++) {
      const tags = [...Array(ROWS).keys()].map((y) => (res.preGrid ? null : res.tags.find((t) => t.r === r && t.y === y)));
      const tease = r === R - 1 && res.tease;
      const n = (turbo ? 6 : 14) + r * (turbo ? 2 : 5) + (tease ? 26 : 0);
      const ms = (turbo ? 380 : 900) + r * (turbo ? 90 : 230) + (tease ? 1700 : 0);
      if (tease) {
        const glow = new PIXI.Graphics().roundRect(X0 + r * CW - 4, Y0 - 6, CW + 8, ROWS * CH + 12, 12).stroke({ width: 6, color: 0x47e891 });
        fxLayer.addChild(glow); const t0 = performance.now();
        const fn = () => { const k = (performance.now() - t0) / 300; glow.tint = [0xff5f6d, 0xffc371, 0x47e891, 0x4facfe][Math.floor(k) % 4]; }; app.ticker.add(fn);
        const lab = txt('彩色聽牌（M-4）', { fontSize: 14, fill: '#fff', fontWeight: '700' }); lab.anchor.set(0.5); lab.position.set(X0 + r * CW + CW / 2, Y0 + ROWS * CH + 22); fxLayer.addChild(lab);
        jobs.push(spinReel(r, (res.preGrid || res.symGrid)[r], tags, n, ms, true).then(() => { app.ticker.remove(fn); fxLayer.removeChild(glow); fxLayer.removeChild(lab); }));
      } else jobs.push(spinReel(r, (res.preGrid || res.symGrid)[r], tags, n, ms, false));
    }
    await Promise.all(jobs);
    if (pre) { fxLayer.removeChild(pre); }
    if (res.preGrid && res.tags.length) {         // 銅鑼 → 倍數 WILD（先變身再算分）
      const lab = persistentBanner(`銅鑼 ${res.tags.length} 顆 → 倍數 WILD（均勻 ×${C.wm.min}～×${C.wm.max}，G-TD-2）`, Y0 + ROWS * CH + 22);
      for (const tg of res.tags) {
        const R0 = reels[tg.r], old = R0.cells[tg.y], c = makeCell(WILDC, { mul: tg.mul });
        c.x = old.x; c.y = old.y; c.scale.set(0.2); R0.cont.removeChild(old); R0.cont.addChild(c); R0.cells[tg.y] = c;
        await tween(c.scale, { x: 1, y: 1 }, 260, ease.back);
      }
      await wait(350); fxLayer.removeChild(lab);
    }
    drawLeft(res, true);
    // MG 連線
    if (res.ways.length) {
      const set = new Set();
      res.ways.forEach((w) => cellsOf(res, (s, r) => r < w.len && (s === w.sym || s === WILDC)).forEach((c) => set.add(c)));
      dimAll(0.35); set.forEach((c) => (c.alpha = 1)); pulse([...set]);
      drawRight(res);
      await countUp(res.mgWin, turbo ? 200 : 600);
      if (!turbo && res.ways.length > 1) {
        for (const w of res.ways.slice().sort((a, b) => b.win - a.win).slice(0, 4)) {
          stopPulse(); dimAll(0.3);
          const cs = cellsOf(res, (s, r) => r < w.len && (s === w.sym || s === WILDC)); cs.forEach((c) => (c.alpha = 1)); pulse(cs);
          drawRight(res, w);
          const lab = persistentBanner(`${w.sym} ×${w.len}連　${w.ways} ways × ${w.odds} ＝ ${credits(w.win)}`, Y0 + ROWS * CH + 22);
          await wait(650); fxLayer.removeChild(lab);
        }
        stopPulse(); dimAll(1);
      }
      const tier = SlotCore.winType(res.mgWin, BET);
      if (['BIG', 'MEGA', 'SUPER', 'GOLDEN'].includes(tier)) await banner(`${tier} WIN　${f(res.mgWin / BET)} 倍`, null, 900);
    } else drawRight(res);
    // FG
    if (res.fg) {
      stopPulse(); dimAll(0.3);
      const sp = cellsOf(res, (s) => SPECIAL.includes(s)); sp.forEach((c) => (c.alpha = 1)); pulse(sp);
      await banner(CL ? `虎 ${res.trig.cnt[0]} ＋ 龍 ${res.trig.cnt[1]}${res.fg.mystery ? '　隨機觸發' : ''}　→　${res.fg.group} Bonus` : HC ? (res.fg.variant === 'Free' ? `SC ${res.nSC} 顆　進入免費遊戲` : `BS ${res.nBS} 顆　大轉盤 → ${VLABEL[res.fg.variant] || res.fg.variant}`) : `SC ${res.nSC} ＋ SS ${res.nSS} ＝ ${res.nSC + res.nSS}　進入免費遊戲`, null, turbo ? 300 : 900, 34);
      stopPulse(); dimAll(1);
      await (CL ? playCoinLock(res) : HC ? playHouse(res) : playFG(res));
      winT.text = credits(res.totalWin);
    }
    session.balance += res.totalWin; session.n++; session.bet += BET; session.win += res.totalWin;
    updateBar(res.totalWin); sessionChip();
    history.push({ seed: res.seed, win: res.totalWin, fg: res.fg && res.fg.group }); if (history.length > 30) history.shift();
    renderSpinTab(res);
    spinBtn.alpha = 1; busy = false;
  }
  async function playSeed(seed) {
    if (busy) return;
    $('#seed').value = seed;
    await play(SlotCore.spin(C, seed >>> 0, { present: true }));
  }
  async function spinOnce() { if (!busy) await playSeed(randSeed()); }

  // 控制列
  $('#btnSpin').onclick = spinOnce;
  $('#btnReplay').onclick = () => { const s = +$('#seed').value; if (s > 0) playSeed(s); };
  $('#btnTurbo').onclick = (e) => { speed = speed < 1 ? 1 : 0.35; e.target.classList.toggle('on', speed < 1); };
  $('#btnAuto').onclick = async (e) => {
    if (autoLeft) { autoLeft = 0; return; }
    autoLeft = 50; e.target.classList.add('on'); e.target.textContent = '停止自動';
    while (autoLeft-- > 0) { await spinOnce(); await wait(150); }
    autoLeft = 0; e.target.classList.remove('on'); e.target.textContent = '自動 ×50';
  };
  window.addEventListener('keydown', (e) => { if (e.code === 'Space' && e.target.tagName !== 'INPUT') { e.preventDefault(); spinOnce(); } });

  // 情境：搜尋會自然產生該結果的 seed
  const SCN = HC ? [
    ['SC 觸發免費遊戲', (r) => r.fg && r.fg.variant === 'Free'],
    ['大帽子 Mega Hat', (r) => r.fg && r.fg.variant === 'mega_hat'],
    ['推土機 Buzz Saw', (r) => r.fg && r.fg.variant === 'buzz_saw'],
    ['豪宅 Mansions', (r) => r.fg && r.fg.variant === 'mansions'],
    ['FG 出現磚屋', (r) => r.fg && r.fg.houses && r.fg.houses.stone > 0],
    ['FG 滿盤 15 棟磚屋', (r) => r.fg && r.fg.stoneCount >= 15],
    ['MG 大圖騰連線 ≥10 倍', (r) => r.mgWin >= 10 * BET && !r.fg],
    ['FG BIG ≥50 倍', (r) => r.fg && r.fg.win >= 50 * BET],
  ] : CL ? [
    ...C.G.map((g, i) => [`${g} Bonus`, (r) => r.fg && r.fg.type === i && !r.fg.mystery]),
    ['隨機觸發', (r) => r.fg && r.fg.mystery],
    ['JACKPOT', (r) => r.fg && r.fg.jackpot],
    ['MaxWin 封頂', (r) => r.fg && r.fg.capped],
    ['倍數 WILD ≥3 顆', (r) => r.mult && r.mult.flat().filter((x) => x).length >= 3 && r.mgWin > 0],
    ['MG BIG ≥10 倍', (r) => r.mgWin >= 10 * BET && !r.fg],
  ] : [
    ['FG 超強', (r) => r.fg && r.fg.group === '超強'],
    ['FG 強', (r) => r.fg && r.fg.group === '強'],
    ['FG 中', (r) => r.fg && r.fg.group === '中'],
    ['FG 弱', (r) => r.fg && r.fg.group === '弱'],
    ['全放 888', (r) => r.fg && r.fg.all888],
    ['彩色聽牌', (r) => r.nSC >= 6 && r.grid[4].includes(C.SS), (p) => p.tease],
    ['復活', (r) => r.fg && r.fg.win >= cfg.fg.revive.threshold * BET && r.fg.gold + r.fg.color > 0, (p) => p.fg.revive],
    ['彩字 ≥200 倍', (r) => r.fg && r.fg.win >= cfg.fg.big_text * BET],
    ['MG BIG ≥10 倍', (r) => r.mgWin >= 10 * BET && !r.fg],
  ];
  SCN.forEach(([name, pre, post]) => {
    const b = document.createElement('button'); b.textContent = name;
    b.onclick = () => {
      if (busy) return;
      let s = randSeed();
      for (let i = 0; i < 4e6; i++, s = (s + 1) >>> 0 || 1) {
        const r = SlotCore.spin(C, s);
        if (pre(r) && (!post || post(SlotCore.spin(C, s, { present: true })))) { playSeed(s); return; }
      }
      b.textContent = name + '（未找到）';
    };
    $('#scenarios').appendChild(b);
  });
  $('#seed').value = '';
  window.__proto = { C, E, play, playSeed, SlotCore, runL2, get busy() { return busy; } };
})();
