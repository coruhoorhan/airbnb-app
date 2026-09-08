import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";
import { generateToken } from "../src/lib/auth.js";
import { validateBookingConflict } from "../src/lib/bookingEngine.js";

describe("iCal Calendar Availability Sync", () => {
  let hostToken;
  let otherHostToken;
  let hostId;
  let otherHostId;
  let listingId;
  let bookingId;

  beforeAll(() => {
    const timestamp = Date.now();
    hostId = `host_ical_${timestamp}`;
    otherHostId = `other_ical_${timestamp}`;
    listingId = `list_ical_${timestamp}`;
    bookingId = `book_ical_${timestamp}`;

    const hostUser = {
      id: hostId,
      name: "iCal Test Host",
      email: `host_${timestamp}@ical.test`,
      isHost: true
    };
    db.insertUser(hostUser);
    hostToken = generateToken(hostUser);

    const otherHost = {
      id: otherHostId,
      name: "Other iCal Host",
      email: `other_${timestamp}@ical.test`,
      isHost: true
    };
    db.insertUser(otherHost);
    otherHostToken = generateToken(otherHost);

    db.insertUser({
      id: `guest_ical_${timestamp}`,
      name: "iCal Guest",
      email: `guest_${timestamp}@ical.test`,
      isHost: false
    });

    db.insertListing({
      id: listingId,
      hostId: hostId,
      title: "iCal Sync Test Villa",
      description: "Testing iCal import and export",
      pricePerNight: 750,
      city: "Fatsa",
      category: "villa",
      propertyType: "entire_home",
      maxGuests: 4,
      bedrooms: 2,
      beds: 2,
      baths: 2,
      cleaningFee: 100,
      serviceFee: 50,
      latitude: 41.02,
      longitude: 37.49,
      lat: 41.02,
      lng: 37.49,
      address: "Sahil Cad. 45",
      country: "Türkiye",
      state: "Ordu",
      createdAt: Date.now()
    });

    db.insertBooking({
      id: bookingId,
      listingId: listingId,
      guestId: `guest_ical_${timestamp}`,
      hostId: hostId,
      checkIn: "2026-10-10",
      checkOut: "2026-10-15",
      numGuests: 2,
      nightlyPrice: 750,
      cleaningFee: 100,
      serviceFee: 50,
      totalPrice: 3900,
      status: "confirmed",
      approvalStatus: "approved",
      paymentStatus: "paid",
      createdAt: Date.now()
    });
  });

  it("GET /api/calendar/:listingId.ics returns valid iCal feed with VEVENT entries", async () => {
    const res = await request(app).get(`/api/calendar/${listingId}.ics`);
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toContain("text/calendar");
    expect(res.text).toContain("BEGIN:VCALENDAR");
    expect(res.text).toContain("END:VCALENDAR");
    expect(res.text).toContain("BEGIN:VEVENT");
    expect(res.text).toContain(`UID:booking-${bookingId}@airbnb-fatsa.com`);
    expect(res.text).toContain("DTSTART;VALUE=DATE:20261010");
    expect(res.text).toContain("DTEND;VALUE=DATE:20261015");
  });

  it("POST /api/calendar/:listingId/sync imports external iCal and creates blocked bookings", async () => {
    const mockIcalData = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Booking.com//Sync//EN
BEGIN:VEVENT
UID:external-booking-9988@booking.com
DTSTART:20261110
DTEND:20261115
SUMMARY:Booking.com Reserved
END:VEVENT
END:VCALENDAR`;

    const res = await request(app)
      .post(`/api/calendar/${listingId}/sync`)
      .set("Authorization", `Bearer ${hostToken}`)
      .send({ icalData: mockIcalData });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.data.syncedCount).toBe(1);

    // Verify calendar conflict engine prevents overlapping booking
    const activeBookings = db.getAllBookings(null, hostId);
    const conflictCheck = validateBookingConflict(listingId, "2026-11-12", "2026-11-18", activeBookings);
    expect(conflictCheck.hasConflict).toBe(true);
  });

  it("GraphQL setCalendarSyncUrl and removeCalendarSync manage sync configuration", async () => {
    // 1. Set Sync URL
    const setMutation = `
      mutation {
        setCalendarSyncUrl(listingId: "${listingId}", url: "https://airbnb.com/calendar/ical/123.ics") {
          id
          calendarSync {
            status
            externalUrl
          }
        }
      }
    `;
    const setRes = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", `Bearer ${hostToken}`)
      .send({ query: setMutation });

    expect(setRes.status).toBe(200);
    const setBody = typeof setRes.body === "string" ? JSON.parse(setRes.body) : setRes.body;
    expect(setBody.data.setCalendarSyncUrl.calendarSync.externalUrl).toBe("https://airbnb.com/calendar/ical/123.ics");

    // 2. Query Listing with calendarSync field
    const getQuery = `
      query {
        listing(id: "${listingId}") {
          id
          calendarSync {
            status
            externalUrl
          }
        }
      }
    `;
    const getRes = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", `Bearer ${hostToken}`)
      .send({ query: getQuery });

    expect(getRes.status).toBe(200);
    const getBody = typeof getRes.body === "string" ? JSON.parse(getRes.body) : getRes.body;
    expect(getBody.data.listing.calendarSync.externalUrl).toBe("https://airbnb.com/calendar/ical/123.ics");

    // 3. Remove Sync URL
    const removeMutation = `
      mutation {
        removeCalendarSync(listingId: "${listingId}") {
          id
          calendarSync {
            status
            externalUrl
          }
        }
      }
    `;
    const removeRes = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", `Bearer ${hostToken}`)
      .send({ query: removeMutation });

    expect(removeRes.status).toBe(200);
    const removeBody = typeof removeRes.body === "string" ? JSON.parse(removeRes.body) : removeRes.body;
    expect(removeBody.data.removeCalendarSync.calendarSync.externalUrl).toBeNull();
  });
});
