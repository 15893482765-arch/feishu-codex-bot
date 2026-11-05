from celery import Celery
import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv
from redis_store import get_group_workspace

load_dotenv()

app = Celery("codex_worker", broker=os.getenv("REDIS_URL"))
app.conf.update(
    result_backend=os.getenv("REDIS_URL"),
    task_ignore_result=False,
    task_track_started=True,
    result_expires=3600,
)

DEFAULT_CODEX_EXE = (
    r"C:\Users\Administrator\AppData\Roaming\npm\node_modules\@openai\codex"
    r"\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\bin\codex.exe"
)


@app.task(bind=True)
def run_codex_and_reply(self, chat_id: str, message_id: str, query: str):
    workspace = get_group_workspace(chat_id)
    os.makedirs(workspace, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    timeout = int(os.getenv("CODEX_TIMEOUT", 300))
    codex_path = os.getenv("CODEX_EXEC_PATH", DEFAULT_CODEX_EXE)

    # --output-last-message: 让 codex 把最终回答写入文件，便于可靠提取
    last_message_file = Path(workspace) / f".codex_last_{message_id}.txt"

    print(f"【开始执行 Codex】task_id={self.request.id}, message_id={message_id}, workspace={workspace}")
    print(f"【Codex 路径】{codex_path}")

    cmd = [
        codex_path,
        "exec",
        "--skip-git-repo-check",
        "--output-last-message", str(last_message_file),
        query,
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        print(f"returncode={proc.returncode}")
        if stderr:
            print(f"===== STDERR (tail) =====\n{stderr[-800:]}")

        if proc.returncode != 0:
            # 从 stderr 中提取关键错误行，避免整段日志刷屏
            err_lines = [
                ln for ln in stderr.splitlines()
                if ln.startswith("ERROR") or "unexpected status" in ln
            ]
            brief = "\n".join(err_lines[-3:]) if err_lines else stderr[-500:]
            reply_text = f"Codex 执行失败（返回码 {proc.returncode}）：\n{brief}"
        else:
            # 优先读取 --output-last-message 的结果，其次退回 stdout
            reply_text = ""
            if last_message_file.exists():
                reply_text = last_message_file.read_text(encoding="utf-8", errors="replace").strip()
                last_message_file.unlink(missing_ok=True)
            if not reply_text:
                reply_text = stdout
            if not reply_text:
                reply_text = "Codex 执行完成，但没有返回文本结果。"

    except subprocess.TimeoutExpired:
        reply_text = f"执行超时（{timeout}s），Codex 任务被终止"
    except Exception as e:
        reply_text = f"任务异常：{str(e)}"

    return reply_text
