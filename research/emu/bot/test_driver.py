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
import shutil
import subprocess
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
        rec = bot.sig_rec(bot.lv.sig_id, 7)
        self.assertEqual((rec["fails"], bot.level_fails.get(7, 0)), (0, 0))
        bot.restart_level()
        self.assertEqual((len(stops), bot.dev.launched, bot.lv.dead_restarts), (1, 1, 0))
        log = (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")
        self.assertIn("الرجوع لم يُعِد المرحلة 7", log)
        # التشغيل 18: إعادة التشغيل محاولة فاشلة للبداية (تُحسب ويُحفظ طريقها) والمرحلة نفسها تُفتح من جديد كمحاولة جديدة
        self.assertEqual((rec["fails"], bot.level_fails[7], bot.restart_n, bot.expect_new), (1, 1, 7, True))
        self.assertIn("طريق مسدود محفوظ لهذه البداية", log)
        # لوحة بدت محلولة ثم أُعيدت اللعبة: أول شاشة غير اللوحة بعد الإطلاق لا تجعل المحاولة الفاشلة «فوزاً» (مراجعة 77e457e)
        bot.lv = driver.LevelCtx(8, {"tubes": []}, 0.0)
        bot.lv.maybe_won = True
        for _ in range(4):
            bot.restart_level()
        bot.leave_level("unknown")
        self.assertEqual((bot.levels_done, bot.lv.result, bot.level_fails[8], bot.restart_n), (0, None, 1, 8))
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


class PlasterGame(FakeGame):
    """قوالب جبس (من المرحلة 100): قارورة محجوبة ("cover": "plaster") ينكسر جبسها حين تكتمل (تمتلئ بلون واحد) قارورة ظاهرة في
    الخانة المجاورة لها في صفّها، فتظهر بطبقاتها (ومنها المخفي) في خانتها. لمسها وهي جبس لا يفعل شيئاً (ويُعدّ خطأً).
    levels[k][3] = فهارس القوالب. show_casts=False: الرؤية لا ترى القوالب أصلاً (كما قبل هذا الإصلاح)، فتظهر قارورتها جديدة
    بين القديمة حين تنكسر (المواضع نفسها لا تتغيّر)."""

    def __init__(self, levels, rng, show_casts=True, **kw):
        self.show_casts = show_casts
        super().__init__(levels, rng, **kw)

    def load(self, k):
        super().load(k)
        lvl = self.levels[k]
        self.plaster = set(lvl[3]) if len(lvl) > 3 else set()
        self.broken = []
        self.plaster_taps = getattr(self, "plaster_taps", 0)

    def neighbours(self, k):
        n = len(self.truth)
        per = n if n <= 5 else (n + 1) // 2
        r, c = divmod(k, per)
        m = per if r == 0 else n - per
        return [r * per + c + d for d in (-1, 1) if 0 <= c + d < m]

    def visible(self):
        st = super().visible()
        tubes = []
        for k, t in enumerate(st["tubes"]):
            if k in self.plaster:
                if not self.show_casts:
                    continue
                t.update(layers=[], blocked=True, cover="plaster")
            tubes.append(t)
        return {"tubes": tubes, "warnings": []}

    def tap(self, x, y):
        if self.screen == "level" and abs(y - 854) >= 35 and self.tube_at(x, y) in self.plaster:
            self.plaster_taps += 1
            return
        super().tap(x, y)

    def pour(self, i, j):
        ok = super().pour(i, j)
        for p in sorted(self.plaster):
            if any(k not in self.plaster and len(self.truth[k]) == self.caps[k] and len(set(self.truth[k])) == 1
                   for k in self.neighbours(p)):
                self.plaster.discard(p)
                self.broken.append(p)
        return ok


def plaster_level():
    """ثماني قوارير في صفّين (أربع في كل صف): القالب 0 جاره الأحمر 1 (ينقصه أحمر في قمة 2)، وفيه أخضر وأصفر بثلاث طبقات
    مخفية؛ ولا يكتمل الأخضر ولا الأصفر بلا ما في الجبس."""
    truth = [["green", "yellow", "green", "yellow"], ["red", "red", "red"], ["blue", "blue", "blue", "red"], [],
             ["yellow", "green", "blue"], ["green", "yellow"], [], []]
    hidden = [[True, True, True, False], [False] * 3, [False] * 4, [], [False] * 3, [False] * 2, [], []]
    return [4] * 8, truth, hidden, {0}


class DelayedPlasterGame(PlasterGame):
    """جبس ينكسر بعد `delay` ثانية من اكتمال جارته بساعة المحرّك الافتراضية (التشغيل التاسع: يظهر مكسوراً بعد 6..7 ث من النقر،
    وقائماً بعد 4 ث)، لا لحظة الصبّ."""

    def __init__(self, levels, rng, clock, delay, **kw):
        self.clock, self.delay = clock, delay
        super().__init__(levels, rng, **kw)

    def load(self, k):
        super().load(k)
        self.due = {}                       # قالب -> وقت انكساره

    def tick(self):
        for p, at in sorted(self.due.items()):
            if self.clock.time() >= at:
                del self.due[p]
                self.plaster.discard(p)
                self.broken.append(p)

    def visible(self):
        self.tick()
        return super().visible()

    def tap(self, x, y):
        self.tick()
        super().tap(x, y)

    def pour(self, i, j):
        ok = FakeGame.pour(self, i, j)
        for p in sorted(self.plaster):
            if p not in self.due and any(k not in self.plaster and len(self.truth[k]) == self.caps[k]
                                         and len(set(self.truth[k])) == 1 for k in self.neighbours(p)):
                self.due[p] = self.clock.time() + self.delay
        return ok


def delayed_plaster_level():
    """ست قوارير في صفّين بلا فارغة: القالب 0 جاره الأحمر 1 (ينقصه أحمر في قمة 2)؛ بعد إكماله لا حركة قانونية حتى ينكسر الجبس."""
    truth = [["orange", "green", "purple", "orange"], ["red", "red", "red"], ["green", "blue", "red"],
             ["blue", "green", "orange"], ["purple", "orange", "green"], ["blue", "purple", "blue", "purple"]]
    return [4] * 6, truth, [[False] * len(t) for t in truth], {0}


class PricedVision(FakeVisionModule):
    """والأدوات نفدت: لا شارة عدد حمراء على أيّ منها (ثمنها بالعملات، كما في كل لقطات المراحل 100..110)."""

    def booster_free(self, arr):
        return [False, False, False]


class TestPlasterSim(unittest.TestCase):
    """البوت كاملاً على مراحل جبس مزيّفة: يكمل الجارة فينكسر الجبس، ويكمل المحاولة نفسها بلا «إعادة» ولا «فوز» كاذب."""

    def setUp(self):
        self.clock = FakeClock()
        self._time = driver.time
        driver.time = self.clock
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = dict(driver.CFG)
        driver.CFG.update(plaster_wait=4.0, plaster_grace=10.0)   # القيم الافتراضية مهما كانت متغيّرات البيئة

    def tearDown(self):
        driver.time = self._time
        driver.CFG.clear()
        driver.CFG.update(self.cfg)
        self.tmp.cleanup()

    def play(self, show_casts, n=None):
        import test_solver as TS
        caps, truth, hidden, _p = plaster_level()
        self.assertTrue(TS.reference_solvable({"tubes": [{"cap": c, "layers": list(t)} for c, t in zip(caps, truth)]}))
        game = PlasterGame([plaster_level()], random.Random(6), show_casts=show_casts)
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        bot = driver.Bot(FakeDevice(game), driver.Vision(FakeVisionModule(game), out), out, 600, git=False)
        bot.level_hint = n                      # رقم المرحلة (الرؤية المزيّفة لا تقرأ العنوان)
        for _ in range(30):
            bot.run(max_iters=100)
            if game.wins:
                break
        return game, bot, (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")

    def test_plaster_breaks_in_place(self):
        game, bot, log = self.play(True)
        self.assertEqual((game.wins, bot.levels_done), (1, 1), log[-3000:])
        self.assertEqual(game.broken, [0], log[-3000:])
        self.assertEqual(game.plaster_taps, 0, log[-3000:])
        self.assertIn("مغطّاة 1 (جبس 1)", log)
        self.assertIn("القالب 0 ينكسر بامتلاء القارورة 1", log)
        self.assertIn("تكمل جارة الجبس؛ انتظار انكساره", log)
        self.assertIn("الجبس انكسر في المرحلة 1: القارورة 0", log)
        self.assertNotIn("أُعيدت من البداية", log)
        self.assertNotIn("تختلف عن المتوقَّع", log)          # الحركة التي كسرت الجبس نجحت كما توقّع النموذج
        self.assertEqual(log.count("فوز بالمرحلة"), 1)
        rows = [json.loads(ln) for ln in (Path(self.tmp.name) / "levels.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows[0]["start"][0]["blocked"], "plaster")

    def test_missed_cast_appears_as_new_tube(self):
        """قالب لم تقرأه الرؤية (في مرحلة جبس: من المرحلة 100): حين ينكسر تظهر قارورة جديدة قبل القديمة (الفهارس تنزاح)؛ استمرار
        بلا إعادة، والسجل يقول جبس."""
        game, bot, log = self.play(False, n=100)
        self.assertEqual((game.wins, bot.levels_done), (1, 1), log[-3000:])
        self.assertEqual(game.broken, [0])
        self.assertIn("الجبس انكسر في المرحلة 100 (القارورة 0 جديدة (قالب لم يُقرأ؟))", log)
        self.assertNotIn("أُعيدت من البداية", log)
        self.assertEqual(log.count("فوز بالمرحلة"), 1)

    def play_delayed(self, delay, priced, until):
        game = DelayedPlasterGame([delayed_plaster_level()], random.Random(3), self.clock, delay)
        d = Path(self.tmp.name) / ("d%g_%s" % (delay, "priced" if priced else "owned"))
        out = driver.Out(d, 600, quiet=True)
        dev = FakeDevice(game)
        keys = []                              # مفاتيح قبل الفوز (بعده تضغط الحلقة الرجوع في الواجهة المتكرّرة)
        dev.key = lambda code: keys.append(code) if not game.wins else None
        vis = (PricedVision if priced else FakeVisionModule)(game)
        bot = driver.Bot(dev, driver.Vision(vis, out), out, 600, git=False)
        bot.level_hint = 100
        log = ""
        for _ in range(40):
            bot.run(max_iters=20)
            log = (d / "log.txt").read_text(encoding="utf-8")
            if until(game, log):
                break
        return game, bot, log, keys

    def test_delayed_break_waits_without_boosters(self):
        """الجبس ينكسر بعد 7 أو 9 ث من اكتمال جارته واللوح بلا حركة قانونية حتى ينكسر: انتظار وإعادة تصوير، لا «قارورة إضافية»
        ولا حركة عشوائية ولا رجوع («إعادة المرحلة»)، ثم الفوز. (كانت الأداة تضيع، أو يُضغط الرجوع حين نفدت الأدوات.)"""
        for delay, priced in ((7.0, False), (9.0, True)):
            game, bot, log, keys = self.play_delayed(delay, priced, lambda g, _l: g.wins)
            self.assertEqual((game.wins, game.broken), (1, [0]), log[-3000:])
            self.assertEqual((game.boosters_used, keys), ([], []), log[-3000:])
            self.assertIn("تكمل جارة الجبس؛ انتظار انكساره", log)
            self.assertIn("وجارة الجبس مكتملة ولم ينكسر بعد: انتظار وإعادة التصوير بلا أدوات (1)", log)
            self.assertIn("الجبس انكسر في المرحلة 100: القارورة 0", log)
            for bad in ("عالقة", "أداة:", "حركة عشوائية", "لا حركة قانونية", "أُعيدت من البداية"):
                self.assertNotIn(bad, log)

    def test_wait_is_bounded_when_cast_never_breaks(self):
        """قالب لا ينكسر (نموذج الجيران خطأ): ست إعادات تصوير فقط ثم مسار «عالقة» المعتاد، فلا انتظار بلا نهاية."""
        game, bot, log, keys = self.play_delayed(1e9, False, lambda g, _l: g.boosters_used)
        self.assertEqual(game.boosters_used[:1], ["add"], log[-3000:])
        self.assertEqual(log.count("انتظار وإعادة التصوير بلا أدوات"), 6, log[-3000:])
        self.assertIn("عالقة (لا خطة)", log)


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
        """الصعبة والرصيد 1050 (يكفي «Play On» وحده): «Give Up» ليبقى ثمن «Refill» (كان يصرف 1950 ← 1050 ← 150 فلا
        يُملأ أبداً)؛ والاحتياطي 0 يعيد «Play On» أولاً. وفي الصعبة جداً «Play On» بلا احتياطي (المرحلة 99 في التشغيل الثامن)."""
        bot, sv, dev = self.make()
        self.nomoves(bot, sv, "hard", 1050)
        self.assertEqual(dev.taps, [(350, 820)])
        self.assertIn("الرصيد 1050 لا يُبقي بعد ثمنه 900 احتياطي ملء الأرواح 900", self.log())
        bot3, sv3, dev3 = self.make()
        self.nomoves(bot3, sv3, "superhard", 1050)
        self.assertEqual(dev3.taps, [(124, 820)])
        driver.CFG["play_on_reserve"] = 0
        bot2, sv2, dev2 = self.make()
        self.nomoves(bot2, sv2, "hard", 1050)
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


class StallVision(TabScriptVision):
    """ومعها الإعلانان (الأسود والأبيض التجريبي) وزرّ إغلاقه وشعار «MAGIC SORT» وسهم التعليم كما يكتبها الاختبار."""

    def is_ad(self, arr):
        return bool(self.now.get("black_ad"))

    def is_white_ad(self, arr):
        return bool(self.now.get("white_ad"))

    def is_dark_ad(self, arr):
        return bool(self.now.get("pangle_ad"))

    def find_ad_close(self, arr):
        return self.now.get("ad_close")

    def is_logo_overlay(self, arr):
        return bool(self.now.get("logo"))

    def find_tutorial_arrow(self, arr):
        return self.now.get("arrow")


class DriverCase(unittest.TestCase):
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

    def make(self, vision_cls=StallVision):
        sv = vision_cls()
        dev = TapDevice()
        dev.stops = []
        dev.force_stop = lambda: dev.stops.append(self.clock.time())
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        bot = driver.Bot(dev, driver.Vision(sv, out), out, 600, git=False)
        bot.loading_hashes, bot.daily_hashes, bot.nonet_hashes = [], [], []
        return bot, sv, dev

    def log(self):
        p = Path(self.tmp.name) / "log.txt"
        return p.read_text(encoding="utf-8") if p.exists() else ""


class TestPlasterDriver(DriverCase):
    """انكسار الجبس في on_level مباشرة: القالب يصير قارورة ظاهرة في خانته (العدد نفسه)، والذاكرة بفهارسها."""

    @staticmethod
    def board():
        return {"tubes": [T(100, 336, [], blocked=True, cover="plaster"), T(168, 330, ["red", "red", "red"], clay=True),
                          T(236, 336, [], blocked=True, cover="plaster"), T(304, 330, ["?", "blue", "red"]),
                          T(133, 537, ["?", "blue"]), T(201, 537, [])]}

    def start(self, bot, st, n=108):
        lv = driver.LevelCtx(n, st, self.clock.time())
        lv.badge = "normal"
        bot.lv = lv
        bot.expect_new = False
        return lv

    def test_break_in_place_keeps_attempt_and_memory(self):
        bot, sv, dev = self.make()
        st = self.board()
        lv = self.start(bot, st)
        lv.memory = {(3, 0): "green", (4, 0): "purple"}
        lv.moves = 5
        stp = driver.with_memory(st, lv.memory)
        self.assertTrue(solver.breaker_completed(stp, 3, 1))
        sv.now.update(kind="level", state=st, level=108)
        bot.do_move(stp, 3, 1)                       # الأحمر يكمل الكاسرة؛ ينتظر السائق انكسار الجبس
        self.assertIn("تكمل جارة الجبس", self.log())
        after = {"tubes": [T(100, 336, ["?", "?", "yellow", "yellow"]), T(168, 330, ["red"] * 4),
                           T(236, 336, ["pink", "?", "cyan"]), T(304, 330, ["?", "blue"]), T(133, 537, ["?", "blue"]),
                           T(201, 537, [])]}
        sv.now.update(state=after)
        bot.on_level(bot.grab())
        log = self.log()
        self.assertIs(bot.lv, lv)
        self.assertEqual((lv.moves, lv.fails, lv.plasters_broken, bot.levels_done), (6, 0, 2, 0), log)
        self.assertIn("الجبس انكسر في المرحلة 108: القارورة 0 (100،336) ← [?,?,yellow,yellow]، القارورة 2", log)
        self.assertIn("باقٍ 0 قالب", log)
        self.assertNotIn("تختلف عن المتوقَّع", log)
        self.assertNotIn("أُعيدت من البداية", log)
        self.assertEqual(lv.memory, {(3, 0): "green", (4, 0): "purple"})   # الفهارس لم تتغيّر
        self.assertFalse(lv.maybe_won)

    def test_missed_cast_remaps_memory_by_position(self):
        """قالب لم تقرأه الرؤية (يسار الكاسرة) وآخر مقروء: اكتمال الأحمر يكسرهما معاً فتكبر اللوحة وتنزاح الفهارس؛ استمرار المحاولة
        نفسها والذاكرة تنتقل بالموضع (slot_map) إلى فهارسها الجديدة، بلا «إعادة» ولا «فوز»."""
        bot, sv, dev = self.make()
        old = {"tubes": [T(168, 330, ["red", "red", "red"], clay=True), T(236, 336, [], blocked=True, cover="plaster"),
                         T(304, 330, ["?", "blue", "red"]), T(133, 537, ["?", "blue"]), T(201, 537, [])]}
        lv = self.start(bot, old)
        lv.memory = {(2, 0): "green", (3, 0): "purple"}
        stp = driver.with_memory(old, lv.memory)
        sv.now.update(kind="level", state=old, level=108)
        bot.do_move(stp, 2, 0)
        new = {"tubes": [T(100, 336, ["?", "?", "yellow", "yellow"]), T(168, 330, ["red"] * 4),
                         T(236, 336, ["pink", "?", "cyan"]), T(304, 330, ["?", "blue"]), T(133, 537, ["?", "blue"]),
                         T(201, 537, [])]}
        sv.now.update(state=new)
        fr = bot.grab()
        for _ in range(4):
            fr = bot.on_level(fr) or bot.grab()
            if lv.plasters_broken:
                break
        log = self.log()
        self.assertIs(bot.lv, lv, log)
        self.assertEqual(lv.memory, {(3, 0): "green", (4, 0): "purple"}, log)
        self.assertIn("الجبس انكسر في المرحلة 108 (القارورة 2 في خانة قالب، القارورة 0 جديدة (قالب لم يُقرأ؟))", log)
        self.assertEqual((lv.moves, bot.levels_done, lv.plasters_broken), (1, 0, 2), log)
        self.assertNotIn("أُعيدت من البداية", log)
        self.assertNotIn("فوز", log)

    def test_sorted_board_with_sealed_tubes_waits(self):
        """الظاهر مرتّب (قوارير مكتملة) والجبس قائم وجاره كاسرة فارغة: المكتملة مسدودة بسدادة ذهبية فلا تُصبّ في الكاسرة (كانت
        خطة «plaster» تصبّها فترفضها اللعبة)؛ لا لمس ولا أداة، والبوت ينتظر (طريق مسدود: «No Available Moves» في اللعبة)."""
        bot, sv, dev = self.make()
        st = {"tubes": [T(100, 336, [], blocked=True, cover="plaster"), T(168, 330, [], clay=True), T(236, 330, ["blue"] * 4),
                        T(304, 330, ["red"] * 4)]}
        lv = self.start(bot, st)
        sv.now.update(kind="level", state=st, level=103)
        bot.on_level(bot.grab())
        log = self.log()
        self.assertIsNone(lv.pending, log)
        self.assertEqual(dev.taps, [], log)
        self.assertIsNotNone(lv.solved_since)
        self.assertFalse(lv.maybe_won)
        self.assertNotIn("تكمل جارة الجبس", log)

    def test_curtain_lifted_in_place_keeps_shared_memory(self):
        """ستارة انزاحت في خانتها (العدد نفسه): ذاكرة المحاولة تبقى قاموس memory_by_sig نفسه، فما ينكشف بعدها يبقى للمحاولة التالية
        بعد «Give Up» (كانت تُنسخ إلى قاموس منفصل فيضيع)."""
        bot, sv, dev = self.make()
        start = {"tubes": [T(100, 330, ["?", "blue"]), T(168, 330, ["blue", "blue"]),
                           T(236, 336, [], blocked=True, cover="curtain", cover_color="green"), T(304, 330, []),
                           T(100, 537, ["?", "red"]), T(168, 537, ["red", "red"])]}
        sv.now.update(kind="level", state=start, level=94)
        bot.new_level(bot.grab(), start)
        lv = bot.lv
        shared = bot.memory_by_sig[lv.start_sig]
        bot.do_move(start, 0, 1)                      # الأزرق إلى 1 يكشف أخضر في قاع 0
        s1 = {"tubes": [T(100, 330, ["green"]), T(168, 330, ["blue"] * 3), start["tubes"][2], T(304, 330, []),
                        T(100, 537, ["?", "red"]), T(168, 537, ["red", "red"])]}
        sv.now.update(state=s1)
        bot.on_level(bot.grab())
        self.assertEqual(shared, {(0, 0): "green"}, self.log())
        lv.pending = None
        s2 = dict(s1, tubes=s1["tubes"][:2] + [T(236, 330, ["green"] * 3)] + s1["tubes"][3:])   # الستارة انزاحت
        sv.now.update(state=s2)
        bot.on_level(bot.grab())
        self.assertIs(lv.memory, shared, self.log())
        lv.pending = None
        bot.do_move(s2, 4, 5)                         # الأحمر إلى 5 يكشف أصفر في قاع 4
        s3 = dict(s2, tubes=s2["tubes"][:4] + [T(100, 537, ["yellow"]), T(168, 537, ["red"] * 3)])
        sv.now.update(state=s3)
        bot.on_level(bot.grab())
        self.assertIs(lv.memory, shared, self.log())
        self.assertEqual(shared, {(0, 0): "green", (4, 0): "yellow"}, self.log())

    def test_extra_empty_tube_is_not_a_cover(self):
        """قارورة فارغة جديدة (أداة «قارورة إضافية» أو «Play On») في مسار الأبواب: سطر «قوارير جديدة» كما كان، لا «قارورة مغطّاة
        عادت إلى القراءة» بملخّص فارغ."""
        bot, sv, dev = self.make()
        old = {"tubes": [T(100, 375, ["red", "blue"]), T(200, 375, ["blue", "red"]), T(300, 375, [])]}
        new = {"tubes": [T(90, 375, ["red", "blue"]), T(180, 375, ["blue", "red"]), T(270, 375, []), T(360, 375, [])]}
        lv = self.start(bot, old, n=42)
        lv.extra_tubes = 1
        bot.door_opened(new, *bot.door_ref(new))
        self.assertIn("المرحلة 42: قوارير جديدة (باب انفتح؟ 3 → 4 قارورة", self.log())
        self.assertNotIn("قارورة مغطّاة عادت", self.log())

    def test_plaster_tag_only_for_casts(self):
        """«الجبس انكسر» لقالب لم يُقرأ في مرحلة جبس فقط: لا لقارورة فاتت قراءتها ثم عادت بجوار مكتملة في المرحلة 40، ولا لباب
        مفتاح انفتح في مرحلة فيها قالب قائم."""
        bot, sv, dev = self.make()
        old = {"tubes": [T(100, 375, ["red"] * 4), T(300, 375, ["green", "blue"]), T(400, 375, [])]}
        new = {"tubes": [T(100, 375, ["red"] * 4), T(200, 375, ["blue", "green"]), T(300, 375, ["green", "blue"]),
                         T(400, 375, [])]}
        self.start(bot, old, n=40)
        bot.door_opened(new, *bot.door_ref(new))
        self.assertIn("المرحلة 40: قوارير جديدة (باب انفتح؟", self.log())
        self.start(bot, old, n=108)
        bot.door_opened(new, *bot.door_ref(new))
        self.assertIn("الجبس انكسر في المرحلة 108 (القارورة 1 جديدة (قالب لم يُقرأ؟))", self.log())
        keyed = {"tubes": [T(100, 336, [], blocked=True, cover="plaster"), T(168, 330, ["red", "red"], clay=True),
                           T(236, 330, ["blue", "yellow", "yellow"], keys=[0]), T(304, 330, [])]}
        opened = {"tubes": keyed["tubes"] + [T(372, 330, ["pink", "pink"])]}
        self.start(bot, keyed, n=112)
        bot.door_opened(opened, *bot.door_ref(opened))
        log = self.log()
        self.assertIn("المرحلة 112: قوارير جديدة (باب انفتح؟ 4 → 5 قارورة", log)
        self.assertNotIn("الجبس انكسر في المرحلة 40", log)
        self.assertNotIn("الجبس انكسر في المرحلة 112", log)

    def test_cast_flicker_is_not_a_break(self):
        """قالب فاتته الرؤية في لقطة ثم عاد: لا «الجبس انكسر» ولا «إعادة»، والمحاولة نفسها مستمرة."""
        bot, sv, dev = self.make()
        st = self.board()
        lv = self.start(bot, st)
        sv.now.update(kind="level", state={"tubes": st["tubes"][1:]}, level=108)
        self.feedn(bot, 3)
        sv.now.update(state=st)
        self.feedn(bot, 3)
        log = self.log()
        self.assertIs(bot.lv, lv, log)
        self.assertEqual(len(lv.last_state["tubes"]), 6, log)
        self.assertNotIn("الجبس انكسر", log)
        self.assertNotIn("أُعيدت من البداية", log)
        self.assertIn("قارورة مغطّاة عادت إلى القراءة (جبس 1", log)

    def feedn(self, bot, n):
        fr = bot.grab()
        for _ in range(n):
            fr = bot.on_level(fr) or bot.grab()

    def test_l108_pipeline_with_real_vision(self):
        """اللقطة الحقيقية لبداية المرحلة 108 عبر Vision.parse في السائق ("box" يصل إلى الحلّال): أول حركة تكمل الأخضر."""
        import vision as real_vision
        out = driver.Out(Path(self.tmp.name), 10, quiet=True)
        vis = driver.Vision(real_vision, out)
        st = vis.parse(driver.Frame(Image.open(Path(driver.HERE) / "testdata" / "L108_plaster.jpg")))
        self.assertEqual(sum(1 for t in st["tubes"] if t.get("cover") == "plaster"), 6)
        self.assertTrue(all(len(t["box"]) == 4 for t in st["tubes"]))
        self.assertTrue(driver.covered(st))
        self.assertEqual(driver.cover_summary(st), "جبس 6")
        info = {}
        mv = solver.plan(st, info=info)
        self.assertEqual(info["mode"], "plaster")
        self.assertTrue(solver.breaker_completed(st, *mv[0]))
        self.assertEqual(st["tubes"][mv[0][1]]["layers"], ["green", "green"])
        self.assertFalse(driver.suspicious_counts(st))        # المغطّاة طبقات مجهولة: لا «إعادة تصوير» بلا داعٍ


class TestStalls(DriverCase):
    """شاشات توقّف البوت في التشغيل التاسع: الإعلان التجريبي الأبيض، وشعار «MAGIC SORT» فوق لوحة معتمة، والإعلان الأسود."""

    def drive(self, bot, sv, seconds, change=None):
        """يكرّر on_unknown حتى يمرّ الوقت المطلوب (الساعة الافتراضية)، ويعيد [(الوقت، النقرة)] و[(الوقت، المفتاح)]."""
        dev = bot.dev
        taps, keys = [], []
        t0 = self.clock.time()
        n_t, n_k = len(dev.taps), len(dev.keys)
        while self.clock.time() - t0 < seconds:
            if change:
                change(self.clock.time() - t0)
            bot.on_unknown(bot.grab(), "unknown")
            taps += [(self.clock.time() - t0, p) for p in dev.taps[n_t:]]
            keys += [(self.clock.time() - t0, k) for k in dev.keys[n_k:]]
            n_t, n_k = len(dev.taps), len(dev.keys)
        return taps, keys

    def test_white_ad_waits_countdown_then_back_then_relaunch(self):
        bot, sv, dev = self.make()
        sv.now.update(kind="unknown", white_ad=True, ad_close=None, arrow=(236, 650), greens=[{"box": (300, 900, 440, 980)}])
        taps, keys = self.drive(bot, sv, 60)
        log = self.log()
        self.assertEqual(taps, [], log)                       # لا «Install» ولا وسط الإعلان ولا «سهم»
        self.assertTrue(keys and all(t >= driver.CFG["ad_wait_sec"] for t, _ in keys), keys)
        self.assertTrue(all(k == 4 for _, k in keys))
        self.assertTrue(all(b - a >= 5 for (a, _), (b, _) in zip(keys, keys[1:])), keys)
        self.assertEqual(len(dev.stops), 1, log)              # إعادة تشغيل واحدة بعد المهلة
        self.assertIn("إعلان تجريبي أبيض (AppLovin)", log)
        self.assertIn("الإعلان التجريبي الأبيض باقٍ منذ", log)
        self.assertGreaterEqual(dev.launched, 1)

    def test_white_ad_taps_corner_close(self):
        """X ظاهر في زاوية علوية (انتهى العدّ): يُلمس هو لا الرجوع، ولا شيء غيره ولا قبل ثانيتين من ظهور الإعلان."""
        bot, sv, dev = self.make()
        sv.now.update(kind="unknown", white_ad=True, ad_close=(440, 38))
        taps, keys = self.drive(bot, sv, 20)
        self.assertTrue(taps, self.log())
        self.assertTrue(all(near(p, (440, 38)) and t >= 2 for t, p in taps), taps)
        self.assertTrue(all(b - a >= 5 for (a, _), (b, _) in zip(taps, taps[1:])), taps)
        self.assertEqual(keys, [])
        self.assertIn("زرّ الإغلاق X في الزاوية", self.log())

    def test_new_ad_resets_timer(self):
        """إعلان ثانٍ بعد ساعة لا يُعاد تشغيل اللعبة له فوراً (مهلته من أول ظهوره هو)."""
        bot, sv, dev = self.make()
        sv.now.update(kind="unknown", white_ad=True)
        self.drive(bot, sv, 5)
        sv.now.update(white_ad=False)
        self.clock.sleep(3600)
        sv.now.update(white_ad=True)
        taps, keys = self.drive(bot, sv, 8)
        self.assertEqual((taps, keys, dev.stops), ([], [], []), self.log())

    def test_logo_waits_then_back_then_relaunch(self):
        bot, sv, dev = self.make()
        sv.now.update(kind="unknown", logo=True, arrow=(338, 705))    # «سهم» كاذب على الحروف الصفراء
        t0 = self.clock.time()
        taps, keys = self.drive(bot, sv, 70)
        log = self.log()
        self.assertEqual(taps, [], log)
        self.assertEqual(len(keys), 1, keys)
        self.assertGreaterEqual(keys[0][0], driver.CFG["logo_wait_sec"])
        self.assertEqual(len(dev.stops), 1, log)
        self.assertGreaterEqual(dev.stops[0] - t0, driver.CFG["logo_wait_sec"] + driver.CFG["logo_back_sec"])
        self.assertLess(dev.stops[0] - t0, driver.CFG["logo_wait_sec"] + driver.CFG["logo_back_sec"] + 5)
        self.assertIn("شعار «MAGIC SORT» فوق لوحة معتمة", log)
        self.assertIn("رجوع مرة واحدة", log)
        self.assertIn("إعادة تشغيل اللعبة", log)
        self.assertNotIn("سهم تعليم", log)
        self.assertNotIn("3 دقائق", log)

    def test_logo_gone_quickly_no_action(self):
        bot, sv, dev = self.make()
        sv.now.update(kind="unknown", logo=True, arrow=(338, 705))
        taps, keys = self.drive(bot, sv, 4)
        self.assertEqual((taps, keys, dev.stops), ([], [], []))

    def test_black_ad_unchanged_then_capped(self):
        """الإعلان الأسود كما كان (رجوع ثم زاويتا الإغلاق)، ومهلة تعيد اللعبة بدل 25 دقيقة من الرجوع (التشغيل التاسع)."""
        bot, sv, dev = self.make()
        sv.now.update(kind="unknown", black_ad=True)
        taps, keys = self.drive(bot, sv, 20)
        self.assertEqual(keys[0][1], 4)
        self.assertTrue(set(p for _, p in taps) <= {(455, 18), (18, 18)}, taps)
        self.assertEqual(dev.stops, [])
        self.drive(bot, sv, 80)
        self.assertEqual(len(dev.stops), 1, self.log())
        self.assertIn("الإعلان الأسود باقٍ منذ", self.log())

    def test_pangle_ad_never_tapped(self):
        """إعلان Pangle التجريبي الرمادي (التشغيلات 6..19): لا يُلمس «View now» ولا وسطه ولا «سهم» كاذب فيه؛ رجوع بعد مهلة العدّ
        كل 5 ثوانٍ على الأكثر، ثم إعادة اللعبة بعد مهلة الإعلان (كالأبيض)."""
        bot, sv, dev = self.make()
        sv.now.update(kind="unknown", pangle_ad=True, ad_close=None, arrow=(338, 705), greens=[{"box": (160, 580, 320, 640)}])
        taps, keys = self.drive(bot, sv, 60)
        log = self.log()
        self.assertEqual(taps, [], log)
        self.assertTrue(keys and all(t >= driver.CFG["ad_wait_sec"] and k == 4 for t, k in keys), keys)
        self.assertTrue(all(b - a >= 5 for (a, _), (b, _) in zip(keys, keys[1:])), keys)
        self.assertEqual(len(dev.stops), 1, log)
        self.assertIn("إعلان تجريبي رمادي (Pangle)", log)
        self.assertIn("الإعلان التجريبي الرمادي باقٍ منذ", log)
        self.assertNotIn("سهم تعليم", log)

    def test_arrow_on_android_home_never_tapped(self):
        """«سهم» على سطح مكتب Android بعد خروج اللعبة: لا يُلمس ولو فُحصت الواجهة قبل ثانية واللعبة ظاهرة (كانت مهلة الفحص 5 ثوانٍ
        فلُمس سطح المكتب عند (338، 705) بعد إعلان Pangle في التشغيلات 10..19)؛ تُشغَّل اللعبة بدله."""
        bot, sv, dev = self.make()
        dev.focus = lambda: "mCurrentFocus=Window{9 u0 com.google.android.apps.nexuslauncher/com.google.android.apps.nexuslauncher.NexusLauncherActivity}"
        sv.now.update(kind="unknown", arrow=(338, 705))
        bot.unknown_streak, bot.unknown_since = 1, self.clock.time() - 3
        bot.last_focus_check = self.clock.time() - 1
        n0, l0 = len(dev.taps), dev.launched
        bot.on_unknown(bot.grab(), "unknown")
        self.assertEqual(dev.taps[n0:], [], self.log())
        self.assertEqual(dev.launched, l0 + 1)
        self.assertIn("سهم مزعوم واللعبة ليست في الواجهة", self.log())

    def test_journey_claim_arrow_still_tapped(self):
        """«Journey Rewards — Tap to Claim» (ليست إعلاناً ولا شعاراً): لمسة «السهم» التي استلمتها في التشغيل التاسع باقية."""
        bot, sv, dev = self.make()
        sv.now.update(kind="unknown", arrow=(302, 234))
        taps, keys = self.drive(bot, sv, 8)
        self.assertTrue(taps and near(taps[0][1], (302, 234)), (taps, self.log()))
        self.assertIn("سهم تعليم: لمس الهدف (302, 234)", self.log())


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

    def test_backup_parts_replace_single_file_on_branch(self):
        """تحديث ساخن أثناء تشغيل كتب كوده القديم out/game_backup.ab في الفرع: أول نسخة بالكود الجديد ترفع الأجزاء وملف الوصف،
        والملف الواحد يُحذف من الفرع (في الرفع التالي على الأكثر، بعد أن تصير شجرة النشر على الفرع)، وجزء زائد من نسخة أكبر كذلك."""
        br = "claude/test-bot"
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            origin, main = d / "origin.git", d / "main"
            self.sh("git", "init", "-q", "--bare", str(origin))
            self.sh("git", "clone", "-q", str(origin), str(main))
            self.sh("git", "config", "user.email", "t@example.com", cwd=main)
            self.sh("git", "config", "user.name", "t", cwd=main)
            self.sh("git", "checkout", "-q", "-b", br, cwd=main)
            (main / "research" / "emu").mkdir(parents=True)
            (main / "research" / "emu" / "cmd.txt").write_text("seq 0\n")
            self.sh("git", "add", "-A", cwd=main)
            self.sh("git", "commit", "-q", "-m", "init", cwd=main)
            self.sh("git", "push", "-q", "origin", br, cwd=main)
            # الكود القديم رفع الملف الواحد في out/ (بعد بداية التشغيل: ليس في HEAD المحلي)
            other = d / "other"
            self.sh("git", "clone", "-q", "-b", br, str(origin), str(other))
            self.sh("git", "config", "user.email", "o@example.com", cwd=other)
            self.sh("git", "config", "user.name", "o", cwd=other)
            (other / driver.OUT_REL).mkdir(parents=True)
            (other / driver.OUT_REL / driver.BACKUP_NAME).write_bytes(b"old single backup")
            self.sh("git", "add", "-A", cwd=other)
            self.sh("git", "commit", "-q", "-m", "old", cwd=other)
            self.sh("git", "push", "-q", "origin", br, cwd=other)

            saved = (driver.ROOT, driver.PUB_DIR, dict(driver.CFG))
            driver.ROOT, driver.PUB_DIR = main, d / "pub"
            driver.CFG["branch"] = br
            driver.CFG["backup_part_mb"] = 0.01
            try:
                game = FakeGame([make_level(random.Random(1), 3, 1)], random.Random(1))
                out = driver.Out(main / driver.OUT_REL, 50, quiet=True)
                (out.dir / driver.BACKUP_NAME).write_bytes(b"old single backup")
                bot = driver.Bot(FakeDevice(game), driver.Vision(FakeVisionModule(game), out), out, 10)
                bot.setup_publisher()
                self.assertTrue(bot.pub_ok)
                tmp = d / "b.ab"
                tmp.write_bytes(backup_bytes(30000, seed=3))
                clock, driver.time = driver.time, FakeClock()
                try:
                    self.assertTrue(bot.store_backup(str(tmp)))
                finally:
                    driver.time = clock
                ls = lambda: self.sh("git", "--git-dir", str(origin), "ls-tree", "-r", "--name-only", br)  # noqa: E731
                self.assertTrue(bot.publish("نشر 1"))
                self.assertTrue(bot.publish("نشر 2"))
                files = ls()
                self.assertNotIn(driver.OUT_REL + "/" + driver.BACKUP_NAME + "\n", files)
                self.assertIn(driver.OUT_REL + "/" + driver.backup_part_name(2), files)
                self.assertIn(driver.OUT_REL + "/" + driver.BACKUP_MANIFEST, files)
                # نسخة أصغر: يُحذف الجزء 02 من الفرع
                tmp.write_bytes(backup_bytes(15000, seed=4))
                driver.time = FakeClock()
                try:
                    self.assertTrue(bot.store_backup(str(tmp)))
                finally:
                    driver.time = clock
                self.assertTrue(bot.publish("نشر 3"))
                files = ls()
                self.assertNotIn(driver.backup_part_name(2), files)
                self.assertIn(driver.OUT_REL + "/" + driver.backup_part_name(1), files)
                # الفرع كما يراه التشغيل التالي: الأجزاء تُجمع وتطابق
                chk = d / "chk"
                self.sh("git", "clone", "-q", "-b", br, str(origin), str(chk))
                got, info = driver.join_backup(chk / driver.OUT_REL, d / "j.ab")
                self.assertEqual(got.read_bytes(), tmp.read_bytes(), info)
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


class TestPlanBoost(unittest.TestCase):
    """مضاعف التخطيط: الصعبة جداً 3، وكل «Give Up» في المرحلة نفسها يزيده 0.75 حتى 4."""

    def test_boost_grows_with_give_ups(self):
        self.assertEqual(driver.plan_boost("unknown", 0), 1.0)
        self.assertEqual(driver.plan_boost(None, 1), 1.75)
        self.assertEqual(driver.plan_boost("hard", 2), 2.5)
        self.assertEqual(driver.plan_boost("unknown", 4), 4.0)
        self.assertEqual(driver.plan_boost("unknown", 40), 4.0)       # الحدّ
        self.assertEqual(driver.plan_boost("superhard", 0), 3.0)
        self.assertEqual(driver.plan_boost("superhard", 1), 3.0)      # الأكبر من الاثنين
        self.assertEqual(driver.plan_boost("superhard", 9), 4.0)
        self.assertEqual(driver.plan_boost("unknown", -3), 1.0)       # عدّاد غريب لا يُنقص


def fake_emulator_host(tc, root):
    """يعزل تشخيص المحاكي في الاختبار عن المضيف الحقيقي: سجلّ المحاكي ومجلّد AVD في مجلّد مؤقت، وفحص عملية المحاكي «تعذّر»
    (None: لا كفّ مبكر عن انتظار الإقلاع). CFG يُعاد في tearDown الصنف."""
    root = Path(root)
    saved = (driver.EMU_LOG, driver.emulator_running)
    driver.EMU_LOG = str(root / "emulator_restart.log")
    driver.emulator_running = lambda: None
    driver.CFG["emu_avd_home"] = str(root / "avd")

    def restore():
        driver.EMU_LOG, driver.emulator_running = saved
    tc.addCleanup(restore)
    return root / "avd" / ("%s.avd" % driver.CFG["emu_avd"])


class FlakyDevice(FakeDevice):
    """جهاز تفشل لقطاته عدداً من المرات (المحاكي مات أو انقطع adb) ثم تعود؛ يسجّل ما فعله حارس المحاكي."""

    def __init__(self, game, fails, boot="1"):
        super().__init__(game)
        self.fails = fails
        self.boot = boot
        self.adb_restarts = 0
        self.states = 0

    def screencap(self):
        if self.fails > 0:
            self.fails -= 1
            return None
        return super().screencap()

    def adb_state(self):
        self.states += 1
        return ""

    def restart_adb(self):
        self.adb_restarts += 1

    def installed(self):
        return True

    def sh(self, cmd, timeout=30):
        return self.boot if "sys.boot_completed" in cmd else ""


class TestEmulatorWatchdog(unittest.TestCase):
    """حارس المحاكي (recover_device): adb عند 3 لقطات فاشلة، والمحاكي عند 4 ثم كل 4، والتوقف بعد إعادات متتالية بلا تقدّم
    (التشغيل العاشر: محاكٍ لا يعود؛ وسياسة التقدّم نفسها في TestEmuRestartPolicy وTestEmuRestartProgress)."""

    def setUp(self):
        self.clock = FakeClock()
        self._time = driver.time
        driver.time = self.clock
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = dict(driver.CFG)
        self._kill, self._start = driver.kill_emulators, driver.start_emulator
        self.started = 0
        self.wipes = 0
        self.start_ok = True
        driver.kill_emulators = lambda: None
        fake_emulator_host(self, self.tmp.name)

        def fake_start(log_path=None, wipe=False):
            self.started += 1
            self.wipes += bool(wipe)
            return self.start_ok
        driver.start_emulator = fake_start

    def tearDown(self):
        driver.time = self._time
        driver.CFG.clear()
        driver.CFG.update(self.cfg)
        driver.kill_emulators, driver.start_emulator = self._kill, self._start
        self.tmp.cleanup()

    def make(self, fails, boot="1"):
        rng = random.Random(3)
        game = FakeGame([make_level(rng, 4, 2)], rng)
        dev = FlakyDevice(game, fails, boot)
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        bot = driver.Bot(dev, driver.Vision(FakeVisionModule(game), out), out, 600, git=False)
        return game, dev, bot

    def log(self):
        return (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")

    def test_defaults(self):
        self.assertEqual(self.cfg["emu_restarts"], 40)
        self.assertEqual(self.cfg["emu_fruitless_max"], 3)
        self.assertEqual(self.cfg["emu_progress_min"], 15.0)
        self.assertEqual(self.cfg["emu_restart_min_left"], 6.0)
        self.assertEqual(self.cfg["backup_win_min"], 10.0)
        self.assertLess(self.cfg["backup_part_mb"] * 1024 * 1024, 50 * 1000 * 1000)   # تحت تحذير GitHub (50 ميغا)

    def test_short_glitch_needs_no_recovery(self):
        game, dev, bot = self.make(2)
        bot.run(max_iters=40)
        self.assertEqual(dev.adb_restarts, 0)
        self.assertEqual(self.started, 0)
        self.assertEqual(bot.cap_fails, 0)
        self.assertFalse(bot.stop)

    def test_adb_restart_after_three_failures(self):
        game, dev, bot = self.make(3)
        bot.run(max_iters=40)
        self.assertEqual(dev.adb_restarts, 1, self.log()[-1500:])
        self.assertEqual(self.started, 0)
        self.assertIn("إعادة تشغيل خادم adb", self.log())
        self.assertEqual(bot.cap_fails, 0)

    def test_emulator_restart_then_play_continues(self):
        game, dev, bot = self.make(7)
        launched = dev.launched
        bot.run(max_iters=80)
        self.assertEqual(self.started, 1, self.log()[-2000:])
        self.assertEqual(bot.emu_restarts, 1)
        self.assertGreater(dev.launched, launched)
        self.assertIn("عاد المحاكي وشُغّلت اللعبة من جديد", self.log())
        self.assertFalse(bot.stop)
        for _ in range(20):
            bot.run(max_iters=100)
            if game.wins:
                break
        self.assertEqual(game.wins, 1, self.log()[-2000:])

    def test_gives_up_after_restarts_without_progress(self):
        # المحاكي لا يعود أبداً (لا أمر emulator): الإعادة الأولى ثم إعادتان بلا تقدّم... حتى emu_fruitless_max إعادات بلا تقدّم
        self.start_ok = None
        game, dev, bot = self.make(10 ** 6)
        bot.run(max_iters=60)
        self.assertEqual(self.started, driver.CFG["emu_fruitless_max"], self.log()[-2000:])
        self.assertTrue(bot.stop)
        self.assertIn("إيقاف البوت لينتهي التشغيل", self.log())
        self.assertIn("إعادات متتالية للمحاكي بلا أي تقدّم", self.log())

    def test_boot_that_never_completes_counts_as_failed_restart(self):
        # كل إعادة: إقلاع عادي فاشل ثم محاولة بمحو البيانات فاشلة (TestEmulatorRestartWipe)، وتُحسب إعادة واحدة بلا ثمرة
        game, dev, bot = self.make(10 ** 6, boot="0")
        bot.run(max_iters=60)
        self.assertEqual(self.started - self.wipes, driver.CFG["emu_fruitless_max"])
        self.assertEqual(self.wipes, driver.CFG["emu_fruitless_max"])
        self.assertEqual(bot.emu_restarts, driver.CFG["emu_fruitless_max"])
        self.assertTrue(bot.stop)
        self.assertIn("لم يكمل إقلاعه", self.log())
        self.assertIn("لم يُقلع حتى بعد محو بياناته", self.log())


# ============================================================== إقلاع المحاكي بمحو البيانات والتشخيص (التشغيل 16)
class WipeDevice(FlakyDevice):
    """جهاز يقلع أو لا بحسب نوع التشغيل (عادي أو بمحو البيانات)، واللعبة تغيب بعد المحو حتى تُثبَّت. present = False: لا جهاز في
    adb، فـ wait-for-device يحجب مهلته كلها بالساعة الوهمية (كـ adb الحقيقي) ثم يفشل."""

    def __init__(self, game, clock=None):
        super().__init__(game, 0)
        self.game_installed = True
        self.clock = clock
        self.present = True
        self.waits = 0

    def installed(self):
        return self.game_installed

    def run(self, args, timeout=30, binary=False):
        if "wait-for-device" in args:
            self.waits += 1
            if not self.present:
                if self.clock:
                    self.clock.sleep(timeout)
                return 124, "timeout"
        return super().run(args, timeout, binary)

    def sh(self, cmd, timeout=30):
        if not self.present:
            return ""
        if callable(self.boot) and "sys.boot_completed" in cmd:
            return self.boot()
        return super().sh(cmd, timeout)


class TestEmulatorRestartWipe(unittest.TestCase):
    """restart_emulator: إقلاع عادي، وإن فشل تشغيل واحد بـ -wipe-data ثم تثبيت اللعبة واستعادة آخر نسخة، في حدود الوقت الباقي؛
    والتشخيص (آخر أسطر سجلّ المحاكي والقرص والذاكرة) في السجل، ولا يتعطّل حين تغيب الملفات أو الأوامر."""

    def setUp(self):
        self.clock = FakeClock()
        self._time = driver.time
        driver.time = self.clock
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.cfg = dict(driver.CFG)
        self._kill, self._start = driver.kill_emulators, driver.start_emulator
        self.avd = fake_emulator_host(self, self.d)
        self.starts = []
        self.kills = 0
        self.plan = {False: "1", True: "1"}      # ما يعيده sys.boot_completed بعد التشغيل العادي / بالمحو

        def fake_kill():
            self.kills += 1
        driver.kill_emulators = fake_kill

        def fake_start(log_path=None, wipe=False):
            self.starts.append(bool(wipe))
            self.dev.boot = self.plan[bool(wipe)]
            if wipe:
                self.dev.game_installed = False
            with open(driver.EMU_LOG, "a", encoding="utf-8") as f:
                f.write("=== start wipe=%s ===\n" % wipe)
                for i in range(30):
                    f.write("emulator line %d\n" % i)
            return True
        driver.start_emulator = fake_start
        rng = random.Random(11)
        game = FakeGame([make_level(rng, 4, 2)], rng)
        self.dev = WipeDevice(game, self.clock)
        self.out = driver.Out(self.d / "out", 600, quiet=True)
        self.bot = driver.Bot(self.dev, driver.Vision(FakeVisionModule(game), self.out), self.out, 300, git=False)
        self.bot.log_host_oom = lambda: None
        self.called = []

        def fake_install(until=None):
            self.called.append("install")
            self.install_left = (until - self.clock.time()) if until else None
            self.dev.game_installed = True
            return True
        self.bot.install_game = fake_install
        self.bot.restore_app = lambda: (self.called.append("restore"), True)[1]

    def tearDown(self):
        driver.time = self._time
        driver.CFG.clear()
        driver.CFG.update(self.cfg)
        driver.kill_emulators, driver.start_emulator = self._kill, self._start
        self.tmp.cleanup()

    def log(self):
        return (self.d / "out" / "log.txt").read_text(encoding="utf-8")

    def test_normal_boot_needs_no_wipe(self):
        launched = self.dev.launched
        self.assertTrue(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False])
        self.assertEqual(self.called, [])
        self.assertGreater(self.dev.launched, launched)
        log = self.log()
        self.assertIn("أقلع المحاكي بعد", log)
        self.assertIn("تشخيص المحاكي: القرص:", log)          # الموجز عند كل إعادة
        self.assertIn("الذاكرة:", log)
        self.assertNotIn("محو", log)
        self.assertFalse((self.d / "out" / "emulator_log.txt").exists())

    def test_failed_boot_then_wipe_installs_and_restores(self):
        self.plan = {False: "0", True: "1"}
        self.avd.mkdir(parents=True)
        (self.avd / "multiinstance.lock").write_text("123")
        (self.avd / "hardware-qemu.ini.lock").mkdir()
        (self.avd / "userdata-qemu.img").write_bytes(b"\0" * 4096)
        t0 = self.clock.time()
        launched = self.dev.launched
        self.assertTrue(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False, True])
        self.assertEqual(self.called, ["install", "restore"])
        self.assertGreater(self.dev.launched, launched)
        self.assertEqual(sorted(p.name for p in self.avd.glob("*.lock")), [])
        self.assertTrue((self.avd / "userdata-qemu.img").exists())
        # الإقلاع العادي يُنتظر emu_boot_min دقيقة لا عشراً
        self.assertLess(self.clock.time() - t0, (driver.CFG["emu_boot_min"] + 2) * 60)
        log = self.log()
        self.assertIn("المحاكي لم يكمل إقلاعه بعد إعادة تشغيله", log)
        self.assertIn("حُذفت أقفال AVD باقية من المحاكي المقتول: hardware-qemu.ini.lock، multiinstance.lock", log)
        self.assertIn("مجلّد AVD test.avd: userdata-qemu.img", log)
        self.assertIn("آخر 15 سطراً من سجلّ المحاكي", log)
        self.assertIn("  | emulator line 29", log)
        self.assertIn("محاولة أخيرة: تشغيل المحاكي بمحو بياناته (-wipe-data)", log)
        self.assertIn("أقلع المحاكي بعد محو بياناته", log)
        self.assertIn("اللعبة غير مثبّتة بعد إعادة المحاكي (مُحيت بياناته)", log)
        self.assertIn("عاد المحاكي بعد محو بياناته: ثُبّتت اللعبة واستُعيدت آخر نسخة احتياطية", log)
        self.assertIn("عاد المحاكي وشُغّلت اللعبة من جديد", log)
        tail = (self.d / "out" / "emulator_log.txt").read_text(encoding="utf-8")
        self.assertIn("emulator line 29", tail)

    def test_wipe_without_backup_says_so(self):
        self.plan = {False: "0", True: "1"}
        self.bot.restore_app = lambda: (self.called.append("restore"), False)[1]
        self.assertTrue(self.bot.restart_emulator(budget=60 * 60))
        self.assertIn("لم تُستعد نسخة احتياطية", self.log())

    def test_both_boots_fail(self):
        self.plan = {False: "0", True: "0"}
        launched = self.dev.launched
        self.assertFalse(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False, True])
        self.assertEqual(self.called, [])
        self.assertEqual(self.dev.launched, launched)
        log = self.log()
        self.assertIn("المحاكي لم يُقلع حتى بعد محو بياناته", log)
        self.assertEqual(log.count("آخر 15 سطراً من سجلّ المحاكي"), 2)

    def test_no_time_for_wipe_and_install(self):
        self.plan = {False: "0", True: "1"}
        self.assertFalse(self.bot.restart_emulator(budget=15 * 60))   # 6 دقائق إقلاع فاشل ثم يبقى نحو 9 < 4 + 12
        self.assertEqual(self.starts, [False])
        self.assertEqual(self.called, [])
        self.assertIn("لا وقت لتشغيل المحاكي بمحو بياناته ثم تثبيت اللعبة واستعادة الحفظ", self.log())

    def test_tight_budget_wipe_boot_leaves_install_time(self):
        self.plan = {False: "0", True: "0"}
        t0 = self.clock.time()
        self.assertFalse(self.bot.restart_emulator(budget=23 * 60))
        self.assertEqual(self.starts, [False, True])
        # انتظار الإقلاع بعد المحو لا يتجاوز ما يترك emu_install_min دقيقة
        self.assertLessEqual(self.clock.time() - t0, (23 - driver.CFG["emu_install_min"]) * 60)
        self.plan = {False: "0", True: "1"}
        self.starts.clear()
        self.assertTrue(self.bot.restart_emulator(budget=23 * 60))
        self.assertEqual(self.called, ["install", "restore"])
        self.assertGreaterEqual(self.install_left, driver.CFG["emu_install_min"] * 60)

    def test_wipe_can_be_disabled(self):
        driver.CFG["emu_wipe"] = 0
        self.plan = {False: "0", True: "1"}
        self.assertFalse(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False])

    def test_install_failure_after_wipe_stops_the_bot(self):
        # المحاكي أقلع بلا اللعبة: محاولة تثبيت ثانية ثم إيقاف البوت (لقطات سطح مكتب Android تنجح فلا تعود recover_device)
        self.plan = {False: "0", True: "1"}
        self.bot.install_game = lambda until=None: (self.called.append("install"), False)[1]
        launched = self.dev.launched
        self.assertFalse(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.called, ["install", "install"])
        self.assertTrue(self.bot.stop)
        self.assertEqual(self.dev.launched, launched)
        log = self.log()
        self.assertIn("تعذّر تثبيت اللعبة بعد إعادة المحاكي: محاولة ثانية", log)
        self.assertIn("المحاكي يعمل بلا اللعبة بعد إعادته: إيقاف البوت", log)

    def test_install_failure_without_time_for_retry(self):
        self.plan = {False: "1", True: "1"}
        self.dev.game_installed = False

        def slow_fail(until=None):
            self.called.append("install")
            self.clock.sleep(until - self.clock.time())        # استهلك المهلة كلها
            return False
        self.bot.install_game = slow_fail
        self.assertFalse(self.bot.restart_emulator(budget=20 * 60))
        self.assertEqual(self.called, ["install"])
        self.assertTrue(self.bot.stop)

    def test_early_stop_when_emulator_process_dies(self):
        # المحاكي خرج فوراً ولا جهاز في adb: wait-for-device يحجب مهلته (20 ث) لا 300، والكفّ عند أول فحص بعد 30 ث
        driver.emulator_running = lambda: False
        self.dev.present = False
        self.plan = {False: "0", True: "0"}
        t0 = self.clock.time()
        self.assertFalse(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False, True])
        self.assertLess(self.clock.time() - t0, 3 * 60)
        self.assertEqual(self.log().count("عملية المحاكي انتهت بعد"), 2)
        self.assertGreaterEqual(self.dev.waits, 4)

    def test_absent_device_times_out_within_boot_window(self):
        # لا جهاز ولا فحص للعملية (None): الإقلاع العادي لا يتجاوز emu_boot_min رغم الحجب
        self.dev.present = False
        self.plan = {False: "0", True: "0"}
        t0 = self.clock.time()
        driver.CFG["emu_wipe"] = 0
        self.assertFalse(self.bot.restart_emulator(budget=60 * 60))
        self.assertLessEqual(self.clock.time() - t0, driver.CFG["emu_boot_min"] * 60 + 60)

    def test_slow_but_alive_emulator_gets_more_time_instead_of_wipe(self):
        running = {"v": False}
        driver.emulator_running = lambda: running["v"]
        boot_at = {}

        def fake_kill():
            self.kills += 1
            running["v"] = False
        driver.kill_emulators = fake_kill
        start = driver.start_emulator

        def start_alive(log_path=None, wipe=False):
            r = start(log_path, wipe)
            running["v"] = True
            boot_at["t"] = self.clock.time() + (driver.CFG["emu_boot_min"] + 2) * 60
            self.dev.boot = lambda: "1" if self.clock.time() >= boot_at["t"] else "0"
            return r
        driver.start_emulator = start_alive
        self.assertTrue(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False])
        self.assertEqual(self.called, [])
        log = self.log()
        self.assertIn("المحاكي حيّ وظاهر في adb لكنه لم يُكمل إقلاعه: تمديد الانتظار 4 دقيقة بدل محو بياناته", log)
        self.assertNotIn("-wipe-data", log)

    def test_slow_emulator_that_never_boots_is_wiped_after_extension(self):
        running = {"v": False}
        driver.emulator_running = lambda: running["v"]

        def fake_kill():
            self.kills += 1
            running["v"] = False
        driver.kill_emulators = fake_kill
        start = driver.start_emulator

        def start_alive(log_path=None, wipe=False):
            r = start(log_path, wipe)
            running["v"] = True
            return r
        driver.start_emulator = start_alive
        self.plan = {False: "0", True: "1"}
        self.assertTrue(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False, True])
        self.assertIn("المحاكي لم يكمل إقلاعه حتى بعد التمديد", self.log())

    def test_lock_message_retries_normal_boot_not_wipe(self):
        # سجلّ المحاكي يذكر محاكياً آخر بالـ AVD نفسه (قفل باقٍ أو زومبي): إقلاع عادي ثانٍ بعد الحصد وحذف الأقفال، لا محو
        start = driver.start_emulator

        def start_locked(log_path=None, wipe=False):
            first = not self.starts
            r = start(log_path, wipe)
            if first:
                with open(driver.EMU_LOG, "a", encoding="utf-8") as f:
                    f.write("ERROR | Running multiple emulators with the same AVD is an experimental feature.\n")
                self.dev.boot = "0"
            else:
                self.dev.boot = "1"
            return r
        driver.start_emulator = start_locked
        self.assertTrue(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False, False])
        self.assertEqual(self.called, [])
        log = self.log()
        self.assertIn("إقلاع عادي ثانٍ بدل محو البيانات", log)
        self.assertNotIn("محاولة أخيرة", log)

    def test_persistent_lock_message_does_not_wipe(self):
        start = driver.start_emulator

        def start_locked(log_path=None, wipe=False):
            r = start(log_path, wipe)
            with open(driver.EMU_LOG, "a", encoding="utf-8") as f:
                f.write("emulator: ERROR: Another emulator instance is running. Please close it\n")
            self.dev.boot = "0"
            return r
        driver.start_emulator = start_locked
        self.assertFalse(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False, False])
        self.assertIn("محو البيانات لا يعالج ذلك", self.log())

    def test_live_old_emulator_keeps_locks_and_blocks_wipe(self):
        # عملية محاكٍ لا تموت (حالة D مثلاً): تُقتل مرتين، ولا تُحذف أقفال AVD، ولا محو
        driver.emulator_running = lambda: True
        self.avd.mkdir(parents=True)
        (self.avd / "multiinstance.lock").write_text("1")
        self.plan = {False: "0", True: "1"}
        self.assertFalse(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False])
        self.assertEqual(self.kills, 2)
        self.assertTrue((self.avd / "multiinstance.lock").exists())
        log = self.log()
        self.assertIn("بقيت عملية محاكٍ حيّة بعد قتلها مرتين: لا تُحذف أقفال AVD", log)
        self.assertIn("لا محو للبيانات", log)

    def test_start_oserror_gets_diagnostics_and_wipe_attempt(self):
        # الأمر موجود وتعذّر تشغيله (False، لا None): تشخيص كامل ثم محاولة المحو، لا «لم يُعثر على الأمر»
        driver.start_emulator = lambda log_path=None, wipe=False: (self.starts.append(bool(wipe)), False)[1]
        self.assertFalse(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False, True])
        log = self.log()
        self.assertIn("تعذّر تشغيل الأمر emulator (خطأ نظام)", log)
        self.assertNotIn("لم يُعثر على الأمر", log)
        self.assertIn("مجلّد AVD", log)

    def test_missing_emulator_command_logs_full_diagnostics(self):
        driver.start_emulator = lambda log_path=None, wipe=False: (self.starts.append(bool(wipe)), None)[1]
        self.assertFalse(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.starts, [False])
        log = self.log()
        self.assertIn("لم يُعثر على الأمر emulator", log)
        self.assertIn("مجلّد AVD", log)

    # --- الاستعادة بعد المحو لا تفقد آخر نسخة سليمة
    def _restore_results(self, results, had_backup=True):
        it = iter(results)

        def fake_restore():
            self.called.append("restore")
            self.bot.restore_had_backup = had_backup
            return next(it)
        self.bot.restore_app = fake_restore

    def test_failed_restore_after_wipe_is_retried(self):
        self.plan = {False: "0", True: "1"}
        self._restore_results([False, True])
        self.bot.levels_done = 5
        self.assertTrue(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.called, ["install", "restore", "restore"])
        self.assertFalse(self.bot.backup_hold)
        # الحالة المستعادة لا تُنسخ فوراً (ولا يُكتب في وصفها levels_done الحالي)
        self.assertEqual(self.bot.backup_levels, 5)
        self.assertGreater(self.bot.last_backup, self.clock.time() - 60)
        self.assertIn("لم تُستعد النسخة الاحتياطية بعد تثبيت اللعبة: محاولة ثانية", self.log())

    def test_failed_restore_after_wipe_holds_backups(self):
        self.plan = {False: "0", True: "1"}
        self._restore_results([False, False])
        self.assertTrue(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.called, ["install", "restore", "restore"])
        self.assertTrue(self.bot.backup_hold)
        log = self.log()
        self.assertIn("لا تُكتب نسخة فوق آخر نسخة سليمة حتى نهاية التشغيل", log)
        self.assertIn("لم تُستعد نسخة احتياطية", log)
        # الحلقة لا تأخذ نسخة (لا بعد فوز ولا كل 45 دقيقة ولا قبل النهاية)، وأمر backup يُرفض، وملف الوصف في out/ كما هو
        man = self.out.dir / driver.BACKUP_MANIFEST
        man.write_text('{"keep": 1}', encoding="utf-8")
        backups = []
        real_backup = self.bot.backup_app
        self.bot.backup_app = lambda: backups.append(1)
        self.bot.remote_thread = lambda: None
        self.bot.git_enabled = True
        self.bot.levels_done = 3
        self.bot.backup_levels = 0
        self.bot.last_backup = self.clock.time() - 60 * 60
        self.bot.deadline = self.clock.time() + 3 * 60
        self.bot.run(max_iters=2)
        self.assertEqual(backups, [])
        self.assertFalse(real_backup())
        self.assertIn("لا تُكتب نسخة فوق آخر نسخة سليمة: اللعبة لم تُستعد", self.log())
        self.assertEqual(man.read_text(encoding="utf-8"), '{"keep": 1}')

    def test_backup_hold_survives_hot_update(self):
        self.bot.backup_hold = True
        saved = driver.STATE_FILE
        driver.STATE_FILE = self.d / "state.json"
        try:
            self.bot.save_counters()
            b2 = driver.Bot(self.dev, self.bot.vis, driver.Out(self.d / "b2", 10, quiet=True), 100, git=False)
            self.assertTrue(b2.load_counters())
        finally:
            driver.STATE_FILE = saved
        self.assertTrue(b2.backup_hold)

    def test_no_backup_anywhere_needs_no_hold(self):
        self.plan = {False: "0", True: "1"}
        self._restore_results([False], had_backup=False)
        self.assertTrue(self.bot.restart_emulator(budget=60 * 60))
        self.assertEqual(self.called, ["install", "restore"])
        self.assertFalse(self.bot.backup_hold)

    def test_policy_wipe_restart_counts_as_normal_restart(self):
        self.plan = {False: "0", True: "1"}
        self.clock.sleep(10 * 60)
        self.bot.last_ok_grab = self.clock.time()
        self.bot.cap_fails = 4
        self.assertTrue(self.bot.recover_device())
        self.assertEqual(self.bot.cap_fails, 0)
        self.assertEqual(self.bot.emu_restarts, 1)
        self.assertEqual(self.bot.emu_fruitless, 0)
        self.assertFalse(self.bot.stop)
        self.assertEqual(self.starts, [False, True])

    def test_wipe_reapplies_airplane_mode(self):
        self.plan = {False: "0", True: "1"}
        self.bot.airplane_on = True
        cmds = []
        sh = self.dev.sh
        self.dev.sh = lambda cmd, timeout=30: (cmds.append(cmd), sh(cmd, timeout))[1]
        self.assertTrue(self.bot.restart_emulator(budget=60 * 60))
        self.assertIn("settings put global airplane_mode_on 1", cmds)

    # --- التشخيص
    def test_diagnostics_robust_when_files_missing(self):
        driver.MEMINFO, saved = str(self.d / "no_meminfo"), driver.MEMINFO
        try:
            lines = driver.emulator_diagnostics(full=True, log_path=str(self.d / "missing.log"))
        finally:
            driver.MEMINFO = saved
        text = "\n".join(lines)
        self.assertIn("القرص: AVD", text)                    # مجلّد AVD غائب: يُقرأ قرص أقرب مجلّد موجود فوقه
        self.assertIn("الذاكرة: تعذّرت قراءتها", text)
        self.assertIn("مجلّد AVD غير موجود", text)
        self.assertIn("عملية المحاكي: تعذّر فحصها", text)
        self.assertIn("غير موجود أو فارغ", text)

    def test_diagnostics_tail_and_brief(self):
        log = self.d / "emu.log"
        log.write_bytes(b"".join(b"line %d\n" % i for i in range(40)) + b"\xff\xfe bad utf8\n\n")
        full = driver.emulator_diagnostics(full=True, log_path=str(log))
        tail = [l for l in full if l.startswith("  | ")]
        self.assertEqual(len(tail), 15)
        self.assertEqual(tail[0], "  | line 26")
        self.assertIn("bad utf8", tail[-1])
        brief = driver.emulator_diagnostics(full=False, log_path=str(log), tail=3)
        self.assertEqual(len([l for l in brief if l.startswith("  | ")]), 3)
        self.assertFalse(any("مجلّد AVD" in l for l in brief))
        self.assertEqual(driver.tail_lines(str(self.d / "nope.log")), [])

    def test_log_emu_diag_never_raises(self):
        saved = driver.emulator_diagnostics

        def boom(**kw):
            raise RuntimeError("x")
        driver.emulator_diagnostics = boom
        try:
            self.bot.log_emu_diag(full=True)
        finally:
            driver.emulator_diagnostics = saved
        self.assertIn("تعذّر تشخيص المحاكي", self.log())

    def test_emulator_running_without_pgrep(self):
        saved = os.environ.get("PATH"), driver.PROC
        os.environ["PATH"] = str(self.d / "empty")
        driver.PROC = str(self.d / "no_proc")                 # لا /proc ولا pgrep: تعذّر الفحص
        try:
            self.assertIsNone(self._real_running()())
        finally:
            os.environ["PATH"], driver.PROC = saved

    def _fake_proc(self, procs):
        root = self.d / "proc"
        for pid, comm, state, ppid, cmd in procs:
            (root / str(pid)).mkdir(parents=True)
            (root / str(pid) / "stat").write_text("%d (%s) %s %d 1 1 0 -1" % (pid, comm, state, ppid))
            (root / str(pid) / "cmdline").write_bytes(cmd.replace(" ", "\0").encode())
        (root / "self").mkdir(parents=True, exist_ok=True)
        saved = driver.PROC
        driver.PROC = str(root)
        self.addCleanup(lambda: setattr(driver, "PROC", saved))
        return root

    def test_zombie_emulator_is_not_running(self):
        # التشغيل 16: بعد التحديث الساخن صار المحاكي الميت زومبي لا يحصده أحد؛ pgrep -f يطابقه، و/proc يبيّن أنه Z
        me = os.getpid()
        self._fake_proc([(4242, "qemu-system-x86", "Z", me, ""),
                         (77, "bash", "S", 1, "bash -c echo hi"),
                         (78, "python3", "S", 1, "python3 driver.py")])
        real = self._real_running()
        self.assertEqual(driver.emulator_procs(), [(4242, "Z", me, "qemu-system-x86")])
        self.assertFalse(real())
        driver.emulator_running = real
        summary = driver.emulator_proc_summary()
        self.assertIn("غائبة", summary)
        self.assertIn("qemu-system-x86 4242 Z ابن البوت", summary)
        self._fake_proc([(4300, "qemu-system-x86", "D", 1,
                          "/sdk/emulator/qemu/linux-x86_64/qemu-system-x86_64 -avd test -no-window")])
        self.assertTrue(real())
        self.assertIn("qemu-system-x86 4300 D", driver.emulator_proc_summary())

    def test_reaps_real_zombie_child_named_qemu(self):
        # زومبي حقيقي: نسخة من sleep باسم qemu-system-x86_64 تُقتل دون wait؛ prepare_emulator يحصدها ويسجّل، ثم لا يراها
        import signal
        import time as real_time
        sleep = shutil.which("sleep")
        if not sleep or not os.path.isdir("/proc/self"):
            self.skipTest("لا sleep أو لا /proc")
        exe = self.d / "qemu-system-x86_64"
        shutil.copy(sleep, exe)
        exe.chmod(0o755)
        p = subprocess.Popen([str(exe), "300"])
        try:
            os.kill(p.pid, signal.SIGKILL)
            state = ""
            for _ in range(200):
                try:
                    state = Path("/proc/%d/stat" % p.pid).read_text().rsplit(")", 1)[1].split()[0]
                except OSError:
                    break
                if state == "Z":
                    break
                real_time.sleep(0.01)
            self.assertEqual(state, "Z")
            self.assertIn((p.pid, "Z", os.getpid(), "qemu-system-x86"), driver.emulator_procs())
            driver.emulator_running = self._real_running()
            self.assertFalse(any(pid == p.pid and st != "Z" for pid, st, _, _ in driver.emulator_procs()))
            self.avd.mkdir(parents=True)
            (self.avd / "multiinstance.lock").write_text(str(p.pid))
            self.assertTrue(self.bot.prepare_emulator())
            self.assertFalse(Path("/proc/%d" % p.pid).exists())
            self.assertFalse((self.avd / "multiinstance.lock").exists())
            self.assertIn("حُصد محاكٍ ميت (زومبي) من قبل التحديث الساخن: qemu-system-x86 pid %d" % p.pid, self.log())
        finally:
            p.returncode = -9                                   # حُصد بـ waitpid: لا يحاول Popen حصده ثانية
            if Path("/proc/%d" % p.pid).exists():
                try:
                    os.waitpid(p.pid, 0)
                except ChildProcessError:
                    pass

    def test_emu_log_lock_detection_reads_last_start_only(self):
        log = self.d / "emu.log"
        log.write_text("=== 10:00 -avd test ===\nRunning multiple emulators with the same AVD\n=== 10:05 -avd test ===\nok\n")
        self.assertFalse(driver.emu_log_mentions_lock(str(log)))
        with open(log, "a") as f:
            f.write("ERROR: another emulator instance is running\n")
        self.assertTrue(driver.emu_log_mentions_lock(str(log)))
        self.assertFalse(driver.emu_log_mentions_lock(str(self.d / "missing.log")))

    def test_avd_dir_search_order(self):
        driver.CFG["emu_avd_home"] = ""
        keys = ("ANDROID_AVD_HOME", "ANDROID_USER_HOME", "ANDROID_EMULATOR_HOME")
        saved = {k: os.environ.get(k) for k in keys}
        try:
            for k in keys:
                os.environ.pop(k, None)
            os.environ["ANDROID_USER_HOME"] = str(self.d / "user")
            os.environ["ANDROID_EMULATOR_HOME"] = str(self.d / "emu")
            (self.d / "emu" / "avd" / "test.avd").mkdir(parents=True)
            self.assertEqual(driver.avd_dir(), self.d / "emu" / "avd" / "test.avd")     # الموجود
            (self.d / "user" / "avd" / "test.avd").mkdir(parents=True)
            self.assertEqual(driver.avd_dir(), self.d / "user" / "avd" / "test.avd")    # ANDROID_USER_HOME قبله
            os.environ["ANDROID_AVD_HOME"] = str(self.d / "avdhome")
            self.assertEqual(driver.avd_dir(), self.d / "avdhome" / "test.avd")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def _real_running(self):
        # الدالة الأصلية (fake_emulator_host بدّلها في هذا الاختبار)
        return type(self)._orig_running

    def test_clear_avd_locks(self):
        self.assertEqual(driver.clear_avd_locks(), [])        # مجلّد غائب
        self.avd.mkdir(parents=True)
        (self.avd / "a.lock").write_text("1")
        (self.avd / "b.lock").mkdir()
        (self.avd / "config.ini").write_text("x")
        self.assertEqual(driver.clear_avd_locks(), ["a.lock", "b.lock"])
        self.assertEqual(sorted(p.name for p in self.avd.iterdir()), ["config.ini"])

    def test_start_emulator_adds_wipe_data(self):
        import time as real_time
        import warnings
        cm = warnings.catch_warnings()
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        warnings.simplefilter("ignore", ResourceWarning)     # Popen المحاكي لا يُنتظر عمداً (يحصده subprocess لاحقاً)
        driver.time = self._time
        sdk = self.d / "sdk"
        (sdk / "emulator").mkdir(parents=True)
        exe = sdk / "emulator" / "emulator"
        exe.write_text('#!/bin/sh\necho "ARGS $*"\n')
        exe.chmod(0o755)
        saved = {k: os.environ.get(k) for k in ("ANDROID_SDK_ROOT", "ANDROID_HOME")}
        os.environ["ANDROID_SDK_ROOT"] = str(sdk)
        log = self.d / "start.log"
        try:
            for wipe in (False, True):
                self.assertTrue(self._start(log_path=str(log), wipe=wipe))   # الأصلية (setUp بدّلها)
                for _ in range(100):
                    if log.exists() and log.read_text().count("ARGS") == 1 + wipe:
                        break
                    real_time.sleep(0.05)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        args = [l for l in log.read_text().splitlines() if l.startswith("ARGS")]
        self.assertEqual(len(args), 2, log.read_text())
        self.assertNotIn("-wipe-data", args[0])
        self.assertTrue(args[1].endswith("-wipe-data"))
        self.assertIn("-avd test -no-window", args[1])
        self.assertEqual(log.read_text().count("=== "), 2)     # سطر فاصل قبل كل تشغيل

    def test_start_emulator_runs_even_if_log_unwritable(self):
        # قرص ممتلئ: كتابة الفاصل تفشل (/dev/full) أو لا يُفتح السجل أصلاً، والمحاكي يُشغَّل على أي حال؛ وبلا الأمر: None
        import time as real_time
        import warnings
        cm = warnings.catch_warnings()
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        warnings.simplefilter("ignore", ResourceWarning)     # Popen المحاكي لا يُنتظر عمداً (يحصده subprocess لاحقاً)
        driver.time = self._time
        sdk = self.d / "sdk"
        (sdk / "emulator").mkdir(parents=True)
        exe = sdk / "emulator" / "emulator"
        marker = self.d / "ran"
        exe.write_text('#!/bin/sh\necho x >> "%s"\n' % marker)
        exe.chmod(0o755)
        saved = {k: os.environ.get(k) for k in ("ANDROID_SDK_ROOT", "ANDROID_HOME", "PATH")}
        os.environ["ANDROID_SDK_ROOT"] = str(sdk)
        try:
            logs = [str(self.d / "no_dir" / "x.log")] + (["/dev/full"] if os.path.exists("/dev/full") else [])
            for i, lp in enumerate(logs, 1):
                self.assertTrue(self._start(log_path=lp))
                for _ in range(100):
                    if marker.exists() and marker.read_text().count("x") == i:
                        break
                    real_time.sleep(0.05)
                self.assertEqual(marker.read_text().count("x"), i, lp)
            os.environ["ANDROID_SDK_ROOT"] = str(self.d / "nosdk")
            os.environ.pop("ANDROID_HOME", None)
            os.environ["PATH"] = str(self.d / "empty")
            self.assertIsNone(self._start(log_path=str(self.d / "y.log")))
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


