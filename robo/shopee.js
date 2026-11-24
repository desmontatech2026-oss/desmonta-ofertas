// Coletor da Shopee. Rodar na aba https://affiliate.shopee.com.br/offer/product_offer (logado como Desmonta Tech).
// Depois de injetar: window.__Q.push(['palavra','categoria',qtd,300,pagina], ...) e acompanhar window.__res / window.__done.
// Para extrair: window.__res.slice(a,b).map(x=>[x.c,x.t.slice(0,90),x.p,x.d,x.sold,x.img,x.fs,x.u.replace('https://s.shopee.com.br/','')].join('|'))
(() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  // o "Obter link em massa" baixa um CSV; o robô lê o conteúdo direto e não deixa baixar arquivo no PC
  if (!window.__dlp) {
    const ac = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function () { const h = this.href || ''; if (/\.csv/i.test(h) || this.hasAttribute('download')) return; return ac.apply(this, arguments); };
    const wo = window.open; window.open = function (u) { if (/\.csv/i.test(String(u))) return null; return wo.apply(this, arguments); };
    window.__dlp = 1;
  }
  window.__lists = window.__lists || []; window.__lk = [];
  if (!window.__hooked) {
    const of = window.fetch;
    window.fetch = async function (u, o) {
      const r = await of.apply(this, arguments);
      try { const s = String(u && u.url || u);
        if (/page_offset/.test(s) && /list_type/.test(s)) window.__lists.push({ s, j: await r.clone().json() });
        if (/batch|offer_link|productOfferLink/i.test(s)) window.__lk.push({ s, t: await r.clone().text() });
      } catch (e) {}
      return r;
    };
    const oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (m, u) { this.__u = u; return oo.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function (b) {
      this.addEventListener('load', () => { const s = String(this.__u);
        if (/page_offset/.test(s) && /list_type/.test(s)) { try { window.__lists.push({ s, j: JSON.parse(this.responseText) }); } catch (e) {} }
        if (/batch|offer_link|productOfferLink/i.test(s)) window.__lk.push({ s, t: String(this.responseText) });
      });
      return os.apply(this, arguments);
    };
    window.__hooked = 1;
  }
  window.__res = window.__res || []; window.__seen = window.__seen || {}; window.__done = window.__done || []; window.__Q = window.__Q || [];
  const bad = /er[oó]tic|sex|lingerie|calcinha|vibrador|arma|faca|canivete|cigarro|vape|narguil|r[eé]plica|tv ?box|iptv|inspirado|contratipo/i;
  window.__doKw = async (kw, cat, maxPick = 4, minSold = 300, page = 1) => {
    document.querySelectorAll('.ant-modal-close').forEach(x => x.click());
    document.querySelectorAll('.ItemCard__container input[type=checkbox]').forEach(x => { if (x.checked) x.click(); });
    const inp = document.querySelector('input.ant-input-lg');
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    const n0 = window.__lists.length; setter.call(inp, kw); inp.dispatchEvent(new Event('input', { bubbles: true }));
    inp.focus(); inp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
    for (let k = 0; k < 50 && window.__lists.length === n0; k++) await sleep(150);
    await sleep(400);
    const n1 = window.__lists.length;
    [...document.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === 'Mais vendidos').click();
    for (let k = 0; k < 50 && window.__lists.length === n1; k++) await sleep(150);
    await sleep(600);
    for (let pg = 2; pg <= page; pg++) {
      const nx = document.querySelector('.page-item.page-next:not(.disabled)'); if (!nx) break;
      const n2 = window.__lists.length; nx.click();
      for (let k = 0; k < 50 && window.__lists.length === n2; k++) await sleep(150);
      await sleep(600);
    }
    const last = window.__lists[window.__lists.length - 1];
    if (!/sort_type=2/.test(last.s)) return { kw, got: 0 };
    const L = last.j.data.list, cards = [...document.querySelectorAll('.ItemCard__container')], pick = [];
    L.forEach((it, i) => { const b = it.batch_item_for_item_card_full; if (pick.length >= maxPick || window.__seen[b.itemid]) return;
      const r = (b.item_rating && b.item_rating.rating_star) || 0;
      if (b.is_adult || bad.test(b.name) || b.historical_sold < minSold || r < 4.5 || b.price / 1e5 < 8) return; pick.push(i); });
    if (!pick.length) return { kw, got: 0 };
    for (const i of pick) { const x = cards[i] && cards[i].querySelector('input[type=checkbox]'); if (x && !x.checked) x.click(); await sleep(60); }
    await sleep(250); window.__lk = [];
    [...document.querySelectorAll('button')].find(b => /Obter Link em Massa/i.test(b.textContent)).click(); await sleep(900);
    const m = [...document.querySelectorAll('.ant-modal')].find(m => m.offsetParent);
    [...m.querySelectorAll('button')].find(b => /Obter link/i.test(b.textContent)).click();
    let hit = null; for (let k = 0; k < 60 && !(hit = window.__lk.find(x => /\.csv/.test(x.t))); k++) await sleep(150);
    let csv = ''; if (hit) { const u = JSON.parse(hit.t).data.result; csv = await (await fetch(u, { credentials: 'include' })).text(); }
    document.querySelectorAll('.ant-modal-close').forEach(x => x.click()); await sleep(300);
    for (const i of pick) { const x = cards[i] && cards[i].querySelector('input[type=checkbox]'); if (x && x.checked) x.click(); }
    const links = {}; csv.split('\n').slice(1).forEach(line => { const mm = line.match(/^(\d+),.*,(https:\/\/s\.shopee\.com\.br\/\w+)\s*$/); if (mm) links[mm[1]] = mm[2]; });
    let got = 0;
    for (const i of pick) { const b = L[i].batch_item_for_item_card_full, lk = links[b.itemid]; if (!lk) continue; window.__seen[b.itemid] = 1; got++;
      window.__res.push({ kw, c: cat, id: b.itemid, t: b.name, p: b.price / 1e5, d: b.raw_discount, sold: b.historical_sold_text || b.sold_text, img: b.image, fs: b.show_free_shipping ? 1 : 0, u: lk }); }
    return { kw, got };
  };
  if (!window.__worker) window.__worker = (async () => { while (true) { const job = window.__Q.shift(); if (!job) { await sleep(1500); continue; }
    try { const r = await window.__doKw(job[0], job[1], job[2], job[3] || 300, job[4] || 1); window.__done.push(job[0] + ':' + r.got); }
    catch (e) { window.__done.push(job[0] + ':ERR'); document.querySelectorAll('.ant-modal-close').forEach(x => x.click()); await sleep(800); } } })();
  return 'coletor shopee pronto';
})()
