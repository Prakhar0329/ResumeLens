import { REQUIREMENT_LABELS, SECTION_LABELS } from "@/lib/format";
import type { RequirementMatch } from "@/types/api";

interface RequirementMatchesProps {
  matches: RequirementMatch[];
  redacted: boolean;
}

function strength(similarity: number): { label: string; className: string } {
  if (similarity >= 0.6) return { label: "Strong", className: "text-moss" };
  if (similarity >= 0.4) return { label: "Partial", className: "text-amber" };
  return { label: "Weak", className: "text-redpen" };
}

/**
 * Explainability: for each key requirement, the resume excerpt that matched it best and the
 * cosine similarity between their embeddings.
 */
export default function RequirementMatches({ matches, redacted }: RequirementMatchesProps) {
  if (matches.length === 0) {
    return <p className="text-sm text-graphite">No requirement sentences were found in the posting.</p>;
  }
  return (
    <div>
      {redacted ? (
        <p className="mb-4 rounded-md border border-rule bg-surface px-3 py-2 text-sm text-graphite">
          Resume excerpts aren&apos;t shown for saved analyses because your resume text is never stored. Run
          the analysis again to see them.
        </p>
      ) : null}
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-left text-sm">
          <caption className="sr-only">Job requirements and the best-matching part of your resume</caption>
          <thead>
            <tr className="border-b border-rule text-graphite">
              <th scope="col" className="w-[42%] py-2 pr-4 font-medium">
                The posting asks for
              </th>
              <th scope="col" className="py-2 pr-4 font-medium">
                Closest line in your resume
              </th>
              <th scope="col" className="w-24 py-2 text-right font-medium">
                Similarity
              </th>
            </tr>
          </thead>
          <tbody>
            {matches.map((match, index) => {
              const s = strength(match.similarity);
              return (
                <tr key={`${index}-${match.requirement}`} className="border-b border-rule/70 align-top">
                  <td className="py-3 pr-4">
                    <p className="doc-quote">{match.requirement}</p>
                    <p className="mt-1 text-xs text-graphite">{REQUIREMENT_LABELS[match.requirement_type]}</p>
                  </td>
                  <td className="py-3 pr-4">
                    {match.best_chunk ? (
                      <p className="doc-quote italic">{match.best_chunk}</p>
                    ) : (
                      <p className="text-graphite">Not stored</p>
                    )}
                    {match.best_chunk_section ? (
                      <p className="mt-1 text-xs text-graphite">
                        From {SECTION_LABELS[match.best_chunk_section]}
                      </p>
                    ) : null}
                  </td>
                  <td className="py-3 text-right tabular-nums">
                    <span className="font-semibold text-ink">{match.similarity.toFixed(2)}</span>
                    <span className={`block text-xs ${s.className}`}>{s.label}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-sm text-graphite">
        Similarity is the cosine between sentence embeddings (all-MiniLM-L6-v2), from -1 to 1. The Strong,
        Partial and Weak labels use rough cut-offs of 0.6 and 0.4; treat them as a reading aid, not a verdict.
      </p>
    </div>
  );
}
