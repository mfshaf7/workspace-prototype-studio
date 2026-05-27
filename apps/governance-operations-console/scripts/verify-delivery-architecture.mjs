#!/usr/bin/env node

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const repoRoot = new URL("..", import.meta.url).pathname;
const scanRoots = [
  join(repoRoot, "src/components/delivery"),
  join(repoRoot, "src/data"),
];
const bannedTerms = [
  "Activate Epic",
  "Commitment",
  "Drafting",
  "Front Control",
  "Fronts",
  "Metadata Readiness",
  "Movement",
  "Package #",
];

const scannedFiles = [];

function walk(path) {
  const stat = statSync(path);

  if (stat.isDirectory()) {
    for (const entry of readdirSync(path)) {
      walk(join(path, entry));
    }
    return;
  }

  if (!/\.(css|ts|tsx)$/.test(path)) {
    return;
  }

  const relativePath = relative(repoRoot, path);

  if (
    relativePath.startsWith("src/data/") &&
    !/^src\/data\/delivery-/.test(relativePath)
  ) {
    return;
  }

  scannedFiles.push(path);
}

for (const root of scanRoots) {
  walk(root);
}

const failures = [];

for (const file of scannedFiles) {
  const relativePath = relative(repoRoot, file);
  const source = readFileSync(file, "utf8");

  if (relativePath === "src/data/delivery-terms.ts") {
    continue;
  }

  for (const term of bannedTerms) {
    if (source.includes(term)) {
      failures.push(`${relativePath}: banned Delivery term "${term}"`);
    }
  }
}

const readModel = readFileSync(join(repoRoot, "src/data/delivery-read-model.ts"), "utf8");
const selectorSource = readFileSync(join(repoRoot, "src/data/delivery-selectors.ts"), "utf8");

for (const required of [
  "DeliveryWorkflowStage",
  "workflow_stage",
  "selected_delivery_package_id",
  "board_summary",
  "art_map",
  "art_tree",
  "apply_intents",
  "audit_events",
]) {
  if (!readModel.includes(required)) {
    failures.push(`src/data/delivery-read-model.ts: missing ${required}`);
  }
}

for (const required of [
  "getDeliveryPackagesByWorkflowStage",
  "getExecutionBoardPackages",
  "getPackagePosture",
  "getAvailableActions",
  "getSelectedPackage",
  "getPackageTree",
  "getPackageAuditEvents",
  "getApplyIntent",
]) {
  if (!selectorSource.includes(required)) {
    failures.push(`src/data/delivery-selectors.ts: missing ${required}`);
  }
}

if (failures.length > 0) {
  console.error("Delivery architecture guard failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log(`Delivery architecture guard passed (${scannedFiles.length} files scanned).`);
