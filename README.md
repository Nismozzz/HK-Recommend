# HK Recommend

一个使用 Next.js + React 前端、FastAPI 后端和大模型工具调用的香港课余就餐推荐 Agent 初版。

## 当前功能

- React/Next.js App Router 对话界面。
- FastAPI：`POST /api/chat` 和 `GET /health`。
- 从中文对话中提取日期、地点、预算、菜系、用餐时长和午晚餐时段。
- 根据示例课表计算 08:00-22:00 的空闲时间，并预留 30 分钟缓冲。
- 按活动地点、预算和菜系筛选餐厅。
- 按午餐/晚餐时段估计排队风险并排序。
- 页面展示 Agent 的执行轨迹，便于学习工具调用流程。
- 课表支持手动添加或 CSV 导入，课程字段为星期、课程号、开始时间和结束时间。

当前 Agent 支持两种模式：配置 `MODEL_API_KEY` 时由大模型通过工具调用完成规划；没有 key 时自动降级为本地中文解析和确定性工具工作流。

配置 `GOOGLE_MAPS_API_KEY` 后，后端会通过 Google Places Text Search 查询真实餐厅，并返回名称、类型、评分（五分制）和地址。Google Places 不提供稳定的人均港币价格，因此真实结果暂不按预算过滤；接口失败时会回退到示例数据。

## 运行

终端 1（后端）：

```bash
cd "/Users/n1sm0/学习/Hk Recommend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example .env
uvicorn backend.main:app --reload --port 8000
```

终端 2（前端）：

```bash
npm install
npm run dev
```

然后打开 <http://localhost:3000>。

也可以运行：

```bash
npm run typecheck
npm run build
```

## 目录

```text
app/page.tsx                 React 页面
backend/main.py              FastAPI 应用入口
backend/agent.py             大模型 Agent 和本地降级逻辑
backend/tools.py             课表、餐厅工具
backend/data.py              后端示例数据
app/api/chat/route.ts        旧版 Next.js 兼容接口
lib/parse-request.ts         旧版前端解析逻辑
lib/data.ts                  示例课表和餐厅数据
lib/recommend.ts             时间计算与 Agent 工作流
app/globals.css              页面样式
```

## 下一步

1. 将 `lib/data.ts` 改成 SQLite/PostgreSQL 数据源。
2. 增加 `.ics` 课表导入和用户偏好记忆。
3. 将 `getFreeSlots` 和餐厅筛选封装成工具，接入支持 tool calling 的模型。
4. 接入地图、营业时间和餐厅平台数据，并显示来源与更新时间。
5. 为时间计算、筛选逻辑和 Agent 工具调用增加 `pytest` 测试。

排队风险目前是示例估计，不是实时承诺。
