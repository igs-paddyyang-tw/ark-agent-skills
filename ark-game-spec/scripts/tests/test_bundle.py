"""gs_bundle 守門：md + gdd-pack → 單檔、零本機連結、燈箱走 __imgsrc、md 圖共用 gdd 素材、deterministic、--check STALE、注入擋下、gs_run 派發。"""
from __future__ import annotations
import json, pathlib, re, subprocess, sys
import pytest

yaml = pytest.importorskip("yaml")
pytest.importorskip("jinja2")
PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
HTML_REPORT = SCRIPTS.parent.parent / "ark-html-report" / "scripts" / "html_images.py"
pytestmark = pytest.mark.skipif(not HTML_REPORT.exists(), reason="需要同層 ark-html-report ≥ 1.2")
sys.path.insert(0, str(SCRIPTS / "tests"))
from test_gdd import make_pack  # noqa: E402


def real_png(p: pathlib.Path, w: int, h: int, c=(200, 40, 40)):
    im = Image.new("RGB", (w, h), c)
    px = im.load()
    for x in range(0, w, 9):
        for y in range(0, h, 7):
            px[x, y] = ((x * 5) % 255, (y * 3) % 255, 90)
    im.save(p)


def setup(tmp: pathlib.Path, md_extra: str = "") -> pathlib.Path:
    pack = make_pack(tmp)
    a = pack / "assets"
    for f in ("S1.png", "S2.png", "W.png"):
        real_png(a / "symbols" / f, 512, 512)
    for f in ("main_1.png", "bad.png.png", "Snipaste_1.png"):
        real_png(a / "illustrations" / f, 1080, 1920, (20, 90, 160))
    real_png(a / "spec-reference-images" / "S1_參考.png", 600, 400)
    rep = tmp / "rep"; rep.mkdir()
    real_png(rep / "chart.png", 1600, 900, (10, 150, 60))
    (rep / "a.md").write_text("---\ntitle: t\ndate: 2026-10-08\nverdict: ok\n---\n\n# 示範競品分析\n\n## 一、快照\n\n| 項目 | 內容 |\n|---|---|\n| 盤面 | 3×5 |\n\n"
                              "![走勢](chart.png)\n\n![星星圖騰](symbols/S1.png)\n\n```mermaid\nflowchart LR\n  A-->B\n```\n" + md_extra, encoding="utf-8")
    y = tmp / "bundle.yaml"
    y.write_text(yaml.safe_dump({"bundle": "1", "title": "Demo 競品分析與規格書", "out": "out/demo.html", "quality": "standard", "budget_mb": 5,
                                 "parts": [{"kind": "md", "id": "analysis", "label": "競品分析", "path": "rep/a.md"},
                                           {"kind": "gdd", "id": "spec", "label": "遊戲規格", "pack": "demo"}]}, allow_unicode=True), encoding="utf-8")
    return y


def run(*args):
    r = subprocess.run([sys.executable, str(SCRIPTS / "bundle" / "gs_bundle.py"), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout.strip().splitlines()[-1]) | {"rc": r.returncode}


def test_bundle_single_file_inline_and_parts(tmp_path):
    y = setup(tmp_path)
    r = run("--bundle", y); assert r["success"], r
    out = tmp_path / "out" / "demo.html"
    t = out.read_text(encoding="utf-8")
    assert "<title>Demo 競品分析與規格書</title>" in t
    # 沒有任何本機圖片連結；燈箱 gallery 的 src 都是 __img:
    assert not re.search(r'(?:src|href)="(?!data:|#|http)[^"]+\.(?:png|jpe?g|webp)"', t)
    assert '"src":"symbols/' not in t and '"src":"__img:' in t
    assert "(window.__imgsrc || (s => s))(d.src)" in t
    # md 段：nav 在規格之前、標題降級、front matter、mermaid 原始碼保留
    assert t.index('href="#part-analysis"') < t.index('href="#rule"')
    assert 'id="part-analysis"' in t and "<h2 class=\"bp-title\">示範競品分析</h2>" in t and "<h3>一、快照</h3>" in t
    assert "bp-meta" in t and "bp-mermaid" in t and "A--&gt;B" in t
    # md 引用 symbols/S1.png 與 gdd 圖騰共用同一份（依路徑用途 icon、內容去重）
    assert r["data"]["duplicates_saved"] > 0 and r["data"]["html_mb"] < 5
    m = json.loads((tmp_path / "out" / "demo.bundle.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in m["parts"]] == ["analysis", "spec"]


def test_bundle_deterministic_and_check_stale(tmp_path):
    y = setup(tmp_path)
    out = tmp_path / "out" / "demo.html"
    assert run("--bundle", y)["success"]; a = out.read_bytes()
    assert run("--bundle", y)["success"]; assert out.read_bytes() == a
    assert run("--bundle", y, "--check")["data"]["status"] == "OK"
    md = tmp_path / "rep" / "a.md"; md.write_text(md.read_text(encoding="utf-8") + "\n補一行\n", encoding="utf-8")
    r = run("--bundle", y, "--check"); assert r["rc"] == 3 and r["error"]["code"] == "GATE_BLOCKED"


def test_bundle_blocks_injection_missing_image_and_budget(tmp_path):
    y = setup(tmp_path, md_extra="\n<script>alert(1)</script>\n")
    r = run("--bundle", y); assert r["rc"] == 2 and "可執行" in r["error"]["message"]
    md = tmp_path / "rep" / "a.md"
    md.write_text(md.read_text(encoding="utf-8").replace("<script>alert(1)</script>", "![x](nope.png)"), encoding="utf-8")
    r = run("--bundle", y); assert r["rc"] == 2 and r["data"]["missing"] == ["nope.png"]
    md.write_text(md.read_text(encoding="utf-8").replace("![x](nope.png)", ""), encoding="utf-8")
    r = run("--bundle", y, "--budget-mb", "0.01"); assert r["rc"] == 3


def test_bundle_md_only_shell(tmp_path):
    y = setup(tmp_path)
    cfg = yaml.safe_load(y.read_text(encoding="utf-8"))
    cfg["parts"] = [cfg["parts"][0]]; cfg["parts"][0]["path"] = "rep/a.md"
    (tmp_path / "rep" / "a.md").write_text("# 只有分析\n\n![走勢](chart.png)\n", encoding="utf-8")
    y.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    r = run("--bundle", y); assert r["success"], r
    t = (tmp_path / "out" / "demo.html").read_text(encoding="utf-8")
    assert "data:image/webp;base64," in t and 'href="#part-analysis"' in t and "ar-fig" in t


def test_gs_run_dispatches_bundle(tmp_path):
    y = setup(tmp_path)
    r = subprocess.run([sys.executable, str(SCRIPTS / "gs_run.py"), "--stage", "bundle", "--bundle", str(y), "--quality", "lite"],
                       capture_output=True, text=True, encoding="utf-8")
    env = json.loads(r.stdout.strip().splitlines()[-1])
    assert env["success"] and env["data"]["quality"] == "lite"
    r = subprocess.run([sys.executable, str(SCRIPTS / "gs_run.py"), "--stage", "bundle"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2
