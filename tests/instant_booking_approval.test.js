import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";
import { generateToken } from "../src/lib/auth.js";
import { validateBookingConflict } from "../src/lib/bookingEngine.js";

describe("Instant Booking Approval Flow", () => {
  let hostToken;
  let guestToken;
  let otherHostToken;
  let hostId;
  let guestId;
  let otherHostId;
  let listingId;
  let bookingId;

  beforeAll(() => {
    const timestamp = Date.now();
    hostId = `host_appr_${timestamp}`;
    guestId = `guest_appr_${timestamp}`;
    otherHostId = `other_host_appr_${timestamp}`;
    listingId = `list_appr_${timestamp}`;
    bookingId = `book_appr_${timestamp}`;

    const hostUser = {
      id: hostId,
      name: "Approval Host User",
      email: `host_${timestamp}@approval.test`,
      isHost: true
    };
    db.insertUser(hostUser);
    hostToken = generateToken(hostUser);

    const guestUser = {
      id: guestId,
      name: "Approval Guest User",
      email: `guest_${timestamp}@approval.test`,
      isHost: false
    };
    db.insertUser(guestUser);
    guestToken = generateToken(guestUser);

    const otherHost = {
      id: otherHostId,
      name: "Other Host User",
      email: `other_${timestamp}@approval.test`,
      isHost: true
    };
    db.insertUser(otherHost);
    otherHostToken = generateToken(otherHost);

    db.insertListing({
      id: listingId,
      hostId: hostId,
      title: "Approval Workflow Test Villa",
      description: "Testing instant booking and host approval flow",
      pricePerNight: 500,
      city: "Fatsa",
      category: "villa",
      propertyType: "entire_home",
      maxGuests: 4,
      bedrooms: 2,
      beds: 2,
      baths: 1,
      cleaningFee: 50,
      serviceFee: 25,
      latitude: 41.03,
      longitude: 37.5,
      lat: 41.03,
      lng: 37.5,
      address: "Cumhuriyet Meydanı No: 1",
      country: "Türkiye",
      state: "Ordu",
      instantBook: 1,
      createdAt: Date.now()
    });

    db.insertBooking({
      id: bookingId,
      listingId: listingId,
      guestId: guestId,
      hostId: hostId,
      checkIn: "2026-10-01",
      checkOut: "2026-10-05",
      numGuests: 2,
      nightlyPrice: 500,
      cleaningFee: 50,
      serviceFee: 25,
      totalPrice: 2075,
      paymentStatus: "paid",
      paymentId: `pay_appr_${timestamp}`,
      status: "pending",
      createdAt: Date.now()
    });
  });

  it("persists approvalStatus default as pending in database", () => {
    const b = db.getBookingById(bookingId);
    expect(b).toBeDefined();
    expect(b.approvalStatus).toBe("pending");
  });

  it("rejects unauthorized approval attempts from non-host users", async () => {
    const mutation = `
      mutation {
        approveBooking(id: "${bookingId}", approve: true) {
          id
          approvalStatus
          status
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", `Bearer ${otherHostToken}`)
      .send({ query: mutation });

    expect(res.status).toBe(200);
    const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
    expect(body.errors).toBeDefined();
    expect(body.errors[0].message).toContain("Unauthorized");
  });

  it("allows host to approve booking and transitions status to confirmed", async () => {
    const mutation = `
      mutation {
        approveBooking(id: "${bookingId}", approve: true) {
          id
          approvalStatus
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
    expect(body.data).toBeDefined();
    expect(body.data.approveBooking.approvalStatus).toBe("approved");
    expect(body.data.approveBooking.status).toBe("confirmed");

    const updated = db.getBookingById(bookingId);
    expect(updated.approvalStatus).toBe("approved");
    expect(updated.status).toBe("confirmed");
  });

  it("allows host to reject booking, releasing calendar dates", async () => {
    const timestamp = Date.now();
    const rejectBookingId = `book_reject_${timestamp}`;
    db.insertBooking({
      id: rejectBookingId,
      listingId: listingId,
      guestId: guestId,
      hostId: hostId,
      checkIn: "2026-11-01",
      checkOut: "2026-11-05",
      numGuests: 2,
      nightlyPrice: 500,
      cleaningFee: 50,
      serviceFee: 25,
      totalPrice: 2075,
      status: "pending",
      createdAt: Date.now()
    });

    const mutation = `
      mutation {
        approveBooking(id: "${rejectBookingId}", approve: false) {
          id
          approvalStatus
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
    expect(body.data.approveBooking.approvalStatus).toBe("rejected");
    expect(body.data.approveBooking.status).toBe("cancelled");

    // Verify calendar conflict engine ignores rejected booking
    const existing = [db.getBookingById(rejectBookingId)];
    const conflictCheck = validateBookingConflict(listingId, "2026-11-01", "2026-11-05", existing);
    expect(conflictCheck.hasConflict).toBe(false);
  });
});
