import { describe, it, expect, beforeAll } from "vitest";
import {
  getAllListings,
  getListingById,
  insertListing,
  toggleListingStatus,
  quickUpdateListingPrice,
  deleteListing,
  insertBooking,
  getBookingById,
  updateBookingStatus,
  updateBookingPayment,
  getAllBookings,
  insertCoupon,
  getCouponByCode,
  toggleCouponStatus,
  deleteCoupon,
  incrementCouponUsage,
  getAllCoupons,
  insertPayment,
  getPaymentByBookingId,
  getPaymentByPaymentId,
  getAllPayments,
  getAllUsers,
  getUserById,
  getUserByEmail,
  insertUser,
  updateUserRole,
  toggleFavorite,
  getUserFavorites,
  isListingFavorited,
  addReview,
  recalculateListingRating,
  flagReview,
  moderateReview,
  getReviewsForListing,
  insertGuardianIssue,
  getAllGuardianIssues,
  resolveGuardianIssue,
  dismissGuardianIssue,
  clearGuardianIssues,
  getAdminAnalytics,
  insertMessage,
  getMessagesForListing,
  markMessagesRead,
  getConversationsForUser,
  getUsersByIds,
  getReviewsForListings,
  getHostRevenueAnalytics,
  updateBookingApproval,
  setListingCalendarSyncUrl,
  removeListingCalendarSync,
  db
} from "../src/lib/db.js";

