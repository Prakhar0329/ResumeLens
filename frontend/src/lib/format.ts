import type {
  AnalysisResponse,
  Priority,
  RequirementType,
  SectionName,
  SkillCategory,
  Verdict,
} from "@/types/api";

export const CATEGORY_LABELS: Record<SkillCategory, string> = {
  language: "Languages",
  frontend: "Frontend",
  backend: "Backend",
  database: "Databases",
  cloud: "Cloud",
  devops: "DevOps",
  data_ml: "Data & ML",
  testing: "Testing",
  tools: "Tools",
  concepts: "Concepts",
  soft_skill: "Soft skills",
};

export const CATEGORY_ORDER: SkillCategory[] = [
  "language",
  "frontend",
  "backend",
  "database",
  "cloud",
  "devops",
  "data_ml",
  "testing",
  "tools",
  "concepts",
  "soft_skill",
];

export const SECTION_LABELS: Record<SectionName, string> = {
  summary: "Summary",
  experience: "Experience",
  projects: "Projects",
  skills: "Skills",
  education: "Education",
  other: "Other",
};

export const REQUIREMENT_LABELS: Record<RequirementType, string> = {
  required: "Required",
  preferred: "Preferred",
  unspecified: "Mentioned",
};

export const PRIORITY_LABELS: Record<Priority, string> = {
  high: "Fix first",
  medium: "Worth doing",
  low: "Polish",
};

export const PRIORITY_ORDER: Priority[] = ["high", "medium", "low"];

/** Tailwind classes per verdict: text colour plus the SVG stroke colour class. */
export function verdictTone(verdict: Verdict): { text: string; stroke: string; bg: string } {
  switch (verdict) {
    case "Excellent match":
      return { text: "text-moss", stroke: "stroke-moss", bg: "bg-moss" };
    case "Strong match":
      return { text: "text-lens", stroke: "stroke-lens", bg: "bg-lens" };
    case "Partial match":
      return { text: "text-amber", stroke: "stroke-amber", bg: "bg-amber" };
    default:
      return { text: "text-redpen", stroke: "stroke-redpen", bg: "bg-redpen" };
  }
}

export function formatScore(score: number): string {
  return (Math.round(score * 10) / 10).toFixed(1);
}

export function formatPercent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string, locale?: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function groupByCategory<T extends { category: SkillCategory }>(
  items: T[],
): Array<{ category: SkillCategory; items: T[] }> {
  return CATEGORY_ORDER.map((category) => ({
    category,
    items: items.filter((item) => item.category === category),
  })).filter((group) => group.items.length > 0);
}

/** Plain-text summary for the "Copy summary" button. Contains no resume text. */
export function buildSummary(analysis: AnalysisResponse): string {
  const b = analysis.score_breakdown;
  const missingRequired = analysis.missing_skills.filter((s) => s.in_jd_as === "required").map((s) => s.name);
  const missingOther = analysis.missing_skills.filter((s) => s.in_jd_as !== "required").map((s) => s.name);
  const lines = [
    `ResumeLens match: ${formatScore(analysis.overall_score)}/100 (${analysis.verdict})`,
    `Skill coverage ${formatScore(b.skill_coverage)} | Semantic similarity ${formatScore(
      b.semantic_similarity,
    )} | Keyword overlap ${formatScore(b.keyword_overlap)}`,
    `Matched skills: ${analysis.matched_skills.map((s) => s.name).join(", ") || "none"}`,
    `Missing required skills: ${missingRequired.join(", ") || "none"}`,
  ];
  if (missingOther.length) lines.push(`Other missing skills: ${missingOther.join(", ")}`);
  const top = analysis.suggestions.filter((s) => s.priority === "high").slice(0, 3);
  if (top.length) {
    lines.push("Top suggestions:");
    top.forEach((s) => lines.push(`- ${s.message}`));
  }
  return lines.join("\n");
}
