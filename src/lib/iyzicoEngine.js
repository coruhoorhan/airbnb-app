import { calculateBookingPrice } from "./bookingEngine.js";
/**
 * iyzico Payment Gateway Engine (Sandbox & Production)
 * Airbnb Full-Stack Clone
 */

import Iyzipay from "iyzipay";

export const IYZICO_CONFIG = {
  apiKey: process.env.IYZICO_API_KEY || "sandbox-FHSfHRPiIquiczjMMxq0eKMbaaM2SoTr",
  secretKey: process.env.IYZICO_SECRET_KEY || "sandbox-xGUXHJrFeXX09EP9ALt1btpeJZmeqBGZ",
  uri: process.env.IYZICO_BASE_URL || "https://sandbox-api.iyzipay.com"
};

/**
 * Creates an instance of Iyzipay client
 */
export function getIyzipayClient(config = IYZICO_CONFIG) {
  return new Iyzipay({
    apiKey: config.apiKey,
    secretKey: config.secretKey,
    uri: config.uri
  });
}

/**
 * Validates credit/debit card format
 */
export function validateCardDetails(card = {}) {
  if (!card) {
    throw new Error("Kart bilgileri gereklidir.");
  }

  const cardHolderName = (card.cardHolderName || "").trim();
  if (!cardHolderName || cardHolderName.length < 3) {
    throw new Error("Geçerli bir kart sahibi adı giriniz.");
  }

  const cleanNumber = (card.cardNumber || "").replace(/\s+/g, "");
  if (!/^\d{15,16}$/.test(cleanNumber)) {
    throw new Error("Kart numarası 15 veya 16 haneli rakam olmalıdır.");
  }

  const month = parseInt(card.expireMonth, 10);
  if (isNaN(month) || month < 1 || month > 12) {
    throw new Error("Geçersiz son kullanma ayı (01-12).");
  }

  const rawYear = String(card.expireYear || "").trim();
  const year = rawYear.length === 2 ? parseInt(`20${rawYear}`, 10) : parseInt(rawYear, 10);
  const currentYear = new Date().getFullYear();
  if (isNaN(year) || year < currentYear || year > currentYear + 25) {
    throw new Error("Geçersiz son kullanma yılı.");
  }

  const cvc = (card.cvc || "").trim();
  if (!/^\d{3,4}$/.test(cvc)) {
    throw new Error("Geçersiz güvenlik kodu (CVC 3 veya 4 hane olmalıdır).");
  }

  return {
    cardHolderName,
    cardNumber: cleanNumber,
    expireMonth: month < 10 ? `0${month}` : String(month),
    expireYear: String(year),
    cvc
  };
}

/**
 * Formats a number to iyzico price string with 2 decimals
 */
export function formatIyzicoPrice(amount) {
  const num = Number(amount) || 0;
  return num.toFixed(2);
}

/**
 * Builds standard iyzico payment request payload
 */
