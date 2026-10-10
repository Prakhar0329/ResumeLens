"use client";

import { Check, Copy, Loader2, Wand2 } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import ErrorBanner from "@/components/ErrorBanner";
import { ApiError, errorMessage, rewriteBullet } from "@/lib/api";
import type { RewriteResponse } from "@/types/api";

interface BulletRewriterProps {
  /** Skill names the user may want the rewrite to emphasise (usually missing skills). */
  candidateSkills: string[];
  /** Optional short JD context sent to the model. */
  jdContext?: string;
}

const MAX_TARGETS = 10;

export default function BulletRewriter({ candidateSkills, jdContext }: BulletRewriterProps) {
  const id = useId();
  const [bullet, setBullet] = useState("");
  const [targets, setTargets] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RewriteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [copied, setCopied] = useState(false);

  function toggle(skill: string) {
    setTargets((current) =>
      current.includes(skill)
        ? current.filter((s) => s !== skill)
        : current.length < MAX_TARGETS
          ? [...current, skill]
          : current,
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (bullet.trim().length < 5) {
      setError("Paste a bullet of at least a few words.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    setCopied(false);
    try {
      setResult(
        await rewriteBullet({ bullet: bullet.trim(), target_skills: targets, jd_context: jdContext ?? null }),
      );
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 501) setUnavailable(true);
      else setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  async function copy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.rewritten);
      setCopied(true);
    } catch {
      setError("Copying failed. Select the text and copy it manually.");
    }
  }

  if (unavailable) {
    return (
      <div className="rounded-md border border-rule bg-surface px-4 py-3 text-sm" role="status">
        <p className="font-medium text-ink">Bullet rewriting is turned off on this server.</p>
        <p className="mt-1 text-graphite">
          It needs an Anthropic API key. Whoever runs the backend can set <code>ANTHROPIC_API_KEY</code> in{" "}
          <code>backend/.env</code> and restart it. Everything else on this page works without it.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div>
        <label htmlFor={`${id}-bullet`} className="mb-2 block text-sm font-medium text-ink">
          A bullet from your resume
        </label>
        <textarea
          id={`${id}-bullet`}
          value={bullet}
          onChange={(event) => setBullet(event.target.value)}
          rows={3}
          maxLength={600}
          placeholder="Worked on the backend API for the student portal."
          className="w-full rounded-lg border border-rule bg-surface px-3.5 py-2.5 font-serif text-ink placeholder:font-sans placeholder:text-graphite focus:border-lens focus:outline-none focus:ring-2 focus:ring-lens/30"
        />
      </div>
      {candidateSkills.length > 0 ? (
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-ink">
            Skills to emphasise, only if the bullet genuinely involved them
          </legend>
          <div className="flex flex-wrap gap-2">
            {candidateSkills.slice(0, 20).map((skill) => {
              const checked = targets.includes(skill);
              return (
                <label
                  key={skill}
                  className={`cursor-pointer rounded border px-2 py-0.5 text-sm ${
                    checked ? "border-lens bg-lens/10 text-ink" : "border-rule text-graphite hover:text-ink"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={checked}
                    onChange={() => toggle(skill)}
                  />
                  {skill}
                </label>
              );
            })}
          </div>
        </fieldset>
      ) : null}
      <ErrorBanner message={error} onDismiss={() => setError(null)} />
      <button type="submit" className="btn-secondary" disabled={loading}>
        {loading ? (
          <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
        ) : (
          <Wand2 aria-hidden className="h-4 w-4" />
        )}
        Rewrite bullet
      </button>
      <div aria-live="polite">
        {result ? (
          <div className="rounded-lg border border-lens/40 bg-lens/5 px-4 py-3">
            <p className="doc-quote">{result.rewritten}</p>
            {result.placeholders.length > 0 ? (
              <p className="mt-2 text-sm text-graphite">
                Replace {result.placeholders.join(", ")} with your real numbers, or remove them. ResumeLens
                never invents metrics.
              </p>
            ) : null}
            <button type="button" onClick={copy} className="btn-secondary mt-3 px-3 py-1.5">
              {copied ? <Check aria-hidden className="h-4 w-4" /> : <Copy aria-hidden className="h-4 w-4" />}
              {copied ? "Copied" : "Copy bullet"}
            </button>
          </div>
        ) : null}
      </div>
    </form>
  );
}
