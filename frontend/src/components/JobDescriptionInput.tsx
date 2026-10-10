"use client";

import { useId } from "react";

import { MAX_JD_CHARS, MIN_JD_CHARS } from "@/lib/validation";

interface JobDescriptionInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export default function JobDescriptionInput({ value, onChange, disabled = false }: JobDescriptionInputProps) {
  const id = useId();
  const length = value.trim().length;
  const tooShort = length > 0 && length < MIN_JD_CHARS;
  const tooLong = length > MAX_JD_CHARS;

  let status = `${length.toLocaleString("en-US")} / ${MAX_JD_CHARS.toLocaleString("en-US")} characters`;
  if (tooShort) status += ` (at least ${MIN_JD_CHARS} needed)`;
  if (tooLong) status += " (too long)";

  return (
    <div className="flex h-full flex-col">
      <label htmlFor={id} className="mb-2 text-sm font-medium text-ink">
        Job description
      </label>
      <textarea
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        rows={12}
        aria-describedby={`${id}-count`}
        aria-invalid={tooShort || tooLong}
        placeholder="Paste the full posting, including requirements and nice-to-haves."
        className="min-h-[180px] w-full flex-1 resize-y rounded-lg border border-rule bg-surface px-3.5 py-3 font-serif text-[15px] leading-relaxed text-ink placeholder:font-sans placeholder:text-graphite focus:border-lens focus:outline-none focus:ring-2 focus:ring-lens/30 disabled:opacity-60"
      />
      <p
        id={`${id}-count`}
        aria-live="polite"
        className={`mt-2 text-right text-sm tabular-nums ${tooShort || tooLong ? "text-redpen" : "text-graphite"}`}
      >
        {status}
      </p>
    </div>
  );
}
