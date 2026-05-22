export default function HomePage() {
  return (
    <main className="container">
      <h1>GraphRAG Copilot</h1>
      <p>Agentic GraphRAG with full retrieval traces.</p>
      <ul>
        <li>
          Web health: <a href="/api/health">/api/health</a>
        </li>
        <li>
          API health: <code>http://localhost:8000/healthz</code>
        </li>
        <li>
          API docs: <code>http://localhost:8000/docs</code>
        </li>
      </ul>
      <p>
        <a href="https://github.com/anothersunset/Graphrag-copilot">
          github.com/anothersunset/Graphrag-copilot
        </a>
      </p>
    </main>
  )
}
