/**
 * Fiyat Takibi Motoru (Price Watch Engine)
 * Kullanıcı ilanı takibe alır, fiyat düşünce bildirim üretilir.
 */
import { db } from "./db.js";

/**
 * İlanı fiyat takibine ekler.
 * Aynı (userId, listingId) çifti tekrar eklenmez.
 */
export function addPriceWatch(userId, listingId) {
  const existing = db.prepare(
    "SELECT * FROM price_watches WHERE userId = ? AND listingId = ?"
  ).get(userId, listingId);
  if (existing) return { ...existing, isWatching: true };

  const id = `pwatch_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
  const listing = db.prepare("SELECT pricePerNight FROM listings WHERE id = ?").get(listingId);
  db.prepare(`
    INSERT INTO price_watches (id, userId, listingId, watchedPrice, createdAt)
    VALUES (?, ?, ?, ?, ?)
  `).run(id, userId, listingId, listing?.pricePerNight || 0, Date.now());

  return { id, userId, listingId, isWatching: true };
}

/**
 * Takibi kaldırır.
 */
export function removePriceWatch(userId, listingId) {
  const res = db.prepare("DELETE FROM price_watches WHERE userId = ? AND listingId = ?").run(userId, listingId);
  return { removed: res.changes > 0 };
}

/**
 * Kullanıcının takip listesi (ilan bilgileriyle birlikte).
 */
export function getUserPriceWatches(userId) {
  const rows = db.prepare("SELECT * FROM price_watches WHERE userId = ? ORDER BY createdAt DESC").all(userId);
  return rows.map((w) => {
    const listing = db.prepare("SELECT id, title, city, pricePerNight, images FROM listings WHERE id = ?").get(w.listingId);
    if (!listing) return null;
    return {
      ...w,
      title: listing.title,
      city: listing.city,
      currentPrice: listing.pricePerNight,
      priceChanged: listing.pricePerNight < w.watchedPrice,
      priceDropAmount: Math.max(0, w.watchedPrice - listing.pricePerNight),
      image: JSON.parse(listing.images || "[]")[0] || null
    };
  }).filter(Boolean);
}

/**
 * Fiyat değişimini kontrol eder; düşüş varsa bildirim üretir (listing güncellendiğinde çağrılır).
 */
export function checkPriceDropsForListing(listingId, oldPrice, newPrice) {
  if (newPrice >= oldPrice) return { dropped: false };

  const watchers = db.prepare("SELECT * FROM price_watches WHERE listingId = ?").all(listingId);
  const listing = db.prepare("SELECT title FROM listings WHERE id = ?").get(listingId);
  let notificationsCreated = 0;

  for (const w of watchers) {
    if (newPrice < w.watchedPrice) {
      db.prepare(`
        INSERT INTO notifications (id, userId, type, title, body, isRead, createdAt)
        VALUES (?, ?, 'price_drop', 'Fiyat Düştü! 🔔', ?, 0, ?)
      `).run(
        `notif_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
        w.userId,
        `"${listing?.title || "Takip ettiğiniz ilan"}" için gece fiyatı ₺${newPrice}'a düştü.`,
        Date.now()
      );
      db.prepare("UPDATE price_watches SET watchedPrice = ? WHERE id = ?").run(newPrice, w.id);
      notificationsCreated++;
    }
  }
  return { dropped: true, notificationsCreated };
}
