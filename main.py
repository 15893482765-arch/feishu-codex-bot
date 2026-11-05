import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1, CreateMessageRequest, CreateMessageRequestBody
from dotenv import load_dotenv
import os
import json
import re
import threading
from tasks import run_codex_and_reply
from redis_store import is_event_duplicate

load_dotenv()


def send_feishu_reply(chat_id: str, message_id: str, content: str):
    cli = lark.Client.builder() \
        .app_id(os.getenv("FEISHU_APP_ID")) \
        .app_secret(os.getenv("FEISHU_APP_SECRET")) \
        .log_level(lark.LogLevel.INFO) \
        .build()

    # 修正：receive_id 放在 request_body 内部
    req = CreateMessageRequest.builder() \
        .receive_id_type("chat_id") \
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(json.dumps({"text": content}))
            .build()
        ) \
        .build()

    resp = cli.im.v1.message.create(req)
    if not resp.success():
        print(f"【飞书发送失败】code={resp.code}, msg={resp.msg}")
    else:
        print(f"【飞书回复成功】message_id={message_id}")


def task_wait_wrapper(task, chat_id, message_id):
    try:
        reply_text = task.get()
        send_feishu_reply(chat_id, message_id, reply_text)
    except Exception as e:
        err_msg = f"等待任务结果异常：{str(e)}"
        print(err_msg)
        send_feishu_reply(chat_id, message_id, err_msg)


def on_message_receive_v2(data: P2ImMessageReceiveV1):
    event = data.event
    msg = event.message
    message_id = msg.message_id

    print(f"【收到飞书消息事件】message_id={message_id}")

    if is_event_duplicate(message_id):
        print(f"【重复消息，跳过】message_id={message_id}")
        return

    if msg.message_type != "text":
        print(f"【不是文本消息，跳过，类型={msg.message_type}】")
        return

    if not msg.mentions:
        print("【消息没有@机器人，跳过】")
        return

    try:
        raw_content = json.loads(msg.content)
        raw_text = raw_content.get("text", "")
        print(f"【原始消息文本】{raw_text}")
    except Exception as e:
        print(f"【解析消息内容异常】{e}")
        return

    mention_keys = [getattr(mention, "key", "") for mention in msg.mentions]
    query = raw_text
    for key in mention_keys:
        if key:
            query = query.replace(key, "")
    query = re.sub(r"\s+", " ", query).strip()
    print(f"【清洗后提问】{query}")

    if not query:
        print("【提问为空，跳过】")
        return

    chat_id = msg.chat_id
    print(f"【投递任务到celery】chat_id={chat_id}, message_id={message_id}")
    try:
        task = run_codex_and_reply.delay(chat_id, message_id, query)
        print(f"【任务投递完成】task_id={task.id}")
        # 后台线程等待结果，不阻塞长连接
        threading.Thread(
            target=task_wait_wrapper,
            args=(task, chat_id, message_id),
            daemon=True
        ).start()
    except Exception as exc:
        print(f"【任务投递失败】message_id={message_id}, error={exc}")
        send_feishu_reply(chat_id, message_id, f"任务投递失败：{str(exc)}")


event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(on_message_receive_v2) \
    .build()


if __name__ == "__main__":
    cli = lark.ws.Client(
        os.getenv("FEISHU_APP_ID"),
        os.getenv("FEISHU_APP_SECRET"),
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )
    print("===== 飞书长连接客户端启动中 =====")
    cli.start()
