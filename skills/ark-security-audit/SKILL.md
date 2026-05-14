---
name: ark-security-audit
description: |
  產出 security_audit.py 安全性掃描 Skill，對專案進行程式碼安全性檢查與弱點偵測。
  檢查項目包含硬編碼密碼、SQL injection、eval 使用、依賴套件漏洞、路徑穿越等。
  輸出 issues 清單、嚴重度摘要與風險分數。
  使用此 Skill 當使用者提及安全性掃描、security audit、弱點偵測、
  vulnerability scan、程式碼安全、依賴檢查、
  或任何需要檢查專案安全性的場景。
---

# ark-security-audit

產出 `src/skills/python_skills/security_audit.py`，對專案進行安全性掃描與弱點偵測，可獨立運作。

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「安全性掃描」、「security audit」、「弱點偵測」
- 「vulnerability scan」、「程式碼安全」
- 「依賴檢查」、「密碼洩漏」
- 「安全性檢查」、「security scan」

## 核心概念

```
專案目錄 → security_audit → issues list + severity summary + risk_score
```

檢查項目：

| 類別 | 檢查內容 | 嚴重度 |
|------|----------|--------|
| 硬編碼密碼 | API key、password、secret 字串 | critical |
| SQL Injection | 字串拼接 SQL、未參數化查詢 | critical |
| eval 使用 | `eval()`、`exec()` 呼叫 | high |
| 依賴套件漏洞 | requirements.txt 已知 CVE | critical/high |
| 路徑穿越 | 未驗證的檔案路徑操作 | high |
| 不安全的 import | `pickle.loads`、`yaml.load` 無 SafeLoader | high |

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_dir` | `str` | ✅ | — | 專案根目錄路徑 |
| `scan_type` | `str` | ❌ | `"all"` | 掃描類型：`code` / `deps` / `all` |
| `severity` | `str` | ❌ | `"all"` | 篩選嚴重度：`critical` / `high` / `all` |

## 產出檔案

- `src/skills/python_skills/security_audit.py`

---

## 產出指引

### 步驟 1：建立參數模型

```python
from src.skills.base import SkillParam

class SecurityAuditParams(SkillParam):
    """security_audit 輸入參數。"""
    project_dir: str
    scan_type: str = "all"    # code / deps / all
    severity: str = "all"     # critical / high / all
```

### 步驟 2：實作 Skill 類別

```python
class SecurityAuditSkill(BaseSkill):
    skill_id = "security_audit"
    skill_type = SkillType.PYTHON
    description = "安全性掃描 + 弱點偵測，檢查硬編碼密碼、SQL injection、依賴漏洞等"
    version = "1.0.0"
    input_schema = SecurityAuditParams

    # 硬編碼密碼偵測 pattern
    SECRET_PATTERNS: list[str] = [
        r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]+['\"]",
        r"(?i)(api_key|apikey|secret_key|secret)\s*=\s*['\"][^'\"]+['\"]",
        r"(?i)(token|access_token)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
    ]

    # 危險函式
    DANGEROUS_CALLS: list[str] = [
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"\bpickle\.loads?\s*\(",
        r"\byaml\.load\s*\([^)]*(?!Loader)",
    ]

    # SQL injection pattern
    SQL_INJECTION_PATTERNS: list[str] = [
        r"f['\"].*(?:SELECT|INSERT|UPDATE|DELETE).*\{",
        r"['\"].*(?:SELECT|INSERT|UPDATE|DELETE).*['\"].*%\s*\(",
        r"\.execute\s*\(\s*f['\"]",
    ]

    # 路徑穿越 pattern
    PATH_TRAVERSAL_PATTERNS: list[str] = [
        r"open\s*\(\s*(?:request|params|user_input)",
        r"Path\s*\(\s*(?:request|params|user_input)",
        r"\.\.\/" ,
    ]
```

### 步驟 3：實作 execute 方法

```python
async def execute(self, params: dict) -> SkillResult:
    try:
        p = SecurityAuditParams(**params)
        project_path = Path(p.project_dir)

        if not project_path.exists():
            return SkillResult(success=False, error=f"目錄不存在: {p.project_dir}")

        issues: list[dict] = []

        # 程式碼掃描
        if p.scan_type in ("code", "all"):
            issues.extend(self._scan_code(project_path))

        # 依賴套件掃描
        if p.scan_type in ("deps", "all"):
            issues.extend(self._scan_dependencies(project_path))

        # 依嚴重度篩選
        if p.severity != "all":
            issues = [i for i in issues if i["severity"] == p.severity]

        # 計算風險分數
        risk_score = self._calculate_risk_score(issues)
        severity_summary = self._summarize_severity(issues)

        return SkillResult(success=True, data={
            "issues": issues,
            "total_issues": len(issues),
            "severity_summary": severity_summary,
            "risk_score": risk_score,
            "scan_type": p.scan_type,
            "project_dir": p.project_dir,
        })
    except Exception as e:
        return SkillResult(success=False, error=f"安全性掃描失敗: {e}")
