export { PackageRegistry, type InstalledPackage, type InstalledDirective } from "./registry.js";
export {
  installPackage,
  uninstallPackage,
  exportPackage,
  exportAllPackages,
  listPackages,
  inferPackageKind,
  type InstallInput,
  type InstallResult,
  type InstallSchema,
} from "./installer.js";
export { handleMeta, META_ACTIONS, type MetaAction, type MetaDeps } from "./meta.js";
