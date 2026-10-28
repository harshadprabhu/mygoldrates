const { chromium } = require('playwright');
const fs = require('fs');
const VO = JSON.parse(fs.readFileSync('vo.json', 'utf8')); const SUB = Object.fromEntries(JSON.parse(fs.readFileSync('lines.json', 'utf8')).map(l => [l.id, l.sub]));
const HIDE = "#liveChip,.live-chip,.sn-fab,#sonaFab,#sonaBanner,.sn-ban,#subPop,.adsbygoogle,ins.adsbygoogle,.sn-fb{display:none!important}html{scroll-behavior:auto!important}.sn-typing span{animation:none!important}.sn-body{scroll-behavior:auto!important}";
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await ctx.addInitScript(() => { if (window.top !== window) { try { localStorage.setItem('gr_sub','1'); localStorage.setItem('sona_ban2','1'); localStorage.setItem('sona_ban','1'); localStorage.setItem('sona_lang','en'); } catch (e) {} } });
  await ctx.route('**/*', r => { const u = r.request().url(); (u.startsWith('http://127.0.0.1') || /fonts\.(googleapis|gstatic)\.com/.test(u)) ? r.continue() : r.abort(); });
  const p = await ctx.newPage();
  await p.goto('http://127.0.0.1:8765/__v/wrap.html', { waitUntil: 'load' });
  await p.waitForTimeout(2500);
  const f = p.frame({ url: /\/\?v=1/ });
  await f.addStyleTag({ content: HIDE });
  const frames = []; let n = 0; let s0 = 0; const marks = [];
  const start = (id) => { s0 = frames.length; marks.push([id, frames.reduce((a, x) => a + x[1], 0)]); };
  const end = (id) => { const have = frames.slice(s0).reduce((a, x) => a + x[1], 0), need = VO[id] + 0.35; if (have < need) frames[frames.length - 1][1] += need - have; };
  const shot = async (dur) => { const fn = `f${String(n++).padStart(3, '0')}.png`; await p.screenshot({ path: 'frames/' + fn }); frames.push([fn, dur]); };
  const scene = (s, cap) => p.evaluate(([s, c]) => window.setScene(s, c), [s, cap]);
  const body = () => f.evaluate(() => { const b = document.querySelector('#sonaPanel .sn-body'); return [b.scrollTop, b.scrollHeight - b.clientHeight]; });
  const scrollTo = (y) => f.evaluate(y => { document.querySelector('#sonaPanel .sn-body').scrollTop = y; }, y);
  const lastQTop = () => f.evaluate(() => { const ms = document.querySelectorAll('#sonaPanel .sn-body > .sn-m.me, #sonaPanel .sn-body > .sn-m.you, #sonaPanel .sn-body > .sn-m:not(.bot)'); const m = ms[ms.length - 1]; return m ? m.offsetTop - 8 : 0; });
  async function typeAsk(q, typeDur) {
    const steps = Math.ceil(q.length / 2);
    for (let i = 1; i <= steps; i++) { await f.evaluate(v => { document.getElementById('sonaInput').value = v; }, q.slice(0, i * 2)); await shot(typeDur / steps); }
    await f.evaluate(q => window.GR_ASK(q), q);
    await p.waitForTimeout(120); await scrollTo(await lastQTop()); await shot(0.35);           // question sent, Sona typing
    await f.waitForFunction(() => !document.querySelector('#sonaPanel .sn-typing'), null, { timeout: 8000 });
    await p.waitForTimeout(200);
  }
  async function reveal(hold, scrollDur, endHold, maxScroll) {
    const top = await lastQTop(); await scrollTo(top); await shot(hold);
    const [, mx] = await body(); const end = Math.min(mx, top + (maxScroll || 9999));
    const k = 8;
    for (let i = 1; i <= k; i++) { const e = i / k, y = top + (end - top) * (e < .5 ? 2 * e * e : 1 - Math.pow(-2 * e + 2, 2) / 2); await scrollTo(y); await shot(scrollDur / k); }
    await shot(endHold);
  }
  fs.mkdirSync('frames', { recursive: true });
  start('l1'); await scene('intro', ''); await shot(1.2); end('l1');
  start('l2'); await scene('', SUB.l2);
  await f.evaluate(() => window.GR_ASK()); await p.waitForTimeout(700); await f.addStyleTag({ content: HIDE }); await shot(0.35);
  await typeAsk('Best offer today', 0.55);
  await reveal(0.75, 0.01, 0.01); end('l2');
  start('l3'); await scene('', SUB.l3);
  await f.locator('#sonaPanel .sn-chip', { hasText: 'Bangle' }).first().click();
  await p.waitForTimeout(150); await scrollTo(await lastQTop()); await shot(0.3);
  await f.waitForFunction(() => !document.querySelector('#sonaPanel .sn-typing'), null, { timeout: 8000 }); await p.waitForTimeout(200);
  await reveal(1.0, 1.3, 0.4, 520); end('l3');
  start('l4'); await scene('', SUB.l4);
  await typeAsk('best offer on a ring', 0.55);
  await reveal(0.9, 1.0, 0.3, 420); end('l4');
  start('l5'); await scene('', SUB.l5);
  await typeAsk('tanishq making charges', 0.55);
  await reveal(1.2, 0.01, 0.01); end('l5');
  start('l6'); await scene('outro', SUB.l6); await shot(2.0); end('l6');
  fs.writeFileSync('frames/list.json', JSON.stringify(frames)); fs.writeFileSync('frames/marks.json', JSON.stringify(marks));
  console.log('frames', frames.length, 'seconds', frames.reduce((a, x) => a + x[1], 0).toFixed(2));
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
