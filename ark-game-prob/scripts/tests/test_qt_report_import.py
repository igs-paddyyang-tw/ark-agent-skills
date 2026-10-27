"""1.6.0：ps_extract 解析 Go 快測範本新格式「名稱 - RTP HitRate Freq …」（ark-game-quicktest 路線 A／C 報表）。"""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ps_extract as X  # noqa: E402

REPORT = """====================== 版本: live ====================== 2026-10-22 13:11:20.1523
Times:20000000 TotalWin:801594998 TotalBet:800000000
********** BASE INFO **********
                Game -        RTP   HitRate      Freq.     Multi  PlayTimes  RetriRate  MaxMulti
            MainGame -   42.9610%    23.66%          -      1.82          -          -    126.05
    SpecialGameTotal -   57.2383%    37.51%     178.88    102.39      11.19     23.75%   3528.25
------------------------------------------------------
              Strong -   20.4205%         -     679.93    138.84      11.18     23.59%   3273.60
               Total -  100.1994%                                                        3531.25
"""


def test_new_format_base_rows():
    r = X.parse_fasttest(REPORT.splitlines())
    b = r["base"]
    assert b["Main"][0] == "42.9610%" and b["Free"][1] == "178.88" and b["Strong"][3] == "138.84"
    assert b["Total"][0] == "100.1994%" and b["Total"][-1] == "3531.25"
    assert b["_order"] == ["Main", "Free", "Strong"]
    assert r["run"]["times"] == 20000000
