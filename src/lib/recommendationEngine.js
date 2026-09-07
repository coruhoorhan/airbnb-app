import * as db from "./db.js";
import NodeCache from "node-cache";

// 15-minute TTL cache (900 seconds)
const recommendationCache = new NodeCache({ stdTTL: 900, checkperiod: 120 });

export function getRecommendedListings(userId = null, limit = 6) {
  const cacheKey = `rec_${userId || "guest"}_${limit}`;
  const cached = recommendationCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  const allListings = db.getAllListings();
  if (!allListings || allListings.length === 0) {
    return [];
  }

  // If no user is logged in, return top-rated listings sorted by rating and review count
  if (!userId) {
    const topRated = [...allListings].sort((a, b) => {
      const scoreA = (a.avgRating || 0) * 10 + Math.min(a.reviewCount || 0, 50);
      const scoreB = (b.avgRating || 0) * 10 + Math.min(b.reviewCount || 0, 50);
      return scoreB - scoreA;
    }).slice(0, limit);

    recommendationCache.set(cacheKey, topRated);
    return topRated;
  }

  // Fetch user history: favorites and bookings
  const userFavorites = db.getUserFavorites(userId) || [];
  const userBookings = db.getAllBookings(userId, null) || [];

  // Extract user preferences
  const preferredCategories = new Set();
  const preferredAmenities = new Set();
  let totalPriceSum = 0;
  let priceCount = 0;

  for (const fav of userFavorites) {
    if (fav.category) preferredCategories.add(fav.category);
    if (fav.pricePerNight) {
      totalPriceSum += fav.pricePerNight;
      priceCount++;
    }
  }

  for (const b of userBookings) {
    const listing = db.getListingById(b.listingId);
    if (listing) {
      if (listing.category) preferredCategories.add(listing.category);
      if (listing.pricePerNight) {
        totalPriceSum += listing.pricePerNight;
        priceCount++;
      }
      if (Array.isArray(listing.amenities)) {
        listing.amenities.forEach(a => preferredAmenities.add(a));
      }
    }
  }

  const targetAveragePrice = priceCount > 0 ? totalPriceSum / priceCount : null;

  // Score each listing based on affinity
  const scoredListings = allListings.map(l => {
    let score = (l.avgRating || 5.0) * 10; // Base score (0 - 50)

    // Category affinity (+30 points)
    if (preferredCategories.has(l.category)) {
      score += 50;
    }

    // Price similarity affinity (+20 points if within 30% of target price)
    if (targetAveragePrice && l.pricePerNight) {
      const diffRatio = Math.abs(l.pricePerNight - targetAveragePrice) / targetAveragePrice;
      if (diffRatio <= 0.3) {
        score += 20 * (1 - diffRatio);
      }
    }

    // Amenity overlap affinity (+2 points per amenity, max 20)
    if (Array.isArray(l.amenities)) {
      let matchCount = 0;
      for (const a of l.amenities) {
        if (preferredAmenities.has(a)) matchCount++;
      }
      score += Math.min(20, matchCount * 2);
    }

    return { listing: l, score };
  });

  // Sort descending by calculated affinity score
  scoredListings.sort((a, b) => b.score - a.score);

  const results = scoredListings.slice(0, limit).map(item => item.listing);
  recommendationCache.set(cacheKey, results);
  return results;
}

export function clearRecommendationCache() {
  recommendationCache.flushAll();
}
