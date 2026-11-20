"""Functional and layout tests for Town Mart Inventory.

Usage (from the repository root):
    pip install playwright && python -m playwright install chromium
    python tests/test_app.py app/src/main/assets/index.html [screenshot-folder]
"""
import sys, os, json
from playwright.sync_api import sync_playwright

PAGE = 'file://' + os.path.abspath(sys.argv[1])
OUT = sys.argv[2] if len(sys.argv) > 2 else 'test-screenshots'
os.makedirs(OUT, exist_ok=True)

# Finds overlapping text/controls, spilled content, page overflow, see-through sheet, content hidden by bottom nav.
LAYOUT_JS = r"""() => {
  const probs = [];
  const de = document.documentElement;
  if (de.scrollWidth > de.clientWidth + 1) probs.push('page wider than screen: ' + de.scrollWidth + ' > ' + de.clientWidth);
  const ov = document.getElementById('ov'), sheetOpen = !ov.hidden;
  const root = sheetOpen ? document.getElementById('sheet') : document.querySelector('.app');
  if (sheetOpen) {
    const bg = getComputedStyle(root).backgroundColor;
    if (!/^rgb\(/.test(bg)) probs.push('sheet background not solid: ' + bg);
    const r = root.getBoundingClientRect();
    if (r.top < 0) probs.push('sheet taller than screen top');
  }
  const vis = el => { const s = getComputedStyle(el); if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  // boxes: each text line (range rects) + each form control
  const boxes = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    if (!n.nodeValue.trim()) continue;
    const el = n.parentElement; if (!el || !vis(el) || el.closest('option,datalist,script,style')) continue;
    const rg = document.createRange(); rg.selectNodeContents(n);
    for (const r of rg.getClientRects()) if (r.width > 1 && r.height > 1) boxes.push({el, r, what: '"' + n.nodeValue.trim().slice(0, 28) + '"'});
  }
  root.querySelectorAll('input:not([type=hidden]),select,textarea,svg').forEach(el => { if (vis(el)) boxes.push({el, r: el.getBoundingClientRect(), what: '<' + el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + '>'}); });
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const a = boxes[i], b = boxes[j];
    if (a.el === b.el || a.el.contains(b.el) || b.el.contains(a.el)) continue;
    const w = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
    const h = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
    if (w > 1.5 && h > 1.5) probs.push('overlap ' + a.what + ' x ' + b.what);
  }
  // spilled content: element wider than its box (ignores scrollable containers)
  root.querySelectorAll('*').forEach(el => {
    if (!vis(el) || el.tagName === 'svg' || el.closest('svg') || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
    const s = getComputedStyle(el);
    if (/(auto|scroll|hidden)/.test(s.overflowX)) return;
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) probs.push('spills: <' + el.tagName.toLowerCase() + ' class=' + el.className + '> ' + (el.textContent || '').trim().slice(0, 30) + ' (' + el.scrollWidth + '>' + el.clientWidth + ')');
    const r = el.getBoundingClientRect();
    if (r.right > innerWidth + 1 && s.position !== 'fixed') probs.push('off right edge: <' + el.tagName.toLowerCase() + ' class=' + el.className + '> ' + (el.textContent || '').trim().slice(0, 30));
  });
  // bottom nav must not hide the end of the page
  if (!sheetOpen) {
    const nav = document.querySelector('nav').getBoundingClientRect();
    window.scrollTo(0, de.scrollHeight);
    const items = [...document.querySelectorAll('main *')].filter(vis);
    const last = items.reduce((m, el) => Math.max(m, el.getBoundingClientRect().bottom), 0);
    if (last > document.querySelector('nav').getBoundingClientRect().top + 1) probs.push('content hidden behind bottom bar: ' + Math.round(last) + ' > ' + Math.round(nav.top));
    window.scrollTo(0, 0);
  }
  return [...new Set(probs)];
}"""

results = {'layout': [], 'func': [], 'errors': []}
def check(pg, name, w):
    pg.wait_for_timeout(120)
    probs = pg.evaluate(LAYOUT_JS)
    results['layout'].append((w, name, probs))
    return probs

