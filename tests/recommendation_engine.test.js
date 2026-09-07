import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";
import { generateToken } from "../src/lib/auth.js";
import { getRecommendedListings, clearRecommendationCache } from "../src/lib/recommendationEngine.js";

describe("AI-Powered Personalized Listing Recommendations", () => {
  let userToken;
  let userId;

  beforeAll(() => {
    clearRecommendationCache();
    const timestamp = Date.now();
    userId = `user_rec_${timestamp}`;

    const testUser = {
      id: userId,
      name: "Recommendation Test User",
      email: `rec_${timestamp}@test.com`,
      isHost: false
    };
    db.insertUser(testUser);
    userToken = generateToken(testUser);

    // Favorite list_01 (Category: Lüks Villa)
    db.toggleFavorite(userId, "list_01");

    // Book list_01
    db.insertBooking({
      id: `book_rec_${timestamp}`,
      listingId: "list_01",
      guestId: userId,
      hostId: "usr_host_01",
      checkIn: "2026-09-01",
      checkOut: "2026-09-04",
      numGuests: 2,
      nightlyPrice: 4850,
      cleaningFee: 750,
      serviceFee: 450,
      totalPrice: 15750,
      status: "confirmed",
      createdAt: Date.now()
    });
  });

  it("returns fallback top-rated listings for anonymous/unauthenticated users", () => {
    clearRecommendationCache();
    const recommendations = getRecommendedListings(null, 3);
    expect(recommendations.length).toBeGreaterThan(0);
    expect(recommendations[0].avgRating).toBeGreaterThanOrEqual(4.0);
  });

  it("returns personalized recommendations prioritizing user preferences (Lüks Villa)", () => {
    clearRecommendationCache();
    const recommendations = getRecommendedListings(userId, 3);
    expect(recommendations.length).toBeGreaterThan(0);
    // User preferences strongly favor 'Lüks Villa'
    expect(recommendations[0].category).toBe("Lüks Villa");
    expect(recommendations[0].id).toBe("list_01");
  });

  it("serves subsequent recommendation requests from cache", () => {
    const rec1 = getRecommendedListings(userId, 3);
    const rec2 = getRecommendedListings(userId, 3);
    expect(rec1).toEqual(rec2);
  });

  it("executes GraphQL recommendedListings query successfully", async () => {
    const query = `
      query {
        recommendedListings(userId: "${userId}", limit: 3) {
          id
          title
          category
          pricePerNight
          avgRating
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", `Bearer ${userToken}`)
      .send({ query });

    expect(res.status).toBe(200);
    const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
    expect(body.data).toBeDefined();
    expect(body.data.recommendedListings).toBeDefined();
    expect(body.data.recommendedListings.length).toBeGreaterThan(0);
    expect(body.data.recommendedListings[0].category).toBe("Lüks Villa");
    expect(body.data.recommendedListings[0].id).toBe("list_01");
  });
});
