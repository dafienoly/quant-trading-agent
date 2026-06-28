export const AGENT_PIPELINE_ROUTE = '/agent-pipeline';
export const HOME_ROUTE = '/';

export function isAgentPipelineRoute(pathname: string): boolean {
  return pathname === AGENT_PIPELINE_ROUTE || pathname === HOME_ROUTE;
}
