
var NB_PLATFORM = (function () { try { return JSON.parse(document.getElementById('nb-platform').textContent) || []; } catch (e) { return []; } })();
// only the owner's AliExpress links and AliExpress photos, whatever a response holds
function safeLink(u) { try { var x = new URL(u); return x.protocol === 'https:' && /(^|\.)aliexpress\.(com|ru|us)$/i.test(x.hostname) ? x.href : ''; } catch (e) { return ''; } }
function safeImg(u) { try { var x = new URL(u); return x.protocol === 'https:' && /(^|\.)(aliexpress-media\.com|alicdn\.com|aliexpress\.com)$/i.test(x.hostname) ? x.href : ''; } catch (e) { return ''; } }
function imgTag(src, w) { var s = safeImg(src); return s ? '<img src="' + esc(s) + '_350x350.jpg" data-fallback="' + esc(s) + '" alt="" width="' + w + '" height="' + w + '" loading="lazy" referrerpolicy="no-referrer">' : ''; }
// a photo that fails in the small size falls back to the original (no inline handlers: the CSP forbids them)
document.addEventListener('error', function (ev) {
  var t = ev.target; if (t && t.tagName === 'IMG' && t.dataset.fallback) { var f = t.dataset.fallback; delete t.dataset.fallback; t.src = f; }
}, true);
function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function priceHtml(v) { var p = Number(v).toFixed(2).split('.'); return '<span class="price"><span class="cur">₪</span><span>' + p[0] + '</span>' + (p[1] !== '00' ? '<span class="sr-only">.</span><span class="ag">' + p[1] + '</span>' : '') + '</span>'; }
function ils(v) { return '₪' + (Math.abs(v - Math.round(v)) < 0.005 ? Math.round(v) : Number(v).toFixed(2)); }
function maskCode(c) { var k = c.length > 5 ? 3 : 2; return c.slice(0, k) + '•'.repeat(Math.max(3, Math.min(5, c.length - k))); }
function couponBtn(code, kind, what, link) {
  return '<button class="tcoupon" type="button" data-code="' + esc(code) + '" data-href="' + esc(link) + '" aria-label="העתקת ' + kind + ' ופתיחת המוצר">' +
    '<span class="tc-what"><b>' + kind + '</b> ' + esc(what) + '</span><span class="tc-code"><span class="tc-txt">' + esc(maskCode(code)) + '</span><span class="tc-act">העתקה</span></span></button>';
}
function coupons(p) {
  var out = '', c = p.code;
  if (c && typeof c === 'object' && c.code && !(c.ends && new Date(c.ends.replace(' ', 'T')) < new Date())) {
    var what = c.off ? ils(c.off) + ' הנחה' : (c.pct ? Math.round(c.pct) + '% הנחה' : '');
    if (c.min && c.min > 1) what += ' מעל ' + ils(c.min);
    out += couponBtn(c.code, 'קוד מוכר', what, p.link);
  }
  var pl = NB_PLATFORM;
  if (pl.length) {
    var fit = pl.filter(function (r) { return r.min <= p.price + 0.01; });
    if (fit.length) { var r = fit.reduce(function (a, b) { return b.off > a.off ? b : a; });
      out += couponBtn(r.code, 'קוד ישראל', r.what, p.link); }
  }
  return out ? '<span class="tcoupons">' + out + '</span>' : '';
}
// a code inside a card: copy it, show it, and open the product in a new tab (the affiliate link)
document.addEventListener('click', function (ev) {
  var b = ev.target.closest && ev.target.closest('.tcoupon'); if (!b) return;
  var code = b.dataset.code, txt = b.querySelector('.tc-txt'), act = b.querySelector('.tc-act');
  var done = function (ok) { txt.textContent = code; act.textContent = ok ? 'הועתק ✓' : 'העתיקו ידנית'; b.classList.add('shown'); };
  try { navigator.clipboard.writeText(code).then(function () { done(true); }, function () { done(false); }); } catch (e) { done(false); }
  var href = safeLink(b.dataset.href); if (href) window.open(href, '_blank', 'noopener');
});
function codeLabel(p) {
  var c = p.code; if (!c || typeof c !== 'object') return null;
  if (c.ends && new Date(c.ends.replace(' ', 'T')) < new Date()) return null;
  if (c.min && c.min > p.price + 0.01) return 'יש קוד הנחה בבוט';
  if (c.off) return 'קוד ₪' + (Math.abs(c.off - Math.round(c.off)) < 0.005 ? Math.round(c.off) : c.off.toFixed(2)) + ' בבוט';
  if (c.pct) return 'קוד ' + Math.round(c.pct) + '% בבוט';
  return 'יש קוד הנחה בבוט';
}
document.querySelectorAll('form.checker').forEach(function (f) {
  var input = f.querySelector('input.q'), btn = f.querySelector('button'), msg = f.querySelector('.msg');
  var idle = msg.innerHTML, label = btn.querySelector('span').textContent;
  var bot = f.dataset.bot, src = f.dataset.src;
  function say(t, err) { msg.textContent = t; msg.classList.toggle('err', !!err); }
  function busy(on, t) { if (on) { btn.setAttribute('aria-busy', 'true'); btn.querySelector('span').textContent = t; } else { btn.removeAttribute('aria-busy'); btn.querySelector('span').textContent = label; } }
  input.addEventListener('input', function () { if (msg.classList.contains('err')) { msg.innerHTML = idle; msg.classList.remove('err'); } });
  // the answers appear as a chat right under the search, newest at the bottom
  function chatLog() {
    var box = document.getElementById('sresults');
    if (!box) {
      var band = f.closest('section') || f;
      box = document.createElement('section'); box.id = 'sresults'; box.className = 'sresults chat'; box.setAttribute('aria-live', 'polite');
      box.innerHTML = '<div class="wrap"><div class="chat-head"><b>התשובות שלכם</b><button type="button" class="chat-clear">ניקוי</button></div><div class="chat-log"></div></div>';
      band.insertAdjacentElement('afterend', box);
      box.querySelector('.chat-clear').addEventListener('click', function () { box.remove(); input.focus(); });
    }
    return box.querySelector('.chat-log');
  }
  function ask(text) {
    var log = chatLog();
    var me = document.createElement('div'); me.className = 'cmsg me'; me.innerHTML = '<p>' + esc(text) + '</p>'; log.appendChild(me);
    var ans = document.createElement('div'); ans.className = 'cmsg bot';
    ans.innerHTML = '<span class="cavatar" aria-hidden="true">N</span><div class="cbody"><p class="typing"><span></span><span></span><span></span></p></div>';
    log.appendChild(ans);
    me.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return ans.querySelector('.cbody');
  }
  function botLink(start) { return bot + '?start=' + start + '-' + src; }
  function tile(p) {
    p.link = safeLink(p.link); if (!p.link) return '';
    var was = p.original && p.original > p.price + 0.5 ? '<span class="was">₪' + p.original.toFixed(2) + '</span>' : '';
    var burst = p.discount && p.discount >= 5 ? '<span class="burst"><span class="sr-only">הנחה של </span>-' + Math.round(p.discount) + '%</span>' : '';
    var meta = (p.rating ? '⭐ ' + esc(p.rating) : '') + (p.sold ? (p.rating ? ' · ' : '') + esc(p.sold) + ' נמכרו' : '');
    var attrs = 'href="' + esc(p.link) + '" rel="sponsored nofollow noopener" target="_blank"';
    return '<li><div class="tile"><a class="tlink" ' + attrs + '><span class="pic">' + imgTag(p.image, 300) + '</span>' + burst +
      '<span class="tprice">' + priceHtml(p.price) + was + '</span><span class="ttl">' + esc(p.title) + '</span><span class="tfoot"><span class="cat">' + meta + '</span></span></a>' + coupons(p) +
      '<a class="cta" ' + attrs + ' tabindex="-1">לצפייה במוצר</a></div></li>';
  }
  // one product as a wide card in the answer (the pasted link, or an alternative)
  function wide(p, alt) {
    p.link = safeLink(p.link); if (!p.link) return '';
    var attrs = 'href="' + esc(p.link) + '" rel="sponsored nofollow noopener" target="_blank"';
    var was = p.original && p.original > p.price + 0.5 ? '<span class="was">₪' + p.original.toFixed(2) + '</span>' : '';
    var disc = p.discount && p.discount >= 5 ? '<span class="pill">-' + Math.round(p.discount) + '%</span>' : '';
    var meta = (p.rating ? '⭐ ' + esc(p.rating) : '') + (p.sold ? (p.rating ? ' · ' : '') + esc(p.sold) + ' נמכרו' : '');
    var save = alt && p.saving > 0.5 ? '<span class="save">חוסכים ' + ils(p.saving) + '</span>' : '';
    return '<div class="wcard' + (alt ? ' alt' : '') + '"><a class="wpic" ' + attrs + ' tabindex="-1">' + imgTag(p.image, 160) + '</a>' +
      '<div class="wbody"><a class="wttl" ' + attrs + '>' + esc(p.title) + '</a>' +
      '<div class="wprice">' + priceHtml(p.price) + was + disc + save + '</div>' + (meta ? '<p class="wmeta">' + meta + '</p>' : '') +
      coupons(p) + '<a class="btn wbtn" ' + attrs + '>' + (alt ? 'לצפייה במוצר' : 'לקנייה באליאקספרס') + '</a></div></div>';
  }
  function fail(body, text) { body.innerHTML = '<p class="cerr">' + esc(text) + '</p><p class="cnote"><a href="' + botLink('') + '">אפשר לנסות גם בבוט בטלגרם</a></p>'; }
  function siteSearch(q) {
    var body = ask(q);
    busy(true, 'מחפש…'); say('מחפשים את הדילים הכי שווים…');
    fetch(f.dataset.search + '?q=' + encodeURIComponent(q) + '&v=2').then(function (r) {
      if (r.status === 429) throw new Error('slow'); if (!r.ok) throw new Error('bad'); return r.json();
    }).then(function (d) {
      busy(false); msg.innerHTML = idle; msg.classList.remove('err');
      var items = (d.products || []);
      if (!items.length) { body.innerHTML = '<p>לא מצאתי תוצאות טובות ל"' + esc(q) + '". נסו מילה אחרת, או באנגלית (למשל power bank).</p>'; return; }
      var coded = items.filter(function (p) { return p.coupon; }), rest = items.filter(function (p) { return !p.coupon; });
      var group = function (title, list) { return list.length ? '<h3 class="cgroup">' + title + '</h3><ul class="tiles">' + list.map(tile).join('') + '</ul>' : ''; };
      body.innerHTML = '<p>מצאתי ' + items.length + ' דילים ל"' + esc(q) + '"' + (coded.length ? ', ' + coded.length + ' מהם עם קוד קופון' : '') + ':</p>' +
        (coded.length ? group('עם קוד קופון', coded) + group('עוד דילים', rest) : '<ul class="tiles">' + rest.map(tile).join('') + '</ul>') +
        '<p class="cnote">תוצאות חיות מאליאקספרס. רוצים מוכר זול יותר למוצר מסוים? הדביקו את הלינק שלו בחיפוש. * קישורי שותפים של אליאקספרס.</p>';
      body.closest('.cmsg').classList.add('wide');
    }).catch(function (e) {
      busy(false); msg.innerHTML = idle;
      fail(body, e.message === 'slow' ? 'רגע, יותר מדי חיפושים. נסו שוב בעוד דקה.' : 'החיפוש לא זמין כרגע. נסו שוב בעוד רגע.');
    });
  }
  function linkCheck(v) {
    var body = ask(v.length > 70 ? v.slice(0, 70) + '…' : v);
    var m = v.match(/(?:\/item\/|productIds?=|[?&]id=|\/i\/)(\d{10,20})/) || v.match(/(\d{13,20})/);
    var sh = v.match(/a\.aliexpress\.[a-z.]+\/_([A-Za-z0-9]{3,40})/i);
    var start = m ? 'p_' + m[1] : (sh ? 's_' + sh[1] : '');
    body.innerHTML = '<p>בודק את המחיר והקופון, ומחפש אם מוכרים אחרים מוכרים את זה בזול יותר… (עד חצי דקה)</p><p class="typing"><span></span><span></span><span></span></p>';
    busy(true, 'בודק…'); say('בודק את הלינק שלכם…');
    fetch(f.dataset.product + '?url=' + encodeURIComponent(v)).then(function (r) {
      if (r.status === 429) throw new Error('slow'); if (!r.ok && r.status !== 400) throw new Error('bad'); return r.json();
    }).then(function (d) {
      busy(false); msg.innerHTML = idle; msg.classList.remove('err');
      if (!d.ok) { body.innerHTML = '<p class="cerr">' + esc(d.message || 'לא הצלחתי לבדוק את הלינק הזה.') + '</p>'; return; }
      var p = d.product, alts = d.alternatives || [];
      var html = '<p>זה המוצר שלכם' + (p.code && p.code.code ? ', ויש לו קוד הנחה של המוכר' : '') + ':</p>' + wide(p, false);
      if (alts.length) {
        html += '<p class="cgap">💡 מצאתי ' + (alts.length === 1 ? 'מוכר אחד שמוכר' : alts.length + ' מוכרים שמוכרים') + ' משהו דומה בזול יותר:</p>' + alts.map(function (a) { return wide(a, true); }).join('') +
          '<p class="cnote">שווה לוודא שזה אותו דגם ואותו מפרט לפני הקנייה.</p>';
      } else {
        html += '<p class="cgap">👌 בדקתי מוכרים אחרים ולא מצאתי את זה זול יותר עם דירוג טוב. נראה שזה כבר מחיר טוב.</p>';
      }
      html += '<p class="cnote">* קישורי שותפים של אליאקספרס.' + (start ? ' <a href="' + botLink(start) + '">להמשיך בבוט בטלגרם</a>' : '') + '</p>';
      body.innerHTML = html;
    }).catch(function (e) {
      busy(false); msg.innerHTML = idle;
      body.innerHTML = '<p class="cerr">' + (e.message === 'slow' ? 'רגע, יותר מדי בדיקות. נסו שוב בעוד דקה.' : 'לא הצלחתי לבדוק כרגע.') + '</p>' +
        (start ? '<p><a class="btn secondary" href="' + botLink(start) + '">לבדוק את המוצר בבוט בטלגרם</a></p>' : '');
    });
  }
  f.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var v = input.value.trim();
    if (!v) { say('הדביקו לינק של מוצר מאליאקספרס, או כתבו מה אתם מחפשים.', true); input.focus(); return; }
    if (btn.getAttribute('aria-busy')) return;
    var isLink = /aliexpress|aliexpi|s\.click\.ali|\d{13,}/i.test(v);
    if (!isLink) {
      if (/https?:|www\./i.test(v)) { say('זה לא לינק מאליאקספרס. באפליקציה: שיתוף ← העתק קישור.', true); input.focus(); return; }
      if (v.length < 2) { say('כתבו שם של מוצר, למשל: סוללה ניידת', true); input.focus(); return; }
      siteSearch(v); input.value = ''; return;
    }
    linkCheck(v); input.value = '';
  });
});
