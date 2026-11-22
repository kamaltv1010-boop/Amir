# -*- coding: utf-8 -*-
"""محاكاة كاملة لحلقة المحرّك (driver.py) بلا محاكي ولا adb:
لعبة مزيّفة (قواعد الصبّ، الطبقات المخفية، نوافذ الفوز، الأدوات، نقرات ضائعة)
+ جهاز مزيّف + رؤية مزيّفة + ساعة افتراضية. يتحقق أن البوت ينهي كل المراحل
ويعدّها ويحفظ لقطاتها ويحترم أوامر التحكم عن بعد.

التشغيل:  python3 research/emu/bot/test_driver.py
"""
import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import driver  # noqa: E402
import solver  # noqa: E402

COLORS = ["red", "orange", "yellow", "green", "blue", "purple", "pink", "lavender", "lime", "teal"]


class FakeClock:
    """ساعة افتراضية: sleep تقدّم الوقت فوراً."""

    def __init__(self):
        self.t = 1_000_000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += max(0.0, float(s))

    def strftime(self, fmt, *a):
        import time as _t
        return _t.strftime(fmt, _t.gmtime(self.t))

    def perf_counter(self):
        import time as _t
        return _t.perf_counter()


class FakeGame:
    def __init__(self, levels, rng, mistap=0.0):
        self.levels = levels
        self.rng = rng
        self.mistap = mistap
        self.li = 0
        self.screen = "loading"
        self.loading_left = 3
        self.snapshots = {}
        self.next_id = 1
        self.wins = 0
        self.taps = 0
        self.taps_at_last_win = 0
        self.boosters_used = []
        self.winpop0_shown = 0
        self.popup_before = {2}            # نافذة «ميزة جديدة» قبل المرحلة الثالثة
        self.load(0)

    # ---- المرحلة
    def load(self, k):
        caps, truth, hidden = self.levels[k][:3]
        self.caps = list(caps)
        self.truth = [list(t) for t in truth]
        self.hidden = [list(h) for h in hidden]
        self.selected = None
        self.history = []

    def layout(self):
        n = len(self.truth)
        per = n if n <= 5 else (n + 1) // 2
        pos = []
        for k in range(n):
            r, c = divmod(k, per)
            m = per if r == 0 else n - per
            x = int(473 * (c + 0.5) / m)
            y = 506 if n <= 5 else (375 if r == 0 else 636)
            pos.append((x, y))
        return pos

    def visible(self):
        tubes = []
        for k, (x, y) in enumerate(self.layout()):
            lifted = self.selected == k
            tubes.append({"x": x, "y": y - (25 if lifted else 0), "cap": self.caps[k],
                          "layers": ["?" if self.hidden[k][p] else c for p, c in enumerate(self.truth[k])],
                          "tall": self.caps[k] > 4, "lifted": lifted})
        return {"tubes": tubes, "warnings": []}

    def solved(self):
        return solver.is_solved({"tubes": [{"cap": c, "layers": list(t)} for c, t in zip(self.caps, self.truth)]})

    # ---- الشاشات
    KIND = {"level": "level", "winpop0": "close", "winpop": "button", "home": "button",
            "popup": "close", "loading": "unknown", "shuffle": "unknown"}

    def snapshot(self):
        if self.screen == "loading":
            self.loading_left -= 1
            if self.loading_left < 0:
                self.screen = "home"
        sid = self.next_id
        self.next_id += 1
        self.snapshots[sid] = {"kind": self.KIND[self.screen], "screen": self.screen,
                               "state": self.visible() if self.screen == "level" else None}
        if self.screen == "winpop0":
            self.winpop0_shown += 1
            if self.winpop0_shown >= 2:
                self.screen = "winpop"
        return sid

    # ---- النقر
    def tube_at(self, x, y):
        best = None
        for k, (tx, ty) in enumerate(self.layout()):
            d = abs(x - tx) + abs(y - ty)
            if abs(x - tx) < 30 and abs(y - ty) < 90 and (best is None or d < best[0]):
                best = (d, k)
        return best[1] if best else None

    def tap(self, x, y):
        self.taps += 1
        if self.rng.random() < self.mistap:
            return
        s = self.screen
        if s in ("level", "shuffle"):
            if abs(y - 854) < 35:
                for name, bx in (("undo", 144), ("shuffle", 236), ("add", 328)):
                    if abs(x - bx) < 35:
                        self.booster(name)
                return
            k = self.tube_at(x, y)
            if k is None:
                return
            if s == "shuffle":
                t = self.truth[k]
                self.rng.shuffle(t)
                self.hidden[k] = [False] * len(t)
                self.screen = "level"
                return
            if self.selected is None:
                if self.truth[k]:
                    self.selected = k
            elif self.selected == k:
                self.selected = None
            else:
                self.pour(self.selected, k)
                self.selected = None
                if self.solved():
                    self.screen = "winpop0"
                    self.winpop0_shown = 0
        elif s == "winpop" and abs(x - 236) < 80 and abs(y - 652) < 40:
            self.wins += 1
            self.taps_at_last_win = self.taps
            self.screen = "home"
            self.li += 1
            if self.li < len(self.levels):
                self.load(self.li)
        elif s == "winpop0" and abs(x - 415) < 30 and abs(y - 272) < 30:
            self.wins += 1                  # الإغلاق بـ X يحسب الفوز أيضاً
            self.taps_at_last_win = self.taps
            self.screen = "home"
            self.li += 1
            if self.li < len(self.levels):
                self.load(self.li)
        elif s == "home" and abs(x - 236) < 100 and abs(y - 786) < 40:
            if self.li < len(self.levels):
                self.screen = "popup" if self.li in self.popup_before else "level"
                self.popup_before.discard(self.li)
        elif s == "popup" and abs(x - 418) < 30 and abs(y - 110) < 30:
            self.screen = "level"

    def pour(self, i, j):
        src, dst = self.truth[i], self.truth[j]
        if not src:
            return False
        top = src[-1]
        run = 1
        while run < len(src) and src[-1 - run] == top and not self.hidden[i][-1 - run]:
            run += 1
        space = self.caps[j] - len(dst)
        if space <= 0 or (dst and dst[-1] != top):
            return False
        amt = min(run, space)
        self.history.append(([list(t) for t in self.truth], [list(h) for h in self.hidden]))
        for _ in range(amt):
            dst.append(src.pop())
            self.hidden[i].pop()
            self.hidden[j].append(False)
        if src:
            self.hidden[i][-1] = False
        return True

    def booster(self, name):
        self.boosters_used.append(name)
        if name == "add":
            self.truth.append([])
            self.hidden.append([])
            self.caps.append(4)
        elif name == "shuffle":
            self.screen = "shuffle"
        elif name == "undo" and self.history:
            t, h = self.history.pop()
            extra = len(self.truth) - len(t)      # قوارير أضيفت بعد الحركة تبقى
            self.truth = t + [[] for _ in range(max(0, extra))]
            self.hidden = h + [[] for _ in range(max(0, extra))]


class DoorGame(FakeGame):
    """مرحلة بمفاتيح وأبواب (المرحلتان 63 و74): قوارير خلف باب لا تظهر حتى تنكشف طبقة مفتاحه (لا شيء بلون آخر
    فوقها)، فتُدرج بين القوارير الظاهرة وتتغيّر المواضع. levels[k][3] = [{"key": (قارورة، موضع)، "tubes": [...]}]."""

    def load(self, k):
        super().load(k)
        lvl = self.levels[k]
        self.doors = [dict(d, open=False) for d in (lvl[3] if len(lvl) > 3 else [])]

    def closed(self):
        return {t for d in getattr(self, "doors", []) if not d["open"] for t in d["tubes"]}

    def layout(self):
        shut = self.closed()
        vis = [k for k in range(len(self.truth)) if k not in shut]
        n = len(vis)
        per = n if n <= 5 else (n + 1) // 2
        pos = [(-1000, -1000)] * len(self.truth)
        for r_i, k in enumerate(vis):
            r, c = divmod(r_i, per)
            m = per if r == 0 else n - per
            pos[k] = (int(473 * (c + 0.5) / m), 506 if n <= 5 else (375 if r == 0 else 636))
        return pos

    def visible(self):
        st = super().visible()
        shut = self.closed()
        keys = {}
        for d in self.doors:
            if not d["open"]:
                keys.setdefault(d["key"][0], []).append(d["key"][1])
        tubes = []
        for k, t in enumerate(st["tubes"]):
            if k in shut:
                continue
            if k in keys:
                t["keys"] = sorted(keys[k])
            tubes.append(t)
        return {"tubes": tubes, "warnings": []}

    def pour(self, i, j):
        ok = super().pour(i, j)
        for d in self.doors:
            k, p = d["key"]
            t = self.truth[k]
            if not d["open"] and p < len(t) and not self.hidden[k][p] and all(c == t[p] for c in t[p:]):
                d["open"] = True
                self.opened = getattr(self, "opened", 0) + 1
        return ok