def expect(cond, msg):
    results['func'].append(('PASS' if cond else 'FAIL', msg))

with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (320, 360, 412, 600):
        ctx = b.new_context(viewport={'width': w, 'height': 760}, device_scale_factor=2)
        pg = ctx.new_page()
        pg.on('pageerror', lambda e: results['errors'].append(str(e)))
        pg.goto(PAGE); pg.evaluate('localStorage.clear()'); pg.reload(); pg.wait_for_timeout(200)
        fn = w == 360  # run functional assertions once, at 360
        check(pg, 'home-empty', w)
        pg.click('nav button[data-t=items]'); check(pg, 'items-empty', w)
        pg.click('nav button[data-t=reports]'); check(pg, 'reports-empty', w)
        pg.click('nav button[data-t=settings]'); check(pg, 'settings', w)
        # add a long-named item with starting stock
        pg.click('nav button[data-t=items]'); pg.click('[data-a=newItem]'); check(pg, 'item-form-add', w)
        pg.click('form[data-f=item] button.pri'); pg.wait_for_timeout(100)
        if fn: expect('Enter the item name' in pg.inner_text('.sheet .err'), 'blank name is rejected')
        pg.fill('#fn', 'Extra long product name to test wrapping on very narrow phones, 1.5L family size bottle')
        pg.click('[data-a=pickSec][data-s=coffee]')
        if fn:
            opts = pg.locator('#fcs option').all_inner_texts()
            expect('Syrups and sauces' in opts and 'Beverages' not in opts and opts[-1].startswith('+ New category'), 'category dropdown switches to coffee shop categories (%d options)' % len(opts))
            pg.select_option('#fcs', '__new'); pg.wait_for_timeout(50)
            expect(pg.locator('#fcn').is_visible(), 'choosing + New category shows a text box')
        pg.select_option('#fcs', 'Syrups and sauces'); pg.select_option('#fu', 'bottle')
        pg.fill('#fr', '5'); pg.fill('#fq', '10'); pg.fill('#fco', '1234.5'); pg.fill('#fsu', 'Café supply store in Davao City, Matina branch')
        pg.fill('#fe', __import__('datetime').date.fromordinal(__import__('datetime').date.today().toordinal() + 3).isoformat())
        check(pg, 'item-form-filled', w)
        pg.click('form[data-f=item] button.pri'); pg.wait_for_timeout(150); check(pg, 'item-detail', w)
        if fn:
            expect(pg.inner_text('.sheet .bigq').startswith('10'), 'new item starts at 10')
            expect('Expires in 3 days' in pg.inner_text('.sheet'), 'expiry tag shows 3 days')
            expect('Starting stock' in pg.inner_text('.sheet .hist'), 'starting stock is in the stock card')
        # stock out 3
        pg.click('.sheet [data-a=move][data-m=out]'); check(pg, 'move-out', w)
        pg.fill('#mq', '3'); pg.wait_for_timeout(50)
        if fn: expect('Stock will be 7' in pg.inner_text('#mprev'), 'out preview shows 7')
        pg.select_option('#mr', 'Spoiled or expired'); pg.fill('#mby', 'Angel'); pg.fill('#mn', 'Leaking bottle')
        pg.click('form[data-f=move] button.pri'); pg.wait_for_timeout(150)
        if fn: expect(pg.inner_text('.sheet .bigq').startswith('7'), 'after out 3 → 7')
        # out more than stock
        pg.click('.sheet [data-a=move][data-m=out]'); pg.fill('#mq', '20'); pg.click('form[data-f=move] button.pri'); pg.wait_for_timeout(100)
        check(pg, 'move-error', w)
        if fn: expect('Only 7' in pg.inner_text('.sheet .err'), 'cannot take out more than stock')
        # switch to count → 5
        pg.click('[data-a=mtype][data-m=count]'); check(pg, 'move-count', w)
        pg.fill('#mq', '5'); pg.wait_for_timeout(50)
        if fn: expect('−2 difference' in pg.inner_text('#mprev'), 'count preview shows −2')
        pg.click('form[data-f=move] button.pri'); pg.wait_for_timeout(150)
        if fn: expect(pg.inner_text('.sheet .bigq').startswith('5'), 'after count → 5') ; expect('Low stock' in pg.inner_text('.sheet'), 'at reorder level shows Low stock')
        # stock in 4 at new cost 1300
        pg.click('.sheet [data-a=move][data-m=in]'); check(pg, 'move-in', w)
        pg.fill('#mq', '4'); pg.fill('#mc', '1300'); pg.click('form[data-f=move] button.pri'); pg.wait_for_timeout(150)
        if fn:
            expect(pg.inner_text('.sheet .bigq').startswith('9'), 'after in 4 → 9')
            expect('₱1,300' in pg.inner_text('.sheet .facts'), 'cost updated to ₱1,300')
            expect('₱11,700' in pg.inner_text('.sheet .facts'), 'stock value 9 × 1,300 = ₱11,700')
            expect(pg.locator('.sheet .hist li').count() == 4, 'stock card has 4 entries')
        check(pg, 'item-detail-history', w)
        pg.click('.sheet [data-a=editItem]'); check(pg, 'item-form-edit', w)
        if fn:
            expect(pg.eval_on_selector('#fcs', 'e => e.value') == 'Syrups and sauces', 'edit form shows the saved category')
            pg.select_option('#fcs', '__new'); check(pg, 'item-form-newcat', w); pg.click('form[data-f=item] button.pri'); pg.wait_for_timeout(80)
            expect('Type the name of the new category' in pg.inner_text('.sheet .err'), 'empty new category is refused')
            pg.fill('#fcn', 'Imported syrups'); pg.click('form[data-f=item] button.pri'); pg.wait_for_timeout(150)
            expect('Imported syrups' in pg.inner_text('.sheet .facts'), 'new category saved on the item')
            pg.click('.sheet [data-a=editItem]')
            expect(pg.eval_on_selector('#fcs', 'e => e.value') == 'Imported syrups', 'new category appears in the dropdown next time')
        pg.click('[data-a=close]')
        # load sample data
        pg.click('nav button[data-t=settings]'); pg.click('[data-a=sampleAsk]'); check(pg, 'confirm-sample', w)
        pg.click('[data-a=doSample]'); pg.wait_for_timeout(150)
        pg.click('nav button[data-t=home]'); check(pg, 'home-all', w)
        if fn:
            stats = pg.locator('.stat .n').all_inner_texts()
            expect(stats == ['12', '3', '1', '2'], 'sample stats: 12 items, 3 low (water, caramel, lids), 1 out (corned beef), 2 expiring (bread, milk) (got %s)' % stats)
        pg.click('[data-a=section][data-s=coffee]'); check(pg, 'home-coffee', w)
        if fn: expect(pg.locator('.stat .n').first.inner_text() == '6', 'coffee section has 6 items')
        pg.click('[data-a=section][data-s=mart]'); check(pg, 'home-mart', w)
        pg.click('[data-a=section][data-s=all]')
        pg.click('[data-a=goFilter][data-f=low]'); check(pg, 'items-low', w)
        if fn: expect(pg.locator('#list .row').count() == 3, 'low filter lists 3 items')
        pg.click('[data-a=filter][data-f=all]'); check(pg, 'items-all', w)
        pg.fill('#q', 'cup'); pg.wait_for_timeout(50)
        if fn: expect(pg.locator('#list .row').count() == 2, 'search "cup" finds 2 (cups, lids)')
        pg.fill('#q', ''); pg.select_option('#cat', 'Beverages'); pg.wait_for_timeout(50)
        if fn: expect(pg.locator('#list .row').count() == 2, 'Beverages category has 2')
        pg.select_option('#cat', '')
        pg.click('nav button[data-t=home]'); pg.click('[data-a=quickMove][data-m=in]'); check(pg, 'pick-item', w)
        pg.fill('#pq', 'milk'); pg.wait_for_timeout(50)
        if fn: expect(pg.locator('#plist .row').count() == 1, 'picker search finds Fresh milk')
        pg.click('#plist .row'); pg.fill('#mq', '2.5'); pg.click('form[data-f=move] button.pri'); pg.wait_for_timeout(150)
        if fn: expect(pg.inner_text('.sheet .bigq').startswith('8.5'), 'fresh milk 6 + 2.5 = 8.5 (decimals)')
        pg.click('[data-a=close]')
        # reports
        pg.click('nav button[data-t=reports]'); check(pg, 'reports-levels', w)
        for v in ('moves', 'profit', 'low', 'value'):
            pg.click('[data-a=rview][data-v=%s]' % v); check(pg, 'reports-' + v, w)
        pg.click('[data-a=rview][data-v=profit]'); check(pg, 'reports-profit', w)
        pg.click('[data-a=period][data-p="30"]'); check(pg, 'reports-value-30', w)
        if fn:
            sales = pg.inner_text('.rep div:nth-child(5) .v'); prof = pg.inner_text('.rep div:nth-child(6) .v')
            expect(sales == '₱1,437' and prof == '₱270.50', 'sample sales ₱1,437 and profit ₱270.50 (Coke 10×12 + water 6×6 + canton 3×3.5 + corned beef 10×8 + soap 3×8) got %s / %s' % (sales, prof))
            pg.click('nav button[data-t=items]'); pg.locator('#list .row', has_text='Coca-Cola').click()
            pg.click('.sheet [data-a=move][data-m=out]'); pg.fill('#mq', '2'); pg.click('form[data-f=move] button.pri'); pg.wait_for_timeout(150); pg.click('[data-a=close]')
            pg.click('nav button[data-t=reports]'); pg.click('[data-a=period][data-p="30"]')
            expect(pg.inner_text('.rep div:nth-child(6) .v') == '₱294.50', 'selling 2 more Coke adds 2 × ₱12 → ₱294.50')
            pg.click('[data-a=rview][data-v=profit]'); first = pg.locator('.rlist li').first.inner_text()
            expect('Coca-Cola' in first and '₱144' in first, 'profit view lists Coca-Cola first with ₱144')
            csvp = pg.evaluate("() => { let t=''; window.Android={share:(x)=>{t=x}}; document.querySelector('[data-a=shareCsv]').click(); delete window.Android; return t }")
            expect(csvp.split('\n')[0] == 'Item,Section,Quantity sold,Unit,Sales,Estimated profit' and csvp.strip().split('\n')[-1] == 'Total,,,,1597,294.5', 'profit CSV header and total row (got %s)' % csvp.strip().split('\n')[-1])
            pg.click('[data-a=rview][data-v=value]')
        pg.click('[data-a=rview][data-v=moves]'); check(pg, 'reports-moves-30', w)
        if fn:
            txt = pg.inner_text('main')
            expect('Fresh milk' in txt and '+14.5' in txt, 'movements report: fresh milk in = 12 opening + 2.5 = +14.5')
            loss = pg.inner_text('.rep div:nth-child(3) .v')
            expect(loss == '₱312', 'losses = spoiled sliced bread 6 × ₱52 = ₱312 (got %s)' % loss)
            csv = pg.evaluate("() => { let t=''; window.Android={share:(x)=>{t=x}}; document.querySelector('[data-a=shareCsv]').click(); delete window.Android; return t }")
            lines = csv.split('\n')
            expect(lines[0].startswith('Date,Time,Item,Section,Type'), 'movement CSV has header')
            expect(any('Fresh milk' in l and 'Stock in' in l for l in lines), 'CSV has the fresh milk stock-in row')
            pg.click('[data-a=rview][data-v=levels]')
            csv2 = pg.evaluate("() => { let t=''; window.Android={share:(x)=>{t=x}}; document.querySelector('[data-a=shareCsv]').click(); delete window.Android; return t }")
            expect(csv2.split('\n')[0].startswith('Item,Section,Category,On hand') and len(csv2.split('\n')) == 13, 'stock levels CSV has header + 12 rows')
            expect('"Café supply store' not in csv2, 'CSV quoting only when needed')
        # delete an item
        pg.click('nav button[data-t=items]'); pg.locator('#list .row', has_text='Bath soap').click()
        pg.click('.sheet [data-a=delItem]'); check(pg, 'confirm-delete', w); pg.click('[data-a=doDelItem]'); pg.wait_for_timeout(100)
        if fn: expect(pg.locator('#list .row', has_text='Bath soap').count() == 0, 'deleted item leaves the list')
        # backup → clear → restore
        if fn:
            backup = pg.evaluate("() => { let t=''; window.Android={share:(x)=>{t=x}}; return t }")
            backup = json.dumps({'app': 'townmart-inventory', 'v': 1, 'data': json.loads(pg.evaluate("localStorage.getItem('townmart:v1')"))})
            pg.click('nav button[data-t=settings]'); pg.click('[data-a=clearAsk]'); pg.click('[data-a=doClear]'); pg.wait_for_timeout(100)
            pg.click('nav button[data-t=home]'); expect('No items yet' in pg.inner_text('main'), 'delete all data empties the app')
            pg.click('nav button[data-t=settings]'); pg.click('[data-a=restore]'); check(pg, 'restore', w)
            pg.fill('.sheet textarea', 'not json'); pg.click('form[data-f=restore] button'); pg.wait_for_timeout(50)
            expect('not a valid backup' in pg.inner_text('.sheet .err'), 'bad backup rejected')
            pg.fill('.sheet textarea', backup); pg.click('form[data-f=restore] button'); pg.wait_for_timeout(150)
            pg.click('nav button[data-t=home]'); expect(pg.locator('.stat .n').first.inner_text() == '11', 'restore brings back 11 items')
            pg.reload(); pg.wait_for_timeout(200); expect(pg.locator('.stat .n').first.inner_text() == '11', 'data persists after reopening')
            # back button
            pg.click('nav button[data-t=items]'); pg.click('#list .row >> nth=0')
            expect(pg.evaluate('appBack()') is True and pg.locator('#ov').is_hidden(), 'back closes the open sheet')
            expect(pg.evaluate('appBack()') is True and pg.inner_text('nav button[aria-current=page]').strip() == 'Home', 'back returns to Home')
            expect(pg.evaluate('appBack()') is False, 'back on Home exits the app')
        # screenshots for review
        if w in (320, 412):
            pg.goto(PAGE); pg.wait_for_timeout(200)
            pg.screenshot(path='%s/%d-home.png' % (OUT, w), full_page=True)
            pg.click('nav button[data-t=items]'); pg.screenshot(path='%s/%d-items.png' % (OUT, w))
            pg.locator('#list .row').first.click(); pg.wait_for_timeout(150); pg.screenshot(path='%s/%d-detail.png' % (OUT, w))
            pg.click('.sheet [data-a=move][data-m=out]'); pg.fill('#mq', '1'); pg.screenshot(path='%s/%d-move.png' % (OUT, w)); pg.click('[data-a=close]')
            pg.click('nav button[data-t=reports]'); pg.click('[data-a=period][data-p="30"]'); pg.screenshot(path='%s/%d-reports.png' % (OUT, w), full_page=True)
        ctx.close()
    b.close()

bad = [(w, n, p) for (w, n, p) in results['layout'] if p]
print('LAYOUT: %d screens checked, %d with problems' % (len(results['layout']), len(bad)))
for w, n, p in bad: print('  %dpx %s: %s' % (w, n, '; '.join(p[:6])))
f = [x for x in results['func'] if x[0] == 'FAIL']
print('FUNCTIONS: %d checks, %d failed' % (len(results['func']), len(f)))
for s, m in results['func']: print('  ' + s + ' ' + m)
print('JS ERRORS:', results['errors'] or 'none')
