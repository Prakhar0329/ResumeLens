import { CATEGORY_LABELS, groupByCategory } from "@/lib/format";
import type { ExtraSkill, SkillItem } from "@/types/api";

type Variant = "matched" | "missing" | "extra";

interface SkillChipsProps {
  title: string;
  description: string;
  skills: Array<SkillItem | ExtraSkill>;
  variant: Variant;
  emptyText: string;
}

function chipClass(variant: Variant, skill: SkillItem | ExtraSkill): string {
  const base = "inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-sm";
  if (variant === "matched") return `${base} mark-highlight`;
  if (variant === "missing") {
    const required = "in_jd_as" in skill && skill.in_jd_as === "required";
    return required
      ? `${base} border border-redpen/50 bg-redpen/5 font-medium text-ink`
      : `${base} border border-rule bg-surface text-ink`;
  }
  return `${base} border border-dashed border-rule text-graphite`;
}

function tagFor(skill: SkillItem | ExtraSkill): string | null {
  if (!("in_jd_as" in skill)) return null;
  if (skill.in_jd_as === "required") return "required";
  if (skill.in_jd_as === "preferred") return "nice to have";
  return null;
}

export default function SkillChips({ title, description, skills, variant, emptyText }: SkillChipsProps) {
  const groups = groupByCategory(skills);
  return (
    <section aria-label={title} data-testid={`skills-${variant}`}>
      <h3 className="font-semibold text-ink">
        {title} <span className="font-normal text-graphite">({skills.length})</span>
      </h3>
      <p className="mt-1 text-sm text-graphite">{description}</p>
      {groups.length === 0 ? (
        <p className="mt-3 text-sm text-graphite">{emptyText}</p>
      ) : (
        <dl className="mt-3 space-y-3">
          {groups.map((group) => (
            <div key={group.category} className="grid gap-1.5 sm:grid-cols-[120px_1fr] sm:gap-3">
              <dt className="pt-0.5 text-sm text-graphite">{CATEGORY_LABELS[group.category]}</dt>
              <dd>
                <ul className="flex flex-wrap gap-1.5">
                  {group.items.map((skill) => {
                    const tag = tagFor(skill);
                    return (
                      <li key={skill.name} className={chipClass(variant, skill)}>
                        <span
                          className={variant === "missing" && tag === "required" ? "mark-redpen" : undefined}
                        >
                          {skill.name}
                        </span>
                        {tag && variant === "missing" ? (
                          <span className={`text-xs ${tag === "required" ? "text-redpen" : "text-graphite"}`}>
                            {tag}
                          </span>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
