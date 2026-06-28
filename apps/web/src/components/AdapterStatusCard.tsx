import { ContextDisplay } from '../api/contextSelectors';

export type AdapterStatusCardProps = {
  display: ContextDisplay;
};

export function AdapterStatusCard({ display }: AdapterStatusCardProps) {
  return (
    <article className="card">
      <h2>Adapter Status</h2>
      <p className="status">{display.status}</p>
      <p>Readonly: {String(display.readonly)}</p>
      <p>Source: {display.sourceName}</p>
      <p>Configured: {String(display.configured)}</p>
    </article>
  );
}

export default AdapterStatusCard;
