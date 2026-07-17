import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AnalysisDetail } from "@/lib/api";
import { AnalysisView, SummaryCard } from "./AnalysisView";

const ANALYSIS: AnalysisDetail = {
  prompt_version: "analysis_v1",
  model: "analysis-model",
  summary: "Resumo do contrato.",
  ai_analysis: {
    overall_assessment: "Contrato equilibrado.",
    risks: [
      {
        title: "Multa alta",
        description: "Multa de 50%.",
        severity: "alta",
        clause_ref: "Cláusula 8ª",
      },
    ],
    obligations: [{ party: "provider", description: "Relatório mensal.", clause_ref: null }],
    attention_points: [{ description: "Foro difere da sede.", clause_ref: null }],
  },
};

describe("AnalysisView", () => {
  it("renderiza avaliação, risco com severidade e obrigação por parte", () => {
    render(<AnalysisView analysis={ANALYSIS} />);

    expect(screen.getByText("Contrato equilibrado.")).toBeDefined();
    expect(screen.getByText("Alta")).toBeDefined();
    expect(screen.getByText("Multa alta")).toBeDefined();
    expect(screen.getByText("Contratada")).toBeDefined();
    expect(screen.getByText("Foro difere da sede.")).toBeDefined();
  });

  it("SummaryCard mostra o resumo", () => {
    render(<SummaryCard summary="Resumo do contrato." />);
    expect(screen.getByText("Resumo do contrato.")).toBeDefined();
  });
});
