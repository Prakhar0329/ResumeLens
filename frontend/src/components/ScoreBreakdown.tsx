import { formatPercent, formatScore } from "@/lib/format";
import type { ScoreBreakdown as Breakdown } from "@/types/api";

interface ScoreBreakdownProps {
  breakdown: Breakdown;
}

const ROWS = [
  {
    key: "skill_coverage",
    label: "Skill coverage",
    help: "Share of the posting's skills found on your resume; required skills count double.",
  },
  {
    key: "semantic_similarity",
    label: "Semantic similarity",
    help: "How closely your bullets express what each requirement asks for, even in different words.",
  },
  {
    key: "keyword_overlap",
    label: "Keyword overlap",
    help: "Exact shared terms between the two documents, as an ATS keyword match would see them.",
  },
] as const;

export default function ScoreBreakdown({ breakdown }: ScoreBreakdownProps) {
  return (
    <div>
      <ul className="space-y-5">
        {ROWS.map((row) => {
          const value = breakdown[row.key];
          const weight = breakdown.weights[row.key];
          const excluded = row.key === "skill_coverage" && breakdown.skill_weight_redistributed;
          return (
            <li key={row.key}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium text-ink">{row.label}</span>
                <span className="text-sm tabular-nums text-graphite">
                  {excluded ? (
                    "not used"
                  ) : (
                    <>
                      <span className="font-semibold text-ink">{formatScore(value)}</span> / 100, weight{" "}
                      {formatPercent(weight)}
                    </>
                  )}
                </span>
              </div>
              <div
                className="mt-2 h-2 overflow-hidden rounded-full bg-rule/70"
                role="meter"
                aria-label={row.label}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={excluded ? 0 : value}
              >
                <div
                  className={`h-full rounded-full ${excluded ? "bg-transparent" : "bg-lens"}`}
                  style={{ width: `${excluded ? 0 : Math.max(0, Math.min(100, value))}%` }}
                />
              </div>
              <p className="mt-1.5 text-sm text-graphite">{row.help}</p>
            </li>
          );
        })}
      </ul>
      {breakdown.skill_weight_redistributed ? (
        <p className="mt-4 text-sm text-graphite">
          No known skills were found in this posting, so the score uses only semantic similarity and keyword
          overlap.
        </p>
      ) : null}
    </div>
  );
}
