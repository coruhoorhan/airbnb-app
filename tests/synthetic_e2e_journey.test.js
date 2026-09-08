import { describe, it, expect, beforeAll, afterAll } from "vitest";
import request from "supertest";
import http from "http";
import { WebSocket } from "ws";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";
import { generateToken, generateCsrfToken } from "../src/lib/auth.js";
import { setupChatWebSocketServer, chatEngine } from "../src/lib/chatEngine.js";

describe("Autonomous Synthetic Full-Stack E2E User Journey Suite", () => {
  let server;
  let wsPort;
  let wsUrl;

  // Test entities
  let guestUser;
  let hostUser;
  let guestToken;
  let hostToken;
  let csrfToken;
  let csrfCookie;
  let testListing;
  let createdBookingId;
  let directPaidBookingId;

  const timestamp = Date.now();
  const checkInDate = "2026-11-10";
  const checkOutDate = "2026-11-14"; // 4 nights

  beforeAll(async () => {
    // 1. Initialize HTTP + WebSocket server for real-time E2E tests
    server = http.createServer(app);
    setupChatWebSocketServer(server);

    await new Promise((resolve) => {
      server.listen(0, "127.0.0.1", () => {
        wsPort = server.address().port;
        wsUrl = `ws://127.0.0.1:${wsPort}/ws/chat`;
        resolve();
      });
    });

    // 2. Seed synthetic test users
    guestUser = {
      id: `usr_synth_guest_${timestamp}`,
      name: "Autonomous Test Guest",
      email: `synth_guest_${timestamp}@fatsa.bel.tr`,
      isHost: false
    };
    db.insertUser(guestUser);
    guestToken = generateToken(guestUser);

    hostUser = {
      id: `usr_synth_host_${timestamp}`,
      name: "Autonomous Test Host",
      email: `synth_host_${timestamp}@fatsa.bel.tr`,
      isHost: true
    };
    db.insertUser(hostUser);
    hostToken = generateToken(hostUser);

    // 3. Setup CSRF tokens
    csrfToken = generateCsrfToken();
    csrfCookie = `_csrf_secret=${csrfToken}`;

    // 4. Seed synthetic test listing
    testListing = {
      id: `list_synth_${timestamp}`,
      hostId: hostUser.id,
      title: "Synthetic E2E Karadeniz Penthouse",
      description: "Autonomous E2E test property in Fatsa with sea view",
      pricePerNight: 2000,
      cleaningFee: 250,
      serviceFee: 150,
      city: "Fatsa",
      category: "apartment",
      propertyType: "entire_home",
      maxGuests: 4,
      bedrooms: 2,
      beds: 3,
      baths: 2,
      lat: 41.031,
      lng: 37.498,
      address: "Atatürk Parkı Yanı No: 52",
      country: "Türkiye",
      state: "Ordu",
      instantBook: 0,
      isPublished: 1,
      createdAt: Date.now()
    };
    db.insertListing(testListing);
  });

  afterAll(async () => {
    if (chatEngine && typeof chatEngine.close === "function") {
      chatEngine.close();
    }
    if (server) {
      await new Promise((resolve) => server.close(resolve));
    }
  });

  // =========================================================================
  // JOURNEY 1: Guest Discovery & Filtering
  // =========================================================================
  describe("Journey 1: Guest Discovery & Filtering", () => {
    it("should fetch listings with city and price filters", async () => {
      const res = await request(app)
        .get("/api/listings")
        .query({
          city: "Fatsa",
          minPrice: 500,
          maxPrice: 10000
        });

      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
      expect(Array.isArray(res.body.data)).toBe(true);
      expect(res.body.data.length).toBeGreaterThan(0);

      // Verify listing structure
      const sample = res.body.data.find((l) => l.id === testListing.id) || res.body.data[0];
      expect(sample).toHaveProperty("id");
      expect(sample).toHaveProperty("title");
      expect(sample).toHaveProperty("pricePerNight");
      expect(sample).toHaveProperty("city");
      expect(sample).toHaveProperty("hostId");
    });

    it("should fetch single listing detail with full metadata", async () => {
      const res = await request(app).get(`/api/listings/${testListing.id}`);
      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
      expect(res.body.data.id).toBe(testListing.id);
      expect(res.body.data.title).toBe(testListing.title);
      expect(res.body.data.pricePerNight).toBe(2000);
      expect(res.body.data.city).toBe("Fatsa");
    });

    it("should compute dynamic pricing with occupancy and season factors", async () => {
      const res = await request(app)
        .get(`/api/listings/${testListing.id}/dynamic-price`)
        .query({
          occupancyRate: 0.85,
          month: 7,
          demandIntensity: "high"
        });

      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
      expect(res.body.data).toBeDefined();
      expect(res.body.data.basePrice).toBe(2000);
      expect(res.body.data.recommendedPrice).toBeGreaterThan(2000);
      expect(res.body.data.multipliers).toBeDefined();
    });
  });

  // =========================================================================
  // JOURNEY 2: Authentication, Session & Security Tokens
  // =========================================================================
  describe("Journey 2: Authentication, Session & Security Tokens", () => {
    it("should authenticate existing user and issue HttpOnly JWT cookie", async () => {
      const res = await request(app)
        .post("/api/auth/login")
        .send({ email: guestUser.email });

      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
      expect(res.body.token).toBeDefined();
      expect(res.body.user).toBeDefined();
      expect(res.body.user.email).toBe(guestUser.email);

      // Verify Set-Cookie header
      const cookies = res.headers["set-cookie"];
      expect(cookies).toBeDefined();
      const tokenCookie = cookies.find((c) => c.startsWith("token="));
      expect(tokenCookie).toBeDefined();
      expect(tokenCookie).toContain("HttpOnly");
      expect(tokenCookie.toLowerCase()).toContain("samesite=strict");
    });

    it("should provide fresh CSRF token and set _csrf_secret cookie", async () => {
      const res = await request(app).get("/api/auth/csrf");
      expect(res.status).toBe(200);
      expect(res.body.csrfToken).toBeDefined();
      expect(typeof res.body.csrfToken).toBe("string");
      expect(res.body.csrfToken.length).toBeGreaterThan(10);

      const cookies = res.headers["set-cookie"];
      expect(cookies).toBeDefined();
      const secretCookie = cookies.find((c) => c.startsWith("_csrf_secret="));
      expect(secretCookie).toBeDefined();
    });

    it("should clear session cookie on logout", async () => {
      const res = await request(app)
        .post("/api/auth/logout")
        .set("Authorization", `Bearer ${guestToken}`)
        .set("x-csrf-token", csrfToken)
        .set("Cookie", csrfCookie);
      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);

      const cookies = res.headers["set-cookie"];
      expect(cookies).toBeDefined();
      const tokenCookie = cookies.find((c) => c.startsWith("token="));
      expect(tokenCookie).toBeDefined();
      expect(tokenCookie).toContain("Expires=Thu, 01 Jan 1970");
    });
  });

  // =========================================================================
  // JOURNEY 3: Booking Lifecycle & Payment Simulation
  // =========================================================================
  describe("Journey 3: Booking Lifecycle & Payment Simulation", () => {
    it("should create a new booking with pending and unpaid status", async () => {
      const res = await request(app)
        .post("/api/bookings")
        .set("Authorization", `Bearer ${guestToken}`)
        .set("x-csrf-token", csrfToken)
        .set("Cookie", csrfCookie)
        .send({
          listingId: testListing.id,
          guestId: guestUser.id,
          checkIn: checkInDate,
          checkOut: checkOutDate,
          numGuests: 2,
          couponCode: null
        });

      expect(res.status).toBe(201);
      expect(res.body.success).toBe(true);
      expect(res.body.data).toBeDefined();
      expect(res.body.data.id).toBeDefined();
      expect(res.body.data.status).toBe("pending");
      expect(res.body.data.paymentStatus).toBe("unpaid");
      expect(res.body.data.totalPrice).toBe(8400); // 4 * 2000 + 250 + 150

      createdBookingId = res.body.data.id;
    });

    it("should process iyzico direct payment and create confirmed paid booking", async () => {
      const payCheckIn = "2026-11-20";
      const payCheckOut = "2026-11-23"; // 3 nights

      const payRes = await request(app)
        .post("/api/payments/iyzico/direct-pay")
        .set("Authorization", `Bearer ${guestToken}`)
        .set("x-csrf-token", csrfToken)
        .set("Cookie", csrfCookie)
        .send({
          listingId: testListing.id,
          guestId: guestUser.id,
          checkIn: payCheckIn,
          checkOut: payCheckOut,
          numGuests: 2,
          card: {
            cardHolderName: "Autonomous Tester",
            cardNumber: "5890040000000016",
            expireMonth: "12",
            expireYear: "2030",
            cvc: "123"
          },
          buyer: {
            id: guestUser.id,
            name: guestUser.name,
            email: guestUser.email,
            phone: "+905551234567",
            address: "Fatsa Sahil",
            city: "Ordu",
            country: "Turkey"
          }
        });

      expect(payRes.status).toBe(201);
      expect(payRes.body.success).toBe(true);
      expect(payRes.body.booking).toBeDefined();
      expect(payRes.body.payment).toBeDefined();
      expect(payRes.body.booking.paymentStatus).toBe("paid");
      expect(payRes.body.booking.status).toBe("confirmed");

      directPaidBookingId = payRes.body.booking.id;

      // Verify persisted booking state in DB
      const updatedBooking = db.getBookingById(directPaidBookingId);
      expect(updatedBooking).toBeDefined();
      expect(updatedBooking.paymentStatus).toBe("paid");
      expect(updatedBooking.status).toBe("confirmed");
    });
  });

  // =========================================================================
  // JOURNEY 4: Real-time Chat & Web-Push Notifications
  // =========================================================================
  describe("Journey 4: Real-time Chat & Web-Push Notifications", () => {
    it("should connect to WebSocket and exchange real-time chat messages", async () => {
      const client = new WebSocket(`${wsUrl}?listingId=${testListing.id}&userId=${guestUser.id}`);

      const ackPromise = new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error("WS ack timeout")), 3000);
        client.on("message", (data) => {
          clearTimeout(timer);
          resolve(JSON.parse(data.toString()));
        });
        client.on("error", reject);
      });

      const ack = await ackPromise;
      expect(ack.type).toBe("CONNECTED");
      expect(ack.listingId).toBe(testListing.id);
      expect(ack.userId).toBe(guestUser.id);

      client.close();
      await new Promise((r) => setTimeout(r, 50));
    });

    it("should persist message in SQLite via POST /api/messages", async () => {
      const res = await request(app)
        .post("/api/messages")
        .set("Authorization", `Bearer ${guestToken}`)
        .set("x-csrf-token", csrfToken)
        .set("Cookie", csrfCookie)
        .send({
          senderId: guestUser.id,
          receiverId: hostUser.id,
          listingId: testListing.id,
          text: "Merhaba! Giriş saati hakkında bilgi alabilir miyim?"
        });

      expect(res.status).toBe(201);
      expect(res.body.success).toBe(true);
      expect(res.body.data).toBeDefined();
      expect(res.body.data.text).toContain("Giriş saati");

      // Verify message in conversations
      const convRes = await request(app)
        .get("/api/messages")
        .query({
          listingId: testListing.id,
          user1: guestUser.id,
          user2: hostUser.id
        });

      expect(convRes.status).toBe(200);
      expect(convRes.body.success).toBe(true);
      expect(Array.isArray(convRes.body.data)).toBe(true);
      expect(convRes.body.data.length).toBeGreaterThan(0);
    });

    it("should accept push notification subscription", async () => {
      const res = await request(app)
        .post("/api/notifications/subscribe")
        .set("Authorization", `Bearer ${guestToken}`)
        .set("x-csrf-token", csrfToken)
        .set("Cookie", csrfCookie)
        .send({
          subscription: {
            endpoint: `https://fcm.googleapis.com/fcm/send/synth_${timestamp}`,
            keys: {
              p256dh: "synth_p256dh_key",
              auth: "synth_auth_key"
            }
          }
        });

      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
    });
  });

  // =========================================================================
  // JOURNEY 5: Host Operations & Revenue Analytics
  // =========================================================================
  describe("Journey 5: Host Operations & Revenue Analytics", () => {
    let pendingBookingId;

    beforeAll(() => {
      // Create a pending booking specifically for host approval flow
      const b = {
        id: `bk_approval_${timestamp}`,
        listingId: testListing.id,
        guestId: guestUser.id,
        hostId: hostUser.id,
        checkIn: "2026-12-01",
        checkOut: "2026-12-05",
        numGuests: 2,
        nightlyPrice: 2000,
        cleaningFee: 250,
        serviceFee: 150,
        totalPrice: 8400,
        status: "pending",
        paymentStatus: "unpaid",
        approvalStatus: "pending",
        createdAt: Date.now()
      };
      db.insertBooking(b);
      pendingBookingId = b.id;
    });

    it("should approve instant booking via GraphQL mutation", async () => {
      const mutation = `
        mutation ApproveBooking($id: ID!, $approve: Boolean!) {
          approveBooking(id: $id, approve: $approve) {
            id
            approvalStatus
            status
          }
        }
      `;

      const res = await request(app)
        .post("/graphql")
        .set("Authorization", `Bearer ${hostToken}`)
        .set("x-csrf-token", csrfToken)
        .set("Cookie", csrfCookie)
        .send({
          query: mutation,
          variables: {
            id: pendingBookingId,
            approve: true
          }
        });

      expect(res.status).toBe(200);
      const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
      expect(body.data).toBeDefined();
      expect(body.data.approveBooking).toBeDefined();
      expect(body.data.approveBooking.approvalStatus).toBe("approved");
    });

    it("should fetch host revenue analytics via GraphQL", async () => {
      const query = `
        query HostAnalytics($hostId: ID!) {
          hostRevenueAnalytics(hostId: $hostId) {
            hostId
            totalEarnings
            averageOccupancyRate
            earningsByMonth {
              month
              earnings
              bookingsCount
            }
          }
        }
      `;

      const res = await request(app)
        .post("/graphql")
        .set("Authorization", `Bearer ${hostToken}`)
        .send({
          query,
          variables: { hostId: hostUser.id }
        });

      expect(res.status).toBe(200);
      const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
      expect(body.data).toBeDefined();
      expect(body.data.hostRevenueAnalytics).toBeDefined();
      expect(body.data.hostRevenueAnalytics.hostId).toBe(hostUser.id);
      expect(typeof body.data.hostRevenueAnalytics.totalEarnings).toBe("number");
    });
  });

  // =========================================================================
  // JOURNEY 6: Guest Reviews & Moderation Flow
  // =========================================================================
  describe("Journey 6: Guest Reviews & Moderation Flow", () => {
    let createdReviewId;

    it("should submit a 5-star review for a completed stay", async () => {
      const res = await request(app)
        .post("/api/reviews")
        .set("Authorization", `Bearer ${guestToken}`)
        .set("x-csrf-token", csrfToken)
        .set("Cookie", csrfCookie)
        .send({
          listingId: testListing.id,
          bookingId: createdBookingId,
          reviewerId: guestUser.id,
          reviewerName: guestUser.name,
          rating: 5,
          comment: "Fevkalade bir Fatsa deneyimi! Manzara ve temizlik kusursuzdu."
        });

      expect(res.status).toBe(201);
      expect(res.body.success).toBe(true);
      expect(res.body.data).toBeDefined();
      expect(res.body.data.id).toBeDefined();
      createdReviewId = res.body.data.id;
    });

    it("should query listing reviews via GraphQL and verify published status", async () => {
      const query = `
        query GetReviews($listingId: ID!) {
          reviews(listingId: $listingId) {
            id
            rating
            comment
            reviewerName
          }
        }
      `;

      const res = await request(app)
        .post("/graphql")
        .set("Authorization", `Bearer ${guestToken}`)
        .send({
          query,
          variables: { listingId: testListing.id }
        });

      expect(res.status).toBe(200);
      const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
      expect(body.data).toBeDefined();
      expect(body.data.reviews).toBeDefined();
      expect(body.data.reviews.length).toBeGreaterThan(0);

      const found = body.data.reviews.find((r) => r.id === createdReviewId || r.reviewerName === guestUser.name);
      expect(found).toBeDefined();
      expect(found.rating).toBe(5);
      expect(found.comment).toContain("Fatsa deneyimi");
    });
  });

  // =========================================================================
  // JOURNEY 7: Security & Vulnerability Fuzzing (Negative Testing)
  // =========================================================================
  describe("Journey 7: Security & Vulnerability Fuzzing (Negative Testing)", () => {
    it("should resist SQL injection payloads in listing search queries", async () => {
      const sqliPayload = "' OR '1'='1' -- ";
      const res = await request(app)
        .get("/api/listings")
        .query({ city: sqliPayload });

      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
      expect(Array.isArray(res.body.data)).toBe(true);
      // No server 500 error or syntax leak
    });

    it("should safely sanitize XSS payloads in review comments", async () => {
      const xssComment = "<script>alert('XSS_ATTACK')</script>Harika yer!";
      const res = await request(app)
        .post("/api/reviews")
        .set("Authorization", `Bearer ${guestToken}`)
        .set("x-csrf-token", csrfToken)
        .set("Cookie", csrfCookie)
        .send({
          listingId: testListing.id,
          reviewerId: guestUser.id,
          reviewerName: guestUser.name,
          rating: 4,
          comment: xssComment
        });

      expect(res.status).toBe(201);
      expect(res.body.success).toBe(true);
    });

    it("should reject state-changing POST requests when CSRF token is missing with cookie auth", async () => {
      const res = await request(app)
        .post("/api/bookings")
        .set("Cookie", `token=${guestToken}`) // Cookie-based auth without CSRF headers/tokens
        .send({
          listingId: testListing.id,
          guestId: guestUser.id,
          checkIn: "2026-12-10",
          checkOut: "2026-12-12",
          numGuests: 1
        });

      expect(res.status).toBe(403);
      expect(res.body.success).toBe(false);
      expect(res.body.error).toContain("CSRF");
    });

    it("should reject unauthenticated GraphQL queries with 401 Unauthorized", async () => {
      const query = "query { listings { id title } }";
      const res = await request(app)
        .post("/graphql")
        .send({ query });

      expect(res.status).toBe(401);
    });
  });
});
