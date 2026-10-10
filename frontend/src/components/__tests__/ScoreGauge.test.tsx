import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ScoreGauge from "@/components/ScoreGauge";

describe("ScoreGauge", () => {
  it("shows the score with one decimal and the verdict", () => {
    render(<ScoreGauge score={72.46} verdict="Strong match" />);
    expect(screen.getByTestId("score-value")).toHaveTextContent("72.5");
    expect(screen.getByTestId("score-verdict")).toHaveTextContent("Strong match");
    expect(screen.getByRole("figure")).toHaveAccessibleName("Match score 72.5 out of 100, Strong match");
  });

  it("uses the verdict colour", () => {
    render(<ScoreGauge score={20} verdict="Weak match" />);
    expect(screen.getByTestId("score-verdict")).toHaveClass("text-redpen");
    expect(screen.getByTestId("score-arc")).toHaveClass("stroke-redpen");
  });

  it("fills the arc in proportion to the score", () => {
    render(<ScoreGauge score={50} verdict="Partial match" />);
    const arc = screen.getByTestId("score-arc");
    const circumference = 2 * Math.PI * 84;
    expect(Number(arc.style.strokeDashoffset)).toBeCloseTo(circumference / 2, 3);
  });

  it("clamps out-of-range scores", () => {
    render(<ScoreGauge score={140} verdict="Excellent match" />);
    expect(screen.getByTestId("score-value")).toHaveTextContent("100.0");
    expect(Number(screen.getByTestId("score-arc").style.strokeDashoffset)).toBeCloseTo(0, 5);
  });
});
