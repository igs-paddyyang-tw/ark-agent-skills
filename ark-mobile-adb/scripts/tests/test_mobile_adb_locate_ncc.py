"""locate_template 無 opencv 退路（ncc_map）：與舊版雙迴圈 NCC 逐點等價、找得到嵌入模板、平坦區不爆分、1600x900 夠快。"""
import pathlib
import sys
import time

import pytest

np = pytest.importorskip("numpy")
Image = pytest.importorskip("PIL.Image")
SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import ark_mobile_adb as M  # noqa: E402


def naive(S, T):
    """舊版公式（全步長）：mean(((W-Wm)/(Ws+1e-6)) * (T-Tm)/(Ts+1e-6))。"""
    th, tw = T.shape
    Tn = (T - T.mean()) / (T.std() + 1e-6)
    out = np.zeros((S.shape[0] - th + 1, S.shape[1] - tw + 1))
    for y in range(out.shape[0]):
        for x in range(out.shape[1]):
            W = S[y:y + th, x:x + tw]
            out[y, x] = (((W - W.mean()) / (W.std() + 1e-6)) * Tn).mean()
    return out


def test_ncc_matches_naive_formula():
    rng = np.random.default_rng(0)
    S = rng.integers(0, 256, (60, 80)).astype(np.float64)
    T = S[20:32, 30:46].copy()
    ref, got = naive(S, T), M.ncc_map(S, T)
    assert got.shape == ref.shape
    assert np.abs(got - ref).max() < 1e-4
    assert np.unravel_index(np.argmax(got), got.shape) == (20, 30)


def test_flat_region_scores_zero_not_inf():
    S = np.full((50, 50), 128.0); S[10:20, 10:20] = np.arange(100).reshape(10, 10)
    got = M.ncc_map(S, S[10:20, 10:20].copy())
    assert np.isfinite(got).all() and got.max() <= 1.0 and got[30, 30] == 0.0


def test_template_larger_than_screen():
    assert M.ncc_map(np.zeros((10, 10)), np.ones((20, 5))).size == 0


def test_locate_template_fast_on_1600x900(tmp_path, monkeypatch):
    """反證（逾時根因）：舊版 1600x900 單次 ~33s，aiqa fake 全鏈因此跑數十分鐘。"""
    monkeypatch.setitem(sys.modules, "cv2", None)          # 強制走 numpy 退路
    rng = np.random.default_rng(1)
    S = rng.integers(0, 256, (900, 1600), dtype=np.uint8)
    Image.fromarray(S).save(tmp_path / "s.png"); Image.fromarray(S[300:340, 700:900]).save(tmp_path / "t.png")
    t0 = time.time()
    r = M.locate_template(tmp_path / "s.png", tmp_path / "t.png")
    assert time.time() - t0 < 5
    assert r["found"] and (r["x"], r["y"]) == (700, 300) and r["score"] > 0.99


def test_locate_templates_batch_equals_single(tmp_path, monkeypatch):
    """同畫面多模板（共用 NCCScreen，FFT 補零尺寸取最大模板）結果須與逐一 locate_template 相同。"""
    monkeypatch.setitem(sys.modules, "cv2", None)
    rng = np.random.default_rng(2)
    S = rng.integers(0, 256, (300, 500), dtype=np.uint8)
    Image.fromarray(S).save(tmp_path / "s.png")
    boxes = [(10, 20, 40, 120), (100, 200, 90, 60), (250, 400, 30, 30)]    # y, x, h, w（大小不同）
    tpls = []
    for i, (y, x, h, w) in enumerate(boxes):
        Image.fromarray(S[y:y + h, x:x + w]).save(tmp_path / f"t{i}.png"); tpls.append((tmp_path / f"t{i}.png", 0.9))
    batch = M.locate_templates(tmp_path / "s.png", tpls)
    single = [M.locate_template(tmp_path / "s.png", p, thr) for p, thr in tpls]
    assert batch == single
    assert [(r["y"], r["x"]) for r in batch] == [(y, x) for y, x, _, _ in boxes] and all(r["found"] for r in batch)
