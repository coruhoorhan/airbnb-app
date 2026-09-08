import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';

describe("HSTS - Strict Transport Security", () => {
  it("should return Strict-Transport-Security header for HTTPS requests", async () => {
    const res = await request(app)
      .get("/api/health")
      .set("x-forwarded-proto", "https");

    expect(res.headers).toHaveProperty("strict-transport-security");
    const hstsHeader = res.headers["strict-transport-security"];
    expect(hstsHeader).toContain("max-age=31536000");
    expect(hstsHeader).toContain("includeSubDomains");
    expect(hstsHeader).toContain("preload");
  });
});
