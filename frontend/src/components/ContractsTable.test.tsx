import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ContractListItem } from "@/lib/api";
import { ContractsTable } from "./ContractsTable";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const CONTRACT: ContractListItem = {
  id: "abc",
  original_filename: "contrato.pdf",
  status: "completed",
  current_stage: null,
  contract_type: "Cloud",
  created_at: "2026-07-16T12:00:00Z",
};

describe("ContractsTable", () => {
  it("renderiza linha com arquivo, tipo e badge de status", () => {
    render(<ContractsTable contracts={[CONTRACT]} />);

    expect(screen.getByText("contrato.pdf")).toBeDefined();
    expect(screen.getByText("Cloud")).toBeDefined();
    expect(screen.getByText("Concluído")).toBeDefined();
  });

  it("mostra estado vazio quando não há contratos", () => {
    render(<ContractsTable contracts={[]} />);
    expect(screen.getByText("Nenhum contrato enviado ainda.")).toBeDefined();
  });

  it("mostra traço quando tipo ainda não existe", () => {
    render(<ContractsTable contracts={[{ ...CONTRACT, contract_type: null }]} />);
    expect(screen.getByText("—")).toBeDefined();
  });
});
