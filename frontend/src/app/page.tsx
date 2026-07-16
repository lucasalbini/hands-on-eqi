"use client";

import useSWR from "swr";

import { ContractsTable } from "@/components/ContractsTable";
import { UploadDropzone } from "@/components/UploadDropzone";
import { listContracts } from "@/lib/api";

export default function Home() {
  const { data, error, mutate } = useSWR("contracts", listContracts, {
    // Polling só enquanto houver contrato em processamento.
    refreshInterval: (latest) =>
      latest?.some((c) => c.status === "processing") ? 2000 : 0,
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-8 p-8">
      <header>
        <h1 className="text-3xl font-semibold">Análise de Contratos</h1>
        <p className="mt-1 text-neutral-500">
          Envie um contrato (PDF/DOCX) para extrair metadados e gerar a análise.
        </p>
      </header>

      <UploadDropzone onUploaded={() => void mutate()} />

      {error ? (
        <p role="alert" className="text-sm text-red-600">
          Erro ao carregar contratos. Verifique se o backend está no ar.
        </p>
      ) : (
        <ContractsTable contracts={data ?? []} />
      )}
    </main>
  );
}
