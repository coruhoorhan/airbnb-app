import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';

describe("HTTP Strict Transport Security (HSTS)", () => {
  it("should include Strict-Transport-Security header with max-age>=31536000, includeSubDomains, and preload", async () => {
    const res = await request(app)
      .get("/api/health")
      .set("x-forwarded-proto", "https");

    expect(res.headers["strict-transport-security"]).toBeDefined();
    const hsts = res.headers["strict-transport-security"];
    expect(hsts).toContain("max-age=");
    const maxAgeMatch = hsts.match(/max-age=(\d+)/);
    expect(maxAgeMatch).not.toBeNull();
    const maxAge = parseInt(maxAgeMatch[1], 10);
    expect(maxAge).toBeGreaterThanOrEqual(31536000);
    expect(hsts).toContain("includeSubDomains");
    expect(hsts).toContain("preload");
  });
});
