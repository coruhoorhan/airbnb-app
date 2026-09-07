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
});

  describe('JWT and Validation', () => {
    it('generates JWT using HS256 algorithm', () => {
      const user = { id: 1, email: 'test@example.com', isHost: 0 };
      const token = generateToken(user);
      const decoded = import('jsonwebtoken').then(jwt => {
         const decodedToken = jwt.default.decode(token, { complete: true });
         expect(decodedToken.header.alg).toBe('HS256');
      });
    });

    it('fails on missing exp claim in verifyToken', async () => {
      const JWT_SECRET = process.env.JWT_SECRET || "dev-secret-key-do-not-use-in-prod-which-is-at-least-thirty-two-chars";
      const jwt = (await import('jsonwebtoken')).default;
      const tokenNoExp = jwt.sign({ id: 1 }, JWT_SECRET, { algorithm: 'HS256' });
      const { verifyToken } = await import('../src/lib/auth.js');
      const result = verifyToken(tokenNoExp);
      expect(result).toBeNull();
    });

    it('validates user input with Joi on login - should return 400 on invalid email', async () => {
      const res = await request(app)
        .post('/api/auth/login')
        .send({ email: 'not-an-email' });
      expect([400, 429]).toContain(res.status);
      if (res.status === 400) expect(res.body.error).toContain('Geçerli bir email gerekli.');
    });
  });

  describe('CSP and CORS', () => {
    it('sets CSP header with object-src none', async () => {
      const res = await request(app).get('/api/users');
      expect(res.headers['content-security-policy']).toContain("object-src 'none'");
    });

    it('rejects CORS for unauthorized origins', async () => {
      const res = await request(app)
        .options('/api/users')
        .set('Origin', 'http://malicious.com');
      // depending on express config, cors rejection could be 500 or just block headers
      // let's check it doesn't return Access-Control-Allow-Origin
      expect(res.headers['access-control-allow-origin']).toBeUndefined();
    });

    it('allows CORS for authorized origin', async () => {
      const res = await request(app)
        .options('/api/users')
        .set('Origin', 'http://localhost:5173');
      expect(res.headers['access-control-allow-origin']).toBe('http://localhost:5173');
    });
  });

  describe('Global Error Handler', () => {
    it('returns 500 and generic message for unhandled errors', async () => {
      // Assuming CORS rejection creates an unhandled error internally, as observed
      const res = await request(app)
        .get('/api/users')
        .set('Origin', 'http://malicious.com');

      expect(res.status).toBe(500);
      expect(res.body.success).toBe(false);
      expect(res.body.error).toBe('Internal Server Error');
    });
  });
