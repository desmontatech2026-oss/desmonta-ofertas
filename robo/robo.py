# Robô do Desmonta Ofertas: soma as ofertas novas ao catálogo (nunca remove) e gera o site.
# Uso: python3 robo.py PASTA --plano   -> mostra as palavras e a página de cada loja nesta rodada
#      python3 robo.py PASTA           -> junta novos_sp.txt / novos_ml.txt e gera o site
# Na PASTA: ofertas.json (o publicado), template.html, img/ com a última folha (as outras só se faltar ph em alguma oferta), novos_sp.txt e/ou novos_ml.txt
#   novos_sp.txt  categoria|titulo|preco|desconto%|vendidos|imagem_shopee|frete(0/1)|codigo_s.shopee
#   novos_ml.txt  categoria|titulo|preco|preco_antigo|flags|imagem_mlstatic|codigo_meli.la
#   novos_ped.txt mesmo formato do novos_sp.txt: produtos que o pessoal pediu (ganham a marca P e saem no post)
#   novos_az.txt  categoria|titulo|ASIN|id_imagem_amazon (sem preço: a Amazon só permite preço vindo da API oficial)
# Saída na PASTA: ofertas.json, index.html e img/fNN.webp novos (lista impressa no fim).
import json, os, re, sys, random, unicodedata, datetime, subprocess
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

D = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
BRT = datetime.timezone(datetime.timedelta(hours=-3))
AGORA = datetime.datetime.now(BRT)

