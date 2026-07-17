import { act, render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ContractDetail } from "@/lib/api";
import ContractDetailPage from "./page";

const swrMock = vi.fn();
vi.mock("swr", () => ({ default: (...args: unknown[]) => swrMock(...args) }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, getContract: vi.fn(), patchFields: vi.fn() };
});

function field(value: string | null) {
  return {
    llm_value: value,
    normalized_value: value,
    is_valid: true,
    validation_error: null,
    corrected_value: null,
    effective_value: value,
  };
}

function baseContract(overrides: Partial<ContractDetail> = {}): ContractDetail {
  return {
    id: "abc",
    original_filename: "contrato.pdf",
    status: "completed",
    current_stage: null,
    error_message: null,
    created_at: "2026-07-16T12:00:00Z",
    extraction: {
      prompt_version: "extraction_v1",
      model: "extraction-model",
      fields: {
        contract_type: field("Cloud"),
        issue_date: field("2025-11-11"),
        contract_object: field("Objeto do contrato."),
        "provider.razao_social": field("ACME LTDA"),
        "provider.cnpj": field("11.222.333/0001-81"),
        "provider.endereco": field("Rua 1"),
        "provider.cidade": field("Curitiba"),
        "provider.uf": field("PR"),
        "provider.representante_nome": field("Maria"),
        "provider.representante_cargo": field("Diretora"),
        "customer.razao_social": field("Cliente SA"),
        "customer.cnpj": field(null),
        "customer.endereco": field(null),
        "customer.cidade": field(null),
        "customer.uf": field(null),
        "customer.representante_nome": field(null),
        "customer.representante_cargo": field(null),
      },
    },
    analysis: null,
    ...overrides,
  };
}

async function renderPage() {
  // use(params) suspende; Suspense fornece o boundary e act aguarda a resolução.
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <ContractDetailPage params={Promise.resolve({ id: "abc" })} />
      </Suspense>,
    );
  });
}

afterEach(() => {
  swrMock.mockReset();
});

describe("ContractDetailPage", () => {
  it("mostra banner de estágio durante processing", async () => {
    swrMock.mockReturnValue({
      data: baseContract({ status: "processing", current_stage: "analyze", extraction: null }),
      error: undefined,
      mutate: vi.fn(),
    });

    await renderPage();

    // use(params) suspende até a promise resolver — findBy aguarda o render.
    expect(screen.getByText(/Analisando com IA/)).toBeDefined();
  });

  it("mostra banner de erro com estágio e mensagem quando failed", async () => {
    swrMock.mockReturnValue({
      data: baseContract({
        status: "failed",
        current_stage: "parse",
        error_message: "PDF sem texto extraível (OCR fora de escopo)",
      }),
      error: undefined,
      mutate: vi.fn(),
    });

    await renderPage();

    expect(screen.getByText(/Falhou no estágio parse/)).toBeDefined();
    expect(screen.getByText(/OCR fora de escopo/)).toBeDefined();
  });

  it("renderiza dados e partes quando completed", async () => {
    swrMock.mockReturnValue({
      data: baseContract(),
      error: undefined,
      mutate: vi.fn(),
    });

    await renderPage();

    expect(screen.getByText("Dados do contrato")).toBeDefined();
    expect(screen.getByText("Contratada")).toBeDefined();
    expect(screen.getByText("Contratante")).toBeDefined();
    expect(screen.getByText("ACME LTDA")).toBeDefined();
  });
});
