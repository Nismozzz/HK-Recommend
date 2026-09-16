import json
import os
import re
from datetime import datetime
from typing import Any

import httpx

from .schedule_store import get_preferences, get_school, list_courses, save_preference, save_school
from .tools import WEEKDAYS, courses_for_date, get_free_slots, local_date_from_message, parse_minutes, search_restaurants


PREFERENCE_TERMS = {
    "cuisine": ["日料", "粤菜", "粵菜", "川菜", "西餐", "东南亚", "東南亞"],
    "flavor": ["辣", "清淡", "甜", "咸", "鹹", "酸"],
    "ingredient": ["香菜", "葱", "蔥", "海鲜", "海鮮", "花生", "牛肉", "猪肉", "豬肉"],
    "dietary": ["素食", "纯素", "純素", "清真", "不吃牛"],
}


def extract_preferences(message: str) -> list[tuple[str, str, str]]:
    """Extract only explicit long-term preference statements; temporary requests are ignored."""
    results: list[tuple[str, str, str]] = []
    for marker, preference in ((r"喜欢|喜歡|愛吃|爱吃|偏好|常吃", "like"), (r"不吃|不喜欢|不喜歡|讨厌|討厭|忌口|过敏|過敏|不要推荐|不要推薦|不要再推荐|不要再推薦", "dislike")):
        for match in re.finditer(rf"(?:我)?(?:{marker})(?:吃|推荐|推薦)?([^，。；;.!！?？\n]+)", message):
            text = match.group(1)
            for category, terms in PREFERENCE_TERMS.items():
                for term in terms:
                    if term in text and (category, term, preference) not in results:
                        results.append((category, term, preference))
    return results


