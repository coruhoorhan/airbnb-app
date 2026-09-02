import { describe, it, expect } from "vitest";
import { 
  validateCardDetails, 
  formatIyzicoPrice, 
  buildPaymentRequest 
} from "../src/lib/iyzicoEngine.js";

describe("iyzico Payment Engine", () => {
  const mockListing = {
    id: "list_01",
    title: "Fatsa Sahil Villa",
    category: "Villa",
    city: "Ordu",
    pricePerNight: 2500,
    cleaningFee: 500,
    serviceFee: 300
  };

  const mockPriceMath = {
    nights: 2,
    basePrice: 5000,
    cleaningFee: 500,
    serviceFee: 300,
    totalPrice: 5800
  };

  const mockBuyer = {
    id: "usr_guest_01",
    name: "Ahmet Yılmaz",
    email: "guest@fatsa.bel.tr",
    phone: "+905351234567"
  };

  describe("validateCardDetails", () => {
    it("validates and formats valid card input", () => {
      const card = {
        cardHolderName: "Ahmet Yilmaz",
        cardNumber: "5890 0400 0000 0016",
        expireMonth: "12",
        expireYear: "2028",
        cvc: "123"
      };

      const result = validateCardDetails(card);
      expect(result.cardNumber).toBe("5890040000000016");
      expect(result.cardHolderName).toBe("Ahmet Yilmaz");
      expect(result.expireMonth).toBe("12");
      expect(result.expireYear).toBe("2028");
      expect(result.cvc).toBe("123");
    });

    it("formats single digit expire month to two digits", () => {
      const card = {
        cardHolderName: "Ahmet Yilmaz",
        cardNumber: "4543600000000009",
        expireMonth: "5",
        expireYear: "28",
        cvc: "999"
      };

      const result = validateCardDetails(card);
      expect(result.expireMonth).toBe("05");
      expect(result.expireYear).toBe("2028");
    });

    it("throws error for missing card holder name", () => {
      expect(() => {
        validateCardDetails({ cardNumber: "5890040000000016", expireMonth: "12", expireYear: "2028", cvc: "123" });
      }).toThrow(/kart sahibi/i);
    });

    it("throws error for invalid card number length", () => {
      expect(() => {
        validateCardDetails({ cardHolderName: "Ahmet", cardNumber: "123456", expireMonth: "12", expireYear: "2028", cvc: "123" });
      }).toThrow(/kart numarası/i);
    });

    it("throws error for invalid expire month", () => {
      expect(() => {
        validateCardDetails({ cardHolderName: "Ahmet", cardNumber: "5890040000000016", expireMonth: "13", expireYear: "2028", cvc: "123" });
      }).toThrow(/son kullanma ayı/i);
    });

    it("throws error for expired or invalid year", () => {
      expect(() => {
        validateCardDetails({ cardHolderName: "Ahmet", cardNumber: "5890040000000016", expireMonth: "12", expireYear: "2020", cvc: "123" });
      }).toThrow(/son kullanma yılı/i);
    });

    it("throws error for invalid CVC", () => {
      expect(() => {
        validateCardDetails({ cardHolderName: "Ahmet", cardNumber: "5890040000000016", expireMonth: "12", expireYear: "2028", cvc: "1" });
      }).toThrow(/güvenlik kodu/i);
    });
  });

  describe("formatIyzicoPrice", () => {
    it("formats integers and floats to 2 decimal string", () => {
      expect(formatIyzicoPrice(5000)).toBe("5000.00");
      expect(formatIyzicoPrice(1234.5)).toBe("1234.50");
      expect(formatIyzicoPrice(1234.567)).toBe("1234.57");
      expect(formatIyzicoPrice(0)).toBe("0.00");
    });
  });

  describe("buildPaymentRequest", () => {
    it("builds correct payment request without discount", () => {
      const request = buildPaymentRequest({
        listing: mockListing,
        buyer: mockBuyer,
        checkIn: "2026-09-01",
        checkOut: "2026-09-03",
        numGuests: 2,
        priceMath: mockPriceMath,
        discountAmount: 0
      });

      expect(request.price).toBe("5800.00"); // 5000 + 500 + 300
      expect(request.paidPrice).toBe("5800.00");
      expect(request.currency).toBe("TRY");
      expect(request.buyer.name).toBe("Ahmet");
      expect(request.buyer.surname).toBe("Yılmaz");
      expect(request.basketItems.length).toBe(3); // Accommodation + Cleaning + Service
      
      const basketSum = request.basketItems.reduce((acc, item) => acc + Number(item.price), 0);
      expect(basketSum).toBe(5800);
    });

    it("builds correct payment request with coupon discount", () => {
      const discountAmount = 1000; // 20% off 5000 base
      const request = buildPaymentRequest({
        listing: mockListing,
        buyer: mockBuyer,
        checkIn: "2026-09-01",
        checkOut: "2026-09-03",
        numGuests: 2,
        priceMath: mockPriceMath,
        discountAmount: discountAmount
      });

      expect(request.price).toBe("5800.00"); // Original total
      expect(request.paidPrice).toBe("4800.00"); // 5800 - 1000
      expect(request.basketItems[0].price).toBe("5000.00");
    });

    it("attaches paymentCard when card is provided", () => {
      const card = {
        cardHolderName: "Ahmet Yilmaz",
        cardNumber: "5890040000000016",
        expireMonth: "12",
        expireYear: "2028",
        cvc: "123"
      };

      const request = buildPaymentRequest({
        listing: mockListing,
        buyer: mockBuyer,
        checkIn: "2026-09-01",
        checkOut: "2026-09-03",
        numGuests: 2,
        priceMath: mockPriceMath,
        card
      });

      expect(request.paymentCard).toBeDefined();
      expect(request.paymentCard.cardNumber).toBe("5890040000000016");
      expect(request.paymentCard.cardHolderName).toBe("Ahmet Yilmaz");
    });

    it("attaches callbackUrl when provided", () => {
      const callbackUrl = "http://100.125.64.102:5173/api/payments/iyzico/callback";
      const request = buildPaymentRequest({
        listing: mockListing,
        buyer: mockBuyer,
        checkIn: "2026-09-01",
        checkOut: "2026-09-03",
        numGuests: 2,
        priceMath: mockPriceMath,
        callbackUrl
      });
      expect(request.callbackUrl).toBe(callbackUrl);
      expect(request.enabledInstallments).toEqual([1, 2, 3, 6]);
    });

    it("filters enabledInstallments when installmentMonths is provided", () => {
      const request = buildPaymentRequest({
        listing: mockListing,
        buyer: mockBuyer,
        checkIn: "2026-09-01",
        checkOut: "2026-09-03",
        numGuests: 2,
        priceMath: mockPriceMath,
        callbackUrl: "http://localhost/callback",
        installmentMonths: 6
      });

      expect(request.installment).toBe("6");
      expect(request.enabledInstallments).toEqual([1, 2, 3, 6]);
    });

    it("restricts enabledInstallments to requested max", () => {
      const request = buildPaymentRequest({
        listing: mockListing,
        buyer: mockBuyer,
        checkIn: "2026-09-01",
        checkOut: "2026-09-03",
        numGuests: 2,
        priceMath: mockPriceMath,
        callbackUrl: "http://localhost/callback",
        installmentMonths: 2
      });

      expect(request.installment).toBe("2");
      expect(request.enabledInstallments).toEqual([1, 2]);
    });
  });
});
