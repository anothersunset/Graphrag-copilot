import type { Metadata } from "next"
import Link from "next/link"
import "./globals.css"

export const metadata: Metadata = {
  title: "GraphRAG Copilot",
  description: "Agentic GraphRAG with full retrieval traces.",
}

const NAV_ITEMS = [
  { href: "/", label: "问答" },
  { href: "/graph", label: "知识图谱" },
  { href: "/status", label: "系统状态" },
]

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body>
        <header
          style={{
            display: "flex",
            alignItems: "center",
            gap: 24,
            padding: "10px 24px",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <Link href="/" style={{ fontWeight: 700, fontSize: 16 }}>
            GraphRAG Copilot
          </Link>
          <nav style={{ display: "flex", gap: 16 }}>
            {NAV_ITEMS.map((item) => (
              <Link key={item.href} href={item.href} style={{ color: "#9AA0A6", fontSize: 14 }}>
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        {children}
      </body>
    </html>
  )
}
