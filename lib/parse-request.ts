import type { MealPeriod } from './data';
import type { RecommendationRequest } from './recommend';

export type ParsedRequest = RecommendationRequest & { understood: string[] };

function localDateString(date: Date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function nextWeekday(target: number, now: Date) {
  const date = new Date(now);
  let days = (target - date.getDay() + 7) % 7;
  if (days === 0) days = 7;
  date.setDate(date.getDate() + days);
  return localDateString(date);
}

function parseDate(message: string, now: Date) {
  const iso = message.match(/\b(20\d{2}-\d{1,2}-\d{1,2})\b/);
  if (iso) return iso[1].split('-').map((part, index) => index ? part.padStart(2, '0') : part).join('-');
  const monthDay = message.match(/(\d{1,2})月(\d{1,2})[日号]?/);
  if (monthDay) return `${now.getFullYear()}-${monthDay[1].padStart(2, '0')}-${monthDay[2].padStart(2, '0')}`;
  const relativeDays = message.includes('后天') ? 2 : message.includes('明天') ? 1 : message.includes('今天') ? 0 : null;
  if (relativeDays !== null) { const date = new Date(now); date.setDate(date.getDate() + relativeDays); return localDateString(date); }
  const weekdays: Array<[RegExp, number]> = [[/(?:周|星期)一/, 1], [/(?:周|星期)二/, 2], [/(?:周|星期)三/, 3], [/(?:周|星期)四/, 4], [/(?:周|星期)五/, 5], [/(?:周|星期)六/, 6], [/(?:周日|周天|星期日|星期天)/, 0]];
  const matched = weekdays.find(([pattern]) => pattern.test(message));
  return matched ? nextWeekday(matched[1], now) : localDateString(now);
}

export function parseRecommendationRequest(message: string, now = new Date()): ParsedRequest {
  const locationMatch = message.match(/(?:在|去|位于|位於)\s*([^，。,.！!；;\n]{2,60}?)(?:附近|一带|一帶|吃|用餐|$)/);
  const area = locationMatch?.[1]?.trim() || '';
  const cuisine = /日料|日本菜|寿司|壽司/.test(message) ? '日料' : /粤菜|粵菜|港式|茶餐厅|茶餐廳/.test(message) ? '粤菜' : /西餐/.test(message) ? '西餐' : /东南亚|東南亞|泰国|泰國|越南/.test(message) ? '东南亚' : /素食|斋|齋/.test(message) ? '素食' : 'all';
  const budgetMatch = message.match(/(?:预算|預算|人均|最多|不超过|不超過|以内|以內)[^\d]{0,6}(\d{2,4})/i) ?? message.match(/(\d{2,4})\s*(?:港币|港幣|hkd|元|块|塊)/i);
  const minuteMatch = message.match(/(\d{2,3})\s*(?:分钟|分鐘|min)/i);
  const hourMatch = message.match(/(\d(?:\.\d+)?)\s*(?:小时|小時)/);
  const preferredPeriod: MealPeriod | undefined = /晚餐|晚上|傍晚/.test(message) ? 'dinner' : /午餐|中午/.test(message) ? 'lunch' : undefined;
  const budget = budgetMatch ? Number(budgetMatch[1]) : 100;
  const duration = minuteMatch ? Number(minuteMatch[1]) : hourMatch ? Math.round(Number(hourMatch[1]) * 60) : 60;
  const date = parseDate(message, now);
  const areaName = area || '未指定';
  const understood = [`日期 ${date}`, `地点 ${areaName}`, `预算 HK$${budget}`, `用餐 ${duration} 分钟`, cuisine === 'all' ? '菜系不限' : `菜系 ${cuisine}`];
  if (preferredPeriod) understood.push(preferredPeriod === 'lunch' ? '午餐时段' : '晚餐时段');
  return { date, area, budget, cuisine, duration, preferredPeriod, understood };
}
