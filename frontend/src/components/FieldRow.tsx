"use client";

import { useState } from "react";

import type { FieldState } from "@/lib/api";
import { CONTRACT_TYPES } from "@/lib/api";

interface FieldRowProps {
  fieldName: string;
  label: string;
  field: FieldState;
  onSave: (fieldName: string, value: string | null) => Promise<void>;
  /** Data usa <input type="date">; contract_type/uf usam <select>. */
  editorKind?: "text" | "date" | "contract_type" | "uf";
  longText?: boolean;
}

const UF_OPTIONS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
  "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

export function FieldRow({
  fieldName,
  label,
  field,
  onSave,
  editorKind = "text",
  longText = false,
}: FieldRowProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const corrected = field.corrected_value !== null;
  const absent = field.effective_value === null && field.is_valid;

  function startEditing() {
    setDraft(field.effective_value ?? "");
    setError(null);
    setEditing(true);
  }

  async function commit(value: string | null) {
    setSaving(true);
    setError(null);
    try {
      await onSave(fieldName, value);
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-1 border-b border-neutral-100 py-2 last:border-0">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-xs font-medium uppercase text-neutral-500">{label}</span>
        {!editing && (
          <button
            type="button"
            onClick={startEditing}
            className="text-xs text-blue-600 hover:underline"
          >
            Editar
          </button>
        )}
      </div>

      {editing ? (
        <div className="flex flex-col gap-1">
          <FieldEditor
            kind={editorKind}
            value={draft}
            onChange={setDraft}
            ufOptions={UF_OPTIONS}
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={saving}
              onClick={() => void commit(draft)}
              className="rounded bg-blue-600 px-2 py-1 text-xs text-white disabled:opacity-50"
            >
              Salvar
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => setEditing(false)}
              className="text-xs text-neutral-500 hover:underline"
            >
              Cancelar
            </button>
            {corrected && (
              <button
                type="button"
                disabled={saving}
                onClick={() => void commit(null)}
                className="text-xs text-neutral-500 hover:underline"
              >
                Restaurar original
              </button>
            )}
          </div>
          {error && (
            <p role="alert" className="text-xs text-red-600">
              {error}
            </p>
          )}
        </div>
      ) : (
        <div className={`text-sm ${longText ? "whitespace-pre-wrap" : ""}`}>
          {absent ? (
            <span className="text-neutral-400">—</span>
          ) : (
            <span>{field.effective_value}</span>
          )}
          {corrected && (
            <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">
              corrigido
            </span>
          )}
        </div>
      )}

      {!field.is_valid && !editing && (
        <p className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">
          <span className="font-medium">Validação falhou:</span> {field.validation_error}. Valor
          extraído: <span className="font-mono">{field.llm_value}</span>
        </p>
      )}
      {corrected && !editing && field.llm_value !== null && (
        <p className="text-xs text-neutral-400">
          Original do LLM: <span className="font-mono">{field.llm_value}</span>
        </p>
      )}
    </div>
  );
}

interface FieldEditorProps {
  kind: "text" | "date" | "contract_type" | "uf";
  value: string;
  onChange: (value: string) => void;
  ufOptions: string[];
}

function FieldEditor({ kind, value, onChange, ufOptions }: FieldEditorProps) {
  const className =
    "w-full rounded border border-neutral-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none";

  if (kind === "date") {
    return (
      <input
        type="date"
        aria-label="Editar valor"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={className}
      />
    );
  }
  if (kind === "contract_type") {
    return (
      <select
        aria-label="Editar valor"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={className}
      >
        <option value="">Selecione</option>
        {CONTRACT_TYPES.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
    );
  }
  if (kind === "uf") {
    return (
      <select
        aria-label="Editar valor"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={className}
      >
        <option value="">Selecione</option>
        {ufOptions.map((uf) => (
          <option key={uf} value={uf}>
            {uf}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      type="text"
      aria-label="Editar valor"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={className}
    />
  );
}
