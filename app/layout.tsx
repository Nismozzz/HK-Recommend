import type { Metadata } from 'next';
import './globals.css';
import './schedule.css';

export const metadata: Metadata = { title: 'HK Recommend · 课余去哪吃？', description: '根据课表、地点和排队风险寻找香港餐厅' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
