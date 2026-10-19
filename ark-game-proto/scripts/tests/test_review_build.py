"""review_build 拍板包（佈局契約 v3.3）：成品收集、gdd 自足化、截圖精選、REVIEW.md 人工區保留、5 MB 額度。"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE.parent / "review_build.py"
pytest.importorskip("PIL")


def _png(p: pathlib.Path, color, size=(900, 600)) -> None:
    from PIL import Image
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(p)


def _repo(tmp: pathlib.Path) -> pathlib.Path:
    d, o = tmp / "data" / "slot" / "x", tmp / "output" / "slot" / "x"
    (d / "proto").mkdir(parents=True)
    (d / "proto" / "game-config.json").write_text(json.dumps({"game": "測試機"}), encoding="utf-8")
    (d / "proto" / "index.html").write_text("<html></html>", encoding="utf-8")
    (d / "prob").mkdir()
    (d / "prob" / "prob-spec.html").write_text("<html></html>", encoding="utf-8")
    s = o / "game" / "pixi-client" / "single"
    s.mkdir(parents=True)
    (s / "index.html").write_text("<html>play</html>", encoding="utf-8")
    (s / "stage-build.json").write_text(json.dumps({"feature": "鎖格重轉"}), encoding="utf-8")
    _png(o / "gdd" / "assets" / "a.png", (200, 40, 40))
    (o / "gdd" / "素材總覽.html").write_text('<html><img src="assets/a.png"></html>', encoding="utf-8")
    bc = o / "proto" / "browser-check"
    for n, c in (("00-load", (1, 2, 3)), ("01-l1", (1, 2, 3)), ("play-ST-01", (9, 9, 9)), ("play-ST-02", (8, 8, 8)), ("91-l2", (7, 7, 7))):
        _png(bc / f"{n}.png", c)
    (bc / "browser-check.json").write_text(json.dumps({"pass": True, "url": "C:/secret/path/index.html", "results": [{"name": "a", "ok": True}]}), encoding="utf-8")
    sm = o / "game" / "pixi-client" / "smoke-shots"
    for i, n in enumerate(("00-base", "01-mid", "01-end")):
        _png(sm / f"{n}.png", (5, 5, 5 + 40 * i), (720, 1100))
    (sm / "smoke.json").write_text(json.dumps({"pass": True, "html": "D:/x/index.html", "checks": [{"name": "b", "ok": True}]}), encoding="utf-8")
    return tmp


def _run(repo: pathlib.Path):
    r = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--slug", "x", "--repo", str(repo)], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])


def test_review_pack(tmp_path):
    repo = _repo(tmp_path)
    rc, env = _run(repo)
    assert rc == 0 and env["success"], env
    rv = repo / "data" / "slot" / "x" / "review"
    for f in ("index.html", "play.html", "gdd-overview.html", "REVIEW.md", "review-manifest.json", "checks/proto-browser-check.json", "checks/stage-smoke.json"):
        assert (rv / f).is_file(), f
    assert 'src="assets/' not in (rv / "gdd-overview.html").read_text(encoding="utf-8"), "gdd 仍外連圖"
    shots = sorted(p.name for p in (rv / "checks").glob("*.webp"))
    assert shots == ["proto-00-load.webp", "proto-91-l2.webp", "proto-play-ST-02.webp", "stage-00-base.webp", "stage-01-end.webp"], shots   # 重複畫面去重、每場取最後、⑦ 取 end
    bc = json.loads((rv / "checks" / "proto-browser-check.json").read_text(encoding="utf-8"))
    assert bc["url"] == "index.html", "本機絕對路徑未去除"
    idx = (rv / "index.html").read_text(encoding="utf-8")
    assert 'href="prob-spec.html"' in idx and 'href="proto.html"' in idx and "play.html" in idx and 'href="../' not in idx   # 外部成品已複製進 review/
    man = json.loads((rv / "review-manifest.json").read_text(encoding="utf-8"))
    assert man["contract"] == "3.3" and {f["path"] for f in man["files"]} >= {"play.html", "gdd-overview.html", "index.html"}


def test_review_md_human_area_kept(tmp_path):
    repo = _repo(tmp_path)
    assert _run(repo)[0] == 0
    md = repo / "data" / "slot" / "x" / "review" / "REVIEW.md"
    md.write_text(md.read_text(encoding="utf-8").replace("（人工填寫）", "人工決議：保留", 1), encoding="utf-8")
    assert _run(repo)[0] == 0
    t = md.read_text(encoding="utf-8")
    assert "人工決議：保留" in t and t.count("<!-- auto -->") == 1


def test_bad_slug(tmp_path):
    rc, env = _run(tmp_path)
    assert rc == 2 and not env["success"]


@pytest.mark.skipif(not (HERE.parents[2] / "ark-book" / "scripts" / "book_build.py").is_file(), reason="需要 ark-book skill")
def test_review_decision_book(tmp_path):
    """拍板書：review/<book>/ 存在 → 附錄重產、人工章節不動、index.html = ark-book book_build 產物、舊 REVIEW.md 移除。"""
    import hashlib
    import shutil
    repo = _repo(tmp_path)
    rv = repo / "data" / "slot" / "x" / "review"
    book = rv / "huffnpuff-open-house-decision"
    shutil.copytree(HERE.parents[1] / "golden" / "review-book", book)
    (rv / "REVIEW.md").parent.mkdir(parents=True, exist_ok=True)
    (rv / "REVIEW.md").write_text("舊版", encoding="utf-8")
    human = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in book.glob("0*.md") if p.name != "01-status.md"}  # noqa: E731
    before = human()
    rc, env = _run(repo)
    assert rc == 0 and env["data"]["book"]["lint_exit"] == 0, env
    assert human() == before, "人工章節被改動"
    appx = (book / "99-appendix-artifacts.md").read_text(encoding="utf-8")
    assert "play.html" in appx and "PASS" in appx
    idx = (rv / "index.html").read_text(encoding="utf-8")
    assert "book-src" in idx and 'src="checks/' in idx and 'href="../' not in idx, "連結必須都在 review/ 內"
    assert not (rv / "REVIEW.md").exists()
    st = (book / "01-status.md").read_text(encoding="utf-8")
    assert "⏳ 待拍板" in st and "R-1" in st, "現況章要列出各章拍板欄狀態"
    import re
    ext = [m for m in re.findall(r"<a\b([^>]*)>", idx) if re.search(r'href="(?!#)', m)]
    assert ext and all('target="_blank"' in m for m in ext), "成品連結要開新分頁"
    assert (rv / "prob-spec.html").is_file() and (rv / "proto.html").is_file(), "外部成品要複製進 review/"
    assert "回拍板書" in (rv / "prob-spec.html").read_text(encoding="utf-8") and "回拍板書" not in (rv / "play.html").read_text(encoding="utf-8")
