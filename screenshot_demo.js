
const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:5001';
const OUTPUT_DIR = path.join(__dirname, 'docs', 'screenshots');

const VIEWS = [
    ['01-dashboard',     '/',              { waitFor: '.stat-number, .focus-card, [class*="widget"]', delay: 1500 }],
    ['02-pipeline',      '/pipeline',      { waitFor: '.pipeline, .kanban, [class*="stage"]', delay: 1000 }],
    ['03-kontakte',      '/contacts',      { waitFor: 'table, .contact-list', delay: 800 }],
    ['04-kontakt-detail', null,            { special: 'first-contact', delay: 800 }],
    ['05-board',         '/board',         { waitFor: '.board, .kanban, [class*="column"]', delay: 1000 }],
    ['06-dokumente',     '/documents',     { waitFor: 'table, .document-list', delay: 800 }],
    ['07-zeiterfassung', '/timetracking',  { waitFor: 'table, .time-entries', delay: 800 }],
    ['08-analytics',     '/analytics',     { waitFor: 'canvas, .chart, svg, [class*="analytics"]', delay: 1500 }],
    ['09-angebot-detail', null,            { special: 'first-quote', delay: 800 }],
    ['10-rechnung-detail', null,           { special: 'first-invoice', delay: 800 }],
    ['11-services',      '/templates',     { waitFor: 'table, .service-list', delay: 800 }],
    ['12-settings',      '/settings/followup', { delay: 800 }],
];

async function findFirstLink(page, urlPattern) {
    const links = await page.$$eval('a[href]', (els) => els.map(e => e.href));
    return links.find(l => l.match(urlPattern));
}

async function run() {
    if (!fs.existsSync(OUTPUT_DIR)) {
        fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    }

    console.log(`\nStellwerk Demo Screenshots`);
    console.log(`Output: ${OUTPUT_DIR}\n`);

    const browser = await puppeteer.launch({
        headless: 'new',
        defaultViewport: { width: 1440, height: 900 },
        args: ['--no-sandbox'],
    });

    const page = await browser.newPage();

    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0');

    for (const [filename, urlPath, options] of VIEWS) {
        try {
            let url;

            if (options.special === 'first-contact') {
                await page.goto(`${BASE_URL}/contacts`, { waitUntil: 'networkidle2', timeout: 15000 });
                await page.waitForSelector('a[href*="/contacts/"]', { timeout: 5000 });
                const contactLink = await page.$eval(
                    'a[href*="/contacts/"]',
                    el => el.href
                );
                url = contactLink;
            } else if (options.special === 'first-quote') {
                await page.goto(`${BASE_URL}/documents?type=quote`, { waitUntil: 'networkidle2', timeout: 15000 });
                await page.waitForSelector('a[href*="/documents/"]', { timeout: 5000 });
                const docLink = await page.$eval(
                    'a[href*="/documents/"]',
                    el => el.href
                );
                url = docLink;
            } else if (options.special === 'first-invoice') {
                await page.goto(`${BASE_URL}/documents?type=invoice`, { waitUntil: 'networkidle2', timeout: 15000 });
                await page.waitForSelector('a[href*="/documents/"]', { timeout: 5000 });
                const docLink = await page.$eval(
                    'a[href*="/documents/"]',
                    el => el.href
                );
                url = docLink;
            } else {
                url = `${BASE_URL}${urlPath}`;
            }

            await page.goto(url, { waitUntil: 'networkidle2', timeout: 15000 });

            if (options.waitFor) {
                try {
                    await page.waitForSelector(options.waitFor, { timeout: 5000 });
                } catch (e) {
                }
            }

            if (options.delay) {
                await new Promise(r => setTimeout(r, options.delay));
            }

            const outputPath = path.join(OUTPUT_DIR, `${filename}.png`);
            await page.screenshot({ path: outputPath, fullPage: false });
            console.log(`  OK  ${filename}.png`);

        } catch (err) {
            console.log(`  ERR ${filename}: ${err.message}`);
        }
    }

    const fullPageViews = [
        ['full-dashboard', '/'],
        ['full-board', '/board'],
        ['full-analytics', '/analytics'],
    ];

    console.log(`\nFull-page screenshots:`);
    for (const [filename, urlPath] of fullPageViews) {
        try {
            await page.goto(`${BASE_URL}${urlPath}`, { waitUntil: 'networkidle2', timeout: 15000 });
            await new Promise(r => setTimeout(r, 1500));
            const outputPath = path.join(OUTPUT_DIR, `${filename}.png`);
            await page.screenshot({ path: outputPath, fullPage: true });
            console.log(`  OK  ${filename}.png`);
        } catch (err) {
            console.log(`  ERR ${filename}: ${err.message}`);
        }
    }

    await browser.close();
    console.log(`\nFertig! ${VIEWS.length + fullPageViews.length} Screenshots in ${OUTPUT_DIR}\n`);
}

run().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
});
