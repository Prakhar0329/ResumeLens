"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import ConfirmDialog from "@/components/ConfirmDialog";
import ErrorBanner from "@/components/ErrorBanner";
import HistoryTable from "@/components/HistoryTable";
import { deleteAllAnalyses, deleteAnalysis, errorMessage, listAnalyses } from "@/lib/api";
import { forgetAllAnalyses, forgetAnalysis } from "@/lib/resultCache";
import type { AnalysisList } from "@/types/api";

const PAGE_SIZE = 20;

function HistorySkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading history" className="space-y-3">
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="skeleton h-10 w-full" />
      ))}
    </div>
  );
}

export default function HistoryPage() {
  const [data, setData] = useState<AnalysisList | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmAll, setConfirmAll] = useState(false);
  const [busyAll, setBusyAll] = useState(false);
  const [status, setStatus] = useState("");

  const load = useCallback(async (nextOffset: number, signal?: AbortSignal) => {
    setLoading(true);
    try {
      const result = await listAnalyses(PAGE_SIZE, nextOffset, signal);
      // Deleting the last item on a page leaves it empty: step back a page.
      if (result.items.length === 0 && nextOffset > 0) {
        setOffset(Math.max(0, nextOffset - PAGE_SIZE));
        return;
      }
      setData(result);
      setError(null);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(offset, controller.signal);
    return () => controller.abort();
  }, [offset, load]);

  async function onDelete(id: string) {
    setDeletingId(id);
    try {
      await deleteAnalysis(id);
      forgetAnalysis(id);
      setStatus("Analysis deleted.");
      await load(offset);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setDeletingId(null);
    }
  }

  async function onDeleteAll() {
    setBusyAll(true);
    try {
      const result = await deleteAllAnalyses();
      forgetAllAnalyses();
      setStatus(`Deleted ${result.deleted} ${result.deleted === 1 ? "analysis" : "analyses"}.`);
      setOffset(0);
      await load(0);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusyAll(false);
      setConfirmAll(false);
    }
  }

  const total = data?.total ?? 0;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-prose">
          <h1 className="text-3xl font-semibold">History</h1>
          <p className="mt-2 text-graphite">
            Saved analyses keep scores, skills and suggestions. Resume text is never stored, so the
            requirement table shows job requirements only.
          </p>
        </div>
        {total > 0 ? (
          <button
            type="button"
            className="btn-danger self-start sm:self-auto"
            onClick={() => setConfirmAll(true)}
          >
            Delete all history
          </button>
        ) : null}
      </div>

      <p aria-live="polite" className="sr-only">
        {status}
      </p>
      <ErrorBanner message={error} title="History couldn't be loaded" onDismiss={() => setError(null)} />

      {loading && !data ? (
        <HistorySkeleton />
      ) : data && data.items.length > 0 ? (
        <>
          <HistoryTable items={data.items} onDelete={onDelete} deletingId={deletingId} />
          {total > PAGE_SIZE ? (
            <nav aria-label="History pages" className="flex items-center justify-between text-sm">
              <p className="text-graphite">
                {offset + 1} to {pageEnd} of {total}
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={offset === 0 || loading}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  Newer
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={pageEnd >= total || loading}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Older
                </button>
              </div>
            </nav>
          ) : null}
        </>
      ) : !error ? (
        <div className="rounded-lg border border-dashed border-rule px-6 py-12 text-center">
          <p className="font-medium text-ink">No saved analyses yet</p>
          <p className="mt-1 text-sm text-graphite">
            Analyses run with &ldquo;Save to history&rdquo; turned on appear here.
          </p>
          <Link href="/" className="btn-primary mt-5">
            Analyze a resume
          </Link>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirmAll}
        title="Delete all history?"
        description={`This permanently removes all ${total} saved ${total === 1 ? "analysis" : "analyses"} from the server.`}
        confirmLabel="Delete everything"
        onConfirm={onDeleteAll}
        onCancel={() => setConfirmAll(false)}
        busy={busyAll}
      />
    </div>
  );
}
