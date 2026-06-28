import { expect, test } from 'vitest';
import { AGENT_PIPELINE_ROUTE, HOME_ROUTE, isAgentPipelineRoute } from './routes';

test('agent pipeline route constants are stable', () => {
  expect(AGENT_PIPELINE_ROUTE).toBe('/agent-pipeline');
  expect(HOME_ROUTE).toBe('/');
});

test('agent pipeline route helper accepts foundation routes', () => {
  expect(isAgentPipelineRoute('/agent-pipeline')).toBe(true);
  expect(isAgentPipelineRoute('/')).toBe(true);
  expect(isAgentPipelineRoute('/other')).toBe(false);
});
