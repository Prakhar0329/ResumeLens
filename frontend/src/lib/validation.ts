/** Client-side limits. They mirror the backend defaults (MAX_UPLOAD_MB, MIN/MAX_JD_CHARS);
 * the backend remains the source of truth and re-validates everything. */
export const MAX_UPLOAD_MB = 5;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;
export const MIN_JD_CHARS = 100;
export const MAX_JD_CHARS = 15000;

export function validateResumeFile(file: File): string | null {
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) return "Choose a PDF file. Export your resume from Word or Google Docs as PDF.";
  if (file.size === 0) return "This file is empty. Choose another PDF.";
  if (file.size > MAX_UPLOAD_BYTES)
    return `This PDF is larger than ${MAX_UPLOAD_MB} MB. Compress it or remove images.`;
  return null;
}

export function validateJobDescription(text: string): string | null {
  const length = text.trim().length;
  if (length < MIN_JD_CHARS) return `Paste at least ${MIN_JD_CHARS} characters of the job description.`;
  if (length > MAX_JD_CHARS)
    return `The job description is over ${MAX_JD_CHARS.toLocaleString("en-US")} characters.`;
  return null;
}
