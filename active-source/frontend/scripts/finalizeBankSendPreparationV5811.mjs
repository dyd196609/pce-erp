import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const VERSION = "V1.14.2.8.4.7.58.1.1";
const CHECKPOINT_ID = "bank_send_preparation_write_contract_ready";
const SOURCE_CHECKPOINT_ID =
  "formal_payment_order_transition_count_consistent_ready";
const frontend = process.cwd();
const workspace = path.resolve(frontend, "..");
const resultRoot = path.join(
  frontend,
  "test-results",
  "bank-send-preparation-v58-1-1",
);
const checkpointRoot = path.join(
  frontend,
  "test-results",
  "purchase-payment-golden-flow",
  "checkpoints",
);
const checkpoint = path.join(checkpointRoot, CHECKPOINT_ID);
const sourceCheckpoint = path.join(checkpointRoot, SOURCE_CHECKPOINT_ID);
const archiveRoot = path.resolve(
  frontend,
  "..",
  "..",
  "CheckpointArchive",
  "purchase-payment-golden-flow",
);
const archive = path.join(archiveRoot, CHECKPOINT_ID);
const sourceArchive = path.join(archiveRoot, SOURCE_CHECKPOINT_ID);
const persistentDatabase = path.join(
  workspace,
  "backend",
  "canary-data",
  "purchase-flow-demo.sqlite3",
);
const developmentDatabase = path.join(workspace, "backend", "db.sqlite3");
const expectedPersistentDatabaseHash =
  "9b1e55fbf318ae04266bc7eda607066e54920c4150c865476b686ca161ce3d9a";
const expectedDevelopmentDatabaseHash =
  "b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0";
const coreFiles = [
  "manifest.json",
  "storage-state.json",
  "application-state.json",
  "business-entities.json",
  "relationship-graph.json",
];
const protectedHashes = {
  "manifest.json":
    "7de56531291db6df3539d4440a52a131e12b826113e5fe47f074b9b97f5af7c5",
  "storage-state.json":
    "8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242",
  "application-state.json":
    "b7cb1df70389d747fcf90ce76eb978a32f36e01adb8c589ddc6b2ffefd3563c4",
  "business-entities.json":
    "efc18c515a4e0605c1a1b3d23e0c313bebc46304c5da981b63e83d7fd5490db6",
  "relationship-graph.json":
    "b4fcf6dde7832092aedf8b739a7f96f52e96957fcf5c721c3d8e040e49d2e610",
};
const reportFiles = [
  "backend-validation-report.json",
  "bank-send-preparation-report.json",
  "build-report.json",
  "cross-process-recovery-report.json",
  "database-protection-report.json",
  "four-surface-consistency-report.json",
  "iab-real-browser-report.json",
  "interface-security-report.json",
  "page-acceptance-report.json",
  "permission-report.json",
  "playwright-validation-report.json",
  "server-facts-report.json",
  "static-guard-report.json",
  "write-intent-contract-gap-report.json",
];

const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};
const readJson = (file) => JSON.parse(fs.readFileSync(file, "utf8"));
const writeJson = (file, value) => fs.writeFileSync(
  file,
  `${JSON.stringify(value, null, 2)}\n`,
  "utf8",
);
const sha256 = (file) => crypto
  .createHash("sha256")
  .update(fs.readFileSync(file))
  .digest("hex");
const hashes = (directory) => Object.fromEntries(
  coreFiles.map((file) => [file, sha256(path.join(directory, file))]),
);
const listFiles = (directory) => fs.existsSync(directory)
  ? fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => (
      entry.isDirectory()
        ? listFiles(path.join(directory, entry.name))
        : [path.join(directory, entry.name)]
    ))
  : [];

