import { describe, it, expect } from "vitest";
import { 
  db, 
  getAllListings,
  getListingById,
  insertListing,
  toggleListingStatus, 
  quickUpdateListingPrice, 
  insertCoupon, 
  toggleCouponStatus, 
  deleteCoupon, 
  getAllUsers, 
  updateUserRole, 
  getAdminAnalytics 
} from "../src/lib/db.js";

describe("Admin Operations & Analytics Engine", () => {
  let testListingId = "list_admin_test";

  it("toggles listing status between published and unpublished", () => {
    let listings = getAllListings({ publishedOnly: false });
    if (listings.length === 0) {
      insertListing({
        id: testListingId,
        hostId: "usr_host_01",
        title: "Test Listing",
        description: "Test description",
        category: "Villa",
        propertyType: "Villa",
        pricePerNight: 3000,
        cleaningFee: 500,
        serviceFee: 300,
        maxGuests: 4,
        bedrooms: 2,
        beds: 2,
        baths: 1,
        address: "Test Cad.",
        city: "Ordu",
        country: "Türkiye",
        lat: 41.0,
        lng: 37.5,
        amenities: [],
        images: [],
        instantBook: 1,
        isPublished: 1
      });
      listings = getAllListings({ publishedOnly: false });
    }

    const target = listings[0];
    const initialStatus = target.isPublished;

    const toggled = toggleListingStatus(target.id);
    expect(toggled).toBeDefined();
    expect(toggled.isPublished).toBe(!initialStatus);

    // Revert back
    const restored = toggleListingStatus(target.id);
    expect(restored.isPublished).toBe(initialStatus);
  });

  it("updates listing price and cleaning fee quickly", () => {
    const listings = getAllListings({ publishedOnly: false });
    const target = listings[0];
    const newPrice = 5200;
    const newCleaning = 800;

    const updated = quickUpdateListingPrice(target.id, newPrice, newCleaning);
    expect(updated).toBeDefined();
    expect(updated.pricePerNight).toBe(newPrice);
    expect(updated.cleaningFee).toBe(newCleaning);

    // Restore
    quickUpdateListingPrice(target.id, target.pricePerNight, target.cleaningFee);
  });

  it("creates, toggles, and deletes coupons dynamically", () => {
    const testCode = "TESTKODU";
    
    // Create
    const created = insertCoupon({
      code: testCode,
      discountType: "percentage",
      discountValue: 15,
      minAmount: 1000,
      expiryDate: "2026-12-31"
    });
    expect(created.code).toBe(testCode);
    expect(created.discountValue).toBe(15);
    expect(created.isActive).toBe(1);

    // Toggle
    const toggled = toggleCouponStatus(testCode);
    expect(toggled.isActive).toBe(0);

    // Delete
    const deleted = deleteCoupon(testCode);
    expect(deleted).toBe(true);
  });

  it("retrieves users list and updates user roles", () => {
    const users = getAllUsers();
    expect(users.length).toBeGreaterThan(0);

    const targetUser = users[0];
    const originalRole = targetUser.isHost;

    const updated = updateUserRole(targetUser.id, !originalRole);
    expect(updated.isHost).toBe(!originalRole);

    // Restore
    updateUserRole(targetUser.id, originalRole);
  });

  it("computes accurate admin analytics metrics", () => {
    const analytics = getAdminAnalytics();
    expect(analytics).toBeDefined();
    expect(analytics.financials).toBeDefined();
    expect(typeof analytics.financials.grossVolume).toBe("number");
    expect(analytics.counts).toBeDefined();
    expect(analytics.counts.totalListings).toBeGreaterThan(0);
    expect(analytics.counts.totalUsers).toBeGreaterThan(0);
    expect(Array.isArray(analytics.monthlyTrend)).toBe(true);
  });
});