TestEmulatorRestartWipe._orig_running = staticmethod(driver.emulator_running)


# ============================================================== سياسة إعادات المحاكي بالتقدّم (التشغيل 15)
class TestEmuRestartPolicy(unittest.TestCase):
    """emu_restart_policy: يُعاد المحاكي ما دام البوت يتقدّم، ويتوقف بعد إعادات متتالية بلا تقدّم أو عند حدّ الأمان أو قرب النهاية."""

    CFG = {"emu_restarts": 40, "emu_fruitless_max": 3, "emu_progress_min": 15.0, "emu_restart_min_left": 6.0}

    def pol(self, restarts, fruitless, won, since, left=200.0):
        return driver.emu_restart_policy(restarts, fruitless, won, since, left, self.CFG)

    def test_first_failure_always_restarts(self):
        allow, f, why = self.pol(0, 0, 0, 1.0)
        self.assertTrue(allow)
        self.assertEqual(f, 0)
        self.assertIn("أول عطل", why)

    def test_win_since_last_restart_is_progress(self):
        allow, f, why = self.pol(7, 2, 1, 2.0)
        self.assertTrue(allow)
        self.assertEqual(f, 0)
        self.assertIn("1 مرحلة", why)

    def test_play_time_without_win_is_progress(self):
        allow, f, _ = self.pol(5, 2, 0, 15.0)
        self.assertTrue(allow)
        self.assertEqual(f, 0)
        allow, f, _ = self.pol(5, 2, 0, 14.9)
        self.assertFalse(allow)                  # الثالثة بلا تقدّم
        self.assertEqual(f, 3)

    def test_counts_consecutive_fruitless_restarts(self):
        seq = [self.pol(1, 0, 0, 1.0), self.pol(2, 1, 0, 1.0), self.pol(3, 2, 0, 1.0)]
        self.assertEqual([(a, f) for a, f, _ in seq], [(True, 1), (True, 2), (False, 3)])
        self.assertIn("بلا أي تقدّم", seq[-1][2])

    def test_progress_resets_the_fruitless_count(self):
        self.assertEqual(self.pol(3, 2, 2, 5.0)[:2], (True, 0))

    def test_absolute_safety_cap(self):
        allow, _f, why = self.pol(40, 0, 3, 30.0)
        self.assertFalse(allow)
        self.assertIn("حدّ الأمان", why)
        self.assertTrue(self.pol(39, 0, 3, 30.0)[0])

    def test_no_restart_near_the_end(self):
        allow, _f, why = self.pol(2, 0, 4, 20.0, left=5.9)
        self.assertFalse(allow)
        self.assertIn("بقي 5.9 دقيقة", why)
        self.assertTrue(self.pol(2, 0, 4, 20.0, left=6.0)[0])
        self.assertFalse(self.pol(0, 0, 0, 0.0, left=1.0)[0])   # ولا أول عطل قرب النهاية

    def test_run15_sequence_never_stops(self):
        # التشغيل 15: تسعة أعطال في 190 دقيقة وفوز بين أغلبها (14 مرحلة)؛ الحدّ الثابت 8 أوقف البوت وأمامه 110 دقائق
        gaps = [(11, 1), (8, 2), (8, 1), (10, 1), (10, 1), (30, 3), (68, 2), (25, 2), (7, 0)]
        restarts, fruitless, left = 0, 0, 300.0
        for since, won in gaps:
            left -= since
            allow, fruitless, _ = self.pol(restarts, fruitless, won, since, left)
            self.assertTrue(allow, (restarts, since, won))
            restarts += 1
        self.assertEqual(restarts, 9)