assert(!fs.existsSync(checkpoint), `Checkpoint exists: ${checkpoint}`);
assert(!fs.existsSync(archive), `Archive exists: ${archive}`);
assert(fs.existsSync(sourceCheckpoint), "Protected source checkpoint missing");
assert(fs.existsSync(sourceArchive), "Protected source archive missing");
const sourceHashesBefore = hashes(sourceCheckpoint);
const sourceArchiveHashesBefore = hashes(sourceArchive);
assert(
  coreFiles.every((file) => sourceHashesBefore[file] === protectedHashes[file]),
  "Protected source checkpoint hash mismatch",
);
assert(
  coreFiles.every(
    (file) => sourceArchiveHashesBefore[file] === protectedHashes[file],
  ),
  "Protected source archive hash mismatch",
);
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  "Persistent canary database changed",
);
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  "Development database changed",
);

const reports = Object.fromEntries(reportFiles.map((file) => {
  const reportPath = path.join(resultRoot, file);
  assert(fs.existsSync(reportPath), `Required report missing: ${file}`);
  const report = readJson(reportPath);
  assert(report.result === "passed", `Required report failed: ${file}`);
  return [file, report];
}));
const server = reports["server-facts-report.json"];
const facts = server.bankSendPreparationFacts;
const writeIntentFacts = facts?.writeIntentFacts;
const consistency = reports["four-surface-consistency-report.json"];
const iab = reports["iab-real-browser-report.json"];
const recovery = reports["cross-process-recovery-report.json"];
const database = reports["database-protection-report.json"];
const build = reports["build-report.json"];
const playwright = reports["playwright-validation-report.json"];
const guards = reports["static-guard-report.json"];

assert(facts?.factType === "BankSendPreparationFacts", "Fact type mismatch");
assert(facts.currentStateSource === "server", "Facts are not server sourced");
assert(facts.sourceFormalPaymentOrderCount === 8, "Source count mismatch");
assert(facts.bankSendPreparationCount === 8, "Preparation count mismatch");
assert(facts.preparedCount === 8, "Prepared count mismatch");
assert(facts.eligibleCount === 8, "Eligible count mismatch");
assert(facts.previewCount === 1, "Preview count mismatch");
assert(
  writeIntentFacts.previewPreparationWriteCount === 1,
  "Preview preparation write count mismatch",
);
assert(writeIntentFacts.auditWriteCount === 9, "Audit write count mismatch");
assert(
  writeIntentFacts.forbiddenBusinessProgressWriteCount === 0,
  "Forbidden business progression write detected",
);
assert(writeIntentFacts.previewOnlyEnforced === true, "Preview-only failed");
assert(consistency.allFourSurfacesConsistent, "Four surfaces differ");
assert(iab.browserBackend === "iab", "IAB evidence missing");
assert(iab.copyDiagnostic.buttonClicked, "Diagnostic copy was not tested");
assert(recovery.independentProcessCount === 2, "Recovery process count mismatch");
assert(
  recovery.conditions.crossProcessFactsEqual,
  "Cross-process facts differ",
);
assert(database.canaryDatabase.immutableDuringRecovery, "Canary DB changed");
assert(database.developmentDatabase.unchanged, "Development DB changed");
assert(build.exitCode === 0 && build.viteProductionBuildCompleted, "Build failed");
assert(playwright.passedCount === 1, "Playwright failed");
assert(guards.blockerCount === 0, "Static guard blocker found");
assert(
  Object.values(server.downstreamCounts).every((value) => value === 0),
  "Downstream object was created",
);

