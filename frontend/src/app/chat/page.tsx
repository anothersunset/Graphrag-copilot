"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ content: string; source: string }>;
  timestamp: Date;
  isStreaming?: boolean;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    };
    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      userMessage,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isStreaming: true,
      },
    ]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch("http://localhost:8000/api/query/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: input, top_k: 5 }),
      });

      if (!response.ok || !response.body) {
        throw new Error("请求失败");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));

            if (event.type === "token") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + event.text }
                    : m
                )
              );
            } else if (event.type === "done") {
              const data = event.data || {};
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        sources: data.sources || [],
                        isStreaming: false,
                      }
                    : m
                )
              );
            } else if (event.type === "error") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: m.content || "抱歉，生成过程中出现错误。",
                        isStreaming: false,
                      }
                    : m
                )
              );
            }
          } catch {
            // skip malformed lines
          }
        }
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: m.content || "抱歉，服务暂时不可用。请确保后端服务已启动。",
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-200px)]">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">智能问答</h1>
        <p className="text-gray-600">基于 GraphRAG 的多跳推理问答系统</p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 mb-4 p-4 bg-gray-50 rounded-lg">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 py-12">
            <div className="text-6xl mb-4">💬</div>
            <p className="text-lg">开始提问吧</p>
            <p className="text-sm mt-2">支持复杂问题、多跳推理、实体关系查询</p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {[
                "GraphRAG Copilot 由哪些核心服务组成？",
                "普通 RAG 和 GraphRAG 的区别是什么？",
                "Neo4j 不可用时系统如何降级？",
              ].map((q) => (
                <button key={q} onClick={() => setInput(q)} className="px-4 py-2 bg-white rounded-full text-sm text-purple-600 hover:bg-purple-50 transition">{q}</button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={"flex " + (msg.role === "user" ? "justify-end" : "justify-start")}>
              <div className={"max-w-[70%] rounded-lg p-4 " + (msg.role === "user" ? "bg-purple-600 text-white" : "bg-white shadow")}>
                <div className="whitespace-pre-wrap">
                  {msg.content}
                  {msg.isStreaming && <span className="inline-block w-2 h-4 bg-purple-600 ml-0.5 animate-pulse align-middle" />}
                </div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-xs text-gray-500 mb-1">参考来源:</p>
                    {msg.sources.slice(0, 3).map((s, i) => (
                      <p key={i} className="text-xs text-gray-600">{i + 1}. {s.source}</p>
                    ))}
                  </div>
                )}
                <div className="text-xs opacity-70 mt-2">{msg.timestamp.toLocaleTimeString()}</div>
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white rounded-lg p-4 shadow">
              <div className="flex items-center space-x-2">
                <div className="animate-pulse-slow">🤖</div>
                <span className="text-gray-500">正在思考...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex space-x-4">
        <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="输入您的问题..." className="flex-1 px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500" disabled={loading} />
        <button type="submit" disabled={loading || !input.trim()} className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition">发送</button>
      </form>
    </div>
  );
}
