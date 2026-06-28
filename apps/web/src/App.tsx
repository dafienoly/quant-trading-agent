import { useEffect, useState } from 'react';
import { getOpsSummary, getQualitySummary, getRuntimeProfile, OpsSummary, QualitySummary, RuntimeProfile } from './api/agentops';
import './styles.css';

const DEFAULT_STAGE = 'codex_pm';

type LoadState = 'loading' | 'ready' | 'error';

export function App() {
  const [state, setState] = useState<LoadState>('loading');
  const [summary, setSummary] = useState<OpsSummary | null>(null);
  const [runtime, setRuntime] = useState<RuntimeProfile | null>(null);
  const [quality, setQuality] = useState<QualitySummary | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    Promise.all([getOpsSummary(), getRuntimeProfile(DEFAULT_STAGE), getQualitySummary()])
      .then(([nextSummary, nextRuntime, nextQuality]) => {
        if (cancelled) return;
        setSummary(nextSummary);
        setRuntime(nextRuntime);
        setQuality(nextQuality);
        setState('ready');
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setError(e.message);
        setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">V16.1 AgentOps Control Tower</p>
        <h1>Agent Pipeline Center</h1>
        <p>Readonly frontend foundation for AgentOps summary, runtime profile, and quality summary.</p>
      </section>

      {state === 'loading' && <section className="card">Loading AgentOps data...</section>}

      {state === 'error' && (
        <section className="card error-card">
          <h2>Load failed</h2>
          <p>{error || 'Unknown error'}</p>
        </section>
      )}

      {state === 'ready' && (
        <section className="grid">
          <article className="card">
            <h2>Ops Summary</h2>
            <p className="status">{summary?.overall_status ?? 'unknown'}</p>
            <p>Readonly: {String(summary?.readonly ?? true)}</p>
            <ul>
              {(summary?.sections ?? []).map((section) => (
                <li key={section.name}>
                  <strong>{section.name}</strong>: {section.status} - {section.note}
                </li>
              ))}
            </ul>
          </article>

          <article className="card">
            <h2>Runtime Profile</h2>
            <p>Stage: {runtime?.stage ?? DEFAULT_STAGE}</p>
            <p>Mode: {runtime?.mode ?? 'unknown'}</p>
            <p>Provider: {runtime?.provider ?? 'unknown'}</p>
            <p>Command env: {runtime?.command_env_var ?? 'n/a'}</p>
          </article>

          <article className="card">
            <h2>Quality Summary</h2>
            <p>Total: {quality?.total_count ?? 0}</p>
            <p>Open: {quality?.open_count ?? 0}</p>
            <p>Resolved: {quality?.resolved_count ?? 0}</p>
          </article>
        </section>
      )}
    </main>
  );
}

export default App;
