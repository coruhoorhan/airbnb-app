import { describe, it, expect } from "vitest";
import { 
  convertPrice, 
  formatCurrency, 
  getAvailableCurrencies, 
  SUPPORTED_CURRENCIES 
} from "../src/lib/currencyEngine.js";

describe("Multi-Currency & Exchange Rate Engine", () => {
  it("converts base TRY amounts correctly to target currencies", () => {
    const amountInTry = 10000;

    // TRY
    expect(convertPrice(amountInTry, "TRY")).toBe(10000);

    // USD (10000 * 0.029 = 290)
    expect(convertPrice(amountInTry, "USD")).toBe(290);

    // EUR (10000 * 0.026 = 260)
    expect(convertPrice(amountInTry, "EUR")).toBe(260);

    // GBP (10000 * 0.022 = 220)
    expect(convertPrice(amountInTry, "GBP")).toBe(220);
  });

  it("formats currency strings with proper symbols", () => {
    expect(formatCurrency(5000, "TRY")).toContain("₺");
    expect(formatCurrency(5000, "USD")).toContain("$");
    expect(formatCurrency(5000, "EUR")).toContain("€");
    expect(formatCurrency(5000, "GBP")).toContain("£");
  });

  it("handles fallback to TRY for unknown currency codes", () => {
    expect(convertPrice(1000, "UNKNOWN")).toBe(1000);
    expect(formatCurrency(1000, "UNKNOWN")).toContain("₺");
  });

  it("returns list of all supported currencies with symbols", () => {
    const currencies = getAvailableCurrencies();
    expect(currencies.length).toBe(4);
    const codes = currencies.map((c) => c.code);
    expect(codes).toContain("TRY");
    expect(codes).toContain("USD");
    expect(codes).toContain("EUR");
    expect(codes).toContain("GBP");
  });
});
