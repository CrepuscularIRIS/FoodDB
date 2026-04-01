import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: '乳制品供应链风险研判智能体',
  description: '基于知识驱动与规则增强的乳制品供应链风险研判系统',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  乳制品供应链风险研判智能体
                </h1>
                <p className="text-sm text-gray-500 mt-1">
                  知识驱动 · 规则增强 · 可解释 · 可演示
                </p>
              </div>
              <div className="flex items-center space-x-4">
                <nav className="flex items-center space-x-4 mr-4">
                  <Link
                    href="/"
                    className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    首页
                  </Link>
                  <Link
                    href="/dashboard"
                    className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    可视化大屏
                  </Link>
                  <Link
                    href="/history"
                    className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    历史记录
                  </Link>
                  <Link
                    href="/subgraph"
                    className="text-sm text-white bg-indigo-600 hover:bg-indigo-700 px-3 py-1 rounded-lg transition-colors font-medium"
                  >
                    子图分析
                  </Link>
                  <Link
                    href="/modela-v2"
                    className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    ModelA v2
                  </Link>
                  <Link
                    href="/modeb-opinion"
                    className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    ModeB 舆情
                  </Link>
                </nav>
                <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                  v1.1
                </span>
              </div>
            </div>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
        <footer className="bg-white border-t border-gray-200 mt-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <p className="text-center text-sm text-gray-500">
              本系统为学术研究原型，研判结果仅供参考，具体执法决策请以现场检查为准
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
