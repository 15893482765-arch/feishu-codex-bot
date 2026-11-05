import redis
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()
r = redis.from_url(os.getenv("REDIS_URL"))

# 幂等：event_id 5分钟过期，防止飞书重试重复执行
def is_event_duplicate(message_id: str) -> bool:
    key = f"feishu:msg:{message_id}"
    if r.exists(key):
        return True
    r.setex(key, 300, "ok")
    return False

# 群聊chat_id绑定工作目录，在这里新增/修改映射
CHAT_DIR_MAP = {
    "oc_8f9de153ab9f32f52f1669c044004b48": "group_workspace/demo1"
}

def get_group_workspace(chat_id: str) -> str:
    # Celery worker 可能从任意工作目录启动，不能依赖当前目录。
    project_root = Path(__file__).resolve().parent
    relative_workspace = CHAT_DIR_MAP.get(chat_id, "group_workspace/default")
    return str((project_root / relative_workspace).resolve())
