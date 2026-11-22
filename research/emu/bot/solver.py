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
"""
from __future__ import annotations

import heapq
import itertools
import time

HIDDEN = -1          # كل طبقة مخفية تُرمَّز بـ -1 (لا تُصبّ ولا يُصبّ عليها)
INF = float("inf")

__all__ = [
    "plan", "apply_move", "is_solved", "legal_moves", "state_key",
    "describe", "HIDDEN",
]


# ---------------------------------------------------------------- الترميز
def _is_hidden(c) -> bool:
    if not isinstance(c, str):
        return True
    c = c.strip().lower()
    return c == "" or c.startswith("?") or c in ("unknown", "unk", "hidden", "none")


class _Enc:
    """يحوّل الحالة (dict) إلى صفوف أعداد صحيحة: لون -> 0..K-1، مخفي -> -1."""

    def __init__(self, state: dict):
        tubes = (state or {}).get("tubes") or []
        self.names: list[str] = []
        idx: dict[str, int] = {}
        caps, enc = [], []
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


def _key(s, caps):
    """مفتاح قانوني: مجموعة (السعة، المحتوى) بلا ترتيب القوارير (تماثل)."""
    return tuple(sorted(zip(caps, s)))


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
        top = t[-1]
        if top < 0:                       # قمّة مخفية: مجمّدة
            continue
        L = len(t)
        run = 1
        while run < L and t[L - 1 - run] == top:
            run += 1
        mono = run == L                   # قارورة أحادية اللون (تشمل المنتهية)
        empty_caps = None
        for j in range(n):
            if j == i:
                continue
            u = s[j]
            space = caps[j] - len(u)
            if space <= 0:
                continue
            if u:
                if u[-1] != top:
                    continue
                amt = run if run <= space else space
                if mono and amt < run:    # صبّ جزئي من أحادية اللون: عبث
                    continue
            else:
                if mono:                  # نقل قارورة أحادية إلى فارغة: عبث
                    continue
                cj = caps[j]
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
    heap = [(w * _h(start), 0, next(cnt), start, k0)]
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
            heapq.heappush(heap, (g1 + w * _h(c), g1, next(cnt), c, kc))
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
        ms.sort(key=lambda m: _order_score(s, caps, *m))
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


def _progress_search(start, caps, budget, avoid, exclude, max_len=8):
    """احتياط: أفضل حالة قريبة (أقل h، مع الحفاظ على الفارغات). سلسلة أو None."""
    e0 = _empties(start)

    def value(s):
        v = float(_h(s))
        e = _empties(s)
        if e < e0:
            v += 1.5 * (e0 - e)
        hr = _h_reveal(s)
        if hr != INF:
            v += 0.5 * hr
        return v

    v0 = value(start)
    cnt = itertools.count()
    k0 = _key(start, caps)
    parent = {k0: None}
    depth = {k0: 0}
    heap = [(v0, 0, next(cnt), start, k0)]
    best = (v0, k0)
    while heap:
        v, g, _, s, k = heapq.heappop(heap)
        if not budget.tick():
            break
        if g >= max_len:
            continue
        for (i, j, amt) in _gen_moves(s, caps, exclude if g == 0 else None):
            c = _apply(s, i, j, amt)
            kc = _key(c, caps)
            if kc in parent or kc in avoid:
                continue
            parent[kc] = k
            depth[kc] = g + 1
            vc = value(c)
            if _solved(c, caps):
                return _chain(parent, kc)
            if vc < best[0] - 1e-9 or (abs(vc - best[0]) < 1e-9 and depth[kc] < depth.get(best[1], 99)):
                best = (vc, kc)
            heapq.heappush(heap, (vc + 0.01 * (g + 1), g + 1, next(cnt), c, kc))
    if best[1] == k0 or best[0] >= v0 - 1e-9:
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
    pos = [(ti, p) for ti, t in enumerate(s) for p, c in enumerate(t) if c < 0]
    H = len(pos)
    missing = []
    for c, n in tot.items():
        missing += [c] * max(0, n - vis.get(c, 0))
    nxt = max(list(vis) + [-1]) + 1
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
        score = (ok / tested, reveal, -e_loss, votes.get(km, 0))
        if best is None or score > best[0]:
            best = (score, (i, j))
        if time.perf_counter() > deadline:
            break
    if info is not None and best is not None:
        info["pimc"] = "%.2f/%d" % (best[0][0], n)
    return best[1] if best else None


# ---------------------------------------------------------------- الواجهة العامة
def plan(state, max_nodes=40000, time_limit=1.6, bad_moves=None, avoid=None,
         info=None, seed=None):
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
    if not s or _solved(s, caps):
        return []
    budget = _Budget(max_nodes, t0 + time_limit)
    exclude = set(tuple(m) for m in (bad_moves or ()))
    av = set()
    for a in (avoid or ()):           # مفاتيح بأسماء الألوان -> مفاتيح بالأعداد
        try:
            av.add(tuple(sorted(
                (cap, tuple(HIDDEN if c == "?" else enc.idx[c] for c in layers))
                for cap, layers in a)))
        except (KeyError, TypeError, ValueError):
            continue                  # لون غير موجود الآن: حالة لا يمكن بلوغها
    av.discard(_key(s, caps))

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
    else:
        info["mode"] = "astar"
        chain = _astar(s, caps, budget, av, exclude, w=3.0,
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
    moves = _derive_moves(s, caps, chain, exclude) if chain else []
    info["nodes"] = budget.nodes
    info["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    if not moves:
        info["mode"] += "-none"
    return moves


def state_key(state):
    """مفتاح قانوني بأسماء الألوان لحالة (dict) — لمجموعة avoid في المحرّك.
    لا يتأثر بترتيب القوارير؛ الطبقة المخفية "?"."""
    out = []
    for t in (state or {}).get("tubes") or []:
        layers = tuple("?" if _is_hidden(c) else c for c in (t.get("layers") or []))
        try:
            cap = int(t.get("cap") or 4)
        except (TypeError, ValueError):
            cap = 4
        out.append((max(cap, len(layers), 1), layers))
    return tuple(sorted(out))


def legal_moves(state):
    """كل الحركات القانونية بقواعد اللعبة (بلا تقليم)، [(i, j), ...]."""
    enc = _Enc(state)
    s, caps = enc.start, enc.caps
    out = []
    for i, t in enumerate(s):
        if not t or t[-1] < 0:
            continue
        for j, u in enumerate(s):
            if i == j or len(u) >= caps[j]:
                continue
            if u and u[-1] != t[-1]:
                continue
            out.append((i, j))
    return out


def apply_move(state, i, j):
    """يطبّق الحركة على نسخة من الحالة (dict) ويعيدها، أو None إن كانت غير قانونية.
    الطبقات المخفية تبقى "?" (يكشفها الواقع لا النموذج)."""
    tubes = (state or {}).get("tubes") or []
    if not (0 <= i < len(tubes) and 0 <= j < len(tubes)) or i == j:
        return None
    src = list(tubes[i].get("layers") or [])
    dst = list(tubes[j].get("layers") or [])
    if not src or _is_hidden(src[-1]):
        return None
    try:
        capj = max(int(tubes[j].get("cap") or 4), len(dst))
    except (TypeError, ValueError):
        capj = max(4, len(dst))
    space = capj - len(dst)
    top = src[-1]
    if space <= 0 or (dst and dst[-1] != top):
        return None
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


def is_solved(state) -> bool:
    enc = _Enc(state)
    return _solved(enc.start, enc.caps)


def describe(state) -> str:
    """وصف نصي قصير للحالة (للسجل)."""
    parts = []
    for t in (state or {}).get("tubes") or []:
        layers = t.get("layers") or []
        parts.append("[" + ",".join(str(c) for c in layers) + "]/%s" % t.get("cap", "?"))
    return " ".join(parts)
