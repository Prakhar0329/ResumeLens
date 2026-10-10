import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import UploadDropzone from "@/components/UploadDropzone";

function pdf(name = "resume.pdf", size = 1024, type = "application/pdf"): File {
  const file = new File(["%PDF-1.4"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

function Harness({ onChange }: { onChange?: (file: File | null) => void }) {
  const [file, setFile] = useState<File | null>(null);
  return (
    <UploadDropzone
      file={file}
      onFileChange={(next) => {
        setFile(next);
        onChange?.(next);
      }}
    />
  );
}

describe("UploadDropzone", () => {
  it("accepts a valid PDF and shows its name and size", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await userEvent.upload(screen.getByTestId("file-input"), pdf("cv.pdf", 2048));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ name: "cv.pdf" }));
    expect(screen.getByText("cv.pdf")).toBeInTheDocument();
    expect(screen.getByText("2 KB, PDF")).toBeInTheDocument();
  });

  it("rejects files that are not PDFs", () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [pdf("resume.docx", 1000, "application/msword")] },
    });
    expect(onChange).toHaveBeenLastCalledWith(null);
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a PDF file");
  });

  it("rejects PDFs over 5 MB", () => {
    render(<Harness />);
    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [pdf("big.pdf", 5 * 1024 * 1024 + 1)] },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("larger than 5 MB");
  });

  it("accepts a dropped file", () => {
    render(<Harness />);
    fireEvent.drop(screen.getByTestId("dropzone"), { dataTransfer: { files: [pdf("dropped.pdf")] } });
    expect(screen.getByText("dropped.pdf")).toBeInTheDocument();
  });

  it("is keyboard operable and can remove the chosen file", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const zone = screen.getByRole("button", { name: "Resume" });
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const click = vi.spyOn(input, "click");
    zone.focus();
    await user.keyboard("{Enter}");
    expect(click).toHaveBeenCalled();

    await user.upload(input, pdf("cv.pdf"));
    await user.click(screen.getByRole("button", { name: "Remove cv.pdf" }));
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });
});
