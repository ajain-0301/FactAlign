import { afterEach, describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { VerificationView } from "@/components/features/verification-view";
import { api } from "@/lib/api";
import type { Verification } from "@/lib/types";

const result: Verification = {
  method: "claim_nli", method_label: "Atomic claims · multilingual XLM-R NLI", is_ai_verification: true,
  limitations: "Scores are uncalibrated.",
  metrics: { n_claims: 1, supported: 0, contradicted: 0, unverifiable: 0, unsupported: 0, uncertain: 1,
    support_rate: 0, contradiction_rate: 0, unverifiable_rate: 0, unsupported_rate: 0,
    mean_claim_score: 95, contradiction_count: 0, formula: "supported / total" },
  claims: [{ claim: "दस विद्यालय खुले।", status: "uncertain", confidence: null, support_score: 95,
    contradiction_warning: true, conflicting_evidence: true, explanation: "Conflicting evidence.",
    evidence: "Ten schools opened.", method: "claim_nli", evidence_passages: [{ passage_id: 0,
      text: "Ten schools opened.", page: 3, start: 10, end: 29, retrieval_similarity: .99,
      nli: { entailment: .95, contradiction: .03, neutral: .02 },
      checks: [{ name: "numbers", passed: false, outcome: "mismatch", detail: "ten versus seven" }] }] }],
};

afterEach(() => vi.unstubAllGlobals());

describe("claim-level reporting", () => {
  it("renders scores, source pages, conflicts, and mismatches without calling a backend", () => {
    const html = renderToStaticMarkup(createElement(VerificationView, { v: result }));
    for (const text of ["Uncertain", "Uncalibrated support score", "95.0/100", "Page 3", "Entailment", "Contradiction", "Neutral", "ten versus seven", "Conflicting source passages", "not a probability", "Mean claim score"]) {
      expect(html).toContain(text);
    }
    expect(html).not.toContain("confidence 95");
  });
  it("filters four-way claim labels", () => {
    const html = renderToStaticMarkup(createElement(VerificationView, { v: result, filter: "supported" }));
    expect(html).not.toContain("दस विद्यालय खुले।");
  });
  it("sends page references and the new method through the existing client", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(result), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const body = { source: "Ten schools opened.", summary: "दस विद्यालय खुले।", method: "claim_nli" as const,
      source_pages: [{ page: 3, start: 0, end: 19 }] };
    expect((await api.verify(body)).claims[0].status).toBe("uncertain");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(body);
  });
});
