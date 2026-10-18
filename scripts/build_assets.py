"""Builds the animated SVG cards used in the profile README.

Usage:  python scripts/build_assets.py
Output: assets/*.svg, each with its own subset fonts embedded, so nothing is loaded externally.
Fonts:  General Sans and Fira Code (TTF), read from PROFILE_FONTS.
Colors: Catppuccin Mocha.
"""

import base64, html, io, logging, math, os, re
from fontTools.ttLib import TTFont
from fontTools import subset

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'assets')
ICONS = os.path.join(ROOT, 'scripts', 'icons')
FONT_DIR = os.environ.get('PROFILE_FONTS', 'C:/Users/Ezentere/tools/fonts')
FONTS = {'gs6': 'GeneralSans-600.ttf', 'gs5': 'GeneralSans-500.ttf', 'fc4': 'FiraCode-400.ttf', 'fc5': 'FiraCode-500.ttf'}

C = dict(crust='#11111b', mantle='#181825', base='#1e1e2e', s0='#313244', s1='#45475a', ov='#6c7086', sub='#a6adc8', text='#cdd6f4',
         mauve='#cba6f7', blue='#89b4fa', sapph='#74c7ec', teal='#94e2d5', green='#a6e3a1', yellow='#f9e2af', peach='#fab387', red='#f38ba8', pink='#f5c2e7')

logging.getLogger('fontTools.subset').setLevel(logging.ERROR)
_fonts = {k: TTFont(os.path.join(FONT_DIR, v)) for k, v in FONTS.items()}


def width(font, s, size, ls=0.0):
    f = _fonts[font]
    cmap, hmtx, upm = f.getBestCmap(), f['hmtx'], f['head'].unitsPerEm
    return sum(hmtx[cmap.get(ord(ch), cmap[ord('?')])][0] for ch in s) * size / upm + ls * len(s)


def esc(s):
    return html.escape(s, quote=False)


def font_css(svg_body):
    chars = set(''.join(html.unescape(t) for t in re.findall(r'>([^<>]+)<', svg_body))) | set('0123456789 ')
    css = []
    used = ' '.join(re.findall(r'class="([^"]*)"', svg_body)).split()
    for key in _fonts:
        if key not in used:
            continue
        sub = subset.Subsetter(subset.Options())
        sub.populate(text=''.join(chars))
        ff = TTFont(os.path.join(FONT_DIR, FONTS[key]))
        sub.subset(ff)
        ff.flavor = 'woff2'
        buf = io.BytesIO()
        ff.save(buf)
        css.append(f"@font-face{{font-family:'{key}';src:url(data:font/woff2;base64,{base64.b64encode(buf.getvalue()).decode()}) format('woff2')}}")
    css.append(".gs6{font-family:'gs6',ui-sans-serif,system-ui,sans-serif}.gs5{font-family:'gs5',ui-sans-serif,system-ui,sans-serif}")
    css.append(".fc4{font-family:'fc4',ui-monospace,Consolas,monospace;white-space:pre}.fc5{font-family:'fc5',ui-monospace,Consolas,monospace;white-space:pre}")
    return ''.join(css)


COMMON_CSS = '''
.tw{animation:tw 4s ease-in-out infinite}
@keyframes tw{0%,100%{opacity:.1}50%{opacity:.75}}
.blink{animation:blink 1.1s step-end infinite}
@keyframes blink{50%{opacity:0}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
'''


def card(w, h, title, body, css='', defs=''):
    """Dark rounded card with a rotating gradient border. Looks the same on GitHub's light and dark themes."""
    frame = f'''<clipPath id="card"><rect width="{w}" height="{h}" rx="16"/></clipPath>
<linearGradient id="bd" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{C['mauve']}"/><stop offset=".35" stop-color="{C['blue']}"/><stop offset=".65" stop-color="{C['s0']}"/><stop offset="1" stop-color="{C['pink']}"/>
<animateTransform attributeName="gradientTransform" type="rotate" values="0 .5 .5;360 .5 .5" dur="12s" repeatCount="indefinite"/></linearGradient>'''
    inner = f'<g clip-path="url(#card)"><rect width="{w}" height="{h}" fill="{C["crust"]}"/>{body}</g><rect x=".75" y=".75" width="{w - 1.5}" height="{h - 1.5}" rx="15.5" fill="none" stroke="url(#bd)" stroke-width="1.5" opacity=".8"/>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">
<title>{esc(title)}</title>
<defs><style>{font_css(inner)}{COMMON_CSS}{css}</style>{frame}{defs}</defs>
{inner}
</svg>
'''


def stars(w, h, n, seed):
    out = []
    for i in range(n):
        x = (seed * 7919 + i * 104729) % (w * 10) / 10
        y = (seed * 3571 + i * 15485863) % (h * 10) / 10
        r = (0.6, 1.0, 1.3)[i % 3]
        out.append(f'<circle class="tw" cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{C["text"]}" style="animation-duration:{2.6 + (i * 7 % 30) / 10:.1f}s;animation-delay:-{(i * 13 % 50) / 10:.1f}s"/>')
    return ''.join(out)


def glow(gid, color, op):
    return f'<radialGradient id="{gid}"><stop offset="0" stop-color="{color}" stop-opacity="{op}"/><stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>'


def kt(times, T):
    return ';'.join(f'{min(t / T, 1):.4f}' for t in times)


def typed(uid, x, y, s, font, size, cls, T, t0, t_erase=None, t_hide=None, cps=24, ecps=60, cursor=True):
    """Typewriter line driven by SMIL: the clip rect grows one character at a time.

    Width never drops to 0 because Safari mishandles zero-area clip paths.
    t_erase: when the line starts deleting itself. t_hide: when it disappears at the end of the loop."""
    cw = width(font, 'a', size)
    n = len(s)
    times, vals = [0.0], [0.1]
    for k in range(1, n + 1):
        times.append(t0 + k / cps)
        vals.append(k * cw + 2)
    if t_erase is not None:
        for k in range(n - 1, -1, -1):
            times.append(t_erase + (n - k) / ecps)
            vals.append(max(k * cw, 0.1) + (2 if k else 0))
    elif t_hide is not None:
        times.append(t_hide)
        vals.append(0.1)
    if times[1] <= 0:
        times[1] = 0.001
    wv = ';'.join(f'{v:.1f}' for v in vals)
    cv = ';'.join(f'{x + max(v - 2, 0):.1f}' for v in vals)
    k = kt(times, T)
    out = f'''<clipPath id="{uid}"><rect x="{x - 1}" y="{y - size}" height="{size * 1.5}" width="0.1"><animate attributeName="width" dur="{T}s" repeatCount="indefinite" calcMode="discrete" values="{wv}" keyTimes="{k}"/></rect></clipPath>
