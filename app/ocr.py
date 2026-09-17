"""错题 OCR 识别（Tesseract 5 + chi_sim，文档 5.5）。

处理流程：
1. 保存图片（随机文件名 err_YYYYMMDD_<uid>_<hex>.jpg）
2. 转灰度 → 增强对比度（阈值 140 二值化）
3. tesseract image_to_string(lang="chi_sim+eng", config="--psm 6")
4. 清理空行，截断 2000 字符
5. 启发式切分题目/答案
6. OCR 失败返回占位提示，家长在编辑页手工补录
"""
import os
import uuid
from datetime import datetime

from .database import UPLOAD_DIR


def generate_image_name() -> str:
    now = datetime.now()
    uid = now.strftime("%H%M%S")
    hex_part = uuid.uuid4().hex[:8]
    return f"err_{now.strftime('%Y%m%d')}_{uid}_{hex_part}.jpg"


def save_upload(upload_file) -> str:
    """保存上传图片，返回文件名（数据在 data/uploads/）。"""
    filename = generate_image_name()
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(upload_file.file.read())
    return filename


def preprocess(image_path: str):
    from PIL import Image, ImageOps

    img = Image.open(image_path)
    img = ImageOps.grayscale(img)
    # 阈值 140 二值化，增强对比度
    img = img.point(lambda p: 255 if p > 140 else 0)
    return img


_QA_MARKERS = ["【答案】", "答案：", "答案:", "参考答案", "答：", "答:"]


def split_qa(text: str) -> tuple[str, str]:
    """按答案标记切分题目与答案。"""
    hits = [(text.find(m), m) for m in _QA_MARKERS if text.find(m) >= 0]
    if not hits:
        return text, ""
    pos, marker = min(hits, key=lambda x: x[0])
    question = text[:pos].strip()
    answer = text[pos + len(marker):].strip()
    return question, answer


def ocr_image(image_path: str) -> tuple[str, str]:
    """OCR 识别并切分。返回 (question, answer)。"""
    import pytesseract

    try:
        img = preprocess(image_path)
        raw = pytesseract.image_to_string(
            img, lang="chi_sim+eng", config="--psm 6"
        )
    except Exception:
        return "（OCR 识别失败，请在编辑页手工补录题目）", ""

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    text = "\n".join(lines)[:2000]
    question, answer = split_qa(text)
    if not question.strip():
        question = "（OCR 未能识别出题目文字，请在编辑页手工补录）"
    return question, answer


# ============================================================
# OpenRouter 免费视觉模型识别（inclusionai/ling-3.0-flash-vl:free）
# 失败返回 None，由调用方回退 Tesseract
# ============================================================

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "inclusionai/ling-3.0-flash-vl:free"
OPENROUTER_TIMEOUT = 30  # 秒

_OCR_PROMPT = (
    "这是一张错题/作业题目照片。请识别题目内容并给出正确答案。"
    "只返回一个 JSON 对象，不要输出任何其他文字或代码块标记："
    '{"question": "题目文字", "answer": "正确答案"}'
)


def image_to_data_url(image_path: str, max_side: int = 1600, quality: int = 85) -> str:
    """图片转 JPEG base64 data URL（压缩避免超 token 限制）。"""
    import base64
    import io

    from PIL import Image

    img = Image.open(image_path)
    img.thumbnail((max_side, max_side))
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def extract_json_object(text: str) -> dict | None:
    """从模型输出中提取 JSON 对象（容忍 markdown 代码块与前后杂文）。"""
    import json
    import re

    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    s, e = text.find("{"), text.rfind("}")
    if 0 <= s < e:
        try:
            return json.loads(text[s : e + 1])
        except Exception:
            pass
    return None


def openrouter_recognize(image_path: str, api_key: str, timeout: int = OPENROUTER_TIMEOUT) -> dict | None:
    """调用 OpenRouter 免费视觉模型识别错题。

    返回 {"question": str, "answer": str, "raw": str}；任何失败（超时/无 key/
    非 200/解析失败/无 question 字段）均返回 None。
    """
    if not api_key:
        return None
    import requests

    try:
        data_url = image_to_data_url(image_path)
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _OCR_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "max_tokens": 1500,
            "temperature": 0.1,
        }
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = extract_json_object(content)
        if not parsed or not str(parsed.get("question", "")).strip():
            return None
        return {
            "question": str(parsed.get("question", "")).strip(),
            "answer": str(parsed.get("answer", "")).strip(),
            "raw": content,
        }
    except Exception:
        return None
