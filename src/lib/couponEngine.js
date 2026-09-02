/**
 * Kupon ve İndirim Kodu Doğrulama ve Hesaplama Motoru
 * (Coupon & Discount Engine)
 */

/**
 * Kuponu doğrular ve uygulanacak indirim tutarını hesaplar.
 *
 * @param {Object} coupon - Kupon nesnesi
 * @param {number} basePrice - Ham konaklama bedeli
 * @param {string|Date} [checkInDate] - Giriş tarihi
 * @param {number} [now=Date.now()] - Doğrulama anındaki zaman damgası
 * @returns {Object} { valid, code, discountType, discountValue, discountAmount, finalBasePrice }
 */
export function validateAndCalculateDiscount(coupon, basePrice, checkInDate, now = Date.now()) {
  if (!coupon || !coupon.code) {
    throw new Error('Geçersiz kupon kodu.');
  }

  if (coupon.isActive !== undefined && coupon.isActive !== 1 && coupon.isActive !== true) {
    throw new Error('Bu kupon kodu aktif değil.');
  }

  const numericBasePrice = Number(basePrice) || 0;

  // Minimum sepet tutarı kontrolü
  const minAmount = Number(coupon.minAmount) || 0;
  if (numericBasePrice < minAmount) {
    throw new Error(`Bu kupon için minimum konaklama tutarı ₺${minAmount} olmalıdır.`);
  }

  // Son kullanma tarihi kontrolü
  if (coupon.expiryDate) {
    const expiryTime = new Date(`${coupon.expiryDate}T23:59:59.999Z`).getTime();
    const currentTime = typeof now === 'number' ? now : new Date(now).getTime();

    if (currentTime > expiryTime) {
      throw new Error('Bu kuponun süresi dolmuş.');
    }
  }

  // İndirim hesaplama
  let discountAmount = 0;
  const discountVal = Number(coupon.discountValue) || 0;

  if (coupon.discountType === 'percentage') {
    discountAmount = Math.round((numericBasePrice * discountVal) / 100);
  } else if (coupon.discountType === 'fixed') {
    discountAmount = Math.min(numericBasePrice, discountVal);
  } else {
    throw new Error('Geçersiz indirim türü.');
  }

  discountAmount = Math.max(0, Math.min(numericBasePrice, discountAmount));
  const finalBasePrice = Math.max(0, numericBasePrice - discountAmount);

  return {
    valid: true,
    code: coupon.code,
    discountType: coupon.discountType,
    discountValue: coupon.discountValue,
    discountAmount,
    finalBasePrice
  };
}
