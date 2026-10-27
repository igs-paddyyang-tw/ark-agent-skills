/* 由 schemas/release-manifest.schema.json 產生（pnpm gen:types），勿手改 */

/**
 * 雜湊一律對實際下載的位元組計算；bundle hash = 依路徑排序的「path\tsha256」行再取 sha256。同一檔案不得屬於兩個 bundle。只有 Release Pointer 可變，本檔發布後不可改。規則見 ark-web-game references/delivery.md。
 */
export interface ReleaseManifestArkWebGameWgRelease {
  schema: 'web-game-release/1';
  releaseId: string;
  gameId: string;
  gameVersion: string;
  runtimeApi: string;
  protocol: {
    result: string;
    info: string;
    wire: string;
    [k: string]: unknown;
  };
  manifestHash?: string | null;
  bundles: {
    name: string;
    requiredForPlayable: boolean;
    hash: string;
    bytes: number;
    files: {
      path: string;
      sha256: string;
      bytes: number;
      [k: string]: unknown;
    }[];
    [k: string]: unknown;
  }[];
  unassigned?: string[];
  status: 'candidate' | 'stable' | 'retired';
  [k: string]: unknown;
}
