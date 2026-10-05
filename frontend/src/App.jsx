import { useRef, useState } from "react";
import { exportMetadata, processBatch, uploadDocuments } from "./services/api";

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

function EditableField({ label, value, onChange, wide = false }) {
  return (
    <label className={`metadata-field ${wide ? "metadata-field-wide" : ""}`}>
      <span>{label}</span>
      <input value={value ?? ""} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function missingMetadataFields(metadata) {
  const namedAuthors = (metadata.authors || []).filter((author) => author.name);
  const missing = [];
  if (!metadata.paper_title) missing.push("paper_title");
  if (!namedAuthors.length) missing.push("authors");
  if (namedAuthors.some((author) => !author.department)) missing.push("author_departments");
  if (metadata.document_type === "journal" && !metadata.journal_name) missing.push("journal_name");
  if (!metadata.publication_date?.year) missing.push("publication_date");
  if (!metadata.issn?.print && !metadata.issn?.electronic) missing.push("issn");
  if (metadata.document_type === "journal" && !metadata.ugc_care?.link) missing.push("ugc_care.link");
  if (metadata.document_type === "conference" && !metadata.conference_name) missing.push("conference_name");
  if (!metadata.doi) missing.push("doi");
  return missing;
}

function confidenceLabel(value) {
  if (value >= 0.95) return "Explicit";
  if (value >= 0.8) return "Strong context";
  if (value > 0) return "Needs verification";
  return "Unavailable";
}

function App() {
  const inputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [job, setJob] = useState(null);
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

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

  const updateMetadata = (filename, path, value) => {
    const keys = path.split(".");
    setResults((current) => current.map((result) => {
      if (result.filename !== filename || !result.metadata) return result;
      const metadata = { ...result.metadata };
      if (keys.length === 2) {
        metadata[keys[0]] = { ...metadata[keys[0]], [keys[1]]: value || null };
      } else {
        metadata[keys[0]] = value || null;
      }
      if (path === "document_type" && value === "conference") {
        metadata.journal_name = null;
        metadata.ugc_care = { status: "not_applicable", link: null };
      } else if (path === "document_type" && value === "journal" && metadata.ugc_care?.status === "not_applicable") {
        metadata.ugc_care = { status: "not_verified", link: null };
      }
      metadata.missing_fields = missingMetadataFields(metadata);
      return { ...result, metadata };
    }));
  };

  const updateAuthor = (filename, authorIndex, field, value) => {
    setResults((current) => current.map((result) => {
      if (result.filename !== filename || !result.metadata) return result;
      const authors = result.metadata.authors.map((author, index) =>
        index === authorIndex ? { ...author, [field]: value || null } : author,
      );
      const metadata = { ...result.metadata, authors };
      metadata.missing_fields = missingMetadataFields(metadata);
      return { ...result, metadata };
    }));
  };

  const addAuthor = (filename) => {
    setResults((current) => current.map((result) => result.filename === filename
      ? (() => {
        const metadata = { ...result.metadata, authors: [...result.metadata.authors, { name: null, department: null, institution: null, location: null }] };
        metadata.missing_fields = missingMetadataFields(metadata);
        return { ...result, metadata };
      })()
      : result));
  };

  const removeAuthor = (filename, authorIndex) => {
    setResults((current) => current.map((result) => {
      if (result.filename !== filename || !result.metadata) return result;
      const metadata = { ...result.metadata, authors: result.metadata.authors.filter((_, index) => index !== authorIndex) };
      metadata.missing_fields = missingMetadataFields(metadata);
      return { ...result, metadata };
    }));
  };

  const downloadMetadata = async (format) => {
    const records = results.filter((result) => result.status === "PROCESSED" && result.metadata).map((result) => result.metadata);
    if (!records.length) return;
    setExporting(true);
    setError("");
    try {
      const blob = await exportMetadata(format, records);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `Research_Paper_Metadata.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (requestError) {
      let message = "The metadata export could not be generated.";
      const responseData = requestError.response?.data;
      if (responseData instanceof Blob) {
        try {
          const payload = JSON.parse(await responseData.text());
          const detail = payload.detail;
          message = Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail || message;
        } catch {
          message = "The reviewed metadata is invalid and could not be exported.";
        }
      } else if (typeof responseData?.detail === "string") {
        message = responseData.detail;
      }
      setError(message);
    } finally {
      setExporting(false);
    }
  };

  const processedCount = results.filter((result) => result.status === "PROCESSED").length;
  const errorCount = results.filter((result) => result.status === "ERROR").length;

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand">PDQA</div>
        <div className="status-line">local batch workflow</div>
      </header>

      <section className="panel intro-panel">
        <div>
          <p className="label">research documents</p>
          <h1>Document intake</h1>
        </div>
        <p className="intro-text">Upload papers, process metadata, and review the extracted output before exporting.</p>
      </section>

      <section className="panel upload-panel">
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
          <div className="upload-icon">↑</div>
          <strong>Upload files</strong>
          <span>PDF, DOCX, JPG, PNG</span>
        </div>

        {files.length > 0 && (
          <div className="file-list">
            {files.map((file) => (
              <div className="file-row" key={`${file.name}-${file.lastModified}`}>
                <span className="file-name">{file.name}</span>
                <span className="file-size">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
              </div>
            ))}
            <button className="primary-btn" type="button" onClick={runPipeline} disabled={busy}>
              {busy ? "Processing..." : "Process batch"}
            </button>
          </div>
        )}

        {error && <div className="error-box">{error}</div>}
      </section>

      <section className="panel summary-panel">
        <div className="summary-box">
          <div>
            <p className="label">batch summary</p>
            <strong>{job ? job.job_id.slice(0, 8) : "waiting"}</strong>
          </div>
          <div className="summary-metrics">
            <div><span>{results.length || "0"}</span><small>total</small></div>
            <div><span>{processedCount || "0"}</span><small>processed</small></div>
            <div><span>{errorCount || "0"}</span><small>errors</small></div>
          </div>
        </div>
      </section>

      {results.length > 0 && (
        <section className="results-wrap">
          <div className="results-head">
            <p className="label">results</p>
            <div className="export-actions">
              <button type="button" onClick={() => downloadMetadata("excel")} disabled={exporting || !processedCount}>Excel</button>
              <button type="button" onClick={() => downloadMetadata("csv")} disabled={exporting || !processedCount}>CSV</button>
            </div>
          </div>

          {results.map((result) => {
            const metadata = result.metadata || {};
            const classification = result.classification || {};
            const extraction = result.extraction || {};
            const extractedText = extraction.cleaned_text || extraction.raw_text;
            return (
              <article className="result-card" key={result.filename}>
                <div className="result-top">
                  <div>
                    <span className="file-tag">{result.filename.split(".").pop().toUpperCase()}</span>
                    <strong>{result.filename}</strong>
                  </div>
                  <StatusPill status={result.status} />
                </div>

                {result.status === "ERROR" ? (
                  <p className="result-error">{result.message || "This document could not be processed."}</p>
                ) : (
                  <>
                    <div className="metadata-grid">
                      <EditableField label="Paper title" value={metadata.paper_title} wide onChange={(value) => updateMetadata(result.filename, "paper_title", value)} />
                      <EditableField label="Journal name" value={metadata.journal_name} onChange={(value) => updateMetadata(result.filename, "journal_name", value)} />
                      <label className="metadata-field">
                        <span>Document type</span>
                        <select value={metadata.document_type} onChange={(event) => updateMetadata(result.filename, "document_type", event.target.value)}>
                          <option value="unknown">Unknown</option>
                          <option value="journal">Journal</option>
                          <option value="conference">Conference</option>
                        </select>
                      </label>
                      <EditableField label="Conference name" value={metadata.conference_name} onChange={(value) => updateMetadata(result.filename, "conference_name", value)} />
                      <EditableField label="Month" value={metadata.publication_date?.month} onChange={(value) => updateMetadata(result.filename, "publication_date.month", value)} />
                      <EditableField label="Year" value={metadata.publication_date?.year} onChange={(value) => updateMetadata(result.filename, "publication_date.year", value)} />
                      <EditableField label="Print ISSN" value={metadata.issn?.print} onChange={(value) => updateMetadata(result.filename, "issn.print", value)} />
                      <EditableField label="Electronic ISSN" value={metadata.issn?.electronic} onChange={(value) => updateMetadata(result.filename, "issn.electronic", value)} />
                      <EditableField label="DOI" value={metadata.doi} onChange={(value) => updateMetadata(result.filename, "doi", value)} />
                      <div className="metadata-status">
                        <span>UGC CARE</span>
                        <strong>{metadata.ugc_care?.status?.replaceAll("_", " ") || "unknown"}</strong>
                      </div>
                      <EditableField label="UGC CARE link" value={metadata.ugc_care?.link} onChange={(value) => updateMetadata(result.filename, "ugc_care.link", value)} wide />
                    </div>

                    <div className="authors-header">
                      <span>Authors</span>
                      <button type="button" onClick={() => addAuthor(result.filename)}>Add author</button>
                    </div>

                    {(metadata.authors || []).map((author, index) => (
                      <div className="author-row" key={`${result.filename}-author-${index}`}>
                        <EditableField label={`Author ${index + 1}`} value={author.name} onChange={(value) => updateAuthor(result.filename, index, "name", value)} />
                        <EditableField label="Department" value={author.department} onChange={(value) => updateAuthor(result.filename, index, "department", value)} />
                        <EditableField label="Institution" value={author.institution} onChange={(value) => updateAuthor(result.filename, index, "institution", value)} />
                        <EditableField label="Location" value={author.location} onChange={(value) => updateAuthor(result.filename, index, "location", value)} />
                        <button className="remove-btn" type="button" onClick={() => removeAuthor(result.filename, index)}>Remove</button>
                      </div>
                    ))}

                    <dl className="basic-fields">
                      <DataField label="Publication type" value={classification.publication_type} />
                      <DataField label="Confidence" value={classification.confidence} />
                      <DataField label="Extraction" value={extraction.extraction_method} />
                    </dl>

                    {metadata.warnings?.length > 0 && (
                      <ul className="notes-list">
                        {metadata.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                      </ul>
                    )}

                    {metadata.missing_fields?.length > 0 && (
                      <p className="missing-fields">Missing: {metadata.missing_fields.join(", ")}</p>
                    )}

                    <details className="details-box">
                      <summary>Evidence and validation</summary>
                      <div className="confidence-box">
                        {Object.entries(metadata.confidence || {}).map(([field, score]) => (
                          <div key={field}>
                            <span>{field.replaceAll("_", " ")}</span>
                            <strong>{confidenceLabel(score)} · {Number(score).toFixed(2)}</strong>
                          </div>
                        ))}
                      </div>
                      <dl className="evidence-box">
                        {Object.entries(metadata.evidence || {}).filter(([, evidence]) => evidence?.text).map(([field, evidence]) => (
                          <div key={field}>
                            <dt>{field.replaceAll("_", " ")}</dt>
                            <dd>{evidence.text}{evidence.page ? ` · page ${evidence.page}` : ""}</dd>
                          </div>
                        ))}
                      </dl>
                    </details>

                    {extractedText && (
                      <details className="details-box">
                        <summary>View extracted text</summary>
                        <p className="text-preview">{extractedText}</p>
                      </details>
                    )}
                  </>
                )}
              </article>
            );
          })}
        </section>
      )}

      <footer className="app-footer">
        <span>Research document extractor</span>
        <span>simple local workflow</span>
      </footer>
    </main>
  );
}

export default App;