<text x="{x}" y="{y}" class="{font} {cls}" font-size="{size}" textLength="{n * cw:.1f}" lengthAdjust="spacingAndGlyphs" clip-path="url(#{uid})">{esc(s)}</text>'''
    if cursor:
        end = (t_erase + n / ecps + 0.15) if t_erase is not None else (t_hide if t_hide is not None else T)
        vis = f'0;1;0' if end < T else '0;1'
        vkt = kt([0, t0, end], T) if end < T else kt([0, t0], T)
        out += f'''<g opacity="0"><animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" calcMode="discrete" values="{vis}" keyTimes="{vkt}"/>
<rect class="blink" x="{x}" y="{y - size * .78:.1f}" width="{cw * .55:.1f}" height="{size * .95:.1f}" fill="{C['mauve']}"><animate attributeName="x" dur="{T}s" repeatCount="indefinite" calcMode="discrete" values="{cv}" keyTimes="{k}"/></rect></g>'''
    return out


def fade(T, t_in, t_out=None, dur=0.35):
    if t_out is None:
        return f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" values="0;0;1;1" keyTimes="{kt([0, t_in, t_in + dur, T], T)}"/>'
    return f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" values="0;0;1;1;0;0" keyTimes="{kt([0, t_in, t_in + dur, t_out, t_out + dur, T], T)}"/>'


def pill(x, y, label, font='gs5', size=14, pad=14, h=30, fill=None, stroke=None, color=None, ls=0.0):
    w = width(font, label, size, ls) + pad * 2
    return w, f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{h / 2}" fill="{fill or C["base"]}" stroke="{stroke or C["s0"]}"/><text x="{x + pad}" y="{y + h / 2 + size * .36:.1f}" class="{font}" font-size="{size}" fill="{color or C["text"]}" letter-spacing="{ls}">{esc(label)}</text>'


# Hero
def hero():
    W, H = 1000, 360
    defs = glow('gM', C['mauve'], .38) + glow('gB', C['blue'], .28) + glow('gT', C['teal'], .16)
    name = 'Gürkan Karadağ'
    nsize = 70
    nx, ny = 56, 158
    nw = width('gs6', name, nsize)
    defs += f'''<linearGradient id="ng" gradientUnits="userSpaceOnUse" x1="{nx}" y1="0" x2="{nx + nw}" y2="0" spreadMethod="reflect">
