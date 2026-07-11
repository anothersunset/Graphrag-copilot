import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "GraphRAG Copilot - 多模态企业知识智能体系统",
  description: "面向企业知识库的多模态检索增强生成系统",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        <nav className="bg-white shadow-sm border-b">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex items-center">
                <Link href="/" className="flex items-center space-x-2">
                  <span className="text-2xl">🧠</span>
                  <span className="font-bold text-xl text-gray-900">GraphRAG Copilot</span>
                </Link>
              </div>
              <div className="flex items-center space-x-8">
                <Link href="/" className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">首页</Link>
                <Link href="/upload" className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">知识上传</Link>
                <Link href="/chat" className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">智能问答</Link>
                <Link href="/graph" className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">知识图谱</Link>
                <Link href="/status" className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">系统状态</Link>
              </div>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>
      </body>
    </html>
  );
}
