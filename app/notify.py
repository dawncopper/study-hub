"""推送模块：企业微信 / 微信群机器人 / 邮件 SMTP（文档 F9）。"""
import smtplib
from email.header import Header
from email.mime.text import MIMEText

import requests


def send_wecom(webhook: str, text: str) -> str:
    """企业微信群机器人。"""
    try:
        resp = requests.post(
            webhook, json={"msgtype": "text", "text": {"content": text}}, timeout=10
        )
        data = resp.json()
        if data.get("errcode") == 0:
            return "企业微信：发送成功"
        return f"企业微信：发送失败（{data.get('errmsg', resp.status_code)}）"
    except Exception as e:  # noqa: BLE001
        return f"企业微信：发送失败（{e}）"


def send_wechat(webhook: str, text: str) -> str:
    """微信群机器人（与企业微信 webhook 协议一致）。"""
    try:
        resp = requests.post(
            webhook, json={"msgtype": "text", "text": {"content": text}}, timeout=10
        )
        data = resp.json()
        if data.get("errcode") == 0:
            return "微信群：发送成功"
        return f"微信群：发送失败（{data.get('errmsg', resp.status_code)}）"
    except Exception as e:  # noqa: BLE001
        return f"微信群：发送失败（{e}）"


def send_email(
    smtp_host: str,
    port: int | str,
    user: str,
    password: str,
    to_addr: str,
    subject: str,
    body: str,
) -> str:
    """SMTP SSL 发送邮件。"""
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = user
        msg["To"] = to_addr
        with smtplib.SMTP_SSL(smtp_host, int(port), timeout=15) as server:
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
        return "邮件：发送成功"
    except Exception as e:  # noqa: BLE001
        return f"邮件：发送失败（{e}）"


def send_notification(settings: dict, text: str) -> list[str]:
    """按已配置渠道全部发送，返回各渠道结果。"""
    results: list[str] = []

    wc = (settings.get("notify_wecom_webhook") or "").strip()
    if wc:
        results.append(send_wecom(wc, text))

    wx = (settings.get("notify_wechat_webhook") or "").strip()
    if wx:
        results.append(send_wechat(wx, text))

    host = (settings.get("notify_email_smtp") or "").strip()
    if host:
        results.append(
            send_email(
                host,
                settings.get("notify_email_port") or "465",
                settings.get("notify_email_user") or "",
                settings.get("notify_email_pass") or "",
                settings.get("notify_email_to") or "",
                "【学习小站提醒】",
                text,
            )
        )
    return results


def build_reminder_text(rows: list[tuple[str, str]]) -> str:
    """构建未完成提醒文案。rows: [(类别名, 科目名), ...]"""
    lines = "\n".join(f"· {c}·{s}" for c, s in rows)
    return (
        f"【学习小站提醒】孩子今天还有 {len(rows)} 项任务未完成：\n"
        f"{lines}\n"
        "快去和孩子一起完成打卡吧~"
    )
