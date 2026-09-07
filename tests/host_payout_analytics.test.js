import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";
import { generateToken } from "../src/lib/auth.js";

describe("Host Payout & Revenue Analytics GraphQL API", () => {
  let hostToken;
  let otherUserToken;
  let hostId;
  let otherUserId;
  let listing1Id;
  let listing2Id;

  beforeAll(() => {
    const timestamp = Date.now();
    hostId = `host_analytics_${timestamp}`;
    otherUserId = `user_analytics_${timestamp}`;
    listing1Id = `list_rev_1_${timestamp}`;
    listing2Id = `list_rev_2_${timestamp}`;

    const hostUser = {
      id: hostId,
      name: "Analytics Test Host",
      email: `host_${timestamp}@analytics.test`,
      isHost: true
    };
    db.insertUser(hostUser);
    hostToken = generateToken(hostUser);

    const otherUser = {
      id: otherUserId,
      name: "Other Test User",
      email: `other_${timestamp}@analytics.test`,
      isHost: false
    };
    db.insertUser(otherUser);
    otherUserToken = generateToken(otherUser);

    // Create 2 listings for this host
    db.insertListing({
      id: listing1Id,
      hostId: hostId,
      title: "Seaside Villa Analytics Test",
      description: "A beautiful villa with ocean view",
      pricePerNight: 1000,
      city: "Fatsa",
      category: "villa",
      propertyType: "entire_home",
      maxGuests: 4,
      bedrooms: 2,
      beds: 2,
      baths: 2,
      cleaningFee: 150,
      serviceFee: 50,
      latitude: 41.0,
      longitude: 37.5,
      lat: 41.0,
      lng: 37.5,
      address: "Sahil Cad. No: 12",
      country: "Türkiye",
      state: "Ordu",
      createdAt: Date.now()
    });

    db.insertListing({
      id: listing2Id,
      hostId: hostId,
      title: "Mountain Bungalow Analytics Test",
      description: "Cozy wooden bungalow in nature",
      pricePerNight: 800,
      city: "Fatsa",
      category: "bungalow",
      propertyType: "entire_home",
      maxGuests: 2,
      bedrooms: 1,
      beds: 1,
      baths: 1,
      cleaningFee: 100,
      serviceFee: 40,
      latitude: 41.02,
      longitude: 37.48,
      lat: 41.02,
      lng: 37.48,
      address: "Doga Sok. No: 5",
      country: "Türkiye",
      state: "Ordu",
      createdAt: Date.now()
    });

    // Create bookings: 1 completed on listing1, 1 confirmed on listing2
    db.insertBooking({
      id: `book_rev_1_${timestamp}`,
      listingId: listing1Id,
      guestId: otherUserId,
      hostId: hostId,
      checkIn: "2026-09-10",
      checkOut: "2026-09-13",
      numGuests: 2,
      nightlyPrice: 1000,
      cleaningFee: 150,
      serviceFee: 50,
      totalPrice: 3150,
      paymentStatus: "paid",
      paymentId: `pay_rev_1_${timestamp}`,
      status: "completed",
      createdAt: Date.now()
    });

    db.insertBooking({
      id: `book_rev_2_${timestamp}`,
      listingId: listing2Id,
      guestId: otherUserId,
      hostId: hostId,
      checkIn: "2026-09-20",
      checkOut: "2026-09-22",
      numGuests: 2,
      nightlyPrice: 800,
      cleaningFee: 100,
      serviceFee: 40,
      totalPrice: 1700,
      paymentStatus: "paid",
      paymentId: `pay_rev_2_${timestamp}`,
      status: "confirmed",
      createdAt: Date.now()
    });
  });

  it("rejects unauthenticated requests to hostRevenueAnalytics with 401", async () => {
    const query = `
      query {
        hostRevenueAnalytics(hostId: "${hostId}") {
          totalEarnings
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .send({ query });

    expect(res.status).toBe(401);
  });

  it("rejects unauthorized access when another user tries to access host analytics", async () => {
    const query = `
      query {
        hostRevenueAnalytics(hostId: "${hostId}") {
          totalEarnings
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", `Bearer ${otherUserToken}`)
      .send({ query });

    expect(res.status).toBe(200);
    const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
    expect(body.errors).toBeDefined();
    expect(body.errors[0].message).toContain("Unauthorized");
  });

  it("returns accurate aggregated analytics for the authenticated host", async () => {
    const query = `
      query {
        hostRevenueAnalytics(hostId: "${hostId}") {
          hostId
          totalEarnings
          pendingPayoutsTotal
          averageOccupancyRate
          earningsByMonth {
            month
            earnings
            bookingsCount
          }
          listingBreakdown {
            listingId
            title
            totalEarnings
            bookingsCount
          }
          pendingPayouts {
            bookingId
            amount
            guestName
          }
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", `Bearer ${hostToken}`)
      .send({ query });

    expect(res.status).toBe(200);
    const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
    expect(body.data).toBeDefined();
    const analytics = body.data.hostRevenueAnalytics;

    expect(analytics.hostId).toBe(hostId);
    // Total net earnings: (3150 - 50) + (1700 - 40) = 3100 + 1660 = 4760
    expect(analytics.totalEarnings).toBe(4760);
    expect(analytics.pendingPayoutsTotal).toBeGreaterThan(0);
    expect(analytics.averageOccupancyRate).toBeGreaterThan(0);

    // Earnings by month
    expect(analytics.earningsByMonth.length).toBeGreaterThan(0);
    expect(analytics.earningsByMonth[0].month).toBe("2026-09");
    expect(analytics.earningsByMonth[0].earnings).toBe(4760);
    expect(analytics.earningsByMonth[0].bookingsCount).toBe(2);

    // Listing breakdown
    expect(analytics.listingBreakdown.length).toBe(2);
    const l1 = analytics.listingBreakdown.find(l => l.listingId === listing1Id);
    expect(l1).toBeDefined();
    expect(l1.totalEarnings).toBe(3100);
    expect(l1.bookingsCount).toBe(1);

    const l2 = analytics.listingBreakdown.find(l => l.listingId === listing2Id);
    expect(l2).toBeDefined();
    expect(l2.totalEarnings).toBe(1660);
    expect(l2.bookingsCount).toBe(1);

    // Pending payouts
    expect(analytics.pendingPayouts.length).toBeGreaterThan(0);
  });
});
