// Client tipado da API do backend (espelha os schemas Pydantic de app/schemas.py).

export type ContractStatus = "processing" | "completed" | "failed";
export type PipelineStage = "parse" | "extract" | "analyze";

export const CONTRACT_TYPES = [
  "Desenvolvimento de Software",
  "Cloud",
  "Suporte",
  "Cibersegurança",
  "App Mobile",
  "Outro",
] as const;

export interface ContractCreated {
  id: string;
  status: ContractStatus;
}

export interface ContractStatusResponse {
  id: string;
  status: ContractStatus;
  current_stage: PipelineStage | null;
  error_message: string | null;
}

export interface ContractListItem {
  id: string;
  original_filename: string;
  status: ContractStatus;
  current_stage: PipelineStage | null;
  contract_type: string | null;
  created_at: string;
}

export interface FieldState {
  llm_value: string | null;
  normalized_value: string | null;
  is_valid: boolean;
  validation_error: string | null;
  corrected_value: string | null;
  effective_value: string | null;
}

export interface ExtractionDetail {
  prompt_version: string;
  model: string;
  fields: Record<string, FieldState>;
}

export interface Risk {
  title: string;
  description: string;
  severity: "alta" | "media" | "baixa";
  clause_ref: string | null;
}

export interface Obligation {
  party: "provider" | "customer";
  description: string;
  clause_ref: string | null;
}

export interface AttentionPoint {
  description: string;
  clause_ref: string | null;
}

export interface AiAnalysis {
  overall_assessment: string;
  risks: Risk[];
  obligations: Obligation[];
  attention_points: AttentionPoint[];
}

export interface AnalysisDetail {
  prompt_version: string;
  model: string;
  summary: string;
  ai_analysis: AiAnalysis;
}

export interface ContractDetail {
  id: string;
  original_filename: string;
  status: ContractStatus;
  current_stage: PipelineStage | null;
  error_message: string | null;
  created_at: string;
  extraction: ExtractionDetail | null;
  analysis: AnalysisDetail | null;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `Erro ${status}`);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = (await response.json())?.detail ?? null;
    } catch {
      // corpo não-JSON (ex.: HTML de erro do proxy) — segue com detail null
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export function uploadContract(file: File): Promise<ContractCreated> {
  const body = new FormData();
  body.append("file", file);
  return request<ContractCreated>("/api/v1/contracts", { method: "POST", body });
}

export function listContracts(): Promise<ContractListItem[]> {
  return request<ContractListItem[]>("/api/v1/contracts");
}

export function getContractStatus(id: string): Promise<ContractStatusResponse> {
  return request<ContractStatusResponse>(`/api/v1/contracts/${id}/status`);
}

export function getContract(id: string): Promise<ContractDetail> {
  return request<ContractDetail>(`/api/v1/contracts/${id}`);
}

export function patchFields(
  id: string,
  fields: Record<string, string | null>,
): Promise<ContractDetail> {
  return request<ContractDetail>(`/api/v1/contracts/${id}/fields`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields }),
  });
}
