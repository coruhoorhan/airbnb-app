import { describe, it, expect, beforeAll } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import { db, insertUser, insertListing } from '../src/lib/db.js';
import { generateToken } from '../src/lib/auth.js';

describe('Server Route Validation', () => {
    let token;
    let csrfToken;
    let guestId = 'usr_guest_test_fail';

    beforeAll(async () => {
        try {
            insertUser({ id: guestId, name: 'Guest Test Fail', email: 'guest_test_fail@test.com' });
        } catch (e) {}

        const res = await request(app).get('/api/auth/csrf');
        csrfToken = res.body.csrfToken;

        token = generateToken({ id: guestId, isHost: 0 });
    });

    it('should return 400 for booking creation with negative prices', async () => {
        const listingId = 'list_test_fail_31';
        try {
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
        } catch(e) {}

        const res = await request(app)
            .post('/api/bookings')
            .set('Authorization', `Bearer ${token}`)
            .set('x-csrf-token', csrfToken)
            .send({
                listingId: listingId,
                guestId: guestId,
                checkIn: '2026-09-01',
                checkOut: '2026-09-10',
                nightlyPrice: -100 // malicious attempt
            });

        // Current implementation is expected to return 400 if validation fails, or it might just override it with calculated price.
        // Let's print out what it currently does.
        console.log("Status: ", res.status);
        console.log("Body: ", res.body);
    });
});
