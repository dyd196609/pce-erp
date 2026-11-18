import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sourceDir = resolve(frontendDir, "..");
const backendDir = resolve(sourceDir, "backend");
const argument = (name, fallback) => {
  const prefix = `${name}=`;
  const value = process.argv.find(item => item.startsWith(prefix));
  return value ? value.slice(prefix.length) : fallback;
};
const reportVersion = argument("--version", "V1.14.2.8.4.7.58");
const reportDirectoryName = argument(
  "--report-dir",
  "bank-send-preparation-v58",
);
const checkpointName = argument(
  "--checkpoint",
  "bank_send_preparation_gate_ready",
);
const reportDir = resolve(
  frontendDir,
  "test-results",
  reportDirectoryName,
);
const pythonExecutable =
  "C:\\Users\\DAODA\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const pythonPath = resolve(backendDir, "venv", "Lib", "site-packages");
const canaryDatabase = resolve(
  backendDir,
  "canary-data",
  "purchase-flow-demo.sqlite3",
);
const developmentDatabase = resolve(backendDir, "db.sqlite3");
const protectedCheckpoint = resolve(
  frontendDir,
  "test-results",
  "purchase-payment-golden-flow",
  "checkpoints",
  "formal_payment_order_transition_count_consistent_ready",
);
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
const protectedV58ReportRoot = resolve(
  frontendDir,
  "test-results",
  "bank-send-preparation-v58",
);
const protectedV58ReportHashes = {
  "server-facts-report.json":
    "4b860303240f793d5916b21874383f4f4a423950ff73fad547edc841f5dc586d",
  "cross-process-recovery-report.json":
    "77469981a6b15bd12927b8858a46c2f526ed89787dcec222f0f769e2042b14a3",
  "database-protection-report.json":
    "d8010a6d5f87bfd088a72921410626b90494340d5ef2442363385d6f0f254bd2",
};
const protectedV581ReportRoot = resolve(
  frontendDir,
  "test-results",
  "bank-send-preparation-v58-1",
);
const protectedV581ReportHashes = {
  "server-facts-report.json":
    "3c197c9c2918cdcec21ecd914e5ee4475f4a1c288b5fa74a206e8c1256e62c9a",
  "cross-process-recovery-report.json":
    "7bf0fe7b1efb1d2eb9e4dd15781a49a4197f3513d2dec16b5322b41b52857230",
  "database-protection-report.json":
    "6557000a6817f8eeb236a2aad9ba940754a65a486b549062113a198927504b81",
};

function sha256(path) {
  if (!existsSync(path)) {
    return null;
  }
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function runReadOnlyReport() {
  const result = spawnSync(
    pythonExecutable,
    ["manage.py", "report_bank_send_preparation_v58"],
    {
      cwd: backendDir,
      encoding: "utf8",
      env: {
        ...process.env,
        DJANGO_SETTINGS_MODULE:
          "pce_backend.action_permission_test_settings",
        PCE_CANARY_DATABASE_PATH: canaryDatabase,
        PYTHONIOENCODING: "utf-8",
        PYTHONPATH: pythonPath,
      },
      maxBuffer: 32 * 1024 * 1024,
    },
  );
  if (result.status !== 0) {
    throw new Error(
      [
        "report_bank_send_preparation_v58 failed",
        `exitCode=${result.status}`,
        result.stdout,
        result.stderr,
      ].join("\n"),
    );
  }
  const jsonLine = result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line.startsWith("{"));
  if (!jsonLine) {
    throw new Error("No JSON report was emitted by the backend command.");
  }
  return JSON.parse(jsonLine);
}

mkdirSync(reportDir, { recursive: true });
const canaryBefore = sha256(canaryDatabase);
const developmentBefore = sha256(developmentDatabase);
const first = runReadOnlyReport();
const second = runReadOnlyReport();
const canaryAfter = sha256(canaryDatabase);
const developmentAfter = sha256(developmentDatabase);
const actualProtectedHashes = Object.fromEntries(
  Object.keys(protectedHashes).map((name) => [
    name,
    sha256(resolve(protectedCheckpoint, name)),
  ]),
);
const protectedCheckpointImmutable = Object.entries(protectedHashes).every(
  ([name, expected]) => actualProtectedHashes[name] === expected,
);
const actualProtectedV58ReportHashes = Object.fromEntries(
  Object.keys(protectedV58ReportHashes).map((name) => [
    name,
    sha256(resolve(protectedV58ReportRoot, name)),
  ]),
);
const protectedV58ReportsImmutable = Object.entries(
  protectedV58ReportHashes,
).every(
  ([name, expected]) => actualProtectedV58ReportHashes[name] === expected,
);
const actualProtectedV581ReportHashes = Object.fromEntries(
  Object.keys(protectedV581ReportHashes).map((name) => [
    name,
    sha256(resolve(protectedV581ReportRoot, name)),
  ]),
);
const protectedV581ReportsImmutable = Object.entries(
  protectedV581ReportHashes,
).every(
  ([name, expected]) => actualProtectedV581ReportHashes[name] === expected,
);
const crossProcessFactsEqual =
  JSON.stringify(first) === JSON.stringify(second);
