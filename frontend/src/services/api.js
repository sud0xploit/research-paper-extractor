import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

export async function uploadDocuments(files) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const { data } = await api.post("/api/upload", formData);
  return data;
}

export async function processBatch(jobId) {
  const { data } = await api.post(`/api/process/${jobId}`);
  return data;
}

export function exportUrl(jobId = "", status = "") {
  const params = new URLSearchParams();
  if (jobId) params.set("job_id", jobId);
  if (status) params.set("status", status);
  const query = params.toString() ? `?${params.toString()}` : "";
  return `${api.defaults.baseURL}/api/export/excel${query}`;
}