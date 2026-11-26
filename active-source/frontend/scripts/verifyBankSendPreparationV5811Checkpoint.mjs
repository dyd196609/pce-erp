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

const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};
const readJson = (file) => JSON.parse(fs.readFileSync(file, "utf8"));
const sha256 = (file) => crypto
  .createHash("sha256")
  .update(fs.readFileSync(file))
  .digest("hex");
const hashes = (directory) => Object.fromEntries(
  coreFiles.map((file) => [file, sha256(path.join(directory, file))]),
);

const checkpointHashesBefore = hashes(checkpoint);
const archiveHashesBefore = hashes(archive);
assert(
  coreFiles.every(
    (file) => checkpointHashesBefore[file] === archiveHashesBefore[file],
  ),
  "Checkpoint/archive hash mismatch",
);
assert(
  coreFiles.every(
    (file) => hashes(sourceCheckpoint)[file] === protectedHashes[file],
  ),
  "Protected source checkpoint changed",
);
assert(
  coreFiles.every(
    (file) => hashes(sourceArchive)[file] === protectedHashes[file],
  ),
  "Protected source archive changed",
);
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  "Persistent canary database changed",
);
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  "Development database changed",
);

const manifest = readJson(path.join(checkpoint, "manifest.json"));
const application = readJson(path.join(checkpoint, "application-state.json"));
const entities = readJson(path.join(checkpoint, "business-entities.json"));
const graph = readJson(path.join(checkpoint, "relationship-graph.json"));
const facts = application.bankSendPreparationFacts;
const writeIntentFacts = facts.writeIntentFacts;
assert(manifest.result === "passed", "Manifest failed");
assert(manifest.version === VERSION, "Version mismatch");
assert(manifest.checkpointId === CHECKPOINT_ID, "Checkpoint id mismatch");
assert(manifest.immutable === true, "Checkpoint is not immutable");
assert(manifest.restorable === true, "Checkpoint is not restorable");
assert(facts.factType === "BankSendPreparationFacts", "Fact type mismatch");
assert(facts.currentStateSource === "server", "Fact source mismatch");
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
assert(entities.bankSendPreparations.length === 8, "Entity count mismatch");
assert(
  entities.bankSendPreparations.every(
    (row) => row.currentStateSource === "server",
  ),
  "Checkpoint entity is not server sourced",
);
assert(
  Object.values(entities.downstreamCounts).every((value) => value === 0),
  "Downstream object found",
);
assert(
  graph.nodes.filter((node) => node.type === "bankSendPreparation").length === 8,
  "Relationship graph preparation count mismatch",
);
assert(
  graph.nodes.filter((node) => node.type === "bankMessagePreview").length === 1,
  "Relationship graph preview count mismatch",
);

const requiredReports = [
  "backend-validation-report.json",
  "build-report.json",
  "cross-process-recovery-report.json",
  "four-surface-consistency-report.json",
  "iab-real-browser-report.json",
  "playwright-validation-report.json",
  "server-facts-report.json",
  "static-guard-report.json",
];
for (const file of requiredReports) {
  const report = readJson(path.join(checkpoint, "reports", file));
  assert(report.result === "passed", `Checkpoint report failed: ${file}`);
}
assert(
  fs.existsSync(path.join(checkpoint, "evidence", "playwright", "trace.zip")),
  "Playwright trace missing",
);
assert(
  fs.existsSync(
    path.join(
      checkpoint,
      "evidence",
      "screenshots",
      "04-iab-bank-send-preparation-facts.png",
    ),
  ),
  "IAB screenshot missing",
);

const checkpointHashesAfter = hashes(checkpoint);
const archiveHashesAfter = hashes(archive);
assert(
  coreFiles.every(
    (file) => checkpointHashesAfter[file] === checkpointHashesBefore[file],
  ),
  "Checkpoint changed during independent verification",
);
assert(
  coreFiles.every(
    (file) => archiveHashesAfter[file] === archiveHashesBefore[file],
  ),
  "Archive changed during independent verification",
);
assert(
  coreFiles.every(
    (file) => checkpointHashesAfter[file] === archiveHashesAfter[file],
  ),
  "Checkpoint/archive changed during verification",
);

console.log(JSON.stringify({
  result: "passed",
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint,
  archivePath: archive,
  immutable: true,
  crossProcessRestoreReady: true,
  currentStateSource: "server",
  checkpointHashes: checkpointHashesAfter,
  archiveHashes: archiveHashesAfter,
  sourceCheckpointId: SOURCE_CHECKPOINT_ID,
  protectedCheckpointImmutable: true,
  protectedArchiveImmutable: true,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
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
  productionUserDataWritten: false,
}, null, 2));
