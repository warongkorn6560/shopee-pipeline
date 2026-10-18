import "server-only";

export const REPO = process.env.GITHUB_REPO || "warongkorn6560/shopee-pipeline";
const API = "https://api.github.com";

export class GitHubError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function githubConfigured(): boolean {
  return Boolean(process.env.GITHUB_TOKEN);
}

async function gh<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) throw new GitHubError(0, "ยังไม่ได้ตั้ง GITHUB_TOKEN");
  const res = await fetch(`${API}/repos/${REPO}${path}`, {
    ...init,
    cache: "no-store",
    redirect: init.redirect,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (res.status === 204 || res.status === 302) return null as T;
  if (!res.ok) {
    let msg = res.statusText;
    try {
      msg = ((await res.json()) as { message?: string }).message ?? msg;
    } catch {}
    throw new GitHubError(res.status, msg);
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}

export type WorkflowState = "active" | "disabled_manually" | "disabled_inactivity" | "missing";

export interface Workflow {
  id: number;
  name: string;
  path: string;
  state: WorkflowState;
  html_url: string;
}

export interface Run {
  id: number;
  name: string;
  path: string;
  display_title: string;
  status: "queued" | "in_progress" | "completed" | "waiting" | "requested" | "pending";
  conclusion: "success" | "failure" | "cancelled" | "skipped" | "timed_out" | "neutral" | null;
  event: string;
  run_number: number;
  created_at: string;
  run_started_at: string;
  updated_at: string;
  html_url: string;
}

export interface Artifact {
  id: number;
  name: string;
  size_in_bytes: number;
  expired: boolean;
  created_at: string;
}

export async function listWorkflows(): Promise<Map<string, Workflow>> {
  const data = await gh<{ workflows: Workflow[] }>("/actions/workflows?per_page=100");
  const map = new Map<string, Workflow>();
  for (const w of data.workflows) map.set(w.path.split("/").pop()!, w);
  return map;
}

export async function listRuns(limit = 15): Promise<Run[]> {
  const data = await gh<{ workflow_runs: Run[] }>(`/actions/runs?per_page=${limit}`);
  return data.workflow_runs;
}

export async function listRunsFor(file: string, limit = 5): Promise<Run[]> {
  try {
    const data = await gh<{ workflow_runs: Run[] }>(`/actions/workflows/${file}/runs?per_page=${limit}`);
    return data.workflow_runs;
  } catch (e) {
    if (e instanceof GitHubError && e.status === 404) return [];
    throw e;
  }
}

export async function failedStep(runId: number): Promise<string | null> {
  const data = await gh<{ jobs: { steps?: { name: string; conclusion: string | null }[] }[] }>(
    `/actions/runs/${runId}/jobs`,
  );
  for (const job of data.jobs) {
    const step = job.steps?.find((s) => s.conclusion === "failure");
    if (step) return step.name;
  }
  return null;
}

export async function runArtifacts(runId: number): Promise<Artifact[]> {
  const data = await gh<{ artifacts: Artifact[] }>(`/actions/runs/${runId}/artifacts`);
  return data.artifacts.filter((a) => !a.expired);
}

export async function artifactDownloadUrl(artifactId: number): Promise<string | null> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) return null;
  const res = await fetch(`${API}/repos/${REPO}/actions/artifacts/${artifactId}/zip`, {
    redirect: "manual",
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
  });
  return res.headers.get("location");
}

export async function dispatch(file: string, inputs?: Record<string, string>): Promise<void> {
  await gh(`/actions/workflows/${file}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref: "main", ...(inputs ? { inputs } : {}) }),
  });
}

export async function setWorkflowEnabled(file: string, enabled: boolean): Promise<void> {
  await gh(`/actions/workflows/${file}/${enabled ? "enable" : "disable"}`, { method: "PUT" });
}

export async function listVariables(): Promise<Record<string, { value: string; updated_at: string }>> {
  const data = await gh<{ variables: { name: string; value: string; updated_at: string }[] }>(
    "/actions/variables?per_page=30",
  );
  return Object.fromEntries(data.variables.map((v) => [v.name, { value: v.value, updated_at: v.updated_at }]));
}

export async function setVariable(name: string, value: string): Promise<void> {
  try {
    await gh(`/actions/variables/${name}`, { method: "PATCH", body: JSON.stringify({ name, value }) });
  } catch (e) {
    if (!(e instanceof GitHubError && e.status === 404)) throw e;
    await gh("/actions/variables", { method: "POST", body: JSON.stringify({ name, value }) });
  }
}

export async function deleteVariable(name: string): Promise<void> {
  try {
    await gh(`/actions/variables/${name}`, { method: "DELETE" });
  } catch (e) {
    if (!(e instanceof GitHubError && e.status === 404)) throw e;
  }
}

export async function listSecretNames(): Promise<Set<string>> {
  const data = await gh<{ secrets: { name: string }[] }>("/actions/secrets?per_page=100");
  return new Set(data.secrets.map((s) => s.name));
}
