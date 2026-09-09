import { describe, it, expect, beforeAll } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import * as db from '../src/lib/db.js';
import { hashToken, isTokenRevoked } from '../src/lib/auth.js';

describe("Security - Refresh Token Rotation & Revocation List", () => {
  let testUser;
  let loginRes;
  let initialRefreshToken;
  let initialAccessToken;

  beforeAll(() => {
    const userId = `u_rot_${Date.now()}`;
    testUser = {
      id: userId,
      name: "Token Rotation User",
      email: `token_rot_${Date.now()}@test.com`,
      isHost: false
    };
    db.insertUser(testUser);
  });

  it("should issue access token and refresh token on login with secure cookies", async () => {
    loginRes = await request(app)
      .post("/api/auth/login")
      .send({ email: testUser.email });

    expect(loginRes.status).toBe(200);
    expect(loginRes.body.success).toBe(true);
    expect(loginRes.body.accessToken).toBeDefined();
    expect(loginRes.body.refreshToken).toBeDefined();
    expect(loginRes.body.token).toBe(loginRes.body.accessToken);

    initialRefreshToken = loginRes.body.refreshToken;
    initialAccessToken = loginRes.body.accessToken;

    // Verify token hash exists in db
    const hashed = hashToken(initialRefreshToken);
    const dbRecord = db.getRefreshTokenByHash(hashed);
    expect(dbRecord).toBeDefined();
    expect(dbRecord.userId).toBe(testUser.id);
    expect(dbRecord.revokedAt).toBeNull();

    // Verify cookies
    const cookies = loginRes.headers['set-cookie'];
    expect(cookies).toBeDefined();
    const tokenCookie = cookies.find(c => c.startsWith('token='));
    const refreshCookie = cookies.find(c => c.startsWith('refreshToken='));
    expect(tokenCookie).toBeDefined();
    expect(refreshCookie).toBeDefined();
    expect(tokenCookie).toContain('HttpOnly');
    expect(tokenCookie).toContain('Secure');
    expect(refreshCookie).toContain('HttpOnly');
    expect(refreshCookie).toContain('Secure');
  });

  it("should return a new access token and rotated refresh token on /api/auth/refresh", async () => {
    const refreshRes = await request(app)
      .post("/api/auth/refresh")
      .send({ refreshToken: initialRefreshToken });

    expect(refreshRes.status).toBe(200);
    expect(refreshRes.body.success).toBe(true);
    expect(refreshRes.body.accessToken).toBeDefined();
    expect(refreshRes.body.refreshToken).toBeDefined();
    expect(refreshRes.body.refreshToken).not.toBe(initialRefreshToken);

    const newRefreshToken = refreshRes.body.refreshToken;

    // Verify old token is marked revoked and stored in revoked_tokens
    const oldHash = hashToken(initialRefreshToken);
    const oldRecord = db.getRefreshTokenByHash(oldHash);
    expect(oldRecord.revokedAt).not.toBeNull();
    expect(oldRecord.replacedByTokenHash).toBe(hashToken(newRefreshToken));
    expect(db.isTokenRevoked(oldHash)).toBe(true);

    // Verify new token is stored and active
    const newHash = hashToken(newRefreshToken);
    const newRecord = db.getRefreshTokenByHash(newHash);
    expect(newRecord).toBeDefined();
    expect(newRecord.userId).toBe(testUser.id);
    expect(newRecord.revokedAt).toBeNull();
  });

  it("should return 401 when using an old/revoked refresh token after rotation", async () => {
    // Attempt to reuse initialRefreshToken which was rotated
    const reuseRes = await request(app)
      .post("/api/auth/refresh")
      .send({ refreshToken: initialRefreshToken });

    expect(reuseRes.status).toBe(401);
    expect(reuseRes.body.success).toBe(false);
    expect(reuseRes.body.error).toContain("revoked");
  });

  it("should return 401 when refreshing without token or with invalid token", async () => {
    // Missing token
    const resNoToken = await request(app)
      .post("/api/auth/refresh")
      .send({});
    expect(resNoToken.status).toBe(401);

    // Invalid token
    const resInvalid = await request(app)
      .post("/api/auth/refresh")
      .send({ refreshToken: "invalid_random_token_12345" });
    expect(resInvalid.status).toBe(401);
  });

  it("should support refresh token rotation via Cookie header", async () => {
    // Perform fresh login
    const login = await request(app)
      .post("/api/auth/login")
      .send({ email: testUser.email });

    const cookies = login.headers['set-cookie'];
    const refreshCookie = cookies.find(c => c.startsWith('refreshToken=')).split(';')[0];

    const refreshRes = await request(app)
      .post("/api/auth/refresh")
      .set("Cookie", refreshCookie);

    expect(refreshRes.status).toBe(200);
    expect(refreshRes.body.success).toBe(true);
    expect(refreshRes.body.accessToken).toBeDefined();
    expect(refreshRes.body.refreshToken).toBeDefined();
  });

  it("should revoke refresh token on logout and persist in revocation list", async () => {
    const login = await request(app)
      .post("/api/auth/login")
      .send({ email: testUser.email });

    const activeRefreshToken = login.body.refreshToken;
    const activeHash = hashToken(activeRefreshToken);

    const csrfRes = await request(app).get('/api/auth/csrf');
    const csrfToken = csrfRes.body.csrfToken;
    const csrfCookie = csrfRes.headers['set-cookie'].find(c => c.startsWith('_csrf_secret=')).split(';')[0];

    const logoutRes = await request(app)
      .post("/api/auth/logout")
      .set("x-csrf-token", csrfToken)
      .set("Cookie", [`refreshToken=${activeRefreshToken}`, csrfCookie])
      .send({ refreshToken: activeRefreshToken });

    expect(logoutRes.status).toBe(200);
    expect(db.isTokenRevoked(activeHash)).toBe(true);

    // Try to refresh with the logged out token
    const refreshAfterLogout = await request(app)
      .post("/api/auth/refresh")
      .send({ refreshToken: activeRefreshToken });

    expect(refreshAfterLogout.status).toBe(401);
  });
});
