export type Language = "auto" | "hi" | "en" | "hinglish";
export type OutputLanguage = "same" | "hi" | "en" | "hinglish";
export type Strategy = "standard" | "factuality";
export type Length = "short" | "medium" | "long";
export type VerifyMethod = "auto" | "rule" | "llm" | "hybrid" | "claim_nli";
export type ClaimStatus = "supported" | "contradicted" | "unverifiable" | "unsupported" | "uncertain";

export interface SourcePage { page: number; start: number; end: number }
export interface NLIScores { entailment: number; contradiction: number; neutral: number }
export interface EvidencePassage { passage_id: number; text: string; page: number | null; start: number; end: number; retrieval_similarity: number; nli: NLIScores; checks: ClaimCheck[] }
export interface ClaimCheck { name: string; passed: boolean; detail: string; outcome?: "match" | "mismatch" | "missing" | "review" | "not_applicable" }
export interface Claim {
  claim: string;
  summary_quote?: string;
  support_score?: number;
  score_calibrated?: boolean;
  nli_scores?: NLIScores | null;
  evidence_passages?: EvidencePassage[];
  contradiction_warning?: boolean;
  conflicting_evidence?: boolean;
  status: ClaimStatus;
  evidence: string;
  evidence_index?: number;
  explanation: string;
  confidence: number | null;
  evidence_score?: number;
  evidence_grounded?: boolean;
  disagreement?: boolean;
  checks?: ClaimCheck[];
  method: string;
}
export interface VerificationMetrics {
  n_claims: number; supported: number; contradicted: number; unverifiable: number;
  support_rate: number | null; contradiction_rate: number | null; unverifiable_rate: number | null;
  unsupported_rate: number | null; formula: string;
  unsupported?: number; uncertain?: number; mean_claim_score?: number | null; contradiction_count?: number;
}
export interface Verification {
  method: "rule" | "llm" | "hybrid" | "claim_nli";
  method_label: string;
  claims: Claim[];
  metrics: VerificationMetrics;
  limitations: string;
  is_ai_verification: boolean;
  verify_ms?: number;
  mode?: string;
  model?: string | null;
  run_id?: number | null;
}
export interface Analysis { key_facts: string[]; entities: string[]; dates: string[]; numbers: string[] }
export interface FactMetrics {
  n_summary_facts: number; n_source_facts: number; fact_precision: number | null; source_coverage: number | null;
  unsupported_facts: string[]; fact_recall_ref: number | null;
}
export interface PRF { precision: number; recall: number; f1: number }
export interface RunMetrics {
  fact: FactMetrics;
  lexical_similarity_to_source: number;
  rouge?: { rouge1: PRF; rouge2: PRF; rougeL: PRF };
}
export interface Run {
  id: number; created_at: string; title: string | null;
  language_requested: Language; language_detected: Exclude<Language, "auto">; output_language: OutputLanguage;
  length: Length; strategy: Strategy; mode: "demo" | "real"; provider: string; model: string;
  summary: string; inference_ms: number; source_words: number; summary_words: number;
  compression_ratio: number; compression_factor: number | null; cmi: number;
  compare_id: string | null; experiment_id: number | null; evaluation_run_id: number | null; saved: boolean;
  verification_metrics: VerificationMetrics | null; verification_method: string | null;
  // full only
  source_text?: string; reference_summary?: string | null; analysis?: Analysis;
  summary_facts?: { entities: string[]; dates: string[]; numbers: string[] };
  verification?: Verification | null; extra?: { warnings?: string[]; engine_note?: string; chunks?: number; source_pages?: SourcePage[] };
  metrics?: RunMetrics; source_preview?: string;
}
export interface SummarizeBody {
  source_pages?: SourcePage[];
  text: string; title?: string; language: Language; output_language: OutputLanguage; length: Length;
  strategy: Strategy; reference_summary?: string; save?: boolean;
}
export interface CompareResponse { compare_id: string; results: Run[] }
export interface HistoryResponse { total: number; limit: number; offset: number; items: Run[] }

export interface SampleItem { id: string; pair_id: string; language: "hi" | "en" | "hinglish"; title: string; source: string; reference_summary: string }
export interface SampleExample { id: string; language: string; title: string; text: string }
export interface SamplesResponse { dataset: string; note: string; items: SampleItem[]; assignment_examples: SampleExample[] }

