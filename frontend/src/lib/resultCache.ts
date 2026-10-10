import type { AnalysisResponse } from "@/types/api";

/**
 * Keeps the most recent full analysis (with resume excerpts) in sessionStorage for this tab.
 * The server stores only a redacted copy, and stores nothing when "Save to history" is off,
 * so the results page reads from here first. Data is cleared when the tab is closed.
 */
const PREFIX = "resumelens:analysis:";

export function cacheAnalysis(analysis: AnalysisResponse): void {
  try {
    sessionStorage.setItem(PREFIX + analysis.analysis_id, JSON.stringify(analysis));
  } catch {
    // Storage full or disabled: the results page falls back to the API.
  }
}

export function readCachedAnalysis(id: string): AnalysisResponse | null {
  try {
    const raw = sessionStorage.getItem(PREFIX + id);
    return raw ? (JSON.parse(raw) as AnalysisResponse) : null;
  } catch {
    return null;
  }
}

export function forgetAnalysis(id: string): void {
  try {
    sessionStorage.removeItem(PREFIX + id);
  } catch {
    // ignore
  }
}

export function forgetAllAnalyses(): void {
  try {
    Object.keys(sessionStorage)
      .filter((key) => key.startsWith(PREFIX))
      .forEach((key) => sessionStorage.removeItem(key));
  } catch {
    // ignore
  }
}
