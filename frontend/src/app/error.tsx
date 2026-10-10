"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div role="alert" className="max-w-prose space-y-4">
      <h1 className="text-2xl font-semibold">This page hit an unexpected error</h1>
      <p className="text-graphite">
        Nothing was lost on the server. Try loading the page again; if it keeps happening, start a new
        analysis.
      </p>
      <div className="flex gap-3">
        <button type="button" className="btn-primary" onClick={reset}>
          Try again
        </button>
        <Link href="/" className="btn-secondary">
          Go to Analyze
        </Link>
      </div>
    </div>
  );
}
