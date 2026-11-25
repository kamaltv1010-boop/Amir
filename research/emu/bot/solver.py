# -*- coding: utf-8 -*-
"""حلّال ألغاز فرز الألوان لبوت Magic Sort (بحث فقط).

الواجهة المشتركة مع vision.py:
    state = {"tubes": [{"x": int, "y": int, "cap": int, "layers": [str, ...]}, ...]}
    الطبقات من الأسفل إلى الأعلى، و"?" طبقة مخفية.
    plan(state) -> [(i, j), ...]   (فهارس في state["tubes"])

القواعد: تُصبّ الكتلة العليا المتصلة من لون واحد في قارورة فارغة أو قمّتها من
اللون نفسه وفيها فراغ، ويُصبّ ما يتّسع فقط. الطبقة المخفية لا تطابق شيئاً ولا
تُعرف إلا حين تصير في القمّة. الهدف: كل قارورة غير فارغة من لون واحد، وكل لون
في قارورة واحدة (أو كل قواريره ممتلئة).

الاستراتيجية:
  * بلا طبقات مخفية: بحث A* موزون (f = g + w*h) ثم بحث عمقي مرتّب إن نفدت
    الميزانية، ثم «أفضل تقدّم» إن لم يُعثر على حل. يعيد الحل كاملاً.
  * مع طبقات مخفية (كل "?" رمز مجهول لا يطابق شيئاً ولا يُصبّ): تصويت عيّنات
    (PIMC): توزيعات عشوائية للمخفي تحترم عدد كل لون، حلّ كامل لكل عيّنة، ثم تُختار
    الحركة التي تبقى بعدها أكثر العيّنات قابلة للحل (والتعادل: الكشف أولاً، ثم
    الحفاظ على القوارير الفارغة). يعيد حركة واحدة ويُعاد التخطيط بعد كل حركة.
    الاحتياط: بحث «أفضل أولاً» عن أقصر تسلسل يكشف طبقة جديدة بعقوبة لاستهلاك
    الفارغات، ثم «أفضل تقدّم».
  * لا يُصبّ من قارورة منتهية، ولا تُنقل قارورة أحادية اللون إلى قارورة فارغة،
    ولا يُصبّ جزء من قارورة أحادية اللون، ولا تُكرَّر حالة سبق المرور بها (avoid).
  * سعة القارورة الطويلة تُرفع إلى عدد طبقات لونها الظاهرة إن قرأتها الرؤية أقل.
  * المفاتيح (من المرحلة 63؛ "keys" في القارورة = مواضع طبقات عليها مفتاح): كل مفتاح يفتح باباً
    خشبياً يخفي قوارير، فاللغز الظاهر ناقص حتى تُفتح. ما دام مفتاح عالقاً يُبحث أولاً عن أقصر تسلسل
    آمن (عقوبة لاستهلاك الفارغات) يكشف طبقته (لا شيء بلون آخر فوقها: هكذا انفتح الباب في المرحلتين
    63 و74)، أو يكشف الطبقة المخفية التي فوقها؛ ومفتاح مكشوف من البداية (لم يطر) يُصبّ لونه خارجها.
    إن لم يوجد تسلسل: لا تُدفن طبقة مفتاح تحت سائل آخر في الحركة الأولى ما دام بديل.
  * ذاكرة الأبواب (plan(doors=...)، التشغيل 12): ما خلف الباب ثابت لكل بداية، فإن عرفه السائق من محاولة سابقة كله (كل مفتاح
    عالق معروف بابه، ولا طبقة مخفية في الحالة ولا خلف الأبواب) يُبحث أولاً في المسألة كلها (_door_search: القوارير المقفلة
    تُلحق بالحالة ولا تُلمس حتى يتحرّر مفتاح بابها) عن حلّ كامل بكل باب مفتوحاً، والخطة تتوقف عند أول باب ينفتح. ومع معرفة
    ناقصة أو بلا حلّ في الميزانية فالمنطق المعتاد كما هو. plan(vary>0) يكسر التعادل عشوائياً (تنويع المحاولات المتكرّرة).
  * القوارير المغطّاة ("blocked": True، تحت ستارة من المرحلة 33 تقريباً أو كيس من 80) محتواها مجهول ولا يُصبّ منها ولا فيها:
    لا يراها الحلّال أبداً (تُحذف قبل البحث وتُعاد الفهارس الأصلية)، ولا تدخل في state_key ولا is_solved ولا الحركات
    القانونية؛ وحين تنكشف تصير قارورة عادية في القراءة التالية.
  * الجبس (من المرحلة 100، "cover": "plaster"): قالب يغلّف قارورة وينكسر حين تكتمل (تمتلئ بلون واحد) قارورة ظاهرة في خانة
    مجاورة له في صفّه، يميناً أو يساراً («كاسراته»: plaster_breakers بالمواضع). اللغز الظاهر وحده ناقص (ألوانه الباقية داخل
    الجبس، وترتيبه «محلولاً» ليس فوزاً)، فما دام جبس قائم بكاسرة لم تكتمل يُبحث أولاً عن أقصر تسلسل آمن يكمل كاسرة (مثل
    المفاتيح)، وإلا تميل بحوث الكشف والتقدّم والعيّنات إلى ملء الكاسرات. بلا جبس لا يتغيّر شيء (A* كما كان).
  * «Tag!» (من المرحلة 130، "accept": اسم لون في القارورة): قارورة موسومة لا يُصبّ فيها إلا لونها (ويُصبّ منها كالعادة)، وتكتمل
    ممتلئة بلونها كأي قارورة. القيد في توليد الحركات نفسه (_gen_moves عبر _ACCEPT) فيسري على كل البحوث والعيّنات وذاكرة الأبواب
    والمغطّاة، وفي legal_moves وapply_move (ومنها key_freed). الموسومة لا تماثل غير الموسومة (المفتاح القانوني والفارغات)، ونقل
    قارورة أحادية غير مكتملة إلى موسومة بلونها ليس عبثاً (يحرّر قارورة عادية تقبل كل لون). state_key يضيف لون الوسم عنصراً ثالثاً
    للموسومة وحدها، فلا يتغيّر شيء في المراحل بلا وسوم.
"""
from __future__ import annotations

import heapq
import itertools
import time

HIDDEN = -1          # كل طبقة مخفية تُرمَّز بـ -1 (لا تُصبّ ولا يُصبّ عليها)
INF = float("inf")

__all__ = [
    "plan", "apply_move", "is_solved", "legal_moves", "state_key",
    "describe", "key_freed", "plaster_breakers", "breaker_completed", "HIDDEN",
]


# ---------------------------------------------------------------- الترميز
def _is_hidden(c) -> bool:
    if not isinstance(c, str):
        return True
    c = c.strip().lower()
    return c == "" or c.startswith("?") or c in ("unknown", "unk", "hidden", "none")


def _visible(state):
    """(الحالة بلا القوارير المغطّاة، فهارسها الأصلية بالترتيب) أو (الحالة نفسها، None) إن لم تكن فيها مغطّاة."""
    tubes = (state or {}).get("tubes") or []
    keep = [k for k, t in enumerate(tubes) if not t.get("blocked")]
    if len(keep) == len(tubes):
        return state, None
    out = {k: v for k, v in state.items() if k != "tubes"}
    out["tubes"] = [tubes[k] for k in keep]
    return out, keep


class _Enc:
    """يحوّل الحالة (dict) إلى صفوف أعداد صحيحة: لون -> 0..K-1، مخفي -> -1."""

    def __init__(self, state: dict):
        tubes = (state or {}).get("tubes") or []
        self.names: list[str] = []
        idx: dict[str, int] = {}
        caps, enc = [], []
        accept: dict[int, int] = {}
        for t in tubes:
            layers = list(t.get("layers") or [])
            try:
                cap = int(t.get("cap") or 4)
            except (TypeError, ValueError):
                cap = 4
            cap = max(cap, len(layers), 1)
            row = []
            for c in layers:
                if _is_hidden(c):
                    row.append(HIDDEN)
                else:
                    k = idx.get(c)
                    if k is None:
                        k = len(self.names)
                        idx[c] = k
                        self.names.append(c)
                    row.append(k)
            caps.append(cap)
            enc.append(tuple(row))
            # لون الوسم («Tag!»): يُرمَّز بعد طبقات قارورته (فترميز قوارير الحالة واحد في _Enc الحالة و_Enc المسألة الممتدّة)
            acc = t.get("accept")
            if isinstance(acc, str) and not _is_hidden(acc):
                k = idx.get(acc)
                if k is None:
                    k = len(self.names)
                    idx[acc] = k
                    self.names.append(acc)
                accept[len(enc) - 1] = k
        # سعة القارورة الطويلة المقروءة من الصورة قد تكون أقل من الحقيقة: القارورة
        # الطويلة تتّسع لكل طبقات لونها (تصميم اللعبة)، فتُرفع سعتها إلى عددها الظاهر
        if caps:
            from collections import Counter
            base = Counter(caps).most_common(1)[0][0]
            vis = Counter(c for row in enc for c in row if c >= 0)
            for k, row in enumerate(enc):
                if caps[k] > base and row and row[0] >= 0 and vis[row[0]] > caps[k]:
                    caps[k] = vis[row[0]]
        self.caps = tuple(caps)
        self.start = tuple(enc)
        self.idx = idx
        self.accept = accept              # {قارورة: اللون الوحيد الذي يُصبّ فيها} («Tag!»)
        # المفاتيح العالقة: (قارورة، موضع) لطبقات معروفة اللون عليها مفتاح
        keys = []
        for k, t in enumerate(tubes):
            for p in (t.get("keys") or ()):
                try:
                    p = int(p)
                except (TypeError, ValueError):
                    continue
                if 0 <= p < len(enc[k]) and enc[k][p] >= 0 and (k, p) not in keys:
                    keys.append((k, p))
        self.keys = tuple(keys)


