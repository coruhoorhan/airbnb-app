import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";
import { generateToken } from "../src/lib/auth.js";
import { calculateBookingPrice, validateBookingConflict } from "../src/lib/bookingEngine.js";
import { buildPaymentRequest, formatIyzicoPrice } from "../src/lib/iyzicoEngine.js";

describe("Uçtan Uca Rezervasyon & Ödeme Yaşam Döngüsü (E2E)", () => {
  let guestToken;
  let hostToken;
  let guestUser;
  let hostUser;
  let listing;
  let calculatedPrice;
  let createdBookingId;

  const checkInDate = "2026-10-15";
  const checkOutDate = "2026-10-18"; // 3 nights

  beforeAll(() => {
    const timestamp = Date.now();

    guestUser = {
      id: `usr_guest_pay_${timestamp}`,
      name: "Mehmet Demir",
      email: `mehmet_${timestamp}@fatsa.bel.tr`,
      isHost: false
    };
    db.insertUser(guestUser);
    guestToken = generateToken(guestUser);

    hostUser = {
      id: `usr_host_pay_${timestamp}`,
      name: "Ayşe Yılmaz",
      email: `ayse_${timestamp}@fatsa.bel.tr`,
      isHost: true
    };
    db.insertUser(hostUser);
    hostToken = generateToken(hostUser);

    listing = {
      id: `list_pay_e2e_${timestamp}`,
      hostId: hostUser.id,
      title: "Dolunay Sahil Manzaralı Taş Villa",
      description: "Fatsa Dolunay mevkisinde panoramik Karadeniz manzaralı lüks villa",
      pricePerNight: 1500,
      cleaningFee: 200,
      serviceFee: 100,
      city: "Fatsa",
      category: "villa",
      propertyType: "entire_home",
      maxGuests: 4,
      bedrooms: 2,
      beds: 3,
      baths: 2,
      lat: 41.035,
      lng: 37.495,
      address: "Dolunay Sahil Cad. No: 88",
      country: "Türkiye",
      state: "Ordu",
      instantBook: 1,
      createdAt: Date.now()
    };
    db.insertListing(listing);
  });

  it("1. Adım: Misafir dinamik fiyat hesaplar (Gecelik + Temizlik + Hizmet Bedeli)", () => {
    calculatedPrice = calculateBookingPrice(
      checkInDate,
      checkOutDate,
      listing.pricePerNight,
      listing.cleaningFee,
      listing.serviceFee
    );

    expect(calculatedPrice.nights).toBe(3);
    expect(calculatedPrice.basePrice).toBe(4500); // 3 * 1500
    expect(calculatedPrice.cleaningFee).toBe(200);
    expect(calculatedPrice.serviceFee).toBe(100);
    expect(calculatedPrice.totalPrice).toBe(4800); // 4500 + 200 + 100
  });

  it("2. Adım: Misafir rezervasyon oluşturur (Status: pending/confirmed)", async () => {
    const res = await request(app)
      .post("/api/bookings")
      .set("Authorization", `Bearer ${guestToken}`)
      .send({
        listingId: listing.id,
        guestId: guestUser.id,
        checkIn: checkInDate,
        checkOut: checkOutDate,
        numGuests: 2,
        couponCode: null
      });

    expect(res.status).toBe(201);
    expect(res.body.success).toBe(true);
    createdBookingId = res.body.data.id;
    expect(createdBookingId).toBeDefined();
    expect(res.body.data.paymentStatus).toBe("unpaid");

    const savedBooking = db.getBookingById(createdBookingId);
    expect(savedBooking).toBeDefined();
    expect(savedBooking.totalPrice).toBe(4800);
  });

  it("3. Adım: iyzico ödeme isteği oluşturulur ve ödeme tamamlanır (paidStatus: paid)", () => {
    const paymentReq = buildPaymentRequest({
      listing,
      buyer: {
        id: guestUser.id,
        name: guestUser.name,
        email: guestUser.email,
        phone: "+905321112233",
        address: "Fatsa Sahil Cad. No: 1",
        city: "Ordu",
        country: "Turkey"
      },
      checkIn: checkInDate,
      checkOut: checkOutDate,
      numGuests: 2,
      priceMath: calculatedPrice,
      currency: "TRY"
    });

    expect(paymentReq.price).toBe(formatIyzicoPrice(4800));
    expect(paymentReq.paidPrice).toBe(formatIyzicoPrice(4800));
    expect(paymentReq.currency).toBe("TRY");
    expect(paymentReq.basketItems.length).toBeGreaterThanOrEqual(1);

    // Record mock payment in DB & update booking payment status
    const paymentId = `pay_e2e_${Date.now()}`;
    db.insertPayment({
      id: paymentId,
      bookingId: createdBookingId,
      paymentId: paymentId,
      conversationId: paymentReq.conversationId,
      provider: "iyzico",
      amount: calculatedPrice.totalPrice,
      currency: "TRY",
      status: "success",
      createdAt: Date.now()
    });

    const updatedBooking = db.updateBookingPayment(createdBookingId, "paid", paymentId);
    expect(updatedBooking.paymentStatus).toBe("paid");
  });

  it("4. Adım: Ev sahibi rezervasyonu onaylar (GraphQL approveBooking -> approved/confirmed)", async () => {
    const mutation = `
      mutation {
        approveBooking(id: "${createdBookingId}", approve: true) {
          id
          status
          approvalStatus
          paymentStatus
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
    expect(body.data.approveBooking.paymentStatus).toBe("paid");

    const approvedInDb = db.getBookingById(createdBookingId);
    expect(approvedInDb.approvalStatus).toBe("approved");
    expect(approvedInDb.status).toBe("confirmed");
  });

  it("5. Adım: iCal takvim akışında tarihler kilitlenir ve çakışan rezervasyonlar engellenir", async () => {
    // Check .ics feed export
    const icsRes = await request(app).get(`/api/calendar/${listing.id}.ics`);
    expect(icsRes.status).toBe(200);
    expect(icsRes.headers["content-type"]).toContain("text/calendar");
    expect(icsRes.text).toContain("BEGIN:VCALENDAR");
    expect(icsRes.text).toContain("BEGIN:VEVENT");
    expect(icsRes.text).toContain(`UID:booking-${createdBookingId}@airbnb-fatsa.com`);
    expect(icsRes.text).toContain("DTSTART;VALUE=DATE:20261015");
    expect(icsRes.text).toContain("DTEND;VALUE=DATE:20261018");

    // Verify booking conflict engine catches overlap
    const activeBookings = db.getAllBookings(null, hostUser.id);
    const conflictCheck = validateBookingConflict(listing.id, "2026-10-16", "2026-10-19", activeBookings);
    expect(conflictCheck.hasConflict).toBe(true);
    expect(conflictCheck.reason).toContain("başka bir misafir tarafından rezerve edilmiş");
  });

  it("6. Adım: Ev sahibi gelir analitiğinde hakediş ve kazanç başarıyla güncellenir", async () => {
    const analyticsQuery = `
      query {
        hostRevenueAnalytics(hostId: "${hostUser.id}") {
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
      .send({ query: analyticsQuery });

    expect(res.status).toBe(200);
    const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
    expect(body.data).toBeDefined();
    const analytics = body.data.hostRevenueAnalytics;

    expect(analytics.hostId).toBe(hostUser.id);
    // Net Host Earnings: totalPrice (4800) - serviceFee (100) = 4700 TL
    expect(analytics.totalEarnings).toBe(4700);
    expect(analytics.pendingPayoutsTotal).toBe(4700);

    // Monthly Earnings check
    expect(analytics.earningsByMonth.length).toBeGreaterThan(0);
    const octEarnings = analytics.earningsByMonth.find(m => m.month === "2026-10");
    expect(octEarnings).toBeDefined();
    expect(octEarnings.earnings).toBe(4700);
    expect(octEarnings.bookingsCount).toBe(1);

    // Listing Breakdown check
    const listingStat = analytics.listingBreakdown.find(l => l.listingId === listing.id);
    expect(listingStat).toBeDefined();
    expect(listingStat.totalEarnings).toBe(4700);
    expect(listingStat.bookingsCount).toBe(1);

    // Pending Payouts check
    const pendingItem = analytics.pendingPayouts.find(p => p.bookingId === createdBookingId);
    expect(pendingItem).toBeDefined();
    expect(pendingItem.amount).toBe(4700);
    expect(pendingItem.guestName).toBe("Mehmet Demir");
  });
});
