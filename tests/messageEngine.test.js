import { describe, it, expect, beforeEach } from "vitest";
import {
  getAllListings,
  insertMessage,
  getMessagesForListing,
  markMessagesRead,
  getConversationsForUser
} from "../src/lib/db.js";

describe("Message Engine", () => {
  let targetListingId = "list_01";
  const testGuestId = "usr_guest_01";
  const testHostId = "usr_host_01";
  const testGuestName = "Ahmet Yılmaz";

  beforeEach(() => {
    const listings = getAllListings({ publishedOnly: false });
    const hostListing = listings.find(l => l.hostId === testHostId);
    if (hostListing) {
      targetListingId = hostListing.id;
    }
  });

  it("insertMessage stores a message and getMessagesForListing retrieves it", () => {
    const msg = insertMessage({
      listingId: targetListingId,
      senderId: testGuestId,
      senderName: testGuestName,
      text: "Test mesajı"
    });

    expect(msg).toBeDefined();
    expect(msg.id).toBeTruthy();
    expect(msg.createdAt).toBeGreaterThan(0);
    expect(msg.isRead).toBe(0);
    expect(msg.text).toBe("Test mesajı");
    expect(msg.senderName).toBe(testGuestName);

    const messages = getMessagesForListing(targetListingId);
    const found = messages.find((m) => m.id === msg.id);
    expect(found).toBeTruthy();
    expect(found.text).toBe("Test mesajı");
  });

  it("markMessagesRead marks only the other sender's messages as read", () => {
    // Snapshot host's own messages before the call (live DB may contain real host messages)
    const hostReadBefore = new Map(
      getMessagesForListing(targetListingId)
        .filter((m) => m.senderId === testHostId)
        .map((m) => [m.id, m.isRead])
    );

    // Guest sends a message to the listing
    const guestMsg = insertMessage({
      listingId: targetListingId,
      senderId: testGuestId,
      senderName: testGuestName,
      text: "Host'a soru"
    });

    // Host marks messages as read (guest's messages become read)
    const result = markMessagesRead(targetListingId, testHostId);
    expect(result.changed).toBeGreaterThanOrEqual(1);

    // Verify: the guest's inserted message is now read
    const guestAfter = getMessagesForListing(targetListingId).find((m) => m.id === guestMsg.id);
    expect(guestAfter).toBeTruthy();
    expect(guestAfter.isRead).toBe(1);

    // Verify: markMessagesRead left the host's own messages untouched
    const hostMsgs = getMessagesForListing(targetListingId).filter((m) => m.senderId === testHostId);
    for (const m of hostMsgs) {
      expect(m.isRead).toBe(hostReadBefore.get(m.id));
    }
  });


  it("getConversationsForUser returns conversation with correct unread count", () => {
    // Guest sends a new message
    insertMessage({
      listingId: targetListingId,
      senderId: testGuestId,
      senderName: testGuestName,
      text: "Bu bir test mesajıdır"
    });

    // Host sees the conversation with unread messages
    const hostConversations = getConversationsForUser(testHostId);
    const conv = hostConversations.find((c) => c.listingId === targetListingId);
    expect(conv).toBeTruthy();
    expect(conv.unreadCount).toBeGreaterThanOrEqual(1);
    expect(conv.lastMessage).toBeTruthy();
    expect(conv.lastMessage.text).toBe("Bu bir test mesajıdır");
    expect(conv.counterpart).toBeTruthy();
    expect(conv.counterpart.id).toBe(testGuestId);

    // Host reads messages
    markMessagesRead(targetListingId, testHostId);

    // After reading, unreadCount should be 0
    const afterRead = getConversationsForUser(testHostId);
    const convAfter = afterRead.find((c) => c.listingId === targetListingId);
    if (convAfter) {
      expect(convAfter.unreadCount).toBe(0);
    }

    // Guest sees the conversation too (as participant)
    const guestConversations = getConversationsForUser(testGuestId);
    const guestConv = guestConversations.find((c) => c.listingId === targetListingId);
    expect(guestConv).toBeTruthy();
    expect(guestConv.counterpart.id).toBe(testHostId);
  });
});