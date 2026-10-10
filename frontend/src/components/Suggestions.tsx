import { PRIORITY_LABELS, PRIORITY_ORDER } from "@/lib/format";
import type { Priority, Suggestion } from "@/types/api";

interface SuggestionsProps {
  suggestions: Suggestion[];
}

const MARKER: Record<Priority, string> = {
  high: "bg-redpen",
  medium: "bg-amber",
  low: "bg-graphite",
};

export default function Suggestions({ suggestions }: SuggestionsProps) {
  if (suggestions.length === 0) {
    return (
      <p className="text-sm text-graphite">
        No rule-based issues found. Compare the requirement table above with your bullets for finer edits.
      </p>
    );
  }
  return (
    <div className="space-y-6">
      {PRIORITY_ORDER.map((priority) => {
        const items = suggestions.filter((s) => s.priority === priority);
        if (items.length === 0) return null;
        return (
          <section key={priority} aria-labelledby={`suggestions-${priority}`}>
            <h3 id={`suggestions-${priority}`} className="flex items-center gap-2 font-semibold text-ink">
              <span aria-hidden className={`h-2.5 w-2.5 rounded-full ${MARKER[priority]}`} />
              {PRIORITY_LABELS[priority]}
              <span className="font-normal text-graphite">({items.length})</span>
            </h3>
            <ul className="mt-2 space-y-2">
              {items.map((item, index) => (
                <li key={`${item.type}-${index}`} className="border-l-2 border-rule py-0.5 pl-4 text-ink">
                  {item.message}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
