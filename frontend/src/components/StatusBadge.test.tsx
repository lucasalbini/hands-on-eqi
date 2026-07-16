import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("mostra 'Processando' com o estágio atual", () => {
    render(<StatusBadge status="processing" currentStage="extract" />);
    expect(screen.getByText(/Processando — Extraindo metadados/)).toBeDefined();
  });

  it("mostra 'Concluído' para completed", () => {
    render(<StatusBadge status="completed" currentStage={null} />);
    expect(screen.getByText("Concluído")).toBeDefined();
  });

  it("mostra 'Falhou' para failed", () => {
    render(<StatusBadge status="failed" currentStage={null} />);
    expect(screen.getByText("Falhou")).toBeDefined();
  });
});
