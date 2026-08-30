export {
  createMemoryCredentialSource,
  type CredentialSource,
  type ResolvedCredential,
} from "./credential-source.js";
export {
  buildGrants,
  isGranted,
  toRefName,
  type CredentialGrant,
  type PackageGrants,
  type CredentialDeclaration,
} from "./grant.js";
export {
  resolveForPackage,
  resolveAllForPackage,
  type ResolveDeps,
  type ResolveResult,
  type ResolveAuditEvent,
} from "./resolver.js";
