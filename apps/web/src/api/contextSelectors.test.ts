import { expect, test } from 'vitest';
import { toContextDisplay } from './contextSelectors';

test('context display falls back safely', () => {
  const display = toContextDisplay(null);
  expect(display.status).toBe('unknown');
  expect(display.sourceName).toBe('n/a');
  expect(display.configured).toBe(false);
  expect(display.readonly).toBe(true);
});

test('context display maps first source', () => {
  const display = toContextDisplay({
    contract_version: 'agentops.remote_context.v1',
    readonly: true,
    status: 'ready',
    sources: [
      {
        name: 'remote_context',
        configured: true,
        readonly: true,
        observed_context: { repository: 'owner/repo' },
      },
    ],
  });
  expect(display.status).toBe('ready');
  expect(display.sourceName).toBe('remote_context');
  expect(display.configured).toBe(true);
  expect(display.readonly).toBe(true);
});
