from typing import TypedDict


class Course(TypedDict, total=False):
    name: str
    start: str
    end: str


class Restaurant(TypedDict):
    id: str
    name: str
    area: str
    cuisines: list[str]
    price: int
    walk_minutes: int
    rating: float
    crowd: dict[str, str]
    note: str


TIMETABLE: dict[int, list[Course]] = {
    0: [],
    1: [
        {"name": "Machine Learning", "start": "09:00", "end": "11:00"},
        {"name": "Research Methods", "start": "14:00", "end": "16:00"},
    ],
    2: [{"name": "Data Mining", "start": "10:00", "end": "12:00"}],
    3: [
        {"name": "Deep Learning", "start": "09:00", "end": "12:00"},
        {"name": "Seminar", "start": "15:00", "end": "17:00"},
    ],
    4: [{"name": "NLP", "start": "13:00", "end": "15:00"}],
    5: [{"name": "Project Workshop", "start": "10:00", "end": "12:00"}],
    6: [],
}

RESTAURANTS: list[Restaurant] = [
    {"id": "hku-tea-house", "name": "港大新茶記", "area": "HKU", "cuisines": ["粤菜"], "price": 65, "walk_minutes": 8, "rating": 4.2, "crowd": {"lunch": "medium", "dinner": "low"}, "note": "離校園近，適合課間快速用餐。"},
    {"id": "mountain-sushi", "name": "山道日食", "area": "HKU", "cuisines": ["日料"], "price": 95, "walk_minutes": 12, "rating": 4.4, "crowd": {"lunch": "low", "dinner": "medium"}, "note": "午餐時段翻台較快，預算內可選。"},
    {"id": "pokfulam-green-bowl", "name": "薄扶林綠碗", "area": "HKU", "cuisines": ["素食", "東南亞"], "price": 88, "walk_minutes": 15, "rating": 4.3, "crowd": {"lunch": "low", "dinner": "low"}, "note": "素食與東南亞選擇，通常不用久等。"},
    {"id": "kowloon-tong-sushi", "name": "九龍塘日和", "area": "CityU", "cuisines": ["日料"], "price": 98, "walk_minutes": 8, "rating": 4.3, "crowd": {"lunch": "low", "dinner": "medium"}, "note": "鄰近城大與九龍塘站，適合下課後用餐。"},
    {"id": "festival-walk-kitchen", "name": "又一城小館", "area": "CityU", "cuisines": ["粤菜", "西餐"], "price": 90, "walk_minutes": 6, "rating": 4.2, "crowd": {"lunch": "medium", "dinner": "medium"}, "note": "又一城內選擇多，預算內方便快速用餐。"},
    {"id": "central-hainan", "name": "中環海南站", "area": "Central", "cuisines": ["東南亞"], "price": 82, "walk_minutes": 7, "rating": 4.1, "crowd": {"lunch": "high", "dinner": "low"}, "note": "晚餐較從容；工作日午餐可能較擁擠。"},
    {"id": "stone-slab-kitchen", "name": "石板街小館", "area": "Central", "cuisines": ["粤菜"], "price": 110, "walk_minutes": 10, "rating": 4.5, "crowd": {"lunch": "medium", "dinner": "medium"}, "note": "菜式選擇多，適合想吃熱菜的日子。"},
    {"id": "causeway-hiyori", "name": "銅鑼灣小日和", "area": "Causeway Bay", "cuisines": ["日料"], "price": 125, "walk_minutes": 6, "rating": 4.6, "crowd": {"lunch": "medium", "dinner": "high"}, "note": "位置方便，但晚餐熱門時段排隊風險較高。"},
    {"id": "victoria-park-table", "name": "維園餐桌", "area": "Causeway Bay", "cuisines": ["西餐", "素食"], "price": 98, "walk_minutes": 11, "rating": 4.2, "crowd": {"lunch": "low", "dinner": "medium"}, "note": "有素食選項，午餐較容易找到座位。"},
]
