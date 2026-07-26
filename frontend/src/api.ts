import type { Algorithm, BackendInfo, JobInfo } from "./types";

async function getJSON<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status} ${await response.text()}`);
  return response.json() as Promise<T>;
}

export const fetchBackends = () => getJSON<BackendInfo[]>("/api/backends");
export const fetchAlgorithms = () => getJSON<Algorithm[]>("/api/algorithms");
export const fetchJob = (id: string) => getJSON<JobInfo>(`/api/jobs/${id}`);

export async function submitJob(
  algorithmId: string,
  backendId: string,
  params: Record<string, number>,
): Promise<JobInfo> {
  const response = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ algorithm_id: algorithmId, backend_id: backendId, params }),
  });
  if (!response.ok) throw new Error(`submit failed: ${response.status} ${await response.text()}`);
  return response.json() as Promise<JobInfo>;
}
