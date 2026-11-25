# -*- coding: utf-8 -*-
"""اختبارات الحلّال (solver.py) بألغاز مصطنعة.

التشغيل:  python3 research/emu/bot/test_solver.py      (أو python3 -m unittest)
يطبع في النهاية ملخّصاً: نسب الحل وأطول زمن لاستدعاء plan.
"""
import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import solver  # noqa: E402

COLORS = ["red", "orange", "yellow", "green", "lime", "blue", "lightblue",
          "purple", "pink", "lavender", "brown", "teal", "gray", "white"]

STATS = {"max_ms": 0.0, "calls": 0}
LIMIT_S = 2.0


def timed_plan(state, **kw):
    t = time.perf_counter()
    mv = solver.plan(state, **kw)
    dt = (time.perf_counter() - t) * 1000
    STATS["max_ms"] = max(STATS["max_ms"], dt)
    STATS["calls"] += 1
    return mv, dt


def mk(tubes):
    """tubes: [(cap, [layers...]), ...] -> state dict (x,y وهمية)."""
    return {"tubes": [{"x": 40 + 80 * k, "y": 400, "cap": c, "layers": list(l)}
                      for k, (c, l) in enumerate(tubes)]}


def random_puzzle(ncol, nempty, seed, cap=4):
    rnd = random.Random(seed)
    layers = [c for c in COLORS[:ncol] for _ in range(cap)]
    rnd.shuffle(layers)
    tubes = [(cap, layers[k * cap:(k + 1) * cap]) for k in range(ncol)]
    tubes += [(cap, []) for _ in range(nempty)]
    return mk(tubes)


def run_moves(state, moves):
    cur = state
    for (i, j) in moves:
        cur = solver.apply_move(cur, i, j)
        if cur is None:
            return None
    return cur


def reference_solvable(state, limit=300000):
    """مرجع مستقل: بحث عمقي بلا أي تقليم (كل الحركات القانونية). True/False/None."""
    enc = solver._Enc(state)
    s0, caps = enc.start, enc.caps
    acc = enc.accept                     # «Tag!»: لا يُصبّ في الموسومة إلا لونها

    def rkey(s):
        return tuple(sorted((caps[k], acc.get(k, -1), s[k]) for k in range(len(s))))
    seen = {rkey(s0)}
    stack = [s0]
    n = 0
    while stack:
        s = stack.pop()
        n += 1
        if solver._solved(s, caps):
            return True
        if n > limit:
            return None
        for i, t in enumerate(s):
            if not t or t[-1] < 0:
                continue
            top = t[-1]
            run = 1
            while run < len(t) and t[-1 - run] == top:
                run += 1
            for j, u in enumerate(s):
                sp = caps[j] - len(u)
                if i == j or sp <= 0 or (u and u[-1] != top) or acc.get(j, top) != top:
                    continue
                c = solver._apply(s, i, j, min(run, sp))
                k = rkey(c)
                if k not in seen:
                    seen.add(k)
                    stack.append(c)
    return False


def solvable_puzzles(ncol, nempty, count, seed0):
    out = []
    seed = seed0
    while len(out) < count and seed < seed0 + 200:
        st = random_puzzle(ncol, nempty, seed)
        if reference_solvable(st):
            out.append((seed, st))
        seed += 1
    return out


# ------------------------------------------------ محاكاة الطبقات المخفية
class HiddenGame:
    """لعبة بحقيقة كاملة؛ اللاعب يرى "?" حتى تصير الطبقة في القمّة."""

    def __init__(self, state, hide_tubes, rnd):
        self.caps = [t["cap"] for t in state["tubes"]]
        self.truth = [list(t["layers"]) for t in state["tubes"]]
        self.hidden = [[False] * len(t) for t in self.truth]
        for k in hide_tubes:
            for p in range(len(self.truth[k]) - 1):     # كل شيء إلا القمّة
                self.hidden[k][p] = True

    def view(self):
        tubes = []
        for k, t in enumerate(self.truth):
            layers = ["?" if self.hidden[k][p] else c for p, c in enumerate(t)]
            tubes.append({"x": 0, "y": 0, "cap": self.caps[k], "layers": layers})
        return {"tubes": tubes}

    def move(self, i, j):
        src, dst = self.truth[i], self.truth[j]
        if not src or i == j:
            return False
        top = src[-1]
        run = 1
        while run < len(src) and src[-1 - run] == top and not self.hidden[i][-1 - run]:
            run += 1
        space = self.caps[j] - len(dst)
        if space <= 0 or (dst and dst[-1] != top):
            return False
        amt = min(run, space)
        for _ in range(amt):
            dst.append(src.pop())
            self.hidden[i].pop()
            self.hidden[j].append(False)
        if src:
            self.hidden[i][-1] = False                  # الكشف
        return True

    def solved(self):
        return solver.is_solved(self.view())


def play_hidden(game, max_steps=300):
    avoid = set()
    for step in range(max_steps):
        v = game.view()
        if solver.is_solved(v):
            return True, step
        avoid.add(solver.state_key(v))
        mv, _ = timed_plan(v, avoid=avoid)
        if not mv:
            return False, step
        i, j = mv[0]
        if not game.move(i, j):
            raise AssertionError("الحلّال اقترح حركة غير قانونية: %r" % ((i, j),))
    return False, max_steps


class TestBasics(unittest.TestCase):
    def test_apply_move_rules(self):
        st = mk([(4, ["red", "blue", "blue"]), (4, ["green", "blue"]), (4, []), (4, ["red"])])
        a = solver.apply_move(st, 0, 1)          # كتلة من طبقتين، الفراغ 2
        self.assertEqual(a["tubes"][1]["layers"], ["green", "blue", "blue", "blue"])
        self.assertEqual(a["tubes"][0]["layers"], ["red"])
        self.assertIsNone(solver.apply_move(st, 0, 3))   # لون مختلف
        b = solver.apply_move(st, 1, 0)          # يُصبّ ما يتّسع فقط
        self.assertEqual(b["tubes"][0]["layers"], ["red", "blue", "blue", "blue"])
        self.assertEqual(b["tubes"][1]["layers"], ["green"])
        h = mk([(4, ["?", "?", "red"]), (4, [])])
        c = solver.apply_move(h, 0, 1)
        self.assertEqual(c["tubes"][0]["layers"], ["?", "?"])
        self.assertIsNone(solver.apply_move(c, 0, 1))    # القمّة مخفية

    def test_is_solved(self):
        self.assertTrue(solver.is_solved(mk([(4, ["red"] * 4), (4, []), (4, ["blue"] * 4)])))
        self.assertFalse(solver.is_solved(mk([(4, ["red"] * 4), (4, ["blue", "red"])])))
        self.assertFalse(solver.is_solved(mk([(4, ["red"] * 2), (4, ["red"] * 2)])))
        self.assertFalse(solver.is_solved(mk([(4, ["?", "red", "red", "red"])])))
        # لون في قارورتين ممتلئتين: لا دمج ممكن = محلول
        self.assertTrue(solver.is_solved(mk([(4, ["red"] * 4), (4, ["red"] * 4)])))
        # القارورة الطويلة غير ممتلئة ومعها قارورة من لونها: غير محلول
        self.assertFalse(solver.is_solved(mk([(8, ["red"] * 4), (4, ["red"] * 4)])))

    def test_already_solved_returns_empty(self):
        st = mk([(4, ["red"] * 4), (4, ["blue"] * 4), (4, [])])
        self.assertEqual(timed_plan(st)[0], [])

    def test_stuck_position(self):
        # كل القوارير ممتلئة، القمم مختلفة، لا فارغة: لا حركة
        st = mk([(4, ["red", "blue", "green", "yellow"]),
                 (4, ["blue", "green", "yellow", "red"]),
                 (4, ["green", "yellow", "red", "blue"]),
                 (4, ["yellow", "red", "blue", "green"])])
        self.assertEqual(timed_plan(st)[0], [])
        # الحركة القانونية الوحيدة نقل قارورة أحادية إلى فارغة: عبث = لا حركة
        st2 = mk([(4, ["red", "blue", "red", "blue"]), (4, ["blue", "red", "blue", "red"]),
                  (4, ["green"] * 4), (4, [])])
        mv, _ = timed_plan(st2)
        self.assertNotIn((2, 3), mv)

    def test_never_pour_from_finished_tube(self):
        st = mk([(4, ["red"] * 4), (4, ["blue", "green", "blue", "green"]),
                 (4, ["green", "blue", "green", "blue"]), (4, []), (4, [])])
        mv, _ = timed_plan(st)
        self.assertTrue(mv)
        self.assertTrue(all(i != 0 for i, _ in mv), mv)
        end = run_moves(st, mv)
        self.assertTrue(end is not None and solver.is_solved(end))

    def test_no_pointless_moves(self):
        for seed, st in solvable_puzzles(8, 2, 6, 500):
            mv, _ = timed_plan(st)
            cur = st
            for k, (i, j) in enumerate(mv):
                src = cur["tubes"][i]["layers"]
                dst = cur["tubes"][j]["layers"]
                mono = len(set(src)) == 1
                self.assertFalse(mono and not dst, "نقل أحادي إلى فارغة seed=%d" % seed)
                if k:
                    self.assertNotEqual((j, i), mv[k - 1], "A->B->A seed=%d" % seed)
                cur = solver.apply_move(cur, i, j)
                self.assertIsNotNone(cur)

    def test_bad_moves_and_avoid(self):
        st = mk([(4, ["red", "red", "red", "blue"]), (4, ["blue", "blue", "blue", "red"]),
                 (4, [])])
        mv, _ = timed_plan(st)
        self.assertTrue(mv)
        first = mv[0]
        mv2, _ = timed_plan(st, bad_moves={first})
        if mv2:
            self.assertNotEqual(mv2[0], first)
        # الحالة بعد الحركة الأولى ممنوعة: لا يعود الحلّال إليها
        nxt = solver.apply_move(st, *first)
        mv3, _ = timed_plan(st, avoid={solver.state_key(nxt)})
        if mv3:
            self.assertNotEqual(solver.state_key(run_moves(st, mv3[:1])), solver.state_key(nxt))

    def test_state_key_order_independent(self):
        a = mk([(4, ["red", "?"]), (4, []), (8, ["blue"])])
        b = mk([(8, ["blue"]), (4, ["red", "?"]), (4, [])])
        self.assertEqual(solver.state_key(a), solver.state_key(b))


