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
    seen = {solver._key(s0, caps)}
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
                if i == j or sp <= 0 or (u and u[-1] != top):
                    continue
                c = solver._apply(s, i, j, min(run, sp))
                k = solver._key(c, caps)
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
    def test_worst_case_speed(self):
        # ألغاز كبيرة عشوائية (قد تكون مستحيلة): يجب أن يعود خلال الحد دائماً
        for seed in range(6):
            st = random_puzzle(14, 2, 9000 + seed)
            mv, dt = timed_plan(st)
            self.assertLess(dt / 1000, LIMIT_S)
            st1 = random_puzzle(12, 1, 9100 + seed)
            mv, dt = timed_plan(st1)
            self.assertLess(dt / 1000, LIMIT_S)


def _summary():
    print("\n[solver tests] calls=%d max_plan_ms=%.0f plain=%s one_empty=%s tall8=%s hidden=%s"
          % (STATS["calls"], STATS["max_ms"], STATS.get("plain"), STATS.get("one_empty"),
             STATS.get("tall8"), STATS.get("hidden")))


if __name__ == "__main__":
    import atexit
    atexit.register(_summary)
    unittest.main(verbosity=2)
