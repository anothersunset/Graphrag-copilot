"use client";

import { useState, useEffect } from "react";

interface SystemStatus {
  status: string;
  llm_model: string;
  embedding_model: string;
  vector_store: {
    type: string;
    total_vectors: number;
    dimension: number;
    total_documents: number;
  };
  graph_store: {
    status: string;
    total_nodes: number;
    total_relations: number;
    node_types: Record<string, number>;
  };
}

export default function StatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { fetchStatus(); }, []);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const response = await fetch("http://localhost:8000/api/system/status");
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
        setError(null);
      } else {
        throw new Error("获取状态失败");
      }
    } catch (err) {
      setError("无法连接到后端服务，请确保服务已启动");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse-slow text-4xl">⏳</div>
        <span className="ml-4 text-gray-500">正在获取系统状态...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-6xl mb-4">⚠️</div>
        <h2 className="text-xl font-semibold mb-2">连接失败</h2>
        <p className="text-gray-600 mb-4">{error}</p>
        <button onClick={fetchStatus} className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition">重试</button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">系统状态</h1>
        <p className="text-gray-600">监控系统运行状态和各组件健康情况</p>
      </div>

      <div className="bg-white rounded-xl shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">系统状态</h3>
          <button onClick={fetchStatus} className="px-4 py-2 text-sm bg-gray-100 rounded-lg hover:bg-gray-200 transition">刷新</button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-green-50 rounded-lg">
            <div className="text-sm text-gray-600">运行状态</div>
            <div className="text-lg font-semibold text-green-600">{status?.status === "running" ? "运行中" : "未知"}</div>
          </div>
          <div className="p-4 bg-blue-50 rounded-lg">
            <div className="text-sm text-gray-600">服务版本</div>
            <div className="text-lg font-semibold text-blue-600">v1.0.0</div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow p-6">
        <h3 className="font-semibold mb-4">模型配置</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <div className="text-sm text-gray-600">LLM 模型</div>
            <div className="text-lg font-semibold">{status?.llm_model || "未配置"}</div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <div className="text-sm text-gray-600">Embedding 模型</div>
            <div className="text-lg font-semibold">{status?.embedding_model || "未配置"}</div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow p-6">
        <h3 className="font-semibold mb-4">向量存储</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 bg-purple-50 rounded-lg text-center">
            <div className="text-3xl font-bold text-purple-600">{status?.vector_store?.total_vectors || 0}</div>
            <div className="text-sm text-gray-600">向量数量</div>
          </div>
          <div className="p-4 bg-blue-50 rounded-lg text-center">
            <div className="text-3xl font-bold text-blue-600">{status?.vector_store?.total_documents || 0}</div>
            <div className="text-sm text-gray-600">文档数量</div>
          </div>
          <div className="p-4 bg-green-50 rounded-lg text-center">
            <div className="text-3xl font-bold text-green-600">{status?.vector_store?.dimension || 0}</div>
            <div className="text-sm text-gray-600">向量维度</div>
          </div>
          <div className="p-4 bg-yellow-50 rounded-lg text-center">
            <div className="text-lg font-semibold text-yellow-600">{status?.vector_store?.type?.toUpperCase() || "N/A"}</div>
            <div className="text-sm text-gray-600">存储类型</div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow p-6">
        <h3 className="font-semibold mb-4">知识图谱</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="p-4 bg-gray-50 rounded-lg text-center">
            <div className="text-3xl font-bold text-purple-600">{status?.graph_store?.total_nodes || 0}</div>
            <div className="text-sm text-gray-600">实体节点</div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg text-center">
            <div className="text-3xl font-bold text-blue-600">{status?.graph_store?.total_relations || 0}</div>
            <div className="text-sm text-gray-600">关系连接</div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg text-center">
            <div className="text-lg font-semibold">{status?.graph_store?.status === "connected" ? "已连接" : "未连接"}</div>
            <div className="text-sm text-gray-600">连接状态</div>
          </div>
        </div>
      </div>
    </div>
  );
}