class TestBlocked(unittest.TestCase):
    """القوارير المغطّاة (ستارة/كيس، "blocked"): محتواها مجهول، لا يُصبّ منها ولا فيها، ولا تُحسب في المفتاح والحل."""

    def board(self):
        st = mk([(4, ["red", "blue", "red", "blue"]), (4, []), (4, ["blue", "red", "blue", "red"]),
                 (4, []), (4, []), (4, ["green", "green"])])
        st["tubes"][1].update(blocked=True, cover="curtain", cover_color="red")
        st["tubes"][4].update(blocked=True, cover="bag")
        return st

    def test_plan_never_touches_blocked(self):
        st = self.board()
        mv, _ = timed_plan(st)
        self.assertTrue(mv)
        self.assertFalse({1, 4} & {k for m in mv for k in m}, mv)
        end = run_moves(st, mv)                    # الخطة كاملة صالحة بالفهارس الأصلية وتحلّ الظاهر
        self.assertIsNotNone(end)
        self.assertTrue(solver.is_solved(end))
        self.assertEqual(end["tubes"][1]["layers"], [])
        self.assertEqual(end["tubes"][4]["layers"], [])

    def test_rules(self):
        st = self.board()
        self.assertIsNone(solver.apply_move(st, 0, 1))      # لا يُصبّ في مغطّاة (ليست فارغة)
        self.assertIsNone(solver.apply_move(st, 1, 0))
        self.assertIsNotNone(solver.apply_move(st, 0, 3))
        lm = solver.legal_moves(st)
        self.assertTrue(lm)
        self.assertFalse({1, 4} & {k for m in lm for k in m}, lm)
        self.assertFalse(solver.key_freed(st, 0, 1))

    def test_key_and_solved_ignore_blocked(self):
        st = self.board()
        bare = mk([(4, ["red", "blue", "red", "blue"]), (4, ["blue", "red", "blue", "red"]), (4, []),
                   (4, ["green", "green"])])
        self.assertEqual(solver.state_key(st), solver.state_key(bare))
        done = mk([(4, ["red"] * 4), (4, []), (4, ["blue"] * 4)])
        done["tubes"][1]["blocked"] = True
        self.assertTrue(solver.is_solved(done))           # الظاهر مرتّب (السائق لا يعدّه فوزاً ما بقيت مغطّاة)
        self.assertIn("#ستارة:red", solver.describe(st))

    def test_bad_moves_use_original_indices(self):
        st = self.board()
        first = timed_plan(st)[0][0]
        mv2, _ = timed_plan(st, bad_moves={first})
        self.assertTrue(mv2)
        self.assertNotEqual(mv2[0], first)
        self.assertFalse({1, 4} & set(mv2[0]))
        nxt = solver.apply_move(st, *first)
        mv3, _ = timed_plan(st, avoid={solver.state_key(nxt)})
        self.assertTrue(mv3)
        self.assertNotEqual(solver.state_key(run_moves(st, mv3[:1])), solver.state_key(nxt))


class TestPlainPuzzles(unittest.TestCase):
    def test_plain_8_to_14_tubes(self):
        total = solved = 0
        for ncol in (6, 8, 10, 12):          # + فارغتان = 8..14 قارورة
            for seed, st in solvable_puzzles(ncol, 2, 6, 1000 * ncol):
                mv, dt = timed_plan(st)
                end = run_moves(st, mv)
                ok = end is not None and solver.is_solved(end)
                total += 1
                solved += ok
                self.assertLess(dt / 1000, LIMIT_S, "بطيء ncol=%d seed=%d" % (ncol, seed))
                self.assertTrue(ok, "لم يُحل: ncol=%d seed=%d %s" % (ncol, seed, solver.describe(st)))
        STATS["plain"] = "%d/%d" % (solved, total)

    def test_one_empty_tube(self):
        found = 0
        for seed, st in solvable_puzzles(7, 1, 4, 77):
            mv, dt = timed_plan(st)
            end = run_moves(st, mv)
            self.assertTrue(end is not None and solver.is_solved(end), solver.describe(st))
            found += 1
        STATS["one_empty"] = found


class TestClay(unittest.TestCase):
    """«الطين» (Magic Sort من المرحلة 40): يُصبّ في القارورة ولا يُصبّ منها حتى تكتمل."""

    def _clay_state(self):
        # حالة المرحلة 40 كما قرأها البوت: ثماني ألوان، والقوارير الفارغة الأربع كلها طين
        rows = ['pink blue lavender blue', 'orange green green green', None, None,
                'orange pink purple', 'lavender yellow blue orange', 'blue pink lavender',
                'yellow lavender purple purple', None, None, 'red purple pink',
                'green yellow orange yellow', 'red red red']
        st = mk([(4, r.split() if r else []) for r in rows])
        for k, r in enumerate(rows):
            if r is None:
                st["tubes"][k]["clay"] = True
        return st

    def test_no_pour_from_clay(self):
        st = self._clay_state()
        clay = {k for k, t in enumerate(st["tubes"]) if t.get("clay")}
        mv, _ = timed_plan(st)
        self.assertTrue(mv)
        cur = st
        for (i, j) in mv:
            self.assertNotIn(i, clay)
            cur = solver.apply_move(cur, i, j)
            self.assertIsNotNone(cur)
        self.assertTrue(solver.is_solved(cur))
        for k in clay:                      # ما صُبّ في الطين لون واحد كامل
            lay = cur["tubes"][k]["layers"]
            self.assertTrue(not lay or (len(lay) == 4 and len(set(lay)) == 1), lay)

    def test_clay_rules(self):
        st = mk([(4, ['red', 'red']), (4, ['red', 'blue']), (4, [])])
        st["tubes"][0]["clay"] = True
        self.assertIsNone(solver.apply_move(st, 0, 2))      # لا صبّ من الطين
        self.assertIsNotNone(solver.apply_move(st, 1, 2))
        self.assertNotIn((0, 2), solver.legal_moves(st))
        self.assertEqual(solver._NOSRC, frozenset())        # لا يبقى أثر بعد plan
        timed_plan(st)
        self.assertEqual(solver._NOSRC, frozenset())


class TestTallTube(unittest.TestCase):
    def _giant_puzzle(self, seed, gcap=8, ginit=4):
        rnd = random.Random(seed)
        cols = COLORS[:7]
        layers = [c for c in cols[1:] for _ in range(4)] + [cols[0]] * (gcap - ginit)
        rnd.shuffle(layers)
        tubes = [(4, layers[k:k + 4]) for k in range(0, len(layers), 4)]
        tubes.insert(rnd.randrange(len(tubes)), (gcap, [cols[0]] * ginit))
        tubes += [(4, []), (4, [])]
        return mk(tubes)

    def test_tall_tube_cap8(self):
        done = 0
        for seed in range(40):
            st = self._giant_puzzle(seed)
            if not reference_solvable(st):
                continue
            mv, dt = timed_plan(st)
            end = run_moves(st, mv)
            self.assertTrue(end is not None and solver.is_solved(end), solver.describe(st))
            g = [t for t in end["tubes"] if t["cap"] == 8][0]
            self.assertEqual(g["layers"], ["red"] * 8)        # الطويلة امتلأت بلونها
            done += 1
            if done >= 6:
                break
        self.assertGreaterEqual(done, 4)
        STATS["tall8"] = done

    def test_tall_tube_cap10(self):
        st = self._giant_puzzle(3, gcap=10, ginit=2)
        if reference_solvable(st):
            mv, _ = timed_plan(st)
            end = run_moves(st, mv)
            self.assertTrue(end is not None and solver.is_solved(end))

    def test_finished_normal_tube_merges_into_tall(self):
        # أربع حمراوات في قارورة عادية ممتلئة + الطويلة فيها 4: يجب الدمج
        st = mk([(8, ["red"] * 4), (4, ["red"] * 4), (4, ["blue"] * 4), (4, [])])
        mv, _ = timed_plan(st)
        self.assertEqual(mv, [(1, 0)])

    def test_level14_like_with_hidden(self):
        # شبيه بالمرحلة 14 (HARD): خمس قوارير بثلاث مخفيات، لا فارغة، وطويلة زرقاء
        st = mk([(4, ["?", "?", "?", "green"]), (4, ["?", "?", "?", "blue"]),
                 (4, ["?", "?", "?", "yellow"]), (4, ["?", "?", "?", "red"]),
                 (4, ["?", "?", "?", "lavender"]),
                 (4, ["blue", "blue", "orange"]), (4, ["purple", "pink", "pink"]),
                 (4, ["green", "orange", "lavender"]), (4, ["orange", "green", "pink"]),
                 (4, ["green", "lavender", "red"]), (8, ["blue"] * 4)])
        mv, dt = timed_plan(st)
        self.assertTrue(mv)
        # الكشف الأرخص: الأزرق فوق المخفيات إلى الطويلة الزرقاء
        self.assertEqual(mv[-1], (1, 10))


