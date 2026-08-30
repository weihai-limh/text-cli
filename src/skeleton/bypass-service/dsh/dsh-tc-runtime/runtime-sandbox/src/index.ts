export { execJs, type ExecRequest, type ExecOptions, type ExecResult } from "./executor.js";
export {
  policyForPackage,
  isNetworkAllowed,
  isEnvKeyAllowed,
  type SandboxPolicy,
  type SandboxMode,
  type PackageCapability,
  type PackageKind,
} from "./policy.js";
export {
  SandboxUnavailableError,
  NULL_SANDBOX,
  PASSTHROUGH_SANDBOX,
  type SandboxProvider,
} from "./sandbox-provider.js";
export {
  ancestorChain,
  MAX_CHAIN,
  type AncestorKey,
} from "./ancestor-chain.js";
export {
  guardDispatch,
  CycleDetectedError,
  cycleKey,
} from "./guard.js";
