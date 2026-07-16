import type { ContractStatus, PipelineStage } from "@/lib/api";

export const STAGE_LABELS: Record<PipelineStage, string> = {
  parse: "Lendo documento",
  extract: "Extraindo metadados",
  analyze: "Analisando com IA",
};

interface StatusBadgeProps {
  status: ContractStatus;
  currentStage: PipelineStage | null;
}

export function StatusBadge({ status, currentStage }: StatusBadgeProps) {
  if (status === "processing") {
    const stage = currentStage ? ` — ${STAGE_LABELS[currentStage]}` : "";
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-600" aria-hidden />
        Processando{stage}
      </span>
    );
  }
  if (status === "completed") {
    return (
      <span className="inline-flex items-center rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
        Concluído
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
      Falhou
    </span>
  );
}