export function buildPaymentRequest({
  listing,
  buyer = {},
  checkIn,
  checkOut,
  numGuests = 1,
  priceMath,
  discountAmount = 0,
  card = null,
  callbackUrl = null,
  conversationId = null,
  installmentMonths = 1,
  currency = "TRY"
}) {
  const currCode = (currency || "TRY").toUpperCase();
  if (!["TRY", "USD", "EUR", "GBP"].includes(currCode)) {
    throw new Error(`Desteklenmeyen para birimi: ${currCode}`);
  }
  if (!listing || !listing.id) {
    throw new Error("Geçerli bir ilan bilgisi gereklidir.");
  }
  const math = priceMath || (checkIn && checkOut ? calculateBookingPrice(checkIn, checkOut, listing.pricePerNight || 100, listing.cleaningFee || 0, listing.serviceFee || 0) : null);
  if (!math || typeof math.basePrice !== "number") {
    throw new Error("Fiyat dökümü gereklidir.");
  }

  const convId = conversationId || `conv_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
  const basketId = `bsk_${Date.now()}`;

  const basePrice = Number(math.basePrice) || 0;
  const cleaningFee = Number(listing.cleaningFee) || 0;
  const serviceFee = Number(listing.serviceFee) || 0;
  const discount = Math.max(0, Number(discountAmount) || 0);

  // Total original price before discounts
  const rawTotalPrice = basePrice + cleaningFee + serviceFee;
  // Final paid price after discount
  const finalPaidPrice = Math.max(0, (basePrice - discount) + cleaningFee + serviceFee);

  // Prepare basket items
  const basketItems = [];

  // 1. Accommodation item
  basketItems.push({
    id: String(listing.id),
    name: (listing.title || "Konaklama Hizmeti").substring(0, 50),
    category1: listing.category || "Konaklama",
    category2: "Oda/Ev Kiralama",
    itemType: Iyzipay.BASKET_ITEM_TYPE ? Iyzipay.BASKET_ITEM_TYPE.VIRTUAL : "VIRTUAL",
    price: formatIyzicoPrice(basePrice)
  });

  // 2. Cleaning Fee (if > 0)
  if (cleaningFee > 0) {
    basketItems.push({
      id: `cleaning_${listing.id}`,
      name: "Temizlik Hizmet Bedeli",
      category1: "Hizmet",
      category2: "Temizlik",
      itemType: Iyzipay.BASKET_ITEM_TYPE ? Iyzipay.BASKET_ITEM_TYPE.VIRTUAL : "VIRTUAL",
      price: formatIyzicoPrice(cleaningFee)
    });
  }

  // 3. Service Fee (if > 0)
  if (serviceFee > 0) {
    basketItems.push({
      id: `service_${listing.id}`,
      name: "Airbnb Platform Hizmet Bedeli",
      category1: "Hizmet",
      category2: "Komisyon",
      itemType: Iyzipay.BASKET_ITEM_TYPE ? Iyzipay.BASKET_ITEM_TYPE.VIRTUAL : "VIRTUAL",
      price: formatIyzicoPrice(serviceFee)
    });
  }

  // Default buyer info with sane defaults for sandbox
  const buyerName = buyer.name ? buyer.name.split(" ")[0] : "Ahmet";
  const buyerSurname = buyer.name && buyer.name.includes(" ") 
    ? buyer.name.split(" ").slice(1).join(" ") 
    : (buyer.surname || "Yılmaz");

  const buyerData = {
    id: buyer.id || "usr_guest_01",
    name: buyerName,
    surname: buyerSurname,
    gsmNumber: buyer.phone || "+905350000000",
    email: buyer.email || "guest@fatsa.bel.tr",
    identityNumber: buyer.identityNumber || "11111111110",
    lastLoginDate: "2026-08-29 12:00:00",
    registrationDate: "2026-01-01 10:00:00",
    registrationAddress: buyer.address || "Fatsa Sahil Cad. No:1",
    ip: buyer.ip || "127.0.0.1",
    city: buyer.city || listing.city || "Ordu",
    country: buyer.country || "Turkey",
    zipCode: buyer.zipCode || "52400"
  };

  const addressData = {
    contactName: `${buyerName} ${buyerSurname}`,
    city: buyerData.city,
    country: buyerData.country,
    address: buyerData.registrationAddress,
    zipCode: buyerData.zipCode
  };

  const request = {
    locale: Iyzipay.LOCALE ? Iyzipay.LOCALE.TR : "tr",
    conversationId: convId,
    price: formatIyzicoPrice(rawTotalPrice),
    paidPrice: formatIyzicoPrice(finalPaidPrice),
    currency: Iyzipay.CURRENCY ? (Iyzipay.CURRENCY[currCode] || currCode) : currCode,
    installment: String(installmentMonths || 1),
    basketId,
    paymentChannel: Iyzipay.PAYMENT_CHANNEL ? Iyzipay.PAYMENT_CHANNEL.WEB : "WEB",
    paymentGroup: Iyzipay.PAYMENT_GROUP ? Iyzipay.PAYMENT_GROUP.PRODUCT : "PRODUCT",
    buyer: buyerData,
    shippingAddress: addressData,
    billingAddress: addressData,
    basketItems
  };

  if (card) {
    const validatedCard = validateCardDetails(card);
    request.paymentCard = {
      cardHolderName: validatedCard.cardHolderName,
      cardNumber: validatedCard.cardNumber,
      expireMonth: validatedCard.expireMonth,
      expireYear: validatedCard.expireYear,
      cvc: validatedCard.cvc,
      registerCard: "0"
    };
  }

  if (callbackUrl) {
    request.callbackUrl = callbackUrl;
    // Taksit seçenekleri: belirtilen taksit sayısına kadar izin ver, aksi halde varsayılanlar
    if (Number(installmentMonths) > 1) {
      const maxInstallment = Math.max(1, Number(installmentMonths) || 1);
      request.enabledInstallments = [1, 2, 3, 6].filter(i => i <= maxInstallment);
      if (request.enabledInstallments.length === 0) request.enabledInstallments = [1];
    } else {
      request.enabledInstallments = [1, 2, 3, 6];
    }
  }

  return request;
}

/**
 * Executes direct credit/debit card payment via iyzico
 */
export async function processDirectPayment(requestPayload, client = getIyzipayClient()) {
  return new Promise((resolve, reject) => {
    client.payment.create(requestPayload, (err, result) => {
      if (err) {
        return reject(err);
      }
      if (result.status !== "success") {
        const errorMessage = result.errorMessage || result.errorGroup || "Ödeme işlemi gerçekleştirilemedi.";
        const error = new Error(errorMessage);
        error.rawResult = result;
        return reject(error);
      }
      resolve(result);
    });
  });
}

/**
 * Initializes iyzico Checkout Form
 */
export async function initializeCheckoutForm(requestPayload, client = getIyzipayClient()) {
  return new Promise((resolve, reject) => {
    client.checkoutFormInitialize.create(requestPayload, (err, result) => {
      if (err) {
        return reject(err);
      }
      if (result.status !== "success") {
        const errorMessage = result.errorMessage || "Ödeme formu başlatılamadı.";
        const error = new Error(errorMessage);
        error.rawResult = result;
        return reject(error);
      }
      resolve(result);
    });
  });
}

/**
 * Retrieves and verifies iyzico Checkout Form result by token
 */
export async function retrieveCheckoutFormResult(token, client = getIyzipayClient()) {
  return new Promise((resolve, reject) => {
    client.checkoutForm.retrieve({ token }, (err, result) => {
      if (err) {
        return reject(err);
      }
      if (result.status !== "success") {
        const errorMessage = result.errorMessage || "Ödeme sonucu doğrulanamadı.";
        const error = new Error(errorMessage);
        error.rawResult = result;
        return reject(error);
      }
      resolve(result);
    });
  });
}

export const createPaymentRequest = buildPaymentRequest;
