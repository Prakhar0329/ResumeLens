import { formatScore, SECTION_LABELS } from "@/lib/format";
import type { SectionScore } from "@/types/api";

interface SectionBarsProps {
  sections: SectionScore[];
}

/** Horizontal bars (pure CSS) of how well each resume section matches the posting. */
export default function SectionBars({ sections }: SectionBarsProps) {
  if (sections.length === 0) {
    return <p className="text-sm text-graphite">No resume sections were detected.</p>;
  }
  const best = sections.reduce((a, b) => (b.score > a.score ? b : a));
  return (
    <div>
      <ul className="space-y-3">
        {sections.map((section) => (
          <li
            key={section.section}
            className="grid grid-cols-[96px_1fr_44px] items-center gap-3 text-sm sm:grid-cols-[120px_1fr_52px]"
          >
            <span className="text-ink">
              {SECTION_LABELS[section.section]}
              <span className="block text-xs text-graphite">{section.word_count} words</span>
            </span>
            <div
              className="h-3 rounded-sm bg-rule/60"
              role="meter"
              aria-label={`${SECTION_LABELS[section.section]} section match`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={section.score}
              title={`Cosine similarity ${section.similarity.toFixed(3)}`}
            >
              <div
                className={`h-full rounded-sm ${section.section === best.section ? "bg-lens" : "bg-lens/55"}`}
                style={{ width: `${Math.max(1.5, Math.min(100, section.score))}%` }}
              />
            </div>
            <span className="text-right tabular-nums text-ink">{formatScore(section.score)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-sm text-graphite">
        Your {SECTION_LABELS[best.section].toLowerCase()} section matches the posting best. Sections near zero
        say little about what this job asks for; that is normal for Education and Skills lists.
      </p>
    </div>
  );
}