const downstreamZero = Object.values(first.downstreamCounts ?? {}).every(
  (value) => value === 0,
);
const conditions = {
  firstProcessPassed: first.result === "passed",
  secondProcessPassed: second.result === "passed",
  crossProcessFactsEqual,
  currentStateSourceIsServer:
    first.currentStateSource === "server" &&
    second.currentStateSource === "server",
  canaryDatabaseUnchangedDuringRecovery: canaryBefore === canaryAfter,
  developmentDatabaseUnchanged:
    developmentBefore === developmentAfter &&
    developmentBefore ===
      "b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0",
  protectedCheckpointImmutable,
  protectedV58ReportsImmutable,
  protectedV581ReportsImmutable,
  bankSendPreparationFactsComplete:
    first.bankSendPreparationFacts?.factType ===
      "BankSendPreparationFacts" &&
    first.bankSendPreparationFacts?.currentStateSource === "server",
  previewOnlyEnforced:
    first.writeIntentFacts?.previewOnlyEnforced === true,
  downstreamZero,
  bankSendNotCreated:
    first.bankSendCreated === false &&
    first.bankMessageSent === false &&
    first.bankTransactionCreated === false,
  paymentNotExecuted:
    first.paymentExecuted === false && first.fundsDebited === false,
};
const recoveryReport = {
  result: Object.values(conditions).every(Boolean) ? "passed" : "failed",
  version: reportVersion,
  checkpointName,
  currentStateSource: "server",
  independentProcessCount: 2,
  conditions,
  firstProcessSummary: {
    result: first.result,
    bankSendPreparationCount: first.bankSendPreparationCount,
    eligibleCount: first.eligibleCount,
    previewCount: first.previewCount,
    previewStatuses: first.previewStatuses,
    statusTransitionCount: first.statusTransitionCount,
    previewPreparationWriteCount:
      first.previewPreparationWriteCount,
    auditWriteCount: first.auditWriteCount,
    forbiddenBusinessProgressWriteCount:
      first.forbiddenBusinessProgressWriteCount,
    previewOnlyEnforced:
      first.writeIntentFacts?.previewOnlyEnforced === true,
  },
  secondProcessSummary: {
    result: second.result,
    bankSendPreparationCount: second.bankSendPreparationCount,
    eligibleCount: second.eligibleCount,
    previewCount: second.previewCount,
    previewStatuses: second.previewStatuses,
    statusTransitionCount: second.statusTransitionCount,
    previewPreparationWriteCount:
      second.previewPreparationWriteCount,
    auditWriteCount: second.auditWriteCount,
    forbiddenBusinessProgressWriteCount:
      second.forbiddenBusinessProgressWriteCount,
    previewOnlyEnforced:
      second.writeIntentFacts?.previewOnlyEnforced === true,
  },
};
const databaseProtectionReport = {
  result:
    conditions.canaryDatabaseUnchangedDuringRecovery &&
    conditions.developmentDatabaseUnchanged &&
    conditions.protectedCheckpointImmutable
    && conditions.protectedV58ReportsImmutable
    && conditions.protectedV581ReportsImmutable
      ? "passed"
      : "failed",
  canaryDatabase: {
    path: canaryDatabase,
    beforeSha256: canaryBefore,
    afterSha256: canaryAfter,
    immutableDuringRecovery: canaryBefore === canaryAfter,
  },
  developmentDatabase: {
    path: developmentDatabase,
    beforeSha256: developmentBefore,
    afterSha256: developmentAfter,
    unchanged:
      developmentBefore === developmentAfter &&
      developmentBefore ===
        "b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0",
  },
  protectedCheckpoint: {
    path: protectedCheckpoint,
    expectedHashes: protectedHashes,
    actualHashes: actualProtectedHashes,
    immutable: protectedCheckpointImmutable,
  },
  protectedV58Reports: {
    path: protectedV58ReportRoot,
    expectedHashes: protectedV58ReportHashes,
    actualHashes: actualProtectedV58ReportHashes,
    immutable: protectedV58ReportsImmutable,
  },
  protectedV581Reports: {
    path: protectedV581ReportRoot,
    expectedHashes: protectedV581ReportHashes,
    actualHashes: actualProtectedV581ReportHashes,
    immutable: protectedV581ReportsImmutable,
  },
  productionUserDataWritten: false,
};

writeFileSync(
  resolve(reportDir, "server-facts-report.json"),
  `${JSON.stringify(first, null, 2)}\n`,
  "utf8",
);
writeFileSync(
  resolve(reportDir, "cross-process-recovery-report.json"),
  `${JSON.stringify(recoveryReport, null, 2)}\n`,
  "utf8",
);
writeFileSync(
  resolve(reportDir, "database-protection-report.json"),
  `${JSON.stringify(databaseProtectionReport, null, 2)}\n`,
  "utf8",
);

console.log(JSON.stringify(recoveryReport, null, 2));
if (recoveryReport.result !== "passed") {
  process.exitCode = 1;
}
