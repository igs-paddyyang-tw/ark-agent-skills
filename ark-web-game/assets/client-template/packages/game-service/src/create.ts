// 依設定建 Service：網址參數 ?service=ws&url=…／?service=http&base=…／?service=replay（trace 另給）
import type { Trace } from '@pgp/shared-types';
import { HttpService } from './http.js';
import { ReplayService } from './replay.js';
import type { GameService } from './types.js';
import { WsService } from './ws.js';

export type ServiceConfig =
  | { kind: 'ws'; url: string; arkId?: string; token?: string; dev?: boolean }
  | { kind: 'http'; base: string; gameId: string; token?: string; dev?: boolean }
  | { kind: 'replay'; trace: Trace };

export function createService(c: ServiceConfig): GameService {
  if (c.kind === 'ws') return new WsService(c);
  if (c.kind === 'http') return new HttpService(c);
  return new ReplayService(c.trace);
}

/** 從網址參數讀 Service 設定（相對 ws 路徑以頁面位址補齊） */
export function serviceFromQuery(q: URLSearchParams, loc: { protocol: string; host: string }, defaults: Partial<{ gameId: string }> = {}): ServiceConfig | null {
  const kind = q.get('service');
  if (kind === 'ws') {
    let url = q.get('url') ?? '/ws';
    if (url.startsWith('/')) url = `${loc.protocol === 'https:' ? 'wss' : 'ws'}://${loc.host}${url}`;
    return { kind, url, arkId: q.get('arkId') ?? undefined, token: q.get('token') ?? undefined, dev: q.has('dev') };
  }
  if (kind === 'http') return { kind, base: q.get('base') ?? '', gameId: q.get('gameId') ?? defaults.gameId ?? 'huff', token: q.get('token') ?? undefined, dev: q.has('dev') };
  return null;
}
