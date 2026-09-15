import { NextResponse } from 'next/server';
import { parseRecommendationRequest } from '../../../lib/parse-request';
import { runRecommendationAgent } from '../../../lib/recommend';

export async function POST(request: Request) {
  try {
    const body = await request.json() as { message?: string };
    const message = body.message?.trim();
    if (!message) return NextResponse.json({ error: '请告诉我你什么时候、在哪里想吃饭' }, { status: 400 });
    const parsed = parseRecommendationRequest(message);
    const result = runRecommendationAgent(parsed);
    const answer = !parsed.area
      ? '我找到了可用时间段，但还不知道你想去哪里。请告诉我地标、商场、车站或街道，我会用 Google Maps 查找附近餐厅。'
      : result.freeSlots.length === 0
      ? `我查了${result.weekday}的课表，没有找到满足 ${parsed.duration} 分钟用餐需求的空闲时段。你可以换一天或缩短用餐时间。`
      : result.recommendations.length === 0
        ? `我找到了 ${result.freeSlots.length} 个可用时间段，但暂时没有符合预算和菜系要求的餐厅。可以放宽预算或告诉我“菜系不限”。`
        : `我查了${result.weekday}的课表，找到 ${result.freeSlots.length} 个可用时间段，并按距离、预算和排队风险选出了 ${result.recommendations.length} 家餐厅。`;
    return NextResponse.json({ answer, parsed, result });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : 'Agent 暂时无法处理这个请求' }, { status: 400 });
  }
}