const sourceManifest = readJson(path.join(sourceCheckpoint, "manifest.json"));
const sourceApplication = readJson(
  path.join(sourceCheckpoint, "application-state.json"),
);
const sourceEntities = readJson(
  path.join(sourceCheckpoint, "business-entities.json"),
);
const sourceGraph = readJson(
  path.join(sourceCheckpoint, "relationship-graph.json"),
);
const manifest = {
  ...sourceManifest,
  result: "passed",
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointVersion: VERSION,
  checkpointId: CHECKPOINT_ID,
  sourceCheckpointId: SOURCE_CHECKPOINT_ID,
  canonicalName: "银行发送准备写入事实契约完整性修正",
  moduleCode: "bank-send-preparation",
  route: "/finance/bank-send-prepares",
  sourceDocumentType: "formalPaymentOrder",
  factType: facts.factType,
  currentStateSource: "server",
  sourceFormalPaymentOrderCount: 8,
  bankSendPreparationCount: 8,
  preparedCount: 8,
  eligibleCount: 8,
  previewCount: 1,
  previewPreparationWriteCount: 1,
  auditWriteCount: 9,
  forbiddenBusinessProgressWriteCount: 0,
  previewOnlyEnforced: true,
  apiPageDiagnosticStrictFactsConsistent: true,
  frontendRecomputationUsed: false,
  silentZeroFallbackUsed: false,
  djangoCheckPassed: true,
  compileallPassed: true,
  backendTestCount: 17,
  staticGuardCount: guards.guardCount,
  staticGuardsPassed: true,
  playwrightPassed: true,
  iabPassed: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: build.transformedModuleCount,
  crossProcessRecoveryReady: true,
  persistentDatabaseSha256: expectedPersistentDatabaseHash,
  persistentDatabaseUnchanged: true,
  developmentDatabaseSha256: expectedDevelopmentDatabaseHash,
  developmentDatabaseUnchanged: true,
  protectedCheckpointsImmutable: true,
  sourceCheckpointImmutable: true,
  sourceArchiveImmutable: true,
  bankSendTaskCreated: false,
  bankMessageCreated: false,
  paymentExecuted: false,
  fundsDebited: false,
  bankTransactionCreated: false,
  paymentVoucherCreated: false,
  ledgerCreated: false,
  postingCreated: false,
  productionUserDataWritten: false,
  immutable: true,
  restorable: true,
  archiveHashVerified: true,
};
const application = {
  ...sourceApplication,
  version: VERSION,
  currentStateSource: "server",
  capacity: {
    sourceFormalPaymentOrderCount: 8,
    bankSendPreparationCount: 8,
    preparedCount: 8,
    eligibleCount: 8,
    previewCount: 1,
  },
  bankSendPreparationFacts: facts,
  writeIntentContract: {
    contractVersion: "PCE-WRITE-INTENT-CONTRACT-V1.0",
    factSource: "workflow_runtime.BankSendPreparationFacts",
    strictFactsSource: "BankSendPreparationFacts",
    frontendRecomputationUsed: false,
    silentZeroFallbackUsed: false,
    ...writeIntentFacts,
  },
  downstreamCounts: server.downstreamCounts,
};
const bankSendPreparations = server.rows.map((row) => ({
  id: row.id,
  prepareNo: row.prepareNo,
  status: row.status,
  sourceDocumentType: row.sourceDocumentType,
  sourceFormalPaymentOrderId: row.sourceFormalPaymentOrderId,
  sourceFormalPaymentOrderNo: row.sourceFormalPaymentOrderNo,
  eligibility: row.eligibility,
  messagePreview: row.messagePreview,
  statusTransitionHistory: row.statusTransitionHistory,
  statusTransitionCount: row.statusTransitionCount,
  writeIntentFacts: row.writeIntentFacts,
  downstreamCounts: row.downstreamCounts,
  currentStateSource: row.currentStateSource,
}));
const entities = {
  ...sourceEntities,
  version: VERSION,
  canonicalName: "银行发送准备",
  bankSendPreparations,
  bankSendPreparationCount: 8,
  bankSendPreparationFacts: facts,
  writeIntentFacts,
  downstreamCounts: server.downstreamCounts,
};
const factNodeId = "bank-send-preparation-facts-v5811";
const preparationNodes = bankSendPreparations.map((row) => ({
  id: `bankSendPreparation:${row.prepareNo}`,
  type: "bankSendPreparation",
  status: row.status,
  currentStateSource: "server",
  previewStatus: row.messagePreview.status,
}));
const previewNodes = bankSendPreparations
  .filter((row) => row.messagePreview.exists)
  .map((row) => ({
    id: `bankMessagePreview:${row.messagePreview.previewNo}`,
    type: "bankMessagePreview",
    status: "preview_only",
    readonly: true,
    sent: false,
  }));
