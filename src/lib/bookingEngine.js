/**
 * Airbnb Core Booking & Conflict Engine (TDD Core)
 */

/**
 * Checks if two date intervals overlap.
 * Rule: Check-out day of booking 1 can be check-in day of booking 2 (same-day transition is allowed).
 */
export function checkIntervalOverlap(newCheckIn, newCheckOut, existingCheckIn, existingCheckOut) {
  const nIn = new Date(newCheckIn).getTime();
  const nOut = new Date(newCheckOut).getTime();
  const eIn = new Date(existingCheckIn).getTime();
  const eOut = new Date(existingCheckOut).getTime();

  if (nIn >= nOut) {
    throw new Error("Geçersiz tarih aralığı: Çıkış tarihi giriş tarihinden sonra olmalıdır.");
  }

  // Overlap Formula: (New_CheckIn < Existing_CheckOut) AND (New_CheckOut > Existing_CheckIn)
  return nIn < eOut && nOut > eIn;
}

/**
 * Validates if a new booking has conflicts with existing bookings or host blocks
 */
export function validateBookingConflict(listingId, newCheckIn, newCheckOut, existingBookings = [], availabilityBlocks = []) {
  // 1. Check against confirmed and pending bookings for the same listing
  const activeBookings = existingBookings.filter(
    (b) => b.listingId === listingId && (b.status === "confirmed" || b.status === "pending")
  );

  for (const booking of activeBookings) {
    if (checkIntervalOverlap(newCheckIn, newCheckOut, booking.checkIn, booking.checkOut)) {
      return {
        hasConflict: true,
        reason: "Seçtiğiniz tarihler başka bir misafir tarafından rezerve edilmiş.",
        conflictingBookingId: booking.id
      };
    }
  }

  // 2. Check against host manual calendar blocks
  const blocks = availabilityBlocks.filter((a) => a.listingId === listingId);
  for (const block of blocks) {
    if (checkIntervalOverlap(newCheckIn, newCheckOut, block.startDate, block.endDate)) {
      return {
        hasConflict: true,
        reason: "Seçtiğiniz tarihler ev sahibi tarafından takvimde kapatılmış.",
        blockReason: block.reason || "Ev sahibi kapattı"
      };
    }
  }

  return { hasConflict: false };
}

/**
 * Server-side dynamic price calculation (prevents price tampering)
 */
export function calculateBookingPrice(checkIn, checkOut, pricePerNight, cleaningFee = 0, serviceFee = 0) {
  const start = new Date(checkIn).getTime();
  const end = new Date(checkOut).getTime();
  
  if (start >= end) {
    throw new Error("Çıkış tarihi giriş tarihinden sonra olmalıdır.");
  }

  const nights = Math.max(1, Math.round((end - start) / (1000 * 60 * 60 * 24)));
  const basePrice = nights * pricePerNight;
  const total = basePrice + cleaningFee + serviceFee;

  return {
    nights,
    basePrice,
    cleaningFee,
    serviceFee,
    totalPrice: total
  };
}

/**
 * Cancellation & Refund Engine
 * Policies:
 * - flexible: 100% refund up to 24h before check-in; after that, first night non-refundable
 * - moderate: 100% refund up to 5 days before check-in; after that, 50% refund
 * - strict: 100% refund within 48h of booking (if >=14 days to check-in); else 50% or 0%
 * - host cancelled: Always 100% refund
 */
export function calculateCancellationRefund(checkIn, totalPrice, nightlyPrice, policy = "flexible", cancelledByHost = false, now = Date.now()) {
  if (cancelledByHost) {
    return {
      refundAmount: totalPrice,
      hostPayout: 0,
      refundPercentage: 100,
      description: "Ev sahibi iptali nedeniyle %100 kesintisiz iade."
    };
  }

  const checkInTime = new Date(checkIn).getTime();
  const hoursUntilCheckIn = (checkInTime - now) / (1000 * 60 * 60);

  if (hoursUntilCheckIn <= 0) {
    return {
      refundAmount: 0,
      hostPayout: totalPrice,
      refundPercentage: 0,
      description: "Giriş saati geçtiği için iade yapılamaz."
    };
  }

  if (policy === "flexible") {
    if (hoursUntilCheckIn >= 24) {
      return {
        refundAmount: totalPrice,
        hostPayout: 0,
        refundPercentage: 100,
        description: "Girişe 24 saatten fazla olduğu için %100 tam iade."
      };
    } else {
      const nonRefundableFirstNight = nightlyPrice;
      const refund = Math.max(0, totalPrice - nonRefundableFirstNight);
      return {
        refundAmount: refund,
        hostPayout: nonRefundableFirstNight,
        refundPercentage: Math.round((refund / totalPrice) * 100),
        description: "Girişe 24 saatten az kaldığı için ilk gece hariç iade."
      };
    }
  }

  if (policy === "moderate") {
    const daysUntil = hoursUntilCheckIn / 24;
    if (daysUntil >= 5) {
      return {
        refundAmount: totalPrice,
        hostPayout: 0,
        refundPercentage: 100,
        description: "Girişe 5 günden fazla olduğu için %100 tam iade."
      };
    } else {
      const refund = Math.round(totalPrice * 0.5);
      return {
        refundAmount: refund,
        hostPayout: totalPrice - refund,
        refundPercentage: 50,
        description: "Girişe 5 günden az kaldığı için %50 iade."
      };
    }
  }

  // Strict Policy
  const daysUntil = hoursUntilCheckIn / 24;
  if (daysUntil >= 14) {
    return {
      refundAmount: totalPrice,
      hostPayout: 0,
      refundPercentage: 100,
      description: "Girişe 14 günden fazla olduğu için %100 tam iade."
    };
  } else if (daysUntil >= 7) {
    const refund = Math.round(totalPrice * 0.5);
    return {
      refundAmount: refund,
      hostPayout: totalPrice - refund,
      refundPercentage: 50,
      description: "Girişe 7-14 gün kaldığı için %50 iade."
    };
  } else {
    return {
      refundAmount: 0,
      hostPayout: totalPrice,
      refundPercentage: 0,
      description: "Katı iptal politikası nedeniyle son 7 gün içinde iade yapılmaz."
    };
  }
}

/**
 * Atomic Review Score Recomputation
 */
export function recomputeAverageRating(currentAvg = 0, currentCount = 0, newRating = 5) {
  if (currentCount <= 0) {
    return {
      avgRating: Number(newRating.toFixed(2)),
      reviewCount: 1
    };
  }
  const newCount = currentCount + 1;
  const newAvg = ((currentAvg * currentCount) + newRating) / newCount;
  return {
    avgRating: Number(newAvg.toFixed(2)),
    reviewCount: newCount
  };
}
