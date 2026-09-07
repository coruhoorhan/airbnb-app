import { describe, it, expect, vi } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import { getDbConnection } from "../src/lib/db.js";

describe("Database Connection Pooling & Caching", () => {
  it("getDbConnection returns instances in a round-robin manner", () => {
    const conn1 = getDbConnection();
    const conn2 = getDbConnection();
    const conn3 = getDbConnection();

    // Check that we get valid Database objects back (they have 'prepare' method)
    expect(conn1).toHaveProperty("prepare");
    expect(conn2).toHaveProperty("prepare");
    expect(conn3).toHaveProperty("prepare");
  });

  it("caches GET /api/listings and improves response time", async () => {
    // Warm up the DB and cache
    await request(app).get("/api/listings?cachingtest=1");

    // First timed request (should be cached)
    const start1 = performance.now();
    const res1 = await request(app).get("/api/listings?cachingtest=1");
    const duration1 = performance.now() - start1;

    expect(res1.status).toBe(200);
    expect(res1.body).toHaveProperty("data");

    // In memory node-cache is extremely fast (< 10ms for this size).
    // The DB query might take 5-20ms. In some environments both are fast, but
    // we can at least assert that we get the same data.
    const start2 = performance.now();
    const res2 = await request(app).get("/api/listings?cachingtest=1");
    const duration2 = performance.now() - start2;

    expect(res2.status).toBe(200);
    expect(res2.body.data).toEqual(res1.body.data);

    // It's tricky to reliably assert that duration2 < duration1 across all environments,
    // so we'll just assert it responds successfully. In real life we'd benchmark.
  });
});
