/**
 * Multi-Currency & Exchange Rate Engine
 * Airbnb Full-Stack Clone
 */

export const SUPPORTED_CURRENCIES = {
  TRY: {
    code: "TRY",
    symbol: "₺",
    name: "Türk Lirası",
    rateToTry: 1.0,      // Base currency
    locale: "tr-TR"
  },
  USD: {
    code: "USD",
    symbol: "$",
    name: "US Dollar",
    rateToTry: 0.029,    // 1 USD ~ 34.50 TRY
    locale: "en-US"
  },
  EUR: {
    code: "EUR",
    symbol: "€",
    name: "Euro",
    rateToTry: 0.026,    // 1 EUR ~ 38.20 TRY
    locale: "de-DE"
  },
  GBP: {
    code: "GBP",
    symbol: "£",
    name: "British Pound",
    rateToTry: 0.022,    // 1 GBP ~ 45.40 TRY
    locale: "en-GB"
  }
};

/**
 * Converts price from base currency (TRY) to target currency
 */
export function convertPrice(amountInTry, targetCurrency = "TRY") {
  const num = Number(amountInTry) || 0;
  const currency = SUPPORTED_CURRENCIES[targetCurrency] || SUPPORTED_CURRENCIES.TRY;
  
  if (currency.code === "TRY") {
    return Math.round(num);
  }

  const converted = num * currency.rateToTry;
  return Math.round(converted);
}

/**
 * Formats price in target currency with symbol and locale formatting
 */
export function formatCurrency(amountInTry, targetCurrency = "TRY") {
  const converted = convertPrice(amountInTry, targetCurrency);
  const currency = SUPPORTED_CURRENCIES[targetCurrency] || SUPPORTED_CURRENCIES.TRY;

  return `${currency.symbol}${converted.toLocaleString(currency.locale)}`;
}

/**
 * Returns all supported currencies
 */
export function getAvailableCurrencies() {
  return Object.values(SUPPORTED_CURRENCIES);
}
