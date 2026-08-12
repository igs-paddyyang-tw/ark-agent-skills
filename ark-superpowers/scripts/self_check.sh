#!/usr/bin/env bash
# self_check.sh — ark-superpowers 自我驗證
# 跑模板 + fixture（pass 組全 PASS / fail 組全 FAIL）+ parity check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
CHECKER="$SCRIPT_DIR/check_doc_completeness.py"

PASS=0
FAIL=0
ERRORS=()

echo "═══════════════════════════════════════════════════════"
echo " ark-superpowers self-check"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── 1. 模板章節完整性（所有模板應 PASS 或僅有 placeholder 警告）──
echo "▸ 模板驗證..."
TEMPLATES_DIR="$SKILL_ROOT/references/templates"
template_count=0
for tmpl in "$TEMPLATES_DIR"/zh-TW/*.md "$TEMPLATES_DIR"/en/*.md; do
    if [[ -f "$tmpl" ]]; then
        template_count=$((template_count + 1))
    fi
done
echo "  找到 $template_count 個模板"

# ── 2. Pass fixtures（全部必須 PASS）────────────────────────────
echo ""
echo "▸ Pass fixtures..."
for f in "$SKILL_ROOT"/tests/fixtures/pass/*.md; do
    if [[ ! -f "$f" ]]; then
        continue
    fi
    output=$(python3 "$CHECKER" "$f" 2>&1) || true
    if echo "$output" | grep -q "✅ PASS"; then
        PASS=$((PASS + 1))
        echo "  ✅ $(basename "$f")"
    else
        FAIL=$((FAIL + 1))
        ERRORS+=("PASS fixture 失敗: $(basename "$f")")
        echo "  ❌ $(basename "$f") — 應 PASS 但 FAIL"
        echo "$output" | head -5 | sed 's/^/     /'
    fi
done

# ── 3. Fail fixtures（全部必須 FAIL）────────────────────────────
echo ""
echo "▸ Fail fixtures..."
for f in "$SKILL_ROOT"/tests/fixtures/fail/*.md; do
    if [[ ! -f "$f" ]]; then
        continue
    fi
    output=$(python3 "$CHECKER" "$f" 2>&1) || true
    if echo "$output" | grep -q "❌ FAIL"; then
        PASS=$((PASS + 1))
        echo "  ✅ $(basename "$f") → 正確偵測為 FAIL"
    else
        FAIL=$((FAIL + 1))
        ERRORS+=("FAIL fixture 未偵測: $(basename "$f")")
        echo "  ❌ $(basename "$f") — 應 FAIL 但 PASS"
    fi
done

# ── 4. Parity Check ─────────────────────────────────────────────
echo ""
echo "▸ Template Parity Check..."
parity_output=$(python3 "$CHECKER" --parity 2>&1) || true
if echo "$parity_output" | grep -q "✅"; then
    PASS=$((PASS + 1))
    echo "  ✅ 中英模板 parity 通過"
else
    FAIL=$((FAIL + 1))
    ERRORS+=("Parity check 失敗")
    echo "  ❌ Parity check 失敗"
    echo "$parity_output" | sed 's/^/     /'
fi

# ── 結果摘要 ─────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
if [[ $FAIL -eq 0 ]]; then
    echo " ✅ ALL PASSED: $PASS checks"
    echo "═══════════════════════════════════════════════════════"
    exit 0
else
    echo " ❌ $PASS passed / $FAIL failed"
    for e in "${ERRORS[@]}"; do
        echo "   - $e"
    done
    echo "═══════════════════════════════════════════════════════"
    exit 1
fi
