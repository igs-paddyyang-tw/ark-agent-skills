// ============================================================
//  數值模擬工具：統計、分布、分批執行（不會卡住畫面）
// ============================================================
(function () {
  'use strict';
  const root = typeof window !== 'undefined' ? window : globalThis;
  const Proto = root.Proto;

  // 平均、標準差、95% 信賴區間
  class Stats {
    constructor() {
      this.n = 0;
      this.sum = 0;
      this.sumSq = 0;
      this.min = Infinity;
      this.max = -Infinity;
    }
    add(x, count = 1) {
      this.n += count;
      this.sum += x * count;
      this.sumSq += x * x * count;
      if (x < this.min) this.min = x;
      if (x > this.max) this.max = x;
    }
    mean() {
      return this.n ? this.sum / this.n : 0;
    }
    sd() {
      if (this.n < 2) return 0;
      const m = this.mean();
      return Math.sqrt(Math.max(0, this.sumSq / this.n - m * m));
    }
    // 平均值的 95% 信賴區間半寬（樣本數越多越窄）
    ci95() {
      return this.n ? (1.96 * this.sd()) / Math.sqrt(this.n) : 0;
    }
  }

  // 分組計數。bounds = [0, 1, 2, 5] → 組別：<0、0~1、1~2、2~5、≥5
  class Histogram {
    constructor(bounds, labels) {
      this.bounds = bounds;
      this.counts = new Array(bounds.length + 1).fill(0);
      this.labels = labels;
      this.total = 0;
    }
    add(x) {
      let i = 0;
      while (i < this.bounds.length && x >= this.bounds[i]) i++;
      this.counts[i]++;
      this.total++;
    }
    rows() {
      const b = this.bounds;
      return this.counts.map((c, i) => {
        const label = this.labels ? this.labels[i] : i === 0 ? `< ${b[0]}` : i === b.length ? `≥ ${b[b.length - 1]}` : `${b[i - 1]} ~ ${b[i]}`;
        return { label, count: c, ratio: this.total ? c / this.total : 0 };
      });
    }
  }

  // 分批執行 total 次，每批呼叫 step(次數)，每批之間讓畫面更新
  async function runChunked(total, chunk, step, onProgress, token) {
    let done = 0;
    while (done < total) {
      if (token && token.cancelled) break;
      const n = Math.min(chunk, total - done);
      step(n);
      done += n;
      if (onProgress) onProgress(done, total);
      if (typeof window !== 'undefined') await new Promise((r) => setTimeout(r, 0));
    }
    return done;
  }

  Proto.sim = { Stats, Histogram, runChunked };
})();