class TestEmuRestartProgress(unittest.TestCase):
    """recover_device على البوت كله: الإعادة تُحسب من التقدّم بين الأعطال (فوز أو وقت لعب) لا من عدد ثابت."""

    def setUp(self):
        self.clock = FakeClock()
        self._time = driver.time
        driver.time = self.clock
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = dict(driver.CFG)
        rng = random.Random(5)
        game = FakeGame([make_level(rng, 4, 2)], rng)
        dev = FlakyDevice(game, 0)
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        self.bot = driver.Bot(dev, driver.Vision(FakeVisionModule(game), out), out, 300, git=False)
        self.bot.log_host_oom = lambda: None
        self.restarted = 0

        self.budgets = []

        def fake_restart(budget=None):
            self.restarted += 1
            self.budgets.append(budget)
            self.clock.sleep(60)
            return True
        self.bot.restart_emulator = fake_restart

    def tearDown(self):
        driver.time = self._time
        driver.CFG.clear()
        driver.CFG.update(self.cfg)
        self.tmp.cleanup()

    def crash(self, after_min, won=0):
        """يلعب after_min دقيقة ويفوز بـ won مرحلة ثم يموت المحاكي: آخر لقطة ناجحة ثم دقيقتان من اللقطات الفاشلة وإعادة adb
        ومحاولة نسخة على محاكٍ ميت (لا تُحسب لعباً)، ثم قرار الحارس عند اللقطة الفاشلة الرابعة. يعيد: أُعيد المحاكي؟"""
        self.clock.sleep(after_min * 60)
        self.bot.last_ok_grab = self.clock.time()
        self.bot.levels_done += won
        self.clock.sleep(120)
        before = self.restarted
        self.bot.cap_fails = 4
        self.assertTrue(self.bot.recover_device())
        return self.restarted > before

    def log(self):
        return (Path(self.tmp.name) / "log.txt").read_text(encoding="utf-8")

    def test_keeps_restarting_while_winning(self):
        for _ in range(12):                      # أكثر من الحدّ الثابت القديم (8)
            self.assertTrue(self.crash(8, won=1), self.log()[-1500:])
            self.assertEqual(self.bot.cap_fails, 0)
        self.assertFalse(self.bot.stop)
        self.assertEqual(self.bot.emu_restarts, 12)
        self.assertIn("تقدّم منذ الإعادة السابقة: 1 مرحلة", self.log())

    def test_stops_after_three_restarts_without_progress(self):
        self.assertTrue(self.crash(10, won=2))
        self.assertTrue(self.crash(3, won=1))
        self.assertTrue(self.crash(2))           # بعد الإعادة 2 لا فوز: 1
        self.assertTrue(self.crash(2))           # 2
        self.assertFalse(self.crash(2))          # 3: توقف
        self.assertTrue(self.bot.stop)
        self.assertEqual(self.bot.emu_restarts, 4)
        self.assertIn("ولن يُعاد تشغيله: 3 إعادات متتالية للمحاكي بلا أي تقدّم", self.log())

    def test_long_play_without_win_still_counts(self):
        self.assertTrue(self.crash(1))
        for _ in range(5):
            self.assertTrue(self.crash(20))      # انتظار أرواح طويل بلا فوز: المحاكي سليم
        self.assertFalse(self.bot.stop)
        self.assertEqual(self.bot.emu_fruitless, 0)

    def test_win_between_fruitless_restarts_resets(self):
        self.assertTrue(self.crash(1))
        self.assertTrue(self.crash(1))
        self.assertTrue(self.crash(1))           # 2 بلا تقدّم
        self.assertTrue(self.crash(1, won=1))    # فوز: يعود الصفر
        self.assertEqual(self.bot.emu_fruitless, 0)
        self.assertTrue(self.crash(1))
        self.assertTrue(self.crash(1))
        self.assertFalse(self.bot.stop)

    def test_stops_within_remaining_time(self):
        self.assertTrue(self.crash(10, won=1))
        self.assertFalse(self.crash(300 - 10 - 1 - 4, won=3))   # بقي نحو 4 دقائق
        self.assertTrue(self.bot.stop)
        self.assertIn("لا فائدة من إعادة المحاكي", self.log())

    def test_safety_cap(self):
        driver.CFG["emu_restarts"] = 5
        for _ in range(5):
            self.assertTrue(self.crash(2, won=1))
        self.assertFalse(self.crash(2, won=1))
        self.assertTrue(self.bot.stop)
        self.assertIn("حدّ الأمان (5 إعادة", self.log())

    def test_adb_restart_still_comes_first(self):
        self.bot.cap_fails = 3
        self.assertTrue(self.bot.recover_device())
        self.assertEqual(self.bot.dev.adb_restarts, 1)
        self.assertEqual(self.restarted, 0)

    def test_counters_survive_hot_update(self):
        self.assertTrue(self.crash(2, won=1))
        self.assertTrue(self.crash(1))
        self.assertEqual((self.bot.emu_restarts, self.bot.emu_fruitless), (2, 1))
        saved = driver.STATE_FILE
        driver.STATE_FILE = Path(self.tmp.name) / "state.json"
        try:
            self.bot.save_counters()
            out = driver.Out(Path(self.tmp.name) / "b2", 10, quiet=True)
            b2 = driver.Bot(self.bot.dev, self.bot.vis, out, 100, git=False)
            b2.levels_done = self.bot.levels_done
            self.assertTrue(b2.load_counters())
        finally:
            driver.STATE_FILE = saved
        self.assertEqual((b2.emu_restarts, b2.emu_fruitless, b2.emu_restart_levels), (2, 1, 1))
        self.assertEqual(b2.emu_restart_at, self.bot.emu_restart_at)


