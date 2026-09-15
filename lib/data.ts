export type MealPeriod = 'lunch' | 'dinner';
export type CrowdRisk = 'low' | 'medium' | 'high';

export type Course = { start: string; end: string; name: string };

export type Restaurant = {
  id: string; name: string; area: string; cuisines: string[]; price: number;
  priceLabel?: string; queueSummary?: string; walkMinutes: number; rating: number; crowd: Record<MealPeriod, CrowdRisk>; note: string;
};

// Sunday is 0, matching JavaScript Date.getDay(). Replace this with an import later.
export const timetable: Record<number, Course[]> = {
  0: [],
  1: [
    { name: 'Machine Learning', start: '09:00', end: '11:00' },
    { name: 'Research Methods', start: '14:00', end: '16:00' }
  ],
  2: [{ name: 'Data Mining', start: '10:00', end: '12:00' }],
  3: [
    { name: 'Deep Learning', start: '09:00', end: '12:00' },
    { name: 'Seminar', start: '15:00', end: '17:00' }
  ],
  4: [{ name: 'NLP', start: '13:00', end: '15:00' }],
  5: [{ name: 'Project Workshop', start: '10:00', end: '12:00' }],
  6: []
};

export const restaurants: Restaurant[] = [
  { id: 'hku-tea-house', name: '港大新茶記', area: 'HKU', cuisines: ['粤菜'], price: 65, walkMinutes: 8, rating: 4.2, crowd: { lunch: 'medium', dinner: 'low' }, note: '離校園近，適合課間快速用餐。' },
  { id: 'mountain-sushi', name: '山道日食', area: 'HKU', cuisines: ['日料'], price: 95, walkMinutes: 12, rating: 4.4, crowd: { lunch: 'low', dinner: 'medium' }, note: '午餐時段翻台較快，預算內可選。' },
  { id: 'pokfulam-green-bowl', name: '薄扶林綠碗', area: 'HKU', cuisines: ['素食', '東南亞'], price: 88, walkMinutes: 15, rating: 4.3, crowd: { lunch: 'low', dinner: 'low' }, note: '素食與東南亞選擇，通常不用久等。' },
  { id: 'kowloon-tong-sushi', name: '九龍塘日和', area: 'CityU', cuisines: ['日料'], price: 98, walkMinutes: 8, rating: 4.3, crowd: { lunch: 'low', dinner: 'medium' }, note: '鄰近城大與九龍塘站，適合下課後用餐。' },
  { id: 'festival-walk-kitchen', name: '又一城小館', area: 'CityU', cuisines: ['粤菜', '西餐'], price: 90, walkMinutes: 6, rating: 4.2, crowd: { lunch: 'medium', dinner: 'medium' }, note: '又一城內選擇多，預算內方便快速用餐。' },
  { id: 'central-hainan', name: '中環海南站', area: 'Central', cuisines: ['東南亞'], price: 82, walkMinutes: 7, rating: 4.1, crowd: { lunch: 'high', dinner: 'low' }, note: '晚餐較從容；工作日午餐可能較擁擠。' },
  { id: 'stone-slab-kitchen', name: '石板街小館', area: 'Central', cuisines: ['粤菜'], price: 110, walkMinutes: 10, rating: 4.5, crowd: { lunch: 'medium', dinner: 'medium' }, note: '菜式選擇多，適合想吃熱菜的日子。' },
  { id: 'causeway-hiyori', name: '銅鑼灣小日和', area: 'Causeway Bay', cuisines: ['日料'], price: 125, walkMinutes: 6, rating: 4.6, crowd: { lunch: 'medium', dinner: 'high' }, note: '位置方便，但晚餐熱門時段排隊風險較高。' },
  { id: 'victoria-park-table', name: '維園餐桌', area: 'Causeway Bay', cuisines: ['西餐', '素食'], price: 98, walkMinutes: 11, rating: 4.2, crowd: { lunch: 'low', dinner: 'medium' }, note: '有素食選項，午餐較容易找到座位。' }
];

export const areas = [
  { value: 'HKU', label: '香港大学' },
  { value: 'CityU', label: '香港城市大学' },
  { value: 'Central', label: '中环' },
  { value: 'Causeway Bay', label: '铜锣湾' }
];

export const cuisines = ['粤菜', '日料', '乌冬面', '西餐', '东南亚', '素食'];
