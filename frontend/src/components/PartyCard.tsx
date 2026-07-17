"use client";

import type { FieldState } from "@/lib/api";
import { FieldRow } from "./FieldRow";

interface PartyCardProps {
  role: "provider" | "customer";
  fields: Record<string, FieldState>;
  onSave: (fieldName: string, value: string | null) => Promise<void>;
}

const TITLES: Record<PartyCardProps["role"], string> = {
  provider: "Contratada",
  customer: "Contratante",
};

const PARTY_FIELDS: { key: string; label: string; kind?: "uf" }[] = [
  { key: "razao_social", label: "Razão social" },
  { key: "cnpj", label: "CNPJ" },
  { key: "endereco", label: "Endereço" },
  { key: "cidade", label: "Cidade" },
  { key: "uf", label: "UF", kind: "uf" },
  { key: "representante_nome", label: "Representante" },
  { key: "representante_cargo", label: "Cargo" },
];

export function PartyCard({ role, fields, onSave }: PartyCardProps) {
  return (
    <section className="rounded-lg border border-neutral-200 p-4">
      <h3 className="mb-2 font-semibold">{TITLES[role]}</h3>
      {PARTY_FIELDS.map(({ key, label, kind }) => {
        const fieldName = `${role}.${key}`;
        const field = fields[fieldName];
        if (!field) return null;
        return (
          <FieldRow
            key={fieldName}
            fieldName={fieldName}
            label={label}
            field={field}
            onSave={onSave}
            editorKind={kind ?? "text"}
          />
        );
      })}
    </section>
  );
}
