import axios from "axios";
import type {
  PercentileResult,
  ProblemDetail,
  ProblemListItem,
  SubmissionResult,
  SubmissionSummary,
  UserProfile,
} from "./types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const TOKEN_KEY = "codearena_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export const http = axios.create({ baseURL: API_BASE_URL });

http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---------- Auth ----------

export async function registerUser(username: string, email: string, password: string): Promise<UserProfile> {
  const { data } = await http.post<UserProfile>("/auth/register", { username, email, password });
  return data;
}

export async function loginUser(username: string, password: string): Promise<string> {
  // The backend expects OAuth2PasswordRequestForm — form-encoded, not JSON.
  const form = new URLSearchParams();
  form.set("username", username);
  form.set("password", password);
  const { data } = await http.post<{ access_token: string; token_type: string }>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data.access_token;
}

export async function fetchMe(): Promise<UserProfile> {
  const { data } = await http.get<UserProfile>("/auth/me");
  return data;
}

// ---------- Problems ----------

export async function fetchProblems(): Promise<ProblemListItem[]> {
  const { data } = await http.get<ProblemListItem[]>("/problems");
  return data;
}

export async function fetchProblem(slug: string): Promise<ProblemDetail> {
  const { data } = await http.get<ProblemDetail>(`/problems/${slug}`);
  return data;
}

// ---------- Submissions ----------

export async function createSubmission(
  problemSlug: string,
  language: string,
  sourceCode: string
): Promise<SubmissionResult> {
  const { data } = await http.post<SubmissionResult>("/submissions", {
    problem_slug: problemSlug,
    language,
    source_code: sourceCode,
  });
  return data;
}

export async function fetchSubmission(id: string): Promise<SubmissionResult> {
  const { data } = await http.get<SubmissionResult>(`/submissions/${id}`);
  return data;
}

export async function fetchMySubmissions(limit = 200): Promise<SubmissionSummary[]> {
  const { data } = await http.get<SubmissionSummary[]>("/submissions", { params: { limit } });
  return data;
}

export function submissionLiveSocketUrl(id: string): string {
  const wsBase = API_BASE_URL.replace(/^http/, "ws");
  return `${wsBase}/submissions/${id}/live`;
}

export async function fetchPercentile(submissionId: string): Promise<PercentileResult> {
  const { data } = await http.get<PercentileResult>(`/submissions/${submissionId}/percentile`);
  return data;
}

// ---------- Trial runs (Run button — sample tests only) ----------

export async function createRun(problemSlug: string, language: string, sourceCode: string): Promise<string> {
  const { data } = await http.post<{ run_id: string }>("/submissions/run", {
    problem_slug: problemSlug,
    language,
    source_code: sourceCode,
  });
  return data.run_id;
}

export function runLiveSocketUrl(runId: string): string {
  const wsBase = API_BASE_URL.replace(/^http/, "ws");
  return `${wsBase}/submissions/run/${runId}/live`;
}
