// 玩法 Presenter 對照：依 feature.script 選 Presenter（遊戲專屬；沒對到用通用版）
//   新增專屬 Presenter：寫 presenters/<玩法>.ts（只讀 feature.script，不重算），在這裡依 script.type 對應
import type { SpinResult } from '@pgp/shared-types';
import { playGeneric, type Presenter } from './generic.js';

export function pickPresenter(_r: SpinResult): Presenter {
  return playGeneric;
}
