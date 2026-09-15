import { NextResponse } from 'next/server';
import { runRecommendationAgent, type RecommendationRequest } from '../../../lib/recommend';

export async function POST(request: Request) {
  try {
    const body = await request.json() as Partial<RecommendationRequest>;
    if (!body.date || !body.area) return NextResponse.json({ error: '请提供日期和活动地点' }, { status: 400 });
    const input: RecommendationRequest = { date: body.date, area: body.area, budget: Number.isFinite(body.budget) ? Number(body.budget) : 100, cuisine: body.cuisine || 'all', duration: Number.isFinite(body.duration) ? Number(body.duration) : 60 };
    return NextResponse.json(runRecommendationAgent(input));
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : '推荐服务暂时不可用' }, { status: 400 });
  }
}
