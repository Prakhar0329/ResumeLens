import { describe, expect, it } from "vitest";

import { buildSummary, formatBytes, formatScore, groupByCategory, verdictTone } from "@/lib/format";
import { validateJobDescription, validateResumeFile } from "@/lib/validation";
import type { AnalysisResponse } from "@/types/api";

describe("format helpers", () => {
  it("formats scores with one decimal", () => {
    expect(formatScore(72)).toBe("72.0");
    expect(formatScore(64.95)).toBe("65.0");
  });

  it("formats bytes", () => {
    expect(formatBytes(500)).toBe("500 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(3.5 * 1024 * 1024)).toBe("3.5 MB");
  });

  it("maps verdicts to tones", () => {
    expect(verdictTone("Weak match").text).toBe("text-redpen");
    expect(verdictTone("Excellent match").text).toBe("text-moss");
  });

  it("groups by category in canonical order", () => {
    const groups = groupByCategory([
      { name: "Docker", category: "devops" as const },
      { name: "Python", category: "language" as const },
    ]);
    expect(groups.map((g) => g.category)).toEqual(["language", "devops"]);
  });
});

describe("validation", () => {
  it("validates resume files", () => {
    expect(validateResumeFile(new File(["x"], "a.pdf", { type: "application/pdf" }))).toBeNull();
    expect(validateResumeFile(new File(["x"], "a.txt", { type: "text/plain" }))).toMatch(/PDF/);
    expect(validateResumeFile(new File([], "a.pdf", { type: "application/pdf" }))).toMatch(/empty/);
  });

  it("validates job description length", () => {
    expect(validateJobDescription("short")).toMatch(/at least 100/);
    expect(validateJobDescription("x".repeat(100))).toBeNull();
    expect(validateJobDescription("x".repeat(15001))).toMatch(/over 15,000/);
  });
});

describe("buildSummary", () => {
  it("includes score, skills and top suggestions but no resume text", () => {
    const analysis = {
      overall_score: 61.24,
      verdict: "Partial match",
      score_breakdown: {
        skill_coverage: 70,
        semantic_similarity: 50,
        keyword_overlap: 40,
        weights: { skill_coverage: 0.5, semantic_similarity: 0.35, keyword_overlap: 0.15 },
        raw_semantic_cosine: 0.4,
        raw_keyword_cosine: 0.2,
        skill_weight_redistributed: false,
      },
      matched_skills: [{ name: "Python", category: "language", in_jd_as: "required" }],
      missing_skills: [
        { name: "Kubernetes", category: "devops", in_jd_as: "required" },
        { name: "Terraform", category: "devops", in_jd_as: "preferred" },
      ],
      suggestions: [{ type: "missing_required_skill", priority: "high", message: "Add Kubernetes." }],
      requirement_matches: [
        {
          requirement: "Docker",
          requirement_type: "required",
          best_chunk: "SECRET resume line",
          best_chunk_section: "experience",
          similarity: 0.5,
        },
      ],
    } as unknown as AnalysisResponse;
    const text = buildSummary(analysis);
    expect(text).toContain("61.2/100 (Partial match)");
    expect(text).toContain("Missing required skills: Kubernetes");
    expect(text).toContain("Other missing skills: Terraform");
    expect(text).toContain("- Add Kubernetes.");
    expect(text).not.toContain("SECRET");
  });
});
