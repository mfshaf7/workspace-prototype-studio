import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const guardRoot = dirname(fileURLToPath(import.meta.url));
export const scriptsRoot = dirname(guardRoot);
export const appRoot = dirname(scriptsRoot);
export const workspaceRoot = join(appRoot, "..", "..");
export const srcRoot = join(appRoot, "src");

export function appPath(path) {
  return join(appRoot, path);
}

export function workspacePath(path) {
  return join(workspaceRoot, path);
}

export function relativeAppPath(path) {
  return relative(appRoot, path).replace(/\\/g, "/");
}

export function readAppFile(path) {
  return readFileSync(appPath(path), "utf8");
}

export function readWorkspaceFile(path) {
  return readFileSync(workspacePath(path), "utf8");
}

export function pathExists(path) {
  return existsSync(appPath(path));
}

export function workspacePathExists(path) {
  return existsSync(workspacePath(path));
}

export function isFile(path) {
  try {
    return statSync(appPath(path)).isFile();
  } catch {
    return false;
  }
}

export function isDirectory(path) {
  try {
    return statSync(appPath(path)).isDirectory();
  } catch {
    return false;
  }
}

export function listDir(path) {
  return readdirSync(appPath(path));
}

export function walkFiles(root, extensions = [".ts", ".tsx", ".css", ".mjs"]) {
  const files = [];
  const absoluteRoot = root.startsWith(appRoot) ? root : appPath(root);

  function walk(path) {
    const stat = statSync(path);

    if (stat.isDirectory()) {
      for (const entry of readdirSync(path)) {
        walk(join(path, entry));
      }
      return;
    }

    if (extensions.includes(extname(path))) {
      files.push(path);
    }
  }

  if (existsSync(absoluteRoot)) {
    walk(absoluteRoot);
  }

  return files;
}

export function assertAppFile(failures, path) {
  if (!isFile(path)) {
    failures.push(`${path}: missing required file`);
  }
}

export function assertWorkspaceFile(failures, path) {
  if (!workspacePathExists(path)) {
    failures.push(`${path}: missing required workspace file`);
  }
}

export function assertAppPathAbsent(failures, path, reason) {
  if (pathExists(path)) {
    failures.push(`${path}: must not exist${reason ? `; ${reason}` : ""}`);
  }
}

export function assertIncludes(failures, path, requiredTerms) {
  if (!isFile(path)) {
    failures.push(`${path}: missing required file`);
    return;
  }

  const source = readAppFile(path);

  for (const term of requiredTerms) {
    if (!source.includes(term)) {
      failures.push(`${path}: missing required token "${term}"`);
    }
  }
}

export function assertWorkspaceIncludes(failures, path, requiredTerms) {
  if (!workspacePathExists(path)) {
    failures.push(`${path}: missing required workspace file`);
    return;
  }

  const source = readWorkspaceFile(path);

  for (const term of requiredTerms) {
    if (!source.includes(term)) {
      failures.push(`${path}: missing required token "${term}"`);
    }
  }
}

export function assertOmits(failures, path, forbiddenTerms) {
  if (!isFile(path)) {
    failures.push(`${path}: missing required file`);
    return;
  }

  const source = readAppFile(path);

  for (const term of forbiddenTerms) {
    if (source.includes(term)) {
      failures.push(`${path}: must not include stale token "${term}"`);
    }
  }
}

export function importSpecifiers(source) {
  return [...source.matchAll(/from\s+["']([^"']+)["']/g)].map(
    (match) => match[1],
  );
}

export function assertOnlyAllowedSpecifiers(
  failures,
  path,
  prefix,
  allowedSpecifiers,
) {
  const normalizeTypeScriptSpecifier = (specifier) =>
    specifier.replace(/\.tsx?$/, "");
  const allowed = new Set(allowedSpecifiers.map(normalizeTypeScriptSpecifier));
  const matchingSpecifiers = importSpecifiers(readAppFile(path)).filter(
    (specifier) => specifier.startsWith(prefix),
  );

  for (const specifier of matchingSpecifiers) {
    if (!allowed.has(normalizeTypeScriptSpecifier(specifier))) {
      failures.push(
        `${path}: import or export "${specifier}" is outside the allowed ${prefix} public boundary`,
      );
    }
  }
}

export function resolvedRelativeImportPath(importerPath, specifier) {
  if (!specifier.startsWith(".")) {
    return null;
  }

  const resolvedPath = resolve(dirname(appPath(importerPath)), specifier);
  return relative(appRoot, resolvedPath).replace(/\\/g, "/");
}

export function lineCount(path) {
  return readAppFile(path).split(/\r?\n/).length;
}

export function assertDomainOwnershipRoot(
  failures,
  domain,
  { allowedLayers, requiredLayers = allowedLayers },
) {
  const domainRoot = `src/domain-workspaces/${domain}`;
  const allowed = new Set(["index.ts", ...allowedLayers]);

  if (!isDirectory(domainRoot)) {
    failures.push(`${domainRoot}: missing domain workspace`);
    return;
  }

  assertAppFile(failures, `${domainRoot}/index.ts`);

  for (const layer of requiredLayers) {
    if (!isDirectory(`${domainRoot}/${layer}`)) {
      failures.push(`${domainRoot}/${layer}: missing required ownership layer`);
    }
  }

  for (const entry of listDir(domainRoot)) {
    const entryPath = `${domainRoot}/${entry}`;

    if (!allowed.has(entry)) {
      failures.push(
        `${entryPath}: root entry is outside the approved ownership layers`,
      );
    }

    if (isFile(entryPath) && entry !== "index.ts") {
      failures.push(
        `${entryPath}: root implementation files must live in an ownership layer`,
      );
    }
  }
}
