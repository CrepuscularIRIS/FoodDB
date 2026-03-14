import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <h1 className="text-4xl font-bold text-gray-900 mb-4">404</h1>
      <h2 className="text-xl text-gray-600 mb-6">页面不存在</h2>
      <p className="text-gray-500 mb-8">
        您访问的页面可能已被删除或暂时不可用
      </p>
      <Link
        href="/"
        className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
      >
        返回首页
      </Link>
    </div>
  );
}
