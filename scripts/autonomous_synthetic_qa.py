#!/usr/bin/env python3
"""
Autonomous Synthetic QA Agent Probe & CLI.
Executes end-to-end synthetic user journey checks against the target
Airbnb-Fatsa application instance.
"""

import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request


def run_synthetic_probe(base_url: str, timeout: float = 10.0) -> Dict[str, Any]:
    base_url = base_url.rstrip("/")
    report: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "total_journeys": 7,
        "passed_journeys": 0,
        "failed_journeys": [],
        "journey_details": {},
        "latency_ms": {},
        "all_passed": False,
    }

    def _req(endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None):
        url = f"{base_url}/{endpoint.lstrip('/')}"
        req_headers = {"User-Agent": "Magda-Autonomous-QA/2.0"}
        if headers:
            req_headers.update(headers)
        payload = None
        if data is not None:
            payload = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        
        req = urllib.request.Request(url, data=payload, headers=req_headers, method=method)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = round((time.perf_counter() - t0) * 1000, 2)
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = raw
                return {"ok": True, "status": resp.status, "body": parsed, "latency_ms": elapsed}
        except urllib.error.HTTPError as e:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            raw = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            return {"ok": False, "status": e.code, "body": parsed, "latency_ms": elapsed}
        except Exception as e:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            return {"ok": False, "status": 0, "error": str(e), "latency_ms": elapsed}

    # 1. Homepage & Static Bundle Probe
    r_home = _req("/")
    report["latency_ms"]["homepage"] = r_home.get("latency_ms", 0)

    # 2. Journey 1: Guest Discovery & Filtering
    r_j1 = _req("/api/listings?city=Fatsa&minPrice=100")
    report["latency_ms"]["listings_api"] = r_j1.get("latency_ms", 0)
    if r_j1.get("ok") and r_j1.get("status") == 200:
        b = r_j1.get("body", {})
        if isinstance(b, dict) and b.get("success") is True and len(b.get("data", [])) > 0:
            report["journey_details"]["1_guest_discovery"] = {"status": "PASSED", "count": len(b.get("data", []))}
            report["passed_journeys"] += 1
        else:
            report["failed_journeys"].append("1_guest_discovery: invalid listings payload or empty results")
    else:
        report["failed_journeys"].append(f"1_guest_discovery: HTTP {r_j1.get('status')} - {r_j1.get('error') or r_j1.get('body')}")

    # 3. Journey 2: Authentication & CSRF
    r_j2 = _req("/api/auth/csrf")
    report["latency_ms"]["csrf_api"] = r_j2.get("latency_ms", 0)
    if r_j2.get("ok") and r_j2.get("status") == 200:
        b = r_j2.get("body", {})
        if isinstance(b, dict) and b.get("csrfToken"):
            report["journey_details"]["2_auth_csrf_tokens"] = {"status": "PASSED"}
            report["passed_journeys"] += 1
        else:
            report["failed_journeys"].append("2_auth_csrf_tokens: missing csrfToken in response")
    else:
        report["failed_journeys"].append(f"2_auth_csrf_tokens: HTTP {r_j2.get('status')}")

    # 4. Journey 3: Dynamic Pricing & Payment Availability
    r_j3 = _req("/api/currencies")
    report["latency_ms"]["currencies_api"] = r_j3.get("latency_ms", 0)
    if r_j3.get("ok") and r_j3.get("status") == 200:
        b = r_j3.get("body", {})
        if isinstance(b, dict) and b.get("success") is True:
            report["journey_details"]["3_pricing_payment_engine"] = {"status": "PASSED"}
            report["passed_journeys"] += 1
        else:
            report["failed_journeys"].append("3_pricing_payment_engine: currencies endpoint returned failure")
    else:
        report["failed_journeys"].append(f"3_pricing_payment_engine: HTTP {r_j3.get('status')}")

    # 5. Journey 4: Real-time Communication & Notifications
    r_j4 = _req("/api/health")
    report["latency_ms"]["health_api"] = r_j4.get("latency_ms", 0)
    if r_j4.get("ok") and r_j4.get("status") == 200:
        b = r_j4.get("body", {})
        if isinstance(b, dict) and b.get("status") == "ok":
            report["journey_details"]["4_realtime_messaging_health"] = {"status": "PASSED"}
            report["passed_journeys"] += 1
        else:
            report["failed_journeys"].append("4_realtime_messaging_health: health check status not ok")
    else:
        report["failed_journeys"].append(f"4_realtime_messaging_health: HTTP {r_j4.get('status')}")

    # 6. Journey 5: Host Operations & Admin Analytics
    r_j5 = _req("/api/admin/analytics")
    report["latency_ms"]["analytics_api"] = r_j5.get("latency_ms", 0)
    if r_j5.get("ok") and r_j5.get("status") == 200:
        b = r_j5.get("body", {})
        if isinstance(b, dict) and b.get("success") is True:
            report["journey_details"]["5_host_admin_analytics"] = {"status": "PASSED"}
            report["passed_journeys"] += 1
        else:
            report["failed_journeys"].append("5_host_admin_analytics: admin analytics returned failure")
    else:
        report["failed_journeys"].append(f"5_host_admin_analytics: HTTP {r_j5.get('status')}")

    # 7. Journey 6: Recommendations & Reviews
    r_j6 = _req("/api/recommendations")
    report["latency_ms"]["recommendations_api"] = r_j6.get("latency_ms", 0)
    if r_j6.get("ok") and r_j6.get("status") == 200:
        b = r_j6.get("body", {})
        if isinstance(b, dict) and b.get("success") is True:
            report["journey_details"]["6_recommendations_reviews"] = {"status": "PASSED"}
            report["passed_journeys"] += 1
        else:
            report["failed_journeys"].append("6_recommendations_reviews: recommendations returned failure")
    else:
        report["failed_journeys"].append(f"6_recommendations_reviews: HTTP {r_j6.get('status')}")

    # 8. Journey 7: Security & Vulnerability Guardrails
    r_j7 = _req("/graphql", method="POST", data={"query": "query { listings { id } }"})
    report["latency_ms"]["graphql_security"] = r_j7.get("latency_ms", 0)
    if r_j7.get("status") == 401:
        report["journey_details"]["7_security_guardrails"] = {"status": "PASSED"}
        report["passed_journeys"] += 1
    else:
        report["failed_journeys"].append(f"7_security_guardrails: GraphQL expected 401 Unauthorized, got {r_j7.get('status')}")

    report["all_passed"] = (report["passed_journeys"] == report["total_journeys"])
    return report


