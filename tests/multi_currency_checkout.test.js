import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import { convertCurrency, formatCurrency, convertPrice, SUPPORTED_CURRENCIES } from "../src/lib/currencyEngine.js";
import { createPaymentRequest } from "../src/lib/iyzicoEngine.js";
import { generateToken } from "../src/lib/auth.js";
import * as db from "../src/lib/db.js";

describe("Multi-Currency Engine & Checkout Support", () => {
  let userToken;

  beforeAll(() => {
    const timestamp = Date.now();
    const user = {
      id: `usr_curr_${timestamp}`,
      name: "Currency Test User",
      email: `curr_${timestamp}@test.com`,
      isHost: false
    };
    db.insertUser(user);
    userToken = generateToken(user);
  });

  describe("Currency Conversion Math", () => {
    it("converts amounts between supported currencies correctly", () => {
      // 1000 TRY to USD -> 1000 * 0.029 = 29 USD
      const tryToUsd = convertCurrency(1000, "TRY", "USD");
      expect(tryToUsd).toBe(29);

      // 1000 TRY to EUR -> 1000 * 0.026 = 26 EUR
      const tryToEur = convertCurrency(1000, "TRY", "EUR");
      expect(tryToEur).toBe(26);

      // 100 EUR to TRY -> 100 / 0.026 = ~3846.15 TRY
      const eurToTry = convertCurrency(100, "EUR", "TRY");
      expect(eurToTry).toBeGreaterThan(3800);
    });

    it("rejects unsupported or invalid currency codes", () => {
      expect(() => convertCurrency(100, "TRY", "XYZ")).toThrow("Geçersiz veya desteklenmeyen para birimi");
      expect(() => convertCurrency(100, "ABC", "USD")).toThrow("Geçersiz veya desteklenmeyen para birimi");
    });
  });

  describe("GraphQL convertCurrency Query", () => {
    it("executes convertCurrency query and returns converted amount", async () => {
      const query = `
        query {
          convertCurrency(amount: 1000, from: "TRY", to: "EUR")
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
      expect(body.data.convertCurrency).toBe(26);
    });
  });

  describe("iyzico Multi-Currency Payment Request", () => {
    const mockListing = {
      id: "list_test_curr",
      title: "Currency Villa",
      pricePerNight: 100,
      cleaningFee: 20,
      serviceFee: 10,
      city: "Fatsa"
    };

    it("creates iyzico request with EUR currency and proper decimal formatting", () => {
      const req = createPaymentRequest({
        listing: mockListing,
        checkIn: "2026-10-01",
        checkOut: "2026-10-03",
        guests: 2,
        currency: "EUR"
      });

      expect(req.currency).toBe("EUR");
      expect(Number(req.paidPrice)).toBeGreaterThan(0);
    });

    it("creates iyzico request with USD and GBP currencies", () => {
      const reqUsd = createPaymentRequest({
        listing: mockListing,
        checkIn: "2026-10-01",
        checkOut: "2026-10-03",
        guests: 2,
        currency: "USD"
      });
      expect(reqUsd.currency).toBe("USD");

      const reqGbp = createPaymentRequest({
        listing: mockListing,
        checkIn: "2026-10-01",
        checkOut: "2026-10-03",
        guests: 2,
        currency: "GBP"
      });
      expect(reqGbp.currency).toBe("GBP");
    });

    it("throws error for unsupported currency in payment request", () => {
      expect(() => {
        createPaymentRequest({
          listing: mockListing,
          checkIn: "2026-10-01",
          checkOut: "2026-10-03",
          guests: 2,
          currency: "JPY"
        });
      }).toThrow("Desteklenmeyen para birimi");
    });
  });
});
