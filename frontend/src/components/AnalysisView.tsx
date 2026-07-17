import type { AiAnalysis, AnalysisDetail } from "@/lib/api";

const SEVERITY_STYLES: Record<string, string> = {
  alta: "bg-red-50 text-red-700",
  media: "bg-amber-50 text-amber-700",
  baixa: "bg-neutral-100 text-neutral-600",
};

const SEVERITY_LABELS: Record<string, string> = {
  alta: "Alta",
  media: "Média",
  baixa: "Baixa",
};

const PARTY_LABELS: Record<string, string> = {
  provider: "Contratada",
  customer: "Contratante",
};

export function SummaryCard({ summary }: { summary: string }) {
  return (
    <section className="rounded-lg border border-neutral-200 p-4">
      <h2 className="mb-2 text-lg font-semibold">Resumo executivo</h2>
      <p className="whitespace-pre-wrap text-sm text-neutral-700">{summary}</p>
    </section>
  );
}

export function AnalysisView({ analysis }: { analysis: AnalysisDetail }) {
  const { ai_analysis } = analysis;
  return (
    <section className="flex flex-col gap-4">
      <div className="rounded-lg border border-neutral-200 p-4">
        <h2 className="mb-2 text-lg font-semibold">Análise</h2>
        <p className="text-sm text-neutral-700">{ai_analysis.overall_assessment}</p>
      </div>
      <RiskList risks={ai_analysis.risks} />
      <ObligationList obligations={ai_analysis.obligations} />
      <AttentionList points={ai_analysis.attention_points} />
    </section>
  );
}

function RiskList({ risks }: { risks: AiAnalysis["risks"] }) {
  if (risks.length === 0) return null;
  return (
    <div className="rounded-lg border border-neutral-200 p-4">
      <h3 className="mb-2 font-semibold">Riscos</h3>
      <ul className="flex flex-col gap-3">
        {risks.map((risk, i) => (
          <li key={i} className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span
                className={`rounded px-1.5 py-0.5 text-xs font-medium ${SEVERITY_STYLES[risk.severity]}`}
              >
                {SEVERITY_LABELS[risk.severity]}
              </span>
              <span className="font-medium">{risk.title}</span>
              {risk.clause_ref && (
                <span className="text-xs text-neutral-400">{risk.clause_ref}</span>
              )}
            </div>
            <p className="text-sm text-neutral-600">{risk.description}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ObligationList({ obligations }: { obligations: AiAnalysis["obligations"] }) {
  if (obligations.length === 0) return null;
  return (
    <div className="rounded-lg border border-neutral-200 p-4">
      <h3 className="mb-2 font-semibold">Obrigações</h3>
      <ul className="flex flex-col gap-2">
        {obligations.map((obligation, i) => (
          <li key={i} className="text-sm">
            <span className="mr-2 rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-600">
              {PARTY_LABELS[obligation.party]}
            </span>
            {obligation.description}
            {obligation.clause_ref && (
              <span className="ml-2 text-xs text-neutral-400">{obligation.clause_ref}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AttentionList({ points }: { points: AiAnalysis["attention_points"] }) {
  if (points.length === 0) return null;
  return (
    <div className="rounded-lg border border-neutral-200 p-4">
      <h3 className="mb-2 font-semibold">Pontos de atenção</h3>
      <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-neutral-700">
        {points.map((point, i) => (
          <li key={i}>
            {point.description}
            {point.clause_ref && (
              <span className="ml-2 text-xs text-neutral-400">{point.clause_ref}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
