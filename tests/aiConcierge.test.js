import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as aiConcierge from "../src/lib/aiConcierge.js";
import * as db from "../src/lib/db.js";

// Mock Auth Middleware
vi.mock("../src/lib/auth.js", async (importOriginal) => {
  const mod = await importOriginal();
  return {
    ...mod,
    authMiddleware: (req, res, next) => {
      req.user = { id: "usr_guest_01", name: "Guest User", role: "guest" };
      req.raw = { user: req.user };
      next();
    },
    csrfMiddleware: (req, res, next) => next()
  };
});

// Mock child_process and generateAiResponse
vi.mock("../src/lib/aiConcierge.js", () => {
  return {
    generateAiResponse: vi.fn().mockResolvedValue({
      response: "İşte bulduğum villalar",
      recommendations: [{
        id: "l_1",
        title: "Bodrum Villa",
        city: "Muğla",
        pricePerNight: 5000,
        rating: 4.8,
        imageUrl: "http://example.com/img.jpg"
      }]
    })
  };
});

describe("AI Concierge Integration", () => {
  const GUEST_ID = "usr_guest_01";
  let token;
  let csrfToken;

  beforeEach(async () => {
    vi.clearAllMocks();

    // Login to get token and CSRF
    const loginRes = await request(app)
      .post("/api/auth/login")
      .send({ email: "guest1@example.com", password: "password123" });

    token = loginRes.body.token;

    const csrfRes = await request(app)
      .get("/api/csrf-token")
      .set("Cookie", loginRes.headers["set-cookie"] || []);

    csrfToken = csrfRes.body.csrfToken;
    if (!csrfToken) csrfToken = "mock_csrf"; // Fallback
  });

  it("should handle requestAiResponse GraphQL mutation successfully", async () => {
    const query = `
      mutation {
        requestAiResponse(message: "Bodrum villa") {
          id
          text
          senderId
          recommendations {
            id
            title
            city
          }
        }
      }
    `;

    const res = await request(app)
      .post("/graphql")
      .set("Authorization", `Bearer ${token}`)
      .set("x-csrf-token", csrfToken)
      .send({ query });

    expect(res.status).toBe(200);
    expect(res.body.errors).toBeUndefined();

    const response = res.body.data.requestAiResponse;
    expect(response.text).toBe("İşte bulduğum villalar");
    expect(response.senderId).toBe("magda");
    expect(response.recommendations.length).toBe(1);
    expect(response.recommendations[0].title).toBe("Bodrum Villa");

    // Verify it was stored in the DB
    const history = db.getMessagesForListing("magda_concierge_" + GUEST_ID);
    expect(history.length).toBeGreaterThanOrEqual(2); // user msg + AI msg

    // Find the latest magda msg
    const latestMagdaMsg = history.reverse().find(m => m.senderId === "magda");
    expect(latestMagdaMsg).toBeDefined();

    const parsedData = JSON.parse(latestMagdaMsg.text);
    expect(parsedData.text).toBe("İşte bulduğum villalar");
    expect(parsedData.recommendations.length).toBe(1);
  });

  it("should query chat history properly", async () => {
    const query = `
      query {
        magdaChatHistory {
          id
          text
          senderId
          recommendations {
            id
            title
          }
        }
      }
    `;

    const res = await request(app)
      .post("/graphql")
      .set("Authorization", `Bearer ${token}`)
      .set("x-csrf-token", csrfToken)
      .send({ query });

    expect(res.status).toBe(200);
    expect(res.body.errors).toBeUndefined();

    const history = res.body.data.magdaChatHistory;
    expect(Array.isArray(history)).toBe(true);

    const aiMsg = history.find(m => m.senderId === "magda");
    if (aiMsg) {
        expect(aiMsg.recommendations).toBeDefined();
    }
  });
});