describe("Parameterized Queries & Prepared Statements Security Suite", () => {
  const testUserId = `test_prep_usr_${Date.now()}`;
  const testHostId = `test_prep_host_${Date.now()}`;
  const testListingId = `test_prep_list_${Date.now()}`;

  beforeAll(() => {
    insertUser({
      id: testUserId,
      name: "Prepared Guest",
      email: `${testUserId}@example.com`,
      isHost: false
    });

    insertUser({
      id: testHostId,
      name: "Prepared Host",
      email: `${testHostId}@example.com`,
      isHost: true
    });

    insertListing({
      id: testListingId,
      hostId: testHostId,
      title: "Safe Prepared Listing",
      description: "A secure listing tested with prepared statements.",
      category: "Apartment",
      propertyType: "Entire Place",
      pricePerNight: 200,
      cleaningFee: 30,
      serviceFee: 20,
      maxGuests: 3,
      bedrooms: 1,
      beds: 2,
      baths: 1,
      address: "123 Secure St",
      city: "Fatsa",
      country: "Türkiye",
      lat: 41.025,
      lng: 37.502,
      amenities: ["WiFi", "Kitchen"],
      images: ["https://example.com/img.jpg"],
      instantBook: 1,
      isPublished: 1
    });
  });

  describe("SQL Injection Immunity in Dynamic Queries", () => {
    it("should safely handle SQL injection payloads in getAllListings filters", () => {
      // Injection attempts in search, city, and category
      const resSearch = getAllListings({ search: "' OR '1'='1" });
      expect(Array.isArray(resSearch)).toBe(true);

      const resCity = getAllListings({ city: "'; DROP TABLE listings; --" });
      expect(Array.isArray(resCity)).toBe(true);
      expect(resCity.length).toBe(0);

      // Verify listings table still exists and is untouched
      const listing = getListingById(testListingId);
      expect(listing).not.toBeNull();
      expect(listing.id).toBe(testListingId);

      const resCategory = getAllListings({ category: "' UNION SELECT * FROM users --" });
      expect(Array.isArray(resCategory)).toBe(true);
      expect(resCategory.length).toBe(0);
    });

    it("should safely handle injection in getCouponByCode", () => {
      const coupon = getCouponByCode("' OR '1'='1");
      expect(coupon).toBeUndefined();
    });

    it("should safely handle injection in getUserById and getUserByEmail", () => {
      const u1 = getUserById("' OR '1'='1");
      expect(u1).toBeUndefined();

      const u2 = getUserByEmail("' OR '1'='1");
      expect(u2).toBeUndefined();
    });
  });

  describe("Empty & Boundary Handling in IN (...) Clause Builders", () => {
    it("getUsersByIds safely handles empty arrays and non-arrays", () => {
      expect(getUsersByIds([])).toEqual([]);
      expect(getUsersByIds(null)).toEqual([]);
      expect(getUsersByIds(undefined)).toEqual([]);

      const users = getUsersByIds([testUserId, testHostId]);
      expect(users.length).toBe(2);
      expect(users.map(u => u.id)).toContain(testUserId);
      expect(users.map(u => u.id)).toContain(testHostId);
    });

    it("getReviewsForListings safely handles empty arrays and non-arrays", () => {
      expect(getReviewsForListings([])).toEqual([]);
      expect(getReviewsForListings(null)).toEqual([]);
      expect(getReviewsForListings(undefined)).toEqual([]);
    });

    it("getUserFavorites safely handles users with no favorites", () => {
      const favs = getUserFavorites(`non_existent_usr_${Date.now()}`);
      expect(favs).toEqual([]);
    });

    it("getHostRevenueAnalytics safely handles hosts with no listings", () => {
      const analytics = getHostRevenueAnalytics(`empty_host_${Date.now()}`);
      expect(analytics.totalEarnings).toBe(0);
      expect(analytics.listingBreakdown).toEqual([]);
      expect(analytics.earningsByMonth).toEqual([]);
    });
  });

  describe("Pre-compiled Prepared Statement Mutation & Read Verification", () => {
    it("manages coupons via prepared statements", () => {
      const code = `TEST_${Date.now()}`;
      insertCoupon({
        code,
        discountType: "fixed",
        discountValue: 100,
        minAmount: 500,
        expiryDate: "2026-12-31"
      });

      const coupon = getCouponByCode(code);
      expect(coupon).not.toBeNull();
      expect(coupon.discountValue).toBe(100);

      incrementCouponUsage(code);
      const afterUsage = getCouponByCode(code);
      expect(afterUsage.usageCount).toBe(1);

      toggleCouponStatus(code);
      const toggled = getCouponByCode(code);
      expect(toggled.isActive).toBe(0);

      const deleted = deleteCoupon(code);
      expect(deleted).toBe(true);
      expect(getCouponByCode(code)).toBeUndefined();
    });

    it("manages favorites via prepared statements", () => {
      expect(isListingFavorited(testUserId, testListingId)).toBe(false);

      const res1 = toggleFavorite(testUserId, testListingId);
      expect(res1.isFavorited).toBe(true);
      expect(isListingFavorited(testUserId, testListingId)).toBe(true);

      const favs = getUserFavorites(testUserId);
      expect(favs.length).toBeGreaterThanOrEqual(1);
      expect(favs.map(f => f.id)).toContain(testListingId);

      const res2 = toggleFavorite(testUserId, testListingId);
      expect(res2.isFavorited).toBe(false);
      expect(isListingFavorited(testUserId, testListingId)).toBe(false);
    });

    it("manages reviews and rating calculations via prepared statements", () => {
      const revRes = addReview({
        listingId: testListingId,
        reviewerId: testUserId,
        reviewerName: "Prepared Reviewer",
        rating: 4,
        comment: "Great prepared query test!"
      });

      expect(revRes).toHaveProperty("id");
      expect(revRes.avgRating).toBe(4);

      const reviews = getReviewsForListing(testListingId);
      expect(reviews.length).toBeGreaterThanOrEqual(1);
      expect(reviews[0].comment).toBe("Great prepared query test!");

      const flagged = flagReview(revRes.id, "Testing flag");
      expect(flagged.status).toBe("flagged");

      const hidden = moderateReview(revRes.id, "hide", "Testing hide");
      expect(hidden.status).toBe("hidden");

      const publishedOnly = getReviewsForListing(testListingId, false);
      expect(publishedOnly.find(r => r.id === revRes.id)).toBeUndefined();

      const includeHidden = getReviewsForListing(testListingId, true);
      expect(includeHidden.find(r => r.id === revRes.id)).toBeDefined();

      const deleted = moderateReview(revRes.id, "delete");
      expect(deleted.status).toBe("deleted");
    });

    it("manages messages and unread counts via prepared statements", () => {
      const msg = insertMessage({
        listingId: testListingId,
        senderId: testUserId,
        senderName: "Prepared Sender",
        text: "Hello from prepared statement!"
      });

      expect(msg).not.toBeNull();
      expect(msg.text).toBe("Hello from prepared statement!");

      const msgs = getMessagesForListing(testListingId);
      expect(msgs.length).toBeGreaterThanOrEqual(1);
      expect(msgs.find(m => m.id === msg.id)).toBeDefined();

      const convs = getConversationsForUser(testHostId);
      expect(Array.isArray(convs)).toBe(true);

      const readRes = markMessagesRead(testListingId, testHostId);
      expect(readRes).toHaveProperty("changed");
    });

    it("manages guardian issues via prepared statements", () => {
      const issue = insertGuardianIssue({
        type: "security",
        severity: "low",
        title: "Test Prepared Statement Issue",
        description: "Testing prepared statements on guardian issues"
      });

      expect(issue).not.toBeNull();
      expect(issue.status).toBe("open");

      const issues = getAllGuardianIssues("open");
      expect(issues.find(i => i.id === issue.id)).toBeDefined();

      const healed = resolveGuardianIssue(issue.id, 1);
      expect(healed.status).toBe("healed");
      expect(healed.autoHealed).toBe(1);

      const dismissed = dismissGuardianIssue(issue.id);
      expect(dismissed.status).toBe("dismissed");
    });

    it("manages calendar sync urls via prepared statements", () => {
      const updated = setListingCalendarSyncUrl(testListingId, "https://calendar.google.com/test.ics");
      expect(updated.calendarSyncUrl).toBe("https://calendar.google.com/test.ics");
      expect(updated.calendarSyncStatus).toBe("pending");

      const removed = removeListingCalendarSync(testListingId);
      expect(removed.calendarSyncUrl).toBeNull();
      expect(removed.calendarSyncStatus).toBe("disabled");
    });

    it("executes admin analytics correctly with pre-compiled statements", () => {
      const analytics = getAdminAnalytics();
      expect(analytics).toHaveProperty("financials");
      expect(analytics).toHaveProperty("counts");
      expect(analytics).toHaveProperty("performance");
      expect(analytics).toHaveProperty("monthlyTrend");
      expect(analytics.counts.totalListings).toBeGreaterThanOrEqual(1);
      expect(analytics.counts.totalUsers).toBeGreaterThanOrEqual(2);
    });
  });
});
