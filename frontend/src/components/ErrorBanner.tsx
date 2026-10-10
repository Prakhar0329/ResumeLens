import { AlertCircle, X } from "lucide-react";

interface ErrorBannerProps {
  message: string | null;
  title?: string;
  onDismiss?: () => void;
}

/** Inline error region. Always rendered so screen readers announce new messages. */
export default function ErrorBanner({ message, title = "That didn't work", onDismiss }: ErrorBannerProps) {
  return (
    <div role="alert" aria-live="assertive" aria-atomic="true">
      {message ? (
        <div className="flex items-start gap-3 rounded-md border border-redpen/40 bg-redpen/5 px-4 py-3 text-sm">
          <AlertCircle aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-redpen" />
          <div className="flex-1">
            <p className="font-medium text-redpen">{title}</p>
            <p className="mt-0.5 text-ink">{message}</p>
          </div>
          {onDismiss ? (
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss error"
              className="rounded p-0.5 text-graphite hover:text-ink"
            >
              <X aria-hidden className="h-4 w-4" />
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
