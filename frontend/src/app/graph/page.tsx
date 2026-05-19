"use client";

import { useState, useEffect } from "react";

interface GraphStats {
  total_nodes: number;
  total_relations: number;
  node_types: Record<string, number>;
}

interface Entity {
  name: string;
  type: string;
  distance: number;
}

export default function GraphPage() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<{ entity: string; neighbors: Entity[] } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { fetchStats(); }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/graph/stats");
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error("获取图谱统计失败:", error);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      // 注意: 这里使用字符串拼接而不是模板字符串，避免嵌套转义问题
      const url = "http://localhost:8000/api/graph/entity/" + encodeURIComponent(searchQuery) + "?depth=2";
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setSearchResult(data);
      }
    } catch (error) {
      console.error("搜索失败:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">知识图谱</h1>
        <p className="text-gray-600">可视化企业知识网络，探索实体关系</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl shadow p-6">
          <div className="text-4xl mb-2">🔗</div>
          <div className="text-3xl font-bold text-purple-600">{stats?.total_nodes || 0}</div>
          <div className="text-gray-600">实体节点</div>
        </div>
        <div className="bg-white rounded-xl shadow p-6">
          <div className="text-4xl mb-2">➡️</div>
          <div className="text-3xl font-bold text-blue-600">{stats?.total_relations || 0}</div>
          <div className="text-gray-600">关系连接</div>
        </div>
        <div className="bg-white rounded-xl shadow p-6">
          <div className="text-4xl mb-2">📊</div>
          <div className="text-3xl font-bold text-green-600">{stats?.node_types ? Object.keys(stats.node_types).length : 0}</div>
          <div className="text-gray-600">实体类型</div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow p-6">
        <h3 className="font-semibold mb-4">实体搜索</h3>
        <div className="flex space-x-4">
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="输入实体名称搜索..." className="flex-1 px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500" onKeyPress={(e) => e.key === "Enter" && handleSearch()} />
          <button onClick={handleSearch} disabled={loading} className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition">
            {loading ? "搜索中..." : "搜索"}
          </button>
        </div>
      </div>

      {searchResult && (
        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold mb-4">{searchResult.entity} 的关联实体</h3>
          {searchResult.neighbors.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {searchResult.neighbors.map((neighbor, index) => (
                <div key={index} className="p-4 bg-gray-50 rounded-lg hover:bg-purple-50 transition">
                  <p className="font-medium">{neighbor.name}</p>
                  <p className="text-sm text-gray-500">{neighbor.type}</p>
                  <div className="mt-2 text-xs text-gray-400">距离: {neighbor.distance} 跳</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">未找到关联实体</p>
          )}
        </div>
      )}

      {stats?.node_types && Object.keys(stats.node_types).length > 0 && (
        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold mb-4">实体类型分布</h3>
          <div className="space-y-3">
            {Object.entries(stats.node_types).map(([type, count]) => (
              <div key={type} className="flex items-center">
                <div className="w-24 text-sm text-gray-600">{type}</div>
                <div className="flex-1 bg-gray-200 rounded-full h-4">
                  <div className="bg-purple-600 rounded-full h-4" style={{ width: ((count / stats.total_nodes) * 100) + "%" }} />
                </div>
                <div className="w-12 text-right text-sm font-medium">{count}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
