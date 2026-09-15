import json
import os
import re
from datetime import datetime
from typing import Any

import httpx

from .schedule_store import get_school, list_courses, save_school
from .tools import WEEKDAYS, courses_for_date, get_free_slots, local_date_from_message, search_restaurants


def parse_message(message: str, default_location: str | None = None) -> dict[str, Any]:
    # Keep the user's original place text. Google Places handles aliases and landmarks.
    location_match = re.search(r"(?:在|去|位于|位於)\s*([^，。,.！!；;\n]{2,60}?)(?:附近|一带|一帶|吃|用餐|$)", message)
    location_query = location_match.group(1).strip() if location_match else None
    relative_location = bool(location_query and re.fullmatch(r"学校|學校|校园|校園|学校旁边|學校旁邊|校门口|校門口|校园旁边|校園旁邊", location_query))
    resolved_location = default_location if relative_location else location_query
    area = resolved_location or default_location or ""
    cuisine = "日料" if re.search(r"日料|日本菜|寿司|壽司", message) else "粤菜" if re.search(r"粤菜|粵菜|港式|茶餐厅|茶餐廳", message) else "西餐" if "西餐" in message else "东南亚" if re.search(r"东南亚|東南亞|泰国|泰國|越南", message) else "素食" if re.search(r"素食|斋|齋", message) else "all"
    budget_match = re.search(r"(?:预算|預算|人均|最多|不超过|不超過|以内|以內)[^\d]{0,6}(\d{2,4})", message, re.I) or re.search(r"(\d{2,4})\s*(?:港币|港幣|hkd|元|块|塊)", message, re.I)
    minute_match = re.search(r"(\d{2,3})\s*(?:分钟|分鐘|min)", message, re.I)
    hour_match = re.search(r"(\d(?:\.\d+)?)\s*(?:小时|小時)", message)
    period = "dinner" if re.search(r"晚餐|晚上|傍晚", message) else "lunch" if re.search(r"午餐|中午", message) else None
    budget = int(budget_match.group(1)) if budget_match else 100
    duration = int(minute_match.group(1)) if minute_match else round(float(hour_match.group(1)) * 60) if hour_match else 60
    date = local_date_from_message(message)
    area_name = area or "未指定"
    understood = [f"日期 {date}", f"地点 {area_name}", f"预算 HK${budget}", f"用餐 {duration} 分钟", "菜系不限" if cuisine == "all" else f"菜系 {cuisine}"]
    if period:
        understood.append("午餐时段" if period == "lunch" else "晚餐时段")
    return {"date": date, "area": area, "location_query": resolved_location or area_name, "budget": budget, "cuisine": cuisine, "duration": duration, "preferred_period": period, "understood": understood}


def school_from_message(message: str) -> str | None:
    names = r"香港城市大学|香港城市大學|香港大学|香港大學|香港中文大学|香港中文大學|香港科技大学|香港科技大學|香港理工大学|香港理工大學|香港浸会大学|香港浸會大學|城市大学|城市大學|中文大学|中文大學|科技大学|理工大学|理工大學|浸会大学|浸會大學|港大|城大|科大"
    explicit = re.search(rf"(?:我在|我就读于|我就讀於|学校是|學校是|就读于|就讀於)\s*({names})", message)
    if explicit:
        return explicit.group(1).strip()
    full_name = re.search(r"(香港城市大学|香港城市大學|香港大学|香港大學|香港中文大学|香港中文大學|香港科技大学|香港科技大學|香港理工大学|香港理工大學|香港浸会大学|香港浸會大學)", message)
    return full_name.group(1).strip() if full_name else None


