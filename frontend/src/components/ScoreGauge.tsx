import type { CSSProperties } from "react";

import { formatScore, verdictTone } from "@/lib/format";
import type { Verdict } from "@/types/api";

interface ScoreGaugeProps {
  score: number;
  verdict: Verdict;
  size?: number;
}

const TICKS = 60;

/**
 * Circular score "aperture": an outer ring of ticks (one per ~1.7 points) and an arc that
 * fills to the score. The arc animates once on mount; reduced-motion users see it static.
 */
export default function ScoreGauge({ score, verdict, size = 220 }: ScoreGaugeProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = 84;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);
  const tone = verdictTone(verdict);
  const litTicks = Math.round((clamped / 100) * TICKS);

  const arcStyle = {
    "--gauge-circumference": `${circumference}`,
    "--gauge-offset": `${offset}`,
    strokeDasharray: circumference,
    strokeDashoffset: offset,
  } as CSSProperties;

  return (
    <figure
      className="flex flex-col items-center"
      aria-label={`Match score ${formatScore(clamped)} out of 100, ${verdict}`}
    >
      <svg
        viewBox="0 0 220 220"
        width={size}
        height={size}
        role="img"
        aria-hidden
        className="max-w-full"
        data-testid="score-gauge"
      >
        <g transform="translate(110 110)">
          {Array.from({ length: TICKS }, (_, i) => {
            const angle = (i / TICKS) * 2 * Math.PI - Math.PI / 2;
            const inner = 99;
            const outer = i % 5 === 0 ? 107 : 104;
            return (
              <line
                key={i}
                x1={Math.cos(angle) * inner}
                y1={Math.sin(angle) * inner}
                x2={Math.cos(angle) * outer}
                y2={Math.sin(angle) * outer}
                strokeWidth={i % 5 === 0 ? 2 : 1}
                className={i < litTicks ? tone.stroke : "stroke-rule"}
              />
            );
          })}
          <circle r={radius} fill="none" strokeWidth="14" className="stroke-rule/60" />
          <circle
            r={radius}
            fill="none"
            strokeWidth="14"
            strokeLinecap="round"
            transform="rotate(-90)"
            className={`${tone.stroke} motion-safe:animate-gauge-fill`}
            style={arcStyle}
            data-testid="score-arc"
          />
          <circle r="62" className="fill-surface" />
        </g>
        <text
          x="110"
          y="112"
          textAnchor="middle"
          className="fill-ink text-[44px] font-semibold tabular-nums"
          data-testid="score-value"
        >
          {formatScore(clamped)}
        </text>
        <text x="110" y="138" textAnchor="middle" className="fill-graphite text-[13px]">
          out of 100
        </text>
      </svg>
      <figcaption className={`mt-3 text-lg font-semibold ${tone.text}`} data-testid="score-verdict">
        {verdict}
      </figcaption>
    </figure>
  );
}
