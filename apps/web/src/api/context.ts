export type ContextSource = {
  name: string;
  configured: boolean;
  readonly: boolean;
  observed_context: Record<string, string>;
  warnings?: string[];
};

export type ContextSummary = {
  contract_version: string;
  readonly: boolean;
  status: string;
  sources: ContextSource[];
  warnings?: string[];
  notes?: string[];
};

export async function getContextSummary(): Promise<ContextSummary> {
  const response = await fetch('/product/agentops/remote', { method: 'GET' });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as ContextSummary;
}