<stop offset="0" stop-color="{C['mauve']}"/><stop offset=".45" stop-color="{C['blue']}"/><stop offset=".8" stop-color="{C['teal']}"/><stop offset="1" stop-color="{C['pink']}"/>
<animateTransform attributeName="gradientTransform" type="translate" values="0 0;{nw:.0f} 0;0 0" dur="10s" repeatCount="indefinite"/></linearGradient>
<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="{C['text']}" opacity=".06"/></pattern>
<linearGradient id="fadeTop" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".22" stop-color="#fff" stop-opacity="1"/></linearGradient>
<mask id="chatMask"><rect x="640" y="86" width="320" height="236" fill="url(#fadeTop)"/></mask>'''
    b = [f'<rect width="{W}" height="{H}" fill="url(#dots)"/>',
         f'<g><ellipse cx="170" cy="40" rx="340" ry="230" fill="url(#gM)"/><animateTransform attributeName="transform" type="translate" values="0 0;60 30;0 0" dur="16s" repeatCount="indefinite"/></g>',
         f'<g><ellipse cx="820" cy="330" rx="360" ry="240" fill="url(#gB)"/><animateTransform attributeName="transform" type="translate" values="0 0;-50 -20;0 0" dur="19s" repeatCount="indefinite"/></g>',
         f'<ellipse cx="520" cy="380" rx="300" ry="120" fill="url(#gT)"/>',
         stars(W, H, 34, 3)]

    # Open to work badge
    label = 'OPEN TO WORK · TÜRKİYE'
    pw = width('fc5', label, 12, 1.6) + 46
    b.append(f'<g class="pop" style="animation-delay:.1s"><rect x="56" y="38" width="{pw:.1f}" height="30" rx="15" fill="{C["base"]}" fill-opacity=".8" stroke="{C["s0"]}"/>'
             f'<circle cx="76" cy="53" r="4.5" fill="{C["green"]}"/><circle class="ping" cx="76" cy="53" r="4.5" fill="none" stroke="{C["green"]}"/>'
             f'<text x="92" y="57.5" class="fc5" font-size="12" letter-spacing="1.6" fill="{C["sub"]}">{label}</text></g>')

    # Name, letters rise in one by one
    x = nx
    for i, ch in enumerate(name):
        if ch != ' ':
            b.append(f'<text x="{x:.1f}" y="{ny}" class="gs6 rise" font-size="{nsize}" fill="url(#ng)" style="animation-delay:{.25 + i * .055:.2f}s">{esc(ch)}</text>')
        x += width('gs6', ch, nsize)

    # Rotating tagline
    lines = ['Full Stack Developer', 'Building npoq for 100+ Kick streamers', 'Shipped ClutchBoard, a Valorant desktop app', 'Next.js · React · Node.js · TypeScript', 'From the database to the last pixel']
    slot, T = 4.6, 4.6 * len(lines)
    b.append(f'<text x="58" y="214" class="fc5" font-size="20" fill="{C["mauve"]}">›</text>')
    for i, s in enumerate(lines):
        t0 = i * slot + .3
        b.append(typed(f'tg{i}', 84, 214, s, 'fc4', 20, 'tl', T, t0, t_erase=t0 + len(s) / 24 + 2.4))

    # Tech chips
    x = 56
    for i, s in enumerate(['Next.js', 'React', 'Node.js', 'TypeScript', 'MongoDB']):
        w, p = pill(x, 248, s, size=14, fill=C['base'], stroke=C['s1'])
        b.append(f'<g class="pop" style="animation-delay:{1.3 + i * .12:.2f}s">{p}</g>')
        x += w + 10

    # npoq chat window with looping messages
    cx0, cy0, cw_, ch_ = 640, 40, 310, 284
    b.append(f'<rect x="{cx0}" y="{cy0}" width="{cw_}" height="{ch_}" rx="14" fill="{C["base"]}" fill-opacity=".85" stroke="{C["s0"]}"/>')
    b.append(f'<path d="M{cx0} {cy0 + 14} a14 14 0 0 1 14 -14 h{cw_ - 28} a14 14 0 0 1 14 14 v26 h-{cw_} z" fill="{C["mantle"]}"/>')
    b.append(f'<circle cx="{cx0 + 20}" cy="{cy0 + 20}" r="4.5" fill="{C["red"]}" class="live"/><text x="{cx0 + 32}" y="{cy0 + 24.5}" class="fc5" font-size="12" letter-spacing="1.4" fill="{C["red"]}">LIVE</text>')
    b.append(f'<text x="{cx0 + cw_ - 16}" y="{cy0 + 24.5}" text-anchor="end" class="fc4" font-size="12" fill="{C["ov"]}">chat · npoq bot</text>')
    msgs = [('ali_k', C['peach'], '!points'), (None, None, '@ali_k has 2,450 points'),
            ('mert34', C['green'], '!join'), (None, None, '@mert34 joined the giveaway (37)'),
            ('ecee', C['pink'], '!level'), (None, None, '@ecee is level 12 · 340 XP to go'),
            ('deniz_c', C['sapph'], '!tts hello chat'), (None, None, '@deniz_c TTS queued (#3)')]
    rh, n = 42, len(msgs)
    rows = []
    for j, (user, col, text) in enumerate(msgs * 2):
        ry = cy0 + 70 + j * rh
        if user:
            rows.append(f'<text x="{cx0 + 18}" y="{ry}" class="gs6" font-size="14" fill="{col}">{user}<tspan class="gs5" fill="{C["text"]}" dx="8">{esc(text)}</tspan></text>')
        else:
            rows.append(f'<rect x="{cx0 + 16}" y="{ry - 14}" width="44" height="19" rx="5" fill="{C["mauve"]}" fill-opacity=".18" stroke="{C["mauve"]}" stroke-opacity=".5"/>'
                        f'<text x="{cx0 + 38}" y="{ry}" text-anchor="middle" class="fc5" font-size="11" fill="{C["mauve"]}">npoq</text>'
                        f'<text x="{cx0 + 70}" y="{ry}" class="gs5" font-size="14" fill="{C["sub"]}">{esc(text)}</text>')
    step, TT = 1.7, 1.7 * n
    # Hold, then ease up one row. Messages are drawn twice so the loop is seamless.
    v2, t2 = ['0 0'], [0]
    for k in range(n):
        t2 += [k * step + 1.25, (k + 1) * step]
        v2 += [f'0 {-k * rh}', f'0 {-(k + 1) * rh}']
    splines = ';'.join(['0 0 1 1', '.4 0 .2 1'] * n)
    b.append(f'<g clip-path="url(#chatClip)" mask="url(#chatMask)"><g><animateTransform attributeName="transform" type="translate" dur="{TT}s" repeatCount="indefinite" calcMode="spline" keySplines="{splines}" values="{";".join(v2)}" keyTimes="{kt(t2, TT)}"/>{"".join(rows)}</g></g>')
    defs += f'<clipPath id="chatClip"><rect x="{cx0}" y="{cy0 + 41}" width="{cw_}" height="{ch_ - 41 - 46}"/></clipPath>'
    b.append(f'<rect x="{cx0 + 14}" y="{cy0 + ch_ - 38}" width="{cw_ - 28}" height="26" rx="8" fill="{C["mantle"]}" stroke="{C["s0"]}"/><text x="{cx0 + 26}" y="{cy0 + ch_ - 20.5}" class="gs5" font-size="13" fill="{C["ov"]}">Send a message…</text>')

    css = '''
