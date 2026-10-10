import Link from "next/link";

export default function NotFound() {
  return (
    <div className="max-w-prose space-y-4">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-graphite">The address may be mistyped, or the page has moved.</p>
      <Link href="/" className="btn-primary">
        Go to Analyze
      </Link>
    </div>
  );
}