const graph = {
  ...sourceGraph,
  version: VERSION,
  nodes: [
    ...sourceGraph.nodes,
    ...preparationNodes,
    ...previewNodes,
    {
      id: factNodeId,
      type: "bankSendPreparationFacts",
      currentStateSource: "server",
      result: "passed",
      writeIntentFacts,
    },
  ],
  edges: [
    ...sourceGraph.edges,
    ...bankSendPreparations.map((row) => ({
      from: `formalPaymentOrder:${row.sourceFormalPaymentOrderNo}`,
      to: `bankSendPreparation:${row.prepareNo}`,
      type: "isSourceOf",
    })),
    ...bankSendPreparations
      .filter((row) => row.messagePreview.exists)
      .map((row) => ({
        from: `bankSendPreparation:${row.prepareNo}`,
        to: `bankMessagePreview:${row.messagePreview.previewNo}`,
        type: "hasPreviewOnlyPreparation",
      })),
    {
      from: factNodeId,
      to: "module:bank-send-preparation",
      type: "authoritativeServerFactFor",
    },
  ],
};

fs.mkdirSync(checkpoint, { recursive: false });
fs.copyFileSync(
  path.join(sourceCheckpoint, "storage-state.json"),
  path.join(checkpoint, "storage-state.json"),
);
writeJson(path.join(checkpoint, "manifest.json"), manifest);
writeJson(path.join(checkpoint, "application-state.json"), application);
writeJson(path.join(checkpoint, "business-entities.json"), entities);
writeJson(path.join(checkpoint, "relationship-graph.json"), graph);

const reportDestination = path.join(checkpoint, "reports");
const screenshotDestination = path.join(
  checkpoint,
  "evidence",
  "screenshots",
);
const playwrightDestination = path.join(
  checkpoint,
  "evidence",
  "playwright",
);
fs.mkdirSync(reportDestination, { recursive: true });
fs.mkdirSync(screenshotDestination, { recursive: true });
fs.mkdirSync(playwrightDestination, { recursive: true });
for (const file of reportFiles) {
  fs.copyFileSync(
    path.join(resultRoot, file),
    path.join(reportDestination, file),
  );
}
for (const screenshot of listFiles(path.join(resultRoot, "screenshots"))) {
  fs.copyFileSync(
    screenshot,
    path.join(screenshotDestination, path.basename(screenshot)),
  );
}
const trace = listFiles(path.join(resultRoot, "playwright-output"))
  .find((file) => path.basename(file) === "trace.zip");
assert(trace, "Playwright trace missing");
fs.copyFileSync(trace, path.join(playwrightDestination, "trace.zip"));

fs.mkdirSync(archiveRoot, { recursive: true });
fs.cpSync(checkpoint, archive, { recursive: true });
const checkpointHashes = hashes(checkpoint);
const archiveHashes = hashes(archive);
assert(
  coreFiles.every((file) => checkpointHashes[file] === archiveHashes[file]),
  "Checkpoint/archive hashes differ",
);
const sourceHashesAfter = hashes(sourceCheckpoint);
const sourceArchiveHashesAfter = hashes(sourceArchive);
assert(
  coreFiles.every((file) => sourceHashesAfter[file] === protectedHashes[file]),
  "Protected source checkpoint changed during finalization",
);
assert(
  coreFiles.every(
    (file) => sourceArchiveHashesAfter[file] === protectedHashes[file],
  ),
  "Protected source archive changed during finalization",
);
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  "Persistent database changed during finalization",
);
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  "Development database changed during finalization",
);

const finalization = {
  result: "passed",
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint,
  archivePath: archive,
  immutable: true,
  crossProcessRestoreReady: true,
  checkpointHashes,
  archiveHashes,
  protectedCheckpointHashesBefore: sourceHashesBefore,
  protectedCheckpointHashesAfter: sourceHashesAfter,
  protectedArchiveHashesBefore: sourceArchiveHashesBefore,
  protectedArchiveHashesAfter: sourceArchiveHashesAfter,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  previewPreparationWriteCount: 1,
  auditWriteCount: 9,
  forbiddenBusinessProgressWriteCount: 0,
  previewOnlyEnforced: true,
  productionUserDataWritten: false,
};
writeJson(path.join(resultRoot, "finalization-report.json"), finalization);
console.log(JSON.stringify(finalization, null, 2));
