"""review_build 拍板包（佈局契約 v3.5）：成品走相對連結不複製、文件 html 回寫定版家、清舊檔、--export、gdd 自足化、截圖精選、REVIEW.md 人工區保留。"""
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
    assert 'href="../prob/prob-spec.html"' in idx and 'href="../proto/index.html"' in idx and "play.html" in idx   # v3.5：相對連結指向定版家
    assert not (rv / "prob-spec.html").exists() and not (rv / "proto.html").exists() and not (rv / "docs").exists(), "定版家成品不可複製進 review/"
    man = json.loads((rv / "review-manifest.json").read_text(encoding="utf-8"))
    assert man["contract"] == "3.5" and {f["path"] for f in man["files"]} >= {"play.html", "gdd-overview.html", "index.html"}
    assert {lk["path"] for lk in man["links"]} >= {"../prob/prob-spec.html", "../proto/index.html"}
    assert all(not pathlib.Path(f["source"]).is_absolute() for f in man["files"] if f["source"] != "review_build"), "清冊來源要相對 repo"


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
    assert "book-src" in idx and 'src="checks/' in idx
    import re as _re
    for h in _re.findall(r'href="(\.\./[^"#]+)"', idx):
        assert (rv / h).resolve().is_file(), f"拍板書連到不存在的定版家檔：{h}"
    assert not (rv / "REVIEW.md").exists()
    st = (book / "01-status.md").read_text(encoding="utf-8")
    assert "⏳ 待拍板" in st and "R-1" in st, "現況章要列出各章拍板欄狀態"
    import re
    ext = [m for m in re.findall(r"<a\b([^>]*)>", idx) if re.search(r'href="(?!#)', m)]
    assert ext and all('target="_blank"' in m for m in ext), "成品連結要開新分頁"
    assert not (rv / "prob-spec.html").exists() and not (rv / "proto.html").exists(), "定版家成品不可複製進 review/"
    assert "回拍板書" not in (repo / "data" / "slot" / "x" / "prob" / "prob-spec.html").read_text(encoding="utf-8"), "定版家檔不可被注入拍板書按鈕"


def test_publish_docs_and_clean(tmp_path):
    """AC-101／AC-102：md 旁產 html（戳記、冪等）、他工具成對 html 不覆寫、白名單外舊檔清掉、closeout 不進送審包。"""
    repo = _repo(tmp_path)
    d = repo / "data" / "slot" / "x"
    (d / "quicktest" / "qt-report").mkdir(parents=True)
    (d / "quicktest" / "qt-report" / "r.md").write_text("---\ntitle: 快測\n---\n# 快測\n\n| a | b |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
    (d / "docs" / "reports").mkdir(parents=True)
    (d / "docs" / "reports" / "s.md").write_text("---\ntitle: 盤點\n---\n# 盤點\n", encoding="utf-8")
    (d / "docs" / "reports" / "s.html").write_text("<html>人工版<!-- content-src: s.md sha256:0000000000000000 --></html>", encoding="utf-8")
    (d / "docs" / "reports" / "z-closeout.md").write_text("---\ntitle: 結案\n---\n# 結案\n", encoding="utf-8")
    rv = d / "review"
    (rv / "docs").mkdir(parents=True)
    (rv / "docs" / "old.html").write_text("orphan", encoding="utf-8")
    (rv / "prob-spec.html").write_text("copy", encoding="utf-8")
    rc, env = _run(repo)
    assert rc == 0, env
    h = (d / "quicktest" / "qt-report" / "r.html").read_text(encoding="utf-8")
    assert "content-src: r.md sha256:" in h and "<table>" in h
    assert (d / "docs" / "reports" / "s.html").read_text(encoding="utf-8").startswith("<html>人工版"), "他工具產的 html 不可覆寫"
    assert not (rv / "docs").exists() and not (rv / "prob-spec.html").exists()
    assert set(env["data"]["removed"]) >= {"docs/", "prob-spec.html"}
    assert "z-closeout" not in (rv / "index.html").read_text(encoding="utf-8"), "結案報告不屬於送審包"
    rc2, env2 = _run(repo)
    assert rc2 == 0 and env2["data"]["docs_published"] == [], "重跑應冪等"


def test_export(tmp_path):
    """AC-103：--export 產可帶走的完整包，相對連結目標都在；寫進 data/ 要拒絕。"""
    import re
    repo = _repo(tmp_path)
    dest = tmp_path / "out-pack"
    r = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--slug", "x", "--repo", str(repo), "--export", str(dest)],
                       capture_output=True, text=True, encoding="utf-8")
    env = json.loads(r.stdout.strip().splitlines()[-1])
    assert r.returncode == 0 and env["data"]["export"]["linked_files"] >= 2, env
    idx = (dest / "review" / "index.html").read_text(encoding="utf-8")
    for h in re.findall(r'href="(\.\./[^"#]+)"', idx):
        assert (dest / "review" / h).resolve().is_file(), h
    bad = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--slug", "x", "--repo", str(repo), "--export", str(repo / "data" / "pack")],
                         capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 2


def test_ref_never_in_review(tmp_path):
    """契約 v3.6：ref/ 參考資源層（含 🔒 live）不進拍板包，也不隨 --export 帶走。"""
    repo = _repo(tmp_path)
    d = repo / "data" / "slot" / "x"
    (d / "ref" / "live").mkdir(parents=True)
    (d / "ref" / "live" / "server-prob.json").write_text("{}", encoding="utf-8")
    (d / "ref" / "docs").mkdir()
    (d / "ref" / "docs" / "spec-docx.md").write_text("# 文字規格\n", encoding="utf-8")
    dest = tmp_path / "pack"
    r = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--slug", "x", "--repo", str(repo), "--export", str(dest)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout
    man = json.loads((d / "review" / "review-manifest.json").read_text(encoding="utf-8"))
    assert not any("ref/" in lk["path"] for lk in man["links"])
    assert "ref/" not in (d / "review" / "index.html").read_text(encoding="utf-8")
    assert not (dest / "ref").exists()
    assert not (d / "ref" / "docs" / "spec-docx.html").exists(), "publish_docs 不可在 ref/ 產 html"
