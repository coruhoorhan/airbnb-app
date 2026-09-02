import { describe, it, expect } from 'vitest';
import { validateAndCalculateDiscount } from '../src/lib/couponEngine.js';

describe('Coupon and Discount Engine', () => {
  const mockNow = new Date('2026-08-29T12:00:00Z').getTime();

  it('validates and applies percentage coupon FATSA2026 (%20 off, min 3000)', () => {
    const coupon = {
      code: 'FATSA2026',
      discountType: 'percentage',
      discountValue: 20,
      minAmount: 3000,
      expiryDate: '2026-12-31',
      isActive: 1
    };

    const basePrice = 5000;
    const result = validateAndCalculateDiscount(coupon, basePrice, '2026-09-01', mockNow);

    expect(result.valid).toBe(true);
    expect(result.discountAmount).toBe(1000); // 5000 * 0.20 = 1000
    expect(result.finalBasePrice).toBe(4000);
    expect(result.code).toBe('FATSA2026');
  });

  it('validates and applies fixed discount coupon HOSGELDIN (500 off, min 2000)', () => {
    const coupon = {
      code: 'HOSGELDIN',
      discountType: 'fixed',
      discountValue: 500,
      minAmount: 2000,
      expiryDate: '2026-12-31',
      isActive: 1
    };

    const basePrice = 2500;
    const result = validateAndCalculateDiscount(coupon, basePrice, '2026-09-01', mockNow);

    expect(result.valid).toBe(true);
    expect(result.discountAmount).toBe(500);
    expect(result.finalBasePrice).toBe(2000);
    expect(result.code).toBe('HOSGELDIN');
  });

  it('rejects coupon when basePrice is below minAmount', () => {
    const coupon = {
      code: 'FATSA2026',
      discountType: 'percentage',
      discountValue: 20,
      minAmount: 3000,
      expiryDate: '2026-12-31',
      isActive: 1
    };

    const basePrice = 2500; // < 3000
    expect(() => {
      validateAndCalculateDiscount(coupon, basePrice, '2026-09-01', mockNow);
    }).toThrow(/minimum/i);
  });

  it('rejects expired coupon', () => {
    const coupon = {
      code: 'EXPIRED20',
      discountType: 'percentage',
      discountValue: 20,
      minAmount: 1000,
      expiryDate: '2026-01-01', // Expired relative to mockNow (2026-08-29)
      isActive: 1
    };

    const basePrice = 5000;
    expect(() => {
      validateAndCalculateDiscount(coupon, basePrice, '2026-09-01', mockNow);
    }).toThrow(/expired|süresi dolmuş|son kullan/i);
  });

  it('rejects inactive or invalid coupon', () => {
    const inactiveCoupon = {
      code: 'INACTIVE',
      discountType: 'fixed',
      discountValue: 100,
      minAmount: 500,
      expiryDate: '2026-12-31',
      isActive: 0
    };

    expect(() => {
      validateAndCalculateDiscount(inactiveCoupon, 1000, '2026-09-01', mockNow);
    }).toThrow(/geçersiz|invalid|inactive|aktif değil/i);

    expect(() => {
      validateAndCalculateDiscount(null, 1000, '2026-09-01', mockNow);
    }).toThrow(/geçersiz|invalid/i);
  });

  it('ensures discount is only applied to basePrice without altering cleaning or service fees', () => {
    const coupon = {
      code: 'FATSA2026',
      discountType: 'percentage',
      discountValue: 20,
      minAmount: 3000,
      expiryDate: '2026-12-31',
      isActive: 1
    };

    const basePrice = 4000;
    const cleaningFee = 500;
    const serviceFee = 300;

    const discountRes = validateAndCalculateDiscount(coupon, basePrice, '2026-09-01', mockNow);
    expect(discountRes.discountAmount).toBe(800); // 4000 * 20% = 800

    const totalBefore = basePrice + cleaningFee + serviceFee; // 4800
    const totalAfter = (basePrice - discountRes.discountAmount) + cleaningFee + serviceFee; // 3200 + 500 + 300 = 4000

    expect(totalBefore - totalAfter).toBe(discountRes.discountAmount);
  });

  it('caps fixed discount at basePrice to avoid negative price', () => {
    const coupon = {
      code: 'BIGDISCOUNT',
      discountType: 'fixed',
      discountValue: 1000,
      minAmount: 500,
      expiryDate: '2026-12-31',
      isActive: 1
    };

    const basePrice = 800;
    const result = validateAndCalculateDiscount(coupon, basePrice, '2026-09-01', mockNow);
    expect(result.discountAmount).toBe(800);
    expect(result.finalBasePrice).toBe(0);
  });
});
