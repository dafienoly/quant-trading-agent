import { useEffect, useMemo, useState } from 'react';
import { ContextSummary, getContextSummary } from '../api/context';
import { toContextDisplay } from '../api/contextSelectors';
import { AdapterStatusCard } from './AdapterStatusCard';

export function AdapterStatusPanel() {
  const [summary, setSummary] = useState<ContextSummary | null>(null);
  const [failed, setFailed] = useState(false);
  const display = useMemo(() => toContextDisplay(summary), [summary]);

  useEffect(() => {
    let cancelled = false;
    getContextSummary()
      .then((nextSummary) => {
        if (cancelled) return;
        setSummary(nextSummary);
      })
      .catch(() => {
        if (cancelled) return;
        setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return <AdapterStatusCard display={{ status: 'error', sourceName: 'adapter', configured: false, readonly: true }} />;
  }

  return <AdapterStatusCard display={display} />;
}

export default AdapterStatusPanel;
