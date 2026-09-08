const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://localhost:5173');
  await page.waitForTimeout(3000); // give app time to load
  await page.screenshot({ path: 'frontend-verification.png' });
  await browser.close();
})();
