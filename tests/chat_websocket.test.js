import { describe, it, expect, beforeAll, afterAll } from "vitest";
import http from "http";
import { WebSocket } from "ws";
import { app } from "../server.js";
import { setupChatWebSocketServer, chatEngine } from "../src/lib/chatEngine.js";
import * as db from "../src/lib/db.js";

describe("Real-time Chat Messaging via WebSocket", () => {
  let server;
  let port;
  let wsUrl;

  beforeAll(async () => {
    server = http.createServer(app);
    setupChatWebSocketServer(server);

    await new Promise((resolve) => {
      server.listen(0, "127.0.0.1", () => {
        port = server.address().port;
        wsUrl = `ws://127.0.0.1:${port}/ws/chat`;
        resolve();
      });
    });
  });

  afterAll(async () => {
    chatEngine.close();
    await new Promise((resolve) => server.close(resolve));
  });

  it("should connect to WebSocket room and receive connection ack", async () => {
    const ws = new WebSocket(`${wsUrl}?listingId=list_01&userId=usr_guest_01`);

    const msg = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Timeout")), 3000);
      ws.on("message", (data) => {
        clearTimeout(timer);
        resolve(JSON.parse(data.toString()));
      });
      ws.on("error", reject);
    });

    expect(msg.type).toBe("CONNECTED");
    expect(msg.listingId).toBe("list_01");
    expect(msg.userId).toBe("usr_guest_01");

    ws.close();
    await new Promise((r) => setTimeout(r, 50));
  });

  it("should broadcast sent message in real-time to other room participants and persist in SQLite", async () => {
    const testListingId = "list_01";
    const client1 = new WebSocket(`${wsUrl}?listingId=${testListingId}&userId=usr_guest_01`);
    const client2 = new WebSocket(`${wsUrl}?listingId=${testListingId}&userId=usr_host_01`);

    await Promise.all([
      new Promise((res) => client1.on("open", res)),
      new Promise((res) => client2.on("open", res)),
    ]);

    const client2ReceivedPromise = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Broadcast receive timeout")), 3000);
      client2.on("message", (data) => {
        const parsed = JSON.parse(data.toString());
        if (parsed.type === "NEW_MESSAGE") {
          clearTimeout(timer);
          resolve(parsed);
        }
      });
    });

    // Small delay to ensure registration
    await new Promise((r) => setTimeout(r, 50));

    // Client 1 sends message
    const sendPayload = JSON.stringify({
      type: "SEND_MESSAGE",
      text: "Fatsa sahilindeki villanız bu hafta sonu müsait mi?",
      listingId: testListingId,
      senderId: "usr_guest_01"
    });
    client1.send(sendPayload);

    const received = await client2ReceivedPromise;
    expect(received.type).toBe("NEW_MESSAGE");
    expect(received.data.text).toBe("Fatsa sahilindeki villanız bu hafta sonu müsait mi?");
    expect(received.data.listingId).toBe(testListingId);

    // Verify SQLite persistence
    const savedMessages = db.getMessagesForListing(testListingId);
    expect(savedMessages.length).toBeGreaterThanOrEqual(1);
    const found = savedMessages.find(m => m.text === "Fatsa sahilindeki villanız bu hafta sonu müsait mi?");
    expect(found).toBeDefined();

    client1.close();
    client2.close();
    await new Promise((r) => setTimeout(r, 50));
  });
});
