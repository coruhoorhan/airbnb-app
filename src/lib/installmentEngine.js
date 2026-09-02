/**
 * Taksit Hesaplama Motoru (Installment Engine)
 * iyzico destekli taksit seçenekleri: 1, 2, 3, 6, 9, 12.
 *
 * Model: Banka taksitli satışa faiz uygular. iyzico sandbox'ında taksit
 * planları `installment` alanı ile gönderilir; burada sadece kullanıcıya
 * gösterilecek aylık ödeme dökümü hesaplanır.
 */
export const INSTALLMENT_PLANS = [
  { months: 1,  feeRate: 0.00, label: "Tek Çekim",  badge: null },
  { months: 2,  feeRate: 0.00, label: "2 Taksit",   badge: null },
  { months: 3,  feeRate: 0.00, label: "3 Taksit",   badge: null },
  { months: 6,  feeRate: 0.05, label: "6 Taksit",   badge: "Faizsiz",  note: "+%5" },
  { months: 9,  feeRate: 0.09, label: "9 Taksit",   badge: null,       note: "+%9" },
  { months: 12, feeRate: 0.12, label: "12 Taksit",  badge: null,       note: "+%12" }
];

/**
 * Taksit planlarını hesaplanmış aylık ödemelerle döner.
 * @param {number} totalPrice - toplam ödeme tutarı (TRY)
 */
export function getInstallmentPlans(totalPrice) {
  const price = Math.max(0, Number(totalPrice) || 0);
  return INSTALLMENT_PLANS.map((plan) => {
    const total = Math.round(price * (1 + plan.feeRate));
    const monthly = Math.ceil(total / plan.months);
    const lastPayment = total - monthly * (plan.months - 1);
    return {
      ...plan,
      totalPrice: total,
      monthlyPayment: monthly,
      lastPayment,
      feeAmount: total - price
    };
  });
}

/**
 * Seçilen taksit planına göre iyzico `installment` alanı değerini döner.
 */
export function resolveInstallmentMonths(plan) {
  return String(plan?.months || 1);
}
