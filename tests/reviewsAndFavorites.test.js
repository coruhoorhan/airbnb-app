import { describe, it, expect, beforeEach } from "vitest";
import { 
  db, 
  getAllListings,
  toggleFavorite, 
  getUserFavorites, 
  isListingFavorited, 
  addReview, 
  getListingById 
} from "../src/lib/db.js";

describe("Reviews & Favorites Engine", () => {
  const testUserId = "usr_test_fav";
  let targetListingId = "list_01";

  beforeEach(() => {
    const listings = getAllListings({ publishedOnly: false });
    if (listings.length > 0) {
      targetListingId = listings[0].id;
    }
  });

  it("toggles favorite state on a listing and persists in DB", () => {
    // Initial state check
    const initial = isListingFavorited(testUserId, targetListingId);

    // Toggle on
    const res1 = toggleFavorite(testUserId, targetListingId);
    expect(res1.isFavorited).toBe(!initial);
    expect(isListingFavorited(testUserId, targetListingId)).toBe(!initial);

    // Check user favorites list
    const favs = getUserFavorites(testUserId);
    if (res1.isFavorited) {
      expect(favs.some((l) => l.id === targetListingId)).toBe(true);
    }

    // Toggle back
    const res2 = toggleFavorite(testUserId, targetListingId);
    expect(res2.isFavorited).toBe(initial);
  });

  it("adds a verified review and recalculates listing average rating", () => {
    const reviewRes = addReview({
      listingId: targetListingId,
      bookingId: `bkg_rev_test_${Date.now()}`,
      reviewerId: "usr_guest_01",
      reviewerName: "Test Misafir",
      rating: 5,
      comment: "Mükemmel Karadeniz manzarası ve çok temiz bir ev!"
    });

    expect(reviewRes).toBeDefined();
    expect(reviewRes.reviewCount).toBeGreaterThan(0);

    const listingAfter = getListingById(targetListingId);
    expect(listingAfter.reviewCount).toBe(reviewRes.reviewCount);
    expect(listingAfter.avgRating).toBeGreaterThanOrEqual(1.0);
  });
});
