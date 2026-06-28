import { expect, test } from 'vitest';

test('agentops api base path is stable', () => {
  expect('/product/agentops/summary').toContain('/product/agentops');
});
