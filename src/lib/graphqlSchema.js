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
    status: String
    moderationReason: String
  }

  
  type CalendarSyncInfo {
    status: String
    externalUrl: String
    lastSyncedAt: Float
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
    calendarSync: CalendarSyncInfo
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
    currency: String
    approvalStatus: String
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
    status: String
    moderationReason: String
  }

  type MonthlyEarnings {
    month: String!
    earnings: Float!
    bookingsCount: Int!
  }

  type ListingRevenueBreakdown {
    listingId: String!
    title: String!
    totalEarnings: Float!
    bookingsCount: Int!
  }

  type PendingPayout {
    bookingId: String!
    amount: Float!
    payoutDate: String
    guestName: String
  }

  type RevenueAnalytics {
    hostId: ID!
    totalEarnings: Float!
    pendingPayoutsTotal: Float!
    averageOccupancyRate: Float!
    earningsByMonth: [MonthlyEarnings]
    listingBreakdown: [ListingRevenueBreakdown]
    pendingPayouts: [PendingPayout]
  }

  
  type Mutation {
    approveBooking(id: ID!, approve: Boolean!): Booking
    setCalendarSyncUrl(listingId: ID!, url: String!): Listing
    removeCalendarSync(listingId: ID!): Listing
    flagReview(id: ID!, reason: String!): Review
    moderateReview(id: ID!, action: String!, reason: String): Review
  }

  type Query {
    user(id: ID!): User
    users: [User]
    listing(id: ID!): Listing
    listings(city: String, category: String): [Listing]
    booking(id: ID!): Booking
    bookings(guestId: String, hostId: String): [Booking]
    reviews(listingId: ID!): [Review]
    recommendedListings(userId: ID, limit: Int): [Listing!]!
    hostRevenueAnalytics(hostId: ID!): RevenueAnalytics!
    convertCurrency(amount: Float!, from: String!, to: String!): Float!
  }
`);
