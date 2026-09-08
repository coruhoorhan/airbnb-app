import { describe, it, expect, beforeAll } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import * as db from '../src/lib/db.js';
import { generateToken, generateCsrfToken } from '../src/lib/auth.js';

describe("Security - Rate Limiter & Input Sanitization", () => {
  let testUserToken;
  let csrfToken;
  let csrfCookie;

  beforeAll(() => {
    const userId = `test_security_user_${Date.now()}`;
    const mockUser = { id: userId, name: 'Security User', email: `sec_${Date.now()}@test.com`, isHost: true };
    db.insertUser(mockUser);
    testUserToken = generateToken(mockUser);
    csrfToken = generateCsrfToken();
    csrfCookie = `_csrf_secret=${csrfToken}`;
  });

  it("should return 400 for malformed listing creation requests", async () => {
    // Missing required fields
    const res1 = await request(app)
      .post("/api/listings")
      .set("Authorization", `Bearer ${testUserToken}`)
      .set("x-csrf-token", csrfToken)
      .set("Cookie", csrfCookie)
      .send({ hostId: "u_1" }); // missing title, pricePerNight

    expect(res1.status).toBeGreaterThanOrEqual(400);

    // Negative pricePerNight
    const res2 = await request(app)
      .post("/api/listings")
      .set("Authorization", `Bearer ${testUserToken}`)
      .set("x-csrf-token", csrfToken)
      .set("Cookie", csrfCookie)
      .send({
        hostId: "u_1",
        title: "Test",
        pricePerNight: -100 // invalid negative price
      });

    expect(res2.status).toBe(400);
  });

  it("should return 400 for malformed booking creation requests", async () => {
    // Missing required fields
    const res1 = await request(app)
      .post("/api/bookings")
      .set("Authorization", `Bearer ${testUserToken}`)
      .set("x-csrf-token", csrfToken)
      .set("Cookie", csrfCookie)
      .send({ guestId: "u_2" }); // missing listingId, checkIn, checkOut

    expect(res1.status).toBeGreaterThanOrEqual(400);
  });

  it("should rate limit requests over 100 per minute globally on /api", async () => {
    let lastStatus = 200;
    // Send 101 requests to /api/health
    for (let i = 0; i < 102; i++) {
      const res = await request(app).get("/api/health");
      lastStatus = res.status;
    }
    expect(lastStatus).toBe(429);
  });

  it("should set Strict-Transport-Security header on requests", async () => {
    const res = await request(app)
      .get("/api/health")
      .set("x-forwarded-proto", "https");

    expect(res.headers["strict-transport-security"]).toBe(
      "max-age=31536000; includeSubDomains; preload"
    );
  });
});
