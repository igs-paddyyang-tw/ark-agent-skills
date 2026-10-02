"""ga_analyze 後處理守門：deterministic，不靠提詞。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from ga_analyze import postprocess  # noqa: E402

ITEM = {"id": "S01", "name": "reel_layout", "claims": [{"key": "reel.columns", "type": "int"}, {"key": "reel.rows", "type": "int"}],
        "entity": {"type": "symbol", "fields": ["id", "type", "visual_description"]}}
EV = {"E001": {"evidence_id": "E001", "type": "visual"}, "E002": {"evidence_id": "E002", "type": "transcript"}}


def test_unknown_key_dropped_and_missing_filled():
    out, viol = postprocess(ITEM, {"claims": [{"key": "reel.made_up", "value": 1, "provenance": "OBSERVED", "evidence": ["E001"]}]}, EV)
    assert viol == 1
    assert {c["key"] for c in out["claims"]} == {"reel.columns", "reel.rows"}
    assert all(c["provenance"] == "UNKNOWN" and c["value"] is None for c in out["claims"])


def test_bad_evidence_downgrades_to_unknown():
    out, viol = postprocess(ITEM, {"claims": [{"key": "reel.columns", "value": 5, "provenance": "OBSERVED", "evidence": ["E999"]}]}, EV)
    c = next(x for x in out["claims"] if x["key"] == "reel.columns")
    assert c["provenance"] == "UNKNOWN" and c["value"] is None and viol >= 1


def test_transcript_only_observed_becomes_inferred():
    out, _ = postprocess(ITEM, {"claims": [{"key": "reel.rows", "value": "3", "provenance": "OBSERVED", "evidence": ["E002"], "confidence": "high"}]}, EV)
    c = next(x for x in out["claims"] if x["key"] == "reel.rows")
    assert c["provenance"] == "INFERRED" and c["value"] == 3


def test_entity_id_rules():
    out, viol = postprocess(ITEM, {"claims": [], "entities": [{"id": "Symbol A", "evidence": ["E001"]}, {"id": "symbol_a", "type": "high", "evidence": ["E001"]},
                                                              {"id": "symbol_a", "evidence": ["E001"]}]}, EV)
    assert [e["id"] for e in out["entities"]] == ["symbol_a"] and viol == 2
    assert out["entities"][0]["entity_type"] == "symbol"
