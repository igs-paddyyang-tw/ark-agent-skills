"""修復指令產生模組"""
import platform


def generate_fix_commands(result: dict) -> list[str]:
    """根據偵測結果產出修復指令"""
    cmds = []
    is_win = platform.system() == "Windows"

    # Go 未安裝
    if "go" in result and not result["go"]["exists"]:
        if is_win:
            cmds.append("winget install GoLang.Go")
        elif platform.system() == "Darwin":
            cmds.append("brew install go")
        else:
            cmds.append("sudo apt-get install -y golang")

    # Node 未安裝
    if "node" in result and not result["node"]["exists"]:
        if is_win:
            cmds.append("winget install OpenJS.NodeJS.LTS")
        elif platform.system() == "Darwin":
            cmds.append("brew install node")
        else:
            cmds.append("curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs")

    # Python venv 未啟用
    if "python" in result and not result["python"]["venv_active"]:
        cmds.append("python -m venv venv")
        if is_win:
            cmds.append(r"venv\Scripts\activate")
        else:
            cmds.append("source venv/bin/activate")

    # Python 套件缺失
    if "python_packages" in result and result["python_packages"]["missing"]:
        pkgs = " ".join(result["python_packages"]["missing"])
        cmds.append(f"pip install {pkgs}")

    # Node 套件缺失
    if "node_packages" in result and result["node_packages"]["missing"]:
        cmds.append("npm install")

    return cmds
