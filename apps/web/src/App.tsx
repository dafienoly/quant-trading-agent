import { useEffect, useMemo, useState } from 'react';
import { getOpsSummary, getQualitySummary, getRuntimeProfile, OpsSummary, QualitySummary, RuntimeProfile } from './api/agentops';
import { ContextDisplay } from './api/contextSelectors';
import { AdapterStatusCard } from './components/AdapterStatusCard';
import { OpsSummaryCard, QualitySummaryCard, RuntimeProfileCard } from './components/AgentOpsCards';
import './styles.css';

const DEFAULT_STAGE = 'codex_pm';

type LoadState = 'loading' | 'ready' | 'error';

export function App() {
  const [state, setState] = useState<LoadState>('loading');
  const [summary, setSummary] = useState<OpsSummary | null>(null);
  const [runtime, setRuntime] = useState<RuntimeProfile | null>(null);
  const [quality, setQuality] = useState<QualitySummary | null>(null);
  const [error, setError] = useState('');
  const adapterDisplay = useMemo<ContextDisplay>(
    () => ({ status: 'pending', sourceName: 'adapter', configured: false, readonly: true }),
    [],
  );

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
        <p>Readonly frontend foundation for AgentOps summary, runtime profile, quality summary, and adapter status.</p>
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
          <OpsSummaryCard summary={summary} />
          <RuntimeProfileCard runtime={runtime} defaultStage={DEFAULT_STAGE} />
          <QualitySummaryCard quality={quality} />
          <AdapterStatusCard display={adapterDisplay} />
        </section>
      )}
    </main>
  );
}

export default App;