# قوارير «الطين» في الحالة الجارية (من المرحلة 40): يُصبّ فيها ولا يُصبّ منها حتى تكتمل؛
# يضبطها plan() طوال البحث فقط (البوت خيط واحد)
_NOSRC = frozenset()
# كاسرات الجبس (من المرحلة 100): كل قارورة ظاهرة تكسر بامتلائها جبساً مجاوراً. ليست متماثلة مع غيرها، والصبّ فيها من
# قارورة أحادية اللون غير مكتملة (إلى فارغة، أو جزء منها) ليس عبثاً (لا عكس له حين لا يُصبّ منها: فتات الجبس طين). أما المكتملة
# فلا يُصبّ منها أبداً (تُسدّ بسدادة ذهبية: حركات التشغيلين الرابع والسادس منها كلها «لا تقدّم»). يضبطها plan() فقط
_FILL = frozenset()
# القوارير الموسومة («Tag!»، من المرحلة 130): {فهرس: اللون الوحيد الذي يُصبّ فيها}؛ يضبطها _plan (و_door_search للمسألة الممتدّة)
_ACCEPT = {}


def _key(s, caps):
    """مفتاح قانوني: مجموعة (السعة، المحتوى) بلا ترتيب القوارير (تماثل). قارورة الطين
    لا تماثل قارورة عادية بالمحتوى نفسه (لا يُصبّ منها)، وكاسرة الجبس لا تماثل أي قارورة أخرى،
    والموسومة لا تماثل إلا موسومة بلونها: عنصر ثالث بلون وسمها (بصيغة state_key، فتعمل avoid)."""
    if _ACCEPT:
        if _FILL or _NOSRC:
            return tuple(sorted((caps[k], k in _NOSRC, k if k in _FILL else -1, s[k], _ACCEPT.get(k, -1))
                                for k in range(len(s))))
        return tuple(sorted((caps[k], s[k]) if k not in _ACCEPT else (caps[k], s[k], _ACCEPT[k]) for k in range(len(s))))
    if _FILL:
        return tuple(sorted((caps[k], k in _NOSRC, k if k in _FILL else -1, s[k]) for k in range(len(s))))
    if _NOSRC:
        return tuple(sorted((caps[k], k in _NOSRC, s[k]) for k in range(len(s))))
    return tuple(sorted(zip(caps, s)))


def _avoid_keys(avoid, idx):
    """مفاتيح avoid بأسماء الألوان (state_key: (سعة، طبقات) أو (سعة، طبقات، لون الوسم)) -> مفاتيح بالأعداد بصيغة _key.
    حالة فيها لون غير موجود الآن لا يمكن بلوغها فتُترك."""
    av = set()
    for a in (avoid or ()):
        try:
            rows = []
            for e in a:
                row = (e[0], tuple(HIDDEN if c == "?" else idx[c] for c in e[1]))
                if len(e) > 2:
                    row = row + (idx[e[2]],)
                rows.append(row)
            av.add(tuple(sorted(rows)))
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    return av


# ---------------------------------------------------------------- الحركات
def _top_run(t):
    top = t[-1]
    n = len(t)
    run = 1
    while run < n and t[n - 1 - run] == top:
        run += 1
    return top, run


def _gen_moves(s, caps, exclude=None):
    """الحركات المفيدة: (i, j, الكمية). تُقصى الحركات العبثية."""
    res = []
    n = len(s)
    for i in range(n):
        t = s[i]
        if not t:
            continue
        if i in _NOSRC:                   # الطين: لا يُصبّ منها
            continue
        top = t[-1]
        if top < 0:                       # قمّة مخفية: مجمّدة
            continue
        L = len(t)
        run = 1
        while run < L and t[L - 1 - run] == top:
            run += 1
        mono = run == L                   # قارورة أحادية اللون (تشمل المنتهية)
        acc_i = _ACCEPT.get(i, -1) if _ACCEPT else -1
        empty_caps = None
        for j in range(n):
            if j == i:
                continue
            u = s[j]
            space = caps[j] - len(u)
            if space <= 0:
                continue
            # «Tag!»: لا يُصبّ في الموسومة إلا لونها. ونقل أحادية غير مكتملة إليها (أو جزء منها) من قارورة ليست موسومة بلونها
            # ليس عبثاً: يحرّر قارورة تقبل كل لون مكان قارورة لا تقبل إلا هذا اللون
            tag_ok = False
            if _ACCEPT and j in _ACCEPT:
                if _ACCEPT[j] != top:
                    continue
                tag_ok = acc_i != top and L < caps[i]
            if u:
                if u[-1] != top:
                    continue
                amt = run if run <= space else space
                # صبّ جزئي من أحادية اللون: عبث (إلا من غير مكتملة في كاسرة جبس؛ المكتملة مسدودة)
                if mono and amt < run and (j not in _FILL or L >= caps[i]) and not tag_ok:
                    continue
            else:
                # نقل قارورة أحادية إلى فارغة: عبث (إلا غير مكتملة إلى كاسرة جبس؛ المكتملة مسدودة)
                if mono and (j not in _FILL or L >= caps[i]) and not tag_ok:
                    continue
                # فارغة الطين لا تماثل الفارغة العادية، وكاسرة الجبس لا تماثل غيرها، والموسومة لا تماثل إلا موسومة بلونها
                cj = (caps[j], j in _NOSRC, j if j in _FILL else -1, _ACCEPT.get(j, -1) if _ACCEPT else -1)
                if empty_caps is None:
                    empty_caps = {cj}
                elif cj in empty_caps:    # الفارغات المتماثلة: واحدة تكفي
                    continue
                else:
                    empty_caps.add(cj)
                amt = run if run <= space else space
            if exclude and (i, j) in exclude:
                continue
            res.append((i, j, amt))
    return res


def _apply(s, i, j, amt):
    t = s[i]
    lst = list(s)
    lst[i] = t[:-amt]
    lst[j] = s[j] + (t[-1],) * amt
    return tuple(lst)


def _solved(s, caps) -> bool:
    groups: dict[int, list[int]] = {}
    for k, t in enumerate(s):
        if not t:
            continue
        c = t[0]
        if c < 0:
            return False
        for x in t:
            if x != c:
                return False
        groups.setdefault(c, []).append(k)
    for c, ks in groups.items():
        if len(ks) > 1 and any(len(s[k]) < caps[k] for k in ks):
            return False
    return True


def _empties(s) -> int:
    return sum(1 for t in s if not t)


def _h(s) -> int:
    """تقدير الحركات الباقية: الكتل غير السفلية + الألوان المتفرّقة في القيعان."""
    runs = 0
    nonempty = 0
    bottoms: dict[int, int] = {}
    for t in s:
        if not t:
            continue
        nonempty += 1
        prev = None
        for c in t:
            if c != prev or c < 0:
                runs += 1
            prev = c
        b = t[0]
        if b >= 0:
            bottoms[b] = bottoms.get(b, 0) + 1
    extra = 0
    for v in bottoms.values():
        if v > 1:
            extra += v - 1
    return runs - nonempty + extra


def _h_reveal(s) -> float:
    """أقل عدد كتل فوق أعلى طبقة مخفية مغطّاة (حدّ أدنى لحركات الكشف)."""
    best = INF
    for t in s:
        if not t or HIDDEN not in t:
            continue
        p = len(t) - 1 - t[::-1].index(HIDDEN)
        if p == len(t) - 1:               # مكشوفة أصلاً: ليست هدفاً جديداً
            continue
        runs = 0
        prev = None
        for c in t[p + 1:]:
            if c != prev:
                runs += 1
            prev = c
        if runs < best:
            best = runs
    return best


def _misplaced(s) -> int:
    """الطبقات المعروفة فوق الكتلة السفلية لقارورتها (يجب أن تتحرّك مرة على الأقل)."""
    n = 0
    for t in s:
        if not t:
            continue
        b = t[0]
        k = 1
        if b >= 0:
            while k < len(t) and t[k] == b:
                k += 1
        for c in t[k:]:
            if c >= 0:
                n += 1
    return n


# ---------------------------------------------------------------- المفاتيح
_KEYS = ()          # المفاتيح العالقة في الحالة الجارية [(قارورة، موضع)]؛ يضبطها plan() طوال البحث فقط


def _key_block(t, p):
    """كم كتلة تحجب طبقة المفتاح في الموضع p من القارورة t: 0 = مكشوفة (كل ما فوقها بلونها)، None = خرجت منها.
    كل طبقة مخفية فوقها كتلة وحدها."""
    if p >= len(t):
        return None
    c = t[p]
    i = p + 1
    while i < len(t) and t[i] == c:
        i += 1
    runs, prev = 0, None
    for x in t[i:]:
        if x != prev or x < 0:
            runs += 1
        prev = x
    return runs


def _key_depth(s, keys=None) -> float:
    """ما يحجب المفاتيح العالقة: الكتل فوق كل مفتاح + 0.3 لكل طبقة منها (الدفن يزيده، والحفر نحوها ينقصه)."""
    n = 0.0
    for k, p in (_KEYS if keys is None else keys):
        t = s[k]
        b = _key_block(t, p)
        if b:
            i = p + 1
            while i < len(t) and t[i] == t[p]:
                i += 1
            n += b + 0.3 * (len(t) - i)
    return n


def _key_targets(s, keys):
    """أهداف الحفر: لكل مفتاح (قارورة، الموضع الذي يجب أن يصير القمّة أو يُكشف، النوع).
    النوع "hid": أعلى طبقة مخفية فوق المفتاح تصير القمّة (فتنكشف)؛ "exp": طبقة المفتاح تنكشف؛
    "out": مفتاح مكشوف من البداية لم يطر (قاعدة «الصبّ خارجها») فيُصبّ لونه من قارورته."""
    out = []
    for k, p in keys:
        t = s[k]
        hid = [q for q in range(p + 1, len(t)) if t[q] < 0]
        if hid:
            out.append((k, hid[-1], "hid"))
        elif _key_block(t, p) == 0:
            out.append((k, p, "out"))
        else:
            out.append((k, p, "exp"))
    return out


