import * as db from "./db.js";
import { randomUUID } from "node:crypto";

function formatDateToIcs(dateStr) {
  // Accepts 'YYYY-MM-DD' or ISO string and formats to 'YYYYMMDD'
  if (!dateStr) return "";
  const cleaned = dateStr.replace(/[^0-9]/g, "");
  return cleaned.slice(0, 8);
}

function parseIcsEvents(icsContent) {
  const events = [];
  const eventBlocks = icsContent.split("BEGIN:VEVENT");
  for (let i = 1; i < eventBlocks.length; i++) {
    const block = eventBlocks[i].split("END:VEVENT")[0];
    const dtStartMatch = block.match(/DTSTART(?:;[^:]+)?:(\d{8})/);
    const dtEndMatch = block.match(/DTEND(?:;[^:]+)?:(\d{8})/);
    const summaryMatch = block.match(/SUMMARY:(.+)/);
    const uidMatch = block.match(/UID:(.+)/);

    if (dtStartMatch && dtEndMatch) {
      const s = dtStartMatch[1];
      const e = dtEndMatch[1];
      const checkIn = `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
      const checkOut = `${e.slice(0, 4)}-${e.slice(4, 6)}-${e.slice(6, 8)}`;
      events.push({
        uid: uidMatch ? uidMatch[1].trim() : randomUUID(),
        summary: summaryMatch ? summaryMatch[1].trim() : "External Reservation",
        checkIn,
        checkOut
      });
    }
  }
  return events;
}

export function generateIcsFeed(listingId) {
  const listing = db.getListingById(listingId);
  if (!listing) return null;

  const bookings = db.db.prepare(
    "SELECT * FROM bookings WHERE listingId = ? AND status IN ('confirmed', 'completed', 'pending') AND (approvalStatus IS NULL OR approvalStatus != 'rejected')"
  ).all(listingId);

  const nowIcs = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z";
  let ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Airbnb Fatsa//Calendar Sync 1.0//TR",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    `X-WR-CALNAME:Airbnb Fatsa - ${listing.title.replace(/\r|\n/g, " ")}`
  ];

  for (const b of bookings) {
    const start = formatDateToIcs(b.checkIn);
    const end = formatDateToIcs(b.checkOut);
    if (!start || !end) continue;

    ics.push(
      "BEGIN:VEVENT",
      `UID:booking-${b.id}@airbnb-fatsa.com`,
      `DTSTAMP:${nowIcs}`,
      `DTSTART;VALUE=DATE:${start}`,
      `DTEND;VALUE=DATE:${end}`,
      `SUMMARY:Airbnb Reserved (${b.numGuests || 1} Guests)`,
      `DESCRIPTION:Booking #${b.id} - ${b.status}`,
      "STATUS:CONFIRMED",
      "END:VEVENT"
    );
  }

  ics.push("END:VCALENDAR");
  return ics.join("\r\n") + "\r\n";
}

export async function syncExternalIcal(listingId, icalUrlOrData) {
  const listing = db.getListingById(listingId);
  if (!listing) throw new Error("İlan bulunamadı.");

  let icsData = icalUrlOrData;
  if (icalUrlOrData.startsWith("http://") || icalUrlOrData.startsWith("https://")) {
    try {
      const res = await fetch(icalUrlOrData);
      if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
      icsData = await res.text();
    } catch (err) {
      db.db.prepare("UPDATE listings SET calendarSyncStatus = 'error' WHERE id = ?").run(listingId);
      throw new Error(`iCal akışı indirilemedi: ${err.message}`);
    }
  }

  const icalUser = db.getUserById("user_ical_sync");
  if (!icalUser) {
    try {
      db.insertUser({
        id: "user_ical_sync",
        name: "iCal Harici Senkronizasyon",
        email: "ical-sync@airbnb-fatsa.system",
        isHost: false
      });
    } catch (e) {}
  }
  const events = parseIcsEvents(icsData);
  let syncedCount = 0;

  for (const ev of events) {
    const syncBookingId = `ical_sync_${listingId}_${ev.checkIn}_${ev.checkOut}`;
    const existing = db.getBookingById(syncBookingId);
    if (!existing) {
      db.insertBooking({
        id: syncBookingId,
        listingId,
        guestId: "user_ical_sync",
        hostId: listing.hostId,
        checkIn: ev.checkIn,
        checkOut: ev.checkOut,
        numGuests: 1,
        nightlyPrice: 0,
        cleaningFee: 0,
        serviceFee: 0,
        totalPrice: 0,
        paymentStatus: "paid",
        status: "confirmed",
        approvalStatus: "approved",
        cancelReason: "iCal Harici Takvim Senkronizasyonu",
        createdAt: Date.now()
      });
      syncedCount++;
    }
  }

  db.db.prepare(
    "UPDATE listings SET calendarSyncStatus = 'synced', lastSyncedAt = ? WHERE id = ?"
  ).run(Date.now(), listingId);

  return { success: true, syncedCount, totalEvents: events.length };
}
