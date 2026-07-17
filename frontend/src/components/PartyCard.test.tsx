import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { FieldState } from "@/lib/api";
import { PartyCard } from "./PartyCard";

function field(value: string | null): FieldState {
  return {
    llm_value: value,
    normalized_value: value,
    is_valid: true,
    validation_error: null,
    corrected_value: null,
    effective_value: value,
  };
}

const PROVIDER_FIELDS: Record<string, FieldState> = {
  "provider.razao_social": field("ACME LTDA"),
  "provider.cnpj": field("11.222.333/0001-81"),
  "provider.endereco": field("Rua das Flores, 100"),
  "provider.cidade": field("Curitiba"),
  "provider.uf": field("PR"),
  "provider.representante_nome": field("Maria Silva"),
  "provider.representante_cargo": field("Diretora"),
};

describe("PartyCard", () => {
  it("renderiza o título e os sete campos da parte", () => {
    render(<PartyCard role="provider" fields={PROVIDER_FIELDS} onSave={async () => {}} />);

    expect(screen.getByText("Contratada")).toBeDefined();
    for (const label of ["Razão social", "CNPJ", "Endereço", "Cidade", "UF", "Representante", "Cargo"]) {
      expect(screen.getByText(label)).toBeDefined();
    }
    expect(screen.getByText("ACME LTDA")).toBeDefined();
  });
});