def _target_hit(t, q, kind) -> bool:
    if kind == "hid":
        return len(t) == q + 1
    if kind == "exp":
        return _key_block(t, q) == 0
    return len(t) <= q


def _target_h(t, q, kind) -> float:
    """حدّ أدنى لعدد الحركات حتى يتحقق الهدف (الكتل فوقه)."""
    if _target_hit(t, q, kind):
        return 0
    if kind == "out":
        return 1
    if kind == "exp":
        return _key_block(t, q) or 0
    runs, prev = 0, None
    for x in t[q + 1:]:
        if x != prev or x < 0:
            runs += 1
        prev = x
    return runs


def _key_search(start, caps, budget, avoid, exclude, max_len=10):
    """أقصر تسلسل آمن يحرّر مفتاحاً (أو يكشف المخفي فوقه)، بعقوبة لاستهلاك الفارغات ولزيادة الفوضى.
    الحالات بلا تماثل (أيّ قارورة فيها المفتاح يهمّ). يعيد (حركات [(i, j)]، الدرجة) أو (None, None)."""
    targets = _key_targets(start, _KEYS)
    if not targets:
        return None, None
    tk = {k for k, _, _ in targets}

    def hval(s):
        return min(_target_h(s[k], q, kind) for k, q, kind in targets)

    e0 = _empties(start)
    h0 = _h(start)
    m0 = _misplaced(start)
    cnt = itertools.count()
    gbest = {start: 0}
    parent = {start: None}
    heap = [(hval(start), 0, _tb(cnt), start)]
    best = None   # (score, state)
    while heap:
        f, g, _, s = heapq.heappop(heap)
        if best is not None and f >= best[0]:
            break
        if g > gbest.get(s, INF):
            continue
        if not budget.tick():
            break
        if g >= max_len:
            continue
        g1 = g + 1
        for (i, j, amt) in _gen_moves(s, caps, exclude if g == 0 else None):
            c = _apply(s, i, j, amt)
            if c in gbest and g1 >= gbest[c]:
                continue
            if i in tk and any(k == i and _target_hit(c[k], q, kind) for k, q, kind in targets):
                e = _empties(c)
                sc = float(g1)
                if e < e0:
                    sc += 1.0 * (e0 - e)
                if e == 0 and e0 > 0:
                    sc += 2.0
                sc += 0.04 * (_h(c) - h0) + 0.03 * (_misplaced(c) - m0)
                if best is None or sc < best[0]:
                    gbest[c] = g1
                    parent[c] = (s, (i, j))
                    best = (sc, c)
                continue
            if _key(c, caps) in avoid:
                continue
            gbest[c] = g1
            parent[c] = (s, (i, j))
            heapq.heappush(heap, (g1 + hval(c), g1, _tb(cnt), c))
    if best is None:
        return None, None
    moves, x = [], best[1]
    while parent.get(x) is not None:
        x, mv = parent[x]
        moves.append(mv)
    moves.reverse()
    return moves, best[0]


def _bury_moves(s, caps, exclude):
    """حركات أولى تدفن مفتاحاً عالقاً (تزيد الكتل فوقه)."""
    d0 = _key_depth(s)
    return {(i, j) for (i, j, amt) in _gen_moves(s, caps, exclude) if _key_depth(_apply(s, i, j, amt)) > d0}


# ---------------------------------------------------------------- الجبس
_PLASTER = ()       # كاسرات الجبس القائم التي لم تكتمل بعد (فهارس الحالة المرمّزة)؛ يضبطها plan() طوال البحث فقط
_KEYS_FIRST = True          # بحث «المفاتيح أولاً» (plan(keys_first=False) يتركه لتنويع المحاولات)


def _is_plaster(t) -> bool:
    return bool(t.get("blocked")) and t.get("cover") == "plaster"


