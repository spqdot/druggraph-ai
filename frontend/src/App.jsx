
import { useEffect, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import "./App.css";

const DEFAULT_API_BASE =
  "https://druggraph-ai-api-spq-gpdnhydndmfrhsca.westeurope-01.azurewebsites.net";
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API_BASE;

async function readApiResponse(response, resource) {
  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("application/json")) {
    throw new Error(
      `${resource} returned an invalid response (HTTP ${response.status}).`
    );
  }

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail || `${resource} request failed (HTTP ${response.status}).`
    );
  }

  return data;
}

function describeRequestError(error, resource) {
  if (error instanceof TypeError) {
    return (
      `${resource} could not reach the API. ` +
      "Check the network connection and API CORS configuration."
    );
  }

  return error.message || `${resource} failed unexpectedly.`;
}

function App() {
  const [diseases, setDiseases] = useState([]);
  const [selectedDisease, setSelectedDisease] =
    useState("MONDO_0004975");

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

  // Beginner-friendly questions.
  const sampleQuestions = [
    {
      category: "Understand the basics",
      icon: "💡",
      questions: [
        "What is a biological target?",
        "How are diseases connected to drugs?",
        "Explain this knowledge graph in simple terms.",
      ],
    },
    {
      category: "Explore this disease",
      icon: "🔬",
      questions: [
        `Which biological targets are associated with ${diseases.find(
          (d) => d.id === selectedDisease
        )?.name || "this disease"}?`,
        "Which drugs are linked to this disease in the graph?",
        "What clinical trial information is available?",
      ],
    },
    {
      category: "Explore drugs and targets",
      icon: "💊",
      questions: [
        "What drugs target APP?",
        "What information is available about the targets?",
        "What connections between drugs and targets are shown?",
      ],
    },
  ];

  // Load available diseases.
  useEffect(() => {
    const loadDiseases = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/diseases`);

        const data = await readApiResponse(
          response,
          "Disease list request"
        );
        const availableDiseases = data.diseases || [];

        setDiseases(availableDiseases);

        if (
          availableDiseases.some(
            (disease) => disease.id === "MONDO_0004975"
          )
        ) {
          setSelectedDisease("MONDO_0004975");
        } else if (availableDiseases.length > 0) {
          setSelectedDisease(availableDiseases[0].id);
        }
      } catch (err) {
        console.error("Disease loading error:", err);
        setError(describeRequestError(err, "Disease list request"));
      }
    };

    loadDiseases();
  }, []);

  // Load the graph whenever the selected disease changes.
  useEffect(() => {
    if (!selectedDisease) return;

    const controller = new AbortController();

    const loadGraph = async () => {
      setGraphLoading(true);
      setError("");
      setAnswer("");
      setSelectedNode(null);

      try {
        const response = await fetch(
          `${API_BASE}/api/graph/${selectedDisease}`,
          { signal: controller.signal }
        );

        const data = await readApiResponse(response, "Knowledge graph request");
        if (!controller.signal.aborted) {
          setGraphData(data);
        }
      } catch (err) {
        if (err.name === "AbortError") return;

        console.error("Graph loading error:", err);

        if (!controller.signal.aborted) {
          setGraphData({
            nodes: [],
            links: [],
            stats: {
              target_count: 0,
              drug_count: 0,
              clinical_trial_count: 0,
            },
          });

          setError(describeRequestError(err, "Knowledge graph request"));
        }
      } finally {
        if (!controller.signal.aborted) {
          setGraphLoading(false);
        }
      }
    };

    loadGraph();

    return () => controller.abort();
  }, [selectedDisease]);

  const selectedDiseaseName =
    diseases.find((disease) => disease.id === selectedDisease)?.name ||
    "Loading...";

  const handleDiseaseChange = (event) => {
    setSelectedDisease(event.target.value);
    setQuestion("");
    setAnswer("");
    setSelectedNode(null);
  };

  // Select a sample question without submitting it immediately.
  const handleSampleQuestion = (sampleQuestion) => {
    setQuestion(sampleQuestion);
    setAnswer("");
    setError("");
    setSelectedNode(null);
  };

  // Ask the RAG backend.
  const askDrugGraph = async () => {
    if (!question.trim() || loading) return;

    setLoading(true);
    setError("");
    setAnswer("");
    setSelectedNode(null);

    try {
      const response = await fetch(`${API_BASE}/api/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: question.trim(),
          disease_id: selectedDisease,
        }),
      });

      const data = await readApiResponse(response, "Question request");

      setAnswer(data.answer);
    } catch (err) {
      console.error("Question request error:", err);
      setError(describeRequestError(err, "Question request"));
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
            Query relationships between diseases, targets, proteins,
            drugs, and clinical trials.
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
                <option key={disease.id} value={disease.id}>
                  {disease.name}
                </option>
              ))}
            </select>
          </div>

          <div className="search-box">
            <input
              type="text"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  askDrugGraph();
                }
              }}
              placeholder={`Ask about ${selectedDiseaseName}...`}
            />

            <button
              onClick={askDrugGraph}
              disabled={loading || graphLoading || !question.trim()}
            >
              {loading ? "Asking..." : "Ask"}
            </button>
          </div>

          {/* Beginner-friendly sample questions */}
          <div
            className="sample-questions"
            style={{
              marginTop: "20px",
              textAlign: "left",
            }}
          >
            <h3
              style={{
                color: "#ffffff",
                fontSize: "16px",
                marginBottom: "6px",
              }}
            >
              Not sure what to ask? Try a sample question.
            </h3>

            <p
              style={{
                color: "#cbd5e1",
                fontSize: "13px",
                marginBottom: "16px",
              }}
            >
              Choose a question to fill the search box, then click Ask.
            </p>

            {sampleQuestions.map((group) => (
              <div
                key={group.category}
                style={{ marginBottom: "14px" }}
              >
                <h4
                  style={{
                    color: "#dbeafe",
                    fontSize: "13px",
                    marginBottom: "8px",
                  }}
                >
                  {group.icon} {group.category}
                </h4>

                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "8px",
                  }}
                >
                  {group.questions.map((sampleQuestion) => (
                    <button
                      key={sampleQuestion}
                      type="button"
                      onClick={() =>
                        handleSampleQuestion(sampleQuestion)
                      }
                      disabled={loading || graphLoading}
                      style={{
                        background: "#ffffff",
                        color: "#172033",
                        border: "1px solid #d7dce5",
                        borderRadius: "8px",
                        padding: "9px 12px",
                        fontSize: "12px",
                        lineHeight: "1.4",
                        textAlign: "left",
                        cursor: "pointer",
                        maxWidth: "100%",
                        whiteSpace: "normal",
                      }}
                    >
                      {sampleQuestion}
                    </button>
                  ))}
                </div>
              </div>
            ))}
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
            <strong>{graphData.stats.clinical_trial_count}</strong>
          </div>
        </section>

        <section className="content-grid">
          <div className="panel">
            <div className="panel-header">
              <h3>Knowledge Graph</h3>
              <span>Azure Cosmos DB</span>
            </div>

            <div className="graph-placeholder">
              {graphLoading ? (
                <p>Loading knowledge graph...</p>
              ) : graphData.nodes.length > 0 ? (
                <ForceGraph2D
                  graphData={graphData}
                  width={700}
                  height={450}
                  backgroundColor="#ffffff"
                  nodeLabel={(node) =>
                    `${node.type}: ${node.label || node.id}`
                  }
                  nodeAutoColorBy="type"
                  nodeRelSize={3}
                  nodeCanvasObject={(node, ctx, globalScale) => {
                    const isDisease = node.type === "Disease";
                    const isTarget = node.type === "Target";

                    const radius = isDisease ? 9 : isTarget ? 5 : 2;

                    ctx.beginPath();
                    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);

                    ctx.fillStyle = isDisease
                      ? "#2563eb"
                      : isTarget
                        ? "#38bdf8"
                        : "#86c96b";

                    ctx.fill();

                    // Avoid clutter from protein and other nodes.
                    if (!isDisease && !isTarget) return;
                    if (!isDisease && globalScale < 2.5) return;

                    const label = node.label || node.id;
                    const fontSize = isDisease
                      ? 14 / globalScale
                      : 10 / globalScale;

                    ctx.font = `${
                      isDisease ? "bold " : ""
                    }${fontSize}px Arial`;

                    ctx.textAlign = "center";
                    ctx.textBaseline = "top";
                    ctx.fillStyle = "#172033";

                    const maxLength = isDisease ? 28 : 24;
                    const shortLabel =
                      label.length > maxLength
                        ? label.slice(0, maxLength - 1) + "…"
                        : label;

                    ctx.fillText(
                      shortLabel,
                      node.x,
                      node.y + radius + 4
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

                  <h4>{selectedNode.label || selectedNode.id}</h4>

                  <p>
                    <strong>Type:</strong> {selectedNode.type}
                  </p>

                  <p>
                    <strong>ID:</strong> {selectedNode.id}
                  </p>

                  <p>
                    Click another node in the knowledge graph to
                    inspect it.
                  </p>
                </>
              ) : (
                <>
                  {loading && (
                    <p>Querying the knowledge graph...</p>
                  )}

                  {error && <p className="error">{error}</p>}

                  {!loading && !error && answer && (
                    <>
                      <p className="question">{question}</p>
                      <p>{answer}</p>
                    </>
                  )}

                  {!loading && !error && !answer && (
                    <>
                      <p className="question">
                        Welcome to DrugGraph AI
                      </p>

                      <p>
                        Select a sample question above to explore
                        diseases, biological targets, drugs, and
                        clinical trials. Answers depend on the
                        information available in the selected
                        disease knowledge graph.
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
