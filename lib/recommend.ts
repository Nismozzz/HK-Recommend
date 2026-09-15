import { restaurants, timetable, type Course, type CrowdRisk, type MealPeriod, type Restaurant } from './data';

export type TimeSlot = { start: string; end: string; minutes: number };
export type RecommendationRequest = { date: string; area: string; budget: number; cuisine: string; foodQuery?: string; dishes?: string[]; duration: number; preferredPeriod?: MealPeriod };
export type RecommendationResponse = {
  date: string; weekday: string; courses: Course[]; freeSlots: TimeSlot[]; mealPeriod: MealPeriod;
  recommendations: Array<Restaurant & { risk: CrowdRisk; matchReason: string }>; agentTrace: string[];
};

const weekdayNames = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
const riskScore: Record<CrowdRisk, number> = { low: 0, medium: 1, high: 2 };
const toMinutes = (value: string) => { const [hour, minute] = value.split(':').map(Number); return hour * 60 + minute; };
const toClock = (value: number) => `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;

export function getFreeSlots(courses: Course[], dayStart = 8 * 60, dayEnd = 22 * 60, buffer = 30): TimeSlot[] {
  const intervals = courses.map((course) => [toMinutes(course.start), toMinutes(course.end)] as const).sort((a, b) => a[0] - b[0]);
  const slots: TimeSlot[] = [];
  let cursor = dayStart;
  for (const [start, end] of intervals) {
    if (start > cursor) {
      const endWithBuffer = start - buffer;
      if (endWithBuffer > cursor) slots.push({ start: toClock(cursor), end: toClock(endWithBuffer), minutes: endWithBuffer - cursor });
    }
    cursor = Math.max(cursor, end + buffer);
  }
  if (cursor < dayEnd) slots.push({ start: toClock(cursor), end: toClock(dayEnd), minutes: dayEnd - cursor });
  return slots;
}

function chooseMealPeriod(slots: TimeSlot[]): MealPeriod {
  const lunchMinutes = slots.reduce((total, slot) => total + Math.max(0, Math.min(toMinutes(slot.end), 14 * 60) - Math.max(toMinutes(slot.start), 11 * 60)), 0);
  return lunchMinutes > 0 ? 'lunch' : 'dinner';
}

export function runRecommendationAgent(input: RecommendationRequest): RecommendationResponse {
  const date = new Date(`${input.date}T12:00:00`);
  if (Number.isNaN(date.getTime())) throw new Error('日期格式无效');
  const courses = timetable[date.getDay()] ?? [];
  const allSlots = getFreeSlots(courses);
  const freeSlots = allSlots.filter((slot) => slot.minutes >= Math.max(30, input.duration));
  const mealPeriod = input.preferredPeriod ?? chooseMealPeriod(freeSlots);
  const agentTrace = ['读取指定日期的课表', '计算 08:00-22:00 空闲时间，并预留 30 分钟缓冲', `筛选地点=${input.area}、预算≤HK$${input.budget}${input.cuisine === 'all' ? '' : `、菜系=${input.cuisine}`}`, `按${mealPeriod === 'lunch' ? '午餐' : '晚餐'}时段估计拥挤风险并排序`];
  const recommendations = freeSlots.length === 0 ? [] : restaurants
    .filter((restaurant) => restaurant.area === input.area && restaurant.price <= input.budget && (input.cuisine === 'all' || restaurant.cuisines.includes(input.cuisine)))
    .map((restaurant) => ({ ...restaurant, risk: restaurant.crowd[mealPeriod], matchReason: `${restaurant.note} 人均 HK$${restaurant.price}，步行约 ${restaurant.walkMinutes} 分钟。` }))
    .sort((a, b) => riskScore[a.risk] - riskScore[b.risk] || a.walkMinutes - b.walkMinutes || b.rating - a.rating).slice(0, 5);
  return { date: input.date, weekday: weekdayNames[date.getDay()], courses, freeSlots, mealPeriod, recommendations, agentTrace };
}
