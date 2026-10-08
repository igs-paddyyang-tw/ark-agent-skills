"""html_images 守門：縮圖尺寸、uri / map 模式、去重、JSON src、放圖輔助、預算、缺檔、外部連結、deterministic。"""
from __future__ import annotations
import base64, io, json, pathlib, re, subprocess, sys
import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import html_images as H  # noqa: E402


def png(path: pathlib.Path, w: int, h: int, alpha=False, noise=True):
    im = Image.new("RGBA" if alpha else "RGB", (w, h), (30, 60, 90, 128) if alpha else (30, 60, 90))
    if noise:
        px = im.load()
        for x in range(0, w, 7):
            for y in range(0, h, 5):
                px[x, y] = ((x * 13) % 255, (y * 7) % 255, (x * y) % 255) + ((200,) if alpha else ())
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return path


def dims(uri: str):
    b = base64.b64decode(uri.split(",", 1)[1])
    return Image.open(io.BytesIO(b)).size


@pytest.fixture
def site(tmp_path):
    png(tmp_path / "img" / "shot.png", 1080, 1920)          # portrait
    png(tmp_path / "img" / "wide.png", 1600, 900)           # landscape
    png(tmp_path / "img" / "icon.png", 300, 300, alpha=True)
    return tmp_path


def test_uri_mode_single_use_no_js_and_resizes(site):
    html = '<html><head></head><body><p><img src="img/shot.png" alt="待機"></p><img src="img/wide.png"><img src="img/icon.png"></body></html>'
    out, rep = H.embed(html, site)
    assert rep["mode"] == "uri" and "<script" not in out and "img/" not in out
    uris = re.findall(r'src="(data:[^"]+)"', out)
    assert [dims(u) for u in uris] == [(560, 996), (800, 450), (240, 240)]
    assert all(u.startswith("data:image/webp") for u in uris)
    assert rep["embedded_mb"] < rep["src_mb"]


def test_map_mode_dedupes_and_resolves_json(site):
    html = ('<html><body><img src="img/icon.png"><img src="img/icon.png"><img src="img/icon.png">'
            '<script>const G=[{"src":"img/shot.png"}];</script></body></html>')
    out, rep = H.embed(html, site)
    assert rep["mode"] == "map" and rep["images"] == 2 and rep["references"] == 4 and rep["duplicates_saved"] == 2
    assert out.count("data:image/webp") == 2                                  # 每張圖只存一份
    assert out.count('data-img="') == 3 and '"src":"__img:' in out
    assert out.index("ar-img-map") < out.index("const G=")                    # map 先於頁面 script 定義
    assert "window.__imgsrc" in out and "ar-img-hydrate" in out


def test_roles_override_and_quality_tiers(site):
    html = '<body><img data-role="icon" src="img/wide.png"><img data-role="full" src="img/shot.png"></body>'
    out, _ = H.embed(html, site, mode="uri", budget_mb=None)
    a, b = re.findall(r'src="(data:[^"]+)"', out)
    assert dims(a) == (240, 135) and dims(b) == (1080, 1920)
    lite, _ = H.embed('<body><img src="img/wide.png"></body>', site, quality="lite")
    assert dims(re.search(r'src="(data:[^"]+)"', lite).group(1))[0] == 520


def test_alpha_kept_and_jpeg_format(site):
    out, _ = H.embed('<body><img src="img/icon.png"><img src="img/wide.png"></body>', site, fmt="jpeg")
    a, b = re.findall(r'src="(data:[^;]+);', out)
    assert a == "data:image/png" and b == "data:image/jpeg"


def test_layout_figures_and_gallery(site):
    html = '<html><head></head><body><p><img src="img/shot.png" alt="待機畫面"></p>\n<p><img src="img/wide.png" alt="大廳"></p>\n<p>文字</p><p><img src="img/icon.png"></p></body></html>'
    out, rep = H.embed(html, site, do_layout=True, lightbox=True)
    assert rep["figures"] == 3 and 'class="ar-gallery"' in out and "<figcaption>待機畫面</figcaption>" in out
    assert 'class="ar-fig ar-portrait"' in out and 'class="ar-fig ar-icon"' in out and "ar-fig-css" in out and 'id="ar-lb"' in out


def test_budget_missing_external(site):
    with pytest.raises(H.EmbedError) as e:
        H.embed('<body><img data-role="full" src="img/shot.png"></body>', site, budget_mb=0.01)
    assert e.value.code == "GATE_BLOCKED" and e.value.data["top"][0]["role"] == "full"
    with pytest.raises(H.EmbedError) as e:
        H.embed('<body><img src="img/nope.png"></body>', site)
    assert e.value.code == "BAD_INPUT" and e.value.data["missing"] == ["img/nope.png"]
    out, rep = H.embed('<body><img src="https://x.com/a.png"><a href="doc.html">d</a></body>', site)
    assert rep["external_images"] == ["https://x.com/a.png"] and 'href="doc.html"' in out


def test_deterministic_and_cli(site):
    (site / "r.html").write_text('<html><body><img src="img/shot.png"><img src="img/shot.png"></body></html>', encoding="utf-8")
    outs = []
    for i in range(2):
        r = subprocess.run([sys.executable, str(SCRIPTS / "html_images.py"), "embed", str(site / "r.html"), "--out", str(site / f"o{i}.html")],
                           capture_output=True, text=True, encoding="utf-8")
        j = json.loads(r.stdout.strip().splitlines()[-1]); assert j["success"], j
        outs.append((site / f"o{i}.html").read_bytes())
    assert outs[0] == outs[1]
    r = subprocess.run([sys.executable, str(SCRIPTS / "html_images.py"), "embed", str(site / "r.html"), "--budget-mb", "0.001"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 3


def test_role_rules_unify_attr_and_json(site):
    """同一張圖在 <img> 與 JSON src 都被引用：role_rules 讓兩邊用同一用途 → 只編一份。"""
    html = ('<html><head></head><body><img src="img/wide.png"><script>var G=[{"src":"img/wide.png"}];</script></body></html>')
    out, rep = H.embed(html, site, role_rules={"img/wide*": "icon"})
    assert rep["images"] == 1 and rep["mode"] == "map"
    k = re.search(r'data-img="(\w+)"', out).group(1)
    assert f'"src":"__img:{k}"' in out
    uri = re.search(r'"%s":"(data:[^"]+)"' % k, out).group(1)
    assert dims(uri)[0] == 240
    with pytest.raises(H.EmbedError):
        H.parse_roles(["bad"])
    assert H.parse_roles(["symbols/*=icon"]) == {"symbols/*": "icon"}
