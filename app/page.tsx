'use client';

import { useEffect, useRef, useState } from 'react';
import type { CrowdRisk } from '../lib/data';
import type { ParsedRequest } from '../lib/parse-request';
import type { RecommendationResponse } from '../lib/recommend';

type AgentReply = { answer: string; parsed: ParsedRequest; result: RecommendationResponse };
type ChatMessage = { id: number; role: 'user' | 'assistant'; text: string; reply?: AgentReply };
type ScheduleCourse = { id: number; weekday: number; course_code: string; location: string; start_time: string; end_time: string };
const prompts = ['周三中午港大附近，预算100，想吃日料', '明天晚上在中环，预算120，菜系不限', '周五铜锣湾附近，想吃素食，不超过100'];
const riskLabel: Record<CrowdRisk, string> = { low: '低排队风险', medium: '中等排队风险', high: '高排队风险' };
const weekdayLabels = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
const apiUrl = (path: string) => `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}${path}`;

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([{ id: 1, role: 'assistant', text: '你好，我是 HK Recommend。你可以直接告诉我时间、地点、预算和菜系，我会帮你找餐厅。你也可以告诉我就读学校并导入课表，我会记住这些信息，之后结合你的课余时间推荐。' }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduleTab, setScheduleTab] = useState<'manual' | 'csv'>('manual');
  const [courses, setCourses] = useState<ScheduleCourse[]>([]);
  const [scheduleMessage, setScheduleMessage] = useState('');
  const [manual, setManual] = useState({ weekday: '1', course_code: '', location: '', start_time: '09:00', end_time: '11:00' });
  const [csvText, setCsvText] = useState('weekday,course_code,location,start_time,end_time\n1,COMP701,HKU Main Building,09:00,11:00');
  const nextId = useRef(2);
  const conversationRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(apiUrl('/api/profile')).then((response) => response.json()).then((profile) => {
      if (profile.school) {
        setMessages([{ id: 1, role: 'assistant', text: profile.has_schedule ? `欢迎回来，我记得你就读于 ${profile.school}，课表也已经准备好了。告诉我你什么时候、在哪里想吃饭吧。` : `欢迎回来，我记得你就读于 ${profile.school}。先在左侧导入课表，我就能根据你的真实空闲时间推荐餐厅。` }]);
      }
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    const conversation = conversationRef.current;
    if (!conversation) return;
    conversation.scrollTo({ top: conversation.scrollHeight, behavior: 'smooth' });
  }, [messages, loading]);

  async function send(text = input) {
    const message = text.trim();
    if (!message || loading) return;
    setMessages((current) => [...current, { id: nextId.current++, role: 'user', text: message }]);
    setInput(''); setLoading(true);
    try {
      const response = await fetch(apiUrl('/api/chat'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || '请求失败');
      setMessages((current) => [...current, { id: nextId.current++, role: 'assistant', text: payload.answer, reply: payload.parsed && payload.result ? payload : undefined }]);
    } catch (error) {
      setMessages((current) => [...current, { id: nextId.current++, role: 'assistant', text: error instanceof Error ? error.message : '连接失败，请稍后再试。' }]);
    } finally { setLoading(false); }
  }

  async function openSchedule() {
    setScheduleOpen(true); setScheduleMessage('');
    try { const response = await fetch(apiUrl('/api/schedule')); const payload = await response.json(); setCourses(payload.courses || []); }
    catch { setScheduleMessage('无法连接课表服务，请先启动 FastAPI。'); }
  }

  async function addManual(event: React.FormEvent) {
    event.preventDefault(); setScheduleMessage('');
    try {
      const response = await fetch(apiUrl('/api/schedule/manual'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...manual, weekday: Number(manual.weekday) }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || '添加失败');
      setCourses((current) => [...current, payload.course].sort((a, b) => a.weekday - b.weekday || a.start_time.localeCompare(b.start_time)));
      setManual((current) => ({ ...current, course_code: '', location: '' })); setScheduleMessage('课程已添加');
    } catch (error) { setScheduleMessage(error instanceof Error ? error.message : '添加失败'); }
  }

  async function importCsv(event: React.FormEvent) {
    event.preventDefault(); setScheduleMessage('');
    try {
      const response = await fetch(apiUrl('/api/schedule/csv'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ csv_text: csvText }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || '导入失败');
      setCourses((current) => [...current, ...(payload.courses || [])]); setScheduleMessage(`成功导入 ${payload.courses?.length || 0} 门课程`);
    } catch (error) { setScheduleMessage(error instanceof Error ? error.message : '导入失败'); }
  }

  async function readCsvFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setCsvText(await file.text());
    setScheduleMessage(`已载入文件：${file.name}`);
  }

  async function removeCourse(id: number) {
    const response = await fetch(apiUrl(`/api/schedule/${id}`), { method: 'DELETE' });
    if (response.ok) setCourses((current) => current.filter((course) => course.id !== id));
  }

  return <main className="app-shell">
    <aside className="sidebar"><div><div className="brand-mark">HK</div><h1>HK Recommend</h1><p>课余就餐 Agent</p></div><div className="agent-status"><span />本地工具已连接</div><button className="schedule-button" onClick={openSchedule}>课表设置 <span>+</span></button><div className="side-note"><strong>当前能力</strong><p>读取你的课表<br />计算空闲时间<br />筛选香港餐厅<br />估计排队风险</p></div><footer>Agent MVP · v0.3</footer></aside>
    <section className="chat-panel">
      <header className="chat-header"><div><h2>去哪吃助手</h2><p>用自然语言告诉我你的需求</p></div><button className="clear-button" onClick={() => setMessages((current) => current.slice(0, 1))}>清空对话</button></header>
      <div className="conversation" ref={conversationRef}>
        {messages.map((message) => <article className={`message-row ${message.role}`} key={message.id}><div className="avatar">{message.role === 'assistant' ? 'AI' : '你'}</div><div className="message-content"><div className="bubble">{message.text}</div>{message.reply && <AgentResult reply={message.reply} />}</div></article>)}
        {loading && <article className="message-row assistant"><div className="avatar">AI</div><div className="typing"><i /><i /><i /></div></article>}
      </div>
      <div className="composer-area">
        {messages.length === 1 && <div className="suggestions">{prompts.map((prompt) => <button key={prompt} onClick={() => send(prompt)}>{prompt}</button>)}</div>}
        <div className="composer"><textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder="例如：周三中午在港大附近，预算 100，想吃日料…" rows={1} /><button className="send-button" disabled={!input.trim() || loading} onClick={() => send()}>发送</button></div>
        <p className="composer-note">排队风险来自演示数据，不代表实时情况。</p>
      </div>
    </section>
    {scheduleOpen && <div className="modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget) setScheduleOpen(false); }}><section className="schedule-modal" role="dialog" aria-modal="true" aria-labelledby="schedule-title"><header><div><p className="eyebrow dark">SCHEDULE</p><h2 id="schedule-title">管理我的课表</h2></div><button className="modal-close" onClick={() => setScheduleOpen(false)} aria-label="关闭">×</button></header><div className="tabs"><button className={scheduleTab === 'manual' ? 'active' : ''} onClick={() => setScheduleTab('manual')}>手动添加</button><button className={scheduleTab === 'csv' ? 'active' : ''} onClick={() => setScheduleTab('csv')}>导入 CSV</button></div>{scheduleTab === 'manual' ? <form className="schedule-form" onSubmit={addManual}><div className="field"><label htmlFor="weekday">星期</label><select id="weekday" value={manual.weekday} onChange={(event) => setManual({ ...manual, weekday: event.target.value })}>{weekdayLabels.map((label, index) => <option value={index} key={label}>{label}</option>)}</select></div><div className="field"><label htmlFor="course-code">课程代号</label><input id="course-code" placeholder="例如 COMP701" value={manual.course_code} onChange={(event) => setManual({ ...manual, course_code: event.target.value })} required /></div><div className="field"><label htmlFor="location">上课地点</label><input id="location" placeholder="例如 Main Building" value={manual.location} onChange={(event) => setManual({ ...manual, location: event.target.value })} required /></div><div className="split-fields"><div className="field"><label htmlFor="start">开始时间</label><input id="start" type="time" value={manual.start_time} onChange={(event) => setManual({ ...manual, start_time: event.target.value })} required /></div><div className="field"><label htmlFor="end">结束时间</label><input id="end" type="time" value={manual.end_time} onChange={(event) => setManual({ ...manual, end_time: event.target.value })} required /></div></div><button className="primary-button" type="submit">添加课程 <span>→</span></button></form> : <form className="schedule-form" onSubmit={importCsv}><p className="csv-hint">表头支持：`weekday,course_code,location,start_time,end_time`。星期使用 0-6，0 是星期日。</p><input className="csv-file" type="file" accept=".csv,text/csv" onChange={readCsvFile} /><textarea className="csv-input" value={csvText} onChange={(event) => setCsvText(event.target.value)} rows={6} /><button className="primary-button" type="submit">导入 CSV <span>→</span></button></form>}{scheduleMessage && <p className="schedule-message">{scheduleMessage}</p>}<div className="course-list"><div className="list-heading"><h3>已保存课程</h3><span>{courses.length} 门</span></div>{courses.length ? courses.map((course) => <div className="course-row" key={course.id}><div><b>{course.course_code}</b><span>{weekdayLabels[course.weekday]} · {course.start_time}-{course.end_time}</span><small>{course.location}</small></div><button onClick={() => removeCourse(course.id)} aria-label={`删除 ${course.course_code}`}>删除</button></div>) : <p className="empty-course">还没有手动导入的课程。未导入时 Agent 会使用示例课表。</p>}</div></section></div>}
  </main>;
}

function AgentResult({ reply }: { reply: AgentReply }) {
  const { result, parsed } = reply;
  return <div className="agent-result"><div className="understood"><span>我理解的条件</span><div>{parsed.understood.map((item) => <b key={item}>{item}</b>)}</div></div>
    <section><div className="result-title"><h3>可用时间</h3><span>{result.weekday}</span></div><div className="slots">{result.freeSlots.map((slot) => <span key={`${slot.start}-${slot.end}`}>{slot.start} - {slot.end}</span>)}</div></section>
    {!!result.recommendations.length && <section><div className="result-title"><h3>推荐餐厅</h3><span>{result.recommendations.length} 个结果</span></div><div className="restaurant-list">{result.recommendations.map((restaurant, index) => <article className="restaurant" key={restaurant.id}><div className="rank">{String(index + 1).padStart(2, '0')}</div><div className="restaurant-main"><div className="restaurant-head"><div><h4>{restaurant.name}</h4><p>{restaurant.cuisines.join(' · ')} · {restaurant.priceLabel ?? `人均 HK$${restaurant.price}`}</p></div><span className={`risk ${restaurant.risk}`}>{riskLabel[restaurant.risk]}</span></div><p className="reason">{restaurant.note}</p><div className="restaurant-meta"><span>评分 {restaurant.rating.toFixed(1)}</span><span>步行约 {restaurant.walkMinutes} 分钟</span></div></div></article>)}</div></section>}
    <details><summary>查看 Agent 的工具调用过程</summary><ol>{result.agentTrace.map((step) => <li key={step}>{step}</li>)}</ol></details>
  </div>;
}
