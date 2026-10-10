"use client";

import { FileText, Upload, X } from "lucide-react";
import { useId, useRef, useState, type DragEvent, type KeyboardEvent } from "react";

import { formatBytes } from "@/lib/format";
import { MAX_UPLOAD_MB, validateResumeFile } from "@/lib/validation";

interface UploadDropzoneProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  disabled?: boolean;
}

export default function UploadDropzone({ file, onFileChange, disabled = false }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hintId = useId();
  const errorId = useId();

  function accept(candidate: File | undefined | null) {
    if (!candidate) return;
    const problem = validateResumeFile(candidate);
    setError(problem);
    onFileChange(problem ? null : candidate);
  }

  function openPicker() {
    if (!disabled) inputRef.current?.click();
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPicker();
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!disabled) accept(event.dataTransfer.files[0]);
  }

  function clear() {
    setError(null);
    onFileChange(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div>
      <p id={`${hintId}-label`} className="mb-2 text-sm font-medium text-ink">
        Resume
      </p>
      {file ? (
        <div className="flex items-center gap-3 rounded-lg border border-rule bg-surface px-4 py-4">
          <FileText aria-hidden className="h-8 w-8 shrink-0 text-lens" />
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-ink" title={file.name}>
              {file.name}
            </p>
            <p className="text-sm text-graphite">{formatBytes(file.size)}, PDF</p>
          </div>
          <button
            type="button"
            onClick={clear}
            disabled={disabled}
            className="btn-secondary px-2.5"
            aria-label={`Remove ${file.name}`}
          >
            <X aria-hidden className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <div
          role="button"
          tabIndex={disabled ? -1 : 0}
          aria-labelledby={`${hintId}-label`}
          aria-describedby={`${hintId} ${error ? errorId : ""}`.trim()}
          aria-disabled={disabled}
          onClick={openPicker}
          onKeyDown={onKeyDown}
          onDragOver={(event) => {
            event.preventDefault();
            if (!disabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          data-testid="dropzone"
          className={`flex min-h-[180px] cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
            dragging ? "border-lens bg-lens/5" : "border-rule bg-surface hover:border-graphite"
          } ${error ? "border-redpen/60" : ""} ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
        >
          <Upload aria-hidden className="h-7 w-7 text-graphite" />
          <div>
            <p className="font-medium text-ink">Drop your resume here, or click to choose a file</p>
            <p id={hintId} className="mt-1 text-sm text-graphite">
              PDF with selectable text, up to {MAX_UPLOAD_MB} MB and 10 pages
            </p>
          </div>
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        data-testid="file-input"
        onChange={(event) => accept(event.target.files?.[0])}
      />
      <p id={errorId} role="alert" className="mt-2 min-h-[1.25rem] text-sm text-redpen">
        {error ?? ""}
      </p>
    </div>
  );
}
