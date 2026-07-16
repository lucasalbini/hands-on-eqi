"use client";

import { useRouter } from "next/navigation";

import type { ContractListItem } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";

interface ContractsTableProps {
  contracts: ContractListItem[];
}

export function ContractsTable({ contracts }: ContractsTableProps) {
  const router = useRouter();

  if (contracts.length === 0) {
    return (
      <p className="rounded-lg border border-neutral-200 p-8 text-center text-neutral-500">
        Nenhum contrato enviado ainda.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-200">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase text-neutral-500">
          <tr>
            <th className="px-4 py-3">Arquivo</th>
            <th className="px-4 py-3">Tipo</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Enviado em</th>
          </tr>
        </thead>
        <tbody>
          {contracts.map((contract) => (
            <tr
              key={contract.id}
              onClick={() => router.push(`/contracts/${contract.id}`)}
              className="cursor-pointer border-b border-neutral-100 last:border-0 hover:bg-neutral-50"
            >
              <td className="px-4 py-3 font-medium">{contract.original_filename}</td>
              <td className="px-4 py-3">{contract.contract_type ?? "—"}</td>
              <td className="px-4 py-3">
                <StatusBadge status={contract.status} currentStage={contract.current_stage} />
              </td>
              <td className="px-4 py-3 text-neutral-500">
                {new Date(contract.created_at).toLocaleString("pt-BR")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
