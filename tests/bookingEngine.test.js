import { describe, it, expect } from "vitest";
import {
  checkIntervalOverlap,
  validateBookingConflict,
  calculateBookingPrice,
  calculateCancellationRefund,
  recomputeAverageRating
} from "../src/lib/bookingEngine.js";

describe("Airbnb Core Booking & Conflict Engine (TDD Suite)", () => {
  const listingId = "list_01";

  it("TC-01: Aynı tarihlere iki rezervasyon çakışma (Overlap) üretmelidir", () => {
    const existing = [
      { id: "b1", listingId, checkIn: "2026-09-10", checkOut: "2026-09-15", status: "confirmed" }
    ];
    const result = validateBookingConflict(listingId, "2026-09-10", "2026-09-15", existing, []);
    expect(result.hasConflict).toBe(true);
  });

  it("TC-02: Kısmi çakışma (iç içe geçen tarihler) reddedilmelidir", () => {
    const existing = [
      { id: "b1", listingId, checkIn: "2026-09-10", checkOut: "2026-09-15", status: "confirmed" }
    ];
    const result = validateBookingConflict(listingId, "2026-09-12", "2026-09-18", existing, []);
    expect(result.hasConflict).toBe(true);
  });

  it("TC-03: Sırt Sırta (Same-day Checkout = Next Checkin) ÇAKIŞMA SAYILMAMALIDIR (Airbnb Standardı)", () => {
    const existing = [
      { id: "b1", listingId, checkIn: "2026-09-10", checkOut: "2026-09-15", status: "confirmed" }
    ];
    // Misafir 2: 15 Eylül giriş, 20 Eylül çıkış (Çakışma olmamalı)
    const result = validateBookingConflict(listingId, "2026-09-15", "2026-09-20", existing, []);
    expect(result.hasConflict).toBe(false);
  });

  it("TC-04: Ev sahibinin kapattığı (availability block) tarihler çakışma üretmelidir", () => {
    const blocks = [
      { id: "ab1", listingId, startDate: "2026-10-01", endDate: "2026-10-10", reason: "Tadilat" }
    ];
    const result = validateBookingConflict(listingId, "2026-10-05", "2026-10-08", [], blocks);
    expect(result.hasConflict).toBe(true);
    expect(result.reason).toContain("kapatılmış");
  });

  it("TC-05: Fiyat hesaplaması gece sayısı, temizlik ve hizmet bedelini doğru toplamalıdır", () => {
    const price = calculateBookingPrice("2026-09-10", "2026-09-13", 1000, 200, 100);
    expect(price.nights).toBe(3);
    expect(price.basePrice).toBe(3000);
    expect(price.totalPrice).toBe(3300);
  });

  it("TC-06: Esnek İptal Politikası (Girişe 48 saat kala %100, 12 saat kala ilk gece kesintili)", () => {
    const checkIn = Date.now() + 48 * 3600 * 1000;
    const refund48h = calculateCancellationRefund(checkIn, 5000, 1000, "flexible", false);
    expect(refund48h.refundPercentage).toBe(100);
    expect(refund48h.refundAmount).toBe(5000);

    const checkInNear = Date.now() + 12 * 3600 * 1000;
    const refund12h = calculateCancellationRefund(checkInNear, 5000, 1000, "flexible", false);
    expect(refund12h.refundAmount).toBe(4000); // 5000 - 1000 ilk gece
  });

  it("TC-07: Ev sahibi iptal ettiğinde misafire DAİMA %100 kesintisiz iade yapılmalıdır", () => {
    const refund = calculateCancellationRefund("2026-09-10", 8500, 2000, "strict", true);
    expect(refund.refundAmount).toBe(8500);
    expect(refund.refundPercentage).toBe(100);
  });

  it("TC-08: Ortalama puan denormalizasyonu yeni yorum eklendiğinde doğru hesaplanmalıdır", () => {
    // 4.80 ortalama, 10 yorum. Yeni gelen puan: 5
    // Yeni ortalama = (4.8 * 10 + 5) / 11 = 53 / 11 = 4.82
    const rating = recomputeAverageRating(4.80, 10, 5);
    expect(rating.avgRating).toBe(4.82);
    expect(rating.reviewCount).toBe(11);
  });

  it("TC-09: Giriş tarihi çıkış tarihinden büyük veya eşitse hata fırlatmalıdır", () => {
    expect(() => calculateBookingPrice("2026-09-15", "2026-09-10", 1000)).toThrow();
  });
});
