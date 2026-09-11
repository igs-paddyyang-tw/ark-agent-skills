import sys
# 🔴 `--help` 不需要任何第三方依賴 —— 在 import 之前先攔截。
#    否則沒裝套件的人連「這支怎麼用」都看不到，只會拿到 traceback。
#    （scripts/tests/test_cli_contract.py 在驗）
if __name__ == "__main__" and {"-h", "--help"} & set(sys.argv[1:]):
    print(__doc__ or "")
    raise SystemExit(0)

from pypdf import PdfReader




reader = PdfReader(sys.argv[1])
if (reader.get_fields()):
    print("This PDF has fillable form fields")
else:
    print("This PDF does not have fillable form fields; you will need to visually determine where to enter data")
