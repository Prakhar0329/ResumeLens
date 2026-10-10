import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SkillChips from "@/components/SkillChips";
import type { ExtraSkill, SkillItem } from "@/types/api";

const missing: SkillItem[] = [
  { name: "Kubernetes", category: "devops", in_jd_as: "required" },
  { name: "Terraform", category: "devops", in_jd_as: "preferred" },
  { name: "Django", category: "backend", in_jd_as: "required" },
];

describe("SkillChips", () => {
  it("groups skills by category in a stable order", () => {
    render(
      <SkillChips title="Missing" description="d" skills={missing} variant="missing" emptyText="none" />,
    );
    const terms = screen.getAllByRole("term").map((el) => el.textContent);
    expect(terms).toEqual(["Backend", "DevOps"]);
  });

  it("highlights missing required skills and labels nice-to-haves", () => {
    render(
      <SkillChips title="Missing" description="d" skills={missing} variant="missing" emptyText="none" />,
    );
    const kube = screen.getByText("Kubernetes");
    expect(kube).toHaveClass("mark-redpen");
    expect(kube.closest("li")).toHaveTextContent("required");
    const terraform = screen.getByText("Terraform");
    expect(terraform).not.toHaveClass("mark-redpen");
    expect(terraform.closest("li")).toHaveTextContent("nice to have");
  });

  it("renders matched skills with the highlighter style and a count", () => {
    const matched: SkillItem[] = [{ name: "Python", category: "language", in_jd_as: "required" }];
    render(
      <SkillChips title="Matched" description="d" skills={matched} variant="matched" emptyText="none" />,
    );
    const section = screen.getByTestId("skills-matched");
    expect(within(section).getByRole("heading")).toHaveTextContent("Matched (1)");
    expect(within(section).getByText("Python").closest("li")).toHaveClass("mark-highlight");
  });

  it("accepts extra skills without a requirement type", () => {
    const extra: ExtraSkill[] = [{ name: "C++", category: "language" }];
    render(<SkillChips title="Extra" description="d" skills={extra} variant="extra" emptyText="none" />);
    expect(screen.getByText("C++")).toBeInTheDocument();
    expect(screen.queryByText("required")).not.toBeInTheDocument();
  });

  it("shows the empty text when there are no skills", () => {
    render(
      <SkillChips
        title="Matched"
        description="d"
        skills={[]}
        variant="matched"
        emptyText="No overlap found."
      />,
    );
    expect(screen.getByText("No overlap found.")).toBeInTheDocument();
  });
});
