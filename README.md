# HK Recommend

一个使用 Next.js + React 前端、FastAPI 后端和大模型工具调用的香港课余就餐 Agent。

## 当前功能

- 使用自然语言解析日期、地点、预算、用餐时长、午餐/晚餐时段和饮食需求。
- 地点使用用户原话查询，不再依赖中环、港大、城大等固定地点映射。
- 支持已保存学校作为“学校附近”“下课后”等相对地点的上下文。
- 区分菜系和具体菜品：支持粤菜、川菜、日料等菜系，也支持海鲜、炸鸡、海南鸡饭、乌冬面等具体菜品。
- 根据课程表计算 08:00-22:00 的空闲时间，并预留 30 分钟缓冲。
- 课表支持手动添加和 CSV 导入。
- 学校信息保存到 SQLite，并通过 `/api/profile` 在页面启动时恢复。
- 仅在用户明确表达“喜欢/不吃/以后不要推荐”等长期意愿时保存口味偏好；“今天想吃”只影响当前请求。
- 配置大模型后，由 LLM 从用户自由输入中提取菜品、口味、食材和饮食限制，再由后端校验后保存为结构化记录；没有模型配置时才使用本地规则降级。
- 配置 Google Places API 后，按照用户地点和饮食需求查询真实餐厅。
- 返回 Google 餐厅名称、地址、评分、价格等级或价格区间。
- 餐厅结果以页面卡片展示，Agent 文字只概括空档和结果数量，避免重复输出整张餐厅列表。
- 排队信息统一显示工作日/周末高峰时段说明。
- 页面展示 Agent 的工具调用过程，便于调试和学习。
- 配置 `MODEL_API_KEY` 时使用大模型进行工具规划；模型不可用时自动降级为本地确定性工作流。

## 数据和限制

Google Places API 可以提供地点、营业信息、评分、价格等级等餐厅资料，但没有稳定公开的实时排队人数或等待分钟数接口。因此页面中的排队信息是基于工作日/周末用餐时段的估计，不代表实时排队情况。

Google Places 的价格区间或价格等级不一定是精确人均港币金额。缺少精确价格时，页面会显示“价格较亲民”“中等价位”或“价格未提供”，不会显示虚假的 `HK$0`。

菜单、餐厅介绍和菜品是否真实供应，当前主要依赖 Google Places 搜索结果；后续可以接入菜单数据和 RAG 做二次验证。

## 配置

复制环境变量模板：

```bash
cp backend/.env.example backend/.env
```

在 `backend/.env` 中填写：

```env
# 可选：大模型工具调用
MODEL_API_KEY=
MODEL_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini

# 查询真实餐厅所需
GOOGLE_MAPS_API_KEY=
```

Google Cloud 需要启用 Places API，并配置计费账号。修改 `backend/.env` 后需要重启 FastAPI。

## 运行

后端：

```bash
cd "/Users/n1sm0/学习/Hk Recommend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

前端另开一个终端：

```bash
cd "/Users/n1sm0/学习/Hk Recommend"
npm install
npm run dev
```

打开 <http://localhost:3000>。

验证命令：

```bash
npm run typecheck
npm run build
```

## API

| 方法 | 路径 | 作用 |
|---|---|---|
| `POST` | `/api/chat` | 处理自然语言就餐请求 |
| `GET` | `/api/profile` | 读取已保存学校和课表状态 |
| `GET` | `/api/preferences` | 读取已保存口味偏好 |
| `DELETE` | `/api/preferences` | 清空全部口味偏好 |
| `DELETE` | `/api/preferences/{preference_id}` | 删除一条口味偏好 |
| `GET` | `/api/schedule` | 读取课程表 |
| `POST` | `/api/schedule/manual` | 手动添加课程 |
| `POST` | `/api/schedule/csv` | 导入 CSV 课表 |
| `DELETE` | `/api/schedule/{course_id}` | 删除课程 |
| `GET` | `/health` | 后端健康检查 |

## 目录

```text
app/page.tsx                 React 对话界面和课表设置
backend/main.py              FastAPI 应用入口和 API
backend/agent.py             Agent、自然语言解析和模型工具调用
backend/tools.py             空闲时间和 Google Places 餐厅工具
backend/schedule_store.py    SQLite 课表和学校记忆
backend/.env.example         后端环境变量模板
```

## TODO

- [x] 自然语言解析日期、地点、预算、时长和用餐时段
- [x] 支持菜系和具体菜品的区分
- [x] 支持学校记忆和学校附近的相对地点
- [x] 读取课程表并计算空闲时间
- [x] 手动添加和 CSV 导入课表
- [x] 接入 Google Places Text Search 查询真实餐厅
- [x] 显示 Google 评分、地址和价格等级/价格区间
- [x] 显示工作日和周末排队风险时段估计
- [x] Agent 工具调用轨迹展示
- [x] ai 识别今天的日期
- [x] 当用户提问包含下课去哪吃内容时，增加距离显示，预计排队风险
- [ ] 增加用户饮食偏好记忆
- [ ] 接入餐厅菜单、菜品和过敏原资料
- [ ] 增加 RAG 菜单检索和餐厅菜品二次验证
- [ ] 增加餐厅营业状态和数据更新时间展示
- [ ] 增加 Python `pytest` 和端到端测试
- [ ] 增加错误监控、请求日志和 API 重试策略
- [ ] 增加 `.ics` 课表导入
- [ ] 搜索结果可能不是餐厅
