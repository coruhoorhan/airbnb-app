import { describe, it, expect } from 'vitest';
import { getAllListings, getHostRevenueAnalytics, getUsersByIds } from '../src/lib/db.js';

describe('Database Parameterized Queries and SQL Injection Prevention', () => {
  it('safely escapes injection attempts in getAllListings', () => {
    // Attempt SQL injection via city filter
    const payload = "' OR 1=1 --";
    const listings = getAllListings({ city: payload });
    // Since it's properly parameterized as `%${payload}%`, it won't match all rows.
    // It should either return empty or only rows where city literally contains "' OR 1=1 --".
    // We expect it to not leak all database listings.
    expect(listings.length).toBe(0);
  });

  it('safely escapes injection attempts in search filter', () => {
    const payload = "' OR '1'='1";
    const listings = getAllListings({ search: payload });
    expect(listings.length).toBe(0);
  });

  it('safely handles injection payloads in getHostRevenueAnalytics', () => {
    const payload = "' OR 1=1 --";
    const analytics = getHostRevenueAnalytics(payload);
    // Since hostId is parameterized, no listings should match this fake hostId.
    expect(analytics.hostId).toBe(payload);
    expect(analytics.listingBreakdown.length).toBe(0);
    expect(analytics.totalEarnings).toBe(0);
  });

  it('safely handles injection payloads in getUsersByIds', () => {
    const payloads = ["' OR 1=1 --", "1; DROP TABLE users;"];
    const users = getUsersByIds(payloads);
    expect(users.length).toBe(0);
  });
});
