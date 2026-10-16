// GreenOps memory sidecar: small shared helpers (canonical JSON, hashing, atomic files).

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

/** Deterministic JSON: object keys sorted recursively, no whitespace. */
export function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).filter((k) => obj[k] !== undefined).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(obj[k])}`).join(",")}}`;
}

export function sha256Hex(text: string | Buffer): string {
  return crypto.createHash("sha256").update(text).digest("hex");
}

/** Write a file atomically: temp file in the same directory, fsync, rename, fsync directory. */
export function atomicWriteFile(file: string, content: string): void {
  const dir = path.dirname(file);
  const tmp = path.join(dir, `.${path.basename(file)}.${process.pid}.${crypto.randomBytes(4).toString("hex")}.tmp`);
  const fd = fs.openSync(tmp, "w", 0o600);
  try {
    fs.writeSync(fd, content, null, "utf-8");
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  try {
    fs.renameSync(tmp, file);
  } catch (err) {
    try { fs.unlinkSync(tmp); } catch { /* best effort */ }
    throw err;
  }
  try {
    const dfd = fs.openSync(dir, "r");
    try { fs.fsyncSync(dfd); } finally { fs.closeSync(dfd); }
  } catch {
    // Directory fsync is not supported on every platform/filesystem; the rename is still atomic.
  }
}

/** Constant-time bearer token comparison (hash first so lengths always match). */
export function tokenMatches(presented: string, expected: string): boolean {
  const a = crypto.createHash("sha256").update(presented, "utf-8").digest();
  const b = crypto.createHash("sha256").update(expected, "utf-8").digest();
  return crypto.timingSafeEqual(a, b);
}

/** Serializes async work: every task starts only after the previous one settled. */
export class SerialQueue {
  private tail: Promise<unknown> = Promise.resolve();
  private pending = 0;

  run<T>(task: () => Promise<T> | T): Promise<T> {
    this.pending++;
    const next = this.tail.then(task);
    this.tail = next.then(
      () => { this.pending--; },
      () => { this.pending--; }
    );
    return next;
  }

  async drain(): Promise<void> {
    while (this.pending > 0) await this.tail;
  }
}
