export type SectionStatus = {
  name: string;
  available: boolean;
  status: string;
  note: string;
};

export type OpsSummary = {
  contract_version: string;
  readonly: boolean;
  overall_status: string;
  sections: SectionStatus[];
  warnings?: string[];
};

export type RuntimeProfile = {
  contract_version: string;
  stage: string;
  mode: string;
  provider?: string;
  command_env_var?: string;
  command_fingerprint?: string;
};

export type QualitySummary = {
  contract_version: string;
  readonly: boolean;
  total_count: number;
  open_count: number;
  resolved_count?: number;
};

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { method: 'GET' });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getOpsSummary(): Promise<OpsSummary> {
  return fetchJson<OpsSummary>('/product/agentops/summary');
}

export function getRuntimeProfile(stage: string): Promise<RuntimeProfile> {
  return fetchJson<RuntimeProfile>(`/product/agentops/runtime/${encodeURIComponent(stage)}`);
}

export function getQualitySummary(): Promise<QualitySummary> {
  return fetchJson<QualitySummary>('/product/agentops/quality');
}
