---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 3633ca83b40dddc277e8ec78acdb8e95_2e2a6b8ab29a11f19369525400de85a5
    ReservedCode1: ERsCxgd+ftohDFiTrQIzfyRHNWvAskRYkVnB6yNs/2S57UYr2SIPv3f6MEBeZwRGftwKUcDBNHzW/kXdyiYvQbzreeTnKBPeOlV8/LeNEsS/BtNP2ZaYiHak3C8FJlZyWa47lGePRGllAnqjTJT+DezxoQogkwvjL9+IeNLMN0VBrSBfjhRz2y6K/9g=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 3633ca83b40dddc277e8ec78acdb8e95_2e2a6b8ab29a11f19369525400de85a5
    ReservedCode2: ERsCxgd+ftohDFiTrQIzfyRHNWvAskRYkVnB6yNs/2S57UYr2SIPv3f6MEBeZwRGftwKUcDBNHzW/kXdyiYvQbzreeTnKBPeOlV8/LeNEsS/BtNP2ZaYiHak3C8FJlZyWa47lGePRGllAnqjTJT+DezxoQogkwvjL9+IeNLMN0VBrSBfjhRz2y6K/9g=
---



# 学习小站 StudyHub

面向初一学生的每日学习验证 + 积分激励应用（多家长协作）。家长负责记录与验证，孩子只看到童趣的学习报告页，不接触后台。

技术栈：**FastAPI + SQLAlchemy + Jinja2 + APScheduler + Tesseract OCR + ReportLab**，前端为 **iOS 风格设计系统**（明暗双模式 / 响应式 / 动效 / 完整状态设计）。

---

## 功能一览

| 模块 | 说明 |
| --- | --- |
| 每日打卡 | 按 作业/预习/拓展 三类、分科目记录，状态（完成/部分/未完成）+ 质量星级，自动积分 |
| 难点疑点 | 记录难点、家长协助解决并写解法，积分激励 |
| 错题本 | 手动录入 / **OCR 拍照识别**，掌握状态跟踪（待复习/已复习/已掌握），按知识点筛选 |
| 积分兑换 | 星数余额、成长树等级、勋章成就、兑换游戏时间、流水明细 |
| 统计报表 | 周报 / 月报（完成率、模块统计、趋势图）、**PDF 导出** |
| 定时提醒 | APScheduler 每晚 20:00 检查未完成打卡，通过 Webhook 推送提醒 |
| 多家长 | 管理员 / 成员角色，科目分工，会话登录（Cookie Session） |
| 儿童端 | 只读展示页 `/kid`，显示今日完成、积分、成长树、兑换记录 |

## 快速开始（本地）

```bash
# 1. 安装依赖（OCR 需系统安装 tesseract-ocr 及中文语言包）
pip install -r requirements.txt

# 2. 启动（首次启动自动建表 + 初始化默认数据）
uvicorn app.main:app --reload --port 8000

# 3. 访问
#    家长端： http://127.0.0.1:8000/   （默认账号 admin / 123456）
#    儿童端： http://127.0.0.1:8000/kid
```

> 默认账号：`admin / 123456`（可在「设置 → 家长管理」中修改密码、新增家长）。

## Docker / Docker Compose 部署

```bash
docker compose up -d --build
# 访问 http://<服务器IP>:8000/
```

## 群晖 NAS 部署步骤

1. 将整个项目目录（含 `app/`、`requirements.txt`、`Dockerfile`、`docker-compose.yml`）上传到群晖的共享文件夹，例如 `/volume1/docker/studyhub`。
2. 打开群晖 **Container Manager**（DSM 7.2+）→ **项目** → 新增，选择路径 `/volume1/docker/studyhub`，来源选「使用现有的 docker-compose.yml」，点击下一步并启动。
   - 老版本套件中心安装 Docker 套件后，在「容器 → 项目」中导入 `docker-compose.yml`。
3. 等待镜像构建与容器启动（首次需拉取 Python 镜像并编译依赖，约 5-15 分钟）。
4. 浏览器访问 `http://群晖IP:8000/`；如需外网访问，在群晖「控制面板 → 登录门户 → 高级 → 反向代理」中添加规则，把域名/端口反代到 `localhost:8000`。
5. 数据持久化：SQLite、上传的错题图片、PDF 导出均存放于 `./data`（已挂载为卷 `studyhub_data`），备份该目录即可备份全部业务数据。
6. 定时提醒（APScheduler）在容器内以 Asia/Shanghai 时区运行，默认每天 20:00 检查；可在「设置 → 通知提醒」中配置 Webhook 地址与提醒时间。

## 目录结构

```
study-hub/
├── app/
│   ├── main.py               # FastAPI 入口：路由挂载、登录/仪表盘/儿童端
│   ├── database.py           # SQLAlchemy 引擎与会话
│   ├── models.py             # 11 张数据表
│   ├── auth.py               # 会话认证（PBKDF2 + Cookie Session）
│   ├── seed.py               # 默认数据初始化
│   ├── common.py             # 积分 / 勋章 / 公共辅助
│   ├── ocr.py                # 错题识别（OpenRouter 视觉 AI + Tesseract OCR 兜底）
│   ├── notify.py             # Webhook 推送
│   ├── report.py             # 统计与 PDF 导出
│   ├── scheduler.py          # APScheduler 定时提醒
│   ├── routes_daily.py       # 每日打卡
│   ├── routes_difficulty.py  # 难点疑点
│   ├── routes_errorbook.py   # 错题（OCR 上传 / PDF 导出）
│   ├── routes_rewards.py     # 积分兑换 / 勋章 / 流水
│   ├── routes_stats.py       # 统计报表
│   ├── routes_settings.py    # 设置（学生 / 科目 / 规则 / 通知 / 家长 / 安全）
│   ├── templates/            # Jinja2 模板（12 个）
│   └── static/css/style.css  # iOS 风格设计系统
│   └── static/js/app.js      # 主题 / 交互脚本
├── data/                     # 运行时数据（SQLite / 上传 / 导出）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 数据表（11 张）

`parents` 家长 · `students` 学生 · `subjects` 科目 · `daily_records` 每日打卡 · `difficulties` 难点疑点 · `error_items` 错题 · `reward_configs` 积分规则 · `point_transactions` 积分流水 · `game_time_orders` 游戏时间兑换 · `badges` 成就勋章 · `settings` 系统设置

## 备注

- 默认数据：1 名学生（小明）、语/数/英 3 科目、管理员 admin、7 条积分规则、2 条系统设置。
- 错题识别支持两级方案：
  1. **OpenRouter 视觉 AI（推荐）**：在「设置 → 错题 AI 识别」中粘贴 OpenRouter API Key 并启用，上传错题将优先调用免费模型 `inclusionai/ling-3.0-flash-vl:free` 识别题目与答案（30 秒超时，识别来源标注为「AI」）。
  2. **Tesseract OCR（兜底）**：AI 未启用、未配置 Key 或识别失败时自动回退，依赖 `pytesseract` + 系统 `tesseract-ocr`（需 `chi_sim` 语言包），识别来源标注为「OCR」。
  - 可点击「发送测试识别请求」验证 Key 与网络连通性；识别失败时仍可直接手填题目。
- 积分规则可在「设置 → 积分规则」中参数化调整，改动实时生效。
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
