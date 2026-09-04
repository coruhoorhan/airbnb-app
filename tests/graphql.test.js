import { describe, it, expect, beforeAll } from 'vitest';
import * as db from '../src/lib/db.js';
import { generateToken } from '../src/lib/auth.js';

describe('GraphQL API', () => {
  let testUserToken;
  let testListing;
  let userId;
  let listingId;

  beforeAll(() => {
    userId = `test_graphql_user_${Date.now()}`;
    listingId = `test_graphql_listing_${Date.now()}`;
    const mockUser = { id: userId, name: 'GraphQL User', email: `gql_${Date.now()}@test.com`, isHost: false };
    db.insertUser(mockUser);
    testUserToken = generateToken(mockUser);

    testListing = db.insertListing({
      id: listingId,
      hostId: userId,
      title: 'GraphQL Listing',
      description: 'A nice place to test GraphQL',
      pricePerNight: 100,
      city: 'Fatsa',
      category: 'house',
      propertyType: 'entire_home',
      maxGuests: 2,
      bedrooms: 1,
      beds: 1,
      baths: 1,
      cleaningFee: 0,
      serviceFee: 0,
      latitude: 0,
      longitude: 0,
      lat: 0,
      lng: 0,
      avgRating: 0,
      reviewCount: 0,
      cancellationPolicy: 'flexible',
      address: 'Test Addr',
      country: 'Turkey',
      state: 'Ordu',
      createdAt: Date.now()
    });
  });

  it('rejects unauthenticated access', async () => {
    const query = `
      query {
        listings {
          id
          title
        }
      }
    `;
    const res = await fetch('http://localhost:4000/graphql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });

    expect(res.status).toBe(401);
  });

  it('fetches listings when authenticated', async () => {
    const query = `
      query {
        listings {
          id
          title
          host {
            name
          }
        }
      }
    `;
    const res = await fetch('http://localhost:4000/graphql', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${testUserToken}`
      },
      body: JSON.stringify({ query })
    });

    expect(res.status).toBe(200);
    const result = await res.json();
    expect(result.data).toBeDefined();
    expect(result.data.listings).toBeDefined();
    expect(result.data.listings.length).toBeGreaterThan(0);

    // Check one of the seeded listings
    const ourListing = result.data.listings.find(l => l.id === 'list_01');
    expect(ourListing).toBeDefined();
    expect(ourListing.title).toContain('Villa');
    expect(ourListing.host.name).toContain('Zeynep');
  });

  it('does not return sensitive fields for users', async () => {
    const query = `
      query {
        user(id: "${userId}") {
          name
        }
      }
    `;
    const res = await fetch('http://localhost:4000/graphql', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${testUserToken}`
      },
      body: JSON.stringify({ query })
    });

    expect(res.status).toBe(200);
    const result = await res.json();

    expect(result.data.user).toBeDefined();
    expect(result.data.user.name).toBe('GraphQL User');

    const badQuery = `
      query {
        user(id: "${userId}") {
          name
          email
        }
      }
    `;
    const badRes = await fetch('http://localhost:4000/graphql', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${testUserToken}`
      },
      body: JSON.stringify({ query: badQuery })
    });

    const badResult = await badRes.json();

    expect(badResult.errors).toBeDefined();

  });
});