def _slot_geometry(tubes):
    """(خطوة الخانات، أسفل كل قارورة أو None). الخطوة الربع الأدنى لأقرب فرق أفقي بين قارورتين غير طويلتين في الصف نفسه
    (نقطتاهما على ارتفاع واحد تقريباً): صفّ تتخلّله قوارير طويلة أو خانات فارغة يعطي ضعفها (المرحلة 102: 137 بدل 68). الأسفل من
    "box" إن وُجد (الرؤية)، وإلا تقدير: نقطة العادية والمغطّاة وسط صندوقها وارتفاعها نحو 2.6 خطوة، والطويلة تمتدّ صفّين (سعة
    حتى 12) أو ثلاثة."""
    pts = []
    for t in tubes:
        try:
            pts.append((float(t["x"]), float(t["y"])))
        except (KeyError, TypeError, ValueError):
            pts.append(None)
    gaps = []
    for i, a in enumerate(tubes):
        if pts[i] is None or a.get("tall"):
            continue
        best = None
        for j, b in enumerate(tubes):
            if i == j or pts[j] is None or b.get("tall") or abs(pts[i][1] - pts[j][1]) > 40:
                continue
            d = abs(pts[i][0] - pts[j][0])
            if d >= 20 and (best is None or d < best):
                best = d
        if best is not None:
            gaps.append(best)
    px = sorted(gaps)[len(gaps) // 4] if gaps else 70.0
    bottoms = []
    for k, t in enumerate(tubes):
        b = t.get("box")
        try:
            if b is not None and len(b) == 4:
                bottoms.append(float(b[3]))
                continue
        except (TypeError, ValueError):
            pass
        if pts[k] is None:
            bottoms.append(None)
        elif t.get("tall"):
            try:
                rows = 2 if int(t.get("cap") or 10) <= 12 else 3
            except (TypeError, ValueError):
                rows = 2
            bottoms.append(pts[k][1] + 1.45 * px * rows)
        else:
            bottoms.append(pts[k][1] + 1.3 * px)
    return px, bottoms


def plaster_breakers(state):
    """{فهرس قالب الجبس: [فهارس كاسراته]} بفهارس الحالة الأصلية. كاسرة الجبس القارورة الظاهرة (غير المغطّاة) في الخانة المجاورة
    له مباشرة يميناً أو يساراً في صفّه (بين نصف خطوة وخطوة ونصف)؛ واكتمالها (امتلاؤها بلون واحد) يكسره (المراحل 100..110).
    الصفّ بالأسفل لا بالنقطة: القارورة الطويلة الممتدّة على صفّين تكسر جبس صفّ قاعدتها (المرحلة 110: قاعدتها فتات جبس مثل
    الكاسرات العادية). جبس جاره جبس آخر أو ستارة لا كاسرة له من تلك الجهة حتى ينكشف الجار (يُعاد الحساب في كل قراءة)."""
    tubes = (state or {}).get("tubes") or []
    plasters = [k for k, t in enumerate(tubes) if _is_plaster(t)]
    if not plasters:
        return {}
    px, bottoms = _slot_geometry(tubes)
    out = {}
    for p in plasters:
        if bottoms[p] is None:
            continue
        try:
            xp = float(tubes[p]["x"])
        except (KeyError, TypeError, ValueError):
            continue
        side = {}
        for k, t in enumerate(tubes):
            if k == p or bottoms[k] is None or abs(bottoms[k] - bottoms[p]) > 0.9 * px:
                continue
            try:
                dx = float(t["x"]) - xp
            except (KeyError, TypeError, ValueError):
                continue
            if 0.5 * px <= abs(dx) <= 1.5 * px:
                s = dx > 0
                if s not in side or abs(dx) < side[s][0]:
                    side[s] = (abs(dx), k)
        out[p] = sorted(k for _d, k in side.values() if not tubes[k].get("blocked"))
    return out


def _breaker_indices(state, keep):
    """فهارس الكاسرات في الحالة بلا المغطّاة (keep: فهارسها الأصلية بالترتيب، أو None)."""
    br = plaster_breakers(state)
    ks = {k for v in br.values() for k in v}
    if keep is None:
        return sorted(ks)
    inv = {k: i for i, k in enumerate(keep)}
    return sorted(inv[k] for k in ks if k in inv)


def _complete(t, cap) -> bool:
    """القارورة ممتلئة بلون واحد معروف (هكذا تكتمل الكاسرة فينكسر الجبس)."""
    return len(t) >= cap and t[0] >= 0 and all(x == t[0] for x in t)


def _bottom_run(t) -> int:
    if not t or t[0] < 0:
        return 0
    b = 1
    while b < len(t) and t[b] == t[0]:
        b += 1
    return b


def _fill_need(t, cap, nosrc) -> float:
    """كم طبقة تحتاج الكاسرة t حتى تكتمل: الفارغة سعتها، والأحادية ما بقي من سعتها، والمختلطة ما فوق كتلتها السفلية (يُصبّ
    خارجها) وما ينقصها بعده؛ والمختلطة التي لا يُصبّ منها (فتات الجبس طين) لا تكتمل أبداً (INF)."""
    b = _bottom_run(t)
    if b == len(t):
        return float(cap - len(t))
    if nosrc:
        return INF
    return float((len(t) - b) + (cap - b))


def _fill_moves(t, cap, nosrc) -> float:
    """حدّ أدنى لعدد الحركات حتى تكتمل الكاسرة: صبّة واحدة على الأقل، وقبلها حركة لكل كتلة فوق قاعدتها."""
    if _complete(t, cap):
        return 0
    b = _bottom_run(t)
    if b == len(t):
        return 1
    if nosrc:
        return INF
    runs, prev = 0, None
    for x in t[b:]:
        if x != prev or x < 0:
            runs += 1
        prev = x
    return runs + 1


def _plaster_need(s, caps) -> float:
    """أقل نقص بين كاسرات الجبس القائم (0 = اكتملت إحداها في النموذج؛ INF = لا تكتمل أيّ منها)."""
    best = INF
    for k in _PLASTER:
        n = 0.0 if _complete(s[k], caps[k]) else _fill_need(s[k], caps[k], k in _NOSRC)
        if n < best:
            best = n
    return best


def _plaster_search(start, caps, budget, avoid, exclude, max_len=10):
    """أقصر تسلسل آمن يكمل كاسرة جبس (فينكسر الجبس المجاور وتظهر قارورته)، بعقوبة لاستهلاك الفارغات ولزيادة الفوضى ولدفن
    المفاتيح، مثل _key_search: الحالات بلا تماثل (أيّ قارورة تكتمل يهمّ). يعيد (حركات [(i, j)]، الدرجة) أو (None, None)."""
    targets = [k for k in _PLASTER if not _complete(start[k], caps[k])]
    if not targets:
        return None, None
    tset = set(targets)

    def hval(s):
        return min(_fill_moves(s[k], caps[k], k in _NOSRC) for k in targets)

    h_start = hval(start)
    if h_start == INF:
        return None, None
    e0, h0, m0 = _empties(start), _h(start), _misplaced(start)
    kd0 = _key_depth(start) if _KEYS else 0
    cnt = itertools.count()
    gbest = {start: 0}
    parent = {start: None}
    heap = [(h_start, 0, next(cnt), start)]
    best = None   # (score, state)
    while heap:
        f, g, _, s = heapq.heappop(heap)
        if best is not None and f >= best[0]:
            break
        if g > gbest.get(s, INF):
            continue
        if not budget.tick():
            break
        if g >= max_len:
            continue
        g1 = g + 1
        for (i, j, amt) in _gen_moves(s, caps, exclude if g == 0 else None):
            c = _apply(s, i, j, amt)
            if c in gbest and g1 >= gbest[c]:
                continue
            if j in tset and _complete(c[j], caps[j]):          # اكتملت كاسرة: ينكسر الجبس
                e = _empties(c)
                sc = float(g1)
                if e < e0:
                    sc += 1.0 * (e0 - e)
                if e == 0 and e0 > 0:
                    sc += 2.0
                sc += 0.04 * (_h(c) - h0) + 0.03 * (_misplaced(c) - m0)
                if _KEYS:
                    sc += 0.5 * (_key_depth(c) - kd0)
                if best is None or sc < best[0]:
                    gbest[c] = g1
                    parent[c] = (s, (i, j))
                    best = (sc, c)
                continue
            if _key(c, caps) in avoid:
                continue
            hc = hval(c)
            if hc == INF:
                continue
            gbest[c] = g1
            parent[c] = (s, (i, j))
            heapq.heappush(heap, (g1 + hc, g1, next(cnt), c))
    if best is None:
        return None, None
    moves, x = [], best[1]
    while parent.get(x) is not None:
        x, mv = parent[x]
        moves.append(mv)
    moves.reverse()
    return moves, best[0]


# ---------------------------------------------------------------- إعادة بناء المسار
def _derive_moves(start, caps, key_chain, exclude_first=None):
    """يحوّل سلسلة مفاتيح قانونية إلى حركات فعلية على الترتيب الحقيقي للقوارير."""
    moves = []
    cur = start
    for step, nxt in enumerate(key_chain):
        found = None
        excl = exclude_first if step == 0 else None
        for (i, j, amt) in _gen_moves(cur, caps, excl):
            c = _apply(cur, i, j, amt)
            if _key(c, caps) == nxt:
                found = (i, j, c)
                break
        if found is None:                 # احتياط: بلا الإقصاء
            for (i, j, amt) in _gen_moves(cur, caps):
                c = _apply(cur, i, j, amt)
                if _key(c, caps) == nxt:
                    found = (i, j, c)
                    break
        if found is None:
            break
        moves.append((found[0], found[1]))
        cur = found[2]
    return moves


def _chain(parent, k):
    out = []
    while True:
        p = parent.get(k)
        if p is None:
            break
        out.append(k)
        k = p
    out.reverse()
    return out


# ---------------------------------------------------------------- البحوث
class _Budget:
    def __init__(self, max_nodes, deadline):
        self.max_nodes = max_nodes
        self.deadline = deadline
        self.nodes = 0

    def tick(self) -> bool:
        """يعيد False حين تنفد الميزانية."""
        self.nodes += 1
        if self.nodes > self.max_nodes:
            return False
        if (self.nodes & 127) == 0 and time.perf_counter() > self.deadline:
            return False
        return True


def _astar(start, caps, budget, avoid, exclude, w=3.0, node_cap=None):
    """A* موزون نحو الحل الكامل. يعيد سلسلة مفاتيح أو None."""
    cnt = itertools.count()
    k0 = _key(start, caps)
    gbest = {k0: 0}
    parent = {k0: None}
    heap = [(w * _h(start), 0, _tb(cnt), start, k0)]
    local = 0
    while heap:
        f, g, _, s, k = heapq.heappop(heap)
        if g > gbest.get(k, INF):
            continue
        if _solved(s, caps):
            return _chain(parent, k)
        if not budget.tick():
            return None
        local += 1
        if node_cap is not None and local > node_cap:
            return None
        g1 = g + 1
        for (i, j, amt) in _gen_moves(s, caps, exclude if g == 0 else None):
            c = _apply(s, i, j, amt)
            kc = _key(c, caps)
            if kc in avoid:
                continue
            if g1 >= gbest.get(kc, INF):
                continue
            gbest[kc] = g1
            parent[kc] = k
            heapq.heappush(heap, (g1 + w * _h(c), g1, _tb(cnt), c, kc))
    return None


def _order_score(s, caps, i, j, amt):
    t, u = s[i], s[j]
    top = t[-1]
    sc = 0
    if u:
        sc += 0 if len(u) + amt == caps[j] and all(x == top for x in u) else 2
    else:
        sc += 6
    rest = len(t) - amt
    if rest == 0:
        sc -= 1                            # يُفرغ قارورة
    elif t[rest - 1] < 0:
        sc -= 1                            # يكشف
    _, run = _top_run(t)
    if amt < run:
        sc += 3                            # صبّ جزئي
    return sc


def _dfs(start, caps, budget, avoid, exclude, max_depth=400):
    """بحث عمقي مرتّب بجدول زيارات. يعيد سلسلة مفاتيح أو None."""
    k0 = _key(start, caps)
    seen = {k0}
    seen.update(avoid)

    def children(s, root):
        ms = _gen_moves(s, caps, exclude if root else None)
        if _TIE is None:
            ms.sort(key=lambda m: _order_score(s, caps, *m))
        else:
            ms.sort(key=lambda m: (_order_score(s, caps, *m), _TIE.random()))
        return ms

    stack = [(start, k0, iter(children(start, True)))]
    path = []
    while stack:
        s, k, it = stack[-1]
        if _solved(s, caps):
            return list(path)
        advanced = False
        for (i, j, amt) in it:
            c = _apply(s, i, j, amt)
            kc = _key(c, caps)
            if kc in seen:
                continue
            seen.add(kc)
            if not budget.tick():
                return None
            if len(stack) >= max_depth:
                continue
            stack.append((c, kc, iter(children(c, False))))
            path.append(kc)
            advanced = True
            break
        if not advanced:
            stack.pop()
            if path:
                path.pop()
    return None


def _reveal_search(start, caps, budget, avoid, exclude):
    """أقصر تسلسل يكشف طبقة مخفية جديدة، بعقوبة لاستهلاك الفارغات.
    يعيد (سلسلة مفاتيح، الدرجة) أو (None, None)."""
    if _h_reveal(start) == INF:
        return None, None
    e0 = _empties(start)
    h0 = _h(start)
    m0 = _misplaced(start)
    kd0 = _key_depth(start) if _KEYS else 0
    pn0 = min(_plaster_need(start, caps), 8.0) if _PLASTER else 0.0
    cnt = itertools.count()
    k0 = _key(start, caps)
    gbest = {k0: 0}
    parent = {k0: None}
    heap = [(_h_reveal(start), 0, next(cnt), start, k0)]
    best = None   # (score, key_chain)
    while heap:
        f, g, _, s, k = heapq.heappop(heap)
        if best is not None and f >= best[0]:
            break
        if g > gbest.get(k, INF):
            continue
        if not budget.tick():
            break
        g1 = g + 1
        for (i, j, amt) in _gen_moves(s, caps, exclude if g == 0 else None):
            c = _apply(s, i, j, amt)
            src = c[i]
            if src and src[-1] == HIDDEN:            # كشف طبقة جديدة
                e = _empties(c)
                sc = float(g1)
                if e < e0:
                    sc += 1.0 * (e0 - e)
                if e == 0 and e0 > 0:
                    sc += 2.0
                sc += 0.04 * (_h(c) - h0) + 0.03 * (_misplaced(c) - m0)
                sc -= 0.01 * sum(1 for x in src if x == HIDDEN)   # الأعمق أولاً
                if _KEYS:
                    sc += 0.5 * (_key_depth(c) - kd0)              # لا تدفن المفاتيح
                if _PLASTER:
                    sc += 0.3 * (min(_plaster_need(c, caps), 8.0) - pn0)   # والكشف الذي يقرّب كاسرة جبس من امتلائها أولاً
                if best is None or sc < best[0]:
                    kc = _key(c, caps)
                    best = (sc, _chain(parent, k) + [kc])
                continue
            kc = _key(c, caps)
            if kc in avoid:
                continue
            if g1 >= gbest.get(kc, INF):
                continue
            hr = _h_reveal(c)
            if hr == INF:
                continue
            gbest[kc] = g1
            parent[kc] = k
            heapq.heappush(heap, (g1 + hr, g1, next(cnt), c, kc))
    if best is None:
        return None, None
    return best[1], best[0]


def _progress_search(start, caps, budget, avoid, exclude, max_len=8, detour=None, stat=None):
    """احتياط: أفضل حالة قريبة (أقل h، مع الحفاظ على الفارغات). سلسلة أو None.
    detour = مفاتيح الطريق المسدود المحفوظ (جزء من avoid؛ التشغيل 17 المرحلة 154): إن لم تُبلغ حالة أفضل من البداية خارج avoid،
    وقصّت هذه المفاتيح نفسها ابناً، وبدونها يُبلغ تحسّن يمرّ بإحداها (هي سبب غياب التحسّن: stat["blocked"])، تُختار أفضل حالة
    بلغها البحث خارج avoid وفيها حركة بعدها، ولو لم تكن أفضل من البداية. وفي غير ذلك None كما بلا detour."""
    e0 = _empties(start)

    def value(s):
        v = float(_h(s))
        e = _empties(s)
        if e < e0:
            v += 1.5 * (e0 - e)
        hr = _h_reveal(s)
        if hr != INF:
            v += 0.5 * hr
        if _KEYS:
            v += 0.8 * _key_depth(s)            # الحفر نحو المفاتيح، لا دفنها
        if _PLASTER:
            v += 0.6 * min(_plaster_need(s, caps), 8.0)   # ملء كاسرات الجبس (اكتمال واحدة يكشف قارورة جديدة)
        return v

    v0 = value(start)
    cnt = itertools.count()
    k0 = _key(start, caps)
    parent = {k0: None}
    depth = {k0: 0}
    cands = []
    heap = [(v0, 0, next(cnt), start, k0)]
    best = (v0, k0)
    pruned = False
    while heap:
        v, g, _, s, k = heapq.heappop(heap)
        if not budget.tick():
            break
        if g >= max_len:
            continue
        for (i, j, amt) in _gen_moves(s, caps, exclude if g == 0 else None):
            c = _apply(s, i, j, amt)
            kc = _key(c, caps)
            if kc in parent:
                continue
            if kc in avoid:
                if detour and kc in detour:
                    pruned = True
                continue
            parent[kc] = k
            depth[kc] = g + 1
            vc = value(c)
            if _solved(c, caps):
                return _chain(parent, kc)
            if vc < best[0] - 1e-9 or (abs(vc - best[0]) < 1e-9 and depth[kc] < depth.get(best[1], 99)):
                best = (vc, kc)
            if detour:
                cands.append((vc, g + 1, next(cnt), c, kc))
            heapq.heappush(heap, (vc + 0.01 * (g + 1), g + 1, next(cnt), c, kc))
    if best[1] == k0 or best[0] >= v0 - 1e-9:
        if detour and pruned:
            # هل الطريق المسدود المحفوظ سبب غياب التحسّن؟ بدونه (بميزانية صغيرة خاصة) يُبلغ تحسّن يمرّ بإحدى حالاته
            alt = _progress_search(start, caps, _Budget(5000, time.perf_counter() + 0.3), avoid - set(detour), exclude, max_len)
            if alt and any(kk in detour for kk in alt):
                if stat is not None:
                    stat["blocked"] = True
                # أفضل حالة بلغها البحث (الأقرب عند التعادل) لا تنسدّ بعدها: حالة بلا حركة طريق مسدود آخر
                for vc, g, _, c, kc in sorted(cands):
                    if _gen_moves(c, caps):
                        return _chain(parent, kc)
        return None
    return _chain(parent, best[1])


# ---------------------------------------------------------------- العيّنات (PIMC)
def _color_totals(s, caps, base):
    """العدد الكلّي المتوقّع لكل لون: سعة القارورة الطويلة للونها، وإلا مضاعف base."""
    vis: dict[int, int] = {}
    for t in s:
        for c in t:
            if c >= 0:
                vis[c] = vis.get(c, 0) + 1
    giant: dict[int, int] = {}
    for t, cap in zip(s, caps):
        if cap > base and t and t[0] >= 0:
            giant[t[0]] = giant.get(t[0], 0) + cap
    tot = {}
    for c, v in vis.items():
        if c in giant:
            tot[c] = max(giant[c], v)
        else:
            tot[c] = base * max(1, -(-v // base))
    return vis, tot


def _make_samples(s, caps, rng, k):
    """k توزيعات عشوائية للطبقات المخفية تحترم عدد كل لون (+ ألوان غير مرئية)."""
    from collections import Counter
    base = Counter(caps).most_common(1)[0][0]
    vis, tot = _color_totals(s, caps, base)
    # «Tag!»: لون وسم لم تظهر له طبقة بعد (كل طبقاته مخفية) لون موجود حتماً بفهرس الوسم، فيدخل الناقص قبل الألوان المخترعة؛
    # والمخترع لا يأخذ فهرس وسم (كان يُخترع لون جديد مكانه فلا تقبل الموسومة في العيّنة لوناً موجوداً)
    acc = set(_ACCEPT.values()) if _ACCEPT else set()
    for a in acc:
        if a >= 0 and a not in vis:
            tot[a] = base
    pos = [(ti, p) for ti, t in enumerate(s) for p, c in enumerate(t) if c < 0]
    H = len(pos)
    missing = []
    for c, n in tot.items():
        missing += [c] * max(0, n - vis.get(c, 0))
    nxt = max(list(vis) + list(acc) + [-1]) + 1
    while len(missing) < H:                   # ألوان لم تظهر بعد
        missing += [nxt] * base
        nxt += 1
    out = []
    for _ in range(k):
        pool = list(missing)
        rng.shuffle(pool)
        pool = pool[:H]
        rows = [list(t) for t in s]
        for (ti, p), c in zip(pos, pool):
            rows[ti][p] = c
        out.append(tuple(tuple(r) for r in rows))
    return out


def _quick_solve(s, caps, nodes, deadline):
    """حل كامل سريع لعيّنة (معلومات كاملة): سلسلة مفاتيح أو None."""
    b = _Budget(nodes, deadline)
    ch = _astar(s, caps, b, (), None, w=3.0)
    return ch


PIMC_SAMPLES = 24        # عدد العيّنات (يقطعه الوقت)
PIMC_CANDS = 10          # أقصى عدد للحركات المرشّحة التي تُقيَّم


def _pimc(s, caps, deadline, avoid, exclude, rng, max_samples=None, info=None):
    """يختار الحركة التالية بتصويت عيّنات: لكل عيّنة حلّ كامل، ثم تُقيَّم الحركات
    المرشّحة بعدد العيّنات التي تبقى قابلة للحل بعدها. يعيد (i, j) أو None."""
    root_moves = _gen_moves(s, caps, exclude)
    if not root_moves:
        return None
    legal = {}                                # مفتاح الحالة الناتجة -> حركة ممثّلة
    by_ij = {}                                # (i, j) -> مفتاح الحالة الناتجة
    k_root = _key(s, caps)
    for (i, j, amt) in root_moves:
        c = _apply(s, i, j, amt)
        k = _key(c, caps)
        if k in avoid or k == k_root:         # k == k_root: تبديل بين قارورتين متماثلتين (عبث)
            continue
        legal.setdefault(k, (i, j, amt))
        by_ij[(i, j)] = k
    if not legal:
        return None
    samples = _make_samples(s, caps, rng, max_samples or PIMC_SAMPLES)
    votes: dict = {}
    sols = []
    t_samples = time.perf_counter() + max(0.05, (deadline - time.perf_counter()) * 0.45)
    for smp in samples:
        if sols and time.perf_counter() > t_samples:
            break
        ch = _quick_solve(smp, caps, 6000, deadline)
        first = None
        if ch:
            # الحالة الأولى في سلسلة العيّنة -> الحركة الحقيقية المقابلة (بفهارسها)
            for (i, j, amt) in _gen_moves(smp, caps, exclude):
                c = _apply(smp, i, j, amt)
                if _key(c, caps) == ch[0]:
                    first = by_ij.get((i, j))
                    break
        sols.append((smp, first))
        if first is not None:
            votes[first] = votes.get(first, 0) + 1
    if info is not None:
        info["samples"] = len(sols)
        info["solvable"] = sum(1 for _, f in sols if f is not None)
    if not votes:
        return None
    n = len(sols)
    cands = sorted(votes, key=lambda k: -votes[k])
    for k in legal:                           # بقية الحركات إن بقي وقت
        if k not in votes:
            cands.append(k)
    cands = cands[:PIMC_CANDS]
    best = None
    for km in cands:
        i, j, amt = legal[km]
        ok = 0
        tested = 0
        for smp, first in sols:
            if time.perf_counter() > deadline:
                break
            tested += 1
            if first == km:
                ok += 1
                continue
            c = _apply(smp, i, j, amt)
            if _quick_solve(c, caps, 2500, deadline) is not None:
                ok += 1
        if tested == 0:
            break
        src_after = _apply(s, i, j, amt)[i]
        reveal = 1 if (src_after and src_after[-1] == HIDDEN) else 0
        e_loss = max(0, _empties(s) - _empties(_apply(s, i, j, amt)))
        kp = (_key_depth(s) - _key_depth(_apply(s, i, j, amt))) if _KEYS else 0
        pp = (min(_plaster_need(s, caps), 8.0) - min(_plaster_need(_apply(s, i, j, amt), caps), 8.0)) if _PLASTER else 0
        score = (ok / tested, kp, pp, reveal, -e_loss, votes.get(km, 0))
        if best is None or score > best[0]:
            best = (score, (i, j))
        if time.perf_counter() > deadline:
            break
    if info is not None and best is not None:
        info["pimc"] = "%.2f/%d" % (best[0][0], n)
    return best[1] if best else None


# ---------------------------------------------------------------- ذاكرة الأبواب
# ما خلف الأبواب ثابت لكل بداية (التشغيل 12، المرحلة 124: البداية نفسها تفتح أبوابها عن القوارير نفسها في المواضع نفسها كل مرة)،
# فالسائق يمرّر ما رآه في محاولة سابقة: doors=[{"key": (قارورة، موضع)، "tubes": [قوارير بابه]}، ...]. القارورة في "key" فهرس في
# القائمة الممتدّة: قوارير الحالة أولاً ثم قوارير الأبواب بترتيب ورودها (مفتاح داخل قارورة باب يفتح باباً آخر معروفاً). "keys" بدل
# "key" لباب انفتح مع مفتاحين معاً (لا يُعرف أيهما فتحه: ينفتح حين يتحرّر الاثنان).
_TIE = None          # مولّد عشوائي لكسر التعادل في البحوث (plan(vary>0): تنويع المحاولات المتكرّرة للبداية نفسها)؛ None = كما كان


def _tb(cnt):
    """كاسر التعادل في طوابير البحث: عدّاد بالترتيب (كما كان)، أو عشوائي في وضع التنويع."""
    return next(cnt) if _TIE is None else _TIE.random()


class _Doors:
    """المسألة المعروفة كلها: قوارير الحالة + قوارير الأبواب المقفلة. القارورة المقفلة لا يُصبّ منها ولا فيها حتى يتحرّر مفتاح
    بابها (قاعدة _key_block: لا شيء بلون آخر فوق طبقته، أو خرجت منها؛ والمكشوف لحظة ظهوره لا يطير حتى يُصبّ لونه خارجها).
    مواصفة مفتاحها غير صالح (خارج قارورته أو على طبقة مخفية) تبقى قواريرها في القائمة (فلا تتغيّر فهارس المواصفات بعدها) لكنها
    مقفلة أبداً (never)، ومواصفة مفتاحها داخلها لا تنفتح أبداً كذلك (مفتاح في قارورة مقفلة لا يتحرّر)."""

    def __init__(self, state, doors):
        tubes = list((state or {}).get("tubes") or [])
        self.n = len(tubes)
        specs = []
        for d in doors or ():
            try:
                tt = [dict(t) for t in (d.get("tubes") or [])]
                ks = d.get("keys")
                if ks is None:
                    ks = [d["key"]] if d.get("key") is not None else []
                ks = [(int(a), int(b)) for a, b in ks]
            except (TypeError, ValueError, KeyError, AttributeError):
                continue
            if not tt:
                continue
            idx = list(range(len(tubes), len(tubes) + len(tt)))
            tubes.extend(tt)
            specs.append((ks, idx))
        self.enc = _Enc({"tubes": tubes})
        s0, caps = self.enc.start, self.enc.caps
        keys = set(self.enc.keys)
        ok_specs = []
        never = set()
        for ks, idx in specs:
            if ks and all(0 <= k < len(s0) and 0 <= p < len(s0[k]) and s0[k][p] >= 0 for k, p in ks):
                keys.update(ks)
                ok_specs.append((ks, idx))
            else:
                never.update(idx)                # مواصفة مرفوضة: قواريرها مقفلة أبداً (لا قوارير وهمية مفتوحة)
        self.never = frozenset(never)
        self.keylist = sorted(keys)
        bit = {kp: b for b, kp in enumerate(self.keylist)}
        self.specs = [(sum(1 << bit[kp] for kp in ks), idx) for ks, idx in ok_specs]
        known = 0
        for m, _idx in self.specs:
            known |= m
        self.unknown = ((1 << len(self.keylist)) - 1) & ~known      # مفاتيح لا يُعرف ما خلف أبوابها
        # المكشوف لحظة ظهوره (في البداية أو حين ينفتح باب قارورته) لا يطير حتى يُصبّ لونه خارجها (كما في _key_targets)
        self.needs_out = [_key_block(s0[k], p) == 0 for k, p in self.keylist]
        self._locked = {}
        self._caps = {}
        self.caps = caps
        self.s0 = s0

    def complete(self, mask) -> bool:
        """المسألة الممتدّة معروفة كلها: لا مفتاح عالق لا يُعرف بابه، ولا باب لا ينفتح أبداً، ولا طبقة مخفية."""
        return (not (self.unknown & ~mask) and not self.never
                and not any(c < 0 for t in self.s0 for c in t))

    def locked(self, mask):
        lk = self._locked.get(mask)
        if lk is None:
            lk = frozenset(k for m, idx in self.specs if (mask & m) != m for k in idx) | self.never
            self._locked[mask] = lk
        return lk

    def caps_eff(self, mask):
        """السعات الفعلية: المقفلة «ممتلئة» بمحتواها (لا يُصبّ فيها)، ومحتواها لا يتغيّر ما دامت مقفلة."""
        c = self._caps.get(mask)
        if c is None:
            lk = self.locked(mask)
            c = tuple(len(self.s0[k]) if k in lk else cap for k, cap in enumerate(self.caps))
            self._caps[mask] = c
        return c

    def settle(self, s, mask):
        """المفاتيح التي تتحرّر في الحالة s (وما تفتحه أبوابها من قوارير فيها مفاتيح أخرى)."""
        changed = True
        while changed:
            changed = False
            lk = self.locked(mask)
            for b, (k, p) in enumerate(self.keylist):
                if (mask >> b) & 1 or k in lk:
                    continue
                t = s[k]
                if self.needs_out[b]:
                    rel = len(t) <= p
                else:
                    blk = _key_block(t, p)
                    rel = blk is None or blk == 0
                if rel:
                    mask |= 1 << b
                    changed = True
        return mask

    def all_open(self, mask) -> bool:
        return all((mask & m) == m for m, _idx in self.specs)

    def moves(self, s, mask, exclude=None):
        lk = self.locked(mask)
        return [m for m in _gen_moves(s, self.caps_eff(mask), exclude) if m[0] not in lk]

    def view_key(self, s, mask):
        """مفتاح الجزء الظاهر (القوارير غير المقفلة) بصيغة avoid (والموسومة بلون وسمها عنصراً ثالثاً، كما في state_key)."""
        lk = self.locked(mask)
        acc = self.enc.accept
        return tuple(sorted((self.caps[k], s[k]) if k not in acc else (self.caps[k], s[k], acc[k])
                            for k in range(len(s)) if k not in lk))


_DOOR_LINE = []      # الخط الكامل لآخر بحث أبواب [(حركة بفهارس المسألة الممتدّة، هل فتحت باباً)] (للسجل والاختبارات)


def _door_search(state, doors, budget, avoid_names, exclude, w=3.0):
    """بحث في المسألة المعروفة كلها (قوارير الحالة + ما خلف الأبواب المعروفة) عن حلّ كامل: كل لون مكتمل وكل باب معروف مفتوح.
    لا يعمل إلا والمسألة الممتدّة معروفة كلها (_Doors.complete): مع مفتاح لا يُعرف بابه أو طبقة مخفية (في الحالة أو خلف باب) لا
    هدف مضموناً، وخطة جشعة نحو «أقرب حدث» كانت تأخذ مكان «المفاتيح أولاً» وPIMC فتخسر مراحل كان يفوز بها (مراجعة التشغيل 12)؛
    فيُترك للمنطق المعتاد بلا صرف ميزانيته. يعيد (حركات حتى أول باب ينفتح أو حتى الحل، الحالة، عدد الأبواب) والحالة
    "doors-full" (خطة) | "hidden" (معرفة ناقصة، لم يُبحث) | "none" (لا حلّ في الميزانية). الحركات بفهارس الحالة (تتوقف بعد
    الحركة التي تفتح باباً: قواريره تظهر فيعيد السائق التخطيط). avoid يقصّ العقد، فإن لم يُعثر على شيء أُعيد البحث بدونه
    (كبقية البحوث: حالة انفتاح باب في «الطريق المسدود» ممرّ إجباري)."""
    P = _Doors(state, doors)
    if not P.specs:
        return None, "none", 0
    s0, caps, n = P.s0, P.caps, P.n
    m0 = P.settle(s0, 0)
    if not P.complete(m0):
        return None, "hidden", len(P.specs)
    enc = P.enc
    global _ACCEPT
    acc_prev = _ACCEPT
    _ACCEPT = dict(enc.accept)                  # الوسوم بفهارس المسألة الممتدّة (قوارير الأبواب بعد قوارير الحالة)
    try:
        return _door_search_run(P, s0, caps, n, m0, enc, budget, avoid_names, exclude, w)
    finally:
        _ACCEPT = acc_prev


def _door_search_run(P, s0, caps, n, m0, enc, budget, avoid_names, exclude, w):
    av = _avoid_keys(avoid_names, enc.idx)
    av.discard(P.view_key(s0, m0))

    def hval(s, mask):
        return w * _h(s) + sum(1 for m, _i in P.specs if (mask & m) != m)

    def search(av):
        cnt = itertools.count()
        st0 = (s0, m0)
        gbest = {st0: 0}
        parent = {st0: None}
        heap = [(hval(s0, m0), 0, _tb(cnt), s0, m0)]
        while heap:
            f, g, _, s, mask = heapq.heappop(heap)
            if g > gbest.get((s, mask), INF):
                continue
            if not budget.tick():
                return None, parent
            g1 = g + 1
            for (i, j, amt) in P.moves(s, mask, exclude if g == 0 else None):
                c = _apply(s, i, j, amt)
                m1 = P.settle(c, mask)
                node = (c, m1)
                if g1 >= gbest.get(node, INF):
                    continue
                if P.all_open(m1) and _solved(c, caps):
                    parent[node] = ((s, mask), (i, j))
                    return node, parent
                if av and P.view_key(c, m1) in av:
                    continue
                gbest[node] = g1
                parent[node] = ((s, mask), (i, j))
                heapq.heappush(heap, (g1 + hval(c, m1), g1, _tb(cnt), c, m1))
        return None, parent

    goal, parent = search(av)
    if goal is None and av and budget.nodes < budget.max_nodes and time.perf_counter() < budget.deadline:
        goal, parent = search(set())
    if goal is None:
        return None, "none", len(P.specs)
    path, x = [], goal
    while parent.get(x) is not None:
        prev, mv = parent[x]
        path.append((prev, mv, x))
        x = prev
    path.reverse()
    _DOOR_LINE[:] = [(mv, P.locked(cm) != P.locked(pm)) for (ps, pm), mv, (_c, cm) in path]
    moves = []
    for (ps, pm), mv, (_c, cm) in path:
        if mv[0] >= n or mv[1] >= n:
            break                                   # قارورة باب لم ينفتح بعد على الشاشة (لا يحدث إلا بباب مفتوح من البداية)
        moves.append(mv)
        if P.locked(cm) != P.locked(pm):
            break                                   # انفتح باب: قواريره تظهر الآن، فيُعاد التخطيط بالحالة الحقيقية
    if not moves:
        return None, "none", len(P.specs)
    return moves, "doors-full", len(P.specs)


# ---------------------------------------------------------------- الواجهة العامة
def plan(state, max_nodes=40000, time_limit=1.6, bad_moves=None, avoid=None,
         info=None, seed=None, keys_first=True, doors=None, vary=0, detour=False):
    """يعيد قائمة حركات (i, j). قائمة فارغة = لا حركة مفيدة (أو محلولة).
    قوارير الطين ("clay": True) لا يُصبّ منها، والمغطّاة ("blocked": True) لا تُلمس أبداً، وكاسرات الجبس (plaster_breakers)
    يُسعى إلى إكمالها أولاً. keys_first=False يترك بحث «المفاتيح أولاً» (فتح الأبواب بأسرع طريق) لتختار بحوث الكشف والتقدّم
    متى تُفتح الأبواب (مع بقاء منع دفن المفاتيح وقيمة عمقها): تنويع في المراحل التي يتكرّر فشلها (المرحلة 124). انظر _plan.
    doors: ما خلف الأبواب كما رآه السائق في محاولة سابقة للبداية نفسها ([{"key": (قارورة، موضع)، "tubes": [...]}]، انظر _Doors):
    يُبحث أولاً في المسألة المعروفة كلها (_door_search) إن عُرفت كلها، وإلا (أو بلا حلّ) فالمنطق المعتاد كما هو.
    vary > 0: كسر تعادل عشوائي (بالبذرة seed) ووزن A* آخر: محاولة أخرى للبداية نفسها لا تكرّر طريق سابقتها.
    detour: مفاتيح (state_key) طريق مسدود محفوظ من محاولة سابقة (جزء من avoid؛ True = avoid كلها): إن لم يُعثر على شيء بالبحوث
    كلها وكانت هي التي قصّت الخط المحسِّن (info["dead_blocked"]) فطريق بديل بعيداً عنها (_progress_search بـ detour) بدل «لا حركة»
    (التشغيل 17، المرحلة 154)."""
    global _NOSRC, _KEYS, _FILL, _PLASTER, _KEYS_FIRST, _TIE, _ACCEPT
    vis, keep = _visible(state)
    if keep is not None:                  # الفهارس الأصلية <-> فهارس الحالة بلا المغطّاة
        inv = {k: i for i, k in enumerate(keep)}
        bad_moves = [(inv[m[0]], inv[m[1]]) for m in (bad_moves or ()) if m[0] in inv and m[1] in inv]
        doors = _remap_doors(doors, inv, len(keep), len((state or {}).get("tubes") or []))
    _NOSRC = frozenset(k for k, t in enumerate((vis or {}).get("tubes") or []) if t.get("clay"))
    _KEYS = ()
    _FILL = frozenset(_breaker_indices(state, keep)) if keep is not None else frozenset()
    _PLASTER = ()
    _KEYS_FIRST = bool(keys_first)
    try:
        vary = int(vary or 0)
    except (TypeError, ValueError):
        vary = 0
    if vary > 0:
        import random as _random
        _TIE = _random.Random((seed if seed is not None else 0) * 1000003 + vary)
    t_call = time.perf_counter()
    try:
        moves = _plan(vis, max_nodes, time_limit, bad_moves, avoid, info, seed, doors, vary, detour)
        if info is not None and doors:
            info["ms"] = round((time.perf_counter() - t_call) * 1000, 1)   # الوقت كله (بحث الأبواب ثم المعتاد)
    finally:
        _NOSRC = frozenset()
        _KEYS = ()
        _FILL = frozenset()
        _PLASTER = ()
        _KEYS_FIRST = True
        _TIE = None
        _ACCEPT = {}
    if keep is not None:
        moves = [(keep[i], keep[j]) for (i, j) in moves]
    return moves


def _remap_doors(doors, inv, nvis, norig):
    """فهارس مفاتيح الأبواب (بالحالة الأصلية بمغطّاتها) -> فهارس الحالة بلا المغطّاة؛ قوارير الأبواب بعد القوارير الظاهرة."""
    if not doors:
        return doors
    out = []
    for d in doors:
        try:
            ks = d.get("keys")
            if ks is None:
                ks = [d["key"]]
            nk = []
            for a, b in ks:
                a = int(a)
                if a < norig:
                    if a not in inv:
                        raise KeyError(a)
                    nk.append((inv[a], int(b)))
                else:
                    nk.append((a - norig + nvis, int(b)))
            out.append({"keys": nk, "tubes": d.get("tubes") or []})
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return out


def _reserve(budget, max_nodes, time_limit):
    """ميزانية الطريق البديل (detour): ما بقي من budget، أو احتياط صغير إن نفدت (A* والعمقي يستهلكانها كلها في لغز لا يُحلّ
    ظاهره: قوارير خلف الأبواب)."""
    if budget.nodes < budget.max_nodes and time.perf_counter() < budget.deadline:
        return budget
    return _Budget(min(int(max_nodes), 5000), time.perf_counter() + min(float(time_limit), 0.3))


def _detour(s, caps, budget, max_nodes, time_limit, av, dav, exclude, info):
    """الطريق البديل عن الطريق المسدود المحفوظ dav (التشغيل 17، المرحلة 154): سلسلة أو None. info["dead_blocked"] حين قصّت
    حالاته الخط المحسِّن (منه يعيد المحرّك التخطيط بدونها إن لم يوجد بديل)، وmode = progress-detour حينئذ فقط."""
    stat = {}
    chain = _progress_search(s, caps, _reserve(budget, max_nodes, time_limit), av, exclude, detour=dav, stat=stat)
    if stat.get("blocked"):
        info["dead_blocked"] = True
        info["mode"] = "progress-detour"
    return chain


def _plan(state, max_nodes=40000, time_limit=1.6, bad_moves=None, avoid=None,
          info=None, seed=None, doors=None, vary=0, detour=False):
    """يعيد قائمة حركات (i, j). قائمة فارغة = لا حركة مفيدة (أو محلولة).

    bad_moves: حركات (i, j) تُستبعد من الخطوة الأولى (فشلت في هذه الحالة).
    avoid: مفاتيح حالات (state_key) مرّ بها البوت في هذه المرحلة لتجنّب الدوران.
    info: قاموس اختياري يُملأ بتفاصيل (mode، nodes، الوقت).
    """
    t0 = time.perf_counter()
    enc = _Enc(state)
    s, caps = enc.start, enc.caps
    if info is None:
        info = {}
    info.update(mode="solved", nodes=0, ms=0.0)
    global _PLASTER, _ACCEPT
    _ACCEPT = dict(enc.accept)            # «Tag!»: يمسحه plan() بعد البحث
    if _ACCEPT:
        info["tags"] = len(_ACCEPT)
    # كاسرات الجبس القائم التي لم تكتمل: الظاهر «مرتّباً» ليس نهاية ما دامت إحداها تكتمل (طويلة أحادية غير مكتملة تُصبّ في كاسرة
    # فارغة؛ المكتملة مسدودة لا يُصبّ منها)
    _PLASTER = tuple(k for k in sorted(_FILL) if k < len(s) and not _complete(s[k], caps[k]))
    if not s or (_solved(s, caps) and not _PLASTER):
        return []
    budget = _Budget(max_nodes, t0 + time_limit)
    exclude = set(tuple(m) for m in (bad_moves or ()))
    av = _avoid_keys(avoid, enc.idx)  # مفاتيح بأسماء الألوان -> مفاتيح بالأعداد
    av.discard(_key(s, caps))
    # مفاتيح الطريق المسدود المحفوظ (للطريق البديل): ما يُبلغ منها ويقع في avoid
    if detour is True:
        dav = set(av)
    elif detour:
        dav = _avoid_keys(detour, enc.idx) & av
    else:
        dav = set()

    # ---- ذاكرة الأبواب: ما خلف أبواب المفاتيح العالقة معروف من محاولة سابقة للبداية نفسها، فيُبحث في المسألة كلها أولاً
    global _KEYS
    _KEYS = enc.keys
    if doors and _KEYS:
        db = _Budget(int(max_nodes * 0.5), t0 + time_limit * 0.5)
        mv, res, nd = _door_search(state, doors, db, avoid, exclude, w=(3.0, 2.5, 4.0)[vary % 3])
        info["doors"] = nd
        info["doors_res"] = res                  # doors-full | hidden (معرفة ناقصة: لم يُبحث) | none (لا حلّ في الميزانية)
        if mv:
            info["mode"] = res
            info["nodes"] = db.nodes
            info["ms"] = round((time.perf_counter() - t0) * 1000, 1)
            return mv
        # لم يُعثر على شيء: المنطق المعتاد كما هو بما بقي من الوقت (لا يقلّ عن ثلثه)
        used = time.perf_counter() - t0
        time_limit = max(time_limit * 0.35, time_limit - used)
        max_nodes = max(int(max_nodes * 0.35), max_nodes - db.nodes)
        t0 = time.perf_counter()
        budget = _Budget(max_nodes, t0 + time_limit)
    if _KEYS:
        info["keys"] = len(_KEYS)
        if _KEYS_FIRST:
            kb = _Budget(int(max_nodes * 0.5), t0 + time_limit * 0.45)
            mv, _ = _key_search(s, caps, kb, av, exclude)
            if mv is None and av:
                mv, _ = _key_search(s, caps, kb, set(), exclude)
            if mv:
                info["mode"] = "key"
                info["nodes"] = kb.nodes
                info["ms"] = round((time.perf_counter() - t0) * 1000, 1)
                return mv
        else:
            info["keys_first"] = False
        bury = _bury_moves(s, caps, exclude)
        allm = {(i, j) for (i, j, _a) in _gen_moves(s, caps, exclude)}
        if bury and allm - bury:
            exclude = exclude | bury

    # ---- الجبس: اللغز الظاهر ناقص (ألوانه الباقية داخل الجبس، وترتيبه «محلولاً» ليس فوزاً)، فإكمال كاسرة أولاً
    if _PLASTER:
        info["breakers"] = len(_PLASTER)
        pb = _Budget(int(max_nodes * 0.5), t0 + time_limit * 0.6)
        mv, _ = _plaster_search(s, caps, pb, av, exclude)
        if mv is None and av:
            mv, _ = _plaster_search(s, caps, pb, set(), exclude)
        if mv:
            info["mode"] = "plaster"
            info["nodes"] = pb.nodes
            info["ms"] = round((time.perf_counter() - t0) * 1000, 1)
            return mv

    hidden = any(c < 0 for t in s for c in t)
    chain = None
    if hidden:
        import random as _random
        rng = _random.Random(seed if seed is not None else hash(_key(s, caps)) & 0xFFFFFFFF)
        info["mode"] = "pimc"
        mv = _pimc(s, caps, t0 + time_limit * 0.8, av, exclude, rng, info=info)
        if mv is not None:
            info["nodes"] = budget.nodes
            info["ms"] = round((time.perf_counter() - t0) * 1000, 1)
            return [mv]
        info["mode"] = "reveal"
        chain, _ = _reveal_search(s, caps, budget, av, exclude)
        if chain is None and av:
            chain, _ = _reveal_search(s, caps, budget, set(), exclude)
        if chain is None:
            info["mode"] = "progress"
            chain = _progress_search(s, caps, budget, av, exclude)
        if chain is None and dav:
            chain = _detour(s, caps, budget, max_nodes, time_limit, av, dav, exclude, info)
    else:
        info["mode"] = "astar"
        chain = _astar(s, caps, budget, av, exclude, w=(3.0, 2.5, 4.0)[vary % 3],
                       node_cap=int(max_nodes * 0.55))
        if chain is None:
            info["mode"] = "dfs"
            chain = _dfs(s, caps, budget, av, exclude)
        if chain is None and av:
            info["mode"] = "dfs-noavoid"
            chain = _dfs(s, caps, budget, set(), exclude)
        if chain is None:
            info["mode"] = "progress"
            chain = _progress_search(s, caps, budget, av, exclude)
        if chain is None and dav:
            chain = _detour(s, caps, budget, max_nodes, time_limit, av, dav, exclude, info)
    moves = _derive_moves(s, caps, chain, exclude) if chain else []
    info["nodes"] = budget.nodes
    info["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    if not moves:
        info["mode"] += "-none"
    return moves


def state_key(state):
    """مفتاح قانوني بأسماء الألوان لحالة (dict) — لمجموعة avoid في المحرّك.
    لا يتأثر بترتيب القوارير؛ الطبقة المخفية "?"؛ والقوارير المغطّاة لا تدخل فيه (كما لا يراها الحلّال)."""
    out = []
    for t in (state or {}).get("tubes") or []:
        if t.get("blocked"):
            continue
        layers = tuple("?" if _is_hidden(c) else c for c in (t.get("layers") or []))
        try:
            cap = int(t.get("cap") or 4)
        except (TypeError, ValueError):
            cap = 4
        acc = _accept_of(t)
        if acc is None:
            out.append((max(cap, len(layers), 1), layers))
        else:
            out.append((max(cap, len(layers), 1), layers, acc))   # الموسومة: لون وسمها عنصر ثالث
    return tuple(sorted(out))


def _accept_of(t):
    """لون وسم القارورة («Tag!») أو None."""
    acc = t.get("accept")
    return acc if isinstance(acc, str) and not _is_hidden(acc) else None


def legal_moves(state):
    """كل الحركات القانونية بقواعد اللعبة (بلا تقليم)، [(i, j), ...] (لا تلمس المغطّاة)."""
    vis, keep = _visible(state)
    enc = _Enc(vis)
    s, caps = enc.start, enc.caps
    out = []
    tubes = (vis or {}).get("tubes") or []
    for i, t in enumerate(s):
        if not t or t[-1] < 0 or tubes[i].get("clay"):
            continue
        for j, u in enumerate(s):
            if i == j or len(u) >= caps[j]:
                continue
            if u and u[-1] != t[-1]:
                continue
            if j in enc.accept and enc.accept[j] != t[-1]:
                continue                      # «Tag!»: لا يُصبّ في الموسومة إلا لونها
            out.append((i, j))
    if keep is not None:
        out = [(keep[i], keep[j]) for (i, j) in out]
    return out


def apply_move(state, i, j):
    """يطبّق الحركة على نسخة من الحالة (dict) ويعيدها، أو None إن كانت غير قانونية.
    الطبقات المخفية تبقى "?" (يكشفها الواقع لا النموذج)."""
    tubes = (state or {}).get("tubes") or []
    if not (0 <= i < len(tubes) and 0 <= j < len(tubes)) or i == j:
        return None
    if tubes[i].get("blocked") or tubes[j].get("blocked"):
        return None                       # المغطّاة لا يُصبّ منها ولا فيها
    src = list(tubes[i].get("layers") or [])
    dst = list(tubes[j].get("layers") or [])
    if not src or _is_hidden(src[-1]) or tubes[i].get("clay"):
        return None
    try:
        capj = max(int(tubes[j].get("cap") or 4), len(dst))
    except (TypeError, ValueError):
        capj = max(4, len(dst))
    space = capj - len(dst)
    top = src[-1]
    if space <= 0 or (dst and dst[-1] != top):
        return None
    acc = _accept_of(tubes[j])
    if acc is not None and acc != top:
        return None                       # «Tag!»: لا يُصبّ في الموسومة إلا لونها
    run = 1
    while run < len(src) and src[-1 - run] == top:
        run += 1
    amt = min(run, space)
    new = {k: v for k, v in state.items() if k != "tubes"}
    nt = []
    for k, t in enumerate(tubes):
        d = dict(t)
        if k == i:
            d["layers"] = src[:-amt]
        elif k == j:
            d["layers"] = dst + [top] * amt
        else:
            d["layers"] = list(t.get("layers") or [])
        nt.append(d)
    new["tubes"] = nt
    return new


def key_freed(state, i, j) -> bool:
    """هل تحرّر الحركة (i, j) مفتاحاً؟ تكشف طبقته (لا شيء بلون آخر فوقها) أو تصبّها خارج قارورتها.
    (السائق ينتظر بعدها طيران المفتاح وانفتاح الباب قبل اللقطة.)"""
    tubes = (state or {}).get("tubes") or []
    if not (0 <= i < len(tubes)) or not tubes[i].get("keys"):
        return False
    after = apply_move(state, i, j)
    if after is None:
        return False
    enc = _Enc(state)
    src = _Enc(after).start[i]
    for k, p in enc.keys:
        if k != i:
            continue
        b = _key_block(src, p)
        if b is None or b == 0:
            return True
    return False


def breaker_completed(state, i, j) -> bool:
    """هل تكمل الحركة (i, j) كاسرة جبس قائم (تمتلئ القارورة j بلون واحد)؟ السائق ينتظر بعدها انكسار الجبس قبل اللقطة
    (التشغيل التاسع: الجبس ينكسر بعد امتلاء الكاسرة بثوانٍ، فكانت اللقطة الأولى تُظهره قائماً)."""
    try:
        br = plaster_breakers(state)
        if not any(j in ks for ks in br.values()):
            return False
        after = apply_move(state, i, j)
        if after is None:
            return False
        vis, keep = _visible(after)
        jj = keep.index(j) if keep is not None else j
        enc = _Enc(vis)
        return _complete(enc.start[jj], enc.caps[jj])
    except (ValueError, IndexError, KeyError, TypeError):
        return False


def is_solved(state) -> bool:
    """هل القوارير الظاهرة مرتّبة؟ (المغطّاة لا تُحسب: السائق لا يعدّها فوزاً ما بقيت مغطّاة.)"""
    enc = _Enc(_visible(state)[0])
    return _solved(enc.start, enc.caps)


def describe(state) -> str:
    """وصف نصي قصير للحالة (للسجل). المغطّاة: [#ستارة:لونها] أو [#كيس] أو [#جبس]."""
    parts = []
    for t in (state or {}).get("tubes") or []:
        if t.get("blocked"):
            kind = {"curtain": "ستارة", "bag": "كيس", "plaster": "جبس"}.get(t.get("cover"), "غطاء")
            parts.append("[#%s%s]" % (kind, (":" + t["cover_color"]) if t.get("cover_color") else ""))
            continue
        layers = t.get("layers") or []
        acc = _accept_of(t)
        parts.append("[" + ",".join(str(c) for c in layers) + "]/%s" % t.get("cap", "?")
                     + ("{وسم:%s}" % acc if acc is not None else ""))
    return " ".join(parts)
