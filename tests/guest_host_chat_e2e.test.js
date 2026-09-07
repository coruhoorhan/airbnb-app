import { describe, it, expect, beforeAll, afterAll } from "vitest";
import request from "supertest";
import http from "http";
import WebSocket from "ws";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";
import { generateToken } from "../src/lib/auth.js";
import { setupChatWebSocketServer, chatEngine } from "../src/lib/chatEngine.js";

describe("Misafir & Ev Sahibi Uçtan Uca (E2E) Mesajlaşma Senaryosu", () => {
  let server;
  let wsPort;
  let guestToken;
  let hostToken;
  let guestUser;
  let hostUser;
  let testListingId;

  beforeAll(async () => {
    const timestamp = Date.now();
    testListingId = `list_e2e_chat_${timestamp}`;

    guestUser = {
      id: `usr_guest_e2e_${timestamp}`,
      name: "Ahmet Yılmaz",
      email: `ahmet_${timestamp}@fatsa.bel.tr`,
      isHost: false
    };
    db.insertUser(guestUser);
    guestToken = generateToken(guestUser);

    hostUser = {
      id: `usr_host_e2e_${timestamp}`,
      name: "Zeynep Kaya",
      email: `zeynep_${timestamp}@fatsa.bel.tr`,
      isHost: true
    };
    db.insertUser(hostUser);
    hostToken = generateToken(hostUser);

    db.insertListing({
      id: testListingId,
      hostId: hostUser.id,
      title: "Yalıkavak Sonsuzluk Havuzlu Villa",
      description: "Eşsiz manzaralı lüks villa",
      pricePerNight: 5000,
      cleaningFee: 500,
      serviceFee: 250,
      city: "Fatsa",
      category: "villa",
      propertyType: "entire_home",
      maxGuests: 6,
      bedrooms: 3,
      beds: 4,
      baths: 3,
      lat: 41.0,
      lng: 37.5,
      address: "Sahil Cad. 10",
      country: "Türkiye",
      state: "Ordu",
      createdAt: Date.now()
    });

    // Start ephemeral HTTP + WebSocket server for real WS tests
    server = http.createServer(app);
    setupChatWebSocketServer(server);

    await new Promise((resolve) => {
      server.listen(0, "127.0.0.1", () => {
        wsPort = server.address().port;
        resolve();
      });
    });
  });

  afterAll(async () => {
    chatEngine.close();
    await new Promise((resolve) => server.close(resolve));
  });

  it("1. Adım: Misafir (Ahmet Yılmaz) ev sahibine mesaj gönderir ve veritabanına kaydedilir", async () => {
    const res = await request(app)
      .post("/api/messages")
      .set("Authorization", `Bearer ${guestToken}`)
      .send({
        listingId: testListingId,
        senderId: guestUser.id,
        text: "Merhaba Zeynep Hanım, villada evcil hayvan kabul ediliyor mu?"
      });

    expect(res.status).toBe(201);
    expect(res.body.success).toBe(true);
    expect(res.body.data.text).toBe("Merhaba Zeynep Hanım, villada evcil hayvan kabul ediliyor mu?");
    expect(res.body.data.senderName).toBe("Ahmet Yılmaz");
    expect(res.body.data.isRead).toBe(0);

    // Direct SQLite check
    const dbMessages = db.getMessagesForListing(testListingId);
    expect(dbMessages.length).toBe(1);
    expect(dbMessages[0].text).toContain("evcil hayvan");
  });

  it("2. Adım: Ev Sahibi (Zeynep Kaya) gelen kutusunu sorgular, 1 okunmamış mesaj ve Ahmet Yılmaz detayını görür", async () => {
    const res = await request(app)
      .get(`/api/conversations?userId=${hostUser.id}`)
      .set("Authorization", `Bearer ${hostToken}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(Array.isArray(res.body.data)).toBe(true);

    const conv = res.body.data.find((c) => c.listingId === testListingId);
    expect(conv).toBeDefined();
    expect(conv.unreadCount).toBe(1);
    expect(conv.counterpart).toBeDefined();
    expect(conv.counterpart.name).toBe("Ahmet Yılmaz");
    expect(conv.lastMessage.text).toContain("evcil hayvan");
  });

  it("3. Adım: Ev Sahibi mesajı okundu olarak işaretler ve unreadCount sıfırlanır", async () => {
    const readRes = await request(app)
      .post("/api/messages/read")
      .set("Authorization", `Bearer ${hostToken}`)
      .send({
        listingId: testListingId,
        userId: hostUser.id
      });

    expect(readRes.status).toBe(200);
    expect(readRes.body.success).toBe(true);

    // Re-check conversations for host
    const convRes = await request(app)
      .get(`/api/conversations?userId=${hostUser.id}`)
      .set("Authorization", `Bearer ${hostToken}`);

    const conv = convRes.body.data.find((c) => c.listingId === testListingId);
    expect(conv).toBeDefined();
    expect(conv.unreadCount).toBe(0);
  });

  it("4. Adım: Ev Sahibi (Zeynep Kaya) yanıt gönderir ve her iki taraf tam sohbet geçmişini görür", async () => {
    const replyRes = await request(app)
      .post("/api/messages")
      .set("Authorization", `Bearer ${hostToken}`)
      .send({
        listingId: testListingId,
        senderId: hostUser.id,
        text: "Merhaba Ahmet Bey, evet küçük ırk evcil hayvanları memnuniyetle kabul ediyoruz."
      });

    expect(replyRes.status).toBe(201);
    expect(replyRes.body.success).toBe(true);

    // Misafir sohbet penceresini açtığında tüm mesajları sırasıyla görür
    const historyRes = await request(app)
      .get(`/api/messages?listingId=${testListingId}`)
      .set("Authorization", `Bearer ${guestToken}`);

    expect(historyRes.status).toBe(200);
    expect(historyRes.body.success).toBe(true);
    const msgs = historyRes.body.data;
    expect(msgs.length).toBe(2);

    // 1st message: Guest
    expect(msgs[0].senderId).toBe(guestUser.id);
    expect(msgs[0].senderName).toBe("Ahmet Yılmaz");
    expect(msgs[0].text).toContain("evcil hayvan kabul ediliyor mu?");

    // 2nd message: Host
    expect(msgs[1].senderId).toBe(hostUser.id);
    expect(msgs[1].senderName).toBe("Zeynep Kaya");
    expect(msgs[1].text).toContain("memnuniyetle kabul ediyoruz");
  });

  it("5. Adım: Canlı WebSocket odasında Misafir ve Ev Sahibi anlık mesaj iletimini alır", async () => {
    const guestWsUrl = `ws://127.0.0.1:${wsPort}/ws/chat?listingId=${testListingId}&userId=${guestUser.id}`;
    const hostWsUrl = `ws://127.0.0.1:${wsPort}/ws/chat?listingId=${testListingId}&userId=${hostUser.id}`;

    const guestWs = new WebSocket(guestWsUrl);
    const hostWs = new WebSocket(hostWsUrl);

    await Promise.all([
      new Promise((res) => guestWs.on("open", res)),
      new Promise((res) => hostWs.on("open", res))
    ]);

    const hostReceivedPromise = new Promise((resolve) => {
      hostWs.on("message", (raw) => {
        const payload = JSON.parse(raw.toString());
        if (payload.type === "NEW_MESSAGE") {
          resolve(payload.data);
        }
      });
    });

    // Misafir WebSocket üzerinden mesaj gönderir
    guestWs.send(JSON.stringify({
      type: "SEND_MESSAGE",
      listingId: testListingId,
      senderId: guestUser.id,
      text: "Giriş saatini 12:00 olarak ayarlayabilir miyiz?"
    }));

    const receivedByHost = await hostReceivedPromise;
    expect(receivedByHost.text).toBe("Giriş saatini 12:00 olarak ayarlayabilir miyiz?");
    expect(receivedByHost.senderName).toBe("Ahmet Yılmaz");

    guestWs.close();
    hostWs.close();
  });
});
