import { describe, it, expect, beforeAll } from 'vitest';
import { insertListing, insertBooking, insertUser, db } from '../src/lib/db.js';

describe('Input Validation & Sanitization', () => {
  beforeAll(() => {
    // Disable foreign keys temporarily to avoid needing to create fake users/listings, or just insert them.
    // We'll insert test users instead
    try {
        insertUser({ id: 'usr_test_1', name: 'Test', email: 'test1@test.com' });
        insertUser({ id: 'usr_test_2', name: 'Test 2', email: 'test2@test.com' });
    } catch (e) {}
  });

  it('should sanitize HTML from listing title and description', () => {
    const maliciousTitle = '<script>alert("xss")</script>Beautiful Villa';
    const maliciousDesc = 'A very nice place <img src="x" onerror="alert(1)"> for vacation.';

    const listing = insertListing({
      id: `list_test_${Date.now()}`,
      hostId: 'usr_test_1',
      title: maliciousTitle,
      description: maliciousDesc,
      category: 'Villa',
      propertyType: 'House',
      pricePerNight: 1500,
      cleaningFee: 200,
      serviceFee: 150,
      maxGuests: 4,
      bedrooms: 2,
      beds: 2,
      baths: 1,
      address: 'Test Addr',
      city: 'Test City',
      country: 'Test Country',
      lat: 41,
      lng: 37,
      amenities: [],
      images: [],
      instantBook: 1,
      isPublished: 1
    });

    // The script tags and img tags should be stripped by DOMPurify
    expect(listing.title).toBe('Beautiful Villa');
    expect(listing.description).toBe('A very nice place  for vacation.');
  });

  it('should sanitize HTML from booking dates (if any malicious input is passed)', () => {
    const listingId = `list_test_${Date.now()}_2`;
    insertListing({
      id: listingId,
      hostId: 'usr_test_1',
      title: 'Valid Title',
      description: 'Valid Desc',
      category: 'Villa',
      propertyType: 'House',
      pricePerNight: 1500,
      cleaningFee: 200,
      serviceFee: 150,
      maxGuests: 4,
      bedrooms: 2,
      beds: 2,
      baths: 1,
      address: 'Test Addr',
      city: 'Test City',
      country: 'Test Country',
      lat: 41,
      lng: 37,
      amenities: [],
      images: [],
      instantBook: 1,
      isPublished: 1
    });

    const booking = insertBooking({
      id: `bkg_test_${Date.now()}`,
      listingId: listingId,
      guestId: 'usr_test_2',
      hostId: 'usr_test_1',
      checkIn: '<b onclick="XSS">2026-09-01</b>',
      checkOut: '2026-09-05<script>alert(1)</script>',
      numGuests: 2,
      nightlyPrice: 1500,
      cleaningFee: 200,
      serviceFee: 150,
      totalPrice: 6350,
      createdAt: Date.now(),
      status: 'confirmed'
    });

    expect(booking.checkIn).toBe('2026-09-01');
    expect(booking.checkOut).toBe('2026-09-05');
  });

  it('should throw an error for missing required fields in listing', () => {
    expect(() => {
      insertListing({
        hostId: 'usr_1',
        description: 'Missing title and price'
      });
    }).toThrow(/"title" is required/);
  });

  it('should throw an error for invalid types in booking', () => {
    expect(() => {
      insertBooking({
        listingId: 'list_1',
        guestId: 'usr_2',
        // checkIn is missing
        checkOut: '2026-09-05'
      });
    }).toThrow(/"checkIn" is required/);
  });
});
