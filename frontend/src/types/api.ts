/**
 * TypeScript mirror of backend/app/schemas.py. Field names and types must stay identical.
 * Python `float`/`int` -> number, `datetime` -> ISO 8601 string, `X | None` -> X | null.
 */

export type Verdict = "Weak match" | "Partial match" | "Strong match" | "Excellent match";
export type RequirementType = "required" | "preferred" | "unspecified";
export type SectionName = "summary" | "experience" | "projects" | "skills" | "education" | "other";
export type Priority = "high" | "medium" | "low";
export type SkillCategory =
  | "language"
  | "frontend"
  | "backend"
  | "database"
  | "cloud"
  | "devops"
  | "data_ml"
  | "testing"
  | "tools"
  | "concepts"
  | "soft_skill";
export type SuggestionType =
  | "missing_required_skill"
  | "missing_required_skills_summary"
  | "missing_preferred_skills"
  | "no_skills_in_jd"
  | "no_quantified_metrics"
  | "few_quantified_metrics"
  | "resume_too_short"
  | "resume_too_long"
  | "skills_section_missing"
  | "experience_section_missing"
  | "no_sections_detected"
  | "no_bullets"
  | "weak_action_verbs"
  | "few_strong_verbs"
  | "long_bullets"
  | "low_semantic_alignment"
  | "low_keyword_overlap";

export interface SkillItem {
  name: string;
  category: SkillCategory;
  in_jd_as: RequirementType;
}

export interface ExtraSkill {
  name: string;
  category: SkillCategory;
}

export interface ScoreWeights {
  skill_coverage: number;
  semantic_similarity: number;
  keyword_overlap: number;
}

export interface ScoreBreakdown {
  skill_coverage: number;
  semantic_similarity: number;
  keyword_overlap: number;
  weights: ScoreWeights;
  raw_semantic_cosine: number;
  raw_keyword_cosine: number;
  skill_weight_redistributed: boolean;
}

export interface SectionScore {
  section: SectionName;
  similarity: number;
  score: number;
  word_count: number;
}

export interface RequirementMatch {
  requirement: string;
  requirement_type: RequirementType;
  best_chunk: string | null;
  best_chunk_section: SectionName | null;
  similarity: number;
}

export interface Suggestion {
  type: SuggestionType;
  priority: Priority;
  message: string;
}

export interface ResumeStats {
  pages: number;
  word_count: number;
  bullet_count: number;
  bullets_with_numbers_pct: number;
}

export interface ModelInfo {
  embedding_model: string;
  spacy_model: string;
  version: string;
}

export interface AnalysisResponse {
  analysis_id: string;
  created_at: string;
  overall_score: number;
  verdict: Verdict;
  score_breakdown: ScoreBreakdown;
  matched_skills: SkillItem[];
  missing_skills: SkillItem[];
  extra_skills: ExtraSkill[];
  section_scores: SectionScore[];
  requirement_matches: RequirementMatch[];
  suggestions: Suggestion[];
  resume_stats: ResumeStats;
  model_info: ModelInfo;
  stored: boolean;
  redacted: boolean;
}

export interface AnalysisSummary {
  analysis_id: string;
  created_at: string;
  overall_score: number;
  verdict: Verdict;
  top_missing_skills: string[];
}

export interface AnalysisList {
  items: AnalysisSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface DeleteResponse {
  deleted: number;
}

export interface ModelStatus {
  spacy_loaded: boolean;
  spacy_model: string;
  embedder_loaded: boolean;
  embedding_model: string;
  skills_count: number;
}

export interface BandConfig {
  floor: number;
  ceiling: number;
}

export interface SkillPriorityWeights {
  required: number;
  unspecified: number;
  preferred: number;
}

export interface VerdictThresholds {
  partial: number;
  strong: number;
  excellent: number;
}

export interface InputLimits {
  max_upload_mb: number;
  max_pdf_pages: number;
  min_jd_chars: number;
  max_jd_chars: number;
}

export interface ScoringConfig {
  weights: ScoreWeights;
  semantic_band: BandConfig;
  keyword_band: BandConfig;
  skill_priority_weights: SkillPriorityWeights;
  verdict_thresholds: VerdictThresholds;
  limits: InputLimits;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  models: ModelStatus;
  llm_enabled: boolean;
  config: ScoringConfig;
}

export interface RewriteRequest {
  bullet: string;
  target_skills?: string[];
  jd_context?: string | null;
}

export interface RewriteResponse {
  original: string;
  rewritten: string;
  placeholders: string[];
  model: string;
}

export interface ErrorDetail {
  code: string;
  message: string;
}

export interface ErrorResponse {
  error: ErrorDetail;
}