class FakeDevice:
    def __init__(self, game):
        self.g = game
        self.W, self.H = 1080, 2280
        self.raw_ok = True
        self.keys = []
        self.launched = 0

    def screencap(self):
        sid = self.g.snapshot()
        a = np.zeros((1000, 473, 3), dtype=np.uint8)
        a[..., 0] = sid % 256
        a[..., 1] = (sid // 256) % 256
        a[..., 2] = 7
        return Image.fromarray(a)

    def to_dev(self, x, y):
        return driver.Device.to_dev(self, x, y)

    def tap(self, X, Y):
        self.g.tap(X * 1000.0 / self.H, Y * 1000.0 / self.H)

    def tap_std(self, x, y):
        self.tap(*self.to_dev(x, y))

    def swipe(self, *a):
        pass

    def key(self, code):
        self.keys.append(code)

    def focus(self):
        return "mCurrentFocus=Window{1 u0 %s/com.unity3d.player.UnityPlayerActivity}" % driver.PKG

    def launch(self):
        self.launched += 1

    def force_stop(self):
        pass

    def run(self, args, timeout=30, binary=False):
        return 0, (b"" if binary else "")

    def sh(self, cmd, timeout=30):
        return ""


class FakeVisionModule:
    def __init__(self, game, tall_cap_delta=0, warn=False):
        self.g = game
        self.tall_cap_delta = tall_cap_delta      # خطأ مقصود في سعة القارورة الطويلة
        self.warn = warn                          # تحذير دائم (مثل يد التعليم)

    def _snap(self, arr):
        return self.g.snapshots[int(arr[0, 0, 0]) + 256 * int(arr[0, 0, 1])]

    def classify(self, arr):
        return self._snap(arr)["kind"]

    def parse_level(self, arr):
        st = self._snap(arr)["state"]
        if st and self.tall_cap_delta:
            st = {"tubes": [dict(t, cap=max(len(t["layers"]), t["cap"] + self.tall_cap_delta))
                            if t["tall"] else t for t in st["tubes"]], "warnings": []}
        if st and self.warn:
            st = dict(st, warnings=["hand pointer"])
        return st

    def find_button(self, arr):
        s = self._snap(arr)["screen"]
        return {"winpop": (236, 652), "home": (236, 786)}.get(s)

    def find_close(self, arr):
        s = self._snap(arr)["screen"]
        return {"winpop0": (415, 272), "popup": (418, 110)}.get(s)


def make_level(rng, ncol, nempty=2, hide_tubes=0, giant=None):
    """مرحلة قابلة للحل (مرجع مستقل)، مع قوارير مخفية اختيارية وقارورة طويلة."""
    import test_solver as T
    for _ in range(200):
        cols = COLORS[:ncol]
        layers = [c for c in cols for _ in range(4)]
        caps = []
        tubes = []
        if giant:
            gcap, ginit = giant
            layers += [cols[0]] * (gcap - 4 - ginit)
        rng.shuffle(layers)
        for k in range(0, len(layers), 4):
            tubes.append(layers[k:k + 4])
            caps.append(4)
        if giant:
            tubes.append([cols[0]] * ginit)
            caps.append(gcap)
        for _ in range(nempty):
            tubes.append([])
            caps.append(4)
        st = {"tubes": [{"cap": c, "layers": list(t)} for c, t in zip(caps, tubes)]}
        if T.reference_solvable(st, 200000):
            hidden = [[False] * len(t) for t in tubes]
            cand = [k for k, t in enumerate(tubes) if len(t) == 4 and caps[k] == 4]
            for k in rng.sample(cand, min(hide_tubes, len(cand))):
                hidden[k] = [True] * 3 + [False]
            return caps, tubes, hidden
    raise RuntimeError("no solvable level")


class TestDriverSim(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self._time = driver.time
        driver.time = self.clock
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = dict(driver.CFG)

    def tearDown(self):
        driver.time = self._time
        driver.CFG.clear()
        driver.CFG.update(self.cfg)
        self.tmp.cleanup()

    def make_bot(self, levels, mistap=0.0, seed=1, minutes=600, tall_cap_delta=0, warn=False):
        rng = random.Random(seed)
        game = FakeGame(levels, rng, mistap=mistap)
        dev = FakeDevice(game)
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        vis = driver.Vision(FakeVisionModule(game, tall_cap_delta, warn), out)
        bot = driver.Bot(dev, vis, out, minutes, git=False)
        return game, bot, out

    def test_plays_levels_end_to_end(self):
        rng = random.Random(5)
        levels = [make_level(rng, 2, 1), make_level(rng, 4, 2), make_level(rng, 6, 2),
                  make_level(rng, 7, 2, hide_tubes=3), make_level(rng, 7, 1, giant=(8, 2)),
                  make_level(rng, 9, 2, hide_tubes=4)]
        game, bot, out = self.make_bot(levels, mistap=0.03)
        for _ in range(40):                  # حتى تنتهي المراحل (أو حدّ أمان)
            bot.run(max_iters=100)
            if game.wins >= len(levels):
                break
        log = (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")
        self.assertEqual(game.wins, len(levels), log[-3000:])
        self.assertEqual(bot.levels_done, len(levels), log[-3000:])
        for n in range(1, len(levels) + 1):
            self.assertTrue((Path(self.tmp.name) / ("L%03d_start.jpg" % n)).exists(), n)
        self.assertTrue((Path(self.tmp.name) / "levels.jsonl").exists())
        state = (Path(self.tmp.name) / "state.txt").read_text(encoding="utf-8")
        self.assertIn("مراحل مكتملة: %d" % len(levels), state)
        moves = sum(json.loads(l)["moves"] for l in
                    (Path(self.tmp.name) / "levels.jsonl").read_text(encoding="utf-8").splitlines())
        print("\n[driver sim] levels=%d moves=%d taps=%d boosters=%s virtual_min=%.1f"
              % (game.wins, moves, game.taps_at_last_win, game.boosters_used, bot.elapsed_min()))

    def test_door_opens_without_restart(self):
        """كشف طبقة المفتاح يفتح باباً تظهر خلفه قارورتان بين القوارير: يكمل البوت المحاولة نفسها (بلا «أُعيدت من
        البداية») ويفوز. الأحمر والأخضر والأزرق والأصفر 4 من كل لون، والمفتاح على الأخضر تحت أزرقين."""
        lvl = ([4] * 6,
               [["red", "green", "blue", "blue"], ["blue", "yellow", "yellow", "red"], [],
                ["green", "green", "green", "yellow"], ["red", "red", "blue", "yellow"], []],
               [[False] * 4, [False] * 4, [], [False] * 4, [False] * 4, []],
               [{"key": (0, 1), "tubes": [3, 4]}])
        rng = random.Random(3)
        game = DoorGame([lvl], rng)
        dev = FakeDevice(game)
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        bot = driver.Bot(dev, driver.Vision(FakeVisionModule(game), out), out, 600, git=False)
        for _ in range(20):
            bot.run(max_iters=100)
            if game.wins >= 1:
                break
        log = (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")
        self.assertEqual(game.wins, 1, log[-3000:])
        self.assertEqual(getattr(game, "opened", 0), 1, log[-3000:])
        self.assertIn("استمرار بلا إعادة", log)
        self.assertNotIn("أُعيدت من البداية", log)
        self.assertIn("(key،", log)                          # أول خطة: تحرير المفتاح
        self.assertIn("تحرّر مفتاحاً", log)

    def test_door_map_keeps_memory(self):
        """door_map: القوارير القديمة تُطابق داخل الجديدة بالترتيب (مخفي انكشف مقبول)، وغير ذلك None."""
        old = {"tubes": [{"layers": ["red", "?", "blue"]}, {"layers": []}, {"layers": ["green"]}]}
        new = {"tubes": [{"layers": ["pink", "pink"]}, {"layers": ["red", "yellow", "blue"]}, {"layers": []},
                         {"layers": ["?", "?"]}, {"layers": ["green"]}]}
        self.assertEqual(driver.door_map(old, new), {0: 1, 1: 2, 2: 4})
        self.assertIsNone(driver.door_map(new, old))
        moved = {"tubes": [{"layers": ["red", "?"]}, {"layers": ["blue"]}, {"layers": ["green"]}, {"layers": []}]}
        self.assertIsNone(driver.door_map(old, moved))

    def test_foreground_lost_escalates_to_relaunch(self):
        """المتجر (من إعلان تجريبي) بقي فوق اللعبة: بعد ثلاث محاولات إطلاق تُوقف اللعبة ثم تُطلق (لا حلقة إطلاق أبدية)."""
        game, bot, out = self.make_bot([make_level(random.Random(1), 2, 1)])
        game.screen = "loading"
        game.loading_left = 10 ** 6                       # شاشة مجهولة دائماً
        stops = []
        bot.dev.focus = lambda: "mCurrentFocus=Window{2 u0 com.android.vending/UnauthenticatedMainActivity}"
        bot.dev.force_stop = lambda: stops.append(1)
        bot.run(max_iters=60)
        log = (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")
        self.assertTrue(stops, log[-2000:])
        self.assertIn("إيقافها ثم تشغيلها", log)

    def test_ignored_back_relaunches_game(self):
        """التشغيل السابع: الرجوع داخل المرحلة لا يفعل شيئاً فتكرّرت «لا حركة قانونية» 40 دقيقة. بعد 4 محاولات «إعادة»
        بلا حركة بينها تُعاد اللعبة نفسها مرة واحدة، والحركة الناجحة تصفّر العدّ."""
        game, bot, out = self.make_bot([make_level(random.Random(1), 2, 1)])
        stops = []
        bot.dev.force_stop = lambda: stops.append(1)
        bot.lv = driver.LevelCtx(7, {"tubes": []}, 0.0)
        for _ in range(3):
            bot.restart_level()
        self.assertEqual((stops, bot.dev.launched, bot.dev.keys), ([], 0, [4, 4, 4]))
        bot.restart_level()
        self.assertEqual((len(stops), bot.dev.launched, bot.lv.dead_restarts), (1, 1, 0))
        log = (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")
        self.assertIn("الرجوع لم يُعِد المرحلة 7", log)
        bot.restart_level()
        bot.lv.dead_restarts = 3
        st = {"tubes": [{"x": 100, "y": 500, "cap": 4, "layers": ["red"]},
                        {"x": 200, "y": 500, "cap": 4, "layers": []}]}
        bot.do_move(st, 0, 1)
        self.assertEqual(bot.lv.dead_restarts, 0)

    def test_stuck_uses_boosters(self):
        # لغز مستحيل بلا قارورة إضافية: يجب أن يضغط أداة «قارورة»
        caps = [4, 4, 4, 4]
        truth = [["red", "blue", "green", "yellow"], ["blue", "green", "yellow", "red"],
                 ["green", "yellow", "red", "blue"], ["yellow", "red", "blue", "green"]]
        hidden = [[False] * 4 for _ in truth]
        game, bot, out = self.make_bot([(caps, truth, hidden)])
        bot.run(max_iters=60)
        self.assertIn("add", game.boosters_used)

    def test_tall_cap_underestimated(self):
        # الرؤية تقرأ سعة الطويلة 9 والحقيقة 10: يجب أن تنتهي المرحلة بالدمج المباشر
        rng = random.Random(21)
        game, bot, out = self.make_bot([make_level(rng, 6, 1, giant=(10, 2))], tall_cap_delta=-1)
        for _ in range(20):
            bot.run(max_iters=100)
            if game.wins:
                break
        self.assertEqual(game.wins, 1, (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")[-2500:])
        self.assertEqual(game.boosters_used, [])   # بلا إهدار الأدوات

    def test_persistent_warnings(self):
        # تحذير دائم من الرؤية (يد التعليم في المرحلة الأولى): يجب أن يلعب رغم ذلك
        rng = random.Random(3)
        game, bot, out = self.make_bot([make_level(rng, 2, 1), make_level(rng, 3, 1)], warn=True)
        for _ in range(20):
            bot.run(max_iters=100)
            if game.wins >= 2:
                break
        self.assertEqual(game.wins, 2)

    def test_remote_commands(self):
        rng = random.Random(9)
        game, bot, out = self.make_bot([make_level(rng, 4, 2)])
        bot.cmdq.put((5, ["pause", "shot test", "tap 540 1140"]))
        bot.run(max_iters=5)
        self.assertTrue(bot.paused)
        self.assertTrue((Path(self.tmp.name) / "005_test.jpg").exists())
        bot.cmdq.put((6, ["resume"]))
        bot.run(max_iters=600)
        self.assertFalse(bot.paused)
        self.assertEqual(game.wins, 1)
        bot.cmdq.put((7, ["stop"]))
        bot.run(max_iters=10)
        self.assertTrue(bot.stop)


class CoverGame(FakeGame):
    """قوارير تحت ستارة (تنزاح حين يكتمل لون أيقونتها) أو كيس (ينفجر بعد عدد من القوارير المكتملة)، كما في المرحلة 99:
    تظهر للرؤية قارورة "blocked" بلا طبقات، ولمسها لا يفعل شيئاً (ويُعدّ خطأً). levels[k][3] = {قارورة: (نوع، وسيط)}."""

    def load(self, k):
        super().load(k)
        lvl = self.levels[k]
        self.covers = dict(lvl[3]) if len(lvl) > 3 else {}
        self.opened_covers = []
        self.cover_taps = getattr(self, "cover_taps", 0)

    def visible(self):
        st = super().visible()
        for k, (kind, arg) in self.covers.items():
            st["tubes"][k].update(layers=[], blocked=True, cover=kind, cover_color=arg if kind == "curtain" else None)
        return st

    def tap(self, x, y):
        if self.screen == "level" and abs(y - 854) >= 35:
            k = self.tube_at(x, y)
            if k in self.covers:
                self.cover_taps += 1
                return
        super().tap(x, y)

    def pour(self, i, j):
        ok = super().pour(i, j)
        done = sum(1 for k, t in enumerate(self.truth) if len(t) == self.caps[k] and len(set(t)) == 1)
        for k, (kind, arg) in list(self.covers.items()):
            if (kind == "curtain" and [arg] * 4 in self.truth) or (kind == "bag" and done >= arg):
                del self.covers[k]
                self.opened_covers.append(kind)
        return ok


class TestCovers(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self._time = driver.time
        driver.time = self.clock
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        driver.time = self._time
        self.tmp.cleanup()

    def test_curtain_and_bag_levels(self):
        """ستارة حمراء على قارورة فيها الأصفر والأخضر، ثم كيس ينفجر بعد قارورتين مكتملتين: لا يلمسهما البوت وهما مغطّتان،
        ولا يعدّ انكشافهما «إعادة» ولا «فوزاً»، ويكمل المرحلتين."""
        tubes = [["red", "blue", "red", "blue"], ["blue", "red", "blue", "red"], ["green", "yellow", "yellow", "green"],
                 ["yellow", "green", "green", "yellow"], [], []]
        hid = [[False] * 4] * 4 + [[], []]
        levels = [([4] * 6, tubes, hid, {3: ("curtain", "red")}), ([4] * 6, tubes, hid, {3: ("bag", 2)})]
        game = CoverGame(levels, random.Random(4))
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        bot = driver.Bot(FakeDevice(game), driver.Vision(FakeVisionModule(game), out), out, 600, git=False)
        for _ in range(30):
            bot.run(max_iters=100)
            if game.wins >= 2:
                break
        log = (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")
        self.assertEqual((game.wins, bot.levels_done), (2, 2), log[-3000:])
        self.assertEqual(game.cover_taps, 0, log[-3000:])
        self.assertNotIn("أُعيدت من البداية", log)
        self.assertIn("مغطّاة 1", log)
        self.assertIn('"blocked": "curtain", "cover_color": "red"', log)
        self.assertEqual(game.opened_covers, ["bag"])            # المرحلة الثانية (load يصفّر القائمة)


class ScriptVision:
    """رؤية مزيّفة بنصّ يكتبه الاختبار في `now` (لا تنظر إلى الصورة)."""

    def __init__(self):
        self.now = {"kind": "level", "state": None, "level": None, "badge": None, "coins": None, "lives": None,
                    "give_up": None, "play_on": None, "button": None, "close": None}

    def classify(self, arr):
        return self.now["kind"]

    def parse_level(self, arr):
        st = self.now["state"]
        if st is None:
            return None
        out = {"tubes": [dict(t, layers=list(t["layers"])) for t in st["tubes"]], "warnings": []}
        if st.get("doors"):
            out["doors"] = st["doors"]
        return out

    def level_number(self, arr):
        return self.now["level"]

    def level_badge(self, arr):
        return self.now["badge"]

    def read_coins(self, arr):
        return self.now["coins"]

    def find_lives_popup(self, arr):
        return self.now["lives"]

    def find_give_up(self, arr):
        return self.now["give_up"]

    def find_play_on(self, arr):
        return self.now["play_on"]

    def find_button(self, arr):
        return self.now["button"]

    def find_close(self, arr):
        return self.now["close"]


class TabScriptVision(ScriptVision):
    """ومعها شريط التبويبات والأزرار الخضراء (المدفوعة منها بـ "paid") كما يكتبها الاختبار."""

    def tabbar_fraction(self, arr):
        return self.now.get("tabbar", 0.0)

    def green_buttons(self, arr):
        return list(self.now.get("greens") or [])

    def _paid(self, arr, b):
        return bool(b.get("paid"))


class TapDevice(FakeDevice):
    """جهاز مزيّف يسجّل النقرات بإحداثيات الارتفاع 1000."""

    def __init__(self):
        self.W, self.H = 1080, 2280
        self.raw_ok = True
        self.keys = []
        self.launched = 0
        self.taps = []

    def screencap(self):
        return Image.new("RGB", (47, 100), (12, 12, 40))

    def tap(self, X, Y):
        self.taps.append((int(round(X * 1000.0 / self.H)), int(round(Y * 1000.0 / self.H))))


def T(x, y, layers, **kw):
    d = {"x": x, "y": y, "cap": 4, "layers": list(layers)}
    d.update(kw)
    return {k: v for k, v in d.items()}


def near(p, q, tol=3):
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


class TestRun7Policies(unittest.TestCase):
    """التشغيل السابع (المرحلة 99): لا فوز كاذب حين تتغيّر اللوحة، وسياسة الأرواح و«Play On»."""

    def setUp(self):
        self.clock = FakeClock()
        self._time = driver.time
        driver.time = self.clock
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = dict(driver.CFG)

    def tearDown(self):
        driver.time = self._time
        driver.CFG.clear()
        driver.CFG.update(self.cfg)
        self.tmp.cleanup()

    def make(self, vision_cls=ScriptVision):
        sv = vision_cls()
        dev = TapDevice()
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        bot = driver.Bot(dev, driver.Vision(sv, out), out, 600, git=False)
        bot.loading_hashes, bot.daily_hashes, bot.nonet_hashes = [], [], []
        return bot, sv, dev

    def log(self):
        return (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")

    def level99(self, bot, st, n=99, active=True):
        lv = driver.LevelCtx(n, st, self.clock.time())
        lv.badge = "superhard"
        lv.active = active
        bot.lv = lv
        bot.expect_new = False
        return lv

    @staticmethod
    def board6():
        return {"tubes": [T(236, 332, []), T(99, 538, ["?", "red", "blue"]), T(167, 538, ["blue", "blue"]),
                          T(236, 538, []), T(304, 538, ["red", "red", "green"]), T(372, 538, ["green", "blue", "red", "yellow"])]}

    def feed(self, bot, n=8, until=None):
        fr = bot.grab()
        for _ in range(n):
            fr = bot.on_level(fr) or bot.grab()
            if until and until():
                break

    def test_big_door_is_not_a_win(self):
        """باب كبير انفتح فدخلت قوارير قبل القديمة وبعدها، وقارورة قديمة تغيّرت (فلا تطابق door_map)، والعنوان غير مقروء:
        كان «فوز بالمرحلة 99 (لغز جديد على الشاشة)» ومحو الذاكرة؛ الآن استمرار المحاولة نفسها وتنتقل الذاكرة إلى فهرسها الجديد."""
        bot, sv, dev = self.make()
        old = self.board6()
        lv = self.level99(bot, old)
        lv.memory = {(1, 0): "green"}
        lv.moves = 7
        new = {"tubes": [T(99, 332, [], blocked=True, cover="curtain", cover_color="red"), T(167, 332, ["yellow", "yellow"]),
                         T(236, 332, []), T(99, 538, ["?", "red", "blue"]), T(167, 538, ["blue", "blue"]), T(236, 538, []),
                         T(304, 538, ["red", "red"]), T(372, 538, ["green", "blue", "red", "yellow"]),
                         T(98, 743, ["?", "purple", "red"]), T(167, 743, ["yellow", "purple"]),
                         T(304, 743, ["purple", "purple", "green"]), T(373, 743, ["?", "blue", "yellow"])]}
        self.assertIsNone(driver.door_map(driver.with_memory(old, lv.memory), new))
        sv.now.update(kind="level", state=new, level=None)
        self.feed(bot, until=lambda: bot.lv.doors_opened)
        log = self.log()
        self.assertNotIn("فوز", log)
        self.assertEqual((bot.levels_done, bot.lv.n, bot.lv.doors_opened, bot.lv.moves), (0, 99, 1, 7), log)
        self.assertIs(bot.lv, lv)
        self.assertEqual(lv.memory, {(3, 0): "green"})
        self.assertIn("لوحة أكبر", log)

    def test_restart_keeps_level_number(self):
        """بعد «Give Up» تُفتح المرحلة نفسها بلوحة أصغر وألوان أخرى والعنوان غير مقروء: إعادة المرحلة 99 لا «فوز» ولا عدّاد
        جديد (التشغيل السابع: صار العدّاد 30..69)، وتُعتمد البداية حين تثبت اللوحة."""
        bot, sv, dev = self.make()
        big = {"tubes": [T(60 + 34 * k, 400 + 200 * (k // 6), ["red", "blue"]) for k in range(12)]}
        self.level99(bot, big, active=False)
        new = {"tubes": [T(236, 332, []), T(99, 538, ["pink", "cyan", "brown"]), T(167, 538, ["cyan", "pink"]),
                         T(236, 538, []), T(304, 538, ["brown", "brown", "pink", "cyan"]), T(372, 538, ["cyan", "pink"])]}
        sv.now.update(kind="level", state=new, level=None)
        self.feed(bot, n=10, until=lambda: len(bot.lv.start_state["tubes"]) == 6)
        log = self.log()
        self.assertNotIn("فوز", log)
        self.assertEqual((bot.levels_done, bot.lv.n, len(bot.lv.start_state["tubes"])), (0, 99, 6), log)
        self.assertIn("المرحلة 99 أُعيدت من البداية (العنوان غير مقروء", log)
        self.assertIn("بداية المرحلة 99:", log)
        self.assertIsNone(bot.restart_n)

    def test_header_number_corrects_counter_without_win(self):
        bot, sv, dev = self.make()
        big = {"tubes": [T(60 + 34 * k, 400 + 200 * (k // 6), ["red", "blue"]) for k in range(12)]}
        self.level99(bot, big, n=26, active=False)
        sv.now.update(kind="level", state=self.board6(), level=99, badge="superhard")
        self.feed(bot, n=4, until=lambda: bot.lv.n != 26)
        self.assertEqual((bot.levels_done, bot.lv.n, bot.lv.badge), (0, 99, "superhard"), self.log())
        self.assertIn("يُعتمد العنوان بلا فوز", self.log())

    def test_solved_puzzle_then_new_board_is_a_win(self):
        """اللغز محلول بنظر البوت ثم لوحة أخرى والعنوان غير مقروء (نافذة الفوز فاتت بين لقطتين): فوز كما كان."""
        bot, sv, dev = self.make()
        lv = self.level99(bot, self.board6(), n=40, active=False)
        lv.maybe_won = True
        nxt = {"tubes": [T(100, 400, ["red", "blue"]), T(200, 400, ["blue", "red"]), T(300, 400, [])]}
        sv.now.update(kind="level", state=nxt, level=None)
        self.feed(bot, n=3, until=lambda: bot.levels_done)
        self.assertEqual(bot.levels_done, 1, self.log())
        self.assertEqual(bot.lv.n, 41)

    def test_solved_with_covers_is_not_maybe_won(self):
        bot, sv, dev = self.make()
        st = {"tubes": [T(100, 400, ["red"] * 4), T(200, 400, [], blocked=True, cover="bag"), T(300, 400, ["blue"] * 4)]}
        self.level99(bot, st)
        sv.now.update(kind="level", state=st, level=99)
        bot.on_level(bot.grab())
        self.assertFalse(bot.lv.maybe_won)
        st2 = {"tubes": [T(100, 400, ["red"] * 4), T(200, 400, ["green"] * 4), T(300, 400, ["blue"] * 4)]}
        sv.now.update(state=st2)
        bot.on_level(bot.grab())
        self.assertTrue(bot.lv.maybe_won)

    def test_slot_map_and_remap_memory(self):
        old = self.board6()
        new = {"tubes": [T(99, 332, [], blocked=True), T(167, 332, ["pink"])] + [dict(t) for t in old["tubes"]]}
        new["tubes"][6] = T(304, 538, ["red", "red"])          # تغيّرت بصبّة أثناء الانفتاح
        mp = driver.slot_map(old, new)
        self.assertEqual(mp, {k: k + 2 for k in range(6)})
        self.assertEqual(driver.remap_memory({(1, 0): "green", (4, 2): "green"}, mp, new), {(3, 0): "green"})
        # غطاء انكشف في خانته (العدد نفسه): يطابق الخانة، والموازنة لا تحسب طبقاته
        a = {"tubes": [T(100, 400, ["red", "blue"]), T(200, 400, [], blocked=True, cover="curtain"), T(300, 400, [])]}
        b = {"tubes": [T(100, 400, ["red", "blue"]), T(200, 400, ["green", "yellow", "green"]), T(300, 400, [])]}
        self.assertEqual(driver.slot_map(a, b), {0: 0, 1: 1, 2: 2})
        self.assertTrue(driver.compatible(a, b))
        self.assertFalse(driver._same_tube(a["tubes"][1], a["tubes"][2]))   # المغطّاة ليست قارورة فارغة

    # ---------------------------------------------------------------- الأرواح
    LIVES = {"refill": (236, 523), "close": (424, 182), "price": 900, "timer": 556}

    def test_lives_refill_once_when_coins_suffice(self):
        bot, sv, dev = self.make()
        sv.now.update(kind="lives", lives=dict(self.LIVES), coins=1950, close=(424, 182))
        bot.on_lives(bot.grab())
        self.assertEqual(len(dev.taps), 1)
        self.assertTrue(near(dev.taps[0], (236, 523)), dev.taps)
        self.assertIn("ملء الأرواح بـ 900 عملة (الرصيد 1950", self.log())
        self.clock.sleep(5)
        bot.on_lives(bot.grab())                              # عادت النافذة فوراً: لا ضغطة «Refill» ثانية
        self.assertTrue(near(dev.taps[-1], (424, 182)), dev.taps)
        self.assertEqual(sum(1 for p in dev.taps if near(p, (236, 523))), 1)
        self.assertTrue(bot.lives_waiting())

    def test_lives_wait_without_coins(self):
        """الرصيد أقل من 900: إغلاق بـ X ثم لا يُضغط زرّ المرحلة قبل موعد الروح القادمة (عدّاد النافذة + 10 ث)، بفحص كل
        دقيقة على الأكثر؛ ثم يُضغط. لا يُلمس زرّ الإعلان أبداً."""
        bot, sv, dev = self.make()
        sv.now.update(kind="lives", lives=dict(self.LIVES), coins=150)
        t0 = self.clock.time()
        bot.on_lives(bot.grab())
        self.assertEqual(len(dev.taps), 1)
        self.assertTrue(near(dev.taps[0], (424, 182)), dev.taps)
        self.assertAlmostEqual(bot.lives_until - t0, 566, delta=1)
        self.assertIn("الرصيد 150 أقل من 900", self.log())
        sv.now.update(kind="button", button=(236, 786), lives=None)
        steps = 0
        while self.clock.time() < bot.lives_until and steps < 30:
            before = self.clock.time()
            bot.on_button(bot.grab())
            self.assertLessEqual(self.clock.time() - before, 61)
            steps += 1
        self.assertEqual(len(dev.taps), 1, dev.taps)           # لا ضغطة أثناء الانتظار
        self.assertGreaterEqual(steps, 9)
        bot.on_button(bot.grab())
        self.assertTrue(near(dev.taps[-1], (236, 786)), dev.taps)
        self.assertFalse(any(abs(p[1] - 650) < 40 for p in dev.taps))

    def test_lives_loop_runs_slowly(self):
        """الحلقة كاملة 20 دقيقة افتراضية والأرواح تعود بعد 12 دقيقة: إغلاق واحد وضغطة مرحلة واحدة بعد الموعد، لا حلقة
        نقر ولا إعلان ولا «Free Lives» ولا تصعيد بزرّ الرجوع."""
        bot, sv, dev = self.make()
        regen = self.clock.time() + 12 * 60
        lives = dict(self.LIVES, timer=12 * 60)
        sv.now.update(kind="lives", lives=lives, coins=150, close=(424, 182))
        clock = self.clock
        started = []
        keys_at_start = []

        def tap(X, Y):
            TapDevice.tap(dev, X, Y)
            p = dev.taps[-1]
            if sv.now["kind"] == "lives" and near(p, (424, 182), 8):
                sv.now.update(kind="button", button=(236, 786), lives=None)
            elif sv.now["kind"] == "button" and near(p, (236, 786), 8):
                if clock.time() >= regen:
                    started.append(clock.time())
                    keys_at_start.extend(dev.keys)
                    sv.now.update(kind="unknown", button=None)
                else:
                    sv.now.update(kind="lives", lives=dict(lives, timer=int(regen - clock.time())))
        dev.tap = tap
        for _ in range(40):
            bot.run(max_iters=10)
            if started:
                break
        self.assertTrue(started, self.log()[-1500:])
        self.assertGreaterEqual(started[0], regen)
        self.assertLess(started[0] - regen, 90)
        self.assertEqual(sum(1 for p in dev.taps if near(p, (424, 182), 8)), 1, dev.taps)
        self.assertEqual(sum(1 for p in dev.taps if near(p, (236, 786), 8)), 1, dev.taps)
        self.assertEqual(sum(1 for p in dev.taps if near(p, (236, 523), 8)), 0)
        self.assertEqual(keys_at_start, [])                   # لا زرّ رجوع طوال الانتظار

    # ---------------------------------------------------------------- «No Available Moves»
    def nomoves(self, bot, sv, badge, coins, fails=0, play_ons=0):
        st = self.board6()
        lv = self.level99(bot, st, n=99 if badge == "superhard" else 95)
        lv.badge = badge
        lv.play_ons = play_ons
        bot.level_fails[lv.n] = fails
        sv.now.update(kind="unknown", give_up=(350, 820), play_on=(124, 820, 900), coins=coins)
        bot.on_unknown(bot.grab(), "unknown")
        return lv

    def test_play_on_on_superhard_with_coins(self):
        bot, sv, dev = self.make()
        lv = self.nomoves(bot, sv, "superhard", 1950)
        self.assertEqual(dev.taps, [(124, 820)])
        self.assertEqual((lv.play_ons, lv.extra_tubes, bot.level_fails[99]), (1, 1, 0))
        self.assertIn("«Play On» (قارورة إضافية بـ 900 عملة، الرصيد 1950، مرحلة صعبة جداً)", self.log())

    def test_give_up_on_normal_level_then_play_on_after_two_fails(self):
        bot, sv, dev = self.make()
        lv = self.nomoves(bot, sv, "normal", 1950)
        self.assertEqual(dev.taps, [(350, 820)])
        self.assertEqual((bot.level_fails[95], bot.restart_n, lv.play_ons), (1, 95, 0))
        self.assertIn("«Give Up» (مرحلة عادية وإخفاقاتها 0)", self.log())
        bot2, sv2, dev2 = self.make()
        self.nomoves(bot2, sv2, "normal", 1950, fails=2)
        self.assertEqual(dev2.taps, [(124, 820)])
        self.assertIn("أُخفقت 2 مرات", self.log())

    def test_give_up_without_coins_or_after_play_on(self):
        for badge, coins, used, why in (("hard", 500, 0, "الرصيد 500 أقل من 900"), ("superhard", None, 0, "الرصيد غير مقروء"),
                                        ("superhard", 1950, 1, "«Play On» استُعمل في هذه المحاولة")):
            bot, sv, dev = self.make()
            self.nomoves(bot, sv, badge, coins, play_ons=used)
            self.assertEqual(dev.taps, [(350, 820)], (badge, coins, used))
            self.assertIn(why, self.log())

    # ---------------------------------------------------------------- إصلاحات المراجعة
    def test_next_level_header_is_inferred_win(self):
        """فوز حقيقي فاتت نافذته وmaybe_won خاطئ (بعد حركات «لا تقدّم»؛ وزرّ «Super Hard» في الواجهة لا يُقرأ رقمه): العنوان
        يعرض المرحلة التالية مباشرة فيُسجَّل فوزاً مستنتجاً (levels_done وlevels.jsonl)؛ ورقم أبعد يبقى تصحيحاً بلا فوز."""
        bot, sv, dev = self.make()
        big = {"tubes": [T(60 + 34 * k, 400 + 200 * (k // 6), ["red", "blue"]) for k in range(12)]}
        self.level99(bot, big, n=18, active=False)
        sv.now.update(kind="level", state=self.board6(), level=19, badge="superhard")
        self.feed(bot, n=4, until=lambda: bot.lv.n != 18)
        log = self.log()
        self.assertEqual((bot.levels_done, bot.lv.n), (1, 19), log)
        self.assertIn("فوز بالمرحلة 18 (لغز جديد على الشاشة: المرحلة 19)", log)
        rows = [json.loads(ln) for ln in (Path(self.tmp.name) / "levels.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["n"], r["result"]) for r in rows], [(18, "win-inferred")])

    def test_truncated_price_is_floored(self):
        """قراءة «Play On 900» مقطوعة (90) والرصيد 500 لا يكفي: «Give Up» لا «Play On»؛ ومثلها «Refill» في نافذة الأرواح."""
        bot, sv, dev = self.make()
        self.level99(bot, self.board6())
        sv.now.update(kind="unknown", give_up=(350, 820), play_on=(124, 820, 90), coins=500)
        bot.on_unknown(bot.grab(), "unknown")
        self.assertEqual(dev.taps, [(350, 820)])
        self.assertIn("الرصيد 500 أقل من 900", self.log())
        bot2, sv2, dev2 = self.make()
        sv2.now.update(kind="lives", lives=dict(self.LIVES, price=90), coins=500, close=(424, 182))
        bot2.on_lives(bot2.grab())
        self.assertEqual(len(dev2.taps), 1)
        self.assertTrue(near(dev2.taps[0], (424, 182)), dev2.taps)
        self.assertTrue(bot2.lives_waiting())

    def test_play_on_keeps_refill_reserve(self):
        """الصعبة جداً والرصيد 1050 (يكفي «Play On» وحده): «Give Up» ليبقى ثمن «Refill» (كان يصرف 1950 ← 1050 ← 150 فلا
        يُملأ أبداً)؛ والاحتياطي 0 يعيد «Play On» أولاً."""
        bot, sv, dev = self.make()
        self.nomoves(bot, sv, "superhard", 1050)
        self.assertEqual(dev.taps, [(350, 820)])
        self.assertIn("الرصيد 1050 لا يُبقي بعد ثمنه 900 احتياطي ملء الأرواح 900", self.log())
        driver.CFG["play_on_reserve"] = 0
        bot2, sv2, dev2 = self.make()
        self.nomoves(bot2, sv2, "superhard", 1050)
        self.assertEqual(dev2.taps, [(124, 820)])

    def test_give_up_starts_new_attempt_with_same_colors(self):
        """«Play On» ثم «Give Up» ثم بداية بالألوان نفسها (يقبلها compatible فكانت المحاولة القديمة تستمر بـ play_ons=1):
        محاولة جديدة للمرحلة 99 بلا فوز، و«No Available Moves» التالية والرصيد يكفي تضغط «Play On» من جديد."""
        bot, sv, dev = self.make()
        lv = self.level99(bot, self.board6())
        lv.play_ons, lv.extra_tubes = 1, 1
        sv.now.update(kind="unknown", give_up=(350, 820), play_on=(124, 820, 900), coins=1950)
        bot.on_unknown(bot.grab(), "unknown")
        self.assertEqual(dev.taps, [(350, 820)])
        self.assertTrue(bot.expect_new)
        fresh = {"tubes": [T(236, 332, []), T(99, 538, ["?", "blue", "red"]), T(167, 538, ["red", "blue"]),
                           T(236, 538, []), T(304, 538, ["green", "red", "blue"]), T(372, 538, ["blue", "red", "yellow", "green"])]}
        self.assertTrue(driver.compatible(lv.last_state, fresh, lv.extra_tubes))
        sv.now.update(kind="level", state=fresh, level=99, badge="superhard", give_up=None, play_on=None)
        self.feed(bot, n=6, until=lambda: bot.lv is not lv)
        log = self.log()
        self.assertIsNot(bot.lv, lv, log)
        self.assertEqual((bot.lv.n, bot.lv.play_ons, bot.lv.extra_tubes, bot.levels_done), (99, 0, 0, 0), log)
        self.assertNotIn("فوز", log)
        self.assertIsNone(bot.restart_n)
        sv.now.update(kind="unknown", give_up=(350, 820), play_on=(124, 820, 900), coins=1950, state=None)
        bot.on_unknown(bot.grab(), "unknown")
        self.assertEqual(dev.taps[-1], (124, 820))

    def test_lives_wait_on_unknown_home_screen(self):
        """الواجهة بزرّ «Super Hard» الأحمر تُقرأ «unknown» أثناء انتظار الأرواح: لا «Home» ولا موضع «Level N» ولا رجوع حتى
        الموعد (كان مسار شريط التبويبات يفتح نافذة More Lives كل 23 ثانية)، ثم «Home» مرتين وموضع «Level N» مرة."""
        bot, sv, dev = self.make(TabScriptVision)
        regen = self.clock.time() + 14 * 60
        bot.lives_until = regen
        sv.now.update(kind="unknown", tabbar=0.68)
        times, started, before = [], [], []

        def tap(X, Y):
            TapDevice.tap(dev, X, Y)
            times.append(self.clock.time())
            if near(dev.taps[-1], (236, 786), 8) and not started:
                started.append(self.clock.time())
                before.extend([list(dev.taps), list(dev.keys)])
                sv.now.update(kind="level", tabbar=0.0)      # بدأت المرحلة (بلا لوحة مقروءة في هذا الاختبار)
        dev.tap = tap
        for _ in range(40):
            bot.run(max_iters=10)
            if started:
                break
        self.assertTrue(started, self.log()[-1500:])
        self.assertEqual([t for t in times if t < regen], [], dev.taps)
        self.assertLess(started[0] - regen, 90)
        taps, keys = before
        self.assertEqual(sum(1 for p in taps if near(p, (236, 955), 8)), 2, taps)
        self.assertEqual(len(taps), 3, taps)
        self.assertEqual(keys, [])
        self.assertIn("انتظار الأرواح (شاشة مجهولة)", self.log())

    def test_escalation_never_taps_paid_button(self):
        """«Continue?» لا تُغلق بـ X (الشاشة نفسها تتكرّر): التصعيد يضغط الرجوع ولا يلمس الوسط (236,620) داخل «Play On 900»؛
        ونقرة الوسط بالزمن في شاشة مجهولة مثلها."""
        paid = [{"box": (97, 561, 375, 646), "paid": True}]
        inside = lambda taps: [p for p in taps if 97 <= p[0] <= 375 and 561 <= p[1] <= 646]   # noqa: E731
        bot, sv, dev = self.make(TabScriptVision)
        sv.now.update(kind="close", close=(428, 215), greens=paid)
        for _ in range(4):
            bot.run(max_iters=10)
        self.assertGreaterEqual(bot.repeat_escalations, 2, self.log())
        self.assertEqual(inside(dev.taps), [])
        self.assertGreaterEqual(dev.keys.count(4), 2)
        bot2, sv2, dev2 = self.make(TabScriptVision)
        self.clock.sleep(9 * 60)                              # بعد 8 دقائق: نقرة الوسط لا زرّ الشروط
        sv2.now.update(kind="unknown", greens=paid)
        for _ in range(4):
            bot2.run(max_iters=10)
        self.assertGreaterEqual(bot2.unknown_acts, 2, self.log())
        self.assertEqual(inside(dev2.taps), [])
        self.assertIn("نقرة التصعيد فوق زرّ يصرف العملات", self.log())

    def test_counters_survive_update(self):
        """أمر «update» (os.execv) كان يصفّر «Give Up» لكل مرحلة وموعد الروح القادمة وحارس «Refill»: تُحفظ قبل التحديث
        وتُقرأ بعده مرة واحدة، والملف القديم (أكثر من 10 دقائق) أو التالف يُهمل."""
        from unittest import mock
        old_sf = driver.STATE_FILE
        driver.STATE_FILE = Path(self.tmp.name) / "bot_state.json"
        try:
            bot, sv, dev = self.make()
            bot.level_fails.update({95: 2, 99: 5})
            bot.lives_until = self.clock.time() + 500
            bot.last_refill_tap = self.clock.time() - 30
            bot.coins = 150
            bot.git = lambda *a, **k: (0, "")
            bot.publish = lambda msg: True
            argvs = []

            def fake_execv(exe, argv):
                argvs.append(argv)
                raise SystemExit(0)
            with mock.patch.object(driver.os, "execv", fake_execv):
                with self.assertRaises(SystemExit):
                    bot.self_update()
            self.assertIn("--no-setup", argvs[0])
            self.clock.sleep(3)
            bot2, _, _ = self.make()
            self.assertTrue(bot2.load_counters())
            self.assertEqual(dict(bot2.level_fails), {95: 2, 99: 5})
            self.assertAlmostEqual(bot2.lives_until, bot.lives_until)
            self.assertAlmostEqual(bot2.last_refill_tap, bot.last_refill_tap)
            self.assertEqual(bot2.coins, 150)
            self.assertTrue(bot2.lives_waiting())
            self.assertFalse(driver.STATE_FILE.exists())          # يُقرأ مرة واحدة
            self.assertFalse(bot2.load_counters())
            bot.save_counters()
            self.clock.sleep(700)
            bot3, _, _ = self.make()
            self.assertFalse(bot3.load_counters())
            self.assertEqual(dict(bot3.level_fails), {})
            driver.STATE_FILE.write_text("{bad json", encoding="utf-8")
            self.assertFalse(bot3.load_counters())
            self.assertIn("عدّادات ما قبل التحديث", self.log())
        finally:
            driver.STATE_FILE = old_sf


FAKE_ADB = r"""#!/usr/bin/env python3
import io, os, struct, sys
args = sys.argv[1:]
with open(os.environ["FAKE_ADB_LOG"], "a") as f:
    f.write(" ".join(args) + "\n")
if args[:2] == ["exec-out", "screencap"]:
    w, h = 108, 228
    if len(args) == 2:
        sys.stderr.write("warning: noise on stderr\n")
        sys.stdout.buffer.write(struct.pack("<IIII", w, h, 1, 0) + bytes([200, 100, 50, 255]) * (w * h))
    else:
        from PIL import Image
        b = io.BytesIO()
        Image.new("RGB", (w, h), (1, 2, 3)).save(b, "PNG")
        sys.stdout.buffer.write(b.getvalue())
elif args and args[0] == "shell":
    cmd = " ".join(args[1:])
    if "dumpsys window" in cmd:
        print("  mCurrentFocus=Window{abc u0 com.grandgames.magicsort/com.unity3d.player.UnityPlayerActivity}")
    elif "pm list packages" in cmd:
        print("package:com.grandgames.magicsort")
"""


class TestDeviceWithFakeAdb(unittest.TestCase):
    """صنف Device الحقيقي مع adb مزيّف: اللقطة الخام (ترويسة 16 بايت) وصيغة النقرات."""

    def test_device(self):
        with tempfile.TemporaryDirectory() as d:
            adb = Path(d) / "adb"
            adb.write_text(FAKE_ADB)
            adb.chmod(0o755)
            log = Path(d) / "log.txt"
            os.environ["FAKE_ADB_LOG"] = str(log)
            dev = driver.Device()
            dev.adb = str(adb)
            im = dev.screencap()
            self.assertEqual(im.size, (108, 228))
            self.assertEqual(im.getpixel((5, 5)), (200, 100, 50))
            self.assertTrue(dev.raw_ok)
            fr = driver.Frame(im)
            self.assertEqual(fr.arr.shape[0], 1000)
            dev.tap2_std((100, 500), (300, 600), 0.3)
            last = log.read_text().strip().splitlines()[-1]
            self.assertEqual(last, "shell input tap 23 114; sleep 0.30; input tap 68 137")
            self.assertTrue(dev.installed())
            self.assertIn(driver.PKG, dev.focus())


class TestGitPublish(unittest.TestCase):
    """النشر من شجرة منفصلة وقراءة cmd.txt مقابل مستودع origin محلي مؤقت."""

    def sh(self, *a, cwd=None):
        import subprocess
        p = subprocess.run(list(a), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(p.returncode, 0, p.stdout.decode())
        return p.stdout.decode()

    def test_publish_and_remote(self):
        br = "claude/test-bot"
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            origin, main, lead = d / "origin.git", d / "main", d / "lead"
            self.sh("git", "init", "-q", "--bare", str(origin))
            self.sh("git", "clone", "-q", str(origin), str(main))
            for repo in (main,):
                self.sh("git", "config", "user.email", "t@example.com", cwd=repo)
                self.sh("git", "config", "user.name", "t", cwd=repo)
            self.sh("git", "checkout", "-q", "-b", br, cwd=main)
            (main / "research" / "emu").mkdir(parents=True)
            (main / "research" / "emu" / "cmd.txt").write_text("seq 0\n")
            self.sh("git", "add", "-A", cwd=main)
            self.sh("git", "commit", "-q", "-m", "init", cwd=main)
            self.sh("git", "push", "-q", "origin", br, cwd=main)

            saved = (driver.ROOT, driver.PUB_DIR, dict(driver.CFG))
            driver.ROOT, driver.PUB_DIR = main, d / "pub"
            driver.CFG["branch"] = br
            try:
                game = FakeGame([make_level(random.Random(1), 3, 1)], random.Random(1))
                out = driver.Out(main / driver.OUT_REL, 50, quiet=True)
                bot = driver.Bot(FakeDevice(game), driver.Vision(FakeVisionModule(game), out), out, 10)
                bot.setup_publisher()
                self.assertTrue(bot.pub_ok)
                bot.poll_remote()
                self.assertEqual(bot.last_seq, 0)
                out.log("سطر أول")
                self.assertTrue(bot.publish("نشر 1"))
                files = self.sh("git", "--git-dir", str(origin), "ls-tree", "-r", "--name-only", br)
                self.assertIn("research/emu/out/log.txt", files)

                # صاحب المشروع يرسل أوامر ويحذف السجل من الفرع (تعارض مع النشر التالي)
                self.sh("git", "clone", "-q", "-b", br, str(origin), str(lead))
                self.sh("git", "config", "user.email", "l@example.com", cwd=lead)
                self.sh("git", "config", "user.name", "l", cwd=lead)
                (lead / "research" / "emu" / "cmd.txt").write_text("seq 1\npause\n")
                self.sh("git", "rm", "-q", "research/emu/out/log.txt", cwd=lead)
                self.sh("git", "commit", "-q", "-am", "cmd", cwd=lead)
                self.sh("git", "push", "-q", "origin", br, cwd=lead)
                bot.poll_remote()
                self.assertEqual(bot.cmdq.get_nowait(), (1, ["pause"]))
                out.log("بعد الحذف")                  # تعديل محلي على ملف حذفه الفرع: تعارض

                out.save_jpg("keep_me.jpg", Image.new("RGB", (10, 20)))
                self.assertTrue(bot.publish("نشر 1ب"))
                self.sh("git", "pull", "-q", cwd=lead)
                self.sh("git", "rm", "-q", "research/emu/out/keep_me.jpg", cwd=lead)
                self.sh("git", "commit", "-q", "-m", "تنظيف", cwd=lead)
                self.sh("git", "push", "-q", "origin", br, cwd=lead)
                out.log("سطر ثان")
                self.assertTrue(bot.publish("نشر 2"))
                files = self.sh("git", "--git-dir", str(origin), "ls-tree", "-r", "--name-only", br)
                self.assertNotIn("keep_me.jpg", files)   # ما حذفه صاحب المشروع لا يعود
                log = self.sh("git", "--git-dir", str(origin), "show", "%s:research/emu/out/log.txt" % br)
                self.assertIn("سطر ثان", log)
                cmd = self.sh("git", "--git-dir", str(origin), "show", "%s:research/emu/cmd.txt" % br)
                self.assertIn("pause", cmd)          # لم يُمحَ أمر صاحب المشروع
                # الشجرة الأصلية لم تُلمس (لا تعديلات على الملفات المتتبَّعة)
                st = self.sh("git", "status", "--porcelain", "--untracked-files=no", cwd=main)
                self.assertEqual(st.strip(), "")
            finally:
                driver.ROOT, driver.PUB_DIR = saved[0], saved[1]
                driver.CFG.clear()
                driver.CFG.update(saved[2])


class TestInstallAbi(unittest.TestCase):
    """التثبيت يختار ملف المعمارية بحسب abilist الجهاز (الحزمة الحديثة فيها arm64_v8a وحده)."""

    class Dev:
        def __init__(self, abilist):
            self.abilist = abilist
            self.calls = []

        def sh(self, cmd, timeout=30):
            return self.abilist if "abilist" in cmd else ""

        def run(self, args, timeout=30, binary=False):
            self.calls.append([Path(a).name for a in args[3:]])
            return 0, "Success"

    def _install(self, names, abilist):
        with tempfile.TemporaryDirectory() as d:
            for n in names:
                Path(d, n).write_bytes(b"x")
            dev = self.Dev(abilist)
            bot = driver.Bot.__new__(driver.Bot)
            bot.dev = dev
            bot.log = lambda m: None
            old = driver.CFG["game_dir"]
            driver.CFG["game_dir"] = d
            try:
                self.assertTrue(bot.install_game())
            finally:
                driver.CFG["game_dir"] = old
            return dev.calls[0]

    def test_arm64_only_on_x86_64(self):
        files = self._install(["com.grandgames.magicsort.apk", "config.arm64_v8a.apk", "config.xxhdpi.apk"],
                              "x86_64,x86,arm64-v8a,armeabi-v7a,armeabi")
        self.assertEqual(files, ["com.grandgames.magicsort.apk", "config.arm64_v8a.apk", "config.xxhdpi.apk"])

    def test_prefers_first_supported_abi(self):
        files = self._install(["com.grandgames.magicsort.apk", "config.arm64_v8a.apk", "config.armeabi_v7a.apk"],
                              "x86,armeabi-v7a,armeabi")
        self.assertEqual(files, ["com.grandgames.magicsort.apk", "config.armeabi_v7a.apk"])



class TestLoadingScreen(unittest.TestCase):
    """شاشة التحميل تُعرف ببصمتها فتُنتظر بلا نقر؛ وشاشات اللعب والواجهة ونافذة الشروط ليست تحميلاً."""

    def test_is_loading(self):
        bot = driver.Bot.__new__(driver.Bot)
        td = Path(driver.HERE) / "testdata"
        bot.loading_hashes = [driver.dhash(driver.Frame(Image.open(p))) for p in sorted(td.glob("loading_*.jpg"))]
        self.assertTrue(bot.loading_hashes)
        self.assertTrue(bot.is_loading(driver.Frame(Image.open(td / "loading_splash.jpg"))))
        self.assertTrue(bot.is_loading(driver.Frame(Image.open(td / "014_a_relaunch_25s.jpg"))))
        for name in ("010_a_level5.jpg", "056_b_home.jpg", "030_a_win.jpg", "000_launch_120s.jpg", "007_a_shop.jpg"):
            self.assertFalse(bot.is_loading(driver.Frame(Image.open(td / name))), name)

    def test_is_daily_popup(self):
        bot = driver.Bot.__new__(driver.Bot)
        td = Path(driver.HERE) / "testdata"
        bot.daily_hashes = [driver.center_hash(driver.Frame(Image.open(p))) for p in sorted(td.glob("daily_popup*.jpg"))]
        self.assertTrue(bot.is_daily_popup(driver.Frame(Image.open(td / "daily_popup.jpg"))))
        for p in sorted(td.glob("*.jpg")):
            if not p.name.startswith("daily_popup"):
                self.assertFalse(bot.is_daily_popup(driver.Frame(Image.open(p))), p.name)

    def test_is_nonet(self):
        bot = driver.Bot.__new__(driver.Bot)
        td = Path(driver.HERE) / "testdata"
        bot.nonet_hashes = [driver.center_hash(driver.Frame(Image.open(p))) for p in sorted(td.glob("nonet_*.jpg"))]
        self.assertTrue(bot.nonet_hashes)
        self.assertTrue(bot.is_nonet(driver.Frame(Image.open(td / "nonet_popup.jpg"))))
        for p in sorted(td.glob("*.jpg")):
            if not p.name.startswith("nonet_"):
                self.assertFalse(bot.is_nonet(driver.Frame(Image.open(p))), p.name)


class TestClayPassThrough(unittest.TestCase):
    """علامة «الطين» من الرؤية تصل إلى الحلّال (كان Vision.parse يحذفها فيصبّ البوت منها)."""

    def test_clay_flag_reaches_plan(self):
        import vision as real_vision
        td = Path(driver.HERE) / "testdata"
        out = driver.Out(Path(tempfile.mkdtemp()), 10, quiet=True)
        vis = driver.Vision(real_vision, out)
        st = vis.parse(driver.Frame(Image.open(td / "L041_clay_full.jpg")))
        self.assertIsNotNone(st)
        clay = [k for k, t in enumerate(st["tubes"]) if t.get("clay")]
        self.assertEqual(clay, [0, 1, 4, 5])
        mv = solver.plan(st)
        self.assertTrue(mv)
        self.assertNotIn(mv[0][0], clay)

    def test_keys_reach_plan(self):
        """طبقة المفتاح من الرؤية الحقيقية تصل إلى الحلّال (Vision.parse لا يحذفها) فتبدأ الخطة بالحفر نحوه."""
        import vision as real_vision
        td = Path(driver.HERE) / "testdata"
        out = driver.Out(Path(tempfile.mkdtemp()), 10, quiet=True)
        vis = driver.Vision(real_vision, out)
        st = vis.parse(driver.Frame(Image.open(td / "L074_keys.jpg")))
        self.assertEqual([(k, t["keys"]) for k, t in enumerate(st["tubes"]) if t.get("keys")], [(3, [1])])
        self.assertEqual(len(st["doors"]), 2)
        info = {}
        mv = solver.plan(st, info=info)
        self.assertEqual(info["mode"], "key")
        self.assertEqual(mv[0][0], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
