import * as db from "./db.js";

function hydrateListing(listing, context) {
  if (!listing) return listing;
  if (typeof listing.amenities === 'string') listing.amenities = JSON.parse(listing.amenities);
  if (typeof listing.images === 'string') listing.images = JSON.parse(listing.images);
  listing.host = () => context.userLoader.load(listing.hostId);
  listing.reviews = () => context.reviewsLoader.load(listing.id);
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
  reviews: ({ listingId }, context) => {
    return context.reviewsLoader.load(listingId);
  }
};
