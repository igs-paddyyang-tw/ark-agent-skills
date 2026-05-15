---
author: paddyyang
name: ark-test-runner
description: |
  產出 test_runner.py 自動化測試執行 Skill，執行 pytest 測試並產生覆蓋率報告。
  支援指定測試目錄、框架選擇、覆蓋率報告產生，
  可串接 chart-generator 產生覆蓋率圖表。
  使用此 Skill 當使用者提及測試執行、test runner、跑測試、
  覆蓋率、coverage、pytest、自動化測試、
  或任何需要執行測試並產生報告的場景。
---

# ark-test-runner

產出 `src/skills/python_skills/test_runner.py`，自動化執行測試並產生報告，可獨立運作。

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「測試執行」、「test runner」、「跑測試」
- 「覆蓋率」、「coverage」、「pytest」
- 「自動化測試」、「測試報告」
- 「run tests」、「test report」

## 核心概念

```
測試目錄 → test_runner（pytest）→ 測試結果 + 覆蓋率報告
                                       ↓
                              chart_generator → 覆蓋率圖表
```

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `test_dir` | `str` | ❌ | `"tests/"` | 測試目錄路徑 |
| `framework` | `str` | ❌ | `"pytest"` | 測試框架（目前僅支援 pytest） |
| `coverage` | `bool` | ❌ | `True` | 是否產生覆蓋率報告 |
| `report_format` | `str` | ❌ | `"json"` | 報告格式：`json` / `html` / `xml` |

## 產出檔案

- `src/skills/python_skills/test_runner.py`

---

## 產出指引

### 步驟 1：建立參數模型

```python
from src.skills.base import SkillParam

class TestRunnerParams(SkillParam):
    """test_runner 輸入參數。"""
    test_dir: str = "tests/"
    framework: str = "pytest"       # 目前僅支援 pytest
    coverage: bool = True
    report_format: str = "json"     # json / html / xml
```

### 步驟 2：實作 Skill 類別

```python
class TestRunnerSkill(BaseSkill):
    skill_id = "test_runner"
    skill_type = SkillType.PYTHON
    description = "自動化測試執行 + 覆蓋率報告產生，可串接 chart-generator"
    version = "1.0.0"
    input_schema = TestRunnerParams
```

### 步驟 3：實作 execute 方法

```python
async def execute(self, params: dict) -> SkillResult:
    try:
        p = TestRunnerParams(**params)
        test_path = Path(p.test_dir)

        if not test_path.exists():
            return SkillResult(success=False, error=f"測試目錄不存在: {p.test_dir}")

        # 組裝 pytest 指令
        cmd = self._build_command(p)

        # 執行測試
        result = await self._run_pytest(cmd)

        # 解析結果
        test_result = self._parse_result(result)

        # 解析覆蓋率
        coverage_data = {}
        if p.coverage:
            coverage_data = self._parse_coverage(p.report_format)

        return SkillResult(success=True, data={
            "test_result": test_result,
            "coverage": coverage_data,
            "report_format": p.report_format,
            "command": cmd,
        })
    except Exception as e:
        return SkillResult(success=False, error=f"測試執行失敗: {e}")
```

### 步驟 4：實作輔助方法

#### _build_command — 組裝 pytest 指令

```python
def _build_command(self, p: TestRunnerParams) -> str:
    """組裝 pytest 執行指令。"""
    parts = ["python", "-m", "pytest", p.test_dir, "-v"]

    if p.coverage:
        parts.extend(["--cov=src", f"--cov-report={p.report_format}"])
        if p.report_format == "json":
            parts.append("--cov-report=json:coverage.json")
        elif p.report_format == "html":
            parts.append("--cov-report=html:htmlcov")
        elif p.report_format == "xml":
            parts.append("--cov-report=xml:coverage.xml")

    # JSON 測試結果輸出
    parts.append("--tb=short")

    return " ".join(parts)
```

#### _run_pytest — 執行 pytest

```python
async def _run_pytest(self, cmd: str) -> dict:
    """以 subprocess 執行 pytest 並回傳結果。"""
    import asyncio
    import json

    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    return {
        "returncode": proc.returncode,
        "stdout": stdout.decode("utf-8", errors="ignore"),
        "stderr": stderr.decode("utf-8", errors="ignore"),
    }
```

#### _parse_result — 解析測試結果

