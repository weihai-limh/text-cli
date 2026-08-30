export { handlePrompt, type DispatchFn, type HandlerDeps, type Envelope } from "./handler.js";
export { createMockDispatch } from "./mock.js";
export { createTcServer, type TcServer, type TcServerOptions } from "./http.js";
export { buildPathDeps, createMetaWithPath, type PathBridgeDeps } from "./pathBridge.js";
export {
  DSH_HOST_DOMAINS, classifyDomain, classifyDirective, classifyPathOwnership,
} from "./ecosystem.js";
export type { EcosystemKind, PathOwnership } from "./ecosystem.js";
export {
  handleHealth,
  handleSkills,
  handleTaskQuery,
  MECHANISMS,
  type HealthInfo,
  type TaskInfo,
  type TaskQueryDeps,
} from "./endpoints.js";
