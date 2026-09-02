/**
 * Son Dakika Fırsatları Motoru (Last Minute Deals Engine)
 * İlanlar son dakika indirimine alınır, misafirler için öne çıkarılır.
 *
 * Kurallar:
 * - Son dakika fırsatları ilanın gece fiyatına uygulanır (%discountPercent kadar).
 * - Kupon/puan indirimleri son dakika indiriminden sonraki tutara uygulanır.
 * - Fırsat otomatik olarak bitmez (host kapatana kadar aktif).
 */
import { db } from "./db.js";

export const LAST_MINUTE_MIN_DISCOUNT = 10;  // en az %10
export const LAST_MINUTE_MAX_DISCOUNT = 60;  // en fazla %60

/**
 * İlanı son dakika fırsatına alır/çıkarır.
 * @param {string} listingId
 * @param {number|null} discountPercent - null ise kaldırır
 */
export function toggleLastMinuteDeal(listingId, discountPercent = null) {
  const listing = db.prepare("SELECT * FROM listings WHERE id = ?").get(listingId);
  if (!listing) return null;

  if (discountPercent === null || discountPercent <= 0) {
    db.prepare("UPDATE listings SET lastMinuteDiscount = 0, lastMinuteOriginalPrice = NULL WHERE id = ?").run(listingId);
  } else {
    const pct = Math.min(LAST_MINUTE_MAX_DISCOUNT, Math.max(LAST_MINUTE_MIN_DISCOUNT, Math.round(Number(discountPercent) || 0)));
    const originalPrice = listing.lastMinuteOriginalPrice || listing.pricePerNight;
    db.prepare(`
      UPDATE listings
      SET lastMinuteDiscount = ?, lastMinuteOriginalPrice = ?
      WHERE id = ?
    `).run(pct, originalPrice, listingId);
  }
  return getLastMinuteDealById(listingId);
}

/**
 * Son dakika fırsatındaki ilanların listesi (indirimli fiyatla).
 */
export function getLastMinuteDeals() {
  const rows = db.prepare(`
    SELECT * FROM listings
    WHERE isPublished = 1 AND lastMinuteDiscount > 0
    ORDER BY lastMinuteDiscount DESC, createdAt DESC
  `).all();
  return rows.map((r) => ({
    ...r,
    amenities: JSON.parse(r.amenities || "[]"),
    images: JSON.parse(r.images || "[]"),
    instantBook: Boolean(r.instantBook),
    isPublished: Boolean(r.isPublished),
    originalPricePerNight: r.lastMinuteOriginalPrice || r.pricePerNight,
    discountPercent: r.lastMinuteDiscount,
    dealPricePerNight: Math.round((r.lastMinuteOriginalPrice || r.pricePerNight) * (1 - r.lastMinuteDiscount / 100))
  }));
}

/**
 * İlanın son dakika fırsat bilgisi.
 */
export function getLastMinuteDealById(listingId) {
  const r = db.prepare("SELECT * FROM listings WHERE id = ?").get(listingId);
  if (!r) return null;
  return {
    ...r,
    amenities: JSON.parse(r.amenities || "[]"),
    images: JSON.parse(r.images || "[]"),
    instantBook: Boolean(r.instantBook),
    isPublished: Boolean(r.isPublished),
    originalPricePerNight: r.lastMinuteOriginalPrice || r.pricePerNight,
    discountPercent: r.lastMinuteDiscount,
    dealPricePerNight: Math.round((r.lastMinuteOriginalPrice || r.pricePerNight) * (1 - r.lastMinuteDiscount / 100))
  };
}

/**
 * İlanın etkin gece fiyatı: son dakika fırsatındaysa indirimli fiyat, değilse normal fiyat.
 * BookingWidget/ödeme fiyat matematiğinde kullanılır.
 */
export function getEffectiveNightlyPrice(listing) {
  if (listing && listing.lastMinuteDiscount > 0) {
    return Math.round((listing.lastMinuteOriginalPrice || listing.pricePerNight) * (1 - listing.lastMinuteDiscount / 100));
  }
  return listing?.pricePerNight || 0;
}