class TestHidden(unittest.TestCase):
    def test_hidden_layers_interactive(self):
        rnd = random.Random(42)
        total = wins = 0
        for ncol in (6, 8, 10):
            for seed, st in solvable_puzzles(ncol, 2, 8, 3000 + 10 * ncol):
                nonempty = [k for k, t in enumerate(st["tubes"]) if t["layers"]]
                hide = rnd.sample(nonempty, max(1, len(nonempty) // 2))
                g = HiddenGame(st, hide, rnd)
                ok, steps = play_hidden(g)
                total += 1
                wins += ok
        STATS["hidden"] = "%d/%d" % (wins, total)
        # لا ضمان مع معلومات ناقصة وبلا تراجع ولا أدوات، لكن يجب أن ينجح في الغالبية
        self.assertGreaterEqual(wins / total, 0.75, STATS["hidden"])

    def test_reveal_search_keeps_an_empty_tube(self):
        # بحث الكشف (الاحتياطي): كشف بحركة واحدة يستهلك الفارغة الوحيدة، وكشف آخر
        # بحركتين يصبّ على ألوان مطابقة -> يختار الثاني
        st = mk([(4, ["?", "?", "?", "red"]),
                 (4, ["?", "?", "green", "blue"]),
                 (4, ["yellow", "blue"]),
                 (4, ["yellow", "green"]),
                 (4, [])])
        enc = solver._Enc(st)
        chain, _ = solver._reveal_search(enc.start, enc.caps,
                                         solver._Budget(20000, time.perf_counter() + 2), set(), set())
        self.assertEqual(solver._derive_moves(enc.start, enc.caps, chain), [(1, 2), (1, 3)])

    def test_pimc_prefers_completing_reveal(self):
        # الأحمر فوق المخفيات يكمل قارورة حمراء ويكشف معاً، بدل صبّه في الفارغة
        st = mk([(4, ["?", "?", "?", "red"]), (4, ["red", "red", "red"]),
                 (4, ["blue", "blue", "green", "green"]), (4, ["green", "green", "blue", "blue"]),
                 (4, [])])
        info = {}
        mv, _ = timed_plan(st, info=info)
        self.assertEqual(mv[:1], [(0, 1)], info)

    def test_hidden_in_the_middle(self):
        # المخفية بين طبقتين معروفتين (كالمرحلة 13)
        st = mk([(4, ["red", "?", "?", "green"]), (4, ["green", "green", "green"]),
                 (4, ["red", "red", "red"]), (4, [])])
        mv, _ = timed_plan(st)
        self.assertEqual(mv, [(0, 1)])


class TestSpeed(unittest.TestCase):
    # ---- المفاتيح والأبواب (المرحلتان 63 و74): كشف طبقة المفتاح يفتح باباً يخفي قوارير
    def _mkk(self, tubes, keys):
        st = mk(tubes)
        for k, ps in keys.items():
            st["tubes"][k]["keys"] = ps
        return st

    def test_key_priority_over_progress(self):
        """مفتاح تحت كتلة وردية يمكن نقلها: الحركة الأولى تكشفه (لا حركات «تقدّم» أخرى)."""
        st = self._mkk([(4, ["green", "red", "pink", "pink"]), (4, ["blue", "blue", "yellow"]),
                        (4, ["yellow", "yellow"]), (4, ["red", "pink"]), (4, ["blue", "green"]), (4, [])], {0: [1]})
        info = {}
        mv, _ = timed_plan(st, info=info)
        self.assertEqual(info["mode"], "key")
        self.assertEqual(mv[0][0], 0)
        after = st
        for (i, j) in mv:
            after = solver.apply_move(after, i, j)
        self.assertEqual(after["tubes"][0]["layers"], ["green", "red"])     # طبقة المفتاح في القمة
        self.assertTrue(solver.key_freed(st, *mv[-1]) or len(mv) > 1)

    def test_keys_first_can_be_turned_off(self):
        """keys_first=False: لا بحث «المفاتيح أولاً» (تنويع المحاولات المتكرّرة)، والحالة نفسها تُخطَّط بغيره بلا دفن المفتاح."""
        st = self._mkk([(4, ["green", "red", "pink", "pink"]), (4, ["blue", "blue", "yellow"]),
                        (4, ["yellow", "yellow"]), (4, ["red", "pink"]), (4, ["blue", "green"]), (4, [])], {0: [1]})
        info = {}
        mv = solver.plan(st, info=info, keys_first=False, time_limit=2.0)
        self.assertNotEqual(info.get("mode"), "key")
        self.assertIs(info.get("keys_first"), False)
        self.assertTrue(mv)
        info2 = {}
        solver.plan(st, info=info2, time_limit=2.0)
        self.assertEqual(info2["mode"], "key")          # القيمة الافتراضية كما كانت، والعلَم يعود بعد الاستدعاء

    def test_key_dig_through_hidden(self):
        """المرحلة 74: [?، أحمر بمفتاح، ?، أزرق] — يُصبّ الأزرق أولاً لينكشف المخفي فوق المفتاح."""
        st = self._mkk([(4, ["?", "red", "?", "blue"]), (4, ["orange", "blue"]), (4, ["red", "red", "red"]),
                        (4, ["yellow", "yellow", "orange"]), (4, [])], {0: [1]})
        info = {}
        mv, _ = timed_plan(st, info=info)
        self.assertEqual(info["mode"], "key")
        self.assertEqual(mv[0], (0, 1))           # فوق أزرق مثله، لا في الفارغة
        self.assertFalse(solver.key_freed(st, 0, 1))
        st2 = self._mkk([(4, ["?", "red", "blue"]), (4, ["orange", "blue"])], {0: [1]})
        self.assertTrue(solver.key_freed(st2, 0, 1))

    def test_key_not_buried(self):
        """لا يمكن كشف المفتاح الآن: لا تُدفن طبقته تحت أحمر آخر ما دامت حركة غيرها."""
        st = self._mkk([(4, ["orange", "blue", "red"]), (4, ["green", "yellow", "yellow", "red"]),
                        (4, ["green", "green", "purple"]), (4, ["orange", "orange", "purple"])], {0: [1]})
        self.assertIn((1, 0), solver.legal_moves(st))
        mv, _ = timed_plan(st)
        self.assertTrue(mv)
        self.assertNotEqual(mv[0], (1, 0))

    def test_exposed_key_poured_out(self):
        """مفتاح مكشوف لم يطر (لو كانت القاعدة «صبّ طبقته خارجها»): يُصبّ لونه من قارورته."""
        st = self._mkk([(4, ["orange", "blue"]), (4, ["blue", "blue"]), (4, ["orange", "orange", "orange"]),
                        (4, ["yellow"] * 4)], {0: [1]})
        info = {}
        mv, _ = timed_plan(st, info=info)
        self.assertEqual(info["mode"], "key")
        self.assertEqual(mv[0], (0, 1))
        self.assertTrue(solver.key_freed(st, 0, 1))

    def test_level74_board_from_image(self):
        """لوحة L074_keys كما تقرؤها الرؤية: أول حركة تحفر نحو المفتاح الأخضر (القارورة 3)."""
        st = {"tubes": [
            {"x": 64, "y": 332, "cap": 4, "layers": ["purple", "lavender", "pink", "cyan"]},
            {"x": 133, "y": 332, "cap": 4, "layers": ["?", "brown", "yellow", "yellow"]},
            {"x": 201, "y": 332, "cap": 4, "layers": ["?", "cyan"]},
            {"x": 270, "y": 332, "cap": 4, "layers": ["?", "red", "?", "blue"], "keys": [1]},
            {"x": 339, "y": 332, "cap": 4, "layers": ["?", "pink", "?", "pink"]},
            {"x": 407, "y": 332, "cap": 4, "layers": ["red", "cyan", "yellow", "purple"]},
            {"x": 64, "y": 538, "cap": 4, "layers": ["darkgreen", "red", "red"]},
            {"x": 133, "y": 538, "cap": 4, "layers": ["blue", "brown", "brown", "brown"]},
            {"x": 202, "y": 621, "cap": 10, "layers": ["orange"] * 9, "tall": True},
            {"x": 270, "y": 643, "cap": 10, "layers": ["plum"] * 10, "tall": True},
            {"x": 338, "y": 537, "cap": 4, "layers": ["orange", "blue"]},
            {"x": 407, "y": 538, "cap": 4, "layers": ["green", "green"]}]}
        info = {}
        mv, _ = timed_plan(st, info=info)
        self.assertEqual(info["mode"], "key")
        self.assertEqual(mv[0], (3, 10))

    def test_level64_board_from_image(self):
        """لوحة L064_key_doors: المفتاح على البني تحت بني وأصفر؛ يُصبّ الأصفر في الفارغة فتنكشف طبقته."""
        st = self._mkk([(4, ["brown", "lavender", "lavender", "lavender"]), (4, ["brown", "brown", "yellow"]),
                        (4, ["cyan"] * 3), (4, ["green"] * 2), (4, ["red", "pink", "pink", "pink"]), (4, [])], {1: [0]})
        info = {}
        mv, _ = timed_plan(st, info=info)
        self.assertEqual(info["mode"], "key")
        self.assertEqual(mv, [(1, 5)])
        self.assertTrue(solver.key_freed(st, 1, 5))

    def test_worst_case_speed(self):
        # ألغاز كبيرة عشوائية (قد تكون مستحيلة): يجب أن يعود خلال الحد دائماً
        for seed in range(6):
            st = random_puzzle(14, 2, 9000 + seed)
            mv, dt = timed_plan(st)
            self.assertLess(dt / 1000, LIMIT_S)
            st1 = random_puzzle(12, 1, 9100 + seed)
            mv, dt = timed_plan(st1)
            self.assertLess(dt / 1000, LIMIT_S)


class TestPlaster(unittest.TestCase):
    """الجبس (من المرحلة 100): قالب محجوب ("cover": "plaster") ينكسر حين تكتمل (تمتلئ بلون واحد) قارورة ظاهرة في خانة مجاورة له
    في صفّه. المواضع والصناديق بإحداثيات لقطات التشغيل التاسع (خطوة الخانات 68 أو 78)."""

    @staticmethod
    def tb(x, y, layers, box_bottom=None, cap=4, **kw):
        d = {"x": x, "y": y, "cap": cap, "layers": list(layers)}
        if box_bottom is not None:
            d["box"] = [x - 31, box_bottom - 176, x + 31, box_bottom]
        d.update(kw)
        return d

    def pl(self, x, y, box_bottom=None):
        return self.tb(x, y, [], box_bottom, blocked=True, cover="plaster")

    def l108(self):
        """بداية المرحلة 108 كما تقرؤها الرؤية: ستة قوالب في الصفّين الأعلى بينها أربع كاسرات طين، وأربع قوارير تحتها؛ لا فارغة
        ولا حلّ للظاهر وحده (الخزامي والوردي والبنفسجي طبقة واحدة)."""
        tb, pl = self.tb, self.pl
        return {"tubes": [
            pl(100, 336, 424), tb(168, 330, ["cyan"] * 2, 418, clay=True), pl(237, 336, 424),
            tb(304, 330, ["yellow"] * 2, 418, clay=True), pl(374, 336, 424),
            pl(100, 542, 630), tb(167, 537, ["green"] * 2, 625, clay=True), pl(237, 542, 630),
            tb(304, 536, ["orange"] * 2, 624, clay=True), pl(374, 542, 630),
            tb(133, 743, ["yellow", "yellow", "lavender"], 831), tb(201, 743, ["red", "green", "green"], 831),
            tb(270, 743, ["pink", "purple", "cyan"], 831), tb(339, 743, ["orange", "orange", "red"], 831)]}

    def test_breakers_by_position(self):
        """كاسرة الجبس جارته الظاهرة يميناً أو يساراً في صفّه؛ جار جبسٌ أو ستارة ليس كاسرة؛ والقارورة الطويلة على صفّين (المرحلة
        110) تكسر جبس صفّ قاعدتها لا صفّ قمّتها."""
        self.assertEqual(solver.plaster_breakers(self.l108()),
                         {0: [1], 2: [1, 3], 4: [3], 5: [6], 7: [6, 8], 9: [8]})
        tb, pl = self.tb, self.pl
        l110 = {"tubes": [
            tb(40, 375, ["?", "?", "?", "blue"], 476), tb(118, 499, ["blue"] * 4, cap=10, tall=True,
                                                         box=[84, 300, 154, 698]),
            tb(196, 374, ["?", "?", "?", "brown"], 475), pl(276, 381, 481), tb(353, 374, ["pink"] * 2, 475, clay=True),
            pl(432, 381, 481), pl(42, 642, 742), pl(198, 642, 742), tb(274, 636, ["pink", "purple", "blue", "blue"], 737),
            tb(353, 636, ["blue", "purple", "purple", "pink"], 737), tb(431, 636, ["purple", "blue", "brown", "blue"], 737)]}
        self.assertEqual(solver.plaster_breakers(l110), {3: [2, 4], 5: [4], 6: [1], 7: [1, 8]})
        # بلا "box" (حالة مصطنعة): الصفّ من نقطة القارورة، والنتيجة نفسها في لوحة بسيطة
        bare = {"tubes": [pl(100, 336), tb(168, 330, ["red"]), pl(236, 336), tb(304, 330, [], blocked=True, cover="curtain"),
                          pl(372, 336), tb(100, 537, ["blue"]), tb(168, 537, ["blue"])]}
        self.assertEqual(solver.plaster_breakers(bare), {0: [1], 2: [1], 4: []})
        self.assertEqual(solver.plaster_breakers(mk([(4, ["red"]), (4, [])])), {})

    def test_l108_plan_completes_breaker_first(self):
        """المرحلة 108: الحلّ الظاهر مستحيل (كان البوت يتقدّم بلا هدف ثم «Give Up»)؛ الخطة الآن تكمل الأخضر أولاً (فينكسر الجبس عن
        جارتيه) ولا تلمس قالباً."""
        st = self.l108()
        info = {}
        mv, _ = timed_plan(st, info=info)
        self.assertEqual(info["mode"], "plaster", info)
        self.assertEqual(mv, [(11, 6)])
        self.assertTrue(solver.breaker_completed(st, 11, 6))
        self.assertFalse({0, 2, 4, 5, 7, 9} & {k for m in mv for k in m})
        end = run_moves(st, mv)
        self.assertEqual(end["tubes"][6]["layers"], ["green"] * 4)

    def test_breaker_needs_digging(self):
        """الكاسرة (طين) تحتاج الأصفر المدفون تحت الخزامي: يُنقل الخزامي إلى الفارغة ثم يُصبّ الأصفر فيها فتكتمل (خطة «plaster»
        تنتهي بإكمالها)، ولا يُصبّ من الكاسرة أبداً."""
        tb, pl = self.tb, self.pl
        st = {"tubes": [pl(100, 336, 424), tb(168, 330, ["yellow", "yellow"], 418, clay=True), pl(236, 336, 424),
                        tb(133, 537, ["yellow", "yellow", "lavender"], 625), tb(201, 537, ["red", "lavender", "red"], 625),
                        tb(270, 537, [], 625)]}
        info = {}
        mv, _ = timed_plan(st, info=info)
        self.assertEqual(info["mode"], "plaster")
        self.assertTrue(mv and len(mv) <= 3, mv)
        self.assertTrue(solver.breaker_completed(run_moves(st, mv[:-1]), *mv[-1]), mv)
        self.assertTrue(all(i != 1 for i, _ in mv))

    def test_mono_pours_into_breaker(self):
        """في كاسرة الجبس لا يُعدّ عبثاً صبّ قارورة أحادية اللون غير مكتملة في فارغة (المرحلة 103: كاسرة فارغة بفتات) ولا صبّ جزء
        منها؛ أما المكتملة فمسدودة بسدادة ذهبية لا يُصبّ منها أبداً (حركات التشغيلين الرابع والسادس منها كلها «لا تقدّم»)."""
        tb, pl = self.tb, self.pl
        st = {"tubes": [pl(100, 336, 424), tb(168, 330, [], 418, clay=True), tb(236, 330, ["blue"] * 3, 418),
                        tb(304, 330, ["green", "blue"], 418), tb(372, 330, ["red", "green"], 418)]}
        info = {}
        mv, _ = timed_plan(st, info=info)
        self.assertEqual(info["mode"], "plaster", info)
        self.assertIn(mv, ([(2, 1), (3, 1)], [(3, 1), (2, 1)]))
        self.assertEqual(run_moves(st, mv)["tubes"][1]["layers"], ["blue"] * 4)
        st2 = {"tubes": [pl(100, 336, 424), tb(168, 330, ["red", "red"], 418, clay=True), tb(236, 330, ["red"] * 3, 418),
                         tb(304, 330, ["blue", "green"], 418), tb(372, 330, ["green", "blue"], 418)]}
        mv2, _ = timed_plan(st2)
        self.assertEqual(mv2[:1], [(2, 1)])
        self.assertEqual(run_moves(st2, mv2[:1])["tubes"][1]["layers"], ["red"] * 4)
        # المكتملة (الأزرق ×4، الأحمر ×4) لا تُصبّ كلها في كاسرة فارغة ولا جزءاً منها في كاسرة من لونها
        st3 = {"tubes": [pl(100, 336, 424), tb(168, 330, [], 418, clay=True), tb(236, 330, ["blue"] * 4, 418),
                         tb(304, 330, ["red", "green"], 418)]}
        mv3, _ = timed_plan(st3)
        self.assertFalse(any(i == 2 for i, _ in mv3), mv3)
        st4 = {"tubes": [pl(100, 336, 424), tb(168, 330, ["red", "red"], 418, clay=True), tb(236, 330, ["red"] * 4, 418),
                         tb(304, 330, ["blue", "green"], 418), tb(372, 330, ["green", "blue"], 418), tb(440, 330, [], 418)]}
        mv4, _ = timed_plan(st4)
        self.assertFalse(any(i == 2 for i, _ in mv4), mv4)

    def test_sorted_board_with_empty_breaker(self):
        """الظاهر مرتّب (كل لون في قارورة مكتملة) والجبس قائم وجاره كاسرة فارغة: المكتملة مسدودة فلا حركة (طريق مسدود حقيقي، تعرض
        له اللعبة «No Available Moves»). وطويلة أحادية غير مكتملة تملأ الكاسرة الفارغة: خطة «plaster» من لوح «محلول»."""
        tb, pl = self.tb, self.pl
        st = {"tubes": [pl(100, 336, 424), tb(168, 330, [], 418, clay=True), tb(236, 330, ["blue"] * 4, 418),
                        tb(304, 330, ["red"] * 4, 418)]}
        self.assertTrue(solver.is_solved(st))
        self.assertEqual(timed_plan(st)[0], [])
        st2 = {"tubes": [pl(100, 336, 424), pl(168, 336, 424), tb(236, 330, ["blue"] * 4, 418), tb(304, 330, [], 418)]}
        self.assertEqual(timed_plan(st2)[0], [])
        st3 = {"tubes": [pl(100, 336, 424), tb(168, 330, [], 418, clay=True), tb(236, 330, ["blue"] * 6, 418, cap=10, tall=True),
                         tb(304, 330, ["red"] * 4, 418)]}
        self.assertTrue(solver.is_solved(st3))
        info = {}
        mv, _ = timed_plan(st3, info=info)
        self.assertEqual((mv, info["mode"]), ([(2, 1)], "plaster"))
        self.assertTrue(solver.breaker_completed(st3, 2, 1))

    def test_breaker_completed(self):
        st = self.l108()
        self.assertTrue(solver.breaker_completed(st, 11, 6))      # الأخضر الثالث والرابع: تكتمل الكاسرة
        self.assertFalse(solver.breaker_completed(st, 12, 1))     # سماوي واحد: لا تكتمل
        self.assertFalse(solver.breaker_completed(st, 13, 8))     # أحمر فوق البرتقالي: غير قانونية
        self.assertFalse(solver.breaker_completed(st, 0, 1))      # القالب لا يُصبّ منه
        self.assertFalse(solver.breaker_completed(mk([(4, ["red"] * 3), (4, ["red"])]), 1, 0))   # بلا جبس

    def test_fallback_with_hidden_layers(self):
        """لا تسلسل يكمل كاسرة (لونها مخفي): يعود الحلّال إلى طرقه المعتادة بلا لمس القوالب ولا أثر بعده."""
        tb, pl = self.tb, self.pl
        st = {"tubes": [pl(100, 336, 424), tb(168, 330, ["plum"], 418, clay=True), pl(236, 336, 424),
                        tb(133, 537, ["?", "?", "red", "blue"], 625), tb(201, 537, ["?", "blue", "red"], 625),
                        tb(270, 537, [], 625), tb(338, 537, ["red", "blue"], 625)]}
        info = {}
        mv, _ = timed_plan(st, info=info)
        self.assertIn(info["mode"].split("-")[0], ("pimc", "reveal", "progress"), info)
        self.assertTrue(mv)
        self.assertFalse({0, 2} & {k for m in mv for k in m})
        self.assertEqual((solver._FILL, solver._PLASTER), (frozenset(), ()))

    def test_plain_levels_unchanged(self):
        """بلا جبس لا يتغيّر شيء: خطط مسجّلة من الحلّال قبل الجبس (ألغاز ثابتة، ومنها قارورة طين) تطابق حرفاً بحرف."""
        cases = [((5, 2, 11), None, [(0, 5), (1, 5), (1, 6), (2, 0), (1, 2), (4, 6), (0, 1), (0, 6), (0, 1), (3, 1),
                                      (3, 5), (3, 6), (2, 3), (2, 4)]),
                 ((6, 1, 15), None, [(3, 6), (0, 3), (4, 6), (5, 6), (2, 5), (2, 4), (3, 2), (1, 3)]),
                 ((6, 2, 21), 6, [(0, 6), (0, 7), (1, 0), (1, 7), (2, 0), (2, 6), (3, 1), (3, 6), (4, 6), (3, 4), (0, 3),
                                  (4, 0), (4, 7), (2, 4), (5, 7), (5, 0), (1, 5), (1, 4)])]
        for (ncol, nempty, seed), clay, want in cases:
            st = random_puzzle(ncol, nempty, seed)
            if clay is not None:
                st["tubes"][clay]["clay"] = True
            mv, _ = timed_plan(st, max_nodes=40000, time_limit=5.0)
            self.assertEqual(mv, want, (ncol, nempty, seed))


def _released(L, p):
    return p >= len(L) or all(x == L[p] for x in L[p:])


def play_with_door(base, key, door_tubes, use_doors, max_steps=60, tl=0.8):
    """لعبة بباب واحد: قوارير الباب تظهر (في آخر القائمة) حين يتحرّر المفتاح (قاعدة اللعبة). البوت يخطّط ويطبّق حتى ينفتح
    الباب أو تنتهي الخطة ثم يعيد التخطيط. use_doors: يعرف ما خلف الباب (محاولة سابقة للبداية نفسها). يعيد (حُلّت؟، الحركات)."""
    tubes = [list(l) for l in base]
    opened, visited, steps = False, set(), 0
    while steps < max_steps:
        st = mk([(4, l) for l in tubes])
        if not opened:
            st["tubes"][key[0]]["keys"] = [key[1]]
        elif solver.is_solved(st):
            return True, steps
        visited.add(solver.state_key(st))
        doors = None
        if use_doors and not opened:
            doors = [{"key": key, "tubes": [{"x": 0, "y": 0, "cap": 4, "layers": list(l)} for l in door_tubes]}]
        mv, dt = timed_plan(st, avoid=visited, doors=doors, time_limit=tl, max_nodes=20000)
        if not mv:
            return False, steps
        for (i, j) in mv:
            st = solver.apply_move(st, i, j)
            if st is None:
                return False, steps
            tubes = [list(t["layers"]) for t in st["tubes"]]
            steps += 1
            if not opened and _released(tubes[key[0]], key[1]):
                opened = True
                tubes += [list(l) for l in door_tubes]
                break
    return False, steps


class TestDoors(unittest.TestCase):
    """ذاكرة الأبواب (التشغيل 12، المرحلة 124): ما خلف الباب ثابت لكل بداية، فالمحاولة التالية تعرفه وتبحث في المسألة كلها."""
    BASE = [["green", "yellow", "blue", "yellow"], ["yellow", "red", "blue", "red"], ["blue", "blue", "red", "red"], []]
    KEY = (0, 2)
    DOOR = [["green", "yellow", "green", "green"]]

    def door_spec(self):
        return [{"key": self.KEY, "tubes": [{"x": 0, "y": 0, "cap": 4, "layers": list(l)} for l in self.DOOR]}]

    def test_doors_aware_plan_solves_where_keys_first_fails(self):
        """«المفاتيح أولاً» يصبّ الأصفر في الفارغة الوحيدة فينفتح الباب واللغز الكامل بلا حل؛ ومع معرفة ما خلفه يُحلّ."""
        st = mk([(4, l) for l in self.BASE])
        st["tubes"][0]["keys"] = [2]
        info = {}
        self.assertEqual(solver.plan(st, info=info), [(0, 3)])
        self.assertEqual(info["mode"], "key")
        after = solver.apply_move(st, 0, 3)
        full = mk([(4, t["layers"]) for t in after["tubes"]] + [(4, self.DOOR[0])])
        self.assertIs(reference_solvable(full), False)          # فتح الباب بأسرع طريق خسارة مؤكّدة
        ok, _ = play_with_door(self.BASE, self.KEY, self.DOOR, use_doors=False)
        self.assertFalse(ok)
        info = {}
        mv = solver.plan(st, info=info, doors=self.door_spec())
        self.assertEqual(info["mode"], "doors-full")
        self.assertNotEqual(mv[0], (0, 3))
        self.assertTrue(solver._DOOR_LINE[len(mv) - 1][1])     # الخطة تتوقف عند الحركة التي تفتح الباب
        self.assertTrue(all(i < 4 and j < 4 for i, j in mv))   # بفهارس الحالة الظاهرة
        ok, steps = play_with_door(self.BASE, self.KEY, self.DOOR, use_doors=True)
        self.assertTrue(ok)
        self.assertLessEqual(steps, 15)

    def test_doors_fallback_unchanged(self):
        """باب بمفتاح غير صالح (طبقة لا توجد): لا بحث أبواب، والمنطق المعتاد كما كان."""
        st = mk([(4, l) for l in self.BASE])
        st["tubes"][0]["keys"] = [2]
        info = {}
        mv = solver.plan(st, info=info, doors=[{"key": (3, 5), "tubes": [{"x": 0, "y": 0, "cap": 4, "layers": ["red"]}]}])
        self.assertEqual((mv, info["mode"], info["doors"]), ([(0, 3)], "key", 0))
        info = {}
        solver.plan(st, info=info, doors=[])
        self.assertNotIn("doors", info)

    def test_hidden_layer_behind_door_falls_back(self):
        """طبقة مخفية في قارورة الباب: المعرفة ناقصة، فلا بحث أبواب (لا خطة جشعة تأخذ مكان «المفاتيح أولاً» وPIMC) والخطة كما
        كانت بلا أبواب تماماً."""
        base = [["red", "blue", "red"], ["blue", "blue", "blue"], ["red", "red"], []]
        st = mk([(4, l) for l in base])
        st["tubes"][0]["keys"] = [1]
        info0 = {}
        want = solver.plan(st, info=info0)
        info = {}
        mv = solver.plan(st, info=info, doors=[{"key": (0, 1), "tubes": [
            {"x": 0, "y": 0, "cap": 4, "layers": ["yellow", "?", "yellow"]}]}])
        self.assertEqual((info["doors_res"], info["doors"]), ("hidden", 1))
        self.assertEqual((mv, info["mode"]), (want, info0["mode"]))
        # ومفتاح داخل قارورة الباب لا يُعرف بابه: كذلك
        info = {}
        mv = solver.plan(st, info=info, doors=[{"key": (0, 1), "tubes": [
            {"x": 0, "y": 0, "cap": 4, "layers": ["yellow", "yellow", "yellow"], "keys": [0]}]}])
        self.assertEqual((mv, info["doors_res"]), (want, "hidden"))

    def test_invalid_spec_tubes_never_open(self):
        """مواصفة مرفوضة (مفتاح على طبقة لا توجد) مع باب صالح: قواريرها لا تصير قوارير مفتوحة وهمية (لا حركة إليها)، والمسألة
        ناقصة فالخطة كما كانت."""
        st = mk([(4, l) for l in self.BASE])
        st["tubes"][0]["keys"] = [2]
        P = solver._Doors(st, self.door_spec() + [{"key": (3, 5), "tubes": [{"x": 0, "y": 0, "cap": 4, "layers": []},
                                                                            {"x": 0, "y": 0, "cap": 4, "layers": []}]}])
        self.assertEqual((len(P.specs), sorted(P.never)), (1, [5, 6]))
        mask = P.settle(P.s0, (1 << len(P.keylist)) - 1)
        self.assertTrue(P.all_open(mask))
        self.assertTrue({5, 6} <= P.locked(mask))
        self.assertTrue(all(i < 5 and j < 5 for i, j, _a in P.moves(P.s0, mask)))
        self.assertFalse(P.complete(mask))
        info = {}
        mv = solver.plan(st, info=info, doors=self.door_spec() + [{"key": (3, 5), "tubes": [
            {"x": 0, "y": 0, "cap": 4, "layers": []}, {"x": 0, "y": 0, "cap": 4, "layers": []}]}])
        self.assertEqual((mv, info["doors_res"]), ([(0, 3)], "hidden"))

    def test_dead_end_door_state_retried_without_avoid(self):
        """«الطريق المسدود» يضمّ حالة يمرّ بها كل حلّ كامل (انفتاح الباب): يُعاد بحث الأبواب بدون avoid فلا تضيع المعرفة."""
        st = mk([(4, l) for l in self.BASE])
        st["tubes"][0]["keys"] = [2]
        mv = solver.plan(st, doors=self.door_spec())
        cur = st
        avoid = set()
        for m in mv:
            cur = solver.apply_move(cur, *m)
            avoid.add(solver.state_key(cur))
        info = {}
        mv2 = solver.plan(st, info=info, doors=self.door_spec(), avoid=avoid)
        self.assertEqual(info["mode"], "doors-full")
        self.assertTrue(mv2)

    def test_l124_cyan_start_with_known_doors(self):
        """بداية المرحلة 124 «السماوية» من سجل التشغيل 12 بالبابين المعروفين: فيهما «?» ومفاتيح لا يُعرف بابها، فلا بحث أبواب،
        والخطة كما كانت بلا أبواب لكل keys_first (التنويع يبقى له أثره) وفي وقتها."""
        start = {"tubes": [
            {"x": 236, "y": 634, "cap": 10, "layers": ["cyan", "cyan"]},
            {"x": 98, "y": 743, "cap": 4, "layers": ["purple", "orange", "darkgreen", "plum"]},
            {"x": 168, "y": 743, "cap": 4, "layers": ["green", "cyan", "green", "green"]},
            {"x": 304, "y": 743, "cap": 4, "layers": ["plum", "plum", "cyan", "cyan"], "keys": [0]},
            {"x": 372, "y": 743, "cap": 4, "layers": ["cyan", "cyan", "darkgreen", "plum"], "keys": [0]}]}
        doors = [{"key": (3, 0), "tubes": [
                     {"x": 98, "y": 538, "cap": 4, "layers": ["darkgreen", "?", "?", "lavender"], "keys": [0]},
                     {"x": 167, "y": 538, "cap": 4, "layers": ["yellow", "purple", "brown", "darkgreen"], "keys": [1]}]},
                 {"key": (4, 0), "tubes": [
                     {"x": 98, "y": 332, "cap": 4, "layers": ["?", "brown", "?", "lavender"]},
                     {"x": 168, "y": 332, "cap": 4, "layers": ["lavender", "orange", "cyan", "cyan"]}]}]
        for kf in (True, False):
            info0, info = {}, {}
            want = solver.plan(start, info=info0, keys_first=kf, time_limit=LIMIT_S)
            mv, dt = timed_plan(start, info=info, doors=doors, keys_first=kf, time_limit=LIMIT_S)
            self.assertEqual((info["doors_res"], info["doors"], info["mode"]), ("hidden", 2, info0["mode"]))
            self.assertLess(dt / 1000, LIMIT_S * 1.2)
            self.assertIn(mv[0], solver.legal_moves(start))

    def test_vary_and_seed(self):
        """vary=0 كما كان تماماً؛ vary>0 يغيّر كسر التعادل (خطط مختلفة بين المحاولات) ويبقى الحل صحيحاً."""
        firsts = set()
        for seed in range(5):
            st = random_puzzle(6, 2, 4400 + seed)
            base = solver.plan(st, time_limit=3.0)
            self.assertEqual(solver.plan(st, time_limit=3.0, vary=0, seed=None), base)
            for v in (1, 2, 3):
                mv = solver.plan(st, time_limit=3.0, vary=v, seed=11 * v)
                if base:
                    self.assertTrue(mv)
                    self.assertTrue(solver.is_solved(run_moves(st, mv)))
                    firsts.add((seed, tuple(mv[:3])))
        self.assertGreater(len(firsts), 5)
        self.assertIsNone(solver._TIE)                          # يعود بعد الاستدعاء


GOLDEN_UNTAGGED = {   # (ألوان، فارغات، بذرة random_puzzle، vary) -> خطة الحلّال قبل «Tag!» (e24ec61)
    (5, 2, 7101, 0): [(0, 5), (1, 6), (2, 6), (2, 5), (3, 1), (0, 3), (0, 2), (3, 0), (3, 6), (0, 3), (4, 2), (1, 0), (1, 5), (0, 1), (4, 1), (4, 6), (2, 4)],
    (5, 2, 7101, 1): [(0, 5), (2, 6), (2, 5), (1, 6), (3, 1), (0, 3), (2, 0), (4, 0), (3, 2), (3, 6), (2, 3), (1, 2), (4, 2), (1, 5), (1, 2), (4, 6), (0, 4), (0, 3)],
    (7, 2, 7102, 0): [(0, 7), (0, 8), (1, 8), (2, 0), (2, 8), (3, 2), (4, 7), (4, 8), (5, 7), (3, 5), (2, 3), (5, 2), (4, 5), (2, 4), (6, 5), (6, 1), (6, 7), (5, 6), (3, 5), (0, 3)],
    (7, 2, 7102, 1): [(5, 7), (0, 7), (4, 7), (1, 0), (4, 8), (6, 4), (6, 1), (6, 7), (4, 6), (5, 4), (0, 8), (5, 6), (3, 5), (2, 0), (2, 8), (3, 4), (3, 5), (0, 3), (2, 5), (2, 4)],
    (9, 2, 7103, 0): [(6, 9), (0, 10), (0, 6), (1, 10), (2, 1), (4, 0), (5, 4), (5, 9), (5, 10), (0, 5), (8, 5), (7, 8), (0, 7), (8, 0), (8, 9), (8, 10), (1, 8), (3, 1), (3, 0), (3, 9), (3, 8), (2, 3), (4, 2), (4, 0), (6, 3), (6, 1), (4, 6), (7, 6), (7, 1), (3, 7)],
    (9, 2, 7103, 1): [(7, 9), (8, 10), (4, 10), (5, 4), (6, 5), (8, 9), (5, 8), (1, 5), (2, 1), (0, 5), (0, 6), (10, 0), (8, 10), (5, 8), (0, 5), (7, 0), (3, 7), (3, 9), (3, 10), (1, 3), (7, 1), (2, 7), (4, 2), (6, 7), (4, 9), (0, 4), (6, 1), (4, 6)],
    (10, 3, 7104, 0): [(0, 10), (6, 0), (7, 10), (0, 11), (0, 6), (4, 0), (8, 4), (9, 8), (7, 9), (7, 0), (6, 7), (3, 6), (1, 3), (2, 1), (5, 6), (1, 12), (1, 10), (6, 1), (4, 6), (3, 4), (3, 10), (3, 12), (2, 3), (2, 7), (2, 6), (9, 3), (9, 0), (3, 9), (5, 2), (5, 12), (5, 11), (8, 2), (8, 11), (2, 8)],
    (10, 3, 7104, 1): [(7, 10), (0, 10), (6, 0), (6, 11), (5, 6), (3, 6), (9, 5), (9, 7), (4, 9), (8, 4), (1, 3), (2, 1), (7, 12), (2, 12), (7, 9), (2, 7), (4, 2), (7, 11), (3, 4), (3, 10), (1, 3), (1, 10), (6, 1), (2, 6), (0, 2), (0, 11), (9, 0), (9, 12), (5, 7), (5, 3), (8, 7), (2, 5), (8, 5), (7, 8)],
    (6, 1, 7105, 0): [(1, 6), (4, 1), (6, 4), (3, 6), (0, 3), (5, 6), (5, 0), (6, 5)],
    (6, 1, 7105, 1): [(1, 6), (4, 1), (6, 4), (3, 6), (0, 3), (5, 6), (5, 0), (6, 5)],
    (12, 2, 7106, 0): [(1, 12), (2, 13), (6, 12), (2, 6), (2, 12), (7, 2), (0, 7), (10, 13), (1, 10), (3, 1), (3, 13), (0, 3), (0, 12), (8, 0), (8, 13), (4, 8), (2, 4), (3, 2), (4, 3), (0, 4), (8, 0), (5, 8), (5, 2), (6, 5), (9, 6), (9, 5), (1, 9), (6, 1), (6, 8), (9, 6), (8, 9), (7, 8), (7, 6), (4, 7), (11, 8), (11, 1), (11, 0), (10, 11), (8, 10)],
    (12, 2, 7106, 1): [(6, 12), (4, 13), (1, 12), (7, 4), (11, 7), (9, 11), (6, 9), (11, 6), (13, 11), (9, 13), (3, 9), (2, 3), (2, 13), (2, 12), (2, 4), (10, 2), (1, 10), (1, 9), (3, 2), (6, 1), (5, 6), (5, 3), (5, 13), (9, 5), (6, 9), (11, 6), (10, 11), (0, 10), (7, 10), (7, 5), (8, 7), (8, 2), (8, 6), (8, 9), (0, 8), (0, 12), (3, 8), (0, 7), (4, 3), (4, 7)],
}


def mk_tags(tubes):
    """tubes: [(cap, [layers...], لون الوسم أو None), ...] -> حالة فيها قوارير موسومة («Tag!»)."""
    st = mk([(c, l) for c, l, _a in tubes])
    for t, (_c, _l, a) in zip(st["tubes"], tubes):
        if a:
            t["accept"] = a
    return st


# بداية المرحلة 130 كما تقرؤها الرؤية (testdata/L130_tags.jpg): أربع قوارير فارغة موسومة ولا فارغة عادية
L130 = [(4, ["pink", "yellow", "yellow", "blue"], None), (4, [], "lavender"), (4, ["yellow", "red", "orange", "pink"], None),
        (4, ["green", "red", "red", "yellow"], None), (4, [], "purple"), (4, ["lavender", "green", "lavender", "green"], None),
        (4, ["blue", "purple", "purple", "lavender"], None), (4, [], "red"), (4, ["orange", "orange", "orange", "blue"], None),
        (4, ["red", "purple", "green", "purple"], None), (4, [], "pink"), (4, ["lavender", "pink", "blue", "pink"], None)]


def tag_ok(state, moves):
    """كل حركة في الخطة قانونية بقيد الوسوم (apply_move يرفض غيرها)، والحالة النهائية."""
    cur = state
    for i, j in moves:
        t = cur["tubes"][j]
        if t.get("accept") and cur["tubes"][i]["layers"][-1] != t["accept"]:
            return False, cur
        cur = solver.apply_move(cur, i, j)
        if cur is None:
            return False, cur
    return True, cur


class TestTags(unittest.TestCase):
    """«Tag!» (من المرحلة 130): لا يُصبّ في القارورة الموسومة إلا لون وسمها (ويُصبّ منها كالعادة)."""

    def test_wrong_color_into_tagged_is_illegal(self):
        st = mk_tags([(4, ["blue", "red"], None), (4, ["red", "blue"], None), (4, [], "blue"), (4, [], None)])
        self.assertIsNone(solver.apply_move(st, 0, 2))                  # الأزرق فقط في الموسومة الزرقاء
        self.assertIsNotNone(solver.apply_move(st, 1, 2))
        self.assertIsNotNone(solver.apply_move(st, 0, 3))               # الفارغة العادية تقبل كل لون
        lm = solver.legal_moves(st)
        self.assertNotIn((0, 2), lm)
        self.assertIn((1, 2), lm)
        mv = solver.plan(st)
        ok, end = tag_ok(st, mv)
        self.assertTrue(ok and solver.is_solved(end), mv)
        # موسومة غير فارغة: يُصبّ فيها لونها، والصبّ منها حرّ (إلى فارغة عادية)
        st = mk_tags([(4, ["red"], "red"), (4, ["blue", "red"], None), (4, ["blue", "blue", "red", "red"], None), (4, [], None)])
        self.assertIsNotNone(solver.apply_move(st, 1, 0))
        self.assertIsNotNone(solver.apply_move(st, 0, 3))

    def test_full_tagged_tube_is_complete(self):
        st = mk_tags([(4, ["red"] * 4, "red"), (4, ["blue"] * 4, None), (4, [], "green"), (4, [], None)])
        self.assertTrue(solver.is_solved(st))
        self.assertEqual(solver.plan(st), [])

    def test_complete_tube_is_corked_in_legal_moves(self):
        """المكتملة تُسدّ بسدادة ذهبية فلا يُصبّ منها: لا تُعدّ حركة قانونية (التشغيل 18، المرحلة 154: الوسم الأخضر قُرئ «lavender»
        فبدت (12، 5) من الخزامي المكتمل إلى الموسومة الفارغة الحركة الوحيدة، وجُرّبت مرتين «لا تقدّم» قبل إعادة المرحلة)."""
        st = mk_tags([(4, ["lavender"] * 4, None), (4, [], "lavender"), (4, ["red", "blue"], None), (4, ["red", "blue"], None)])
        lm = solver.legal_moves(st)
        self.assertNotIn((0, 1), lm)
        self.assertFalse([m for m in lm if m[0] == 0])
        self.assertEqual(sorted(lm), [(2, 3), (3, 2)])                    # الأزرق على الأزرق يبقى قانونياً
        st2 = mk_tags([(4, ["lavender"] * 3, None), (4, [], "lavender")])  # غير مكتملة: يُصبّ منها كالعادة
        self.assertIn((0, 1), solver.legal_moves(st2))

    def test_l130_start_has_plan_with_constraint(self):
        st = mk_tags(L130)
        self.assertEqual(len(solver.legal_moves(st)), 4)                # كان 0: الموسومة قُرئت ممتلئة بلون مجهول
        self.assertIs(reference_solvable(st), True)
        info = {}
        mv, dt = timed_plan(st, info=info)
        self.assertEqual(info.get("tags"), 4)
        ok, end = tag_ok(st, mv)
        self.assertTrue(ok, mv)
        self.assertTrue(solver.is_solved(end), solver.describe(end))
        self.assertLess(dt / 1000, LIMIT_S)
        # بلا الوسوم (الحالة نفسها) تُحلّ بخطة أخرى تخالف القيد غالباً: الوسوم تغيّر البحث فعلاً
        plain = mk([(c, l) for c, l, _a in L130])
        self.assertFalse(tag_ok(st, solver.plan(plain))[0])

    def test_random_tagged_puzzles(self):
        """ألغاز عشوائية بفارغة موسومة أو اثنتين (وأحياناً فارغة عادية): كل خطة تحترم القيد، وما يحلّه المرجع المستقل يُحلّ."""
        solved = total = 0
        for seed in range(40):
            rnd = random.Random(9100 + seed)
            ncol = rnd.randint(4, 8)
            base = random_puzzle(ncol, 0, 9100 + seed)
            tubes = [(4, t["layers"], None) for t in base["tubes"]]
            cols = rnd.sample(COLORS[:ncol], 2)
            tubes += [(4, [], cols[0]), (4, [], cols[1] if seed % 3 else None)]
            st = mk_tags(tubes)
            ref = reference_solvable(st, limit=200000)
            mv, _dt = timed_plan(st, time_limit=1.6)
            ok, end = tag_ok(st, mv)
            self.assertTrue(ok, (seed, mv))
            if ref:
                total += 1
                cur, steps = st, 0
                while not solver.is_solved(cur) and steps < 6:          # كما يعيد السائق التخطيط
                    ok, cur = tag_ok(cur, mv)
                    self.assertTrue(ok)
                    if solver.is_solved(cur):
                        break
                    mv = solver.plan(cur, time_limit=1.6)
                    if not mv:
                        break
                    steps += 1
                solved += solver.is_solved(cur)
        self.assertGreater(total, 10)
        self.assertGreaterEqual(solved, total - 1)

    def test_mono_into_tagged_empty_is_generated(self):
        """نقل قارورة أحادية غير مكتملة إلى موسومة بلونها ليس عبثاً (يحرّر قارورة تقبل كل لون)؛ ومن موسومة إلى فارغة عادية عبث."""
        st = mk_tags([(4, ["red", "red"], None), (4, [], "red"), (4, ["blue"] * 4, None)])
        enc = solver._Enc(st)
        solver._ACCEPT = dict(enc.accept)
        try:
            ms = {(i, j) for i, j, _a in solver._gen_moves(enc.start, enc.caps)}
        finally:
            solver._ACCEPT = {}
        self.assertIn((0, 1), ms)
        st = mk_tags([(4, ["red", "red"], "red"), (4, [], None), (4, ["blue"] * 4, None)])
        enc = solver._Enc(st)
        solver._ACCEPT = dict(enc.accept)
        try:
            ms = {(i, j) for i, j, _a in solver._gen_moves(enc.start, enc.caps)}
        finally:
            solver._ACCEPT = {}
        self.assertNotIn((0, 1), ms)

    def test_state_key_and_avoid(self):
        """state_key: الموسومة بلون وسمها عنصراً ثالثاً (لا تماثل فارغة عادية)، وغير الموسومة كما كانت تماماً؛ وavoid يعمل بها."""
        st = mk_tags([(4, ["red", "blue"], None), (4, ["blue", "red"], None), (4, [], "blue"), (4, [], None)])
        sk = solver.state_key(st)
        self.assertIn((4, (), "blue"), sk)
        self.assertIn((4, ()), sk)
        plain = mk([(4, ["red", "blue"]), (4, ["blue", "red"]), (4, []), (4, [])])
        self.assertEqual(solver.state_key(plain), tuple(sorted([(4, ("red", "blue")), (4, ("blue", "red")), (4, ()), (4, ())])))
        self.assertNotEqual(solver.state_key(plain), sk)
        mv = solver.plan(st)
        first = solver.apply_move(st, *mv[0])
        mv2 = solver.plan(st, avoid={solver.state_key(first)})
        self.assertTrue(mv2)
        self.assertNotEqual(solver.state_key(solver.apply_move(st, *mv2[0])), solver.state_key(first))
        self.assertEqual(solver._ACCEPT, {})                            # يعود بعد الاستدعاء
        self.assertIn("{وسم:blue}", solver.describe(st))

    def test_tags_with_covers_and_pimc(self):
        """المغطّاة تُحذف قبل البحث (الفهارس تتغيّر) والوسم يتبع قارورته؛ ومع طبقات مخفية (PIMC) لا حركة تخالف القيد."""
        st = mk_tags([(4, ["red", "blue", "red", "blue"], None), (4, [], None), (4, ["blue", "red", "blue", "red"], None),
                      (4, [], "red")])
        st["tubes"].insert(1, {"x": 0, "y": 0, "cap": 4, "layers": [], "blocked": True, "cover": "curtain"})
        mv = solver.plan(st)
        ok, _end = tag_ok(st, mv)
        self.assertTrue(ok and mv, mv)
        self.assertTrue(all(i != 1 and j != 1 for i, j in mv))
        for seed in range(6):
            base = random_puzzle(5, 0, 9300 + seed)
            tubes = [(4, ["?"] + t["layers"][1:], None) for t in base["tubes"]]
            st = mk_tags(tubes + [(4, [], "red"), (4, [], None)])
            info = {}
            mv = solver.plan(st, info=info, seed=seed)
            self.assertEqual(info["mode"] in ("pimc", "reveal", "progress", "progress-none"), True, info)
            for i, j in mv:
                self.assertIn((i, j), solver.legal_moves(st))

    def test_tagged_door_tube(self):
        """قارورة باب موسومة في ذاكرة الأبواب: بحث المسألة الممتدّة يحترم وسمها (ولا يبقى _ACCEPT بعده)."""
        base = [["green", "yellow", "blue", "yellow"], ["yellow", "red", "blue", "red"], ["blue", "blue", "red", "red"], []]
        st = mk([(4, l) for l in base])
        st["tubes"][0]["keys"] = [2]
        door = [{"key": (0, 2), "tubes": [{"x": 0, "y": 0, "cap": 4, "layers": ["green", "green", "green"], "accept": "green"}]}]
        P = solver._Doors(st, door)
        self.assertEqual(P.enc.accept, {4: P.enc.idx["green"]})
        b = solver._Budget(40000, time.perf_counter() + 3)
        mv, res, nd = solver._door_search(st, door, b, None, set())
        self.assertEqual(solver._ACCEPT, {})
        self.assertEqual((res, nd), ("doors-full", 1))
        # الخط الكامل في المسألة الممتدّة (قارورة الباب بالفهرس 4) يحترم الوسم الأخضر ويحلّها
        ext = {"tubes": [dict(t) for t in st["tubes"]] + [dict(door[0]["tubes"][0])]}
        ok, end = tag_ok(ext, [m for m, _opened in solver._DOOR_LINE])
        self.assertTrue(ok)
        self.assertTrue(solver.is_solved(end), solver.describe(end))
        self.assertTrue(any(j == 4 for (_i, j), _o in solver._DOOR_LINE))          # الأخضر يُكمَل في قارورة الباب الموسومة
        self.assertTrue(all(i < 4 and j < 4 for i, j in mv))

    def test_tagged_empty_door_tube_is_respected(self):
        """قارورة باب فارغة موسومة بالأزرق: الحلّ بلا قيد يصبّ فيها الأحمر (طفرة تُهمل وسوم المسألة الممتدّة في _door_search
        تمرّ على الاختبار السابق لأن الأخضر هناك لون الوسم أصلاً)؛ بالقيد كل صبّ فيها أزرق والخط يحلّ المسألة."""
        base = [["blue", "green", "red", "green"], ["blue", "blue", "red", "green"], ["blue", "red", "green", "red"], []]
        st = mk([(4, l) for l in base])
        st["tubes"][0]["keys"] = [3]
        door = [{"key": (0, 3), "tubes": [{"x": 0, "y": 0, "cap": 4, "layers": [], "accept": "blue"}]}]
        b = solver._Budget(40000, time.perf_counter() + 3)
        solver._DOOR_LINE[:] = []
        mv, res, nd = solver._door_search(st, door, b, None, set())
        self.assertEqual((res, nd), ("doors-full", 1))
        self.assertEqual(solver._ACCEPT, {})
        rows = [list(t["layers"]) for t in st["tubes"]] + [[]]
        into = []
        for (i, j), _o in solver._DOOR_LINE:                 # محاكاة مباشرة للطبقات (قارورة الباب بالفهرس 4)
            top = rows[i][-1]
            run = 1
            while run < len(rows[i]) and rows[i][-1 - run] == top:
                run += 1
            amt = min(run, 4 - len(rows[j]))
            self.assertGreater(amt, 0, (i, j))
            if j == 4:
                into.append(top)
            rows[j] += [top] * amt
            del rows[i][-amt:]
        self.assertTrue(into)
        self.assertEqual(set(into), {"blue"})
        self.assertTrue(all(len(set(r)) <= 1 and len(r) in (0, 4) for r in rows), rows)

    def test_pimc_samples_model_hidden_tag_color(self):
        """لون وسم كل طبقاته مخفية: عيّنات PIMC تضعه في الطبقات المخفية بفهرس الوسم (كانت تخترع لوناً جديداً مكانه فلا تقبل
        الموسومة في العيّنة لوناً موجوداً: 7 عيّنات قابلة للحل من 24)."""
        st = mk_tags([(4, [], "pink")] + [(4, ["?", "?", "?", c], None) for c in ("red", "blue", "green", "yellow", "red")]
                     + [(4, [], None)])
        for seed in (0, 1):
            info = {}
            mv = solver.plan(st, info=info, seed=seed)
            self.assertTrue(mv)
            self.assertEqual(info.get("mode"), "pimc")
            self.assertEqual(info["solvable"], info["samples"], info)
        self.assertEqual(solver._ACCEPT, {})

    def test_untagged_plans_unchanged(self):
        """انحدار: بلا وسوم لا يتغيّر شيء. خطط محسوبة بالحلّال قبل «Tag!» (‏e24ec61) لألغاز ثابتة، مع التنويع وبدونه."""
        for (ncol, ne, seed, vary), exp in GOLDEN_UNTAGGED.items():
            st = random_puzzle(ncol, ne, seed)
            got = solver.plan(st, time_limit=20, max_nodes=20000, seed=1 if not vary else 5, vary=vary)
            self.assertEqual(got, exp, (ncol, ne, seed, vary))


class TestDetour(unittest.TestCase):
    """detour (التشغيل 17، المرحلة 154): avoid فيها طريق مسدود قصّ الخط المحسِّن نفسه، فطريق بديل بعيداً عنه بدل «لا حركة»."""
    START = [["cyan", "cyan", "cyan", "green"], ["cyan", "purple", "purple", "red"], [], [],
             ["lavender", "lavender", "pink", "red"], ["brown", "plum", "yellow", "mint"]]

    def st(self):
        return {"tubes": [{"x": 64 + 68 * k, "y": 743, "cap": 4, "layers": list(l)} for k, l in enumerate(self.START)]}

    def dead(self):
        s = self.st()
        out = {solver.state_key(s)}
        for m in solver.plan(s) + [(5, 3)]:
            s = solver.apply_move(s, *m)
            out.add(solver.state_key(s))
        return out

    def test_default_unchanged_and_detour_plans(self):
        s, dead = self.st(), self.dead()
        info = {}
        self.assertEqual(solver.plan(s, avoid=dead, info=info), [])
        self.assertEqual(info["mode"], "progress-none")
        info = {}
        mv = solver.plan(s, avoid=dead, info=info, detour=True)
        self.assertEqual((mv, info["mode"]), ([(0, 2)], "progress-detour"))
        cur = s
        for m in mv:
            cur = solver.apply_move(cur, *m)
            self.assertNotIn(solver.state_key(cur), dead)
        self.assertTrue(solver.legal_moves(cur))           # لا ينتهي الطريق البديل في حالة بلا حركة

    def test_detour_not_used_without_avoid_or_when_progress_works(self):
        s = self.st()
        info = {}
        self.assertEqual(solver.plan(s, info=info, detour=True), [(1, 2), (4, 2)])
        self.assertEqual(info["mode"], "progress")

    def test_detour_none_when_every_child_is_avoided(self):
        s = self.st()
        av = {solver.state_key(solver.apply_move(s, i, j)) for i, j in solver.legal_moves(s)}
        info = {}
        self.assertEqual(solver.plan(s, avoid=av, info=info, detour=True), [])
        self.assertEqual(info["mode"], "progress-detour-none")

    def test_detour_only_when_dead_states_block_progress(self):
        """الطريق البديل فقط حين قصّت حالات الطريق المسدود نفسها الخط المحسِّن (info["dead_blocked"]): لا مع حالة مسدودة لا تُبلغ،
        ولا مع حالة مقصوصة لا تحسّن بعدها، ولا حين قصّت الخطَّ حالاتُ المحاولة (avoid) لا حالات detour."""
        s, dead = self.st(), self.dead()
        irrelevant = solver.state_key({"tubes": [{"x": 0, "y": 0, "cap": 4, "layers": ["cyan"] * 4}]})
        info = {}
        self.assertEqual(solver.plan(s, avoid=dead, info=info, detour=dead), [(0, 2)])
        self.assertEqual(info["mode"], "progress-detour")
        self.assertTrue(info.get("dead_blocked"))
        info = {}
        self.assertEqual(solver.plan(s, avoid=dead | {irrelevant}, info=info, detour={irrelevant}), [])
        self.assertEqual(info["mode"], "progress-none")
        self.assertNotIn("dead_blocked", info)
        s2 = s
        for m in [(1, 2), (4, 2)]:
            s2 = solver.apply_move(s2, *m)
        child = {solver.state_key(solver.apply_move(s2, 5, 3))}
        for d in (child, {irrelevant}):
            info = {}
            self.assertEqual(solver.plan(s2, avoid=d, info=info, detour=d), [])
            self.assertEqual(info["mode"], "progress-none")
            self.assertNotIn("dead_blocked", info)


def _summary():
    print("\n[solver tests] calls=%d max_plan_ms=%.0f plain=%s one_empty=%s tall8=%s hidden=%s"
          % (STATS["calls"], STATS["max_ms"], STATS.get("plain"), STATS.get("one_empty"),
             STATS.get("tall8"), STATS.get("hidden")))


if __name__ == "__main__":
    import atexit
    atexit.register(_summary)
    unittest.main(verbosity=2)
