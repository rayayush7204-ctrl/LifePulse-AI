/**
 * Responsive UI Verification Script
 * 
 * Uses Playwright to programmatically capture screenshots of the frontend at various 
 * common viewports (Mobile, Tablet, Desktop) and check for horizontal overflow issues.
 * 
 * PREREQUISITES:
 * 1. Playwright must be installed in package.json devDependencies
 *    Run: npm install -D playwright playwright-core
 *    Run: npx playwright install chromium
 * 2. The local dev server must be running (npm run dev) on http://localhost:3000
 * 
 * USAGE:
 * node scripts/test-responsive.cjs
 * 
 * NOTE: Generated screenshots are saved in frontend/scripts/screenshots/ 
 *       and are ignored by git (.gitignore).
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function takeScreenshots() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  const viewports = [
    { name: 'iPhone_SE', width: 320, height: 568 },
    { name: 'iPhone_8', width: 375, height: 667 },
    { name: 'iPhone_X', width: 375, height: 812 },
    { name: 'iPhone_14', width: 390, height: 844 },
    { name: 'iPhone_14_Pro_Max', width: 430, height: 932 },
    { name: 'iPad', width: 768, height: 1024 },
    { name: 'Desktop', width: 1440, height: 900 }
  ];

  const outDir = path.join(__dirname, 'screenshots');
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir);
  }

  // Go to the emergency request page
  await page.goto('http://localhost:3000/request', { waitUntil: 'networkidle' });
  
  // Wait a bit for map to render
  await page.waitForTimeout(2000);

  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.waitForTimeout(500); // allow layout to settle
    
    // Check for horizontal overflow
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    const hasHorizontalOverflow = bodyWidth > vp.width;
    
    const screenshotPath = path.join(outDir, `${vp.name}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    
    console.log(`Viewport: ${vp.name} (${vp.width}x${vp.height}) - Horizontal Overflow: ${hasHorizontalOverflow}`);
  }

  await browser.close();
}

takeScreenshots().catch(console.error);
