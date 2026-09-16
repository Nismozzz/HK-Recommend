from datetime import date, datetime, timedelta
import os
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .schedule_store import Course, courses_by_weekday


WEEKDAYS = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"]
QUEUE_SUMMARY = "工作日 12:00-14:00、18:00-20:00 可能需要排队，其余时间排队几率较小；周末 12:00-14:30、18:00-20:30 可能需要排队，其余时间排队几率较小。"
AREA_COORDINATES = {"HKU": (22.2840, 114.1378), "CityU": (22.3370, 114.1720), "Central": (22.2819, 114.1580), "Causeway Bay": (22.2803, 114.1849)}


def parse_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":", 1))
    return hour * 60 + minute


def clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def get_free_slots(courses: list[Course], duration: int = 60) -> list[dict[str, Any]]:
    intervals = sorted((parse_minutes(item["start"]), parse_minutes(item["end"])) for item in courses)
    slots: list[dict[str, Any]] = []
    cursor, day_end = 8 * 60, 23 * 60
    for start, end in intervals:
        if start > cursor:
            slots.append({"start": clock(cursor), "end": clock(start), "minutes": start - cursor})
        cursor = max(cursor, end)
    if cursor < day_end:
        slots.append({"start": clock(cursor), "end": clock(day_end), "minutes": day_end - cursor})
    return [slot for slot in slots if slot["minutes"] >= max(30, duration)]


def search_restaurants(area: str, budget: int = 100, cuisine: str = "all", meal_period: str = "lunch", location_query: str | None = None, food_query: str | None = None, radius_m: int = 2500, origin_area: str | None = None, request_time: str | None = None, weekend: bool = False) -> list[dict[str, Any]]:
    return search_live_restaurants(area, cuisine, location_query, food_query, radius_m, origin_area, request_time, weekend)


def search_live_restaurants(area: str, cuisine: str = "all", location_query: str | None = None, food_query: str | None = None, radius_m: int = 2500, origin_area: str | None = None, request_time: str | None = None, weekend: bool = False) -> list[dict[str, Any]]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not location_query and not area:
        return []
    coordinates = AREA_COORDINATES.get(origin_area or area) or AREA_COORDINATES.get({"香港城市大学": "CityU", "香港城市大學": "CityU", "香港大学": "HKU", "香港大學": "HKU"}.get(origin_area or area, ""))
    if not api_key:
        return []
    cuisine_query = f"{food_query} restaurants" if food_query else ("restaurants" if cuisine == "all" else f"{cuisine} restaurants")
    area_name = location_query or area
    request_body: dict[str, Any] = {"textQuery": f"{cuisine_query} near {area_name}", "languageCode": "zh-HK", "regionCode": "HK", "maxResultCount": 10}
    if coordinates:
        request_body["locationBias"] = {"circle": {"center": {"latitude": coordinates[0], "longitude": coordinates[1]}, "radius": float(radius_m)}}
    try:
        response = httpx.post("https://places.googleapis.com/v1/places:searchText", headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "places.id,places.displayName,places.primaryType,places.rating,places.formattedAddress,places.location,places.priceLevel,places.priceRange,places.currentOpeningHours,places.regularOpeningHours"}, json=request_body, timeout=12)
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
        opening = place.get("currentOpeningHours") or {}
        open_now = opening.get("openNow")
        risk, queue_summary = queue_risk(request_time, weekend)
        normalized.append({"id": place.get("id", name), "name": name, "area": area, "cuisines": [cuisine] if cuisine != "all" else [place.get("primaryType", "餐厅")], "price": price, "price_label": price_label, "priceLabel": price_label, "walk_minutes": 0, "walkMinutes": 0, "rating": rating if isinstance(rating, (int, float)) else 0.0, "crowd": {"lunch": risk, "dinner": risk}, "risk": risk, "queue_summary": queue_summary, "queueSummary": queue_summary, "open_now": open_now if isinstance(open_now, bool) else None, "openNow": open_now if isinstance(open_now, bool) else None, "opening_status": "营业中" if open_now is True else "目前休息" if open_now is False else "营业状态未知", "openingStatus": "营业中" if open_now is True else "目前休息" if open_now is False else "营业状态未知", "data_updated_at": datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat(timespec="minutes"), "dataUpdatedAt": datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat(timespec="minutes"), "address": place.get("formattedAddress", "地址待确认"), "latitude": location.get("latitude"), "longitude": location.get("longitude"), "source": "Google Places", "match_reason": match_reason, "matchReason": match_reason})
    origin = location_query or origin_area or area
    add_distances(normalized, origin, api_key)
    return normalized


def queue_risk(request_time: str | None, weekend: bool = False) -> tuple[str, str]:
    if not request_time:
        return "medium", "当前时间未明确，午餐/晚餐高峰可能需要排队。"
    minutes = parse_minutes(request_time)
    lunch_peak = (12 * 60, 14 * 60 + (30 if weekend else 0))
    dinner_peak = (18 * 60, 20 * 60 + (30 if weekend else 0))
    if lunch_peak[0] <= minutes <= lunch_peak[1] or dinner_peak[0] <= minutes <= dinner_peak[1]:
        return "high", "该时间处于用餐高峰，排队概率较高。"
    return "low", "该时间不在主要用餐高峰，排队风险较低。"


def add_distances(restaurants: list[dict[str, Any]], origin: str, api_key: str) -> None:
    destinations = [
        f"{item['latitude']},{item['longitude']}"
        for item in restaurants
        if isinstance(item.get("latitude"), (int, float)) and isinstance(item.get("longitude"), (int, float))
    ]
    if not destinations:
        return
    try:
        response = httpx.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params={"origins": origin, "destinations": "|".join(destinations), "mode": "walking", "language": "zh-TW", "key": api_key},
            timeout=12,
        )
        response.raise_for_status()
        rows = response.json().get("rows", [])
        elements = rows[0].get("elements", []) if rows else []
    except (httpx.HTTPError, ValueError, IndexError, TypeError):
        return
    distance_index = 0
    for item in restaurants:
        if not (isinstance(item.get("latitude"), (int, float)) and isinstance(item.get("longitude"), (int, float))):
            continue
        element = elements[distance_index] if distance_index < len(elements) else {}
        distance_index += 1
        if element.get("status") != "OK":
            continue
        distance = element.get("distance") or {}
        if isinstance(distance.get("value"), (int, float)):
            item["distance_meters"] = distance["value"]
            item["distanceMeters"] = distance["value"]
        if distance.get("text"):
            item["distance_text"] = distance["text"]
            item["distanceText"] = distance["text"]


def courses_for_date(date_text: str) -> list[Course]:
    chosen = datetime.strptime(date_text, "%Y-%m-%d").date()
    javascript_day = (chosen.weekday() + 1) % 7
    return courses_by_weekday(javascript_day)


def local_date_from_message(message: str) -> str:
    today = datetime.now(ZoneInfo("Asia/Hong_Kong")).date()
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