def extract_preferences_with_model(message: str, api_key: str, base_url: str, model: str) -> None:
    """Ask the model for arbitrary user-provided preferences, then validate before persistence."""
    prompt = {
        "model": model,
        "messages": [
            {"role": "system", "content": "从用户消息中提取长期口味记忆。只有明确表达喜欢、爱吃、偏好、不吃、忌口、过敏或以后不要推荐时才提取；‘今天想吃’等临时需求不要提取。只返回 JSON，不要 Markdown：{\"preferences\":[{\"category\":\"cuisine|dish|flavor|ingredient|dietary\",\"value\":\"用户原话中的具体内容\",\"preference\":\"like|dislike\"}]}。菜品、口味和食材可以是任意用户输入，不要限制在预设列表。"},
            {"role": "user", "content": message},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    try:
        response = httpx.post(f"{base_url}/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json=prompt, timeout=20)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"].get("content", "{}")
        payload = json.loads(content)
        for item in payload.get("preferences", []):
            if not isinstance(item, dict):
                continue
            save_preference(str(item.get("category", "")), str(item.get("value", "")), str(item.get("preference", "")), "llm")
    except (httpx.HTTPError, KeyError, ValueError, TypeError, json.JSONDecodeError):
        return


def parse_message(message: str, default_location: str | None = None) -> dict[str, Any]:
    # Keep the user's original place text. Google Places handles aliases and landmarks.
    location_match = re.search(r"(?:在|去|位于|位於)\s*([^，。,.！!；;\n]{2,60}?)(?:附近|一带|一帶|吃|用餐|$)", message)
    location_query = location_match.group(1).strip() if location_match else None
    if not location_query:
        after_class_location = re.search(r"下(?:了)?课[^，。,.！!；;\n]*[，,]\s*([^，。,.！!；;\n]{2,60}?)(?:附近|有什么|有什麼|吃|用餐|$)", message)
        location_query = after_class_location.group(1).strip() if after_class_location else None
    if not location_query:
        nearby_location = re.search(r"([^，。,.！!；;\n]{2,40}?)(?:附近|有什么|有什麼)(?:吃|餐厅|餐廳|美食|$)", message)
        candidate = nearby_location.group(1).strip() if nearby_location else None
        if candidate and not re.search(r"下课|下了课|下課|放学|放學|今天|明天|后天", candidate):
            location_query = candidate
    if location_query and re.search(r"(?:周|星期)[一二三四五六日天]|下课|下課|午餐|晚餐|吃饭|吃飯|用餐", location_query):
        location_query = None
    relative_location = bool(location_query and re.fullmatch(r"学校|學校|校园|校園|学校旁边|學校旁邊|校门口|校門口|校园旁边|校園旁邊", location_query))
    resolved_location = default_location if relative_location else location_query
    area = resolved_location or default_location or ""
    cuisine = "日料" if re.search(r"日料|日本菜|寿司|壽司", message) else "粤菜" if re.search(r"粤菜|粵菜|港式|茶餐厅|茶餐廳", message) else "川菜" if re.search(r"川菜|川味|四川菜", message) else "西餐" if "西餐" in message else "东南亚" if re.search(r"东南亚|東南亞|泰国|泰國|越南", message) else "素食" if re.search(r"素食|斋|齋", message) else "all"
    dish_matches = re.findall(r"乌冬面?|烏冬面?|うどん|海鲜|海鮮|炸鸡|炸雞|海南鸡饭|海南雞飯", message, re.I)
    dishes = list(dict.fromkeys(dish_matches))
    food_query = dishes[0] if dishes else (cuisine if cuisine != "all" else None)
    budget_match = re.search(r"(?:预算|預算|人均|最多|不超过|不超過|以内|以內)[^\d]{0,6}(\d{2,4})", message, re.I) or re.search(r"(\d{2,4})\s*(?:港币|港幣|hkd|元|块|塊)", message, re.I)
    minute_match = re.search(r"(\d{2,3})\s*(?:分钟|分鐘|min)", message, re.I)
    hour_match = re.search(r"(\d(?:\.\d+)?)\s*(?:小时|小時)", message)
    period = "dinner" if re.search(r"晚餐|晚上|傍晚", message) else "lunch" if re.search(r"午餐|中午", message) else None
    clock_match = re.search(r"(?<!\d)([01]?\d|2[0-3])\s*[点時时:：]\s*([0-5]\d)?", message)
    if clock_match:
        hour = int(clock_match.group(1))
        minute = int(clock_match.group(2) or (30 if "半" in message[clock_match.start():clock_match.end() + 1] else 0))
        if ("下午" in message or "晚上" in message) and hour < 12:
            hour += 12
        request_time = f"{hour:02d}:{minute:02d}"
    elif period == "dinner":
        request_time = "19:00"
    elif period == "lunch":
        request_time = "12:30"
    else:
        request_time = None
    budget = int(budget_match.group(1)) if budget_match else 100
    duration = int(minute_match.group(1)) if minute_match else round(float(hour_match.group(1)) * 60) if hour_match else 60
    date = local_date_from_message(message)
    after_class = bool(re.search(r"下课|下了课|下課|下了課|放学|放學", message))
    area_name = area or "未指定"
    understood = [f"日期 {date}", f"地点 {area_name}", f"预算 HK${budget}", f"用餐 {duration} 分钟"]
    understood.append(f"菜品 {', '.join(dishes)}" if dishes else ("菜系不限" if cuisine == "all" else f"菜系 {cuisine}"))
    if period:
        understood.append("午餐时段" if period == "lunch" else "晚餐时段")
    if after_class:
        understood.append("下课后出发，餐厅范围 1 公里内")
    if request_time:
        understood.append(f"查询时间 {request_time}")
    return {"date": date, "area": area, "location_query": resolved_location or area_name, "budget": budget, "cuisine": cuisine, "food_query": food_query, "dishes": dishes, "duration": duration, "preferred_period": period, "request_time": request_time, "after_class": after_class, "understood": understood}


def school_from_message(message: str) -> str | None:
    names = r"香港城市大学|香港城市大學|香港大学|香港大學|香港中文大学|香港中文大學|香港科技大学|香港科技大學|香港理工大学|香港理工大學|香港浸会大学|香港浸會大學|城市大学|城市大學|中文大学|中文大學|科技大学|理工大学|理工大學|浸会大学|浸會大學|港大|城大|科大|cityu|city university|hku|the university of hong kong"
    explicit = re.search(rf"(?:我在|我就读于|我就讀於|学校是|學校是|就读于|就讀於)\s*({names})", message)
    if explicit:
        value = explicit.group(1).strip()
    else:
        full_name = re.search(r"(香港城市大学|香港城市大學|香港大学|香港大學|香港中文大学|香港中文大學|香港科技大学|香港科技大學|香港理工大学|香港理工大學|香港浸会大学|香港浸會大學|cityu|city university|hku|the university of hong kong)", message, re.I)
        value = full_name.group(1).strip() if full_name else None
    if not value:
        return None
    normalized = value.lower().replace(" ", "")
    if normalized in {"cityu", "cityuniversity"} or value in {"城大", "城市大学", "城市大學"}:
        return "香港城市大学"
    if normalized in {"hku", "theuniversityofhongkong"} or value in {"港大", "香港大學"}:
        return "香港大学"
    return value


def deterministic_agent(message: str) -> dict[str, Any]:
    school = get_school()
    mentioned_school = school_from_message(message)
    if mentioned_school:
        school = save_school(mentioned_school)
    for category, value, preference in extract_preferences(message):
        save_preference(category, value, preference)
    preferences = get_preferences()
    parsed = parse_message(message, school)
    if parsed["cuisine"] == "all" and preferences["likes"]:
        preferred_cuisine = next((value for value in preferences["likes"] if value in PREFERENCE_TERMS["cuisine"]), None)
        if preferred_cuisine:
            parsed["cuisine"] = preferred_cuisine
            parsed["food_query"] = preferred_cuisine
            parsed["understood"].append(f"沿用偏好 {preferred_cuisine}")
        elif preferences["likes"]:
            preferred_dish = next((value for value in preferences["likes"] if value not in PREFERENCE_TERMS["flavor"]), None)
            if preferred_dish:
                parsed["food_query"] = preferred_dish
                parsed["understood"].append(f"沿用偏好 {preferred_dish}")
    has_schedule = bool(list_courses())
    courses = courses_for_date(parsed["date"]) if has_schedule else []
    slots = get_free_slots(courses, parsed["duration"])
    after_class_time = max((course["end"] for course in courses), default=None)
    if parsed.get("after_class") and after_class_time:
        slots = [slot for slot in slots if parse_minutes(slot["start"]) >= parse_minutes(after_class_time)]
    meal_period = parsed["preferred_period"] or ("lunch" if any(slot["start"] < "14:00" for slot in slots) else "dinner")
    radius_m = 1000 if parsed.get("after_class") else 2500
    avoid = ", 避免 " + "、".join(preferences["dislikes"]) if preferences["dislikes"] else ""
    request_weekend = datetime.strptime(parsed["date"], "%Y-%m-%d").weekday() >= 5
    recommendations = search_restaurants(parsed["area"], parsed["budget"], parsed["cuisine"], meal_period, parsed.get("location_query"), (parsed.get("food_query") or "") + avoid, radius_m, school if parsed.get("after_class") else None, parsed.get("request_time"), request_weekend) if slots and parsed["area"] else []
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
    if parsed.get("after_class") and after_class_time and slots:
        answer = answer.replace("找到 ", f"{after_class_time} 下课后，找到 ", 1)
    return {"answer": answer + profile_hint, "parsed": parsed, "profile": {"school": school, "has_schedule": has_schedule, "preferences": preferences}, "result": {"date": parsed["date"], "weekday": weekday, "courses": courses, "afterClassTime": after_class_time if parsed.get("after_class") else None, "freeSlots": slots, "mealPeriod": meal_period, "recommendations": recommendations, "agentTrace": ["读取已记住的学校" if school else "未设置学校，使用通用推荐", "读取已记住的口味偏好", "解析自然语言需求", "调用 get_free_slots 查询课表空闲时间", "下课后按学校周边 1 公里范围搜索" if parsed.get("after_class") else "调用 search_restaurants 筛选餐厅", "按时段估计拥挤风险并排序"]}}


TOOLS = [
    {"type": "function", "function": {"name": "get_free_slots", "description": "查询指定日期的课程空闲时间，必须先调用此工具。", "parameters": {"type": "object", "properties": {"date": {"type": "string", "description": "YYYY-MM-DD"}, "duration": {"type": "integer", "description": "用餐分钟数"}}, "required": ["date", "duration"]}}},
    {"type": "function", "function": {"name": "search_restaurants", "description": "按照用户地点、预算、菜系或具体菜品搜索真实餐厅。", "parameters": {"type": "object", "properties": {"area": {"type": "string", "description": "自然语言地点"}, "budget": {"type": "integer"}, "cuisine": {"type": "string"}, "food_query": {"type": "string", "description": "用户提到的具体菜品，例如海鲜、炸鸡、海南鸡饭、乌冬面"}, "meal_period": {"type": "string", "enum": ["lunch", "dinner"]}}, "required": ["area", "budget", "cuisine", "meal_period"]}}},
]


def model_agent(message: str) -> dict[str, Any]:
    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        return deterministic_agent(message)
    base_url = os.getenv("MODEL_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("MODEL_NAME", "gpt-4o-mini")
    extract_preferences_with_model(message, api_key, base_url, model)
    local = deterministic_agent(message)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": f"你是香港课余就餐 Agent。本次请求使用的日期是 {local['parsed']['date']}。空闲时间范围固定为 08:00-23:00，直接扣除上课时间，不设置交通缓冲。用户学校是 {local.get('profile', {}).get('school', '未提供')}。用户长期口味偏好：喜欢 {', '.join(local.get('profile', {}).get('preferences', {}).get('likes', [])) or '暂无'}；不喜欢或忌口 {', '.join(local.get('profile', {}).get('preferences', {}).get('dislikes', [])) or '暂无'}。学校和课表是可选个性化信息，不得阻止普通餐厅推荐。必须先调用 get_free_slots，再调用 search_restaurants；只要有空档就必须继续搜索餐厅，不能只回答空档时间。用户说‘今天/明天/后天/周几’时，必须使用后端解析出的日期，不能自行猜测日期。用户说下课后去吃时，先读取当天课表并依据最后一节课结束时间，餐厅搜索范围限制为学校周边 1 公里。课表工具返回的课程必须视为当天真实课程，不能说当天没课，除非工具返回的课程列表确实为空。用户提到具体食物（例如海鲜、炸鸡、海南鸡饭、乌冬面）时，必须把它作为 food_query 传给 search_restaurants；用户说粤菜、川菜等时放入 cuisine。地点使用用户原话或已记住学校，不要把相对地点（学校旁边、校门口）原样传给搜索工具。只使用工具返回的数据，不要编造餐厅。最后用简洁中文回答，只概括空档和找到的餐厅数量，不要在文字中逐一列出餐厅、评分、价格或地址；具体餐厅列表由前端结果卡片展示。"},
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
                    answer = assistant.get("content") or local["answer"]
                    # Do not let a model hallucinate "no class" when the
                    # backend already found courses for the requested day.
                    if local["result"].get("courses") and re.search(r"没课|没有课|无课|没有安排课程", answer):
                        answer = local["answer"]
                    return {**local, "answer": answer, "result": {**state, "agentTrace": ["大模型理解自然语言需求", "模型选择并调用后端工具", "校验工具结果并生成回答"]}}
                for call in calls:
                    name = call["function"]["name"]
                    arguments = json.loads(call["function"].get("arguments", "{}"))
                    if name == "get_free_slots":
                        relative_date = bool(re.search(r"今天|明天|后天|(?:周|星期)[一二三四五六日天]", message))
                        tool_date = local["parsed"]["date"] if relative_date else arguments.get("date", local["parsed"]["date"])
                        value = get_free_slots(courses_for_date(tool_date) if list_courses() else [], int(arguments.get("duration", local["parsed"].get("duration", 60))))
                        state["freeSlots"] = value
                    elif name == "search_restaurants":
                        tool_area = str(arguments.get("area", "")).strip()
                        if re.fullmatch(r"学校|學校|校园|校園|学校旁边|學校旁邊|校门口|校門口|校园旁边|校園旁邊", tool_area):
                            tool_area = local.get("profile", {}).get("school") or tool_area
                        tool_cuisine = arguments.get("cuisine", "all")
                        if local["parsed"].get("cuisine") != "all":
                            tool_cuisine = local["parsed"]["cuisine"]
                        remembered_dislikes = local.get("profile", {}).get("preferences", {}).get("dislikes", [])
                        dislike_hint = ", 避免 " + "、".join(remembered_dislikes) if remembered_dislikes else ""
                        tool_food_query = (local["parsed"].get("food_query") or arguments.get("food_query") or "") + dislike_hint
                        request_weekend = datetime.strptime(local["parsed"]["date"], "%Y-%m-%d").weekday() >= 5
                        value = search_restaurants(tool_area, int(arguments.get("budget", local["parsed"].get("budget", 100))), tool_cuisine, arguments.get("meal_period", "lunch"), tool_area, tool_food_query, 1000 if local["parsed"].get("after_class") else 2500, local.get("profile", {}).get("school") if local["parsed"].get("after_class") else None, local["parsed"].get("request_time"), request_weekend)
                        state["recommendations"] = value
                    else:
                        value = {"error": "unknown tool"}
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(value, ensure_ascii=False)})
    except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError):
        return {**local, "result": {**local["result"], "agentTrace": ["大模型调用失败，切换本地工具工作流", *local["result"]["agentTrace"]]}}
    return local
