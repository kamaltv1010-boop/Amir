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
        caps, truth, hidden = self.levels[k]
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
