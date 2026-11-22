// Generated from backend/app/schemas/models.py. Do not edit.
export type ExperimentInput = { size?: number; distribution?: "random" | "sorted" | "reversed"; seed?: number; values?: (number)[] | null };
export type ValidationResult = { valid: boolean; reason?: string | null };
export type Visualization = { enabled?: boolean };
export type ExperimentConfig = { schema_version?: "1.0"; algorithm?: "bubble_sort"; mode?: "experiment"; input?: ExperimentInput; parameters?: Record<string, unknown>; visualization?: Visualization; metrics?: ("comparisons" | "swaps" | "elapsed_ms")[] };
export type ExperimentResult = { run_id: string; status: "completed" | "failed"; config: ExperimentConfig; input: (number)[]; output: (number)[]; metrics: Record<string, number>; validation: ValidationResult; trace: (TraceEvent)[]; trace_truncated: boolean; created_at: string };
export type TraceEvent = { step: number; type: "initial" | "compare" | "swap" | "write" | "pivot" | "complete"; indices?: (number)[]; array?: (number)[] | null; metadata?: Record<string, unknown> };
export type AlgorithmCapability = { name: string; level: "L1" | "L2" | "L3" | "L4"; executable: boolean; visualizable: boolean; max_input_size: number };
export type ConversationState = { session_id: string; current_algorithm?: string | null; last_config?: ExperimentConfig | null; last_run_id?: string | null; summary?: string; modified_fields?: (string)[] };
export type ConversationStartRequest = { config: ExperimentConfig };
export type ConversationRevisionRequest = { changes: Record<string, unknown> };
export type ParseRequest = { text: string; session_id?: string | null; confirmed_changes?: Record<string, unknown> | null };
export type ParseResult = { config: ExperimentConfig; source: "qwen" | "manual" | "mock"; requires_confirmation?: boolean; session_id?: string | null };
export type APIError = { code: string; message: string; details?: Record<string, unknown> | null };
export type APIResponse<T> = { data: T | null; error: APIError | null; request_id: string };