if '--plano' in sys.argv:
    P = json.load(open(os.path.join(D, 'palavras.json'), encoding='utf-8'))
    ini = datetime.date.fromisoformat(P['inicio'])
    # 4 rodadas por dia (~4h, ~12h, ~16h, ~19h)
    slot = 0 if AGORA.hour < 8 else 1 if AGORA.hour < 14 else 2 if AGORA.hour < 18 else 3
    rodada = max(0, (AGORA.date() - ini).days) * 4 + slot
    hoje = AGORA.date().isoformat()
    plano = {'rodada': rodada}
    for loja, por, qtd in (('shopee', P['shopee_por_rodada'], P['shopee_qtd']), ('ml', P['ml_por_rodada'], P['ml_qtd'])):
        lista = P[loja]; n = len(lista)
        extra = []
        for ep in P.get('epocas', []):
            if ep.get('de', '0000') <= hoje <= ep['ate']:
                da_epoca = [x for x in lista if x[1] == ep['cat']]
                k = ep[loja]
                if da_epoca:
                    s0 = (rodada * k) % len(da_epoca)
                    extra += [da_epoca[(s0 + j) % len(da_epoca)] for j in range(min(k, len(da_epoca)))]
        s0 = (rodada * por) % n
        base = [lista[(s0 + j) % n] for j in range(por)]
        pagina = 1 + ((rodada * por) // n) % 5
        vistos, sel = set(), []
        for x in extra + base:
            if x[0] not in vistos:
                vistos.add(x[0]); sel.append([x[0], x[1], qtd])
        plano[loja] = {'pagina': pagina, 'palavras': sel}
    print(json.dumps(plano, ensure_ascii=False))
    sys.exit(0)
DATA = json.load(open(os.path.join(D, 'ofertas.json'), encoding='utf-8'))
items = DATA['items']
random.seed(datetime.date.today().toordinal())
JUNK = re.compile(r'envio aleat|aleat[oó]rio de produtos|n[aã]o acompanha|surpresa|er[oó]tic|sexy|r[eé]plica|inspirado em|contratipo|vinho|cerveja|whisky|vodka|cigarro|vape', re.I)

def norm(s):
    s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()

def key(t):
    return ' '.join(norm(t).split()[:7])

def clean(t):
    t = re.sub(r'\s+', ' ', str(t)).strip()
    parts = re.split(r'\s*[/|]\s*(?=[A-Za-zÀ-ú])', t)
    if len(parts) > 1 and len(parts[0]) >= 18:
        t = parts[0]
    if len(t) > 95:
        t = t[:95].rsplit(' ', 1)[0]
    t = t.strip(' ,-;:')
    return t[:1].upper() + t[1:]

def help_for(it):
    t = norm(it['t'])
    m = re.search(r'(\d{4,5})\s?mah', t)
    if 'power bank' in t or 'carregador portatil' in t:
        return {'h': 'pb', **({'cap': int(m.group(1))} if m else {})}
    if 'air fryer' in t or 'airfryer' in t or 'fritadeira' in t:
        return {'h': 'cap', 'k': 'airfryer'}
    if 'geladeira' in t or 'refrigerador' in t:
        return {'h': 'cap', 'k': 'geladeira'}
    if 'lavadora' in t or 'maquina de lavar' in t:
        return {'h': 'cap', 'k': 'lavar'}
    if re.search(r'smart ?tv|televis', t):
        return {'h': 'tv'}
    if 'ar condicionado' in t:
        return {'h': 'btu'}
    if 'placa de video' in t:
        return {'h': 'pc'}
    return {'h': 'vista'} if it['p'] >= 900 else {}

seen_k = {key(i['t']) for i in items}
seen_u = {i['u'] for i in items}
n_next = max(i['n'] for i in items) + 1
novos = []

def add(it, img):
    global n_next
    if not it['t'] or JUNK.search(it['t']) or key(it['t']) in seen_k or it['u'] in seen_u:
        return
    seen_k.add(key(it['t'])); seen_u.add(it['u'])
    it['n'] = n_next; n_next += 1
    it.update(help_for(it))
    novos.append((it, img))

def lines(name):
    fn = os.path.join(D, name)
    return [l.rstrip('\n').split('|') for l in open(fn, encoding='utf-8')] if os.path.exists(fn) else []

for f in [x + ['sp'] for x in lines('novos_sp.txt')] + [x + ['P'] for x in lines('novos_ped.txt')]:
    tag = f.pop()
    if len(f) < 8:
        continue
    c, t, p, d, sold, img, fs, u = f[0], '|'.join(f[1:-6]), *f[-6:]
    p, d = float(p), int(float(d))
    o = round(p / (1 - d / 100), 2) if 0 < d < 95 else None
    it = {'s': 'sp', 't': clean(t), 'p': p, 'off': d if o else 0, 'c': c, 'f': ('F' if fs == '1' else '') + ('P' if tag == 'P' else ''), 'u': 'https://s.shopee.com.br/' + u}
    if o: it['o'] = o
    if sold and sold != '0': it['sold'] = sold
    add(it, 'https://down-br.img.susercontent.com/file/%s_tn' % img)

for f in lines('novos_ml.txt'):
    if len(f) != 7:
        continue
    c, t, p, o, fl, img, u = f
    p, o = float(p), float(o or 0)
    off = round((1 - p / o) * 100) if o > p else 0
    it = {'s': 'ml', 't': clean(t), 'p': p, 'off': off, 'c': c, 'f': fl.replace('X', ''), 'u': 'https://meli.la/' + u}
    if off: it['o'] = o
    add(it, img if img.startswith('http') else 'https://http2.mlstatic.com/' + img)

for f in lines('novos_az.txt'):
    if len(f) != 4:
        continue
    c, t, asin, img = f
    # Amazon: link oficial de associado (tag desmontatech-20) e sem preço, como pede o acordo de associados
    it = {'s': 'az', 't': clean(t), 'p': 0, 'off': 0, 'c': c, 'f': 'M', 'np': 1, 'u': 'https://www.amazon.com.br/dp/%s?tag=desmontatech-20' % asin}
    add(it, img if img.startswith('http') else 'https://m.media-amazon.com/images/I/%s._AC_SL300_.jpg' % img)

# fotos em sprites 12 x 5 de 120 px, continuando a numeração
os.makedirs(os.path.join(D, 'dl'), exist_ok=True)
os.makedirs(os.path.join(D, 'img'), exist_ok=True)
def fetch(url):
    fn = os.path.join(D, 'dl', re.sub(r'[^A-Za-z0-9_.-]', '_', url.split('/')[-1])[:120])
    if not os.path.exists(fn) or os.path.getsize(fn) < 500:
        subprocess.run(['curl', '-s', '-L', '-m', '25', '-o', fn, url])
    try:
        im = Image.open(fn); im.load(); return im
    except Exception:
        return None
with ThreadPoolExecutor(16) as ex:
    imgs = list(ex.map(lambda x: fetch(x[1]), novos))

ult = max(int(i['sp'][1:]) for i in items if i.get('sp'))
usados = 1 + max((i['ix'] for i in items if i.get('sp') == 'f%d' % ult), default=59)
fn_ult = os.path.join(D, 'img', 'f%d.webp' % ult)
if usados < 60 and os.path.exists(fn_ult):
    sheet_no, slot, sheet = ult, usados, Image.open(fn_ult).convert('RGB')
else:
    sheet_no, slot, sheet = ult + 1, 0, None
sheets = []
def flush():
    global sheet
    if sheet is not None:
        name = 'img/f%d.webp' % sheet_no
        sheet.save(os.path.join(D, name), 'WEBP', quality=72, method=6)
        sheets.append(name); sheet = None
ok = []
for (it, _), im in zip(novos, imgs):
    if im is None:
        continue
    if sheet is None:
        sheet = Image.new('RGB', (1440, 600), 'white')
    im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg.convert('RGB')
    im.thumbnail((112, 112), Image.LANCZOS)
    cellx, celly = (slot % 12) * 120, (slot // 12) * 120
    sheet.paste(im, (cellx + (120 - im.width) // 2, celly + (120 - im.height) // 2))
    it['sp'] = 'f%d' % sheet_no; it['ix'] = slot
    ok.append(it); slot += 1
    if slot == 60:
        flush(); sheet_no += 1; slot = 0
flush()
items = items + ok  # nunca remove oferta: o catálogo só cresce
# só sai o que é repetido: mesma loja + mesmo preço (até 2%) + mesma foto ou mesmo nome; fica o que vende mais
# (a "impressão digital" da foto fica salva no campo ph de cada oferta)
def _cell_hash(sh, ix):
    x, y = (ix % 12) * 120, (ix // 12) * 120
    px = list(sh.crop((x + 4, y + 4, x + 116, y + 116)).convert('L').resize((9, 8), Image.LANCZOS).get_flattened_data())
    b = 0
    for r in range(8):
        for c in range(8):
            b = b << 1 | (px[r * 9 + c] > px[r * 9 + c + 1])
    return '%016x' % b
_shs = {}
for i in items:
    if i.get('ph') or not i.get('sp'): continue
    fn = os.path.join(D, 'img', i['sp'] + '.webp')
    if not os.path.exists(fn): continue
    if i['sp'] not in _shs: _shs[i['sp']] = Image.open(fn).convert('RGB')
    i['ph'] = _cell_hash(_shs[i['sp']], i['ix'])
def _toks(t):
    return set(w for w in norm(t).split() if len(w) > 2)
def _vend(i):
    m = re.match(r'(\d+)(mil|mi)?', i.get('sold') or '')
    return 0 if not m else int(m.group(1)) * (1000000 if m.group(2) == 'mi' else 1000 if m.group(2) else 1)
fora = set()
for loja in ('sp', 'ml', 'az'):
    L = sorted([i for i in items if i['s'] == loja], key=lambda x: x['p'])
    T = [_toks(x['t']) for x in L]
    for a in range(len(L)):
        A = L[a]
        if id(A) in fora: continue
        for b in range(a + 1, len(L)):
            B = L[b]
            if B['p'] > A['p'] * 1.02 + (0 if A['p'] else 0.001): break
            if id(B) in fora: continue
            j = len(T[a] & T[b]) / max(1, len(T[a] | T[b]))
            h = bin(int(A['ph'], 16) ^ int(B['ph'], 16)).count('1') if A.get('ph') and B.get('ph') else 99
            if A['u'] == B['u'] or (j >= 0.95 if loja == 'az' else (j >= 0.6 or (h <= 6 and j >= 0.4) or (h <= 3 and j >= 0.25) or (A['p'] == B['p'] and A.get('o') and A.get('o') == B.get('o') and h <= 10))):
                keep, drop = sorted([A, B], key=lambda x: (-_vend(x), x['n']))
                fora.add(id(drop))
                if drop is A: break
# o mesmo produto com nome igual (7 primeiras palavras) e preço até 10% diferente também sai; fica o mais barato
grupos = {}
for i in items:
    if id(i) not in fora: grupos.setdefault(key(i['t']), []).append(i)
for g in grupos.values():
    if len(g) < 2: continue
    mantidos = []
    for i in sorted(g, key=lambda x: x['p']):
        if any(abs(i['p'] - m['p']) <= 0.10 * m['p'] for m in mantidos): fora.add(id(i))
        else: mantidos.append(i)
items = [i for i in items if id(i) not in fora]
print('REPETIDOS_REMOVIDOS', len(fora))

# radar "preço prestes a cair": alvo próprio para cada produto, perto do preço real
VERD = ['Ainda sem desconto forte. Abaixo de {a} vira compra boa.', 'Perto da Black Friday costuma baixar. Se bater {a}, pode ir.',
        'Hoje tá {p}. Nosso preço-alvo é {a}.', 'Tá salgado ainda. Em {a} ou menos, vale o carrinho.',
        'Deixa o alerta em {a}: quando chegar, a gente avisa.', 'Produto bom, preço ainda não. Espera chegar em {a}.',
        'Muita gente de olho nesse. Em {a} ele vira oferta de verdade.']
def brl(v):
    s = '{:,.0f}'.format(v) if abs(v - round(v)) < 0.005 else '{:,.2f}'.format(v)
    return 'R$ ' + s.replace(',', 'X').replace('.', ',').replace('X', '.')
def alvo_for(p):
    a = p * random.uniform(0.78, 0.93)
    if a >= 1000: a = int(a / 10) * 10 + random.choice([0, 3, 5, 7, 9, 9])
    elif a >= 100: a = int(a) - int(a) % 5 + random.choice([0, 2, 4, 7, 9, 9])
    else: a = int(a) + random.choice([0.0, 0.49, 0.90, 0.99])
    return round(a, 2)
live = {i['u']: i for i in items}
radar = []
for r0 in DATA.get('radar', []):
    if r0['u'] in live and len(radar) < 40:
        r = dict(live[r0['u']]); a = alvo_for(r['p']); r['alvo'] = a; r['v'] = random.choice(VERD).format(a=brl(a), p=brl(r['p'])); radar.append(r)
used = {r['u'] for r in radar}
pool = [i for i in items if (i.get('off') or 0) <= 12 and i['p'] >= 60 and i.get('sp') and i['u'] not in used]
random.shuffle(pool)
for i in pool:
    if len(radar) >= 80: break
    r = dict(i); a = alvo_for(r['p']); r['alvo'] = a; r['v'] = random.choice(VERD).format(a=brl(a), p=brl(r['p'])); radar.append(r)

DATA['items'] = items
DATA['radar'] = radar
# cupons do dia coletados na rodada (cupons.json na PASTA); sem arquivo, ficam os de antes
if os.path.exists(os.path.join(D, 'cupons.json')):
    DATA['cupons'] = json.load(open(os.path.join(D, 'cupons.json'), encoding='utf-8'))
DATA['updated'] = AGORA.replace(microsecond=0).isoformat()
js = json.dumps(DATA, ensure_ascii=False, separators=(',', ':'))
open(os.path.join(D, 'ofertas.json'), 'w', encoding='utf-8').write(js)
tpl = open(os.path.join(D, 'template.html'), encoding='utf-8').read()
tot_txt = '{:,}'.format((len(items) // 100) * 100).replace(',', '.')  # vai pra prévia do link no WhatsApp
open(os.path.join(D, 'index.html'), 'w', encoding='utf-8').write(tpl.replace('__DATA__', js).replace('__TOTAL__', tot_txt))
ml = sum(1 for i in items if i['s'] == 'ml')
az = sum(1 for i in items if i['s'] == 'az')
print('NOVAS', len(ok), '| TOTAL', len(items), '| SHOPEE', len(items) - ml - az, '| ML', ml, '| AMAZON', az, '| RADAR', len(radar))
print('SPRITES_NOVOS', ' '.join(sheets))
dup = len(items) - len({key(i['t']) for i in items})
print('DUPLICADOS', dup)

# textos do dia: story (sem link) e post do canal (com link)
EMO = {'natal': '🎄', 'games': '🎮', 'audio': '🎧', 'celulares': '📱', 'informatica': '💻', 'tv': '📺', 'eletro': '🔌', 'casa': '🏠', 'moveis': '🛋️',
       'ferramentas': '🔧', 'beleza': '💄', 'saude': '💪', 'moda': '👟', 'bebes': '🍼', 'auto': '🚗', 'pet': '🐶', 'brinquedos': '🧸', 'mercado': '🛒', 'esporte': '⚽'}
def curto(t):
    t = re.split(r',| - | – | \| |\(', t)[0]
    for corte in (' com ', ' para ', ' pra '):
        k = t.lower().find(corte)
        if k >= 18: t = t[:k]
    if len(t) > 40: t = t[:40].rsplit(' ', 1)[0]
    w = t.split()
    while w and w[-1].lower() in ('de', 'da', 'do', 'das', 'dos', 'e', 'em', 'para', 'com', 'a', 'o', 'p/', '+', '-'):
        w.pop()
    return ' '.join(w)
def vendas(i):
    s = i.get('sold') or ''
    m = re.match(r'(\d+)(mil|mi)?', s)
    return 0 if not m else int(m.group(1)) * (1000000 if m.group(2) == 'mi' else 1000 if m.group(2) else 1)
novas_url = {i['u'] for i in ok}
# nunca repetir no post/story o que já saiu nos últimos 45 dias (por link e por nome parecido)
POST = DATA.get('postados', {})
lim = (AGORA.date() - datetime.timedelta(days=45)).isoformat()
POST = {u: d for u, d in POST.items() if d >= lim}
ja_u = set(POST)
ja_k = {key(live[u]['t'])[:18] for u in POST if u in live}
def livre(i):
    return i['u'] not in ja_u and key(i['t'])[:18] not in ja_k
cand = [i for i in items if livre(i) and (i.get('off') or 0) >= 60 and i.get('o') and i['p'] >= 12 and (vendas(i) >= 1000 or 'M' in (i.get('f') or ''))]
# as ofertas que entraram nesta rodada vêm primeiro (critério mais leve), depois as antigas que nunca foram postadas
cand_novas = [i for i in items if i['u'] in novas_url and livre(i) and (i.get('off') or 0) >= 25 and i.get('o') and i['p'] >= 12 and (vendas(i) >= 300 or 'M' in (i.get('f') or ''))]
import math
# o primeiro do post é o que mais engatilha a compra: desconto alto + muita venda, de categoria que todo mundo compra
LARGO = ('casa', 'eletro', 'beleza', 'moda', 'natal', 'brinquedos', 'mercado', 'saude', 'bebes', 'tv', 'celulares', 'moveis', 'ferramentas')
def forca(i):
    return i['off'] + 6 * math.log10(max(vendas(i), 1)) + (4 if i['c'] == 'natal' else 0) + (3 if i['u'] in novas_url else 0)
cand.sort(key=forca, reverse=True)
cand_novas.sort(key=forca, reverse=True)
pick, cats = [], {}
for i in cand_novas[:8] + cand:
    if i in pick: continue
    if cats.get(i['c'], 0) >= 1 or any(key(i['t'])[:18] == key(x['t'])[:18] for x in pick):
        continue
    pick.append(i); cats[i['c']] = cats.get(i['c'], 0) + 1
    if len(pick) == 5: break
largos = [i for i in pick if i['c'] in LARGO]
if largos:
    pick.remove(largos[0]); pick.insert(0, largos[0])
amz = [i for i in items if i['s'] == 'az']
amz_pick = []
if amz:
    k = datetime.date.today().toordinal() * 4 + AGORA.hour // 6
    amz_n = [i for i in amz if i['u'] in novas_url and livre(i)]
    amz_v = [i for i in amz if livre(i) and i not in amz_n]
    amz_v = amz_v[(k * 2) % len(amz_v):] + amz_v[:(k * 2) % len(amz_v)] if amz_v else []
    amz_pick = (amz_n + amz_v)[:2]
for i in pick + amz_pick:
    POST[i['u']] = AGORA.date().isoformat()
DATA['postados'] = POST
total = (len(items) // 100) * 100
story = ['DESMONTEI OS PREÇOS DE HOJE 🔧🔥', '']
for i in pick:
    story += [f"{EMO.get(i['c'], '🔥')} {curto(i['t'])}", f"Tava {brl(i['o'])}. Desmontei: caiu pra {brl(i['p'])}", f"👉 {i['off']}% OFF", '']
story += ['👇 GOSTOU DE ALGUMA?', '1. Toca em LINK DE OFERTAS', '2. Digita o nome do produto na busca', '3. Garante o seu antes que o preço volte!', '',
          f'Mais de {total:,} ofertas te esperando. Achou? Coloca no carrinho pra não perder 🛒'.replace(',', '.'), '',
          '(Figurinha de link com o texto LINK DE OFERTAS + GIF de seta "toque aqui" apontando pra ela)']
zap = ['🔥 DESMONTEI OS PREÇOS DE HOJE 🔥', '']
for i in pick:
    zap += [f"{EMO.get(i['c'], '🔥')} {curto(i['t'])}", f"De {brl(i['o'])} por {brl(i['p'])} ({i['off']}% OFF)", i['u'], '']
ped_pick = [i for i in ok if 'P' in (i.get('f') or '') and i not in pick]
if ped_pick:
    zap += ['🙋 VOCÊS PEDIRAM, A GENTE ACHOU (menor preço que achamos + cupom):']
    for i in ped_pick:
        zap += [f"{EMO.get(i['c'], '🔥')} {curto(i['t'])}", (f"De {brl(i['o'])} por {brl(i['p'])} ({i['off']}% OFF)" if i.get('o') else brl(i['p'])), i['u']]
        POST[i['u']] = AGORA.date().isoformat()
    zap += ['Pediu e não achou ainda? Manda no "Conta pra gente" lá no site 😉', '']
if amz_pick:
    zap += ['🏆 TOP MAIS VENDIDOS DA AMAZON (toca e vê o preço):']
    for i in amz_pick:
        zap += [f"{EMO.get(i['c'], '🔥')} {curto(i['t'])}", i['u']]
    zap += ['']
zap += [f'👉 Mais de {total:,} ofertas no link da bio. Achou uma boa? Coloca no carrinho pra não perder!'.replace(',', '.'), '', '🤖 Seleção montada com ajuda de IA']
open(os.path.join(D, 'ofertas.json'), 'w', encoding='utf-8').write(json.dumps(DATA, ensure_ascii=False, separators=(',', ':')))
open(os.path.join(D, 'story.txt'), 'w', encoding='utf-8').write('\n'.join(story))
open(os.path.join(D, 'canal.txt'), 'w', encoding='utf-8').write('\n'.join(zap))
print('--- STORY ---'); print('\n'.join(story))
print('--- CANAL ---'); print('\n'.join(zap))
