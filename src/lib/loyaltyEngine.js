/**
 * Sadakat Puanı Motoru (Loyalty Points Engine)
 * Her rezervasyonda puan kazan, kupon olarak kullan.
 *
 * Kural: ₺1 harcama = 1 puan, 1000 puan = ₺100 indirim (₺1 = 0.1₺ değer)
 * Konaklama bedeli (gece + temizlik) üzerinden puan kazanılır, hizmet bedeli hariç.
 */
import { db } from "./db.js";

export const POINTS_PER_TL = 1;          // ₺1 = 1 puan
export const POINTS_TO_TL = 1000;        // 1000 puan = ₺100
export const POINTS_REDEEM_STEP = 1000;  // En az 1000 puan ile kullanılabilir

/**
 * Kullanıcının güncel puan bakiyesini döner.
 */
export function getLoyaltyBalance(userId) {
  const row = db.prepare("SELECT * FROM loyalty_accounts WHERE userId = ?").get(userId);
  return {
    userId,
    balance: row?.balance || 0,
    lifetimeEarned: row?.lifetimeEarned || 0,
    lifetimeRedeemed: row?.lifetimeRedeemed || 0
  };
}

/**
 * Kazanılan puanları hesaba işler. Booking tamamlandığında çağrılır.
 * @returns {Object} yeni bakiye bilgisi
 */
export function awardLoyaltyPoints(userId, bookingId, earnedPoints) {
  const points = Math.max(0, Math.round(Number(earnedPoints) || 0));
  if (!points) return null;

  db.prepare(`
    INSERT INTO loyalty_accounts (userId, balance, lifetimeEarned, lifetimeRedeemed, updatedAt)
    VALUES (?, ?, ?, 0, ?)
    ON CONFLICT(userId) DO UPDATE SET
      balance = balance + excluded.balance,
      lifetimeEarned = lifetimeEarned + excluded.lifetimeEarned,
      updatedAt = excluded.updatedAt
  `).run(userId, points, points, Date.now());

  db.prepare(`
    INSERT INTO loyalty_transactions (id, userId, type, amount, description, createdAt)
    VALUES (?, ?, 'earn', ?, ?, ?)
  `).run(`ltx_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`, userId, points, `Rezervasyon ${bookingId} tamamlandı`, Date.now());

  return getLoyaltyBalance(userId);
}

/**
 * Puanları indirim kuponuna çevirir (redeem).
 * Minumum POINTS_REDEEM_STEP adet puan kullanılabilir.
 * @returns {Object} { success, couponCode, discountAmount, newBalance, error? }
 */
export function redeemLoyaltyPoints(userId, pointsToRedeem) {
  const account = getLoyaltyBalance(userId);
  const points = Math.max(0, Math.round(Number(pointsToRedeem) || 0));

  if (points < POINTS_REDEEM_STEP) {
    return { success: false, error: `En az ${POINTS_REDEEM_STEP} puan ile kullanılabilir.` };
  }
  if (points > account.balance) {
    return { success: false, error: "Yetersiz puan bakiyesi." };
  }

  const discountAmount = Math.round((points / POINTS_TO_TL) * 100);
  const couponCode = `LOYAL${Math.random().toString(36).toUpperCase().substring(2, 8)}`;

  // Puanı düş, kuponu oluştur
  const tx = db.transaction(() => {
    db.prepare(`
      INSERT INTO loyalty_accounts (userId, balance, lifetimeEarned, lifetimeRedeemed, updatedAt)
      VALUES (?, ?, 0, ?, ?)
      ON CONFLICT(userId) DO UPDATE SET
        balance = balance - ?,
        lifetimeRedeemed = lifetimeRedeemed + ?,
        updatedAt = ?
    `).run(userId, 0, points, Date.now(), points, points, Date.now());

    db.prepare(`
      INSERT INTO loyalty_transactions (id, userId, type, amount, description, createdAt)
      VALUES (?, ?, 'redeem', ?, ?, ?)
    `).run(`ltx_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`, userId, points, `Puan dönüşümü: ${couponCode}`);

    db.prepare(`
      INSERT INTO coupons (code, discountType, discountValue, minAmount, expiryDate, usageCount, isActive)
      VALUES (?, 'fixed', ?, 0, ?, 0, 1)
    `).run(couponCode, discountAmount, "2026-12-31");
  });
  tx();

  return {
    success: true,
    couponCode,
    discountAmount,
    newBalance: getLoyaltyBalance(userId).balance
  };
}

/**
 * Kullanıcının puan geçmişini döner.
 */
export function getLoyaltyTransactions(userId, limit = 20) {
  return db.prepare(
    "SELECT * FROM loyalty_transactions WHERE userId = ? ORDER BY createdAt DESC LIMIT ?"
  ).all(userId, limit);
}

export const TIER_THRESHOLDS = [
  { name: "Bronz", min: 0, color: "text-amber-700", bg: "bg-amber-100", icon: "Circle" },
  { name: "Gümüş", min: 5000, color: "text-slate-500", bg: "bg-slate-100", icon: "CircleDot" },
  { name: "Altın", min: 20000, color: "text-yellow-600", bg: "bg-yellow-100", icon: "Award" },
  { name: "Platin", min: 50000, color: "text-purple-600", bg: "bg-purple-100", icon: "Crown" }
];

export function getLoyaltyTier(lifetimeEarned) {
  const points = lifetimeEarned || 0;
  let current = TIER_THRESHOLDS[0];
  let next = TIER_THRESHOLDS[1];
  for (let i = TIER_THRESHOLDS.length - 1; i >= 0; i--) {
    if (points >= TIER_THRESHOLDS[i].min) {
      current = TIER_THRESHOLDS[i];
      next = TIER_THRESHOLDS[i + 1] || null;
      break;
    }
  }
  return {
    tier: current,
    nextTier: next,
    pointsToNext: next ? next.min - points : 0,
    progress: next ? Math.min(100, Math.round(((points - current.min) / (next.min - current.min)) * 100)) : 100
  };
}

/**
 * Get lifetime total earned points for a user
 */
export function getLifetimeEarned(userId) {
  const row = db.prepare("SELECT COALESCE(SUM(amount), 0) as total FROM loyalty_transactions WHERE userId = ? AND type = 'earn'").get(userId);
  return row?.total || 0;
}
