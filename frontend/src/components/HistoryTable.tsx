"use client";

import { Trash2 } from "lucide-react";
import Link from "next/link";

import { formatDate, formatScore, verdictTone } from "@/lib/format";
import type { AnalysisSummary } from "@/types/api";

interface HistoryTableProps {
  items: AnalysisSummary[];
  onDelete: (id: string) => void;
  deletingId?: string | null;
}

export default function HistoryTable({ items, onDelete, deletingId = null }: HistoryTableProps) {
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[600px] border-collapse text-left text-sm">
        <caption className="sr-only">Saved analyses, newest first</caption>
        <thead>
          <tr className="border-b border-rule text-graphite">
            <th scope="col" className="py-2 pr-4 font-medium">
              Date
            </th>
            <th scope="col" className="py-2 pr-4 text-right font-medium">
              Score
            </th>
            <th scope="col" className="py-2 pr-4 font-medium">
              Verdict
            </th>
            <th scope="col" className="py-2 pr-4 font-medium">
              Top missing skills
            </th>
            <th scope="col" className="py-2 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const tone = verdictTone(item.verdict);
            return (
              <tr key={item.analysis_id} className="border-b border-rule/70 hover:bg-surface">
                <td className="py-3 pr-4">
                  <Link
                    href={`/results/${item.analysis_id}`}
                    className="font-medium text-lens underline-offset-4 hover:underline"
                  >
                    {formatDate(item.created_at)}
                  </Link>
                </td>
                <td className="py-3 pr-4 text-right text-base font-semibold tabular-nums text-ink">
                  {formatScore(item.overall_score)}
                </td>
                <td className={`py-3 pr-4 font-medium ${tone.text}`}>{item.verdict}</td>
                <td className="py-3 pr-4 text-ink">
                  {item.top_missing_skills.length ? (
                    item.top_missing_skills.join(", ")
                  ) : (
                    <span className="text-graphite">None</span>
                  )}
                </td>
                <td className="py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onDelete(item.analysis_id)}
                    disabled={deletingId === item.analysis_id}
                    className="rounded p-1.5 text-graphite hover:bg-redpen/10 hover:text-redpen disabled:opacity-50"
                    aria-label={`Delete analysis from ${formatDate(item.created_at)}`}
                  >
                    <Trash2 aria-hidden className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
