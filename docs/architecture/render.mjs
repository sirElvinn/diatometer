// render.mjs - architecture.html -> docs/images/architecture.png (2x, for Devpost/README)
// needs playwright-core and Google Chrome:  npx -y -p playwright-core node docs/architecture/render.mjs
import { chromium } from 'playwright-core'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 })
await page.goto('file://' + path.join(here, 'architecture.html'), { waitUntil: 'networkidle' })
await page.evaluate(() => document.fonts.ready)
await page.locator('svg').screenshot({ path: path.join(here, '..', 'images', 'architecture.png') })
await browser.close()
console.log('saved docs/images/architecture.png')
