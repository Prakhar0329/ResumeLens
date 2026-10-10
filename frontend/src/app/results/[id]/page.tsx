"use client";

import { Check, ClipboardCopy, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import BulletRewriter from "@/components/BulletRewriter";
import ConfirmDialog from "@/components/ConfirmDialog";
import ErrorBanner from "@/components/ErrorBanner";
import RequirementMatches from "@/components/RequirementMatches";
import ResumeStats from "@/components/ResumeStats";
import ScoreBreakdown from "@/components/ScoreBreakdown";
import ScoreGauge from "@/components/ScoreGauge";
import SectionBars from "@/components/SectionBars";
import SkillChips from "@/components/SkillChips";
import Suggestions from "@/components/Suggestions";
import { ApiError, deleteAnalysis, errorMessage, getAnalysis } from "@/lib/api";
import { buildSummary, formatDate } from "@/lib/format";
import { forgetAnalysis, readCachedAnalysis } from "@/lib/resultCache";
import type { AnalysisResponse } from "@/types/api";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; analysis: AnalysisResponse }
  | { status: "missing" }
  | { status: "error"; message: string };

function Section({
  id,
  title,
  intro,
  children,
}: {
  id: string;
  title: string;
  intro?: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="border-t border-rule pt-8">
      <h2 id={id} className="section-title">
        {title}
      </h2>
      {intro ? <p className="mt-1 max-w-prose text-sm text-graphite">{intro}</p> : null}
      <div className="mt-5">{children}</div>
    </section>
  );
}

function ResultsSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading results" className="space-y-10">
      <div className="grid gap-10 md:grid-cols-[260px_1fr]">
        <div className="skeleton mx-auto h-[220px] w-[220px] rounded-full" />
        <div className="space-y-5">
          <div className="skeleton h-7 w-2/3" />
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-2">
              <div className="skeleton h-4 w-1/2" />
              <div className="skeleton h-2 w-full" />
            </div>
          ))}
        </div>
      </div>
      {[0, 1].map((i) => (
        <div key={i} className="space-y-3 border-t border-rule pt-8">
          <div className="skeleton h-5 w-48" />
          <div className="skeleton h-4 w-full" />
          <div className="skeleton h-4 w-5/6" />
        </div>
      ))}
    </div>
  );
}

