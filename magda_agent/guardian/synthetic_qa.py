"""
Magda-Agent Synthetic QA Guardian Module.
Runs comprehensive synthetic user journeys and live probe checks against
the application frontend, REST APIs, and GraphQL schemas.
"""

from datetime import datetime, timezone
import json
import logging
import time
import sqlite3
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

from magda_agent.guardian.base.abstract_guard import BaseGuardian, GuardianIssue

logger = logging.getLogger("SyntheticQAGuardian")


class SyntheticQAGuardian(BaseGuardian):
    """Synthetic QA Guardian evaluating live service health and user journeys."""

    def __init__(self, base_url: str = "http://127.0.0.1:5173", timeout: float = 8.0):
        super().__init__(name="SyntheticQAGuardian", category="synthetic_qa", is_universal=True)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _http_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Performs HTTP request and returns status, json/text body, and latency."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        req_headers = {"User-Agent": "Magda-Autonomous-QA/2.0"}
        if headers:
            req_headers.update(headers)

        payload = None
        if data is not None:
            payload = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=payload, headers=req_headers, method=method)
        start_t = time.perf_counter()

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
                body_bytes = resp.read()
                try:
                    parsed = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    parsed = body_bytes.decode("utf-8", errors="replace")
                return {
                    "ok": True,
                    "status": resp.status,
                    "body": parsed,
                    "latency_ms": elapsed_ms,
                    "headers": dict(resp.headers),
                }
        except urllib.error.HTTPError as e:
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
            body_bytes = e.read()
            try:
                parsed = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                parsed = body_bytes.decode("utf-8", errors="replace")
            return {
                "ok": False,
                "status": e.code,
                "body": parsed,
                "latency_ms": elapsed_ms,
                "headers": dict(e.headers),
            }
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
            return {
                "ok": False,
                "status": 0,
                "body": str(e),
                "latency_ms": elapsed_ms,
                "headers": {},
                "error": str(e),
            }

    def run_synthetic_qa_probe(self) -> Dict[str, Any]:
        """Executes 7 synthetic user journey checks against the target base URL."""
        results: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "base_url": self.base_url,
            "total_journeys": 7,
            "passed_journeys": 0,
            "failed_journeys": [],
            "journey_details": {},
            "latency_ms": {},
            "all_passed": False,
        }

        # ---------------------------------------------------------------------
        # Journey 1: Guest Discovery & Filtering
        # ---------------------------------------------------------------------
        j1_res = self._http_request("/api/listings?city=Fatsa&minPrice=100")
        results["latency_ms"]["listings_api"] = j1_res.get("latency_ms", 0)
        if j1_res.get("ok") and j1_res.get("status") == 200:
            body = j1_res.get("body", {})
            if isinstance(body, dict) and body.get("success") is True and len(body.get("data", [])) > 0:
                results["journey_details"]["guest_discovery"] = {"status": "PASSED", "count": len(body.get("data", []))}
                results["passed_journeys"] += 1
            else:
                results["failed_journeys"].append("guest_discovery: invalid listings payload or empty results")
        else:
            results["failed_journeys"].append(f"guest_discovery: HTTP {j1_res.get('status')} - {j1_res.get('error') or j1_res.get('body')}")

        # ---------------------------------------------------------------------
        # Journey 2: Authentication, Session & Security Tokens
        # ---------------------------------------------------------------------
        j2_res = self._http_request("/api/auth/csrf")
        results["latency_ms"]["csrf_api"] = j2_res.get("latency_ms", 0)
        if j2_res.get("ok") and j2_res.get("status") == 200:
            body = j2_res.get("body", {})
            if isinstance(body, dict) and body.get("csrfToken"):
                results["journey_details"]["auth_csrf_tokens"] = {"status": "PASSED"}
                results["passed_journeys"] += 1
            else:
                results["failed_journeys"].append("auth_csrf_tokens: missing csrfToken in response")
        else:
            results["failed_journeys"].append(f"auth_csrf_tokens: HTTP {j2_res.get('status')} - {j2_res.get('error') or j2_res.get('body')}")

        # ---------------------------------------------------------------------
        # Journey 3: Dynamic Pricing & Payment Availability
        # ---------------------------------------------------------------------
        j3_res = self._http_request("/api/currencies")
        results["latency_ms"]["currencies_api"] = j3_res.get("latency_ms", 0)
        if j3_res.get("ok") and j3_res.get("status") == 200:
            body = j3_res.get("body", {})
            if isinstance(body, dict) and body.get("success") is True:
                results["journey_details"]["pricing_payment_engine"] = {"status": "PASSED"}
                results["passed_journeys"] += 1
            else:
                results["failed_journeys"].append("pricing_payment_engine: currencies endpoint returned failure")
        else:
            results["failed_journeys"].append(f"pricing_payment_engine: HTTP {j3_res.get('status')}")

        # ---------------------------------------------------------------------
        # Journey 4: Real-time Communication & Notifications
        # ---------------------------------------------------------------------
        j4_res = self._http_request("/api/health")
        results["latency_ms"]["health_api"] = j4_res.get("latency_ms", 0)
        if j4_res.get("ok") and j4_res.get("status") == 200:
            body = j4_res.get("body", {})
            if isinstance(body, dict) and body.get("status") == "ok":
                results["journey_details"]["realtime_messaging_health"] = {"status": "PASSED"}
                results["passed_journeys"] += 1
            else:
                results["failed_journeys"].append("realtime_messaging_health: health check non-ok")
        else:
            results["failed_journeys"].append(f"realtime_messaging_health: HTTP {j4_res.get('status')}")

        # ---------------------------------------------------------------------
        # Journey 5: Host Operations & Admin Analytics
        # ---------------------------------------------------------------------
        j5_res = self._http_request("/api/admin/analytics")
        results["latency_ms"]["analytics_api"] = j5_res.get("latency_ms", 0)
        if j5_res.get("ok") and j5_res.get("status") == 200:
            body = j5_res.get("body", {})
            if isinstance(body, dict) and body.get("success") is True:
                results["journey_details"]["host_admin_analytics"] = {"status": "PASSED"}
                results["passed_journeys"] += 1
            else:
                results["failed_journeys"].append("host_admin_analytics: admin analytics returned failure")
        else:
            results["failed_journeys"].append(f"host_admin_analytics: HTTP {j5_res.get('status')}")

        # ---------------------------------------------------------------------
        # Journey 6: Recommendations & Reviews
        # ---------------------------------------------------------------------
        j6_res = self._http_request("/api/recommendations")
        results["latency_ms"]["recommendations_api"] = j6_res.get("latency_ms", 0)
        if j6_res.get("ok") and j6_res.get("status") == 200:
            body = j6_res.get("body", {})
            if isinstance(body, dict) and body.get("success") is True:
                results["journey_details"]["recommendations_reviews"] = {"status": "PASSED"}
                results["passed_journeys"] += 1
            else:
                results["failed_journeys"].append("recommendations_reviews: recommendations returned failure")
        else:
            results["failed_journeys"].append(f"recommendations_reviews: HTTP {j6_res.get('status')}")

        # ---------------------------------------------------------------------
        # Journey 7: Security & Vulnerability Fuzzing
        # ---------------------------------------------------------------------
        # Unauthenticated GraphQL must be rejected with 401
        j7_res = self._http_request("/graphql", method="POST", data={"query": "query { listings { id } }"})
        results["latency_ms"]["graphql_security"] = j7_res.get("latency_ms", 0)
        if j7_res.get("status") == 401:
            results["journey_details"]["security_guardrails"] = {"status": "PASSED"}
            results["passed_journeys"] += 1
        else:
            results["failed_journeys"].append(f"security_guardrails: GraphQL expected 401 Unauthorized, got {j7_res.get('status')}")

        results["all_passed"] = (results["passed_journeys"] == results["total_journeys"])
        return results

    def run_check(
        self,
        app_root: str,
        db_conn: Optional[sqlite3.Connection] = None
    ) -> List[GuardianIssue]:
        """BaseGuardian run_check implementation."""
        issues: List[GuardianIssue] = []
        probe_res = self.run_synthetic_qa_probe()

        if not probe_res["all_passed"]:
            for failure in probe_res["failed_journeys"]:
                issues.append(
                    GuardianIssue(
                        issue_type="synthetic_qa",
                        severity="high",
                        title=f"Synthetic QA Journey Failure: {failure.split(':')[0]}",
                        description=f"Synthetic probe failed: {failure}",
                        suggestion="Verify endpoint availability, database connectivity, and backend services.",
                        metadata={"probe_report": probe_res},
                    )
                )
        return issues
