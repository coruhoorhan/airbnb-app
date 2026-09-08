import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";
import { generateToken } from "../src/lib/auth.js";

describe("GraphQL Depth Limit", () => {
  let testUserToken;

  beforeAll(() => {
    const userId = "test_graphql_depth_user_" + Date.now();
    const email = "depth_" + Date.now() + "@test.com";
    const mockUser = { id: userId, name: "Depth User", email: email, isHost: false };
    db.insertUser(mockUser);
    testUserToken = generateToken(mockUser);
  });

  it("allows queries within depth limit (depth 1 to 4)", async () => {
    const query = `
      query {
        bookings {
          id
          totalPrice
          listing {
            id
            title
            pricePerNight
            host {
              id
              name
            }
            reviews {
              id
              rating
              comment
            }
          }
          guest {
            id
            name
          }
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", "Bearer " + testUserToken)
      .send({ query });

    expect(res.status).toBe(200);
    const result = res.body;
    expect(result.errors).toBeUndefined();
    expect(result.data).toBeDefined();
    expect(Array.isArray(result.data.bookings)).toBe(true);
  });

  it("allows queries using fragments within depth limit", async () => {
    const query = `
      query {
        listings {
          ...ListingFields
        }
      }
      fragment ListingFields on Listing {
        id
        title
        pricePerNight
        host {
          id
          name
        }
        reviews {
          id
          rating
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", "Bearer " + testUserToken)
      .send({ query });

    expect(res.status).toBe(200);
    const result = res.body;
    expect(result.errors).toBeUndefined();
    expect(result.data).toBeDefined();
    expect(Array.isArray(result.data.listings)).toBe(true);
  });

  it("rejects queries exceeding depth limit 8 (depth 9)", async () => {
    const query = `
      query {
        listings { #1
          host { #2
            listings { #3
              host { #4
                listings { #5
                  host { #6
                    listings { #7
                      host { #8
                        listings { #9
                          id
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", "Bearer " + testUserToken)
      .send({ query });

    expect(res.status).toBe(200);
    const result = res.body;
    expect(result.errors).toBeDefined();
    expect(result.errors.some(err => err.message.includes("exceeds maximum operation depth of 8"))).toBe(true);
  });

  it("rejects queries using fragments exceeding depth limit 8", async () => {
    const query = `
      query {
        listings {
          ...DeepFragment
        }
      }
      fragment DeepFragment on Listing {
        host {
          listings {
            host {
              listings {
                host {
                  listings {
                    host {
                      listings {
                        id
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    `;
    const res = await request(app)
      .post("/graphql")
      .set("Content-Type", "application/json")
      .set("Authorization", "Bearer " + testUserToken)
      .send({ query });

    expect(res.status).toBe(200);
    const result = res.body;
    expect(result.errors).toBeDefined();
    expect(result.errors.some(err => err.message.includes("exceeds maximum operation depth of 8"))).toBe(true);
  });
});
