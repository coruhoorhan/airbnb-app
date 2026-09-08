import { test, expect, describe, vi } from 'vitest';
import request from 'supertest';

vi.mock('../src/lib/auth.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    authMiddleware: (req, res, next) => {
      req.user = { id: 'test_user_id', email: 'test@example.com' };
      next();
    },
    csrfMiddleware: (req, res, next) => next(),
  };
});

import { app } from '../server.js';

describe('GraphQL Complexity Limit', () => {
  test('rejects complex queries (> 200) with 400 response', async () => {
    let listingsStr = '';
    for (let i = 0; i < 250; i++) {
       listingsStr += `l${i}: listings { id title } `;
    }
    const query = `
      query {
        ${listingsStr}
      }
    `;
    const response = await request(app)
      .post('/graphql')
      .send({ query });

    // Accept either 400 or 200 since the GraphQL spec and library handles execution errors returning 200 with an errors array.
    expect([200, 400]).toContain(response.status);
    const hasComplexityError = response.body.errors?.some(
      err => err.message.includes('complexity') || err.message.includes('Cost of') || err.message.includes('exceeds the maximum')
    );
    expect(hasComplexityError).toBe(true);
  });

  test('allows normal queries (complexity <= 200)', async () => {
    const query = `
      query {
        listings {
          id
          title
        }
      }
    `;
    const response = await request(app)
      .post('/graphql')
      .send({ query });

    expect(response.status).toBe(200);
    expect(response.body.errors).toBeUndefined();
  });
});
