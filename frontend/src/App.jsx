import { useEffect, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

function App() {
  const [diseases, setDiseases] = useState([]);
  const [selectedDisease, setSelectedDisease] = useState("MONDO_0004975");

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [graphLoading, setGraphLoading] = useState(true);
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

  // Load available diseases
  useEffect(() => {
    const loadDiseases = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/diseases`);

        if (!response.ok) {
          throw new Error("Failed to load diseases.");
        }

        const data = await response.json();

        setDiseases(data.diseases || []);

        // Keep Alzheimer as the initial selection if available.
        if (
          data.diseases?.some(
            (disease) => disease.id === "MONDO_0004975"
          )
        ) {
          setSelectedDisease("MONDO_0004975");
        } else if (data.diseases?.length > 0) {
          setSelectedDisease(data.diseases[0].id);
        }
      } catch (err) {
        console.error("Disease loading error:", err);
        setError("Could not load available diseases.");
      }
    };

    loadDiseases();
  }, []);

  // Load graph whenever the selected disease changes
  useEffect(() => {
    if (!selectedDisease) {
      return;
    }

    const loadGraph = async () => {
      setGraphLoading(true);
      setError("");
      setAnswer("");
      setSelectedNode(null);

      try {
        const response = await fetch(
          `${API_BASE}/api/graph/${selectedDisease}`
        );

        if (!response.ok) {
          throw new Error("Failed to load graph data.");
        }

        const data = await response.json();

        setGraphData(data);
      } catch (err) {
        console.error("Graph loading error:", err);

        setGraphData({
          nodes: [],
          links: [],
          stats: {
            target_count: 0,
            drug_count: 0,
            clinical_trial_count: 0,
          },
        });

        setError("Could not load the knowledge graph.");
      } finally {
        setGraphLoading(false);
      }
    };

    loadGraph();
  }, [selectedDisease]);

  const selectedDiseaseName =
    diseases.find(
      (disease) => disease.id === selectedDisease
    )?.name || "Loading...";

  const handleDiseaseChange = (event) => {
    setSelectedDisease(event.target.value);
    setQuestion("");
  };

  const askDrugGraph = async () => {
    if (!question.trim()) {
      return;
    }

    setLoading(true);
    setError("");
    setAnswer("");
    setSelectedNode(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/ask`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: question,
            disease_id: selectedDisease,
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

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              marginBottom: "16px",
              flexWrap: "wrap",
            }}
          >
            <label
              htmlFor="disease-selector"
              style={{
                fontWeight: "600",
                color: "#172033",
              }}
            >
              Disease
            </label>

            <select
              id="disease-selector"
              value={selectedDisease}
              onChange={handleDiseaseChange}
              disabled={graphLoading || diseases.length === 0}
              style={{
                padding: "10px 14px",
                borderRadius: "8px",
                border: "1px solid #d7dce5",
                background: "#ffffff",
                color: "#172033",
                fontSize: "14px",
                minWidth: "280px",
                cursor: "pointer",
              }}
            >
              {diseases.map((disease) => (
                <option
                  key={disease.id}
                  value={disease.id}
                >
                  {disease.name}
                </option>
              ))}
            </select>
          </div>

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
              placeholder={`Ask about ${selectedDiseaseName}...`}
            />

            <button
              onClick={askDrugGraph}
              disabled={loading || graphLoading}
            >
              {loading ? "Asking..." : "Ask"}
            </button>
          </div>
        </section>

        <section className="stats">
          <div className="stat-card">
            <span>Disease</span>
            <strong>{selectedDiseaseName}</strong>
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
            <strong>
              {graphData.stats.clinical_trial_count}
            </strong>
          </div>
        </section>

        <section className="content-grid">
          <div className="panel">
            <div className="panel-header">
              <h3>Knowledge Graph</h3>
              <span>Neo4j</span>
            </div>

            <div className="graph-placeholder">
              {graphLoading ? (
                <p>Loading knowledge graph...</p>
              ) : graphData.nodes.length > 0 ? (
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

                    const radius =
                      node.type === "Disease"
                        ? 10
                        : node.type === "Target"
                        ? 7
                        : 4;

                    ctx.beginPath();
                    ctx.arc(
                      node.x,
                      node.y,
                      radius,
                      0,
                      2 * Math.PI
                    );

                    ctx.fillStyle = node.color;
                    ctx.fill();

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
                <p>No graph data available.</p>
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
                    <strong>Type:</strong>{" "}
                    {selectedNode.type}
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
                        information from the selected disease
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