```

### 步驟 4：實作掃描方法

#### _scan_code — 程式碼掃描

```python
def _scan_code(self, project_path: Path) -> list[dict]:
    """掃描 Python 原始碼中的安全性問題。"""
    import re
    issues: list[dict] = []
    py_files = list(project_path.rglob("*.py"))

    for file_path in py_files:
        # 跳過虛擬環境與測試
        rel = file_path.relative_to(project_path)
        if any(part in rel.parts for part in (".venv", "venv", "__pycache__")):
            continue

        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        for line_no, line in enumerate(lines, 1):
            # 硬編碼密碼
            for pattern in self.SECRET_PATTERNS:
                if re.search(pattern, line):
                    issues.append(self._make_issue(
                        "hardcoded_secret", "critical", str(rel), line_no, line.strip()
                    ))
            # 危險函式
            for pattern in self.DANGEROUS_CALLS:
                if re.search(pattern, line):
                    issues.append(self._make_issue(
                        "dangerous_call", "high", str(rel), line_no, line.strip()
                    ))
            # SQL injection
            for pattern in self.SQL_INJECTION_PATTERNS:
                if re.search(pattern, line):
                    issues.append(self._make_issue(
                        "sql_injection", "critical", str(rel), line_no, line.strip()
                    ))
            # 路徑穿越
            for pattern in self.PATH_TRAVERSAL_PATTERNS:
                if re.search(pattern, line):
                    issues.append(self._make_issue(
                        "path_traversal", "high", str(rel), line_no, line.strip()
                    ))
    return issues
```

#### _scan_dependencies — 依賴套件掃描

```python
def _scan_dependencies(self, project_path: Path) -> list[dict]:
    """檢查 requirements.txt 中的已知漏洞套件。"""
    issues: list[dict] = []
    req_file = project_path / "requirements.txt"

    if not req_file.exists():
        return issues

    # 已知有漏洞的套件版本（簡化版，實務上應查詢 CVE 資料庫）
    KNOWN_VULNERABLE: dict[str, str] = {
        "requests": "<2.31.0",
        "urllib3": "<2.0.7",
        "cryptography": "<41.0.0",
        "pillow": "<10.0.1",
    }

    lines = req_file.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split("==")[0].split(">=")[0].split("<=")[0].strip()
        if pkg.lower() in KNOWN_VULNERABLE:
            issues.append({
                "type": "vulnerable_dependency",
                "severity": "high",
                "file": "requirements.txt",
                "line": 0,
                "detail": f"套件 {pkg} 可能存在已知漏洞，建議更新",
                "recommendation": f"更新 {pkg} 至最新版本",
            })
    return issues
```

#### _make_issue — 建立 issue 物件

```python
def _make_issue(self, issue_type: str, severity: str, file: str, line: int, detail: str) -> dict:
    """建立標準化 issue 物件。"""
    recommendations = {
        "hardcoded_secret": "使用環境變數或 .env 檔案管理敏感資訊",
        "dangerous_call": "避免使用 eval/exec，改用安全的替代方案",
        "sql_injection": "使用參數化查詢，避免字串拼接 SQL",
        "path_traversal": "驗證並正規化檔案路徑，限制存取範圍",
    }
    return {
        "type": issue_type,
        "severity": severity,
        "file": file,
        "line": line,
        "detail": detail,
        "recommendation": recommendations.get(issue_type, "請人工審查"),
    }
```

#### _calculate_risk_score — 計算風險分數

```python
def _calculate_risk_score(self, issues: list[dict]) -> float:
    """計算 0-100 風險分數。"""
    if not issues:
        return 0.0
    weights = {"critical": 10.0, "high": 5.0, "medium": 2.0, "low": 1.0}
    total = sum(weights.get(i["severity"], 1.0) for i in issues)
    return min(100.0, total)
```

#### _summarize_severity — 嚴重度摘要

```python
def _summarize_severity(self, issues: list[dict]) -> dict[str, int]:
    """統計各嚴重度的 issue 數量。"""
    from collections import Counter
    counts = Counter(i["severity"] for i in issues)
    return {"critical": counts.get("critical", 0), "high": counts.get("high", 0),
            "medium": counts.get("medium", 0), "low": counts.get("low", 0)}
```

---

## 輸出格式

```json
{
  "success": true,
  "data": {
    "issues": [
      {
        "type": "hardcoded_secret",
        "severity": "critical",
        "file": "src/config.py",
        "line": 15,
        "detail": "api_key = 'sk-abc123...'",
        "recommendation": "使用環境變數或 .env 檔案管理敏感資訊"
      }
    ],
    "total_issues": 3,
    "severity_summary": {
      "critical": 1,
      "high": 2,
      "medium": 0,
      "low": 0
    },
    "risk_score": 20.0,
    "scan_type": "all",
    "project_dir": "/path/to/project"
  }
}
```

Workflow YAML 串接範例：

```yaml
- id: audit
  type: skill
  skill: security_audit
  params:
    project_dir: "{{ project_root }}"
    scan_type: "all"
    severity: "all"
  output: audit_result

- id: notify
  type: skill
  skill: telegram_notify
  params:
    message: |
      🔒 安全性掃描完成
      風險分數: {{ outputs.audit_result.risk_score }}
      Critical: {{ outputs.audit_result.severity_summary.critical }}
      High: {{ outputs.audit_result.severity_summary.high }}
  condition: "{{ outputs.audit_result.risk_score > 0 }}"
```

## 注意事項

- 掃描範圍自動排除 `.venv`、`venv`、`__pycache__` 目錄
- `SECRET_PATTERNS` 為正則比對，可能產生 false positive，建議人工確認
- 依賴套件漏洞檢查為簡化版，實務上建議整合 `pip-audit` 或 `safety` 工具
- `risk_score` 為 0-100 分，critical 權重 10、high 權重 5
- 路徑操作必須使用 `pathlib.Path`，禁止 `os.path` 字串拼接
- 掃描大型專案時建議限制 `scan_type` 以加速執行
