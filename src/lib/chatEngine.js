import { WebSocketServer, WebSocket } from "ws";
import * as db from "./db.js";
import { generateAiResponse } from "./aiConcierge.js";

/**
 * Real-time WebSocket Chat Engine for Airbnb Fatsa Clone
 * Handles listing-based chat rooms, real-time message broadcasting,
 * SQLite persistence, and heartbeat ping/pong.
 */
class ChatWebSocketEngine {
  constructor() {
    this.wss = null;
    this.rooms = new Map(); // listingId -> Set<WebSocket>
  }

  initialize(httpServer) {
    this.wss = new WebSocketServer({ noServer: true });

    // Handle HTTP Upgrade requests on /ws/chat
    httpServer.on("upgrade", (request, socket, head) => {
      const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
      if (url.pathname === "/ws/chat" || url.pathname === "/ws") {
        this.wss.handleUpgrade(request, socket, head, (ws) => {
          this.wss.emit("connection", ws, request);
        });
      }
    });

    this.wss.on("connection", (ws, req) => {
      const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
      const listingId = url.searchParams.get("listingId") || "general";
      const userId = url.searchParams.get("userId") || "guest";

      ws.isAlive = true;
      ws.listingId = listingId;
      ws.userId = userId;

      // Join room
      if (!this.rooms.has(listingId)) {
        this.rooms.set(listingId, new Set());
      }
      this.rooms.get(listingId).add(ws);

      // Send connection ack
      ws.send(JSON.stringify({
        type: "CONNECTED",
        listingId,
        userId,
        timestamp: Date.now()
      }));

      ws.on("pong", () => {
        ws.isAlive = true;
      });

      ws.on("message", (data) => {
        try {
          const payload = JSON.parse(data.toString());
          this.handleIncomingMessage(ws, payload);
        } catch (err) {
          ws.send(JSON.stringify({ type: "ERROR", error: "Invalid JSON message format" }));
        }
      });

      ws.on("close", () => {
        if (this.rooms.has(ws.listingId)) {
          this.rooms.get(ws.listingId).delete(ws);
          if (this.rooms.get(ws.listingId).size === 0) {
            this.rooms.delete(ws.listingId);
          }
        }
      });

      ws.on("error", (err) => {
        console.error("[WebSocket Chat Error]:", err.message);
      });
    });

    // Heartbeat cleanup interval (every 30 seconds)
    const interval = setInterval(() => {

      if (!this.wss) return;
      for (const ws of this.wss.clients) {
        if (ws.isAlive === false) {
          ws.terminate();
          continue;
        }
        ws.isAlive = false;
        ws.ping();
      }
    }, 30000);

    interval.unref();
    this.wss.on("close", () => {
      clearInterval(interval);
    });

    return this.wss;
  }

  handleIncomingMessage(ws, payload) {
    const { type, text, listingId, senderId } = payload;
    const targetListingId = listingId || ws.listingId;
    const targetSenderId = senderId || ws.userId;

    if (type === "SEND_MESSAGE") {
      if (!text || !text.trim()) {
        ws.send(JSON.stringify({ type: "ERROR", error: "Message text cannot be empty" }));
        return;
      }

      // Fetch sender name from DB
      const user = db.getUserById(targetSenderId) || { name: "Misafir Kullanıcı" };
      const savedMsg = db.insertMessage({
        listingId: targetListingId,
        senderId: targetSenderId,
        senderName: user.name,
        text: text.trim()
      });

      // Broadcast to all clients in the room
      this.broadcast(targetListingId, {
        type: "NEW_MESSAGE",
        data: savedMsg
      });
    } else if (type === "TYPING") {
      // Broadcast typing indicator to others in room
      this.broadcast(targetListingId, {
        type: "USER_TYPING",
        senderId: targetSenderId,
        isTyping: Boolean(payload.isTyping)
      }, ws);
    }
  }

  broadcast(listingId, message, excludeWs = null) {
    const clients = this.rooms.get(listingId);
    if (!clients) return;
    const payload = JSON.stringify(message);

    for (const client of clients) {
      if (client !== excludeWs && client.readyState === WebSocket.OPEN) {
        client.send(payload);
      }
    }
  }

  close() {
    if (this.wss) {
      this.wss.close();
      this.rooms.clear();
    }
  }
}

export const chatEngine = new ChatWebSocketEngine();
export function setupChatWebSocketServer(httpServer) {
  return chatEngine.initialize(httpServer);
}

export async function requestAiResponse(message, user) {
  const safeMessage = typeof message === "string" ? message.trim().substring(0, 500) : "";
  if (!safeMessage) {
    throw new Error("Geçersiz veya boş mesaj.");
  }

  const userId = user?.id || "guest";
  const userName = user?.name || "Misafir Kullanıcı";
  const listingId = "magda_concierge_" + userId;

  // Ensure the dummy listing exists to satisfy foreign key constraints
  try {
    const existing = db.getListingById(listingId);
    if (!existing) {
            try {
        if (!db.getUserById("magda")) {
          db.db.prepare("INSERT INTO users (id, name, email, passwordHash, isHost, role, status, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)").run("magda", "Magda AI", "magda@fatsaescapes.com", "virtual", 1, "magda", "active", Date.now());
        }
      } catch (e) {
        console.error("Failed to ensure magda user:", e);
      }
      try {
        const existing = db.getListingById(listingId);
        if (!existing) {
          db.db.prepare("INSERT INTO listings (id, hostId, title, description, pricePerNight, city, propertyType, category, address, amenities, images, maxGuests, bedrooms, beds, baths, lat, lng, isPublished, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)").run(listingId, "magda", "Magda AI Concierge", "AI Concierge Session", 0, "Virtual", "Virtual", "AI", "Virtual Address", "[]", "[]", 1, 0, 0, 0, 0, 0, 1, Date.now());
        }
      } catch (e) {
        console.error("Failed to ensure AI virtual listing:", e);
      }
    }
  } catch (e) {
    console.error("Warning: Failed to ensure dummy listing for AI chat", e);
  }

  // Insert user message
  const userMsg = db.insertMessage({
    listingId,
    senderId: userId,
    senderName: userName,
    text: safeMessage
  });

  // Call AI Concierge
  const aiResponseData = await generateAiResponse(safeMessage);

  // Insert AI message
  // Store both text and recommendations by serializing to JSON
  // Only serialize if recommendations exist, otherwise just text
  const serializedAiData = JSON.stringify({
    text: aiResponseData.response,
    recommendations: aiResponseData.recommendations || []
  });

  const aiMsg = db.insertMessage({
    listingId,
    senderId: "magda",
    senderName: "Magda AI",
    text: serializedAiData
  });

  return aiMsg;
}

export function getMagdaChatHistoryForUser(userId) {
  const listingId = "magda_concierge_" + (userId || "guest");
  return db.getMessagesForListing(listingId);
}
