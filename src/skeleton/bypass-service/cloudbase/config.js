// CloudBase gateway route configuration
// Maps domain -> cloud function name.
// Route table is now supplementary — primary routing is schema-driven (T4 design).
// This config is only for cloud function dispatch.

const routeTable = {
  'web-utils': 'web-utils',
};

const packages = ['web-utils'];

module.exports = { routeTable, packages };
