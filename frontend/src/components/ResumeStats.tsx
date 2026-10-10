import type { ResumeStats as Stats } from "@/types/api";

interface ResumeStatsProps {
  stats: Stats;
}

export default function ResumeStats({ stats }: ResumeStatsProps) {
  const items = [
    { label: "Pages", value: String(stats.pages) },
    { label: "Words", value: stats.word_count.toLocaleString("en-US") },
    { label: "Bullets", value: String(stats.bullet_count) },
    { label: "Bullets with a number", value: `${Math.round(stats.bullets_with_numbers_pct)}%` },
  ];
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-rule bg-rule sm:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="bg-surface px-4 py-3">
          <dt className="text-sm text-graphite">{item.label}</dt>
          <dd className="mt-0.5 text-2xl font-semibold tabular-nums text-ink">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
