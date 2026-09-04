import { buildSchema } from "graphql";
import * as db from "./db.js";

export const schema = buildSchema(`
  type User {
    id: ID!
    name: String!
    avatarUrl: String
    isHost: Boolean
    bio: String
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
`);

