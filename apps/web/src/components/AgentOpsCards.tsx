import { OpsSummary, QualitySummary, RuntimeProfile, SectionStatus } from '../api/agentops';

export type OpsSummaryCardProps = {
  summary: OpsSummary | null;
};

export type RuntimeProfileCardProps = {
  runtime: RuntimeProfile | null;
  defaultStage: string;
};

export type QualitySummaryCardProps = {
  quality: QualitySummary | null;
};

export function OpsSummaryCard({ summary }: OpsSummaryCardProps) {
  return (
    <article className="card">
      <h2>Ops Summary</h2>
      <p className="status">{summary?.overall_status ?? 'unknown'}</p>
      <p>Readonly: {String(summary?.readonly ?? true)}</p>
      <ul>
        {(summary?.sections ?? []).map((section: SectionStatus) => (
          <li key={section.name}>
            <strong>{section.name}</strong>: {section.status} - {section.note}
          </li>
        ))}
      </ul>
    </article>
  );
}

export function RuntimeProfileCard({ runtime, defaultStage }: RuntimeProfileCardProps) {
  return (
    <article className="card">
      <h2>Runtime Profile</h2>
      <p>Stage: {runtime?.stage ?? defaultStage}</p>
      <p>Mode: {runtime?.mode ?? 'unknown'}</p>
      <p>Provider: {runtime?.provider ?? 'unknown'}</p>
      <p>Command env: {runtime?.command_env_var ?? 'n/a'}</p>
    </article>
  );
}

export function QualitySummaryCard({ quality }: QualitySummaryCardProps) {
  return (
    <article className="card">
      <h2>Quality Summary</h2>
      <p>Total: {quality?.total_count ?? 0}</p>
      <p>Open: {quality?.open_count ?? 0}</p>
      <p>Resolved: {quality?.resolved_count ?? 0}</p>
    </article>
  );
}
