import { describe, it, expect, beforeEach } from "vitest";
import { 
  db, 
  insertGuardianIssue, 
  getAllGuardianIssues, 
  resolveGuardianIssue, 
  clearGuardianIssues 
} from "../src/lib/db.js";
import { 
  runDatabaseHealthAudit, 
  runBusinessLogicAudit, 
  executeFullWatchdogScan, 
  autoHealGuardianIssue, 
  formatGitHubIssueMarkdown 
} from "../src/lib/watchdogEngine.js";

describe("7/24 Autonomous Watchdog & Guardian Engine", () => {
  beforeEach(() => {
    clearGuardianIssues();
  });

  it("runs database health audit without fatal integrity exceptions", () => {
    const issues = runDatabaseHealthAudit();
    expect(Array.isArray(issues)).toBe(true);
    // WAL mode and healthy DB
    const integrityIssues = issues.filter((i) => i.severity === "critical");
    expect(integrityIssues.length).toBe(0);
  });

  it("detects expired active coupons and suspicious logic in business logic audit", () => {
    // Insert an expired active coupon to test detection
    db.prepare(`
      INSERT OR REPLACE INTO coupons (code, discountType, discountValue, minAmount, expiryDate, usageCount, isActive)
      VALUES ('EXPIRED_TEST', 'fixed', 100, 500, '2020-01-01', 0, 1)
    `).run();

    const issues = runBusinessLogicAudit();
    const expiredCouponIssue = issues.find((i) => i.title.includes("Kupon"));
    expect(expiredCouponIssue).toBeDefined();
    expect(expiredCouponIssue.type).toBe("quality");

    // Clean up
    db.prepare("DELETE FROM coupons WHERE code = 'EXPIRED_TEST'").run();
  });

  it("executes full watchdog scan, persists issues and prevents duplicate entries", () => {
    const scan1 = executeFullWatchdogScan();
    expect(scan1).toBeDefined();
    expect(scan1.scanTime).toBeGreaterThan(0);

    const issuesInDb = getAllGuardianIssues();
    expect(issuesInDb.length).toBe(scan1.openIssues.length);

    // Running second scan should not duplicate already open issues
    const scan2 = executeFullWatchdogScan();
    expect(scan2.newIssuesInserted).toBe(0);
  });

  it("auto-heals a detected issue safely and updates status to healed", () => {
    const issue = insertGuardianIssue({
      id: "test_heal_01",
      type: "performance",
      severity: "medium",
      title: "SQLite WAL (Write-Ahead Logging) Modu Kapalı",
      description: "Test WAL issue",
      suggestion: "Enable WAL mode",
      status: "open"
    });

    const result = autoHealGuardianIssue("test_heal_01");
    expect(result.success).toBe(true);
    expect(result.issue.status).toBe("healed");
    expect(result.issue.autoHealed).toBe(1);
    expect(result.actionTaken).toContain("WAL");
  });

  it("formats structured GitHub Issue markdown properly", () => {
    const mockIssue = {
      id: "iss_sample_01",
      type: "performance",
      severity: "high",
      title: "Yavaş SQL Sorgusu",
      description: "Listings sorgusunda indeks eksikliği",
      suggestion: "CREATE INDEX ekleyin",
      status: "open",
      createdAt: 1788010000000
    };

    const markdown = formatGitHubIssueMarkdown(mockIssue);
    expect(markdown).toContain("[AI Guardian]");
    expect(markdown).toContain("Yavaş SQL Sorgusu");
    expect(markdown).toContain("[AÇIK]");
    expect(markdown).toContain("PERFORMANCE");
    expect(markdown).toContain("HIGH");
  });
});