.rise{opacity:0;animation:rise .7s cubic-bezier(.2,.8,.2,1) forwards}
@keyframes rise{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}
.pop{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .5s cubic-bezier(.2,.9,.3,1.3) forwards}
@keyframes pop{from{opacity:0;transform:scale(.85)}to{opacity:1;transform:none}}
.ping{transform-box:fill-box;transform-origin:center;animation:ping 2s ease-out infinite}
@keyframes ping{from{transform:scale(1);opacity:.8}to{transform:scale(3.2);opacity:0}}
.live{animation:live 1.6s ease-in-out infinite}
@keyframes live{50%{opacity:.35}}
.tl{fill:#cdd6f4}
@media (prefers-reduced-motion:reduce){.rise,.pop{opacity:1}}
'''
    return card(W, H, 'Gürkan Karadağ — Full Stack Developer', ''.join(b), css, defs)


# Terminal
def terminal():
    W, H, T = 1000, 342, 17.0
    b = [stars(W, H, 18, 7),
         f'<rect x="0" y="0" width="{W}" height="40" fill="{C["mantle"]}"/><line x1="0" y1="40" x2="{W}" y2="40" stroke="{C["s0"]}"/>',
         f'<circle cx="24" cy="20" r="6" fill="{C["red"]}"/><circle cx="44" cy="20" r="6" fill="{C["yellow"]}"/><circle cx="64" cy="20" r="6" fill="{C["green"]}"/>',
         f'<text x="{W / 2}" y="24.5" text-anchor="middle" class="fc4" font-size="13" fill="{C["ov"]}">gurkan@karadag: ~</text>',
         f'<rect class="scan" x="0" y="40" width="{W}" height="60" fill="url(#scanG)"/>']
    defs = f'<linearGradient id="scanG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C["mauve"]}" stop-opacity="0"/><stop offset=".5" stop-color="{C["mauve"]}" stop-opacity=".05"/><stop offset="1" stop-color="{C["mauve"]}" stop-opacity="0"/></linearGradient>'
    session = [('whoami', [('Gürkan Karadağ — Full Stack Developer', C['text'])]),
               ('cat now.txt', [('Building npoq.net: chatbot, OBS overlays and stats for Kick streamers (100+ active)', C['blue']), ('Shipped ClutchBoard v0.5: Valorant stats desktop app (Tauri · Rust · React)', C['red'])]),
               ('cat stack.txt', [('Next.js · React · TypeScript · Node.js · Express · MongoDB · PostgreSQL', C['peach'])]),
               ('echo $STATUS', [('open to work · remote / hybrid · can start immediately', C['green'])])]
    y, t, hide = 72, .5, T - 1.4
    for i, (cmd, outs) in enumerate(session):
        b.append(f'<g opacity="0">{fade(T, t, hide)}<text x="28" y="{y}" class="fc5" font-size="15" fill="{C["green"]}">~</text><text x="44" y="{y}" class="fc5" font-size="15" fill="{C["mauve"]}">›</text></g>')
        b.append(typed(f'tc{i}', 62, y, cmd, 'fc4', 15, 'tl', T, t, t_hide=hide + .35, cps=16, cursor=False))
        t += len(cmd) / 16 + .35
        for s, col in outs:
            y += 24
            b.append(f'<text x="28" y="{y}" class="fc4" font-size="15" fill="{col}" opacity="0">{fade(T, t, hide)}{esc(s)}</text>')
            t += .45
        y += 30
    b.append(f'<g opacity="0">{fade(T, t, hide)}<text x="28" y="{y}" class="fc5" font-size="15" fill="{C["green"]}">~</text><text x="44" y="{y}" class="fc5" font-size="15" fill="{C["mauve"]}">›</text>'
             f'<rect class="blink" x="62" y="{y - 12}" width="8.5" height="15" fill="{C["mauve"]}"/></g>')
    css = '''
.tl{fill:#cdd6f4}
.scan{animation:scan 6s linear infinite}
@keyframes scan{from{transform:translateY(-60px)}to{transform:translateY(342px)}}
'''
    return card(W, H, 'Terminal: whoami — Gürkan Karadağ, Full Stack Developer. Building npoq for Kick streamers, shipped ClutchBoard for Valorant. Open to work.', ''.join(b), css, defs)


# Tech orbit
ICON_COLORS = {'react': '#61DAFB', 'nextdotjs': '#FFFFFF', 'typescript': '#3178C6', 'tailwindcss': '#06B6D4', 'nodedotjs': '#5FA04E', 'express': '#FFFFFF',
               'mongodb': '#47A248', 'postgresql': '#4169E1', 'socketdotio': '#FFFFFF', 'prisma': '#FFFFFF', 'python': '#3776AB', 'git': '#F05032', 'tauri': '#24C8DB', 'rust': '#DEA584'}
ICON_LABELS = {'react': 'React', 'nextdotjs': 'Next.js', 'typescript': 'TypeScript', 'tailwindcss': 'Tailwind', 'nodedotjs': 'Node.js', 'express': 'Express',
               'mongodb': 'MongoDB', 'postgresql': 'PostgreSQL', 'socketdotio': 'Socket.IO', 'prisma': 'Prisma', 'python': 'Python', 'git': 'Git', 'tauri': 'Tauri', 'rust': 'Rust'}


def icon_path(slug):
    return re.search(r'<path d="([^"]+)"', open(os.path.join(ICONS, slug + '.svg'), encoding='utf-8').read()).group(1)


def orbit():
    W, H = 1000, 440
    cx, cy = 500, 228
    defs = glow('core', C['mauve'], .5) + glow('bgG', '#313a7a', .45)
    defs += f'''<linearGradient id="cs" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{C['teal']}"/><stop offset=".5" stop-color="{C['blue']}"/><stop offset="1" stop-color="{C['pink']}"/>
<animateTransform attributeName="gradientTransform" type="rotate" values="0 .5 .5;360 .5 .5" dur="6s" repeatCount="indefinite"/></linearGradient>
<linearGradient id="gk" gradientUnits="userSpaceOnUse" x1="{cx - 30}" y1="0" x2="{cx + 30}" y2="0" spreadMethod="reflect"><stop offset="0" stop-color="{C['mauve']}"/><stop offset=".5" stop-color="{C['blue']}"/><stop offset="1" stop-color="{C['teal']}"/>
<animateTransform attributeName="gradientTransform" type="translate" values="0 0;60 0;0 0" dur="5s" repeatCount="indefinite"/></linearGradient>
<linearGradient id="comet" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C['teal']}"/><stop offset="1" stop-color="{C['pink']}"/></linearGradient>'''
    rings = [dict(rx=235, ry=66, period=26, dir=1, slugs=['react', 'nextdotjs', 'typescript', 'tailwindcss', 'tauri']),
             dict(rx=430, ry=128, period=44, dir=-1, slugs=['nodedotjs', 'express', 'mongodb', 'postgresql', 'socketdotio', 'prisma', 'rust', 'python', 'git'])]
    back, front = [], []
    N = 72
    for r in rings:
        m = len(r['slugs'])
        for i, slug in enumerate(r['slugs']):
            ph = 2 * math.pi * i / m
            pos, sc, ob, of = [], [], [], []
            for k in range(N + 1):
                a = ph + r['dir'] * 2 * math.pi * k / N
                s = math.sin(a)
                pos.append(f'{cx + r["rx"] * math.cos(a):.1f} {cy + r["ry"] * s:.1f}')
                d = (s + 1) / 2
                sc.append(f'{.62 + .5 * d:.3f}')
                op = .35 + .65 * d
                ob.append(f'{op:.2f}' if s < 0 else '0')
                of.append(f'{op:.2f}' if s >= 0 else '0')
            dur = r['period']
            col = ICON_COLORS[slug]
            body = (f'<circle r="27" fill="{C["base"]}" stroke="{col}" stroke-opacity=".55" stroke-width="1.5"/>'
                    f'<g transform="translate(-13 -13) scale({26 / 24:.4f})"><path d="{icon_path(slug)}" fill="{col}"/></g>'
                    f'<text y="46" text-anchor="middle" class="gs5" font-size="13" fill="{C["text"]}">{ICON_LABELS[slug]}</text>')
            for lst, opv in ((back, ob), (front, of)):
                lst.append(f'<g><animateTransform attributeName="transform" type="translate" values="{";".join(pos)}" dur="{dur}s" repeatCount="indefinite"/>'
                           f'<g><animateTransform attributeName="transform" type="scale" values="{";".join(sc)}" dur="{dur}s" repeatCount="indefinite"/>'
                           f'<animate attributeName="opacity" values="{";".join(opv)}" dur="{dur}s" repeatCount="indefinite" calcMode="discrete"/>{body}</g></g>')
    b = [f'<ellipse cx="{cx}" cy="{cy}" rx="560" ry="300" fill="url(#bgG)"/>', stars(W, H, 46, 11),
         f'<text x="30" y="40" class="fc5" font-size="13" letter-spacing="1.5" fill="{C["mauve"]}">TECH STACK</text>',
         f'<text x="{W - 30}" y="40" text-anchor="end" class="fc4" font-size="13" fill="{C["sub"]}">inner · frontend &amp; desktop   |   outer · backend &amp; data</text>']
    for r in rings:
        b.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{r["rx"]}" ry="{r["ry"]}" fill="none" stroke="{C["s1"]}" stroke-dasharray="2 6" opacity=".7"/>')
    b.append(f'<ellipse cx="{cx}" cy="{cy}" rx="430" ry="128" fill="none" stroke="url(#comet)" stroke-width="2" stroke-linecap="round" pathLength="100" class="comet"/>')
    b += back
    b.append(f'<circle cx="{cx}" cy="{cy}" r="120" fill="url(#core)"/>'
             f'<circle cx="{cx}" cy="{cy}" r="56" class="pulse" fill="none" stroke="{C["mauve"]}"/>'
             f'<circle cx="{cx}" cy="{cy}" r="70" fill="none" stroke="{C["blue"]}" stroke-opacity=".5" stroke-dasharray="14 10" class="spin"/>'
             f'<circle cx="{cx}" cy="{cy}" r="54" fill="{C["crust"]}" stroke="url(#cs)" stroke-width="2.5"/>'
             f'<text x="{cx}" y="{cy + 13}" text-anchor="middle" class="gs6" font-size="38" fill="url(#gk)">GK</text>')
    b += front
    css = f'''
.comet{{stroke-dasharray:6 94;animation:run 14s linear infinite}}
@keyframes run{{from{{stroke-dashoffset:100}}to{{stroke-dashoffset:0}}}}
.spin{{transform-origin:{cx}px {cy}px;animation:spin 18s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.pulse{{transform-origin:{cx}px {cy}px;animation:pulse 3.4s ease-out infinite}}
@keyframes pulse{{from{{transform:scale(1);opacity:.7}}to{{transform:scale(2.2);opacity:0}}}}
'''
    desc = 'Tech stack in orbit. Inner orbit (frontend and desktop): React, Next.js, TypeScript, Tailwind, Tauri. Outer orbit (backend and data): Node.js, Express, MongoDB, PostgreSQL, Socket.IO, Prisma, Rust, Python, Git.'
    return card(W, H, desc, ''.join(b), css, defs)


# Project cards
def wrap(s, font, size, maxw):
    lines, cur = [], ''
    for w in s.split():
        t = (cur + ' ' + w).strip()
        if width(font, t, size) > maxw and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + [cur]


def motif_npoq(x, y):
    # OBS alert: slides in, timer bar runs down, slides out
    return f'''<g class="alert"><rect x="{x}" y="{y}" width="150" height="74" rx="10" fill="{C['base']}" stroke="{C['mauve']}" stroke-opacity=".6"/>
<text x="{x + 14}" y="{y + 26}" class="fc5" font-size="11" letter-spacing="1.2" fill="{C['mauve']}">NEW FOLLOWER</text>
<text x="{x + 14}" y="{y + 50}" class="gs6" font-size="18" fill="{C['text']}">ali_k</text>
<rect x="{x + 14}" y="{y + 60}" width="122" height="4" rx="2" fill="{C['s0']}"/><rect class="bar" x="{x + 14}" y="{y + 60}" width="122" height="4" rx="2" fill="{C['mauve']}"/></g>
<g transform="translate({x + 6} {y + 116})">{''.join(f'<rect class="eq" x="{i * 12}" y="-24" width="7" height="24" rx="2" fill="{C["teal"]}" style="animation-delay:-{(i * 37 % 10) / 10:.1f}s;animation-duration:{.8 + (i * 3 % 5) / 10:.1f}s"/>' for i in range(12))}</g>'''


def motif_repodle(x, y):
    word, cols = 'GUESS', [C['green'], C['yellow'], C['s1'], C['green'], C['green']]
    out = []
    for i, (ch, col) in enumerate(zip(word, cols)):
        tx = x + i * 30
        out.append(f'<g class="flip" style="animation-delay:{i * .25:.2f}s;transform-origin:{tx + 13}px {y + 13}px"><rect x="{tx}" y="{y}" width="26" height="26" rx="5" fill="{col}"/>'
                   f'<text x="{tx + 13}" y="{y + 18.5}" text-anchor="middle" class="gs6" font-size="15" fill="{C["crust"]}">{ch}</text></g>')
    for row in (1, 2):
        for i in range(5):
            out.append(f'<rect x="{x + i * 30}" y="{y + row * 32}" width="26" height="26" rx="5" fill="none" stroke="{C["s1"]}"/>')
    return ''.join(out)


def motif_ficonica(x, y):
    hues = [C['mauve'], C['blue'], C['teal'], C['peach'], C['pink'], C['green'], C['yellow'], C['sapph'], C['red']]
    out = []
    for i in range(9):
        cx, cy = x + (i % 3) * 44, y + (i // 3) * 34
        vals = ';'.join(hues[(i + k) % 9] for k in range(10))
        out.append(f'<rect x="{cx}" y="{cy}" width="34" height="26" rx="7" fill="{hues[i]}" fill-opacity=".85"><animate attributeName="fill" values="{vals}" dur="9s" repeatCount="indefinite"/>'
                   + (f'<animate attributeName="rx" values="7;13;3;7" dur="4s" repeatCount="indefinite"/>' if i == 4 else '') + '</rect>')
    return ''.join(out)


def motif_ancienda(x, y):
    tiles = [C['mauve'], C['blue'], C['peach'], C['teal']]
    rows = ''.join(f'<rect x="{x + 12}" y="{y + 14 + i * 34}" width="22" height="22" rx="6" fill="{c}"/><rect x="{x + 42}" y="{y + 17 + i * 34}" width="44" height="6" rx="3" fill="{C["sub"]}" opacity=".7"/><rect x="{x + 42}" y="{y + 28 + i * 34}" width="30" height="5" rx="2.5" fill="{C["ov"]}"/>'
                   for i, c in enumerate(tiles * 2))
    return (f'<clipPath id="ph"><rect x="{x}" y="{y}" width="100" height="120" rx="14"/></clipPath>'
            f'<rect x="{x}" y="{y}" width="100" height="120" rx="14" fill="{C["base"]}" stroke="{C["s1"]}"/>'
            f'<g clip-path="url(#ph)"><g><animateTransform attributeName="transform" type="translate" values="0 0;0 -136" dur="8s" repeatCount="indefinite"/>{rows}</g></g>'
            f'<rect x="{x + 36}" y="{y + 6}" width="28" height="5" rx="2.5" fill="{C["s1"]}"/>')


PROJECTS = [
    ('npoq', 'npoq.net', 'Chatbot, OBS overlays, alerts and stats for Kick streamers. Realtime giveaways, user scripts and TTS. Used by 100+ active streamers.', ['Next.js', 'Express', 'MongoDB', 'Socket.IO'], motif_npoq),
    ('repodle', 'repodle.com', 'Wordle-style daily guessing game for R.E.P.O. in 3 languages, with a shared backend and admin panel.', ['Next.js', 'Express', 'Prisma', 'PostgreSQL'], motif_repodle),
    ('ficonica', 'ficonica.com', 'Icon and favicon generator with color editing, SVG processing and PDF/ZIP export.', ['Next.js', 'Firebase', 'Zustand'], motif_ficonica),
    ('ancienda', 'ancienda.com', 'Freelance build for an AI iOS app studio: app showcase, blog and admin panel.', ['Next.js', 'Firebase', 'TinyMCE'], motif_ancienda),
]


def project(slug, url, desc, chips, motif):
    W, H = 490, 230
    title = {'npoq': 'npoq', 'repodle': 'Repodle', 'ficonica': 'Ficonica', 'ancienda': 'Ancienda'}[slug]
    b = [f'<ellipse cx="420" cy="20" rx="200" ry="140" fill="url(#pg)"/>', stars(W, H, 10, len(slug)),
         f'<text x="26" y="50" class="gs6" font-size="26" fill="{C["text"]}">{title}</text>',
         f'<text x="26" y="72" class="fc4" font-size="12.5" fill="{C["mauve"]}">↗ {url}</text>']
    for i, ln in enumerate(wrap(desc, 'gs5', 14, 280)):
        b.append(f'<text x="26" y="{104 + i * 21}" class="gs5" font-size="14" fill="{C["sub"]}">{esc(ln)}</text>')
    x = 26
    for c in chips:
        w, p = pill(x, 186, c, font='fc4', size=11.5, pad=10, h=24, fill=C['base'], stroke=C['s1'], color=C['text'])
        b.append(p)
        x += w + 8
    b.append(motif(330, 60))
    css = '''
.alert{animation:alert 5s cubic-bezier(.2,.8,.2,1) infinite}
@keyframes alert{0%{transform:translateX(180px);opacity:0}12%,78%{transform:none;opacity:1}90%,100%{transform:translateX(180px);opacity:0}}
.bar{transform-box:fill-box;transform-origin:left;animation:bar 5s linear infinite}
@keyframes bar{0%,12%{transform:scaleX(1)}78%,100%{transform:scaleX(0)}}
.eq{transform-box:fill-box;transform-origin:bottom;animation:eq 1s ease-in-out infinite alternate}
@keyframes eq{from{transform:scaleY(.2)}to{transform:scaleY(1)}}
.flip{animation:flip 6s ease-in-out infinite}
@keyframes flip{0%,4%{transform:scaleY(1)}8%{transform:scaleY(0)}12%,100%{transform:scaleY(1)}}
'''
    return card(W, H, f'{title} — {desc}', ''.join(b), css, glow('pg', C['mauve'], .22))


CB_RED = '#EF4458'  # ClutchBoard brand color
CB_MARK = 'M763.1,578.7 L646.8,579.2 L599.0,632.5 L574.3,645.1 L405.8,646.2 L240.0,787.8 L653.9,735.7Z M812.0,236.2 L434.9,236.2 L332.8,295.4 L212.0,770.3 L368.4,636.7 L436.0,371.7 L479.9,333.3 L671.5,332.8 L593.5,468.9 L767.5,347.6Z'


def clutchboard():
    """Wide featured card with a self-drawing RR chart, based on the app's profile screen."""
    W, H = 1000, 260
    desc = 'Valorant stats, match history and live match intel as a fast, private desktop app. Rank history, scoreboards with Performance Score, live match ranks and a game settings manager with a crosshair editor.'
    b = [f'<ellipse cx="820" cy="40" rx="320" ry="200" fill="url(#rg)"/>', stars(W, H, 18, 21),
         f'<g transform="translate(30 26) scale({44 / 616:.4f}) translate(-204 -228.2)"><path d="{CB_MARK}" fill="{CB_RED}"/></g>',
         f'<text x="86" y="62" class="gs6" font-size="32" fill="{C["text"]}">ClutchBoard</text>']
    nx = 86 + width('gs6', 'ClutchBoard', 32) + 14
    pw, p = pill(nx, 39, 'NEW · v0.5.1', font='fc5', size=11, pad=10, h=24, fill='#3a1a22', stroke=CB_RED, color=CB_RED, ls=1)
    b.append(f'<g class="newp">{p}</g>')
    b.append(f'<text x="32" y="96" class="fc4" font-size="12.5" fill="{C["mauve"]}">↗ github.com/Gurkankaradag0/ClutchBoard</text>')
    for i, ln in enumerate(wrap(desc, 'gs5', 14.5, 520)):
        b.append(f'<text x="32" y="{128 + i * 22}" class="gs5" font-size="14.5" fill="{C["sub"]}">{esc(ln)}</text>')
    x = 32
    for c in ['Tauri v2', 'Rust', 'React 19', 'TypeScript', 'TanStack Query', 'i18next']:
        w, p = pill(x, 210, c, font='fc4', size=11.5, pad=10, h=24, fill=C['base'], stroke=C['s1'], color=C['text'])
        b.append(p)
        x += w + 8

    # App window with RR chart
    px, py, pw_, ph = 610, 28, 360, 204
    b.append(f'<rect x="{px}" y="{py}" width="{pw_}" height="{ph}" rx="12" fill="{C["base"]}" fill-opacity=".9" stroke="{C["s0"]}"/>')
    b.append(f'<text x="{px + 18}" y="{py + 28}" class="fc5" font-size="11" letter-spacing="1.4" fill="{C["sub"]}">RR HISTORY</text>')
    tabs = ['K/D', 'HS%', 'WIN%', 'PERF']
    tx = px + pw_ - 18
    for t in reversed(tabs):
        tw = width('fc4', t, 10.5) + 14
        tx -= tw
        b.append(f'<rect x="{tx:.1f}" y="{py + 15}" width="{tw:.1f}" height="19" rx="5" fill="{C["mantle"]}" stroke="{C["s0"]}"/><text x="{tx + 7:.1f}" y="{py + 28.5}" class="fc4" font-size="10.5" fill="{C["ov"]}">{esc(t)}</text>')
        tx -= 6
    gx0, gx1, gy0, gy1 = px + 20, px + pw_ - 24, py + 56, py + ph - 22
    for k in range(4):
        gy = gy0 + k * (gy1 - gy0) / 3
        b.append(f'<line x1="{gx0}" y1="{gy:.1f}" x2="{gx1}" y2="{gy:.1f}" stroke="{C["s0"]}" stroke-dasharray="3 5"/>')
    ys = [.78, .7, .74, .58, .63, .5, .55, .42, .47, .36, .4, .28, .2]
    pts = [(gx0 + i * (gx1 - gx0) / (len(ys) - 1), gy0 + v * (gy1 - gy0)) for i, v in enumerate(ys)]
    line = 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts)
    area = line + f' L{gx1},{gy1} L{gx0},{gy1} Z'
    ex, ey = pts[-1]
    b.append(f'<path d="{area}" fill="url(#ar)" class="area"/>')
    b.append(f'<path d="{line}" fill="none" stroke="{CB_RED}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" pathLength="100" class="draw"/>')
    b.append(f'<g class="endp"><circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{CB_RED}"/><circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="none" stroke="{CB_RED}" class="ring"/></g>')
    b.append(f'<g class="rankup"><rect x="{ex - 92:.1f}" y="{ey - 36:.1f}" width="80" height="22" rx="6" fill="{CB_RED}"/><text x="{ex - 52:.1f}" y="{ey - 21:.1f}" text-anchor="middle" class="fc5" font-size="11" letter-spacing="1" fill="#fff">RANK UP</text></g>')
    defs = glow('rg', CB_RED, .2) + f'<linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CB_RED}" stop-opacity=".28"/><stop offset="1" stop-color="{CB_RED}" stop-opacity="0"/></linearGradient>'
    # 7s loop: line draws, area and end point fade in, RANK UP pops, everything fades out
    css = f'''
.draw{{stroke-dasharray:100;animation:draw 7s cubic-bezier(.5,0,.2,1) infinite}}
@keyframes draw{{0%{{stroke-dashoffset:100}}35%,88%{{stroke-dashoffset:0;opacity:1}}96%,100%{{stroke-dashoffset:0;opacity:0}}}}
.area{{animation:area 7s ease infinite}}
@keyframes area{{0%,30%{{opacity:0}}42%,88%{{opacity:1}}96%,100%{{opacity:0}}}}
.endp{{animation:area 7s ease infinite}}
.ring{{transform-box:fill-box;transform-origin:center;animation:ping 1.6s ease-out infinite}}
@keyframes ping{{from{{transform:scale(1);opacity:.8}}to{{transform:scale(3);opacity:0}}}}
.rankup{{transform-box:fill-box;transform-origin:center;animation:rankup 7s cubic-bezier(.2,.9,.3,1.3) infinite}}
@keyframes rankup{{0%,40%{{opacity:0;transform:translateY(8px) scale(.8)}}48%,86%{{opacity:1;transform:none}}94%,100%{{opacity:0;transform:none}}}}
.newp{{animation:newp 2.4s ease-in-out infinite}}
@keyframes newp{{50%{{opacity:.55}}}}
'''
    return card(W, H, f'ClutchBoard — {desc}', ''.join(b), css, defs)


# Divider and footer
def divider():
    W, H = 1000, 24
    defs = f'''<linearGradient id="ln" x1="0" x2="1"><stop offset="0" stop-color="{C['s0']}" stop-opacity="0"/><stop offset=".5" stop-color="{C['s1']}"/><stop offset="1" stop-color="{C['s0']}" stop-opacity="0"/></linearGradient>
<linearGradient id="cm" x1="0" x2="1"><stop offset="0" stop-color="{C['mauve']}" stop-opacity="0"/><stop offset="1" stop-color="{C['teal']}"/></linearGradient>'''
    body = (f'<line x1="0" y1="12" x2="{W}" y2="12" stroke="url(#ln)"/>'
            f'<line x1="0" y1="12" x2="{W}" y2="12" stroke="url(#cm)" stroke-width="2" stroke-linecap="round" pathLength="100" class="cmt"/>'
            f'<rect x="{W / 2 - 4}" y="8" width="8" height="8" transform="rotate(45 {W / 2} 12)" fill="{C["mauve"]}"/>')
    css = '.cmt{stroke-dasharray:14 86;animation:cmt 5s linear infinite}@keyframes cmt{from{stroke-dashoffset:100}to{stroke-dashoffset:0}}' + COMMON_CSS
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" aria-hidden="true"><defs><style>{css}</style>{defs}</defs>{body}</svg>
'''


def footer():
    W, H = 1000, 150

    def wave(amp, y0, ph, n=4):
        pts = []
        for k in range(0, 2 * W + 1, 20):
            pts.append(f'{k},{y0 + amp * math.sin(2 * math.pi * n * k / (2 * W) * 2 + ph):.1f}')
        return f'M{pts[0]} L' + ' '.join(pts[1:]) + f' L{2 * W},{H} L0,{H} Z'
    b = [stars(W, H, 20, 5)]
    for i, (col, op, amp, y0, dur) in enumerate([(C['mauve'], .22, 10, 92, 14), (C['blue'], .2, 12, 104, 10), (C['teal'], .16, 8, 118, 7)]):
        b.append(f'<path d="{wave(amp, y0, i)}" fill="{col}" fill-opacity="{op}"><animateTransform attributeName="transform" type="translate" values="0 0;-{W} 0" dur="{dur}s" repeatCount="indefinite"/></path>')
    b.append(f'<text x="{W / 2}" y="54" text-anchor="middle" class="gs6" font-size="24" fill="{C["text"]}">Thanks for stopping by</text>')
    b.append(f'<text x="{W / 2}" y="80" text-anchor="middle" class="fc4" font-size="13" fill="{C["mauve"]}">gurkankaradag.me</text>')
    return card(W, H, 'Thanks for stopping by — gurkankaradag.me', ''.join(b))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    files = {'hero.svg': hero(), 'terminal.svg': terminal(), 'tech-orbit.svg': orbit(), 'divider.svg': divider(), 'footer.svg': footer(), 'project-clutchboard.svg': clutchboard()}
    for p in PROJECTS:
        files[f'project-{p[0]}.svg'] = project(*p)
    for name, svg in files.items():
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            f.write(svg)
        print(f'{name:24} {len(svg.encode()) / 1024:6.1f} KB')
