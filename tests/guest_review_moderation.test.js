import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";
import { generateToken } from "../src/lib/auth.js";

describe("Guest Review Moderation System", () => {
  let hostToken;
  let otherUserToken;
  let hostId;
  let otherUserId;
  let listingId;
  let review1Id;
  let review2Id;

  beforeAll(() => {
    const timestamp = Date.now();
    hostId = `host_mod_${timestamp}`;
    otherUserId = `user_mod_${timestamp}`;
    listingId = `list_mod_${timestamp}`;

    const hostUser = {
      id: hostId,
      name: "Moderation Host",
      email: `host_${timestamp}@mod.test`,
      isHost: true
    };
    db.insertUser(hostUser);
    hostToken = generateToken(hostUser);

    const otherUser = {
      id: otherUserId,
      name: "Other User",
      email: `other_${timestamp}@mod.test`,
      isHost: false
    };
    db.insertUser(otherUser);
    otherUserToken = generateToken(otherUser);

    db.insertListing({
      id: listingId,
      hostId: hostId,
      title: "Review Moderation Test Villa",
      description: "Testing moderation features",
      pricePerNight: 500,
      city: "Fatsa",
      category: "villa",
      propertyType: "entire_home",
      maxGuests: 4,
      bedrooms: 2,
      beds: 2,
      baths: 2,
      cleaningFee: 50,
      serviceFee: 25,
      latitude: 41.0,
      longitude: 37.5,
      lat: 41.0,
      lng: 37.5,
      address: "Sahil Cad. 100",
      country: "Türkiye",
      state: "Ordu",
      createdAt: Date.now()
    });

    // Add 2 reviews: 1 positive (5 star), 1 negative (1 star)
    db.addReview({
      listingId,
      reviewerId: otherUserId,
      reviewerName: "Happy Guest",
      rating: 5,
      comment: "Harika bir deneyimdi!"
    });
    db.addReview({
      listingId,
      reviewerId: otherUserId,
      reviewerName: "Spam Reviewer",
      rating: 1,
      comment: "Spam / inappropriate content"
    });

    const reviews = db.getReviewsForListing(listingId, true);
    review1Id = reviews.find(r => r.rating === 5).id;
    review2Id = reviews.find(r => r.rating === 1).id;
  });

  it("adds reviews with default status 'published'", () => {
    const r = db.db.prepare("SELECT * FROM reviews WHERE id = ?").get(review1Id);
    expect(r).toBeDefined();
    expect(r.status).toBe("published");
  });

  it("allows host to flag a review with a reason", async () => {
    const mutation = `
      mutation {
        flagReview(id: "${review2Id}", reason: "Spam ve yanıltıcı içerik") {
          id
          status
          moderationReason
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", `Bearer ${hostToken}`)
      .send({ query: mutation });

    expect(res.status).toBe(200);
    const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
    expect(body.data).toBeDefined();
    expect(body.data.flagReview.status).toBe("flagged");
    expect(body.data.flagReview.moderationReason).toContain("Spam");
  });

  it("rejects moderation attempts from non-host users", async () => {
    const mutation = `
      mutation {
        moderateReview(id: "${review2Id}", action: "hide", reason: "Unauthorized hide") {
          id
          status
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", `Bearer ${otherUserToken}`)
      .send({ query: mutation });

    expect(res.status).toBe(200);
    const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
    expect(body.errors).toBeDefined();
    expect(body.errors[0].message).toContain("Unauthorized");
  });

  it("allows host to hide a review, excluding it from public reviews and recalculating rating", async () => {
    const mutation = `
      mutation {
        moderateReview(id: "${review2Id}", action: "hide", reason: "İçerik kurallarına aykırı") {
          id
          status
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", `Bearer ${hostToken}`)
      .send({ query: mutation });

    expect(res.status).toBe(200);
    const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
    expect(body.data.moderateReview.status).toBe("hidden");

    // Public getReviewsForListing excludes hidden reviews
    const publicReviews = db.getReviewsForListing(listingId);
    expect(publicReviews.find(r => r.id === review2Id)).toBeUndefined();
    expect(publicReviews.length).toBe(1);

    // Listing rating recalculated to 5.0 (since 1-star review is hidden)
    const listing = db.getListingById(listingId);
    expect(listing.avgRating).toBe(5.0);
    expect(listing.reviewCount).toBe(1);
  });
});