# ============================================================== النسخة الاحتياطية أجزاءً (أقل من 50 ميغا لكل ملف)
def backup_bytes(n, seed=1, compressed=True):
    """أرشيف adb backup كامل حجمه نحو n بايت (أقل منه بـ 600 على الأكثر): الترويسة ثم tar (محتوى عشوائي بكتل 512 وكتلتا الأصفار
    في آخره)، مضغوطاً بـ zlib بلا ضغط فعلي (المستوى 0) فيبقى الحجم متوقَّعاً."""
    import zlib
    head = b"ANDROID BACKUP\n5\n%d\nnone\n" % (1 if compressed else 0)
    body = max(512, (n - len(head) - 1024 - 40) // 512 * 512)
    tar = random.Random(seed).randbytes(body) + bytes(1024)
    return head + (zlib.compress(tar, 0) if compressed else tar)


class TestBackupParts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.out = self.d / "out"
        self.out.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def blob(self, n, seed=1):
        body = random.Random(seed).randbytes(max(0, n - len(driver.BACKUP_MAGIC)))
        data = (driver.BACKUP_MAGIC + body)[:n]
        p = self.d / ("src_%d_%d.ab" % (n, seed))
        p.write_bytes(data)
        return p, data

    def names(self, d=None):
        return sorted(p.name for p in (d or self.out).iterdir())

    def test_round_trip_around_the_boundary(self):
        P = 1000
        for n in (20, P - 1, P, P + 1, 2 * P - 1, 2 * P, 2 * P + 1, 5 * P + 7):
            with self.subTest(n=n):
                src, data = self.blob(n, seed=n)
                man = driver.split_backup(src, self.out, P)
                sizes = [pt["size"] for pt in man["parts"]]
                self.assertEqual(len(sizes), -(-n // P))
                self.assertTrue(all(0 < s <= P for s in sizes), sizes)
                self.assertEqual(sum(sizes), n)
                self.assertEqual(self.names(), sorted([driver.backup_part_name(i) for i in range(len(sizes))]
                                                      + [driver.BACKUP_MANIFEST]))
                got, info = driver.join_backup(self.out, self.d / "joined.ab")
                self.assertIsNotNone(got, info)
                self.assertEqual(got.read_bytes(), data)
                self.assertIn("تحقّق الحجم والبصمة", info)

    def test_real_sizes_stay_below_github_warning(self):
        # 77.6 ميغا (التشغيل 15) بأجزاء backup_part_mb: جزءان تحت 50 ميغا (بلا كتابة 77 ميغا في الاختبار: الحساب فقط)
        P = int(driver.CFG["backup_part_mb"] * 1024 * 1024)
        self.assertLess(P, 50 * 1000 * 1000)
        self.assertEqual(-(-77599608 // P), 2)

    def test_stale_higher_parts_and_legacy_file_are_removed(self):
        src, _ = self.blob(3500)
        driver.split_backup(src, self.out, 1000)            # 4 أجزاء
        (self.out / driver.BACKUP_NAME).write_bytes(b"old single file")
        (self.out / "log.txt").write_text("keep")
        small, data = self.blob(1500, seed=2)
        man = driver.split_backup(small, self.out, 1000)    # جزءان: يُحذف 02 و03 والملف الواحد
        self.assertEqual(len(man["parts"]), 2)
        self.assertEqual(self.names(), [driver.BACKUP_MANIFEST, driver.backup_part_name(0),
                                        driver.backup_part_name(1), "log.txt"])
        self.assertEqual(driver.join_backup(self.out, self.d / "j.ab")[0].read_bytes(), data)

    def test_no_temp_files_left_and_meta_kept(self):
        src, _ = self.blob(2500)
        man = driver.split_backup(src, self.out, 1000, meta={"levels_done": 7, "size": -1})
        self.assertEqual(man["levels_done"], 7)
        self.assertEqual(man["size"], 2500)                 # meta لا يغطّي حقول التحقق
        self.assertFalse([n for n in self.names() if n.startswith(".")])
        on_disk = json.loads((self.out / driver.BACKUP_MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(on_disk, man)

    def test_empty_source_is_refused(self):
        p = self.d / "empty.ab"
        p.write_bytes(b"")
        with self.assertRaises(ValueError):
            driver.split_backup(p, self.out, 1000)
        self.assertEqual(self.names(), [])

    def test_legacy_single_file(self):
        _, data = self.blob(5000)
        (self.out / driver.BACKUP_NAME).write_bytes(data)
        got, info = driver.join_backup(self.out, self.d / "j.ab")
        self.assertEqual(got, self.out / driver.BACKUP_NAME)    # كما هو بلا نسخ
        self.assertIn("ملف واحد", info)

    def test_corrupted_part_is_rejected(self):
        src, _ = self.blob(2500)
        driver.split_backup(src, self.out, 1000)
        p1 = self.out / driver.backup_part_name(1)
        b = bytearray(p1.read_bytes())
        b[10] ^= 0xFF
        p1.write_bytes(bytes(b))
        got, info = driver.join_backup(self.out, self.d / "j.ab")
        self.assertIsNone(got)
        self.assertIn("part01", info)
        self.assertFalse((self.d / "j.ab").exists())
        self.assertFalse((self.d / ".j.ab.tmp").exists())

    def test_truncated_part_is_rejected(self):
        src, _ = self.blob(2500)
        driver.split_backup(src, self.out, 1000)
        p2 = self.out / driver.backup_part_name(2)
        p2.write_bytes(p2.read_bytes()[:-1])
        self.assertIsNone(driver.join_backup(self.out, self.d / "j.ab")[0])

    def test_missing_part_is_rejected(self):
        src, _ = self.blob(2500)
        driver.split_backup(src, self.out, 1000)
        (self.out / driver.backup_part_name(1)).unlink()
        got, info = driver.join_backup(self.out, self.d / "j.ab")
        self.assertIsNone(got)
        self.assertIn("غائب", info)

    def test_parts_without_manifest(self):
        src, data = self.blob(2500)
        driver.split_backup(src, self.out, 1000)
        (self.out / driver.BACKUP_MANIFEST).unlink()
        got, info = driver.join_backup(self.out, self.d / "j.ab")
        self.assertEqual(got.read_bytes(), data)
        self.assertIn("بلا ملف وصف", info)
        (self.out / driver.backup_part_name(1)).unlink()     # فجوة بلا ملف وصف
        got, info = driver.join_backup(self.out, self.d / "j.ab")
        self.assertIsNone(got)
        self.assertIn("فجوة", info)

    def test_broken_manifest_and_bad_header(self):
        src, _ = self.blob(2500)
        driver.split_backup(src, self.out, 1000)
        (self.out / driver.BACKUP_MANIFEST).write_text("{not json")
        self.assertIn("ملف الوصف تالف", driver.join_backup(self.out, self.d / "j.ab")[1])
        bad = self.d / "bad"
        bad.mkdir()
        p = self.d / "noheader.ab"
        p.write_bytes(b"x" * 3000)
        driver.split_backup(p, bad, 1000)
        got, info = driver.join_backup(bad, self.d / "j.ab")
        self.assertIsNone(got)
        self.assertIn("ترويسة", info)

    def test_nothing_there(self):
        self.assertEqual(driver.join_backup(self.out, self.d / "j.ab"), (None, "لا نسخة"))
        (self.out / driver.BACKUP_NAME).write_bytes(driver.BACKUP_MAGIC)   # أصغر من 2 ك.ب: ليس نسخة
        self.assertEqual(driver.join_backup(self.out, self.d / "j.ab"), (None, "لا نسخة"))

    def test_find_backup_order_and_fallbacks(self):
        save, out = self.d / "save", self.out
        save.mkdir()
        logs = []
        self.assertEqual(driver.find_backup((save, out), self.d / "j.ab", logs.append), (None, None))
        _, old = self.blob(4000, seed=9)
        (save / driver.BACKUP_NAME).write_bytes(old)              # حفظ قديم بملف واحد
        src, new = self.blob(4500, seed=10)
        driver.split_backup(src, out, 1000)
        got, info = driver.find_backup((save, out), self.d / "j.ab", logs.append)
        self.assertEqual(got.read_bytes(), old)                   # save/ أولاً
        self.assertTrue(info.startswith("save/"))
        # أجزاء جديدة في save/ (أرشفة) بجانب الملف القديم: الأجزاء أولاً
        driver.split_backup(src, save, 2000)
        (save / driver.BACKUP_NAME).write_bytes(old)              # split_backup حذفه؛ يعاد ليبقى بجانب الأجزاء
        got, info = driver.find_backup((save, out), self.d / "j.ab", logs.append)
        self.assertEqual(got.read_bytes(), new)
        self.assertIn("جزء", info)
        # جزء تالف في save/: الملف الواحد القديم بجانبه بديله، مع سطر السبب
        (save / driver.backup_part_name(0)).write_bytes(b"broken")
        got, info = driver.find_backup((save, out), self.d / "j.ab", logs.append)
        self.assertEqual(got.read_bytes(), old)
        self.assertIn("بدل الأجزاء التالفة", info)
        self.assertTrue(any("مرفوضة في save/" in ln for ln in logs))
        # بلا الملف القديم: out/ بعدها
        (save / driver.BACKUP_NAME).unlink()
        got, info = driver.find_backup((save, out), self.d / "j.ab", logs.append)
        self.assertEqual(got.read_bytes(), new)
        self.assertTrue(info.startswith("out/"))


class TestBackupInBot(unittest.TestCase):
    """البوت يحفظ النسخة أجزاءً في out/ ويستعيدها من save/ (مجموعةً ومتحقَّقاً منها)، والنشر يحذف الأجزاء الزائدة والملف الواحد."""

    def setUp(self):
        self.clock = FakeClock()
        self._time = driver.time
        driver.time = self.clock
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.cfg = dict(driver.CFG)
        rng = random.Random(2)
        game = FakeGame([make_level(rng, 4, 2)], rng)
        self.dev = FakeDevice(game)
        self.out = driver.Out(self.d / "out", 50, quiet=True)
        self.bot = driver.Bot(self.dev, driver.Vision(FakeVisionModule(game), self.out), self.out, 100, git=False)

    def tearDown(self):
        driver.time = self._time
        driver.CFG.clear()
        driver.CFG.update(self.cfg)
        self.tmp.cleanup()

    def ab(self, n, seed=1):
        p = self.d / "tmp_backup.ab"
        p.write_bytes(backup_bytes(n, seed))
        return p

    def test_store_backup_writes_parts_and_drops_single_file(self):
        driver.CFG["backup_part_mb"] = 0.01                  # 10485 بايت لكل جزء
        (self.out.dir / driver.BACKUP_NAME).write_bytes(b"legacy")
        self.bot.levels_done = 3
        self.assertTrue(self.bot.store_backup(str(self.ab(30000))))
        names = sorted(p.name for p in self.out.dir.iterdir())
        self.assertNotIn(driver.BACKUP_NAME, names)
        self.assertEqual([n for n in names if ".part" in n], [driver.backup_part_name(i) for i in range(3)])
        man = json.loads((self.out.dir / driver.BACKUP_MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(man["levels_done"], 3)
        self.assertEqual(self.bot.backup_levels, 3)
        log = (self.out.dir / "log.txt").read_text(encoding="utf-8")
        self.assertIn("في 3 جزء", log)

    def test_restore_mid_run_prefers_this_runs_backup(self):
        # بعد نسخة في هذا التشغيل (محاكٍ أُعيد ففقد اللعبة): out/ أحدث من save/ (حفظ بداية التشغيل)
        root = self.d / "repo" / "research" / "emu"
        (root / "bot").mkdir(parents=True)
        old, new = self.ab(12000, seed=7), None
        driver.split_backup(old, root / "save", 10000)
        old_bytes = old.read_bytes()
        restored = []

        def fake_popen(cmd, **k):
            restored.append(Path(cmd[-1]).read_bytes())

            class P:
                def wait(self, timeout=None):
                    return 0
            return P()
        saved = (driver.HERE, driver.subprocess.Popen)
        driver.HERE = root / "bot"
        driver.subprocess.Popen = fake_popen
        self.bot.confirm_backup_dialog = lambda tries=25: True
        self.dev._cmd = lambda args: ["adb"] + list(args)
        out2 = driver.Out(root / "out", 50, quiet=True)
        self.bot.out = out2
        try:
            self.assertTrue(self.bot.restore_app())            # بداية التشغيل: save/
            new = self.ab(14000, seed=8)
            self.assertTrue(self.bot.store_backup(str(new)))
            self.assertTrue(self.bot.restore_app())            # بعد نسخة هذا التشغيل: out/
        finally:
            driver.HERE, driver.subprocess.Popen = saved
        self.assertEqual(restored, [old_bytes, new.read_bytes()])

    def test_restore_timeout_is_not_a_restore(self):
        # adb restore قُتل بعد مهلته (300 ث) رغم لمس التأكيد: لا تُعدّ استعادة (restore_after_install يعيدها ثم يمنع النسخ)
        root = self.d / "repo" / "research" / "emu"
        (root / "bot").mkdir(parents=True)
        driver.split_backup(self.ab(12000, seed=3), root / "save", 10000)
        killed = []

        def fake_popen(cmd, **k):
            class P:
                def wait(self, timeout=None):
                    raise driver.subprocess.TimeoutExpired(cmd, timeout)

                def kill(self):
                    killed.append(1)
            return P()
        saved = (driver.HERE, driver.subprocess.Popen)
        driver.HERE = root / "bot"
        driver.subprocess.Popen = fake_popen
        self.bot.confirm_backup_dialog = lambda tries=25: True
        self.dev._cmd = lambda args: ["adb"] + list(args)
        try:
            self.assertFalse(self.bot.restore_app())
            self.assertTrue(self.bot.restore_had_backup)
            self.assertFalse(self.bot.restore_after_install(self.clock.time() + 3600))
        finally:
            driver.HERE, driver.subprocess.Popen = saved
        self.assertEqual(len(killed), 3)                     # الأولى، ثم الاستعادة ومحاولتها الثانية
        self.assertTrue(self.bot.backup_hold)
        log = (self.out.dir / "log.txt").read_text(encoding="utf-8")
        self.assertIn("انتهت مهلة adb restore بعد التأكيد (لم تكتمل)", log)

    def test_store_backup_refuses_tiny_or_huge(self):
        p = self.d / "tiny.ab"
        p.write_bytes(b"x" * 100)
        self.assertFalse(self.bot.store_backup(str(p)))
        driver.CFG["backup_max_mb"] = 0.01
        self.assertFalse(self.bot.store_backup(str(self.ab(30000))))
        self.assertFalse([p for p in self.out.dir.iterdir() if driver.is_backup_file(p.name)])

    def test_restore_joins_parts_from_save(self):
        root = self.d / "repo" / "research" / "emu"
        (root / "bot").mkdir(parents=True)
        src = self.ab(25000, seed=4)
        driver.split_backup(src, root / "save", 10000)
        restored = []

        def fake_popen(cmd, **k):
            restored.append(Path(cmd[-1]).read_bytes())

            class P:
                def wait(self, timeout=None):
                    return 0
            return P()
        saved = (driver.HERE, driver.subprocess.Popen)
        driver.HERE = root / "bot"
        driver.subprocess.Popen = fake_popen
        self.bot.confirm_backup_dialog = lambda tries=25: True
        self.dev._cmd = lambda args: ["adb"] + list(args)
        try:
            self.assertTrue(self.bot.restore_app())
        finally:
            driver.HERE, driver.subprocess.Popen = saved
        self.assertEqual(restored, [src.read_bytes()])
        log = (self.out.dir / "log.txt").read_text(encoding="utf-8")
        self.assertIn("استعادة بيانات اللعبة من save/: 3 جزء", log)

    def test_sync_out_mirrors_backup_deletions_only(self):
        pub = self.d / "pub"
        saved = driver.PUB_DIR
        driver.PUB_DIR = pub
        try:
            dst = pub / driver.OUT_REL
            dst.mkdir(parents=True)
            # شجرة النشر فيها نسخة أكبر (4 أجزاء) والملف الواحد القديم، وملف حذفه صاحب المشروع محلياً لا يُمسّ
            for n in [driver.BACKUP_NAME, driver.BACKUP_MANIFEST] + [driver.backup_part_name(i) for i in range(4)]:
                (dst / n).write_bytes(b"old")
            (dst / "other.jpg").write_bytes(b"keep")
            driver.split_backup(self.ab(15000), self.out.dir, 10000)   # جزءان محلياً
            self.out.log("سطر")
            self.bot._sync_out()
            names = sorted(p.name for p in dst.iterdir())
            self.assertEqual(names, sorted([driver.BACKUP_MANIFEST, driver.backup_part_name(0),
                                            driver.backup_part_name(1), "log.txt", "other.jpg"]))
            got, _ = driver.join_backup(dst, self.d / "j.ab")
            self.assertIsNotNone(got)
        finally:
            driver.PUB_DIR = saved


# ============================================================== ذاكرة كل بداية والأبواب (التشغيل 12، المرحلة 124)
L124_START = [
    {"x": 236, "y": 634, "cap": 10, "layers": ["cyan", "cyan"]},
    {"x": 98, "y": 743, "cap": 4, "layers": ["purple", "orange", "darkgreen", "plum"]},
    {"x": 168, "y": 743, "cap": 4, "layers": ["green", "cyan", "green", "green"]},
    {"x": 304, "y": 743, "cap": 4, "layers": ["plum", "plum", "cyan", "cyan"], "keys": [0]},
    {"x": 372, "y": 743, "cap": 4, "layers": ["cyan", "cyan", "darkgreen", "plum"], "keys": [0]}]
# من سجل التشغيل 12 (23:03:39 و23:04:00): البداية «السماوية» بعد الباب الأول ثم الثاني
L124_DOOR1 = [
    {"x": 98, "y": 538, "cap": 4, "layers": ["darkgreen", "?", "?", "lavender"], "keys": [0]},
    {"x": 167, "y": 538, "cap": 4, "layers": ["yellow", "purple", "brown", "darkgreen"], "keys": [1]},
    {"x": 236, "y": 634, "cap": 10, "layers": ["cyan", "cyan", "cyan", "cyan"]},
    {"x": 98, "y": 743, "cap": 4, "layers": ["purple", "orange", "darkgreen", "plum"]},
    {"x": 168, "y": 743, "cap": 4, "layers": ["green", "cyan", "green", "green"]},
    {"x": 304, "y": 743, "cap": 4, "layers": ["plum", "plum"]},
    {"x": 372, "y": 743, "cap": 4, "layers": ["cyan", "cyan", "darkgreen", "plum"], "keys": [0]}]
L124_DOOR2 = [
    {"x": 98, "y": 332, "cap": 4, "layers": ["?", "brown", "?", "lavender"]},
    {"x": 168, "y": 332, "cap": 4, "layers": ["lavender", "orange", "cyan", "cyan"]},
    {"x": 98, "y": 538, "cap": 4, "layers": ["darkgreen", "?", "?", "lavender"], "keys": [0]},
    {"x": 167, "y": 538, "cap": 4, "layers": ["yellow", "purple", "brown", "darkgreen"], "keys": [1]},
    {"x": 236, "y": 634, "cap": 10, "layers": ["cyan", "cyan", "cyan", "cyan"]},
    {"x": 98, "y": 743, "cap": 4, "layers": ["purple", "orange", "darkgreen", "darkgreen"]},
    {"x": 168, "y": 743, "cap": 4, "layers": ["green", "cyan", "green", "green"]},
    {"x": 304, "y": 743, "cap": 4, "layers": ["plum", "plum", "plum", "plum"]},
    {"x": 372, "y": 743, "cap": 4, "layers": ["cyan", "cyan"]}]


def _cp(tubes):
    return {"tubes": [dict(t, layers=list(t["layers"])) for t in tubes]}


class TestDoorMemory(unittest.TestCase):
    def test_door_record_from_l124_log(self):
        """الباب الأول: الحركة (3، 0) تصبّ السماوي فيتحرّر مفتاح (304،743 طبقة 0) وتظهر قارورتان؛ والثاني من (372،743 طبقة 0).
        بعد انفتاح الأول تتغيّر الفهارس (372 صارت 6) فيُطابق الباب الثاني بالموضع."""
        start = _cp(L124_START)
        ref1 = solver.apply_move(start, 3, 0)
        st1 = _cp(L124_DOOR1)
        mp1 = driver.door_map(ref1, st1)
        self.assertIsNotNone(mp1)
        keys1, tubes1 = driver.door_record(ref1, st1, mp1)
        self.assertEqual(keys1, [[304, 743, 0]])
        self.assertEqual([(t["x"], t["y"], t["layers"], t.get("keys")) for t in tubes1],
                         [(98, 538, ["darkgreen", "?", "?", "lavender"], [0]),
                          (167, 538, ["yellow", "purple", "brown", "darkgreen"], [1])])
        # قبل الحركة التي حرّرت المفتاح الثاني: (6، 3) تصبّ الأخضر الداكن من (372،743)
        pre2 = _cp(L124_DOOR1)
        pre2["tubes"][3]["layers"] = ["purple", "orange", "darkgreen"]
        pre2["tubes"][5]["layers"] = ["plum"] * 4
        pre2["tubes"][6]["layers"] = ["cyan", "cyan", "darkgreen"]
        ref2 = solver.apply_move(pre2, 6, 3)
        st2 = _cp(L124_DOOR2)
        mp2 = driver.door_map(ref2, st2)
        keys2, tubes2 = driver.door_record(ref2, st2, mp2)
        self.assertEqual(keys2, [[372, 743, 0]])
        self.assertEqual([(t["x"], t["y"]) for t in tubes2], [(98, 332), (168, 332)])
        doors = []
        self.assertEqual(driver.merge_door(doors, keys1, tubes1), "new")
        self.assertEqual(driver.merge_door(doors, keys2, tubes2), "new")
        self.assertEqual(driver.merge_door(doors, [[304, 744, 0]], tubes1), "known")     # بكسل فرق في القراءة
        self.assertEqual(len(doors), 2)
        # محاولة جديدة بالبداية نفسها: البابان بفهارس البداية
        kd = driver.known_doors(_cp(L124_START), doors)
        self.assertEqual([d["keys"] for d in kd], [[(3, 0)], [(4, 0)]])
        # بعد انفتاح الأول: مفتاحه طار، والثاني صار على القارورة 6
        kd = driver.known_doors(_cp(L124_DOOR1), doors)
        self.assertEqual([d["keys"] for d in kd], [[(6, 0)]])
        self.assertEqual([t["y"] for t in kd[0]["tubes"]], [332, 332])
        # بعد الاثنين: لا باب معروف مغلق
        self.assertEqual(driver.known_doors(_cp(L124_DOOR2), doors), [])
        # والحلّال يستقبلها، وفيها «?» ومفاتيح لا يُعرف بابها: المنطق المعتاد كما هو (والحركة الأولى قانونية بفهارس الحالة)
        info = {}
        mv = solver.plan(_cp(L124_START), info=info, doors=driver.known_doors(_cp(L124_START), doors))
        self.assertEqual((info["doors_res"], info["doors"]), ("hidden", 2))
        self.assertIn(mv[0], solver.legal_moves(_cp(L124_START)))

    def test_no_record_without_freed_key(self):
        """قارورة إضافية فارغة (أداة أو «Play On») ليست باباً: لا مفتاح تحرّر ولا قوارير بطبقات."""
        a = _cp(L124_DOOR2)
        b = _cp(L124_DOOR2 + [{"x": 440, "y": 743, "cap": 4, "layers": []}])
        self.assertIsNone(driver.door_record(a, b, driver.door_map(a, b)))

    def test_nested_door_by_position(self):
        """مفتاح داخل قارورة باب مغلق معروف يفتح باباً آخر معروفاً: يُطابق بقوارير الباب الأول في القائمة الممتدّة."""
        st = {"tubes": [{"x": 100, "y": 700, "cap": 4, "layers": ["blue", "red"], "keys": [0]},
                        {"x": 170, "y": 700, "cap": 4, "layers": ["red", "red", "red"]},
                        {"x": 240, "y": 700, "cap": 4, "layers": []}]}
        doors = [{"keys": [[100, 700, 0]], "tubes": [{"x": 100, "y": 500, "cap": 4,
                                                      "layers": ["yellow", "blue", "blue", "blue"], "keys": [0]}]},
                 {"keys": [[100, 500, 0]], "tubes": [{"x": 170, "y": 500, "cap": 4, "layers": ["yellow"] * 3}]}]
        kd = driver.known_doors(st, list(reversed(doors)))       # الترتيب في الذاكرة لا يهمّ
        self.assertEqual([d["keys"] for d in kd], [[(0, 0)], [(3, 0)]])
        info = {}
        mv = solver.plan(st, info=info, doors=kd)
        self.assertEqual(info["mode"], "doors-full")
        self.assertEqual(mv, [(0, 1)])                          # تصبّ الأحمر فيتحرّر المفتاح: ينفتح الباب الأول
        self.assertEqual(sum(1 for _m, o in solver._DOOR_LINE if o), 2)

    def test_learn_and_fill_hidden_layers(self):
        """طبقة مخفية انكشفت في قارورة باب تُكتب في ذاكرته، وفي المحاولة التالية تدخل ذاكرة الطبقات حين ينفتح الباب."""
        doors = []
        driver.merge_door(doors, [[304, 743, 0]], [dict(t, layers=list(t["layers"])) for t in L124_DOOR1[:2]])
        st = _cp(L124_DOOR2)
        self.assertEqual(driver.learn_door_layers(doors, st, [(2, 2, "brown"), (0, 2, "green")]), 1)
        self.assertEqual(doors[0]["tubes"][0]["layers"], ["darkgreen", "?", "brown", "lavender"])
        self.assertEqual(driver.learn_door_layers(doors, st, [(2, 2, "brown")]), 0)      # معروفة الآن
        mem = {}
        self.assertEqual(driver.fill_from_doors(doors, _cp(L124_DOOR1), [0, 1], mem), 1)
        self.assertEqual(mem, {(0, 2): "brown"})


class TestSignatureStrategy(DriverCase):
    def lv_for(self, bot, n=124, tubes=L124_START):
        st = _cp(tubes)
        lv = driver.LevelCtx(n, st, 0.0)
        rec = bot.sig_rec(lv.sig_id, n)
        lv.sig_attempt = rec["fails"]
        bot.lv = lv
        return lv, rec

    def test_alternation_per_signature(self):
        """keys_first بالتناوب بعدد محاولات البداية نفسها لا بعدد «Give Up» في المرحلة؛ والأولى لكل بداية كما كانت."""
        bot, _, _ = self.make()
        bot.level_fails[124] = 5                        # الصيغة القديمة: 5 فردي ≥ 3 → بلا «المفاتيح أولاً»
        lv, rec = self.lv_for(bot)
        pp = bot.plan_params(lv, lv.start_state)
        self.assertEqual((pp["keys_first"], pp["seed"], pp["vary"], pp["doors"]), (True, None, 0, None))
        self.assertIs(pp["avoid"], lv.visited)
        seeds = set()
        for att, kf in ((1, False), (2, True), (3, False)):
            rec["fails"] = att
            lv2, _ = self.lv_for(bot)
            pp = bot.plan_params(lv2, lv2.start_state)
            self.assertEqual((pp["keys_first"], pp["vary"]), (kf, att))
            seeds.add(pp["seed"])
        self.assertEqual(len(seeds), 3)
        # بداية أخرى للمرحلة نفسها: محاولتها الأولى كما كانت
        other = [dict(t) for t in L124_START]
        other[0] = dict(other[0], layers=["purple", "purple"])
        lv3, rec3 = self.lv_for(bot, tubes=other)
        self.assertNotEqual(lv3.sig_id, lv.sig_id)
        self.assertEqual(rec3["fails"], 0)
        self.assertTrue(bot.plan_params(lv3, lv3.start_state)["keys_first"])

    def test_dead_end_remembered_and_avoided(self):
        """«Give Up»: آخر الحالات قبل الانسداد تُحفظ للبداية، وتصل إلى الحلّال (avoid) في محاولتها التالية."""
        bot, _, _ = self.make()
        lv, rec = self.lv_for(bot)
        cur = lv.start_state
        for mv in [(3, 0), (1, 3), (4, 3)]:
            cur = solver.apply_move(cur, *mv)
            k = solver.state_key(cur)
            lv.history.append((k, k))
        for i in range(6):                              # حالات وهمية حتى يتجاوز الذيل خمس حالات
            lv.history.append(((("x%d" % i,),), (("y%d" % i,),)))
        bot.note_dead_end(lv)
        self.assertEqual(rec["fails"], 1)
        self.assertEqual(len(rec["dead"]), 2 * driver.DEAD_TAIL)
        bot.note_dead_end(lv)                           # النافذة قُرئت مرتين: تُحسب مرة في المحاولة
        lv2, _ = self.lv_for(bot)
        self.assertEqual(lv2.sig_attempt, 1)
        pp = bot.plan_params(lv2, lv2.start_state)
        self.assertTrue(set(rec["dead"]) <= pp["avoid"])
        self.assertFalse(pp["keys_first"])
        self.assertIn("طريق مسدود محفوظ", self.log())
        # الحدّ: لا يزيد الطريق المسدود على SIG_DEAD_MAX
        for r in range(20):
            lv.dead_noted = False
            lv.history = [(((("z%d_%d" % (r, i)),),), ((("w%d_%d" % (r, i)),),)) for i in range(5)]
            bot.note_dead_end(lv)
        self.assertEqual(len(rec["dead"]), driver.SIG_DEAD_MAX)

    def test_dead_states_change_the_plan(self):
        """الحلّال لا يمرّ بحالة من الطريق المسدود ما دام له بديل."""
        st = {"tubes": [{"x": 0, "y": 0, "cap": 4, "layers": l} for l in
                        (["red", "blue"], ["blue", "red"], ["red", "blue"], ["blue", "red"], [], [])]}
        mv = solver.plan(st)
        first = solver.state_key(solver.apply_move(st, *mv[0]))
        mv2 = solver.plan(st, avoid={first})
        self.assertTrue(mv2)
        self.assertNotEqual(solver.state_key(solver.apply_move(st, *mv2[0])), first)
        cur = st
        for m in mv2:
            cur = solver.apply_move(cur, *m)
        self.assertTrue(solver.is_solved(cur))

    def test_sig_cap(self):
        bot, _, _ = self.make()
        for i in range(driver.SIG_MAX + 5):
            self.clock.sleep(1)
            bot.sig_rec("1:%04d" % i, 1)
        self.assertEqual(len(bot.sig_data), driver.SIG_MAX)
        self.assertNotIn("1:0000", bot.sig_data)          # الأقدم استعمالاً حُذف
        self.assertIn("1:%04d" % (driver.SIG_MAX + 4), bot.sig_data)

    def test_sigs_survive_hot_update_and_old_json_loads(self):
        """سجلّات البدايات تُحفظ مع level_fails قبل التحديث الساخن وتُقرأ بعده؛ والملف القديم بلا "sigs" أو بسجلّ تالف يُقرأ."""
        old_sf = driver.STATE_FILE
        driver.STATE_FILE = Path(self.tmp.name) / "bot_state.json"
        try:
            bot, _, _ = self.make()
            lv, rec = self.lv_for(bot)
            bot.memory_by_sig[lv.start_sig] = bot.sig_mem[lv.sig_id] = {(1, 2): "brown"}
            # البداية لا تُحفظ، والحالتان التاليتان مفتاحان تالفان يسقطان عند القراءة: الحالة العالقة بعد ثلاث حركات وحدها
            cur = lv.start_state
            lv.history = [(lv.start_sig, lv.start_sig)]
            for mv in [(3, 0), (1, 3), (4, 3)]:
                cur = solver.apply_move(cur, *mv)
                k = solver.state_key(cur)
                lv.history.append((k, k))
            lv.history[1:3] = [(("a",), ("a",)), (("b",), ("b",))]
            bot.note_dead_end(lv)
            driver.merge_door(rec["doors"], [[304, 743, 0]], [dict(t, layers=list(t["layers"])) for t in L124_DOOR1[:2]])
            bot.level_fails[124] = 1
            bot.save_counters()
            bot2, _, _ = self.make()
            self.assertTrue(bot2.load_counters())
            r2 = bot2.sig_data[lv.sig_id]
            self.assertEqual((r2["n"], r2["fails"]), (124, 1))
            self.assertEqual(r2["dead"], [k])                 # صفوف كما يعيدها state_key
            self.assertEqual(r2["doors"][0]["keys"], [[304, 743, 0]])
            self.assertEqual(r2["mem"], [[1, 2, "brown"]])
            self.assertIn("ذاكرة 1 بداية", self.log())
            # البداية نفسها بعد التحديث: محاولتها الثانية وذاكرة طبقاتها
            fr = driver.Frame(Image.new("RGB", (473, 1000)))
            bot2.new_level(fr, _cp(L124_START), n=124)
            self.assertEqual(bot2.lv.sig_attempt, 1)
            self.assertEqual(bot2.lv.memory, {(1, 2): "brown"})
            self.assertIn("البداية نفسها للمرة 2", self.log())
            # ملف قديم بلا الحقول الجديدة
            driver.STATE_FILE.write_text(json.dumps({"t": self.clock.time(), "level_fails": {"124": 3},
                                                     "lives_until": 0, "refills": 0, "coins": 70}), encoding="utf-8")
            bot3, _, _ = self.make()
            self.assertTrue(bot3.load_counters())
            self.assertEqual((dict(bot3.level_fails), bot3.sig_data), ({124: 3}, {}))
            # سجلّات تالفة تُهمل وحدها
            driver.STATE_FILE.write_text(json.dumps({"t": self.clock.time(), "level_fails": {}, "sigs": {
                "a": "bad", "b": {"n": "x"}, "c": {"n": 7, "fails": "2", "dead": [[[4, ["red"]]], "bad"],
                                                    "doors": [{"keys": "bad"}, {"keys": [[1, 2, 0]], "tubes": [
                                                        {"x": 1, "y": 2, "cap": 4, "layers": ["red"]}]}],
                                                    "mem": [[0, 1, "red"], ["bad"]]}}}), encoding="utf-8")
            bot4, _, _ = self.make()
            self.assertTrue(bot4.load_counters())
            self.assertEqual(list(bot4.sig_data), ["c"])
            c = bot4.sig_data["c"]
            self.assertEqual((c["fails"], c["dead"], len(c["doors"]), c["mem"]), (2, [((4, ("red",)),)], 1, [[0, 1, "red"]]))
        finally:
            driver.STATE_FILE = old_sf


# ============================================================== ذاكرة الطريق المسدود لا تُبقي البوت بلا خطة (التشغيل 17، المرحلة 154)
# من سجل التشغيل 17 (04:04:10 و04:17:52 و05:36:41): بداية «سماوية» صعبة بثلاثة أبواب، ومفتاح أزرق في قاع القارورة 0 لا تقرؤه
# الرؤية (أزرق على سماوي)؛ الظاهر وحده لا يُحلّ (ألوانه خلف الأبواب)
L154_X = [64, 133, 201, 270, 338, 407]
L154_CYAN = [["cyan", "cyan", "cyan", "green"], ["cyan", "purple", "purple", "red"], [], [],
             ["lavender", "lavender", "pink", "red"], ["brown", "plum", "yellow", "mint"]]
# 04:16:33 و06:09:10: بداية أخرى للمرحلة نفسها بمفتاح مقروء
L154_RED = [["red", "darkgreen", "red", "darkgreen"], ["red", "red", "yellow", "pink"], [], [],
            ["cyan", "blue", "darkgreen", "green"], ["pink", "purple", "yellow", "darkgreen"]]


def _l154(layers, keys=None):
    st = {"tubes": [{"x": L154_X[k], "y": 743, "cap": 4, "layers": list(l)} for k, l in enumerate(layers)]}
    for k, p in (keys or {}).items():
        st["tubes"][k]["keys"] = [p]
    return st


class TestDeadEndNeverBlocksPlan(DriverCase):
    def lv_for(self, bot, st, n=154, fails=0):
        lv = driver.LevelCtx(n, st, 0.0)
        rec = bot.sig_rec(lv.sig_id, n)
        rec["fails"] = fails
        lv.sig_attempt = rec["fails"]
        bot.lv = lv
        return lv, rec

    def dead_line(self, s0):
        """محاولة 04:17:52: خطة progress بحركتين (الأحمر إلى فارغة)، ثم «لا خطة» وحركة عشوائية (5، 3) و«No Available Moves»."""
        info = {}
        mv = solver.plan(s0, info=info)
        self.assertEqual((mv, info["mode"]), ([(1, 2), (4, 2)], "progress"))
        states = [s0]
        for m in mv + [(5, 3)]:
            states.append(solver.apply_move(states[-1], *m))
        self.assertEqual(solver.legal_moves(states[-1]), [])
        return states

    def start_plan(self, bot, lv):
        stp = driver.with_memory(lv.start_state, lv.memory)
        key = solver.state_key(stp)
        lv.visited.add(key)
        lv.history.append((key, key, driver.compact_tubes(stp)))
        bot.plan_level(lv, stp, key)
        return stp

    def test_reproduce_run17_empty_plan(self):
        """السبب كما في التشغيل 17: البداية وأول حالتين في avoid تقصّ كل حركة أولى، والحلّال بلا detour يعيد «لا حركة»."""
        s0 = _l154(L154_CYAN)
        dead = {solver.state_key(s) for s in self.dead_line(s0)}
        for kf in (True, False):
            info = {}
            self.assertEqual(solver.plan(s0, avoid=dead, keys_first=kf, info=info), [])
            self.assertEqual(info["mode"], "progress-none")

    def test_short_attempt_changes_the_opening(self):
        """محاولة انسدّت بعد 3 حركات (S0..S3): تُحفظ S1 وS2 وS3 ولا تُحفظ البداية؛ والمحاولتان التاليتان لا تعيدان الافتتاح
        الخاسر [(1, 2), (4, 2)] بل تبدآن بالأخضر إلى فارغة (يحرّر المفتاح الذي لا تقرؤه الرؤية)."""
        bot, _, _ = self.make()
        s0 = _l154(L154_CYAN)
        lv, rec = self.lv_for(bot, s0, fails=0)
        states = self.dead_line(s0)
        lv.history = [(solver.state_key(s), solver.state_key(s), driver.compact_tubes(s)) for s in states]
        bot.note_dead_end(lv)
        self.assertEqual(rec["dead"], [solver.state_key(s) for s in states[1:]])
        self.assertEqual(len(rec["dead_st"]), 3)
        self.assertIn("الحالة العالقة: آخر لوحة مقروءة", self.log())
        for att in (1, 2):
            lv2, _ = self.lv_for(bot, _l154(L154_CYAN), fails=att)
            self.start_plan(bot, lv2)
            self.assertTrue(lv2.plan, self.log())
            self.assertNotEqual(lv2.plan[:2], [(1, 2), (4, 2)])
            self.assertEqual(lv2.plan[0], (0, 2))
        # محاولة قصيرة جداً (حركة واحدة ثم الانسداد): الحالة العالقة تُحفظ، والبداية لا
        lv.dead_noted = False
        s1 = solver.apply_move(s0, 0, 2)
        lv.history = [(lv.start_sig, lv.start_sig, None), (solver.state_key(s1), solver.state_key(s1), None)]
        bot.note_dead_end(lv)
        self.assertIn(solver.state_key(s1), rec["dead"])
        self.assertNotIn(lv.start_sig, rec["dead"])

    def test_real_run17_history_records_unread_stuck_state(self):
        """توقيت التشغيل 17 (04:18:21، «3 حالة جديدة»): اللوحة بعد (5، 3) لم تُقرأ قبل النافذة (lv.pending)، فالتاريخ S0 وS1 وS2
        وحدها؛ الحالة العالقة الحقيقية S3 تُحفظ من lv.pending، والمحاولة التالية تبدأ بـ (0، 2)."""
        bot, _, _ = self.make()
        s0 = _l154(L154_CYAN)
        lv, rec = self.lv_for(bot, s0, fails=0)
        states = self.dead_line(s0)
        lv.history = [(solver.state_key(s), solver.state_key(s), driver.compact_tubes(s)) for s in states[:3]]
        lv.pending = (states[2], (5, 3), states[3], 0)
        bot.note_dead_end(lv)
        self.assertEqual(rec["dead"], [solver.state_key(s) for s in states[1:]])
        self.assertEqual(rec["dead_st"][-1], driver.compact_tubes(states[3]))
        self.assertIn("الحالة العالقة: الحالة بعد الحركة الأخيرة (5, 3) (لم تُقرأ)", self.log())
        lv2, _ = self.lv_for(bot, _l154(L154_CYAN), fails=rec["fails"])
        self.start_plan(bot, lv2)
        self.assertEqual(lv2.plan[:1], [(0, 2)], self.log())

    def test_random_move_avoids_dead_states(self):
        """الحركة العشوائية لا تذهب إلى حالة في الطريق المسدود المحفوظ ما وُجدت غيرها (S2: كل ابن عدا (2، 3) مسدود)."""
        bot, _, _ = self.make()
        s0 = _l154(L154_CYAN)
        lv, rec = self.lv_for(bot, s0, fails=1)
        s2 = self.dead_line(s0)[2]
        rec["dead"] = [solver.state_key(solver.apply_move(s2, i, j)) for i, j in solver.legal_moves(s2) if (i, j) != (2, 3)]
        bot.do_move = lambda st, i, j: (i, j)
        for _ in range(12):
            self.assertEqual(bot.random_move(s2), (2, 3))
        rec["dead"] = [solver.state_key(solver.apply_move(s2, i, j)) for i, j in solver.legal_moves(s2)]
        self.assertIn(bot.random_move(s2), solver.legal_moves(s2))   # كلها مسدودة: أي حركة قانونية

    def test_unrelated_dead_memory_keeps_stuck_flow(self):
        """ذاكرة طريق مسدود لا دخل لها بغياب الخطة (حالات لا تُبلغ، أو حالة مقصوصة بلا تحسّن بعدها، أو لوحة بلا حركة): لا طريق
        بديل ولا إعادة تخطيط، والخطة الفارغة تذهب إلى stuck() كما في المحاولة الأولى."""
        s0 = _l154(L154_CYAN)
        states = self.dead_line(s0)
        s2, s3 = states[2], states[3]
        cases = ((s2, [solver.state_key(_l154(L154_RED))]),                       # لا تُبلغ
                 (s2, [solver.state_key(solver.apply_move(s2, 5, 3))]),           # تُقصّ ولا تحسّن بدونها
                 (s3, [solver.state_key(s) for s in states[1:3]]))                 # لا حركة قانونية
        for cur, dead in cases:
            bot, _, _ = self.make()
            lv, rec = self.lv_for(bot, s0, fails=1)
            rec["dead"] = list(dead)
            key = solver.state_key(cur)
            lv.visited.add(key)
            bot.plan_level(lv, cur, key)
            self.assertEqual(lv.plan, [], self.log())
            self.assertNotIn("طريق بديل", self.log())
            self.assertNotIn("تخطيط من جديد بدونها", self.log())
            self.assertIn("(progress-none", self.log())

    def test_poisoned_record_from_run17_plans_a_detour(self):
        """05:36:41: سجلّ قديم فيه البداية وأول حالتين والعالقة، والمحاولة الثالثة («المفاتيح أولاً»): الخطة لا
        تُترك فارغة؛ طريق بديل بعيداً عن الطريق المسدود: الأخضر إلى فارغة (يحرّر المفتاح الذي لا تقرؤه الرؤية)."""
        for fails in (2, 1):
            bot, _, _ = self.make()
            s0 = _l154(L154_CYAN)
            lv, rec = self.lv_for(bot, s0, fails=fails)
            states = self.dead_line(s0)
            rec["dead"] = [solver.state_key(s) for s in states]
            stp = self.start_plan(bot, lv)
            self.assertTrue(lv.plan, self.log())
            self.assertEqual(lv.plan[0], (0, 2))
            first = solver.state_key(solver.apply_move(stp, *lv.plan[0]))
            self.assertNotIn(first, set(rec["dead"]))
            self.assertIn("طريق بديل بعيداً عنه", self.log())
            self.assertNotIn("لا حركة مفيدة", self.log())

    def test_known_key_frees_it_first_despite_dead_memory(self):
        """والمفتاح نفسه مقروءاً (keys: [0]): «المفاتيح أولاً» يحرّره بالحركة الأولى ولو كانت البداية في سجلّ قديم."""
        bot, _, _ = self.make()
        s0 = _l154(L154_CYAN, {0: 0})
        lv, rec = self.lv_for(bot, s0, fails=2)
        rec["dead"] = [solver.state_key(s) for s in self.dead_line(_l154(L154_CYAN))]
        self.start_plan(bot, lv)
        self.assertEqual(lv.plan[:1], [(0, 2)])
        self.assertTrue(solver.key_freed(s0, 0, 2))

    def test_all_first_moves_dead_replans_without_memory(self):
        """كل حركة أولى في الطريق المسدود المحفوظ (والطريق البديل لا يجد حالة خارجه): تخطيط من جديد بدونه برسالة واضحة، ولا
        «لا خطة» وفي اللوحة حركات."""
        for layers, keys, fails in ((L154_CYAN, None, 2), (L154_RED, {4: 1}, 1)):
            bot, _, _ = self.make()
            s0 = _l154(layers, keys)
            lv, rec = self.lv_for(bot, s0, fails=fails)
            rec["dead"] = [solver.state_key(solver.apply_move(s0, i, j)) for i, j in solver.legal_moves(s0)]
            self.start_plan(bot, lv)
            self.assertTrue(lv.plan, self.log())
            self.assertIn(lv.plan[0], solver.legal_moves(s0))
            self.assertIn("الخطة بذاكرة الطريق المسدود فارغة (قصّت كل خط محسِّن)؛ تخطيط من جديد بدونها", self.log())

    def test_dead_memory_still_changes_the_line(self):
        """التنويع باقٍ: حالة مسدودة لها بديل تُتجنّب، والطريق البديل وإعادة التخطيط بدون الذاكرة لا يعملان حينئذ (الحالة بعد أول
        حركة لخطة المحاولة الأولى ليست أول حركة الثانية؛ وفي L124 بلا «المفاتيح أولاً» الحالة بعد الحركة الثانية)."""
        rb = [{"x": 64 + 68 * k, "y": 743, "cap": 4, "layers": l} for k, l in
              enumerate((["red", "blue"], ["blue", "red"], ["red", "blue"], ["blue", "red"], [], []))]
        for tubes, n, fails, step in ((rb, 7, 2, 0), (L124_START, 124, 1, 1)):
            bot, _, _ = self.make()
            s0 = _cp(tubes)
            lv, _ = self.lv_for(bot, s0, n=n, fails=fails)
            rec = bot.sig_data[lv.sig_id]
            rec["fails"] = 0
            lv.sig_attempt = 0
            pp = bot.plan_params(lv, s0)
            pp["keys_first"] = fails % 2 == 0
            line = solver.plan(s0, **pp)
            cur = s0
            for m in line[:step + 1]:
                cur = solver.apply_move(cur, *m)
            bad = solver.state_key(cur)
            rec["dead"] = [bad]
            rec["fails"] = lv.sig_attempt = fails
            self.start_plan(bot, lv)
            self.assertTrue(lv.plan)
            cur = s0
            seen = []
            for m in lv.plan:
                cur = solver.apply_move(cur, *m)
                seen.append(solver.state_key(cur))
            self.assertNotIn(bad, seen)
            self.assertNotIn("تخطيط من جديد بدونها", self.log())
            self.assertNotIn("طريق بديل", self.log())


class TestDoorReviewFixes(DriverCase):
    """إصلاحات مراجعة ذاكرة الأبواب (التشغيل 12)."""

    def lv_for(self, bot, n=124, tubes=L124_START):
        st = _cp(tubes)
        lv = driver.LevelCtx(n, st, 0.0)
        rec = bot.sig_rec(lv.sig_id, n)
        lv.sig_attempt = rec["fails"]
        bot.lv = lv
        return lv, rec

    def test_merge_door_identity_by_position(self):
        """هوية الباب خانات قواريره: مفتاح زائد في قراءة لاحقة لا يصنع سجلاً ثانياً (والمفاتيح التقاطع)، وقراءة تتداخل مع سجلّ ولا
        تطابقه تستبدله؛ وknown_doors يتجاهل سجلاً في خانة قارورة ظاهرة أو قارورة باب قُبل قبله."""
        d1 = [dict(t, layers=list(t["layers"])) for t in L124_DOOR1[:2]]
        doors = []
        self.assertEqual(driver.merge_door(doors, [[304, 743, 0]], d1), "new")
        d1b = [dict(t, layers=list(t["layers"])) for t in L124_DOOR1[:2]]
        d1b[0]["layers"] = ["darkgreen", "green", "?", "lavender"]
        self.assertEqual(driver.merge_door(doors, [[304, 743, 0], [372, 743, 0]], d1b), "known")
        self.assertEqual(len(doors), 1)
        self.assertEqual(doors[0]["keys"], [[304, 743, 0]])
        self.assertEqual(doors[0]["tubes"][0]["layers"], ["darkgreen", "green", "?", "lavender"])
        # بابان في لقطة واحدة (قوارير أكثر تتداخل مع السجلّ): القراءة الأحدث تحلّ محلّه
        both = d1 + [dict(t, layers=list(t["layers"])) for t in L124_DOOR2[:2]]
        self.assertEqual(driver.merge_door(doors, [[304, 743, 0], [372, 743, 0]], both), "replaced")
        self.assertEqual((len(doors), len(doors[0]["tubes"])), (1, 4))
        # ملف قديم فيه سجلّان للقوارير نفسها: الأول وحده يدخل المسألة
        dup = [{"keys": [[304, 743, 0]], "tubes": d1}, {"keys": [[304, 743, 0], [372, 743, 0]], "tubes": d1b}]
        self.assertEqual(len(driver.known_doors(_cp(L124_START), dup)), 1)
        # سجلّ قارورته في خانة قارورة ظاهرة الآن: لا يدخل
        bad = [{"keys": [[304, 743, 0]], "tubes": [{"x": 168, "y": 743, "cap": 4, "layers": ["red"] * 4}]}]
        self.assertEqual(driver.known_doors(_cp(L124_START), bad), [])

    def test_door_attributed_to_vanished_key(self):
        """لقطة بين طيران المفتاح وانفتاح الباب اعتُمدت (اللوحة المرجعية بلا المفتاح): يُنسب الباب إلى المفتاح الذي اختفى منذ آخر
        باب؛ وبلا ذلك يُقال في السجل إنه لم يُسجَّل."""
        bot, _, _ = self.make()
        lv, rec = self.lv_for(bot)
        ref = solver.apply_move(_cp(L124_START), 3, 0)          # المفتاح ما زال مرسوماً
        late = _cp(ref["tubes"])
        late["tubes"][3].pop("keys")                            # طار ولم ينفتح الباب بعد
        lv.last_state = ref
        bot.track_vanished(lv, late)
        self.assertEqual(lv.vanished, [[304, 743, 0]])
        lv.last_state = late
        st1 = _cp(L124_DOOR1)
        mp = driver.door_map(late, st1)
        self.assertIsNone(driver.door_record(late, st1, mp))
        self.assertEqual(driver.door_record(late, st1, mp, lv.vanished)[0], [[304, 743, 0]])
        lv.history = [("a", "a", None), ("b", "b", None)]
        bot.door_opened(st1, late, mp)
        self.assertEqual((len(rec["doors"]), rec["doors"][0]["keys"]), (1, [[304, 743, 0]]))
        self.assertEqual((lv.vanished, lv.door_idx), ([], 2))
        # مفتاح عاد للقراءة (ملصق فات لقطة) ليس محرَّراً
        lv2, rec2 = self.lv_for(bot)
        lv2.last_state = ref
        bot.track_vanished(lv2, late)
        lv2.last_state = late
        bot.track_vanished(lv2, ref)
        self.assertEqual(lv2.vanished, [])
        bot.door_opened(st1, late, driver.door_map(late, st1))
        self.assertIn("تعذّر نسب الباب إلى مفتاح", self.log())

    def test_dead_tail_after_door_and_hidden_filled(self):
        """الطريق المسدود: لا تدخله حالة انفتاح الباب ولا ما قبلها، و«?» في حالاته تُملأ بما عُرف بعدها (طبقات الباب) فيطابق
        مفتاحها ما يراه الحلّال في المحاولة التالية."""
        bot, _, _ = self.make()
        lv, rec = self.lv_for(bot)
        s0 = _cp(L124_START)
        s1 = solver.apply_move(s0, 3, 0)
        s2 = _cp(L124_DOOR1)                                    # بعد الباب
        s3 = solver.apply_move(s2, 3, 5)
        s4 = solver.apply_move(s3, 6, 5)
        ent = lambda s: (solver.state_key(s), solver.state_key(s), driver.compact_tubes(s))
        lv.history = [ent(s0), ent(s1)]
        lv.door_idx = len(lv.history)
        lv.history += [ent(s2), ent(s3), ent(s4)]
        bot.note_dead_end(lv)
        self.assertEqual(rec["dead"], [solver.state_key(s3), solver.state_key(s4)])
        self.assertEqual(len(rec["dead_st"]), 2)
        self.assertIn("بعد آخر باب انفتح", self.log())
        # المحاولة التالية: طبقتا الباب عُرفتا (learn_door_layers)، والحلّال يرى s4 بهما
        driver.merge_door(rec["doors"], [[304, 743, 0]], [dict(t, layers=list(t["layers"])) for t in L124_DOOR1[:2]])
        rec["doors"][0]["tubes"][0]["layers"] = ["darkgreen", "green", "brown", "lavender"]
        seen = _cp(s4["tubes"])
        seen["tubes"][0]["layers"] = ["darkgreen", "green", "brown", "lavender"]
        lv2, _ = self.lv_for(bot)
        pp = bot.plan_params(lv2, lv2.start_state)
        self.assertNotIn(solver.state_key(seen), set(rec["dead"]))
        self.assertIn(solver.state_key(seen), pp["avoid"])
        # والحفظ عبر التحديث الساخن
        c = driver.clean_sig_rec(json.loads(json.dumps(rec)))
        self.assertEqual(c["dead_st"], rec["dead_st"])

    def test_legacy_hot_update_does_not_replay_lost_attempt(self):
        """ملف عدّادات من كود بلا "sigs" والمرحلة خسرت قبله: أول محاولة لكل بداية فيها تُعدّ الثانية (لا الاستدعاء الحتمي الخاسر)."""
        old_sf = driver.STATE_FILE
        driver.STATE_FILE = Path(self.tmp.name) / "bot_state.json"
        try:
            fr = driver.Frame(Image.new("RGB", (473, 1000)))
            driver.STATE_FILE.write_text(json.dumps({"t": self.clock.time(), "level_fails": {"124": 5},
                                                     "lives_until": 0, "refills": 0, "coins": 70}), encoding="utf-8")
            bot, _, _ = self.make()
            self.assertTrue(bot.load_counters())
            bot.new_level(fr, _cp(L124_START), n=124)
            self.assertEqual(bot.lv.sig_attempt, 1)
            self.assertFalse(bot.plan_params(bot.lv, bot.lv.start_state)["keys_first"])
            self.assertIn("بداية بلا سجلّ بعد التحديث", self.log())
            bot.new_level(fr, _cp(L124_DOOR2), n=125)          # مرحلة لم تخسر قبل التحديث: كما كانت
            self.assertEqual(bot.lv.sig_attempt, 0)
            # ملف بذاكرة البدايات (ولو فارغة): لا تعديل
            driver.STATE_FILE.write_text(json.dumps({"t": self.clock.time(), "level_fails": {"124": 5}, "sigs": {}}),
                                         encoding="utf-8")
            bot2, _, _ = self.make()
            self.assertTrue(bot2.load_counters())
            bot2.new_level(fr, _cp(L124_START), n=124)
            self.assertEqual(bot2.lv.sig_attempt, 0)
        finally:
            driver.STATE_FILE = old_sf

    def test_shuffle_stops_door_learning(self):
        """بعد الخلط: لا يُسجَّل باب ولا تُملأ ذاكرة منه، وذاكرة المحاولة لا تدخل معرفة الطريق المسدود."""
        bot, _, _ = self.make()
        lv, rec = self.lv_for(bot)
        lv.boosters.append("shuffle")
        ref = solver.apply_move(_cp(L124_START), 3, 0)
        st1 = _cp(L124_DOOR1)
        note = bot.remember_door(ref, st1, driver.door_map(ref, st1))
        self.assertIn("بعد الخلط", note)
        self.assertEqual(rec["doors"], [])
        lv.memory = {(1, 0): "red"}
        self.assertEqual(bot.hidden_knowledge(lv, rec), [])

    def test_known_doors_with_blocked_tube_keeps_original_indices(self):
        """مسألة معروفة كلها وقارورة مغطّاة قبل قارورة المفتاح: الحلّال يحذفها ويعيد الحركات بالفهارس الأصلية (_remap_doors)."""
        base = [["green", "yellow", "blue", "yellow"], ["yellow", "red", "blue", "red"], ["blue", "blue", "red", "red"], []]
        door = {"keys": [[100, 700, 2]], "tubes": [{"x": 100, "y": 500, "cap": 4, "layers": ["green", "yellow", "green", "green"]}]}
        plain = {"tubes": [{"x": 100 + 70 * k, "y": 700, "cap": 4, "layers": list(l)} for k, l in enumerate(base)]}
        plain["tubes"][0]["keys"] = [2]
        want = solver.plan(plain, doors=driver.known_doors(plain, [door]))
        cov = {"tubes": [{"x": 30, "y": 700, "cap": 4, "layers": [], "blocked": True, "cover": "curtain"}]
               + [dict(t, layers=list(t["layers"])) for t in plain["tubes"]]}
        kd = driver.known_doors(cov, [door])
        self.assertEqual(kd[0]["keys"], [(1, 2)])
        info = {}
        mv = solver.plan(cov, info=info, doors=kd)
        self.assertEqual(info["mode"], "doors-full")
        self.assertEqual(mv, [(i + 1, j + 1) for i, j in want])


class FixedDoorGame(DoorGame):
    """مرحلة بباب مواضع قواريرها ثابتة (كاللعبة الحقيقية: القوارير خلف الباب تظهر في مكانه، والقديمة لا تتحرّك)، و«No Available
    Moves» حين لا يبقى اللغز الكامل (مع ما خلف الباب) قابلاً للحل بعد ثلاث صبّات، ثم «Give Up» يعيد البداية نفسها."""
    KIND = dict(FakeGame.KIND, nomoves="unknown")
    POS = [(98, 743), (168, 743), (236, 743), (304, 743), (98, 538), (168, 538)]

    def load(self, k):
        super().load(k)
        self.dead_pours = 0
        self.dead_snaps = None

    def snapshot(self):
        # النافذة تظهر بعد لقطات قليلة (البوت يرى الباب منفتحاً أولاً كما في المرحلة 124)
        if self.screen == "level" and self.dead_snaps is not None:
            self.dead_snaps += 1
            if self.dead_snaps > 3:
                self.screen = "nomoves"
                self.dead_snaps = None
        return super().snapshot()

    def layout(self):
        shut = self.closed()
        return [(-1000, -1000) if k in shut else self.POS[k] for k in range(len(self.truth))]

    def pour(self, i, j):
        ok = super().pour(i, j)
        if ok:
            import test_solver as T
            full = T.mk([(c, list(t)) for c, t in zip(self.caps, self.truth)])
            if not self.solved() and not T.reference_solvable(full):
                self.dead_pours += 1
                if (self.dead_pours >= 3 or not solver.legal_moves(self.visible())) and self.dead_snaps is None:
                    self.dead_snaps = 0
        return ok

    def tap(self, x, y):
        if self.screen == "nomoves":
            if abs(x - 236) < 60 and abs(y - 700) < 40:
                self.give_ups = getattr(self, "give_ups", 0) + 1
                self.load(self.li)
                self.screen = "level"
            return
        super().tap(x, y)


class GiveUpVision(FakeVisionModule):
    def find_give_up(self, arr):
        return (236, 700) if self._snap(arr)["screen"] == "nomoves" else None

    def booster_free(self, arr):
        return [False, False, False]                  # الأدوات نفدت (ثمنها بالعملات)


class TestDoorMemorySim(DriverCase):
    def test_second_attempt_uses_door_memory(self):
        """مرحلة بباب واحد: «المفاتيح أولاً» يصبّ الأصفر في الفارغة الوحيدة فينفتح الباب واللغز الكامل بلا حل («Give Up»).
        المحاولة الثانية للبداية نفسها تعرف ما خلف الباب فتحلّ المسألة كلها أولاً (doors-full) وتفوز."""
        lvl = ([4] * 5,
               [["green", "yellow", "blue", "yellow"], ["yellow", "red", "blue", "red"], ["blue", "blue", "red", "red"], [],
                ["green", "yellow", "green", "green"]],
               [[False] * 4, [False] * 4, [False] * 4, [], [False] * 4],
               [{"key": (0, 2), "tubes": [4]}])
        game = FixedDoorGame([lvl], random.Random(2))
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        bot = driver.Bot(FakeDevice(game), driver.Vision(GiveUpVision(game), out), out, 600, git=False)
        bot.loading_hashes, bot.daily_hashes, bot.nonet_hashes = [], [], []
        for _ in range(40):
            bot.run(max_iters=100)
            if game.wins >= 1:
                break
        log = self.log()
        self.assertEqual(game.wins, 1, log[-4000:])
        self.assertEqual(getattr(game, "give_ups", 0), 1, log[-4000:])
        self.assertIn("ذاكرة الأبواب: المفتاح (98،743 طبقة 2) ← 1 قارورة (جديد)", log)
        self.assertIn("طريق مسدود محفوظ", log)
        self.assertIn("البداية نفسها للمرة 2", log)
        self.assertIn("(doors-full", log)
        rec = next(iter(bot.sig_data.values()))
        self.assertEqual((rec["fails"], len(rec["doors"])), (1, 1))

    def test_hidden_door_layer_learned_then_known(self):
        """طبقة مخفية في قارورة الباب تنكشف في المحاولة الأولى (فتُكتب في ذاكرة الباب) ثم «Give Up»؛ في الثانية المسألة الممتدّة
        معروفة كلها فيُخطَّط لها كاملة (doors-full)، وحين ينفتح الباب تدخل الطبقة ذاكرة المحاولة قبل أن تنكشف (الحلّال يراها)."""
        lvl = ([4] * 5,
               [["green", "green", "yellow", "red"], ["yellow", "green", "red", "yellow"], ["red", "blue", "green", "red"], [],
                ["blue", "blue", "blue", "yellow"]],
               [[False] * 4, [False] * 4, [False] * 4, [], [False, False, True, False]],
               [{"key": (0, 0), "tubes": [4]}])
        game = FixedDoorGame([lvl], random.Random(2))
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        bot = driver.Bot(FakeDevice(game), driver.Vision(GiveUpVision(game), out), out, 600, git=False)
        bot.loading_hashes, bot.daily_hashes, bot.nonet_hashes = [], [], []
        snaps = []
        orig = bot.remember_door

        def spy(ref, st, mp, record=True):
            note = orig(ref, st, mp, record)
            k = next(i for i, t in enumerate(st["tubes"]) if t["y"] == 538)
            snaps.append((st["tubes"][k]["layers"][2], bot.lv.memory.get((k, 2))))
            return note
        bot.remember_door = spy
        for _ in range(40):
            bot.run(max_iters=100)
            if game.wins >= 1:
                break
        log = self.log()
        self.assertEqual((game.wins, getattr(game, "give_ups", 0)), (1, 1), log[-4000:])
        self.assertIn("ذاكرة الأبواب: طبقة مخفية انكشفت في قارورة باب معروف", log)
        self.assertIn("(doors-full", log)
        self.assertIn("1 طبقة مخفية معروفة من محاولة سابقة", log)
        self.assertEqual(snaps, [("?", None), ("?", "blue")])
        rec = next(iter(bot.sig_data.values()))
        self.assertEqual(rec["doors"][0]["tubes"][0]["layers"], ["blue", "blue", "blue", "yellow"])


class TagGame(FakeGame):
    """«Tag!» (المرحلة 130): levels[k][3] = {قارورة: لون وسمها}؛ لا يُصبّ في الموسومة إلا لونها (اللعبة ترفض غيره ويُحسب خطأً).
    flicker: أول لقطة بعد كل صبّة في موسومة لا يُقرأ فيها وسمها (البطاقة يحجبها الصبّ) فتعيده ذاكرة الوسوم بالموضع."""

    def __init__(self, levels, rng, flicker=False):
        self.flicker = flicker
        self.bad_pours = 0
        self.flickers = 0
        self.hide_tag = None
        super().__init__(levels, rng)

    def load(self, k):
        super().load(k)
        lvl = self.levels[k]
        self.tags = dict(lvl[3]) if len(lvl) > 3 else {}

    def visible(self):
        st = super().visible()
        for k, acc in self.tags.items():
            if k == self.hide_tag:
                self.flickers += 1
                continue
            st["tubes"][k]["accept"] = acc
        self.hide_tag = None
        return st

    def pour(self, i, j):
        if j in self.tags and self.truth[i] and self.truth[i][-1] != self.tags[j]:
            self.bad_pours += 1
            return False
        ok = super().pour(i, j)
        if ok and self.flicker and j in self.tags:
            self.hide_tag = j
        return ok


class TestTags(DriverCase):
    """«Tag!» في السائق: الوسم يصل من الرؤية إلى الحلّال، ويُحفظ بالموضع، ويدخل مفاتيح الحالات وسجلّات الأبواب والطريق المسدود."""
    L130 = [["pink", "yellow", "yellow", "blue"], [], ["yellow", "red", "orange", "pink"], ["green", "red", "red", "yellow"], [],
            ["lavender", "green", "lavender", "green"], ["blue", "purple", "purple", "lavender"], [],
            ["orange", "orange", "orange", "blue"], ["red", "purple", "green", "purple"], [], ["lavender", "pink", "blue", "pink"]]
    L130_TAGS = {1: "lavender", 4: "purple", 7: "red", 10: "pink"}

    def test_l130_played_end_to_end(self):
        """بداية المرحلة 130 الحقيقية (أربع فارغات موسومة ولا فارغة عادية) ثم لغز بفارغة موسومة وأخرى عادية: يُحلّان بلا صبّة
        مرفوضة واحدة، ومع وسم يغيب عن لقطة بعد كل صبّة فيه (ذاكرة الوسوم)."""
        lv2 = [["red", "blue", "red", "blue"], ["blue", "red", "blue", "red"], ["green", "green", "yellow", "yellow"],
               ["yellow", "yellow", "green", "green"], [], []]
        levels = [([4] * 12, self.L130, [[False] * len(t) for t in self.L130], self.L130_TAGS),
                  ([4] * 6, lv2, [[False] * len(t) for t in lv2], {4: "green"})]
        game = TagGame(levels, random.Random(3), flicker=True)
        out = driver.Out(Path(self.tmp.name), 600, quiet=True)
        bot = driver.Bot(FakeDevice(game), driver.Vision(FakeVisionModule(game), out), out, 600, git=False)
        for _ in range(30):
            bot.run(max_iters=100)
            if game.wins >= 2:
                break
        log = self.log()
        self.assertEqual((game.wins, bot.levels_done), (2, 2), log[-3000:])
        self.assertEqual(game.bad_pours, 0, log[-3000:])
        self.assertGreater(game.flickers, 0)
        self.assertIn("وسوم المرحلة 1", log)
        self.assertIn("القارورة 1: lavender، القارورة 4: purple، القارورة 7: red، القارورة 10: pink", log)
        self.assertIn("ذاكرة الوسوم:", log)
        self.assertIn('"accept": "lavender"', log)
        self.assertNotIn("لا حركة قانونية", log)

    def test_parse_keeps_accept_with_real_vision(self):
        import vision as real_vision
        out = driver.Out(Path(self.tmp.name), 10, quiet=True)
        vis = driver.Vision(real_vision, out)
        st = vis.parse(driver.Frame(Image.open(Path(driver.HERE) / "testdata" / "L130_tags.jpg")))
        self.assertEqual({k: t["accept"] for k, t in enumerate(st["tubes"]) if t.get("accept")}, self.L130_TAGS)
        self.assertEqual([t["layers"] for t in st["tubes"]], self.L130)
        self.assertFalse(st["warnings"])
        self.assertFalse(driver.suspicious_counts(st))
        mv = solver.plan(st)
        self.assertTrue(mv)
        cur = st
        for i, j in mv:
            cur = solver.apply_move(cur, i, j)
            self.assertIsNotNone(cur)
        self.assertTrue(solver.is_solved(cur))
        self.assertEqual(driver.compact_state(st)[1], {"x": st["tubes"][1]["x"], "y": st["tubes"][1]["y"], "cap": 4,
                                                       "layers": [], "accept": "lavender"})

    def test_remember_tags(self):
        tags = []
        st = {"tubes": [T(118, 377, [], accept="red"), T(196, 375, ["red", "blue"]), T(352, 377, [], accept="pink")]}
        out, n = driver.remember_tags(st, tags)
        self.assertEqual((n, sorted(r[2] for r in tags)), (0, ["pink", "red"]))
        # الوسم غاب عن لقطة: يعود بالموضع ما دامت القارورة فارغة أو كل طبقاتها بلونه
        st2 = {"tubes": [T(118, 377, ["red", "red"]), T(196, 375, ["red", "blue"]), T(352, 377, ["blue"])]}
        out, n = driver.remember_tags(st2, tags)
        self.assertEqual(n, 1)
        self.assertEqual([t.get("accept") for t in out["tubes"]], ["red", None, None])   # الزرقاء في خانة الوردي: ليست هي
        self.assertNotIn("accept", st2["tubes"][0])                                        # لا تتغيّر الحالة الأصلية
        self.assertEqual(driver.remember_tags({"tubes": [T(40, 375, [])]}, tags), ({"tubes": [T(40, 375, [])]}, 0))

    def test_tags_follow_tubes_when_the_board_changes(self):
        """قارورة إضافية أو «Play On» تعيد ترتيب الصفّ السفلي (المرحلة 121 بمواضع 130: سبع قوارير، 352→304 و431→372): ذاكرة
        الوسوم تتبع قواريرها بالمطابقة، ولا يقع مدخل الوردي القديم (352) على القارورة العادية التي صارت على 372 (بُعدها 20)."""
        top = [T(x, 375, ["red", "blue", "green", "yellow"]) for x in (40, 118, 196, 274, 352, 431)]
        old = {"tubes": top + [T(40, 636, ["blue", "purple"]), T(118, 638, [], accept="red"), T(196, 636, ["orange"]),
                               T(274, 636, ["green", "purple"]), T(352, 638, [], accept="pink"), T(431, 636, ["pink", "pink"])]}
        tags = []
        driver.remember_tags(old, tags)
        new = {"tubes": top + [T(x, 636, L) for x, L in ((36, ["blue", "purple"]), (104, []), (172, ["orange"]),
                                                          (240, ["green", "purple"]), (304, []), (372, ["pink", "pink"]),
                                                          (440, []))]}
        # بلا نقل: المدخل القديم يعطي العادية على 372 وسماً خطأً (الخطأ الذي يُحرس)
        _out, bad = driver.remember_tags(new, [list(r) for r in tags])
        self.assertEqual([t["x"] for t in _out["tubes"] if t.get("accept") == "pink"], [372])
        driver.rebase_tags(tags, old, new, driver.slot_map(old, new))
        self.assertEqual(sorted(tags), [[104, 636, "red", 1], [304, 636, "pink", 1]])     # (الثقة 1: فارغة بلا مصدر مقروء)
        out, n = driver.remember_tags(new, tags)
        got = {t["x"]: t.get("accept") for t in out["tubes"][6:]}
        self.assertEqual(got, {36: None, 104: "red", 172: None, 240: None, 304: "pink", 372: None, 440: None})
        self.assertEqual(n, 2)

    def test_tag_memory_keeps_the_bottom_reading(self):
        """التشغيل 19: الوسم الأخضر قُرئ «lavender» في الإطار الحيّ. ما قُرئ من قاع قارورة غير فارغة (ثقة 3: لون الوسم في قاعها) لا
        تغيّره قراءة أقلّ ثقة بعد أن تفرغ، بل تُصحَّح بها؛ وقارورة لم يُقرأ وسمها تأخذه ما دامت فارغة أو قاعها بلونه."""
        tags = []
        full = {"tubes": [T(168, 537, ["green", "orange", "yellow", "lavender"], accept="green", tag_src="bottom")]}
        out, n = driver.remember_tags(full, tags)
        self.assertEqual((n, tags), (0, [[168, 537, "green", 3]]))
        empty = {"tubes": [T(167, 537, [], accept="lavender", tag_src="ribbon")]}
        out, n = driver.remember_tags(empty, tags)
        self.assertEqual((n, out["tubes"][0]["accept"], out["tubes"][0]["tag_src"]), (1, "green", "memory"))
        self.assertEqual(tags, [[167, 537, "green", 3]])
        self.assertEqual(empty["tubes"][0]["accept"], "lavender")                         # لا تتغيّر الحالة الأصلية
        out, n = driver.remember_tags({"tubes": [T(168, 537, ["green"])]}, tags)        # البطاقة لم تُقرأ: القاع بلونه
        self.assertEqual((n, out["tubes"][0]["accept"]), (1, "green"))
        out, n = driver.remember_tags({"tubes": [T(168, 537, ["blue"])]}, tags)         # قاع بلون آخر: ليست هي
        self.assertEqual((n, out["tubes"][0].get("accept")), (0, None))
        # قراءة بثقة أعلى من الذاكرة تغيّرها (البطاقة فوق قارورة فارغة أوثق من الشريط)
        tags2 = [[300, 537, "purple", 1]]
        out, n = driver.remember_tags({"tubes": [T(304, 537, [], accept="blue", tag_src="icon")]}, tags2)
        self.assertEqual((n, out["tubes"][0]["accept"], tags2), (0, "blue", [[304, 537, "blue", 2]]))
        self.assertEqual(driver.tag_conf(T(1, 1, ["red", "blue"], accept="red", tag_src="icon")), 3)
        self.assertEqual(driver.tag_conf(T(1, 1, [], accept="red", tag_src="vote")), 0)

    def test_keys_and_records_carry_accept(self):
        a, b = T(118, 377, [], accept="red"), T(118, 377, [], accept="blue")
        self.assertFalse(driver._same_tube(a, b))
        self.assertTrue(driver._same_tube(a, T(118, 377, [])))
        st = {"tubes": [T(40, 375, ["red", "blue"]), a, T(196, 375, ["blue", "?"])]}
        tc = driver.compact_tubes(st)
        self.assertEqual(tc[1], [118, 377, 4, [], "red"])
        self.assertEqual(len(tc[0]), 4)                                   # غير الموسومة كما كانت
        know = [(196, 375, 4, 1, "red")]
        filled = driver.fill_known(tc, know)
        self.assertEqual(solver.state_key(filled), solver.state_key(
            {"tubes": [T(40, 375, ["red", "blue"]), a, T(196, 375, ["blue", "red"])]}))
        rec = {"n": 130, "dead": [json.loads(json.dumps(solver.state_key(st)))], "dead_st": [json.loads(json.dumps(tc))],
               "doors": [{"keys": [[40, 375, 0]], "tubes": [{"x": 300, "y": 375, "cap": 4, "layers": ["red"], "accept": "red"}]}]}
        clean = driver.clean_sig_rec(json.loads(json.dumps(rec)))
        self.assertEqual(clean["dead"], [solver.state_key(st)])
        self.assertEqual(clean["dead_st"], [tc])
        self.assertEqual(clean["doors"][0]["tubes"][0]["accept"], "red")
        # باب ظهرت خلفه قارورة موسومة: يُسجَّل وسمها
        ref = {"tubes": [dict(T(40, 375, ["green", "red"]), keys=[0])]}
        new = {"tubes": [T(40, 375, ["green"]), T(300, 375, ["red"], accept="red")]}
        freed, tubes = driver.door_record(ref, new, {0: 0})
        self.assertEqual(tubes[0]["accept"], "red")
        self.assertIn("{وسم:red}", solver.describe(new))


# ============================================================== ملاحظات المراجعة: قياس اللعب، ومهلة الإعادة، والأرشيف المقطوع، والأرشفة
class TestReviewFixes(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self._time = driver.time
        driver.time = self.clock
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.cfg = dict(driver.CFG)
        self._kill, self._start = driver.kill_emulators, driver.start_emulator
        driver.kill_emulators = lambda: None
        driver.start_emulator = lambda log_path=None, wipe=False: True
        fake_emulator_host(self, self.d)

    def tearDown(self):
        driver.time = self._time
        driver.CFG.clear()
        driver.CFG.update(self.cfg)
        driver.kill_emulators, driver.start_emulator = self._kill, self._start
        self.tmp.cleanup()

    def make(self, boot="1", minutes=300):
        rng = random.Random(9)
        game = FakeGame([make_level(rng, 4, 2)], rng)
        dev = FlakyDevice(game, 0, boot)
        out = driver.Out(self.d / "out", 600, quiet=True)
        bot = driver.Bot(dev, driver.Vision(FakeVisionModule(game), out), out, minutes, git=False)
        bot.log_host_oom = lambda: None
        return dev, bot

    def log(self):
        return (self.d / "out" / "log.txt").read_text(encoding="utf-8")

    # --- 1: دقائق اللعب حتى آخر لقطة ناجحة لا حتى القرار
    def test_outage_time_is_not_play_time(self):
        dev, bot = self.make()
        bot.restart_emulator = lambda budget=None: (self.clock.sleep(60), True)[1]
        crashes = []
        for k in range(5):
            # المحاكي يعيش 13 دقيقة بلا فوز ثم يموت؛ العطل حتى القرار 3 دقائق (لقطات فاشلة وadb ونسخة على محاكٍ ميت):
            # 13 + 3 = 16 دقيقة منذ الإعادة، لكن اللعب 13 فقط (< emu_progress_min = 15)، فلا يُحسب تقدّماً
            self.clock.sleep(13 * 60)
            bot.last_ok_grab = self.clock.time()
            self.clock.sleep(3 * 60)
            bot.cap_fails = 4
            self.assertTrue(bot.recover_device())
            crashes.append(bot.stop)
        self.assertEqual(crashes, [False, False, False, True, True], self.log()[-1500:])
        self.assertIn("بلا تقدّم منذ الإعادة السابقة (13 دقيقة بلا فوز)", self.log())

    def test_failed_restart_counts_zero_play(self):
        dev, bot = self.make()
        results = iter([True, False, False, False])
        bot.restart_emulator = lambda budget=None: (self.clock.sleep(600), next(results))[1]
        self.clock.sleep(30 * 60)
        bot.last_ok_grab = self.clock.time()
        bot.cap_fails = 4
        bot.recover_device()                     # أول عطل: يُعاد وينجح
        bot.last_ok_grab = self.clock.time() + 20 * 60   # 20 دقيقة لعب بعدها
        self.clock.sleep(21 * 60)
        bot.cap_fails = 4
        bot.recover_device()                     # تقدّم: يُعاد ويفشل (لا لقطة ناجحة بعده)
        for n in (8, 12):                        # إعادتان فاشلتان متتاليتان: 10 دقائق انتظار الإقلاع ليست لعباً
            bot.cap_fails = n
            bot.recover_device()
        self.assertEqual(bot.emu_fruitless, 2, self.log()[-1500:])
        bot.cap_fails = 16
        bot.recover_device()
        self.assertTrue(bot.stop)

    # --- 2: مهلة الإعادة من الوقت الباقي
    def test_restart_gets_remaining_time_budget(self):
        dev, bot = self.make(minutes=60)
        got = []
        bot.restart_emulator = lambda budget=None: (got.append(budget), True)[1]
        self.clock.sleep(50 * 60)
        bot.cap_fails = 4
        bot.recover_device()
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0], 10 * 60 - 60, delta=1)

    def test_restart_emulator_gives_up_when_budget_runs_out(self):
        dev, bot = self.make(boot="0")           # لا يكمل الإقلاع أبداً
        t0 = self.clock.time()
        self.assertFalse(bot.restart_emulator(budget=90))
        self.assertLess(self.clock.time() - t0, 200)
        self.assertIn("نفدت مهلة الإعادة", self.log())

    def test_restart_emulator_skips_install_without_time(self):
        dev, bot = self.make()
        dev.installed = lambda: False
        called = []
        bot.install_game = lambda until=None: (called.append("install"), True)[1]
        bot.restore_app = lambda: (called.append("restore"), True)[1]
        launched = dev.launched
        self.assertFalse(bot.restart_emulator(budget=5 * 60))
        self.assertEqual(called, [])
        self.assertEqual(dev.launched, launched)
        self.assertIn("لم يبقَ وقت لتثبيتها", self.log())
        self.assertTrue(bot.restart_emulator(budget=30 * 60))
        self.assertEqual(called, ["install", "restore"])

    def test_install_game_respects_until(self):
        dev, bot = self.make()
        g = self.d / "game"
        g.mkdir()
        (g / (driver.PKG + ".apk")).write_bytes(b"x")
        driver.CFG["game_dir"] = str(g)
        calls = []
        dev.run = lambda args, timeout=None: (calls.append(timeout), (1, "Failure"))[1]
        self.assertFalse(bot.install_game(until=self.clock.time() + 100))
        self.assertTrue(calls and all(t <= 100 for t in calls), calls)
        calls.clear()
        self.assertFalse(bot.install_game(until=self.clock.time() + 10))
        self.assertEqual(calls, [])

    # --- 3: backups_saved يبقى بعد التحديث الساخن
    def test_backups_saved_survives_hot_update(self):
        dev, bot = self.make()
        bot.backups_saved = 2
        saved = driver.STATE_FILE
        driver.STATE_FILE = self.d / "state.json"
        try:
            bot.save_counters()
            b2 = driver.Bot(dev, bot.vis, driver.Out(self.d / "b2", 10, quiet=True), 100, git=False)
            self.assertTrue(b2.load_counters())
        finally:
            driver.STATE_FILE = saved
        self.assertEqual(b2.backups_saved, 2)

    # --- 4: الأرشيف المقطوع لا يحلّ محلّ النسخة السليمة
    def test_verify_backup(self):
        def chk(data):
            p = self.d / "v.ab"
            p.write_bytes(data)
            return driver.verify_backup(p)
        good = backup_bytes(40000, seed=2)
        self.assertTrue(chk(good)[0])
        self.assertTrue(chk(backup_bytes(40000, seed=2, compressed=False))[0])
        for cut in (30, 100, len(good) // 2, len(good) - 1):
            with self.subTest(cut=cut):
                self.assertFalse(chk(good[:cut])[0])
        plain = backup_bytes(40000, seed=2, compressed=False)
        self.assertFalse(chk(plain[:-512])[0])               # بلا كتلتي النهاية
        self.assertFalse(chk(plain[:-100])[0])               # كتل ناقصة
        self.assertFalse(chk(good + b"junk")[0])             # بيانات بعد التيار
        self.assertFalse(chk(good.replace(b"none", b"AES-256", 1))[0])
        self.assertFalse(chk(b"x" * 5000)[0])
        import zlib
        head = b"ANDROID BACKUP\n5\n1\nnone\n"
        no_eof = head + zlib.compress(random.Random(1).randbytes(4096), 0)    # tar بلا كتلتي الأصفار
        self.assertFalse(chk(no_eof)[0])

    def test_truncated_backup_keeps_previous_parts(self):
        dev, bot = self.make()
        driver.CFG["backup_part_mb"] = 0.01
        good = self.d / "good.ab"
        good.write_bytes(backup_bytes(30000, seed=5))
        bot.levels_done = 3
        self.assertTrue(bot.store_backup(str(good)))
        before = {p.name: p.read_bytes() for p in bot.out.dir.iterdir() if driver.is_backup_file(p.name)}
        cut = self.d / "cut.ab"
        cut.write_bytes(backup_bytes(60000, seed=6)[:25000])  # مات المحاكي أثناء النقل
        bot.levels_done = 4
        self.assertFalse(bot.store_backup(str(cut)))
        after = {p.name: p.read_bytes() for p in bot.out.dir.iterdir() if driver.is_backup_file(p.name)}
        self.assertEqual(after, before)
        self.assertEqual(bot.backup_levels, 3)
        self.assertEqual(bot.backups_saved, 1)
        self.assertIn("نسخة احتياطية غير كاملة", self.log())
        got, info = driver.join_backup(bot.out.dir, self.d / "j.ab")
        self.assertEqual(got.read_bytes(), good.read_bytes(), info)


class TestArchiveCommands(unittest.TestCase):
    """أوامر أرشفة التشغيل في تعليق driver.py (بين «أوامر الأرشفة (بداية)» و«(نهاية)») تُنفَّذ كما هي على مستودع مؤقت."""

    @staticmethod
    def commands():
        src = (Path(__file__).resolve().parent / "driver.py").read_text(encoding="utf-8").splitlines()
        a = next(i for i, l in enumerate(src) if "أوامر الأرشفة (بداية)" in l)
        b = next(i for i, l in enumerate(src) if "أوامر الأرشفة (نهاية)" in l)
        lines = [l[4:] if l.startswith("#   ") else l.lstrip("#") for l in src[a + 1:b]]
        return "\n".join(lines).replace("runN-Lxxx", "run99-L999").replace("التشغيل N", "التشغيل 99")

    def setUp(self):
        import shutil
        import subprocess
        if not shutil.which("git") or not shutil.which("bash"):
            self.skipTest("لا git أو bash")
        self.sp = subprocess
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.origin = self.d / "origin.git"
        self.repo = self.d / "repo"
        self.git("init", "-q", "--bare", str(self.origin), cwd=self.d)
        self.git("init", "-q", "-b", "main", str(self.repo), cwd=self.d)
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            self.git("config", k, v)
        self.git("remote", "add", "origin", str(self.origin))
        self.emu = self.repo / "research" / "emu"
        (self.emu / "runs" / "run1").mkdir(parents=True)
        (self.emu / "runs" / "run1" / "log.txt").write_text("old run")
        (self.emu / "out").mkdir()
        (self.emu / "out" / "log.txt").write_text("this run")
        (self.emu / "save").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *a, cwd=None):
        r = self.sp.run(["git"] + list(a), cwd=str(cwd or self.repo), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def commit_all(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "حالة")
        self.git("push", "-q", "-u", "origin", "main")

    def archive(self):
        r = self.sp.run(["bash", "-c", self.commands()], cwd=str(self.repo), capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def tree(self, sub):
        out = self.git("ls-tree", "-r", "--name-only", "origin/main", "--", "research/emu/" + sub)
        return sorted(l.split("/")[-1] for l in out.split())

    def parts(self, d, n, seed):
        src = self.d / ("src%d.ab" % seed)
        src.write_bytes(backup_bytes(n, seed=seed))
        driver.split_backup(src, d, 10000)
        return src.read_bytes()

    def test_parts_replace_old_save_and_stale_parts(self):
        self.parts(self.emu / "save", 35000, 1)               # 4 أجزاء قديمة
        (self.emu / "save" / driver.BACKUP_NAME).write_bytes(b"older single")
        new = self.parts(self.emu / "out", 15000, 2)          # جزءان جديدان
        self.commit_all()
        rc, out = self.archive()
        self.assertEqual(rc, 0, out)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.tree("save"), sorted([driver.BACKUP_MANIFEST, driver.backup_part_name(0),
                                                    driver.backup_part_name(1)]))
        self.assertEqual(self.tree("runs/run99-L999"), ["log.txt"])
        self.assertEqual(self.tree("out"), [])
        got, info = driver.join_backup(self.emu / "save", self.d / "j.ab")
        self.assertEqual(got.read_bytes(), new, info)

    def test_old_single_file_from_old_code(self):
        self.parts(self.emu / "save", 25000, 1)
        (self.emu / "out" / driver.BACKUP_NAME).write_bytes(backup_bytes(5000, seed=3))
        self.commit_all()
        rc, out = self.archive()
        self.assertEqual(rc, 0, out)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.tree("save"), [driver.BACKUP_NAME])
        self.assertEqual(self.tree("runs/run99-L999"), ["log.txt"])

    def test_failure_commits_nothing(self):
        (self.emu / "save" / driver.BACKUP_NAME).write_bytes(b"keep me")
        (self.emu / "out" / driver.BACKUP_MANIFEST).write_text("{}")      # ملف وصف بلا أجزاء: git mv يفشل
        self.commit_all()
        head = self.git("rev-parse", "origin/main")
        rc, out = self.archive()
        self.assertNotEqual(rc, 0)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), head)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)

    def test_no_backup_keeps_save(self):
        (self.emu / "save" / driver.BACKUP_NAME).write_bytes(b"keep me")
        self.commit_all()
        rc, out = self.archive()
        self.assertEqual(rc, 0, out)
        self.assertIn("يبقى save/ كما هو", out)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.tree("save"), [driver.BACKUP_NAME])
        self.assertEqual(self.tree("runs/run99-L999"), ["log.txt"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
