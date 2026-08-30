export { QuotaStore, createMemoryStorage } from "./store.js";
export { windowFor, needsFlip } from "./period.js";
export type {
  QuotaPeriod,
  QuotaStatus,
  QuotaRecord,
  StorageKV,
  RegisterOptions,
  RegisterResult,
  CheckResult,
  ConsumeResult,
  ListResult,
} from "./types.js";