export default function ResultsPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [copied, setCopied] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const cached = readCachedAnalysis(id);
    if (cached) {
      setState({ status: "ready", analysis: cached });
      return;
    }
    const controller = new AbortController();
    getAnalysis(id, controller.signal)
      .then((analysis) => setState({ status: "ready", analysis }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (error instanceof ApiError && error.status === 404) setState({ status: "missing" });
        else setState({ status: "error", message: errorMessage(error) });
      });
    return () => controller.abort();
  }, [id]);

  if (state.status === "loading") return <ResultsSkeleton />;

  if (state.status === "missing") {
    return (
      <div className="max-w-prose space-y-4">
        <h1 className="text-2xl font-semibold">This analysis isn&apos;t available</h1>
        <p className="text-graphite">
          It may have been deleted, or it was run with &ldquo;Save to history&rdquo; turned off and this
          browser tab has since been closed.
        </p>
        <div className="flex gap-3">
          <Link href="/" className="btn-primary">
            Analyze a resume
          </Link>
          <Link href="/history" className="btn-secondary">
            Open history
          </Link>
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="max-w-prose space-y-4">
        <h1 className="text-2xl font-semibold">Results couldn&apos;t be loaded</h1>
        <ErrorBanner message={state.message} title="Request failed" />
        <button type="button" className="btn-secondary" onClick={() => window.location.reload()}>
          Try again
        </button>
      </div>
    );
  }

  const { analysis } = state;
  const missingRequired = analysis.missing_skills.filter((s) => s.in_jd_as === "required");
  const jdContext = analysis.requirement_matches
    .slice(0, 5)
    .map((m) => m.requirement)
    .join(" ")
    .slice(0, 2000);

  async function copySummary() {
    try {
      await navigator.clipboard.writeText(buildSummary(analysis));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setActionError("Copying failed. Your browser blocked clipboard access.");
    }
  }

  async function confirmDelete() {
    setDeleting(true);
    setActionError(null);
    try {
      if (analysis.stored) await deleteAnalysis(analysis.analysis_id);
      forgetAnalysis(analysis.analysis_id);
      router.push(analysis.stored ? "/history" : "/");
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        forgetAnalysis(analysis.analysis_id);
        router.push("/history");
        return;
      }
      setActionError(errorMessage(error));
      setDeleting(false);
      setConfirmOpen(false);
    }
  }

  return (
    <article className="space-y-10">
      <h1 className="sr-only">Analysis results</h1>

      <div className="grid items-start gap-10 md:grid-cols-[260px_1fr]">
        <ScoreGauge score={analysis.overall_score} verdict={analysis.verdict} />
        <div>
          <p className="max-w-prose text-lg text-ink">
            {missingRequired.length === 0
              ? "Your resume shows every skill this posting marks as required."
              : `${missingRequired.length} required ${missingRequired.length === 1 ? "skill is" : "skills are"} missing: ${missingRequired
                  .slice(0, 4)
                  .map((s) => s.name)
                  .join(", ")}${missingRequired.length > 4 ? ", and more" : ""}.`}
          </p>
          <p className="mt-1 text-sm text-graphite">
            Analyzed {formatDate(analysis.created_at)}
            {analysis.stored ? ", saved to history" : ", not saved"}
          </p>
          <div className="mt-6">
            <ScoreBreakdown breakdown={analysis.score_breakdown} />
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <button type="button" className="btn-secondary" onClick={copySummary}>
              {copied ? (
                <Check aria-hidden className="h-4 w-4" />
              ) : (
                <ClipboardCopy aria-hidden className="h-4 w-4" />
              )}
              {copied ? "Summary copied" : "Copy summary"}
            </button>
            <Link href="/" className="btn-secondary">
              <Plus aria-hidden className="h-4 w-4" />
              New analysis
            </Link>
            <button type="button" className="btn-danger" onClick={() => setConfirmOpen(true)}>
              <Trash2 aria-hidden className="h-4 w-4" />
              Delete this analysis
            </button>
          </div>
          <div className="mt-4">
            <ErrorBanner message={actionError} onDismiss={() => setActionError(null)} />
          </div>
        </div>
      </div>

      <Section
        id="skills"
        title="Skills"
        intro="Skills found in the posting, checked against your resume. Required skills you are missing are underlined."
      >
        <div className="grid gap-8 lg:grid-cols-2">
          <SkillChips
            title="Missing"
            description="Asked for in the posting, not found on your resume."
            skills={analysis.missing_skills}
            variant="missing"
            emptyText="Nothing missing."
          />
          <SkillChips
            title="Matched"
            description="Asked for in the posting and present on your resume."
            skills={analysis.matched_skills}
            variant="matched"
            emptyText="No overlap found."
          />
        </div>
        <div className="mt-8">
          <SkillChips
            title="Also on your resume"
            description="Skills the posting doesn't mention. Keep the ones that support this role."
            skills={analysis.extra_skills}
            variant="extra"
            emptyText="None."
          />
        </div>
      </Section>

      <Section
        id="requirements"
        title="Requirement by requirement"
        intro="The posting's most important requirements, each paired with the line of your resume that comes closest to it."
      >
        <RequirementMatches matches={analysis.requirement_matches} redacted={analysis.redacted} />
      </Section>

      <Section id="suggestions" title="What to change">
        <Suggestions suggestions={analysis.suggestions} />
      </Section>

      <div className="grid gap-10 border-t border-rule pt-8 lg:grid-cols-2">
        <section aria-labelledby="sections">
          <h2 id="sections" className="section-title">
            Match by resume section
          </h2>
          <div className="mt-5">
            <SectionBars sections={analysis.section_scores} />
          </div>
        </section>
        <section aria-labelledby="stats">
          <h2 id="stats" className="section-title">
            Resume at a glance
          </h2>
          <div className="mt-5">
            <ResumeStats stats={analysis.resume_stats} />
          </div>
        </section>
      </div>

      <Section
        id="rewrite"
        title="Rewrite a bullet"
        intro="Paste one bullet and get a stronger version. Numbers you didn't write become placeholders like [X%] for you to fill in."
      >
        <div className="max-w-2xl">
          <BulletRewriter
            candidateSkills={analysis.missing_skills.map((s) => s.name)}
            jdContext={jdContext}
          />
        </div>
      </Section>

      <p className="border-t border-rule pt-6 text-xs text-graphite">
        Models: {analysis.model_info.embedding_model}, {analysis.model_info.spacy_model}. ResumeLens{" "}
        {analysis.model_info.version}. Analysis ID {analysis.analysis_id}.
      </p>

      <ConfirmDialog
        open={confirmOpen}
        title="Delete this analysis?"
        description={
          analysis.stored
            ? "This removes it from your history on the server. It can't be undone."
            : "This analysis wasn't saved; deleting clears it from this browser tab."
        }
        confirmLabel="Delete analysis"
        onConfirm={confirmDelete}
        onCancel={() => setConfirmOpen(false)}
        busy={deleting}
      />
    </article>
  );
}
