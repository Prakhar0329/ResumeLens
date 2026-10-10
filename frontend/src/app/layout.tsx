import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-serif/400.css";
import "@fontsource/ibm-plex-serif/400-italic.css";
import "./globals.css";

import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import Navbar from "@/components/Navbar";
import { themeInitScript } from "@/components/ThemeToggle";

export const metadata: Metadata = {
  title: { default: "ResumeLens", template: "%s | ResumeLens" },
  description:
    "See how well your resume matches a job description, which skills are missing, and what to fix.",
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F6F8FB" },
    { media: "(prefers-color-scheme: dark)", color: "#0E1726" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Sets the theme class before paint to avoid a light/dark flash. */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="flex min-h-screen flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <Navbar />
        <main id="main" className="mx-auto w-full min-w-0 max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
          {children}
        </main>
        <footer className="border-t border-rule">
          <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-6 text-sm text-graphite sm:flex-row sm:justify-between sm:px-6">
            <p>ResumeLens scores are estimates to guide edits, not hiring decisions.</p>
            <p>Your resume text is never stored on the server.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
