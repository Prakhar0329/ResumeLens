"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import ThemeToggle from "@/components/ThemeToggle";

const LINKS = [
  { href: "/", label: "Analyze", short: "Analyze" },
  { href: "/history", label: "History", short: "History" },
  { href: "/about", label: "How it works", short: "About" },
];

function LensMark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className="h-7 w-7">
      <circle cx="16" cy="16" r="12.5" fill="none" className="stroke-lens" strokeWidth="3.5" />
      <circle cx="16" cy="16" r="5" className="fill-highlight stroke-ink" strokeWidth="1.25" />
    </svg>
  );
}

export default function Navbar() {
  const pathname = usePathname();
  return (
    <header className="border-b border-rule bg-paper/90 backdrop-blur supports-[backdrop-filter]:bg-paper/75">
      <nav
        aria-label="Main"
        className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6"
      >
        <Link href="/" aria-label="ResumeLens home" className="flex items-center gap-2.5 rounded-md text-ink">
          <LensMark />
          {/* Wordmark hides on very narrow phones so the nav fits without sideways scrolling. */}
          <span className="hidden text-[17px] font-semibold tracking-tight min-[400px]:inline">
            ResumeLens
          </span>
        </Link>
        <div className="flex items-center gap-0.5 sm:gap-2">
          <ul className="flex items-center gap-0.5 text-sm sm:gap-1">
            {LINKS.map((link) => {
              const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    aria-current={active ? "page" : undefined}
                    className={`rounded-md px-1.5 py-1.5 sm:px-3 ${
                      active
                        ? "font-medium text-ink underline decoration-lens decoration-2 underline-offset-[6px]"
                        : "text-graphite hover:text-ink"
                    }`}
                  >
                    {link.short === link.label ? (
                      link.label
                    ) : (
                      <>
                        <span className="sm:hidden">{link.short}</span>
                        <span className="hidden sm:inline">{link.label}</span>
                      </>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}
