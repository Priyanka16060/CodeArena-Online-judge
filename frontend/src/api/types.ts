export type Difficulty = "EASY" | "MEDIUM" | "HARD";

export type Language = "python" | "cpp" | "java" | "javascript";

export type Verdict =
  | "PENDING"
  | "QUEUED"
  | "JUDGING"
  | "ACCEPTED"
  | "WRONG_ANSWER"
  | "TIME_LIMIT_EXCEEDED"
  | "MEMORY_LIMIT_EXCEEDED"
  | "RUNTIME_ERROR"
  | "COMPILE_ERROR"
  | "INTERNAL_ERROR";

export interface ProblemListItem {
  id: string;
  slug: string;
  title: string;
  difficulty: Difficulty;
}

export interface SampleTest {
  ordinal: number;
  input_data: string;
  expected_output: string;
}

export interface ProblemDetail {
  id: string;
  slug: string;
  title: string;
  statement: string;
  difficulty: Difficulty;
  time_limit_seconds: number;
  memory_limit_mb: number;
  sample_tests: SampleTest[];
}

export interface SubmissionResult {
  id: string;
  problem_id: string;
  language: Language;
  verdict: Verdict;
  passed_test_count: number;
  total_test_count: number;
  score: number;
  max_time_ms: number;
  max_memory_kb: number;
  compile_output: string | null;
  failing_test_ordinal: number | null;
  stderr_snippet: string | null;
  submitted_at: string;
  judged_at: string | null;
  worker_id: string | null;
}

export interface SubmissionSummary {
  id: string;
  problem_id: string;
  verdict: Verdict;
  submitted_at: string;
}

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  is_admin: boolean;
  created_at: string;
}

export interface RunCaseEvent {
  final: false;
  ordinal: number;
  passed: boolean;
  status: string;
  input_data: string;
  expected_output: string;
  actual_output: string | null;
  stderr_snippet: string | null;
  time_ms: number;
}

export interface RunFinalEvent {
  final: true;
  status: "ok" | "compile_error" | "error";
  all_passed?: boolean;
  case_count?: number;
  compile_output?: string;
  message?: string;
}

export type RunEvent = RunCaseEvent | RunFinalEvent | { ping: true };

export interface PercentileResult {
  faster_than_pct: number | null;
  less_memory_than_pct: number | null;
  sample_size: number;
}

export const TERMINAL_VERDICTS: Verdict[] = [
  "ACCEPTED",
  "WRONG_ANSWER",
  "TIME_LIMIT_EXCEEDED",
  "MEMORY_LIMIT_EXCEEDED",
  "RUNTIME_ERROR",
  "COMPILE_ERROR",
  "INTERNAL_ERROR",
];
