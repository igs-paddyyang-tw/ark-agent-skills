// ============================================================
//  介面：上方工具列、右側除錯面板、表格小工具
// ============================================================
(function () {
  'use strict';
  const Proto = window.Proto;
  const h = (...a) => Proto.h(...a);

  class UI {
    constructor(app) {
      this.app = app;
      this.tabs = [];
      this.root = h('div', { class: 'proto-app' });
      this.toolbar = h('div', { class: 'proto-toolbar' });
      this.stageWrap = h('div', { class: 'proto-stage-wrap' });
      this.debug = h('div', { class: 'proto-debug', hidden: true });
      this.tabBar = h('div', { class: 'proto-tabbar' });
      this.tabBody = h('div', { class: 'proto-tabbody' });
      this.debug.append(this.tabBar, this.tabBody);
      this.root.append(this.toolbar, h('div', { class: 'proto-main' }, this.stageWrap, this.debug));
      document.body.appendChild(this.root);
      this.buildToolbar();
      setInterval(() => this.autoRefresh(), 500);
    }

    buildToolbar() {
      const app = this.app;
      const title = h('span', { class: 'proto-title' }, app.config.name || '原型');
      this.pauseBtn = h('button', { onclick: () => this.togglePause(), title: '暫停／繼續（P）' }, '⏸ 暫停');
      const speed = h('select', { title: '倍速', onchange: (e) => { Proto.setSpeed(Number(e.target.value)); app.audio.refresh(); app.stage.refresh(); } },
        ...[0.25, 0.5, 1, 2, 4, 8, 16].map((s) => h('option', { value: s, selected: s === 1 }, `${s}x`)));
      this.skipBtn = h('button', { onclick: () => this.toggleSkip(), title: '跳過演出：等待立即結束、不播影音，用來快速測流程' }, '⏭ 跳過演出');
      this.muteBtn = h('button', { onclick: () => { app.audio.muted = !app.audio.muted; this.muteBtn.textContent = app.audio.muted ? '🔇' : '🔊'; app.audio.refresh(); } }, '🔊');
      const master0 = Math.round(((app.config.volume || {}).master ?? 1) * 100);
      const vol = h('input', { type: 'range', min: 0, max: 100, value: master0, title: '主音量', oninput: (e) => { app.audio.master = e.target.value / 100; app.audio.refresh(); } });
      const full = h('button', { onclick: () => (document.fullscreenElement ? document.exitFullscreen() : this.root.requestFullscreen()) }, '⛶');
      const dbg = h('button', { onclick: () => this.toggleDebug(), title: '除錯面板（D）' }, '🛠 除錯');
      this.toolbar.append(title, this.pauseBtn, speed, this.skipBtn, this.muteBtn, vol, h('span', { class: 'proto-spacer' }), full, dbg);
      document.addEventListener('keydown', (e) => {
        if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
        if (e.key === 'p' || e.key === 'P') this.togglePause();
        else if (e.key === 'd' || e.key === 'D') this.toggleDebug();
        else app.events.emit('key', e);
      });
    }

    // 遊戲控制列：放在工具列下方、遊戲畫面外面，不會遮住畫面
    gameBar() {
      if (!this.gameBarEl) {
        this.gameBarEl = h('div', { class: 'proto-gamebar' });
        this.toolbar.after(this.gameBarEl);
        setTimeout(() => this.app.stage.fit(), 0);
      }
      return this.gameBarEl;
    }

    // 狀態列：放在遊戲畫面外面，給總回轉、持ち玉這類「看數字」的資訊用
    statusBar() {
      if (!this.statusBarEl) {
        this.statusBarEl = h('div', { class: 'proto-statusbar' });
        (this.gameBarEl || this.toolbar).after(this.statusBarEl);
        setTimeout(() => this.app.stage.fit(), 0);
      }
      return this.statusBarEl;
    }

    togglePause() {
      Proto.setPaused(!Proto.time.paused);
      this.pauseBtn.textContent = Proto.time.paused ? '▶ 繼續' : '⏸ 暫停';
      this.pauseBtn.classList.toggle('on', Proto.time.paused);
      this.app.audio.refresh();
      this.app.stage.refresh();
    }

    toggleSkip() {
      Proto.time.skip = !Proto.time.skip;
      this.skipBtn.classList.toggle('on', Proto.time.skip);
      if (Proto.time.skip) this.app.audio.stopAll({ keepBgm: true });
    }

    toggleDebug() {
      this.debug.hidden = !this.debug.hidden;
      this.app.stage.fit();
      if (!this.debug.hidden) this.renderTab();
    }

    // 加一個除錯分頁。render(容器) 每次切到這個分頁時呼叫；live: true 會每 0.5 秒重畫
    addTab(title, render, { live = false } = {}) {
      const tab = { title, render, live, btn: null };
      tab.btn = h('button', { onclick: () => { this.current = tab; this.renderTab(); } }, title);
      this.tabBar.appendChild(tab.btn);
      this.tabs.push(tab);
      if (!this.current) this.current = tab;
    }

    renderTab() {
      if (!this.current || this.debug.hidden) return;
      for (const t of this.tabs) t.btn.classList.toggle('on', t === this.current);
      this.tabBody.innerHTML = '';
      this.current.render(this.tabBody);
    }

    autoRefresh() {
      if (this.current && this.current.live && !this.debug.hidden && !this.debug.contains(document.activeElement)) this.renderTab();
    }

    // 載入中畫面
    showLoading() {
      this.loading = h('div', { class: 'proto-overlay' }, h('div', { class: 'proto-overlay-title' }, this.app.config.name || '原型'),
        h('div', { class: 'proto-progress' }, h('div')), h('div', { class: 'proto-overlay-note' }, '載入素材中…'));
      this.stageWrap.appendChild(this.loading);
    }

    progress(done, total) {
      if (!this.loading) return;
      this.loading.querySelector('.proto-progress div').style.width = total ? `${(done / total) * 100}%` : '100%';
      this.loading.querySelector('.proto-overlay-note').textContent = `載入素材中… ${done} / ${total}`;
    }

    // 點擊開始（瀏覽器規定要先點一下才能播聲音）
    waitStart(missingCount) {
      return new Promise((resolve) => {
        const note = this.loading.querySelector('.proto-overlay-note');
        note.textContent = missingCount ? `載入完成（${missingCount} 個素材缺檔，會用佔位畫面或靜音代替，詳見除錯面板「設定檢查」）` : '載入完成';
        const btn = h('button', { class: 'proto-start' }, '點擊開始');
        btn.onclick = () => {
          this.loading.remove();
          this.loading = null;
          resolve();
        };
        this.loading.appendChild(btn);
        btn.focus();
      });
    }
  }

  // 表格：headers = ['欄1', ...]；rows = [[...], ...]
  Proto.table = function (headers, rows, opts = {}) {
    return h('table', { class: `proto-table ${opts.class || ''}` },
      h('thead', {}, h('tr', {}, headers.map((x) => h('th', {}, x)))),
      h('tbody', {}, rows.map((r) => h('tr', {}, r.map((c) => (c instanceof Node ? h('td', {}, c) : h('td', {}, c === undefined || c === null ? '' : String(c))))))));
  };

  Proto.download = function (filename, text, mime = 'text/plain') {
    const blob = new Blob(['﻿' + text], { type: `${mime};charset=utf-8` });
    const a = h('a', { href: URL.createObjectURL(blob), download: filename });
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  };

  Proto.UI = UI;
})();
