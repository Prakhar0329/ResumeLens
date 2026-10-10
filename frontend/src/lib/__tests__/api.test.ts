import { afterEach, describe, expect, it, vi } from "vitest";

import { analyzeResume, ApiError, getAnalysis, rewriteBullet } from "@/lib/api";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue(
    new Response(body === undefined ? "" : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("maps the backend error format to ApiError", async () => {
    mockFetch(413, { error: { code: "file_too_large", message: "Resume must be at most 5 MB." } });
    const error = await getAnalysis("abc").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 413,
      code: "file_too_large",
      message: "Resume must be at most 5 MB.",
    });
  });

  it("handles non-JSON error bodies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>bad gateway</html>", { status: 502 })),
    );
    await expect(getAnalysis("abc")).rejects.toMatchObject({ code: "http_error", status: 502 });
  });

  it("reports network failures clearly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(getAnalysis("abc")).rejects.toMatchObject({ code: "network_error", status: 0 });
  });

  it("sends multipart form data for analyze", async () => {
    const fetchMock = mockFetch(200, { analysis_id: "1" });
    await analyzeResume(new File(["%PDF"], "cv.pdf", { type: "application/pdf" }), "jd text", false);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/analyze");
    expect(init.method).toBe("POST");
    const form = init.body as FormData;
    expect(form.get("jd_text")).toBe("jd text");
    expect(form.get("save")).toBe("false");
    expect((form.get("resume") as File).name).toBe("cv.pdf");
  });

  it("exposes 501 for the optional rewriter", async () => {
    mockFetch(501, { error: { code: "feature_unavailable", message: "disabled" } });
    await expect(rewriteBullet({ bullet: "Worked on API", target_skills: [] })).rejects.toMatchObject({
      status: 501,
    });
  });
});
