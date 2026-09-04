import { describe, it, expect } from "vitest";
import { calculateDynamicPrice } from "../src/lib/pricingEngine.js";

describe("Yapay Zekâ Dinamik Fiyatlandırma Motoru", () => {
  it("temel fiyat ve düşük etkenlerle fiyatı düşürür", () => {
    const basePrice = 1000;
    const result = calculateDynamicPrice(basePrice, { occupancyRate: 0.2, month: 11, demandIntensity: "low" });

    expect(result.basePrice).toBe(1000);
    expect(result.multipliers.occupancy).toBe(0.9); // < 0.3
    expect(result.multipliers.season).toBe(1.0); // 11 is not winter/summer/shoulder, just 1.0 (wait, check pricingEngine.js for 11 -> it falls to else? Actually there's no else, it's 1.0)
    expect(result.multipliers.demand).toBe(0.9);

    // 1000 * 0.9 * 1.0 * 0.9 = 810
    expect(result.recommendedPrice).toBe(810);
  });

  it("yüksek sezon, yüksek doluluk ve yüksek talepte fiyatı artırır", () => {
    const basePrice = 1000;
    const result = calculateDynamicPrice(basePrice, { occupancyRate: 0.9, month: 7, demandIntensity: "high" });

    expect(result.multipliers.occupancy).toBe(1.2); // >= 0.8
    expect(result.multipliers.season).toBe(1.5); // 7 is summer
    expect(result.multipliers.demand).toBe(1.3); // high

    // 1000 * 1.2 * 1.5 * 1.3 = 2340
    expect(result.recommendedPrice).toBe(2340);
  });

  it("omuz sezon ve kritik talepte fiyatı hesaplar", () => {
    const basePrice = 2000;
    const result = calculateDynamicPrice(basePrice, { occupancyRate: 0.65, month: 9, demandIntensity: "critical" });

    expect(result.multipliers.occupancy).toBe(1.1); // >= 0.6
    expect(result.multipliers.season).toBe(1.2); // 9 is shoulder
    expect(result.multipliers.demand).toBe(1.5); // critical

    // 2000 * 1.1 * 1.2 * 1.5 = 3960
    expect(result.recommendedPrice).toBe(3960);
  });

  it("kış sezonu ve normal talepte fiyatı indirger", () => {
    const basePrice = 1000;
    const result = calculateDynamicPrice(basePrice, { occupancyRate: 0.4, month: 1, demandIntensity: "medium" });

    expect(result.multipliers.occupancy).toBe(1.0); // 0.4 falls to default 1.0
    expect(result.multipliers.season).toBe(0.8); // 1 is winter
    expect(result.multipliers.demand).toBe(1.0); // medium

    // 1000 * 1.0 * 0.8 * 1.0 = 800
    expect(result.recommendedPrice).toBe(800);
  });

  it("hatalı verilerde hata fırlatır", () => {
    expect(() => calculateDynamicPrice(0, { occupancyRate: 0.5, month: 1, demandIntensity: "low" })).toThrow("Taban fiyat 0'dan büyük olmalıdır.");
    expect(() => calculateDynamicPrice(-100, { occupancyRate: 0.5, month: 1, demandIntensity: "low" })).toThrow("Taban fiyat 0'dan büyük olmalıdır.");
  });

  it("eksik parametrelerde varsayılanları kullanır", () => {
    const result = calculateDynamicPrice(1000, {});
    expect(result.multipliers.occupancy).toBe(0.9); // occupancyRate default is 0 (<= 0.3)
    expect(result.multipliers.season).toBe(0.8); // month default is 1 (winter)
    expect(result.multipliers.demand).toBe(1.0); // demand default is medium

    // 1000 * 0.9 * 0.8 * 1.0 = 720
    expect(result.recommendedPrice).toBe(720);
  });
});