export interface Health { status: string; version: string; database: string; mode: "demo" | "real" | "unavailable"; time: string }
export interface Preferences {
  provider_mode: "auto" | "demo" | "real" | null; model: string | null; default_strategy: Strategy;
  default_length: Length; default_language: Language; default_output_language: OutputLanguage;
  auto_save: boolean; verifier: VerifyMethod;
}
export interface SettingsState {
  provider: string; api_key_configured: boolean; provider_mode: "auto" | "demo" | "real";
  effective_mode: "demo" | "real" | "unavailable"; mode_problem: string | null; model: string; model_options: string[];
  connection: { verified: boolean; verified_at: string | null; model: string | null; error: string | null };
  preferences: Preferences; setup_instructions: string[];
  limits: { max_input_chars: number; max_upload_mb: number; chunk_chars: number; llm_timeout_seconds: number };
  database: string;
}

export interface GroupAgg {
  n_runs: number; avg_source_words?: number | null; avg_summary_words?: number | null; avg_compression_ratio?: number | null;
  avg_inference_ms?: number | null; median_inference_ms?: number | null; avg_cmi?: number | null;
  n_verified_runs?: number; n_claims?: number; claim_support_rate?: number | null; claim_contradiction_rate?: number | null;
  n_with_reference?: number; rouge1_f1?: number | null; rouge2_f1?: number | null; rougeL_f1?: number | null;
}
export interface SeriesPoint {
  run_id: number; created_at: string; strategy: Strategy; language: string; mode: string; summary_words: number;
  compression_ratio: number; inference_ms: number; claim_support_rate: number | null; rougeL_f1: number | null; cmi: number;
}
export interface PerClass { precision: number | null; recall: number | null; f1: number | null; tp: number; fp: number; fn: number }
export interface VerifierEval {
  n_labeled_claims: number; confusion: Record<string, Record<string, number>>;
  per_class: Record<string, PerClass>; accuracy: number | null; macro_f1: number | null; unsupported_detection: PerClass;
}
export interface BenchRow {
  item_id: string; pair_id: string; language: string; strategy: Strategy; run_id: number; summary_words: number;
  compression_ratio: number; inference_ms: number; cmi: number; rouge1_f1: number; rouge2_f1: number; rougeL_f1: number;
  fact_precision: number | null; fact_recall_ref: number | null; claim_support_rate: number | null; n_claims: number;
}
export interface BenchGroup {
  strategy: Strategy; language: string; n: number; avg_summary_words: number | null; avg_compression_ratio: number | null;
  avg_inference_ms: number | null; rouge1_f1: number | null; rouge2_f1: number | null; rougeL_f1: number | null;
  fact_precision: number | null; fact_recall_ref: number | null; claim_support_rate: number | null; avg_cmi: number | null;
}
export interface GapEntry {
  strategy: Strategy; n_pairs: number; mean_delta: Record<string, number | null>;
  pairs: { pair_id: string; hi: Record<string, number | null>; hinglish: Record<string, number | null>; delta: Record<string, number | null> }[];
}
export interface EvaluationRunOut {
  id: number; created_at: string; mode: "demo" | "real"; model: string; dataset: string; config: Record<string, unknown>;
  results: {
    items: BenchRow[]; by_strategy_language: BenchGroup[];
    verifier: { method: string; overall: VerifierEval; by_language: Record<string, VerifierEval> };
    code_mixing_gap: GapEntry[]; notes: string[];
  };
}
export interface MetricsResponse {
  totals: GroupAgg;
  counts: { all: number; workspace: number; experiments: number; evaluation: number; demo: number; real: number };
  by_strategy: Record<string, GroupAgg>;
  by_language: Record<string, GroupAgg>;
  by_strategy_language: (GroupAgg & { strategy: Strategy; language: string })[];
  language_distribution: Record<string, number>;
  series: SeriesPoint[];
  latest_evaluation: EvaluationRunOut | null;
  formulas: Record<string, string>;
  notes: string[];
}

export interface Experiment {
  id: number; created_at: string; name: string; description: string | null; status: "completed" | "failed" | "running";
  error: string | null; mode: "demo" | "real"; model: string; language: string; strategies: Strategy[]; length: Length;
  config: Record<string, unknown>;
  results: { by_strategy?: Record<string, GroupAgg>; overall?: GroupAgg; n_runs?: number; planned_runs?: number };
  duration_ms: number; runs?: Run[];
}
export interface ExperimentBody {
  name: string; description?: string; language: "all" | "hi" | "en" | "hinglish"; strategies: Strategy[]; length: Length;
  model?: string; dataset: "sample" | "custom"; documents: { title?: string; text: string; language?: Language }[]; verify: boolean;
}
