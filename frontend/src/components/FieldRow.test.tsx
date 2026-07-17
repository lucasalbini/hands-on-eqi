import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { FieldState } from "@/lib/api";
import { FieldRow } from "./FieldRow";

function makeField(overrides: Partial<FieldState> = {}): FieldState {
  return {
    llm_value: "valor",
    normalized_value: "valor",
    is_valid: true,
    validation_error: null,
    corrected_value: null,
    effective_value: "valor",
    ...overrides,
  };
}

const noop = async () => {};

describe("FieldRow", () => {
  it("renderiza o valor efetivo de um campo válido", () => {
    render(<FieldRow fieldName="f" label="Campo" field={makeField()} onSave={noop} />);
    expect(screen.getByText("valor")).toBeDefined();
  });

  it("mostra alerta de validação com erro e valor bruto quando inválido", () => {
    render(
      <FieldRow
        fieldName="provider.cnpj"
        label="CNPJ"
        field={makeField({
          is_valid: false,
          validation_error: "dígito verificador inválido",
          normalized_value: null,
          effective_value: null,
          llm_value: "11.222.333/0001-80",
        })}
        onSave={noop}
      />,
    );
    expect(screen.getByText(/dígito verificador inválido/)).toBeDefined();
    expect(screen.getByText("11.222.333/0001-80")).toBeDefined();
  });

  it("mostra badge 'corrigido' e o valor original", () => {
    render(
      <FieldRow
        fieldName="provider.cidade"
        label="Cidade"
        field={makeField({
          corrected_value: "Joinville",
          effective_value: "Joinville",
          llm_value: "Curitiba",
        })}
        onSave={noop}
      />,
    );
    expect(screen.getByText("corrigido")).toBeDefined();
    expect(screen.getByText("Curitiba")).toBeDefined();
  });

  it("mostra traço quando o campo está ausente", () => {
    render(
      <FieldRow
        fieldName="customer.cnpj"
        label="CNPJ"
        field={makeField({ effective_value: null, llm_value: null, normalized_value: null })}
        onSave={noop}
      />,
    );
    expect(screen.getByText("—")).toBeDefined();
  });

  it("edita e chama onSave com o novo valor", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<FieldRow fieldName="f" label="Campo" field={makeField()} onSave={onSave} />);

    fireEvent.click(screen.getByText("Editar"));
    fireEvent.change(screen.getByLabelText("Editar valor"), { target: { value: "novo" } });
    fireEvent.click(screen.getByText("Salvar"));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith("f", "novo"));
  });

  it("restaura original enviando null", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <FieldRow
        fieldName="f"
        label="Campo"
        field={makeField({ corrected_value: "corrigido", effective_value: "corrigido" })}
        onSave={onSave}
      />,
    );

    fireEvent.click(screen.getByText("Editar"));
    fireEvent.click(screen.getByText("Restaurar original"));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith("f", null));
  });

  it("exibe erro do onSave (ex.: 422) sem fechar a edição", async () => {
    const onSave = vi.fn().mockRejectedValue(new Error("dígito verificador inválido"));
    render(<FieldRow fieldName="f" label="Campo" field={makeField()} onSave={onSave} />);

    fireEvent.click(screen.getByText("Editar"));
    fireEvent.click(screen.getByText("Salvar"));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "dígito verificador inválido",
    );
  });
});
