"use client";

import Link from "next/link";
import { use } from "react";
import useSWR from "swr";

import { AnalysisView, SummaryCard } from "@/components/AnalysisView";
import { FieldRow } from "@/components/FieldRow";
import { PartyCard } from "@/components/PartyCard";
import { STAGE_LABELS } from "@/components/StatusBadge";
import { getContract, patchFields } from "@/lib/api";

export default function ContractDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: contract, error, mutate } = useSWR(
    ["contract", id],
    () => getContract(id),
    {
      refreshInterval: (latest) => (latest?.status === "processing" ? 2000 : 0),
    },
  );

  async function handleSave(fieldName: string, value: string | null) {
    const updated = await patchFields(id, { [fieldName]: value });
    await mutate(updated, { revalidate: false });
  }

  if (error) {
    return (
      <Wrapper>
        <p role="alert" className="text-red-600">
          Contrato não encontrado ou backend indisponível.
        </p>
      </Wrapper>
    );
  }

  if (!contract) {
    return (
      <Wrapper>
        <p className="text-neutral-500">Carregando...</p>
      </Wrapper>
    );
  }

  return (
    <Wrapper>
      <header className="flex flex-col gap-1">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← Voltar
        </Link>
        <h1 className="text-2xl font-semibold">{contract.original_filename}</h1>
      </header>

      {contract.status === "processing" && (
        <div className="flex items-center gap-2 rounded-lg bg-blue-50 p-4 text-blue-700">
          <span className="h-2 w-2 animate-pulse rounded-full bg-blue-600" aria-hidden />
          {contract.current_stage
            ? STAGE_LABELS[contract.current_stage]
            : "Processando"}
          ...
        </div>
      )}

      {contract.status === "failed" && (
        <div role="alert" className="rounded-lg bg-red-50 p-4 text-red-700">
          <p className="font-medium">
            Falhou no estágio {contract.current_stage ?? "desconhecido"}.
          </p>
          {contract.error_message && <p className="text-sm">{contract.error_message}</p>}
        </div>
      )}

      {contract.extraction && (
        <>
          <section className="rounded-lg border border-neutral-200 p-4">
            <h2 className="mb-2 text-lg font-semibold">Dados do contrato</h2>
            <FieldRow
              fieldName="contract_type"
              label="Tipo"
              field={contract.extraction.fields["contract_type"]}
              onSave={handleSave}
              editorKind="contract_type"
            />
            <FieldRow
              fieldName="issue_date"
              label="Data de emissão"
              field={contract.extraction.fields["issue_date"]}
              onSave={handleSave}
              editorKind="date"
            />
            <FieldRow
              fieldName="contract_object"
              label="Objeto"
              field={contract.extraction.fields["contract_object"]}
              onSave={handleSave}
              longText
            />
          </section>

          <div className="grid gap-4 md:grid-cols-2">
            <PartyCard role="provider" fields={contract.extraction.fields} onSave={handleSave} />
            <PartyCard role="customer" fields={contract.extraction.fields} onSave={handleSave} />
          </div>
        </>
      )}

      {contract.analysis && (
        <>
          <SummaryCard summary={contract.analysis.summary} />
          <AnalysisView analysis={contract.analysis} />
        </>
      )}
    </Wrapper>
  );
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-6 p-8">{children}</main>
  );
}
