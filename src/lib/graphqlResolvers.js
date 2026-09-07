import { getRecommendedListings } from "./recommendationEngine.js";
import { convertCurrency } from "./currencyEngine.js";
import { createNotification } from "./notifications.js";
import * as db from "./db.js";

function hydrateListing(listing, context) {
  if (!listing) return listing;
  if (typeof listing.amenities === 'string') listing.amenities = JSON.parse(listing.amenities);
  if (typeof listing.images === 'string') listing.images = JSON.parse(listing.images);
  listing.host = () => context.userLoader.load(listing.hostId);
  listing.reviews = () => context.reviewsLoader.load(listing.id);
  listing.calendarSync = () => ({
    status: listing.calendarSyncStatus || "idle",
    externalUrl: listing.calendarSyncUrl || null,
    lastSyncedAt: listing.lastSyncedAt || null
  });
  return listing;
}

export const rootValue = {
  user: ({ id }, context) => {
    const user = db.getUserById(id);
    if (!user) return null;
    if (!context || !context.user || (context.user.id !== id && !context.user.isAdmin)) {
      delete user.email;
      delete user.phone;
    }
    return user;
  },
  users: () => {
    return db.getAllUsers().map(user => {
      delete user.email;
      delete user.phone;
      return user;
    });
  },
  listing: ({ id }, context) => {
    const listing = db.getListingById(id);
    return hydrateListing(listing, context);
  },
  listings: ({ city, category }, context) => {
    const filters = {};
    if (city) filters.city = city;
    if (category) filters.category = category;
    return db.getAllListings(filters).map(l => hydrateListing(l, context));
  },
  booking: ({ id }, context) => {
    const b = db.getBookingById(id);
    if (b) {
      b.listing = () => hydrateListing(db.getListingById(b.listingId), context);
      b.guest = () => context.userLoader.load(b.guestId);
    }
    return b;
  },
  bookings: ({ guestId, hostId }, context) => {
    return db.getAllBookings(guestId, hostId).map(b => {
      b.listing = () => hydrateListing(db.getListingById(b.listingId), context);
      b.guest = () => context.userLoader.load(b.guestId);
      return b;
    });
  },
  recommendedListings: ({ userId, limit }, context) => {
    return getRecommendedListings(userId, limit).map(l => hydrateListing(l, context));
  },
  reviews: ({ listingId }, context) => {
    return context.reviewsLoader.load(listingId);
  },
  
  
  setCalendarSyncUrl: ({ listingId, url }, context) => {
    const listing = db.getListingById(listingId);
    if (!listing) throw new Error("Listing not found");
    if (!context || !context.user || (context.user.id !== listing.hostId && !context.user.isAdmin)) {
      throw new Error("Unauthorized: You can only configure calendar sync for your own listing.");
    }
    const updated = db.setListingCalendarSyncUrl(listingId, url);
    return hydrateListing(updated, context);
  },
  removeCalendarSync: ({ listingId }, context) => {
    const listing = db.getListingById(listingId);
    if (!listing) throw new Error("Listing not found");
    if (!context || !context.user || (context.user.id !== listing.hostId && !context.user.isAdmin)) {
      throw new Error("Unauthorized: You can only configure calendar sync for your own listing.");
    }
    const updated = db.removeListingCalendarSync(listingId);
    return hydrateListing(updated, context);
  },

  
  flagReview: ({ id, reason }, context) => {
    const review = db.db.prepare("SELECT * FROM reviews WHERE id = ?").get(id);
    if (!review) throw new Error("Review not found");
    const listing = db.getListingById(review.listingId);
    if (!context || !context.user || (context.user.id !== listing.hostId && !context.user.isAdmin)) {
      throw new Error("Unauthorized: Only the listing host or admin can flag a review.");
    }
    return db.flagReview(id, reason);
  },
  moderateReview: ({ id, action, reason }, context) => {
    const review = db.db.prepare("SELECT * FROM reviews WHERE id = ?").get(id);
    if (!review) throw new Error("Review not found");
    const listing = db.getListingById(review.listingId);
    if (!context || !context.user || (context.user.id !== listing.hostId && !context.user.isAdmin)) {
      throw new Error("Unauthorized: Only the listing host or admin can moderate reviews.");
    }
    return db.moderateReview(id, action, reason);
  },

  approveBooking: ({ id, approve }, context) => {
    const booking = db.getBookingById(id);
    if (!booking) {
      throw new Error("Booking not found");
    }
    if (!context || !context.user || (context.user.id !== booking.hostId && !context.user.isAdmin)) {
      throw new Error("Unauthorized: Only the host can approve or reject this booking.");
    }
    const newApprovalStatus = approve ? "approved" : "rejected";
    const updated = db.updateBookingApproval(id, newApprovalStatus);

    if (updated) {
      createNotification({
        userId: updated.guestId,
        title: approve ? "Rezervasyonunuz Onaylandı! 🎉" : "Rezervasyon Talebiniz Reddedildi",
        message: approve 
          ? "Ev sahibi #" + updated.id + " numaralı rezervasyonunuzu onayladı. İyi konaklamalar!" 
          : "Ev sahibi #" + updated.id + " numaralı rezervasyon talebinizi onaylayamadı.",
        type: "booking"
      });
      updated.listing = () => hydrateListing(db.getListingById(updated.listingId), context);
      updated.guest = () => context.userLoader.load(updated.guestId);
    }
    return updated;
  },

  convertCurrency: ({ amount, from, to }) => convertCurrency(amount, from, to),
  hostRevenueAnalytics: ({ hostId }, context) => {
    if (!context || !context.user || (context.user.id !== hostId && !context.user.isAdmin)) {
      throw new Error("Unauthorized: You can only access your own host revenue analytics.");
    }
    return db.getHostRevenueAnalytics(hostId);
  }
};