```python
def _parse_result(self, result: dict) -> dict:
    """解析 pytest 輸出，提取測試統計。"""
    import re
    stdout = result["stdout"]

    # 解析摘要行：如 "5 passed, 2 failed, 1 error in 3.21s"
    summary_pattern = r"(\d+) passed|(\d+) failed|(\d+) error|(\d+) skipped"
    matches = re.findall(summary_pattern, stdout)

    passed = failed = errors = skipped = 0
    for m in matches:
        if m[0]: passed = int(m[0])
        if m[1]: failed = int(m[1])
        if m[2]: errors = int(m[2])
        if m[3]: skipped = int(m[3])

    total = passed + failed + errors + skipped

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "success_rate": round(passed / total * 100, 1) if total > 0 else 0.0,
        "returncode": result["returncode"],
        "output": stdout[-2000:] if len(stdout) > 2000 else stdout,
    }
```

#### _parse_coverage — 解析覆蓋率

```python
def _parse_coverage(self, report_format: str) -> dict:
    """解析覆蓋率報告。"""
    import json

    if report_format == "json":
        cov_file = Path("coverage.json")
        if not cov_file.exists():
            return {"error": "coverage.json 不存在"}

        data = json.loads(cov_file.read_text(encoding="utf-8"))
        totals = data.get("totals", {})

        # 提取各模組覆蓋率（供 chart_generator 使用）
        modules: list[dict] = []
        for file_path, file_data in data.get("files", {}).items():
            modules.append({
                "module": file_path,
                "coverage": file_data.get("summary", {}).get("percent_covered", 0),
            })

        # 依覆蓋率排序
        modules.sort(key=lambda m: m["coverage"])

        return {
            "total_coverage": totals.get("percent_covered", 0),
            "total_statements": totals.get("num_statements", 0),
            "covered_statements": totals.get("covered_lines", 0),
            "missing_statements": totals.get("missing_lines", 0),
            "modules": modules,
        }

    return {"report_format": report_format, "note": "詳細報告已產生至對應目錄"}
```

---

## 輸出格式

```json
{
  "success": true,
  "data": {
    "test_result": {
      "total": 42,
      "passed": 40,
      "failed": 1,
      "errors": 0,
      "skipped": 1,
      "success_rate": 95.2,
      "returncode": 1,
      "output": "..."
    },
    "coverage": {
      "total_coverage": 87.5,
      "total_statements": 320,
      "covered_statements": 280,
      "missing_statements": 40,
      "modules": [
        {"module": "src/skills/base.py", "coverage": 95.0},
        {"module": "src/server/main.py", "coverage": 72.3}
      ]
    },
    "report_format": "json",
    "command": "python -m pytest tests/ -v --cov=src --cov-report=json:coverage.json --tb=short"
  }
}
```

Workflow YAML 串接範例（搭配 chart-generator 產生覆蓋率圖表）：

```yaml
- id: run_tests
  type: skill
  skill: test_runner
  params:
    test_dir: "tests/"
    coverage: true
    report_format: "json"
  output: test_data

- id: transform_coverage
  type: skill
  skill: etl_pipeline
  params:
    source: "{{ outputs.test_data.coverage.modules }}"
    x_field: "module"
    y_field: "coverage"
    sort_by: "coverage"
    sort_desc: false
    chart_type: "bar"
    title: "模組覆蓋率分佈"
  output: chart_data

- id: draw_coverage
  type: skill
  skill: chart_generator
  params:
    chart_type: "{{ outputs.chart_data.chart_type }}"
    title: "{{ outputs.chart_data.title }}"
    x: "{{ outputs.chart_data.x }}"
    y: "{{ outputs.chart_data.y }}"
    labels: "{{ outputs.chart_data.labels }}"
    output_name: "coverage_report"
  output: chart
```

## 注意事項

- 測試執行使用 `asyncio.create_subprocess_shell`，需確保 pytest 已安裝於環境中
- `coverage=True` 時需要 `pytest-cov` 套件
- 覆蓋率 JSON 報告預設輸出至 `coverage.json`，HTML 輸出至 `htmlcov/`
- 長輸出會被截斷至最後 2000 字元，避免 SkillResult 過大
- 測試目錄路徑使用 `pathlib.Path`，支援相對與絕對路徑
- 可透過 Workflow 串接 `etl_pipeline` + `chart_generator` 產生覆蓋率視覺化圖表
- `framework` 參數預留擴充，目前僅支援 pytest
