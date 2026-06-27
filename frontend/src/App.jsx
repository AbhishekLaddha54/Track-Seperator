import React, { useEffect, useMemo, useState } from "react";

const MODES = {
  quick: "quick",
  studio: "studio",
};

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [mode, setMode] = useState(MODES.quick);
  const [studioFourStem, setStudioFourStem] = useState(true);
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [stems, setStems] = useState([]);

  const canSubmit = useMemo(() => {
    return !!selectedFile && (status === "idle" || status === "failed" || status === "completed");
  }, [selectedFile, status]);

  useEffect(() => {
    if (!jobId || status === "completed" || status === "failed") {
      return;
    }

    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (!res.ok) {
          throw new Error("Failed to read job status.");
        }
        const data = await res.json();
        setStatus(data.status);
        setStems(data.stems || []);
        setError(data.error || "");
      } catch (pollErr) {
        setError(pollErr.message || "Polling failed.");
        setStatus("failed");
      }
    }, 1500);

    return () => clearInterval(timer);
  }, [jobId, status]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!selectedFile) {
      return;
    }

    setStatus("queued");
    setError("");
    setStems([]);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("mode", mode);
    formData.append("studio_four_stem", studioFourStem ? "true" : "false");

    try {
      const res = await fetch(`/api/separate`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Failed to start processing.");
      }

      const data = await res.json();
      setJobId(data.job_id);
      setStatus("processing");
    } catch (submitErr) {
      setError(submitErr.message || "Unexpected error.");
      setStatus("failed");
    }
  }

  function statusLabel() {
    if (status === "idle") return "Ready";
    if (status === "queued") return "Queued...";
    if (status === "processing") return "Processing locally...";
    if (status === "completed") return "Completed";
    return "Failed";
  }

  function statusTone() {
    if (status === "completed") return "is-good";
    if (status === "failed") return "is-bad";
    if (status === "processing" || status === "queued") return "is-busy";
    return "is-idle";
  }

  return (
    <main className="app-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <section className="panel">
        <header className="panel-header">
          <p className="kicker">LOCAL FIRST AUDIO LAB</p>
          <h1 className="h1">Local Track Separator</h1>
          <p>Craft karaoke and studio-ready stems in a focused desktop-like workflow.</p>
        </header>

        <div className="layout-grid">
          <form onSubmit={handleSubmit} className="stack card-block">
            <div className="section-head">
              <h2 className="h2">Upload</h2>
              <span>Accepted: WAV, MP3, FLAC, M4A, OGG</span>
            </div>

            <label className="upload-zone" htmlFor="audio-input">
              <input
                id="audio-input"
                type="file"
                accept="audio/*"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              />
              <strong>{selectedFile ? selectedFile.name : "Drop or choose an audio file"}</strong>
              <span>{selectedFile ? "Ready to process" : "No cloud transfer. Local machine only."}</span>
            </label>

            <div className="section-head">
              <h2 className="h2">Mode</h2>
              <span>Choose your separation depth</span>
            </div>

            <div className="mode-grid">
              <button
                type="button"
                className={mode === MODES.quick ? "mode-btn active" : "mode-btn"}
                onClick={() => setMode(MODES.quick)}
              >
                <strong>Quick Karaoke</strong>
                <span>Instrumental output only</span>
              </button>
              <button
                type="button"
                className={mode === MODES.studio ? "mode-btn active" : "mode-btn"}
                onClick={() => setMode(MODES.studio)}
              >
                <strong>Studio</strong>
                <span>Vocals, drums, bass, other</span>
              </button>
            </div>

            {mode === MODES.studio && (
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={studioFourStem}
                  onChange={(e) => setStudioFourStem(e.target.checked)}
                />
                <span>Use 4-stem separation (vocals, drums, bass, other)</span>
              </label>
            )}

            <button type="submit" disabled={!canSubmit} className="primary-btn">
              Start Processing
            </button>
          </form>

          <aside className="stack">
            <section className="card-block status-box">
              <div className="section-head">
                <h2 className="h2">Processing Status</h2>
              </div>
              <div className={`status-pill ${statusTone()}`}>{statusLabel()}</div>
              {error && <p className="error-text">{error}</p>}
              <p className="muted">Processing happens locally. Your audio is not uploaded to any cloud.</p>
            </section>
            <section className="card-block downloads">
              <div className="section-head">
                <h2>Generated Stems</h2>
                <span>{stems.length} file(s)</span>
              </div>
              <div className="cards">
                {stems.length === 0 && <p className="muted">No outputs yet.</p>}
                {stems.map((stem) => (
                  <article key={stem.filename} className="card">
                    <h3>{stem.label}</h3>
                    <p>{stem.filename}</p>
                    <a href={stem.download_url} download>
                      Download Stem
                    </a>
                  </article>
                ))}
              </div>
            </section>
          </aside>
        </div>
      </section>
    </main>
  );
}

export default App;
