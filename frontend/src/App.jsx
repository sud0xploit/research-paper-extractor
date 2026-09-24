import { useRef, useState } from "react";
import { exportUrl, processBatch, uploadDocuments } from "./services/api";

const ACCEPTED_TYPES = ".pdf,.docx,.jpg,.jpeg,.png";

function StatusPill({ status }) {
  return <span className={`status status-${status.toLowerCase()}`}>{status}</span>;
}

function DataField({ label, value, wide = false }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className={`data-field ${wide ? "data-field-wide" : ""}`}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function App() {
  const inputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [job, setJob] = useState(null);
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  const chooseFiles = (selectedFiles) => {
    const accepted = Array.from(selectedFiles).filter((file) =>
      ACCEPTED_TYPES.split(",").some((type) => file.name.toLowerCase().endsWith(type.slice(1))),
    );
    setFiles(accepted);
    setError(accepted.length < selectedFiles.length ? "Some files were skipped because their format is unsupported." : "");
  };

  const runPipeline = async () => {
    if (!files.length) return;
    setBusy(true);
    setError("");
    setResults([]);
    try {
      const uploaded = await uploadDocuments(files);
      const successful = uploaded.files.filter((file) => file.status === "UPLOADED");
      setJob(uploaded);
      if (successful.length) {
        const processed = await processBatch(uploaded.job_id);
        setResults(processed.files);
      } else {
        setResults(uploaded.files);
      }
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "The backend could not process this batch.");
    } finally {
      setBusy(false);
    }
  };

  const processedCount = results.filter((result) => result.status === "PROCESSED").length;
  const errorCount = results.filter((result) => result.status === "ERROR").length;

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">P</span><span>paperwork</span></div>
        <div className="topbar-note">research document desk <span className="live-dot" /> local workspace</div>
      </header>

      <section className="intro">
        <p className="eyebrow">DOCUMENT INTAKE / 01</p>
        <h1>Turn a stack of papers<br /><em>into a clear record.</em></h1>
        <p className="lede">Drop your research documents here. Paperwork extracts the signal, classifies each item, and keeps every result visible when a batch gets messy.</p>
      </section>

      <section className="workspace-grid">
        <div className="intake-column">
          <div
            className={`dropzone ${dragging ? "is-dragging" : ""}`}
            onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFiles(event.dataTransfer.files); }}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }}
          >
            <input ref={inputRef} type="file" multiple accept={ACCEPTED_TYPES} onChange={(event) => chooseFiles(event.target.files)} />
            <div className="upload-glyph">↑</div>
            <strong>Drop documents to begin</strong>
            <span>or browse from this computer</span>
            <small>PDF / DOCX / JPG / PNG · up to 50 MB each</small>
          </div>

          {files.length > 0 && (
            <div className="selected-files">
              <div className="section-label"><span>SELECTED FILES</span><span>{files.length.toString().padStart(2, "0")}</span></div>
              {files.map((file) => <div className="file-row" key={`${file.name}-${file.lastModified}`}><span className="file-type">{file.name.split(".").pop().toUpperCase()}</span><span className="file-name">{file.name}</span><span className="file-size">{(file.size / 1024 / 1024).toFixed(1)} MB</span></div>)}
              <button className="primary-button" type="button" onClick={runPipeline} disabled={busy}>
                {busy ? "Processing batch..." : "Process batch  →"}
              </button>
            </div>
          )}
          {error && <div className="error-message">{error}</div>}
        </div>

        <aside className="summary-panel">
          <div className="section-label"><span>BATCH SUMMARY</span><span>{job ? job.job_id.slice(0, 8) : "WAITING"}</span></div>
          <div className="metric-grid">
            <div className="metric"><span className="metric-value">{results.length || "—"}</span><span>Total files</span></div>
            <div className="metric"><span className="metric-value metric-good">{processedCount || "—"}</span><span>Processed</span></div>
            <div className="metric"><span className="metric-value metric-warn">{errorCount || "—"}</span><span>Needs attention</span></div>
          </div>
          <div className="summary-rule" />
          <p className="summary-copy">Each document is handled independently. A failed scan stays visible without holding up the rest of the batch.</p>
          <a className={`export-link ${results.length && job ? "" : "is-disabled"}`} href={results.length && job ? exportUrl(job.job_id) : undefined} onClick={(event) => (!results.length || !job) && event.preventDefault()}>
            <span>↓</span> Export workbook
          </a>
        </aside>
      </section>

      {results.length > 0 && (
        <section className="results-section">
          <div className="results-heading">
            <div className="section-label"><span>STRUCTURED RECORDS</span><span>{results.length.toString().padStart(2, "0")} RECORDS</span></div>
            <a className="export-link" href={job ? exportUrl(job.job_id) : undefined}>
              <span>↓</span> Export reviewed data
            </a>
          </div>
          <div className="results-list">
            {results.map((result) => {
              const metadata = result.metadata || {};
              const classification = result.classification || {};
              const extraction = result.extraction || {};
              const authors = metadata.authors?.map((author) => author.name).filter(Boolean).join(", ");
              const extractedText = extraction.cleaned_text || extraction.raw_text;
              return (
                <article className="result-card" key={result.filename}>
                  <div className="result-card-header">
                    <div><span className="file-type">{result.filename.split(".").pop().toUpperCase()}</span><strong>{result.filename}</strong></div>
                    <StatusPill status={result.status} />
                  </div>
                  {result.status === "ERROR" ? (
                    <p className="result-error">{result.message || "This document could not be processed."}</p>
                  ) : (
                    <>
                      <dl className="data-grid">
                        <DataField label="Title" value={metadata.title} wide />
                        <DataField label="Authors" value={authors} wide />
                        <DataField label="Publication year" value={metadata.publication_year} />
                        <DataField label="Journal" value={metadata.journal} />
                        <DataField label="Conference" value={metadata.conference} />
                        <DataField label="Publisher" value={metadata.publisher} />
                        <DataField label="DOI" value={metadata.doi} />
                        <DataField label="Volume / issue" value={[metadata.volume, metadata.issue].filter(Boolean).join(" / ")} />
                        <DataField label="Pages" value={metadata.pages} />
                        <DataField label="Document status" value={metadata.document_status} />
                        <DataField label="Publication type" value={classification.publication_type} />
                        <DataField label="Classification confidence" value={classification.confidence} />
                        <DataField label="Metadata confidence" value={metadata.metadata_confidence} />
                        <DataField label="Extraction method" value={extraction.extraction_method} />
                      </dl>
                      {extractedText && (
                        <details className="extracted-text">
                          <summary>View extracted text</summary>
                          <p>{extractedText}</p>
                        </details>
                      )}
                    </>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      )}
      <footer><span>Paperwork / Research document extractor</span><span>Built for careful reading.</span></footer>
    </main>
  );
}

export default App;