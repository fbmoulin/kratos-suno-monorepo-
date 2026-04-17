// Metro config para monorepo pnpm.
// Sem watchFolders e disableHierarchicalLookup, Metro não resolve
// @kratos-suno/core (symlink do workspace) nem encontra node_modules do root.
//
// Ref: https://docs.expo.dev/guides/monorepos/

const { getDefaultConfig } = require("expo/metro-config");
const path = require("path");

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, "../..");

const config = getDefaultConfig(projectRoot);

// 1. Observar também a raiz do workspace (onde ficam os outros packages)
config.watchFolders = [workspaceRoot];

// 2. Deixar Metro resolver módulos de ambos: projectRoot + workspaceRoot
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(workspaceRoot, "node_modules"),
];

// 3. Forçar resolução não-hierárquica — necessário com pnpm (symlinks isolados)
config.resolver.disableHierarchicalLookup = true;

module.exports = config;
