// Fail fast on an unsupported Node runtime before `npm start` / `npm test`.
// Plain JavaScript with conservative syntax so it runs, and explains itself, on any Node.
// Supported: Node 22.12+ within major 22 (tested on v22.16.0). Node 26 rejects
// --experimental-transform-types, which the sidecar needs for upstream TypeScript.
import { spawnSync } from "child_process";

var FLAG = "--experimental-transform-types";
var SUPPORTED = ">=22.12 <23";
var parts = process.versions.node.split(".");
var major = Number(parts[0]);
var minor = Number(parts[1]);
var problems = [];

if (!(major === 22 && minor >= 12)) {
  problems.push("Node v" + process.versions.node + " is outside the supported range " + SUPPORTED + ".");
}
var probe = spawnSync(process.execPath, [FLAG, "--no-warnings", "-e", "0"], { encoding: "utf-8" });
if (probe.error || probe.status !== 0) {
  var detail = probe.error ? String(probe.error.message) : String(probe.stderr || "").trim();
  problems.push("This Node does not accept " + FLAG + (detail ? " (" + detail + ")" : "") + ".");
}

if (problems.length > 0) {
  process.stderr.write(
    "memory-sidecar: unsupported Node runtime at " + process.execPath + "\n" +
    problems.map(function (p) { return "  - " + p + "\n"; }).join("") +
    "Use Node 22 (see .nvmrc), for example:\n" +
    "  nvm use                                  # reads .nvmrc\n" +
    "  PATH=/usr/local/bin:$PATH npm test       # put a Node 22 install first on PATH\n" +
    "  NODE=/usr/local/bin/node; \"$NODE\" " + FLAG + " --test test/*.test.ts\n"
  );
  process.exit(1);
}
