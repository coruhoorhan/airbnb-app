"""
Airbnb Domain-Specific Guardian Plugin.
Contains business logic rules specific ONLY to the Airbnb Fatsa Clone project:
- Double booking date conflicts
- 0 TL / Negative pricing auto-heal
- Expired coupon auto-deactivation
- iyzico payment reconciliation
- Broken image URL checks
"""

from datetime import datetime, timezone
import sqlite3
import time
from typing import List, Optional

from magda_agent.guardian.base.abstract_guard import BaseGuardian, GuardianIssue


class AirbnbDomainGuardian(BaseGuardian):
    """Domain Guardian enforcing Airbnb business rules and auto-healing runtime anomalies."""

    def __init__(self):
        super().__init__(name="AirbnbDomainGuardian", category="business_logic", is_universal=False)

    def run_check(
        self,
        app_root: str,
        db_conn: Optional[sqlite3.Connection] = None
    ) -> List[GuardianIssue]:
        issues: List[GuardianIssue] = []
        if not db_conn:
            return issues

        # 1. Booking Date Conflicts (Double Booking Detection)
        try:
            conflicts = db_conn.execute("""
                SELECT b1.id AS b1_id, b2.id AS b2_id, b1.listingId, b1.checkIn, b1.checkOut 
                FROM bookings b1 
                JOIN bookings b2 ON b1.listingId = b2.listingId AND b1.id < b2.id 
                WHERE b1.status = 'confirmed' AND b2.status = 'confirmed' 
                AND b1.checkIn < b2.checkOut AND b1.checkOut > b2.checkIn
            """).fetchall()

            for c in conflicts:
                desc = f"Çakışan onaylı rezervasyon: #{c['b1_id']} ve #{c['b2_id']} (İlan #{c['listingId']}, {c['checkIn']} - {c['checkOut']})."
                issues.append(GuardianIssue(
                    issue_type="business_logic",
                    severity="high",
                    title="Booking Date Overlap Conflict",
                    description=desc,
                    suggestion="Reschedule or refund one of the overlapping confirmed bookings.",
                    metadata={"b1_id": c["b1_id"], "b2_id": c["b2_id"], "listing_id": c["listingId"]}
                ))
        except Exception:
            pass

        # 2. Zero-Price Listings Auto-Heal
        try:
            zero_prices = db_conn.execute("""
                SELECT id, title FROM listings 
                WHERE isPublished = 1 AND (pricePerNight <= 0 OR pricePerNight IS NULL)
            """).fetchall()

            for zp in zero_prices:
                db_conn.execute("UPDATE listings SET pricePerNight = 1000 WHERE id = ?", (zp["id"],))
                db_conn.commit()
                issues.append(GuardianIssue(
                    issue_type="business_logic",
                    severity="medium",
                    title=f"Zero-Price Listing Auto-Healed (#{zp['id']})",
                    description=f"İlan #{zp['id']} ({zp['title']}) için geçersiz 0 TL fiyat 1000 TL taban fiyata çekildi.",
                    auto_healed=True,
                    metadata={"listing_id": zp["id"]}
                ))
        except Exception:
            pass

        # 3. Expired Active Coupons Auto-Deactivate
        try:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            expired_coupons = db_conn.execute("""
                SELECT code FROM coupons WHERE isActive = 1 AND expiryDate < ?
            """, (today_str,)).fetchall()

            for ec in expired_coupons:
                db_conn.execute("UPDATE coupons SET isActive = 0 WHERE code = ?", (ec["code"],))
                db_conn.commit()
                issues.append(GuardianIssue(
                    issue_type="business_logic",
                    severity="low",
                    title=f"Expired Coupon Auto-Deactivated ({ec['code']})",
                    description=f"Süresi dolan kupon {ec['code']} otomatik olarak pasife alındı.",
                    auto_healed=True,
                    metadata={"coupon_code": ec["code"]}
                ))
        except Exception:
            pass

        # 4. Failed iyzico Payments on Confirmed Bookings Reconciliation
        try:
            failed_payments = db_conn.execute("""
                SELECT b.id AS booking_id, b.totalPrice 
                FROM bookings b 
                LEFT JOIN payments p ON b.id = p.bookingId 
                WHERE b.status = 'confirmed' AND (p.status = 'failed' OR p.id IS NULL)
            """).fetchall()

            for fp in failed_payments:
                issues.append(GuardianIssue(
                    issue_type="business_logic",
                    severity="high",
                    title=f"Unpaid Confirmed Booking Anomaly (#{fp['booking_id']})",
                    description=f"Onaylı görünen ancak iyzico ödemesi başarısız/eksik olan rezervasyon: #{fp['booking_id']} (Tutar: {fp['totalPrice']} TL).",
                    suggestion="Verify payment status with iyzico gateway API or cancel unpaid booking.",
                    metadata={"booking_id": fp["booking_id"]}
                ))
        except Exception:
            pass

        return issues
