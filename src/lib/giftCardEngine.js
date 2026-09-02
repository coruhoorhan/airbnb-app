/**
 * Hediye Kartı Motoru (Gift Card Engine)
 * Satın al + kod oluştur, kupon olarak kullan (fixed indirim).
 */
import { db } from "./db.js";

/**
 * Yeni hediye kartı oluşturur.
 * @param {Object} params { buyerId, recipientName, amount, message }
 * @returns {Object} hediye kartı
 */
export function createGiftCard({ buyerId, recipientName = null, amount, message = null }) {
  const cardAmount = Math.max(100, Math.round(Number(amount) || 0));
  const code = `GIFT-${generateCode(12)}`;
  const expiresAt = Date.now() + 365 * 86400000; // 1 yıl geçerli

  db.prepare(`
    INSERT INTO gift_cards (code, buyerId, recipientName, amount, remainingBalance, message, isActive, expiresAt, createdAt, redeemedAt)
    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, NULL)
  `).run(code, buyerId, recipientName, cardAmount, cardAmount, message, expiresAt, Date.now());

  return getGiftCardByCode(code);
}

/**
 * Kod ile hediye kartını çeker.
 */
export function getGiftCardByCode(code) {
  if (!code) return null;
  const upperCode = code.trim().toUpperCase();
  const card = db.prepare("SELECT * FROM gift_cards WHERE code = ?").get(upperCode);
  if (!card) return null;
  return {
    ...card,
    isActive: Boolean(card.isActive)
  };
}

/**
 * Hediye kartını bir rezervasyonda kullanır.
 * Bakiye kısmi olarak da kullanılabilir; kart tamamen bitene kadar aktif kalır.
 * @returns {Object} { success, code, amountUsed, remainingBalance, error? }
 */
export function redeemGiftCard(code, amountToApply) {
  const card = getGiftCardByCode(code);
  if (!card) return { success: false, error: "Geçersiz hediye kartı kodu." };
  if (!card.isActive) return { success: false, error: "Bu hediye kartı pasif." };
  if (Date.now() > card.expiresAt) return { success: false, error: "Bu hediye kartının süresi dolmuş." };
  if (card.remainingBalance <= 0) return { success: false, error: "Bu hediye kartının bakiyesi tükenmiş." };

  const amountUsed = Math.min(card.remainingBalance, Math.max(0, Number(amountToApply) || 0));
  if (amountUsed <= 0) return { success: false, error: "Uygulanacak tutar geçersiz." };

  const newBalance = card.remainingBalance - amountUsed;
  const wasFullyRedeemed = newBalance <= 0;

  const tx = db.transaction(() => {
    db.prepare(`
      UPDATE gift_cards
      SET remainingBalance = ?,
          isActive = ?,
          redeemedAt = CASE WHEN redeemedAt IS NULL THEN ? ELSE redeemedAt END
      WHERE code = ?
    `).run(Math.max(0, newBalance), wasFullyRedeemed ? 0 : 1, Date.now(), card.code);

    db.prepare(`
      INSERT INTO gift_card_transactions (id, giftCardCode, amount, note, createdAt)
      VALUES (?, ?, ?, ?, ?)
    `).run(`gctx_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`, card.code, amountUsed, "Rezervasyon ödemesinde kullanıldı", Date.now());
  });
  tx();

  return {
    success: true,
    code: card.code,
    amountUsed,
    remainingBalance: Math.max(0, newBalance)
  };
}

/**
 * Kullanıcının satın aldığı hediye kartlarını listeler.
 */
export function getGiftCardsForBuyer(buyerId) {
  return db.prepare("SELECT * FROM gift_cards WHERE buyerId = ? ORDER BY createdAt DESC").all(buyerId);
}

/**
 * Hediye kartı işlem geçmişi.
 */
export function getGiftCardTransactions(code) {
  return db.prepare("SELECT * FROM gift_card_transactions WHERE giftCardCode = ? ORDER BY createdAt DESC").all(code);
}

function generateCode(len) {
  const alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
  let out = "";
  for (let i = 0; i < len; i++) {
    out += alphabet[Math.floor(Math.random() * alphabet.length)];
  }
  return out;
}
