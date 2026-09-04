/**
 * Yapay Zekâ Dinamik Fiyatlandırma Motoru
 *
 * Doluluk oranı, mevsimsellik ve talep yoğunluğuna göre optimal gecelik fiyat hesaplayan akıllı motor.
 */

/**
 * Dinamik fiyat hesaplar
 * @param {number} basePrice - Taban fiyat
 * @param {Object} factors - Etken faktörler
 * @param {number} factors.occupancyRate - Doluluk oranı (0 ile 1 arasında, örn: 0.85 = %85)
 * @param {string|number} factors.month - Ay (1-12 veya ay ismi)
 * @param {string} factors.demandIntensity - Talep yoğunluğu ("low", "medium", "high", "critical")
 * @returns {Object} { recommendedPrice, basePrice, multipliers: { occupancy, season, demand } }
 */
export function calculateDynamicPrice(basePrice, { occupancyRate = 0, month = 1, demandIntensity = "medium" }) {
  if (basePrice <= 0) throw new Error("Taban fiyat 0'dan büyük olmalıdır.");

  let occupancyMultiplier = 1.0;
  let seasonMultiplier = 1.0;
  let demandMultiplier = 1.0;

  // 1. Doluluk oranı etkisi
  // Doluluk > %80 ise fiyat %20 artar
  // Doluluk < %30 ise fiyat %10 düşer
  if (occupancyRate >= 0.8) {
    occupancyMultiplier = 1.2;
  } else if (occupancyRate >= 0.6) {
    occupancyMultiplier = 1.1;
  } else if (occupancyRate <= 0.3) {
    occupancyMultiplier = 0.9;
  }

  // 2. Mevsimsellik etkisi (Yaz ayları yüksek sezon)
  // Haziran (6), Temmuz (7), Ağustos (8)
  const m = typeof month === 'string' ? parseInt(month, 10) : month;
  if ([6, 7, 8].includes(m)) {
    seasonMultiplier = 1.5; // Yaz aylarında fiyat %50 artar
  } else if ([5, 9].includes(m)) {
    seasonMultiplier = 1.2; // Omuz sezon
  } else if ([12, 1, 2].includes(m)) {
    seasonMultiplier = 0.8; // Kış ayları düşük sezon
  }

  // 3. Talep yoğunluğu etkisi (Bölgesel etkinlikler vs.)
  switch (demandIntensity.toLowerCase()) {
    case "low":
      demandMultiplier = 0.9;
      break;
    case "medium":
      demandMultiplier = 1.0;
      break;
    case "high":
      demandMultiplier = 1.3;
      break;
    case "critical":
      demandMultiplier = 1.5;
      break;
    default:
      demandMultiplier = 1.0;
  }

  // Son fiyat hesaplama (çarpanların etkisi)
  const combinedMultiplier = occupancyMultiplier * seasonMultiplier * demandMultiplier;
  const recommendedPrice = Math.round(basePrice * combinedMultiplier);

  return {
    recommendedPrice,
    basePrice,
    multipliers: {
      occupancy: occupancyMultiplier,
      season: seasonMultiplier,
      demand: demandMultiplier
    }
  };
}
