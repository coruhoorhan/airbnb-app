import { buildSchema } from "graphql";
import * as db from "./db.js";

export const schema = buildSchema(\`
  type User {
    id: ID!
    name: String!
    email: String!
    avatarUrl: String
    isHost: Boolean
    bio: String
    phone: String
    createdAt: Float
  }

  type Listing {
    id: ID!
    hostId: String!
    host: User
    title: String!
    description: String!
    pricePerNight: Float!
    city: String!
    district: String
    category: String!
    maxGuests: Int!
    bedrooms: Int!
    beds: Int!
    baths: Int!
    amenities: [String]
    images: [String]
    avgRating: Float
    reviewCount: Int
    latitude: Float
    longitude: Float
    isPublished: Boolean
    instantBook: Boolean
    reviews: [Review]
  }

  type Booking {
    id: ID!
    listingId: String!
    listing: Listing
    guestId: String!
    guest: User
    checkIn: String!
    checkOut: String!
    guests: Int!
    totalPrice: Float!
    status: String!
    paymentStatus: String!
    nightlyPrice: Float
    cleaningFee: Float
    serviceFee: Float
    discountAmount: Float
  }

  type Review {
    id: ID!
    listingId: String!
    bookingId: String
    reviewerId: String!
    reviewerName: String!
    rating: Float!
    comment: String
    createdAt: Float
  }

  type Query {
    user(id: ID!): User
    users: [User]
    listing(id: ID!): Listing
    listings(city: String, category: String): [Listing]
    booking(id: ID!): Booking
    bookings(guestId: String, hostId: String): [Booking]
    reviews(listingId: ID!): [Review]
  }
\`);

function hydrateListing(listing) {
  if (!listing) return listing;
  if (typeof listing.amenities === 'string') listing.amenities = JSON.parse(listing.amenities);
  if (typeof listing.images === 'string') listing.images = JSON.parse(listing.images);
  listing.host = () => db.getUserById(listing.hostId);
  listing.reviews = () => db.getReviewsForListing(listing.id);
  return listing;
}

export const rootValue = {
  user: ({ id }) => {
    return db.getUserById(id);
  },
  users: () => {
    return db.getAllUsers();
  },
  listing: ({ id }) => {
    const listing = db.getListingById(id);
    return hydrateListing(listing);
  },
  listings: ({ city, category }) => {
    const filters = {};
    if (city) filters.city = city;
    if (category) filters.category = category;
    return db.getAllListings(filters).map(hydrateListing);
  },
  booking: ({ id }) => {
    const b = db.getBookingById(id);
    if (b) {
      b.listing = () => hydrateListing(db.getListingById(b.listingId));
      b.guest = () => db.getUserById(b.guestId);
    }
    return b;
  },
  bookings: ({ guestId, hostId }) => {
    return db.getAllBookings(guestId, hostId).map(b => {
      b.listing = () => hydrateListing(db.getListingById(b.listingId));
      b.guest = () => db.getUserById(b.guestId);
      return b;
    });
  },
  reviews: ({ listingId }) => {
    return db.getReviewsForListing(listingId);
  }
};