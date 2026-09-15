from datetime import date, datetime, timedelta
import os
from typing import Any

import httpx

from .data import RESTAURANTS, TIMETABLE, Course
from .schedule_store import courses_by_weekday


WEEKDAYS = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"]
RISK_SCORE = {"low": 0, "medium": 1, "high": 2}
QUEUE_SUMMARY = "工作日 12:00-14:00、18:00-20:00 可能需要排队，其余时间排队几率较小；周末 12:00-14:30、18:00-20:30 可能需要排队，其余时间排队几率较小。"
AREA_COORDINATES = {"HKU": (22.2840, 114.1378), "CityU": (22.3370, 114.1720), "Central": (22.2819, 114.1580), "Causeway Bay": (22.2803, 114.1849)}


def parse_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":", 1))
    return hour * 60 + minute


def clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def get_free_slots(courses: list[Course], duration: int = 60, buffer: int = 30) -> list[dict[str, Any]]:
    intervals = sorted((parse_minutes(item["start"]), parse_minutes(item["end"])) for item in courses)
    slots: list[dict[str, Any]] = []
    cursor, day_end = 8 * 60, 22 * 60
    for start, end in intervals:
        if start > cursor and start - buffer > cursor:
            slots.append({"start": clock(cursor), "end": clock(start - buffer), "minutes": start - buffer - cursor})
        cursor = max(cursor, end + buffer)
    if cursor < day_end:
        slots.append({"start": clock(cursor), "end": clock(day_end), "minutes": day_end - cursor})
    return [slot for slot in slots if slot["minutes"] >= max(30, duration)]


def search_restaurants(area: str, budget: int = 100, cuisine: str = "all", meal_period: str = "lunch", location_query: str | None = None, food_query: str | None = None) -> list[dict[str, Any]]:
    live_results = search_live_restaurants(area, cuisine, location_query, food_query)
    if live_results:
        return live_results
    matches = [item for item in RESTAURANTS if item["area"] == area and item["price"] <= budget and (cuisine == "all" or cuisine in item["cuisines"])]
    return [
        {**item, "risk": item["crowd"][meal_period], "queue_summary": QUEUE_SUMMARY, "queueSummary": QUEUE_SUMMARY, "match_reason": f"{item['note']} 人均 HK${item['price']}，步行约 {item['walk_minutes']} 分钟。", "walkMinutes": item["walk_minutes"], "matchReason": f"{item['note']} 人均 HK${item['price']}，步行约 {item['walk_minutes']} 分钟。"}
        for item in sorted(matches, key=lambda item: (RISK_SCORE[item["crowd"][meal_period]], item["walk_minutes"], -item["rating"]))[:5]
    ]


def search_live_restaurants(area: str, cuisine: str = "all", location_query: str | None = None, food_query: str | None = None) -> list[dict[str, Any]]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not location_query and not area:
        return []
    coordinates = AREA_COORDINATES.get(area)
    if not api_key:
        return []
    cuisine_query = f"{food_query} restaurants" if food_query else ("restaurants" if cuisine == "all" else f"{cuisine} restaurants")
    area_name = location_query or area
    request_body: dict[str, Any] = {"textQuery": f"{cuisine_query} near {area_name}", "languageCode": "zh-HK", "regionCode": "HK", "maxResultCount": 10}
    if coordinates:
        request_body["locationBias"] = {"circle": {"center": {"latitude": coordinates[0], "longitude": coordinates[1]}, "radius": 2500.0}}
    try:
        response = httpx.post("https://places.googleapis.com/v1/places:searchText", headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "places.id,places.displayName,places.primaryType,places.rating,places.formattedAddress,places.location,places.priceLevel,places.priceRange"}, json=request_body, timeout=12)
        response.raise_for_status()
        places = response.json().get("places", [])
    except (httpx.HTTPError, ValueError):
        return []
    normalized = []
    for place in places:
        name = place.get("displayName", {}).get("text")
        if not name:
            continue
        location = place.get("location", {})
        rating = place.get("rating")
        price_range = place.get("priceRange") or {}
        start_price = price_range.get("startPrice") or {}
        end_price = price_range.get("endPrice") or {}
        start_amount = start_price.get("units")
        end_amount = end_price.get("units")
        if start_amount is not None and end_amount is not None:
            price = round((float(start_amount) + float(end_amount)) / 2)
            price_label = f"约 HK${price}"
        else:
            price = 0
            price_label = {"PRICE_LEVEL_INEXPENSIVE": "价格较亲民", "PRICE_LEVEL_MODERATE": "中等价位", "PRICE_LEVEL_EXPENSIVE": "价格较高", "PRICE_LEVEL_VERY_EXPENSIVE": "高价"}.get(place.get("priceLevel"), "价格未提供")
        match_reason = f"真实地点结果：{place.get('formattedAddress', '地址待确认')}。评分 {rating if rating is not None else '暂无评分'} / 5。{price_label}。"
        normalized.append({"id": place.get("id", name), "name": name, "area": area, "cuisines": [cuisine] if cuisine != "all" else [place.get("primaryType", "餐厅")], "price": price, "price_label": price_label, "priceLabel": price_label, "walk_minutes": 0, "walkMinutes": 0, "rating": rating if isinstance(rating, (int, float)) else 0.0, "crowd": {"lunch": "medium", "dinner": "medium"}, "risk": "medium", "queue_summary": QUEUE_SUMMARY, "queueSummary": QUEUE_SUMMARY, "address": place.get("formattedAddress", "地址待确认"), "latitude": location.get("latitude"), "longitude": location.get("longitude"), "source": "Google Places", "match_reason": match_reason, "matchReason": match_reason})
    return normalized


def courses_for_date(date_text: str) -> list[Course]:
    chosen = datetime.strptime(date_text, "%Y-%m-%d").date()
    # Python Monday=0; the timetable uses Sunday=0.
    javascript_day = (chosen.weekday() + 1) % 7
    saved = courses_by_weekday(javascript_day)
    return saved if saved else TIMETABLE.get(javascript_day, [])


def local_date_from_message(message: str) -> str:
    today = date.today()
    if "后天" in message:
        return (today + timedelta(days=2)).isoformat()
    if "明天" in message:
        return (today + timedelta(days=1)).isoformat()
    if "今天" in message:
        return today.isoformat()
    weekday_terms = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 0, "天": 0}
    for term, target in weekday_terms.items():
        if f"周{term}" in message or f"星期{term}" in message:
            days = (target - ((today.weekday() + 1) % 7)) % 7 or 7
            return (today + timedelta(days=days)).isoformat()
    return today.isoformat()