def deterministic_agent(message: str) -> dict[str, Any]:
    school = get_school()
    mentioned_school = school_from_message(message)
    if mentioned_school:
        school = save_school(mentioned_school)
    parsed = parse_message(message, school)
    has_schedule = bool(list_courses())
    courses = courses_for_date(parsed["date"]) if has_schedule else []
    slots = get_free_slots(courses, parsed["duration"])
    meal_period = parsed["preferred_period"] or ("lunch" if any(slot["start"] < "14:00" for slot in slots) else "dinner")
    recommendations = search_restaurants(parsed["area"], parsed["budget"], parsed["cuisine"], meal_period, parsed.get("location_query")) if slots and parsed["area"] else []
    weekday = WEEKDAYS[(datetime.strptime(parsed["date"], "%Y-%m-%d").date().weekday() + 1) % 7]
    if not slots:
        answer = f"我查了{weekday}的课表，没有找到满足 {parsed['duration']} 分钟用餐需求的空闲时段。你可以换一天或缩短用餐时间。"
    elif not parsed["area"]:
        answer = "我找到了可用时间段，但还不知道你想去哪里。请告诉我地标、商场、车站或街道，我会用 Google Maps 查找附近餐厅。"
    elif not recommendations and not os.getenv("GOOGLE_MAPS_API_KEY"):
        answer = "我已识别地点，但后端尚未配置 GOOGLE_MAPS_API_KEY，暂时无法调用 Google Maps 查找真实餐厅。请配置 key 后重启后端。"
    elif not recommendations:
        answer = "我调用了 Google Maps，但暂时没有找到符合预算和菜系要求的餐厅。可以放宽预算或告诉我“菜系不限”。"
    else:
        answer = f"我查了{weekday}的课表，找到 {len(slots)} 个可用时间段，并按距离、预算和排队风险选出了 {len(recommendations)} 家餐厅。"
    profile_hint = ""
    if not school:
        profile_hint = "\n\n提示：你也可以告诉我就读学校，并在左侧导入课表；之后我会记住这些信息，按真实空闲时间推荐。"
    elif not has_schedule:
        profile_hint = f"\n\n我记得你就读于 {school}。如果导入课表，我可以把推荐限制在你的真实课余时间。"
    return {"answer": answer + profile_hint, "parsed": parsed, "profile": {"school": school, "has_schedule": has_schedule}, "result": {"date": parsed["date"], "weekday": weekday, "courses": courses, "freeSlots": slots, "mealPeriod": meal_period, "recommendations": recommendations, "agentTrace": ["读取已记住的学校" if school else "未设置学校，使用通用推荐", "解析自然语言需求", "调用 get_free_slots 查询课表空闲时间", "调用 search_restaurants 筛选餐厅", "按时段估计拥挤风险并排序"]}}


TOOLS = [
    {"type": "function", "function": {"name": "get_free_slots", "description": "查询指定日期的课程空闲时间，必须先调用此工具。", "parameters": {"type": "object", "properties": {"date": {"type": "string", "description": "YYYY-MM-DD"}, "duration": {"type": "integer", "description": "用餐分钟数"}}, "required": ["date", "duration"]}}},
    {"type": "function", "function": {"name": "search_restaurants", "description": "按照用户提供的自然语言地点、预算、菜系和午晚餐时段搜索真实餐厅。", "parameters": {"type": "object", "properties": {"area": {"type": "string", "description": "自然语言地点，例如又一城、九龙塘站附近或 HKU"}, "budget": {"type": "integer"}, "cuisine": {"type": "string"}, "meal_period": {"type": "string", "enum": ["lunch", "dinner"]}}, "required": ["area", "budget", "cuisine", "meal_period"]}}},
]


def model_agent(message: str) -> dict[str, Any]:
    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        return deterministic_agent(message)
    base_url = os.getenv("MODEL_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("MODEL_NAME", "gpt-4o-mini")
    local = deterministic_agent(message)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": f"你是香港课余就餐 Agent。用户学校是 {local.get('profile', {}).get('school', '未提供')}。学校和课表是可选个性化信息，不得阻止普通餐厅推荐。必须先调用 get_free_slots，再调用 search_restaurants。只使用工具返回的数据，不要编造餐厅。最后用简洁中文回答。"},
        {"role": "user", "content": message},
    ]
    state = local["result"]
    try:
        with httpx.Client(timeout=45) as client:
            for _ in range(4):
                response = client.post(f"{base_url}/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json={"model": model, "messages": messages, "tools": TOOLS, "tool_choice": "auto"})
                response.raise_for_status()
                assistant = response.json()["choices"][0]["message"]
                messages.append(assistant)
                calls = assistant.get("tool_calls", [])
                if not calls:
                    return {**local, "answer": assistant.get("content") or local["answer"], "result": {**state, "agentTrace": ["大模型理解自然语言需求", "模型选择并调用后端工具", "校验工具结果并生成回答"]}}
                for call in calls:
                    name = call["function"]["name"]
                    arguments = json.loads(call["function"].get("arguments", "{}"))
                    if name == "get_free_slots":
                        value = get_free_slots(courses_for_date(arguments["date"]) if list_courses() else [], int(arguments.get("duration", 60)))
                        state["freeSlots"] = value
                    elif name == "search_restaurants":
                        value = search_restaurants(arguments["area"], int(arguments.get("budget", 100)), arguments.get("cuisine", "all"), arguments.get("meal_period", "lunch"), arguments["area"])
                        state["recommendations"] = value
                    else:
                        value = {"error": "unknown tool"}
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(value, ensure_ascii=False)})
    except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError):
        return {**local, "result": {**local["result"], "agentTrace": ["大模型调用失败，切换本地工具工作流", *local["result"]["agentTrace"]]}}
    return local
