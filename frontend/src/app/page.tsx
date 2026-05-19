export default function Home() {
  return (
    <div className="space-y-12">
      <section className="text-center py-16 gradient-bg rounded-2xl text-white">
        <h1 className="text-4xl font-bold mb-4">GraphRAG Copilot</h1>
        <p className="text-xl mb-8 opacity-90">面向企业知识库的多模态检索增强生成系统</p>
        <div className="flex justify-center space-x-4">
          <a href="/upload" className="bg-white text-purple-600 px-8 py-3 rounded-lg font-semibold hover:bg-gray-100 transition">开始使用</a>
          <a href="/chat" className="border-2 border-white text-white px-8 py-3 rounded-lg font-semibold hover:bg-white/10 transition">体验问答</a>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-center mb-12">核心功能</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-white p-6 rounded-xl shadow-md hover:shadow-lg transition">
            <div className="text-4xl mb-4">📄</div>
            <h3 className="text-lg font-semibold mb-2">多模态解析</h3>
            <p className="text-gray-600 text-sm">支持 PDF、图片、表格、视频等多种格式，统一结构化处理</p>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-md hover:shadow-lg transition">
            <div className="text-4xl mb-4">🔗</div>
            <h3 className="text-lg font-semibold mb-2">知识图谱</h3>
            <p className="text-gray-600 text-sm">自动抽取实体关系，构建企业知识图谱，支持多跳推理</p>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-md hover:shadow-lg transition">
            <div className="text-4xl mb-4">🤖</div>
            <h3 className="text-lg font-semibold mb-2">Multi-Agent</h3>
            <p className="text-gray-600 text-sm">问题理解 {'->'} 检索规划 {'->'} 推理生成 {'->'} 事实校验，多智能体协作</p>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-md hover:shadow-lg transition">
            <div className="text-4xl mb-4">✅</div>
            <h3 className="text-lg font-semibold mb-2">可信回答</h3>
            <p className="text-gray-600 text-sm">带引用来源、推理路径，幻觉控制，答案可追溯</p>
          </div>
        </div>
      </section>

      <section className="bg-gray-50 rounded-2xl p-8">
        <h2 className="text-2xl font-bold text-center mb-8">系统架构</h2>
        <div className="max-w-3xl mx-auto">
          <div className="space-y-4">
            {[
              { step: "1", title: "用户提问", desc: "自然语言输入复杂问题" },
              { step: "2", title: "问题理解 Agent", desc: "识别意图、实体、时间范围" },
              { step: "3", title: "混合检索", desc: "向量检索 + BM25 + 图谱多跳查询" },
              { step: "4", title: "推理生成 Agent", desc: "多跳推理、信息融合" },
              { step: "5", title: "验证 Agent", desc: "检查幻觉、验证引用来源" },
              { step: "6", title: "最终回答", desc: "带引用来源、推理路径的可信回答" },
            ].map((item) => (
              <div key={item.step} className="flex items-start space-x-4">
                <div className="flex-shrink-0 w-10 h-10 bg-purple-600 text-white rounded-full flex items-center justify-center font-bold">{item.step}</div>
                <div>
                  <h4 className="font-semibold">{item.title}</h4>
                  <p className="text-gray-600 text-sm">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
