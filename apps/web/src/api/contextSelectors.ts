import { ContextSummary } from './context';

export type ContextDisplay = {
  status: string;
  sourceName: string;
  configured: boolean;
  readonly: boolean;
};

export function toContextDisplay(value: ContextSummary | null): ContextDisplay {
  const source = value?.sources?.[0];
  return {
    status: value?.status ?? 'unknown',
    sourceName: source?.name ?? 'n/a',
    configured: source?.configured ?? false,
    readonly: value?.readonly ?? true,
  };
}
