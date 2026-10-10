"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import ErrorBanner from "@/components/ErrorBanner";
import JobDescriptionInput from "@/components/JobDescriptionInput";
import UploadDropzone from "@/components/UploadDropzone";
import { analyzeResume, ApiError, errorMessage } from "@/lib/api";
import { cacheAnalysis } from "@/lib/resultCache";
import { validateJobDescription } from "@/lib/validation";

/** Shown while waiting. The backend returns one response, so these advance on a timer. */
const PROGRESS_STEPS = ["Parsing PDF", "Extracting skills", "Scoring"] as const;
const STEP_MS = 1400;

const ERROR_TITLES: Record<string, string> = {
  unsupported_media_type: "That file isn't a PDF",
  file_too_large: "The file is too large",
  too_many_pages: "The resume has too many pages",
  unreadable_pdf: "We couldn't read text from that PDF",
  encrypted_pdf: "The PDF is password-protected",
  invalid_job_description: "Check the job description",
  rate_limited: "Too many requests",
  network_error: "Can't reach the server",
};

export default function AnalyzePage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [save, setSave] = useState(true);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<{ title: string; message: string } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    if (!loading) return;
    setStep(0);
    const timer = window.setInterval(
      () => setStep((current) => Math.min(current + 1, PROGRESS_STEPS.length - 1)),
      STEP_MS,
    );
    return () => window.clearInterval(timer);
  }, [loading]);

  const jdProblem = validateJobDescription(jdText);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError({ title: "Add your resume", message: "Choose a PDF of your resume to analyze." });
      return;
    }
    if (jdProblem) {
      setError({ title: "Check the job description", message: jdProblem });
      return;
    }
    setError(null);
    setLoading(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const result = await analyzeResume(file, jdText, save, controller.signal);
      cacheAnalysis(result);
      router.push(`/results/${result.analysis_id}`);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      const code = caught instanceof ApiError ? caught.code : "";
      setError({ title: ERROR_TITLES[code] ?? "Analysis failed", message: errorMessage(caught) });
      setLoading(false);
    }
  }

  return (
    <div className="space-y-10">
      <header className="max-w-prose">
        <h1 className="text-3xl font-semibold sm:text-[2.5rem] sm:leading-[1.15]">
          How well does your resume fit this job?
        </h1>
        <p className="mt-4 text-lg text-graphite">
          Upload your resume and paste a job description. You get a match score, the skills the posting asks
          for that your resume doesn&apos;t show, and specific edits to make.
        </p>
      </header>

      <form onSubmit={onSubmit} noValidate className="space-y-6" aria-busy={loading}>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <UploadDropzone file={file} onFileChange={setFile} disabled={loading} />
          <JobDescriptionInput value={jdText} onChange={setJdText} disabled={loading} />
        </div>

        <ErrorBanner message={error?.message ?? null} title={error?.title} onDismiss={() => setError(null)} />

        <div className="flex flex-col-reverse gap-4 border-t border-rule pt-6 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex cursor-pointer items-start gap-3 text-sm">
            <input
              type="checkbox"
              checked={save}
              onChange={(event) => setSave(event.target.checked)}
              disabled={loading}
              className="mt-0.5 h-4 w-4 rounded border-rule accent-lens"
            />
            <span>
              <span className="font-medium text-ink">Save to history</span>
              <span className="block text-graphite">
                Stores scores and skills only. Your resume text is never saved.
              </span>
            </span>
          </label>

          <div className="flex items-center gap-4">
            <p aria-live="polite" className="text-sm text-graphite">
              {loading ? `${PROGRESS_STEPS[step]}…` : ""}
            </p>
            <button type="submit" className="btn-primary min-w-[150px] py-2.5" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
                  Analyzing
                </>
              ) : (
                "Analyze resume"
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
