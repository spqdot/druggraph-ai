import { useEffect, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedNode, setSelectedNode] = useState(null);
  const [graphData, setGraphData] = useState({
    nodes: [],
    links: [],
    stats: {
      target_count: 0,
      drug_count: 0,
      clinical_trial_count: 0,
    },
  });

  useEffect(() => {
    const loadGraph = async () => {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/api/graph/MONDO_0004975"
        );

        if (!response.ok) {
          throw new Error("Failed to load graph data.");
        }

        const data = await response.json();

        setGraphData(data);
      } catch (err) {
        console.error("Graph loading error:", err);
      }
    };

    loadGraph();
  }, []);

  const askDrugGraph = async () => {
    if (!question.trim()) {
      return;
    }

    setLoading(true);
    setError("");
    setAnswer("");

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/ask",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: question,
            disease_id: "MONDO_0004975",
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Something went wrong."
        );
      }

      setAnswer(data.answer);
    } catch (err) {
      setError(
        err.message ||
          "Could not connect to the DrugGraph AI API."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>DrugGraph AI</h1>
          <p>Biomedical Knowledge Graph &amp; RAG Assistant</p>
        </div>

        <div className="status">
          <span className="status-dot"></span>
          API Connected
        </div>
      </header>

      <main className="dashboard">
        <section className="hero-card">
          <h2>Explore Biomedical Knowledge</h2>

          <p>
            Query relationships between diseases, targets,
            proteins, drugs, and clinical trials.
          </p>

          <div className="search-box">
            <input
              type="text"
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  askDrugGraph();
                }
              }}
              placeholder="Ask DrugGraph AI a question..."
            />

            <button
              onClick={askDrugGraph}
              disabled={loading}
            >
              {loading ? "Asking..." : "Ask"}
            </button>
          </div>
        </section>

        <section className="stats">
          <div className="stat-card">
            <span>Disease</span>
            <strong>Alzheimer disease</strong>
          </div>

          <div className="stat-card">
            <span>Targets</span>
            <strong>{graphData.stats.target_count}</strong>
          </div>

          <div className="stat-card">
            <span>Drugs</span>
            <strong>{graphData.stats.drug_count}</strong>
          </div>

          <div className="stat-card">
            <span>Clinical Trials</span>
            <strong>{graphData.stats.clinical_trial_count}</strong>
          </div>
        </section>

        <section className="content-grid">
          <div className="panel">
            <div className="panel-header">
              <h3>Knowledge Graph</h3>
              <span>Neo4j</span>
            </div>

            <div className="graph-placeholder">
              {graphData.nodes.length > 0 ? (
                <ForceGraph2D
                  graphData={graphData}
                  width={520}
                  height={300}

                  backgroundColor="#ffffff"

                  nodeLabel={(node) =>
                    `${node.type}: ${node.label || node.id}`
                  }

                  nodeAutoColorBy="type"

                  nodeRelSize={5}

                  nodeCanvasObject={(node, ctx, globalScale) => {
                    const label = node.label || node.id;

                    // Different node sizes by type
                    const radius =
                      node.type === "Disease"
                        ? 10
                        : node.type === "Target"
                        ? 7
                        : 4;

                    // Draw node
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);

                    ctx.fillStyle = node.color;
                    ctx.fill();

                    // Only display labels for Disease and Target nodes
                    // Drug names appear when hovering over the node.
                    if (node.type === "Drug") {
                      return;
                    }

                    const fontSize =
                      node.type === "Disease"
                        ? 13 / globalScale
                        : 11 / globalScale;

                    ctx.font = `600 ${fontSize}px Sans-Serif`;
                    ctx.textAlign = "center";
                    ctx.textBaseline = "top";
                    ctx.fillStyle = "#172033";

                    ctx.fillText(
                      label,
                      node.x,
                      node.y + radius + 3
                    );
                  }}

                  linkLabel={(link) => link.type}

                  linkDirectionalArrowLength={5}
                  linkDirectionalArrowRelPos={1}

                  linkWidth={(link) =>
                    link.type === "ASSOCIATED_WITH" ? 2 : 1
                  }

                  d3VelocityDecay={0.35}
                  cooldownTicks={150}

                  onNodeClick={(node) => {
                    setSelectedNode(node);
                    setAnswer("");
                    setError("");
                  }}
                />
              ) : (
                <p>Loading knowledge graph...</p>
              )}
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <h3>DrugGraph AI Answer</h3>
              <span>RAG</span>
            </div>

            <div className="answer">
              {selectedNode ? (
                <>
                  <p className="question">
                    Selected {selectedNode.type}
                  </p>

                  <h4>
                    {selectedNode.label || selectedNode.id}
                  </h4>

                  <p>
                    <strong>Type:</strong> {selectedNode.type}
                  </p>

                  <p>
                    <strong>ID:</strong> {selectedNode.id}
                  </p>

                  <p>
                    Click another node in the knowledge graph
                    to inspect it.
                  </p>
                </>
              ) : (
                <>
                  {loading && (
                    <p>Querying the knowledge graph...</p>
                  )}

                  {error && (
                    <p className="error">
                      {error}
                    </p>
                  )}

                  {!loading && !error && answer && (
                    <>
                      <p className="question">
                        {question}
                      </p>

                      <p>{answer}</p>
                    </>
                  )}

                  {!loading && !error && !answer && (
                    <>
                      <p className="question">
                        What drugs target APP?
                      </p>

                      <p>
                        Ask a question to retrieve grounded
                        information from the biomedical
                        knowledge graph.
                      </p>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;