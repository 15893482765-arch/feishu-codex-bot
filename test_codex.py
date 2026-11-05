# -*- coding: utf-8 -*-
"""本地测试：加载 .env 后直接调用 codex exec，不在命令行暴露密钥。"""
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

CODEX_EXE = r"C:\Users\Administrator\AppData\Roaming\npm\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\bin\codex.exe"
WORKSPACE = PROJECT_ROOT / "group_workspace" / "demo1"

query = sys.argv[1] if len(sys.argv) > 1 else "回复两个字：成功"

env = os.environ.copy()
env["PYTHONUTF8"] = "1"

proc = subprocess.run(
    [CODEX_EXE, "exec", "--skip-git-repo-check", query],
    cwd=str(WORKSPACE),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=300,
)

print(f"returncode={proc.returncode}")
print("===== STDOUT (tail) =====")
print("\n".join(proc.stdout.strip().splitlines()[-15:]))
print("===== STDERR errors =====")
for line in (proc.stderr or "").splitlines():
    if "ERROR" in line or "error" in line.lower():
        print(line)
