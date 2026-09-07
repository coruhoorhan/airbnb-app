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

  it("rejects queries exceeding depth limit 8", async () => {
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

    expect(res.status).toBe(200); // Or 400 depending on library error response format
    const result = res.body;
    expect(result.errors).toBeDefined();
    expect(result.errors[0].message).toContain("exceeds maximum operation depth");
  });
});