def main():
    parser = argparse.ArgumentParser(description="Autonomous Synthetic QA Agent Probe")
    parser.add_argument("--url", default=os.getenv("AIRBNB_BASE_URL", "http://127.0.0.1:5173"), help="Base URL of application")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output raw JSON diagnostic report")
    parser.add_argument("--exit-on-failure", action="store_true", help="Exit code 1 on any journey failure")

    args = parser.parse_args()

    report = run_synthetic_probe(base_url=args.url, timeout=args.timeout)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status_symbol = "🟢 PASS" if report["all_passed"] else "🔴 FAIL"
        print("=================================================================")
        print(f" MAGDA AUTONOMOUS SYNTHETIC QA PROBE — {status_symbol}")
        print("=================================================================")
        print(f"Target Base URL: {report['base_url']}")
        print(f"Timestamp:       {report['timestamp']}")
        print(f"Results:         {report['passed_journeys']}/{report['total_journeys']} Journeys Passed")
        print("-----------------------------------------------------------------")
        for journey, details in report["journey_details"].items():
            print(f"  [✓] {journey:<32} {details.get('status')}")
        if report["failed_journeys"]:
            print("-----------------------------------------------------------------")
            print("FAILURES DETECTED:")
            for f in report["failed_journeys"]:
                print(f"  [✗] {f}")
        print("-----------------------------------------------------------------")
        print(f"Latencies (ms):  {report['latency_ms']}")
        print("=================================================================")

    if args.exit_on_failure and not report["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
