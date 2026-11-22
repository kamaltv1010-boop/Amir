#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""المحرّك الذاتي لبوت Magic Sort (بحث فقط، يعمل على مشغّل GitHub بجوار المحاكي).

الحلقة: لقطة adb -> تصغير إلى ارتفاع 1000 -> vision.classify -> فعل:
  level  : parse_level ثم solver.plan، وتُنفَّذ حركة واحدة (نقر المصدر ثم الهدف)،
           ثم لقطة جديدة للتحقق (الطبقات المخفية تنكشف). لا تقدّم = حركة سيئة؛
           بعد 3 إخفاقات: لقطة stuck_* ثم الأدوات (قارورة إضافية، ثم خلط، ثم تراجع).
  button : نقر find_button.   close : نقر find_close.
  unknown: لقطة unknown_* (محدودة)، ثم انتظار/رجوع/نقر الوسط/إعادة تشغيل اللعبة.
كل شاشة غير اللغز لم يُرَ شكلها من قبل (بصمة إدراكية) تُحفظ new_*.jpg، وأول لقطة
لكل مرحلة L{n:03d}_start.jpg مع حالتها في السجل.

التحكم عن بعد: research/emu/cmd.txt في الفرع (السطر الأول "seq N" ثم أوامر):
  pause | resume | stop | tap X Y | swipe X1 Y1 X2 Y2 [MS] | wait S | shot NAME | back |
  key K | launch | relaunch | logcat [N] | top | booster undo|shuffle|add | minutes M | skip |
  airplane on|off
  (الإحداثيات بكسلات الجهاز 1080x2280 كالحلقة القديمة؛ تُنفَّذ مرة لكل seq جديد،
  والـ seq الموجود عند البدء يُعتبر منفَّذاً.)
النشر كل 5 دقائق من شجرة git منفصلة (/tmp/bot_pub): نسخ research/emu/out إليها ثم
commit ثم fetch + rebase ثم push، فلا تتوقف الحلقة أثناء مشكلات الشبكة.

التشغيل:
  python3 research/emu/bot/driver.py                    # على المشغّل (BOT_MINUTES=300)
  python3 research/emu/bot/driver.py --offline DIR      # تجربة جافة على لقطات محفوظة بلا adb
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import io
import json
import os
import queue
import random
import shutil
import struct
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import solver  # noqa: E402

ROOT = HERE.parents[2]                 # جذر المستودع
OUT_REL = "research/emu/out"
CMD_REL = "research/emu/cmd.txt"
PKG = "com.grandgames.magicsort"
STD_H = 1000


def _env(name, default, typ=str):
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    try:
        return typ(v)
    except ValueError:
        return default


CFG = {
    "minutes": _env("BOT_MINUTES", 300.0, float),
    "branch": _env("BOT_BRANCH", "claude/quirky-ride-r4oor0"),
    "game_dir": _env("GAME_DIR", "/tmp/game"),
    "max_images": _env("BOT_MAX_IMAGES", 600, int),
    "publish_sec": _env("BOT_PUBLISH_SEC", 300.0, float),
    "poll_sec": _env("BOT_POLL_SEC", 10.0, float),
    "airplane": _env("BOT_AIRPLANE", "off"),            # off | after_load | start (النسخ الحديثة تشترط الإنترنت)
    "loading_max_sec": _env("BOT_LOADING_MAX_SEC", 720.0, float),  # صبر شاشة التحميل قبل إعادة التشغيل
    "pour_wait": _env("BOT_POUR_WAIT", 1.2, float),
    "tap_gap": _env("BOT_TAP_GAP", 0.3, float),
    "level_max_min": _env("BOT_LEVEL_MAX_MIN", 30.0, float),
    "plan_sec": _env("BOT_PLAN_SEC", 1.6, float),
}
BOOSTER_DEFAULT = {"undo": (144, 854), "shuffle": (236, 854), "add": (328, 854)}
NOVEL_DIST = 28        # بصمة 256 بت: نوافذ الفوز بينها ≤32، والشاشات المختلفة ≥73
PUB_DIR = Path(os.environ.get("BOT_PUB_DIR", "/tmp/bot_pub"))   # شجرة git منفصلة للنشر
TOS_POINT = (236, 660)                 # زرّ CONTINUE في نافذة الشروط عند أول تشغيل


def ts():
    return time.strftime("%H:%M:%S")


# ============================================================== الإخراج
class Out:
    """السجل والصور والملفات في research/emu/out (قفل مشترك مع النشر)."""

    def __init__(self, directory: Path, max_images: int, quiet=False):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.max_images = max_images
        self.images = 0
        self.quiet = quiet
        self.capped_logged = False

    def log(self, msg):
        line = "[%s] %s" % (ts(), msg)
        if not self.quiet:
            print(line, flush=True)
        with self.lock:
            with open(self.dir / "log.txt", "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def write(self, name, text):
        with self.lock:
            tmp = self.dir / (".%s.tmp" % name)
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, self.dir / name)

    def append(self, name, text):
        with self.lock:
            with open(self.dir / name, "a", encoding="utf-8") as f:
                f.write(text)

    def save_jpg(self, name, img, force=False) -> bool:
        if self.images >= self.max_images and not force:
            if not self.capped_logged:
                self.capped_logged = True
                self.log("بلغ عدد الصور الحد (%d): لا مزيد من الصور" % self.max_images)
            return False
        if isinstance(img, np.ndarray):
            img = Image.fromarray(img)
        img = downscale(img)
        with self.lock:
            tmp = self.dir / (".%s.tmp" % name)
            img.save(tmp, format="JPEG", quality=80)
            os.replace(tmp, self.dir / name)
        self.images += 1
        return True


def downscale(im: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    w, h = im.size
    if h != STD_H:
        im = im.resize((int(w * STD_H / h), STD_H), Image.LANCZOS)
    return im


class Frame:
    """لقطة مصغّرة: PIL + numpy (1000xW)."""
    __slots__ = ("pil", "arr", "t")

    def __init__(self, pil):
        self.pil = downscale(pil)
        self.arr = np.asarray(self.pil)
        self.t = time.time()


def dhash(fr: Frame, size=16):
    g = fr.pil.convert("L").resize((size + 1, size), Image.BILINEAR)
    a = np.asarray(g, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


def center_hash(fr: Frame, size=16):
    """بصمة وسط الشاشة (حيث النوافذ المنبثقة) بمقياس اللقطة المعيارية 473×1000."""
    g = fr.pil.convert("L").resize((473, 1000), Image.BILINEAR).crop((40, 260, 433, 700))
    a = np.asarray(g.resize((size + 1, size), Image.BILINEAR), dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


def hash_hex(bits) -> str:
    return np.packbits(bits.astype(np.uint8)).tobytes().hex()


def hex_hash(h: str):
    return np.unpackbits(np.frombuffer(bytes.fromhex(h), dtype=np.uint8)).astype(bool)


# ============================================================== الجهاز
class Device:
    def __init__(self, serial=None):
        self.adb = shutil.which("adb") or "adb"
        self.serial = serial
        self.W, self.H = 1080, 2280
        self.raw_ok = True
        self.logcat = None

    def _cmd(self, args):
        base = [self.adb]
        if self.serial:
            base += ["-s", self.serial]
        return base + list(args)

    def run(self, args, timeout=30, binary=False):
        try:
            p = subprocess.run(self._cmd(args), stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL if binary else subprocess.STDOUT,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            return 124, (b"" if binary else "timeout")
        except OSError as e:
            return 127, (b"" if binary else str(e))
        return p.returncode, (p.stdout if binary else p.stdout.decode("utf-8", "replace"))

    def sh(self, cmd, timeout=30) -> str:
        rc, out = self.run(["shell", cmd], timeout=timeout)
        return out.strip()

    def to_dev(self, x, y):
        s = self.H / float(STD_H)
        X = int(round(x * s))
        Y = int(round(y * s))
        return max(0, min(self.W - 1, X)), max(0, min(self.H - 1, Y))

    def tap(self, X, Y):
        self.run(["shell", "input", "tap", str(int(X)), str(int(Y))], timeout=15)

    def tap_std(self, x, y):
        self.tap(*self.to_dev(x, y))

    def tap2_std(self, a, b, gap):
        """نقرتان (المصدر ثم الهدف) في استدعاء adb واحد لتوفير الوقت."""
        (X1, Y1), (X2, Y2) = self.to_dev(*a), self.to_dev(*b)
        self.run(["shell", "input tap %d %d; sleep %.2f; input tap %d %d" % (X1, Y1, gap, X2, Y2)],
                 timeout=20)

    def swipe(self, x1, y1, x2, y2, ms=300):
        self.run(["shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)),
                  str(int(y2)), str(int(ms))], timeout=20)

    def key(self, code):
        self.run(["shell", "input", "keyevent", str(code)], timeout=15)

    def screencap(self):
        """لقطة بالحجم الكامل (PIL) أو None. الخام أسرع من PNG على المحاكي."""
        if self.raw_ok:
            rc, data = self.run(["exec-out", "screencap"], timeout=20, binary=True)
            if rc == 0 and len(data) > 16:
                w, h, fmt = struct.unpack("<III", data[:12])
                n = w * h * 4
                if 0 < w < 8000 and 0 < h < 8000 and fmt in (1, 2) and len(data) >= n + 12:
                    off = len(data) - n            # ترويسة 12 أو 16 بايت حسب الإصدار
                    arr = np.frombuffer(data, dtype=np.uint8, count=n, offset=off).reshape(h, w, 4)
                    self.W, self.H = w, h
                    self.raw_fails = 0
                    return Image.fromarray(np.ascontiguousarray(arr[:, :, :3]))
            self.raw_fails = getattr(self, "raw_fails", 0) + 1
            if self.raw_fails >= 3:                # 3 إخفاقات متتالية: PNG دائماً
                self.raw_ok = False
        rc, data = self.run(["exec-out", "screencap", "-p"], timeout=25, binary=True)
        if rc != 0 or not data:
            return None
        try:
            im = Image.open(io.BytesIO(data))
            im.load()
            self.W, self.H = im.size
            return im.convert("RGB")
        except Exception:
            return None

    def focus(self) -> str:
        return self.sh("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'", timeout=20)

    def launch(self):
        self.sh("monkey -p %s -c android.intent.category.LAUNCHER 1" % PKG, timeout=30)

    def force_stop(self):
        self.sh("am force-stop %s" % PKG, timeout=20)

    def installed(self) -> bool:
        return ("package:%s" % PKG) in self.sh("pm list packages %s" % PKG)

    def start_logcat(self, path):
        try:
            self.run(["logcat", "-c"], timeout=10)
            f = open(path, "wb")
            self.logcat = subprocess.Popen(self._cmd(["logcat", "-v", "time"]), stdout=f,
                                           stderr=subprocess.DEVNULL)
        except OSError:
            self.logcat = None


# ============================================================== الرؤية
class Vision:
    """غلاف آمن حول vision.py: أي استثناء يُسجَّل ويعيد قيمة افتراضية."""

    def __init__(self, mod, out: Out):
        self.m = mod
        self.out = out
        self.errs = Counter()

    def _safe(self, name, *a, default=None):
        fn = getattr(self.m, name, None)
        if fn is None:
            return default
        try:
            return fn(*a)
        except Exception as e:                       # noqa: BLE001
            self.errs[name] += 1
            n = self.errs[name]
            if n <= 3 or n % 50 == 0:
                self.out.log("خطأ في vision.%s (%d): %r" % (name, n, e))
                if n == 1:
                    self.out.log(traceback.format_exc(limit=4).replace("\n", " | "))
            return default

    def classify(self, fr: Frame) -> str:
        k = self._safe("classify", fr.arr, default="unknown")
        return k if isinstance(k, str) else "unknown"

    def parse(self, fr: Frame):
        st = self._safe("parse_level", fr.arr)
        if not isinstance(st, dict) or not isinstance(st.get("tubes"), list):
            return None
        tubes = []
        for t in st["tubes"]:
            try:
                tubes.append({"x": int(t["x"]), "y": int(t["y"]), "cap": int(t.get("cap") or 4),
                              "layers": [c if isinstance(c, str) else "?" for c in (t.get("layers") or [])],
                              "tall": bool(t.get("tall", False)), "lifted": bool(t.get("lifted", False))})
            except (KeyError, TypeError, ValueError):
                return None
        return {"tubes": tubes, "warnings": list(st.get("warnings") or [])}

    @staticmethod
    def _pt(p):
        if p is None:
            return None
        try:
            return int(p[0]), int(p[1])
        except (TypeError, ValueError, IndexError):
            return None

    def button(self, fr):
        return self._pt(self._safe("find_button", fr.arr))

    def close(self, fr):
        return self._pt(self._safe("find_close", fr.arr))

    def level_number(self, fr):
        n = self._safe("level_number", fr.arr)
        return n if isinstance(n, int) and 0 < n < 100000 else None

    def boosters(self, fr):
        """مواضع الأدوات من اليسار: تراجع، خلط، قارورة (إحداثيات الارتفاع 1000)."""
        pts = self._safe("find_boosters", fr.arr)
        if isinstance(pts, (list, tuple)) and len(pts) >= 2:
            pts = [self._pt(p) for p in pts]
            if all(pts):
                return {"undo": pts[0], "shuffle": pts[len(pts) // 2], "add": pts[-1]}
        try:
            a = fr.arr
            H, W = a.shape[:2]
            y0, y1 = int(0.76 * H), int(0.95 * H)
            pm = self.m.purple_btn_mask(a[y0:y1])
            bs = [b for b in self.m._rect_blobs(pm, W, H)
                  if 0.10 * W <= b["w"] <= 0.17 * W and 0.10 * W <= b["h"] <= 0.17 * W]
            bs.sort(key=lambda b: b["x"])
            if len(bs) >= 2:
                pts = [(int(round(b["x"])), int(round(b["y"] + y0))) for b in bs]
                return {"undo": pts[0], "shuffle": pts[len(pts) // 2], "add": pts[-1]}
        except Exception:                               # noqa: BLE001
            pass
        return dict(BOOSTER_DEFAULT)


def load_vision(path=None):
    if path:
        spec = importlib.util.spec_from_file_location("vision", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    import vision  # noqa: F401
    return sys.modules["vision"]


# ============================================================== أدوات الحالة
def layers_of(st):
    return [tuple(t["layers"]) for t in st["tubes"]]


def compare(prev, expected, cur):
    """('nochange'|'ok'|'different', [(قارورة، موضع، لون) لكل طبقة انكشفت]).
    'ok' = كما توقّع النموذج؛ "?" في المتوقَّع قد يصير لوناً (كشف)، ولون متوقَّع
    من الذاكرة قد يبقى "?" في اللعبة."""
    lp, lc = layers_of(prev), layers_of(cur)
    if len(lp) == len(lc) and lp == lc:
        return "nochange", []
    if expected is not None:
        le = layers_of(expected)
        if len(le) == len(lc):
            revealed = []
            for k, (te, tc) in enumerate(zip(le, lc)):
                if len(te) != len(tc):
                    break
                bad = False
                for p, (a, b) in enumerate(zip(te, tc)):
                    if a == b:
                        continue
                    if a == "?" and b != "?":
                        revealed.append((k, p, b))
                        continue
                    if b == "?":
                        continue
                    bad = True
                    break
                if bad:
                    break
            else:
                return "ok", revealed
    return "different", []


def with_memory(st, memory):
    """نسخة من الحالة تُستبدل فيها الطبقات المخفية التي رأينا لونها من قبل
    (بعد تراجع أو إعادة المرحلة؛ الطبقة المخفية لا تتحرّك فموضعها ثابت)."""
    if not memory:
        return st
    tubes = []
    changed = False
    for k, t in enumerate(st["tubes"]):
        L = list(t["layers"])
        for p, c in enumerate(L):
            if c == "?" and (k, p) in memory:
                L[p] = memory[(k, p)]
                changed = True
        d = dict(t)
        d["layers"] = L
        tubes.append(d)
    if not changed:
        return st
    out = dict(st)
    out["tubes"] = tubes
    return out


def color_counts(st):
    return Counter(c for t in st["tubes"] for c in t["layers"])


def compatible(old, new, extra_tubes=0) -> bool:
    """هل `new` استمرار للغز `old` نفسه (لا مرحلة جديدة)؟ الألوان لا تتغيّر بالحركات."""
    no, nn = len(old["tubes"]), len(new["tubes"])
    if not (no - 1 <= nn <= no + 1 + extra_tubes):
        return False
    co, cn = color_counts(old), color_counts(new)
    to, tn = sum(co.values()), sum(cn.values())
    if abs(to - tn) > 1:
        return False
    lost = sum(max(0, v - cn.get(c, 0)) for c, v in co.items() if c != "?")
    return lost <= 2


def suspicious_counts(st) -> bool:
    """هل أعداد الألوان الظاهرة مستحيلة؟ (لون عادي ليس مضاعفاً للسعة المعتادة بلا مخفي،
    أو أكثر من سعة أي قارورة)."""
    tubes = st["tubes"]
    if not tubes:
        return False
    base = Counter(t["cap"] for t in tubes).most_common(1)[0][0]
    cnt = color_counts(st)
    hidden = cnt.pop("?", 0)
    giant = {t["layers"][0] for t in tubes if t["cap"] > base and t["layers"]}
    for c, n in cnt.items():
        if c in giant:
            continue
        if n > base and n % base != 0:
            return True
        if not hidden and n % base != 0:
            return True
    return False


def lifted_index(st):
    """القارورة المرفوعة (مختارة) إن وُجدت: من vision ("lifted") أو بفرق y في صفّها."""
    for k, t in enumerate(st["tubes"]):
        if t.get("lifted"):
            return k
    tubes = st["tubes"]
    if len(tubes) < 3:
        return None
    base = Counter(t["cap"] for t in tubes).most_common(1)[0][0]
    normal = sorted([(k, t) for k, t in enumerate(tubes) if t["cap"] == base and not t.get("tall")],
                    key=lambda kt: kt[1]["y"])
    rows = []
    for k, t in normal:
        if rows and abs(t["y"] - rows[-1][-1][1]["y"]) < 60:
            rows[-1].append((k, t))
        else:
            rows.append([(k, t)])
    for row in rows:
        if len(row) < 3:
            continue
        ys = sorted(t["y"] for _, t in row)
        med = ys[len(ys) // 2]
        for k, t in row:
            if med - t["y"] > 18:
                return k
    return None


def compact_state(st):
    return [{"x": t["x"], "y": t["y"], "cap": t["cap"], "layers": t["layers"]} for t in st["tubes"]]


class LevelCtx:
    def __init__(self, n, st, t0):
        self.n = n
        self.start_state = st
        self.last_state = st
        self.t0 = t0
        self.moves = 0
        self.fails = 0                 # إخفاقات متتالية
        self.bad = {}                  # state_key -> {(i,j)}
        self.ban = set()               # حركات فشلت مرتين في هذه المرحلة
        self.badcount = Counter()
        self.visited = set()
        self.plan = None
        self.plan_key = None
        self.pending = None            # (prev_state, (i,j), expected, retries)
        self.boosters = []
        self.undos = 0
        self.stuck = 0
        self.stuck_shots = 0
        self.maybe_won = False
        self.solved_since = None
        self.merge_tries = 0
        self.lift_fixes = 0
        self.incompat = 0
        self.extra_tubes = 0
        self.random_moves = 0
        self.reparse = 0
        self.attempts = Counter()      # (state_key، حركة) -> عدد المحاولات
        self.active = True
        self.result = None
        self.start_sig = solver.state_key(st)
        self.memory = {}               # (قارورة، موضع) -> لون طبقة مخفية انكشفت

    def bad_for(self, key):
        return set(self.bad.get(key, set())) | self.ban


# ============================================================== المحرّك
class Bot:
    def __init__(self, dev: Device, vis: Vision, out: Out, minutes: float, git=True):
        self.dev = dev
        self.vis = vis
        self.out = out
        self.git_enabled = git
        self.t_start = time.time()
        self.deadline = self.t_start + minutes * 60
        self.levels_done = 0
        self.lv: LevelCtx | None = None
        self.expect_new = True
        self.unknown_streak = 0
        self.warn_retries = 0
        self.unknown_since = 0.0
        self.unknown_acts = 0
        self.last_unknown_shot = 0.0
        self.unknown_shots = 0
        self.last_focus_check = 0.0
        self.last_state_write = 0.0
        self.last_kind = None
        self.close_frame = None        # آخر نافذة X بعد آخر زرّ (نافذة «ميزة جديدة» قبل المرحلة)
        self.just_won_at = 0.0
        self.close_waits = 0
        self.paused = False
        self.stop = False
        self.cmdq: queue.Queue = queue.Queue()
        self.last_seq = None
        self.git_lock = threading.Lock()
        self.last_publish = time.time()
        self.memory_by_sig = {}        # ذاكرة الطبقات المكشوفة لكل مرحلة (تبقى بعد إعادتها)
        self.airplane_on = None
        self.level_hint = None         # رقم المرحلة التالية كما قرأته الرؤية من زرّ الواجهة
        self.pub_ok = False
        self.copied_sig = {}           # اسم الملف -> (الحجم، الوقت) عند آخر نسخ إلى شجرة النشر
        self.pushed_sig = {}           # ... عند آخر رفع ناجح
        self.hashes = []               # بصمات الشاشات غير اللغز المعروفة
        self.new_count = 0
        self.kinds = Counter()
        self.repeat = (None, 0)        # (بصمة آخر شاشة زرّ/X، عدد تكرارها)
        self.repeat_shots = 0
        self.repeat_escalations = 0
        self.stuck_total = 0
        self.loading_since = None      # منذ متى تظهر شاشة التحميل (None: لا تظهر)
        self.pause_home = False        # أمر pause_home: يتوقف عند الواجهة الرئيسية التالية بدل ضغط «Level N»
        self.last_arrow_tap = 0.0      # آخر لمس لهدف سهم تعليم
        self.arrow_taps = 0            # محاولات السهم في الشاشة المجهولة الحالية
        self.arrow_shots = 0
        self.net_required = False      # ظهرت نافذة «No internet connection»: لا وضع طيران بعدها
        self.last_daily_log = 0.0
        self.daily_hashes = []         # بصمات وسط نافذة «Daily Challenge» (تقويم ولغز بعدّاد): تُغلق ولا يلعبها البوت
        for p in sorted((HERE / "testdata").glob("daily_popup*.jpg")):
            try:
                self.daily_hashes.append(center_hash(Frame(Image.open(p))))
            except Exception:                           # noqa: BLE001
                pass
        self.last_nonet_log = 0.0
        self.nonet_hashes = []         # بصمات وسط نافذة «لا يوجد إنترنت» (النافذة معتمة فلا تتأثر بما خلفها)
        for p in sorted((HERE / "testdata").glob("nonet_*.jpg")):
            try:
                self.nonet_hashes.append(center_hash(Frame(Image.open(p))))
            except Exception:                           # noqa: BLE001
                pass
        self.loading_hashes = []       # بصمات شاشة التحميل («Loading.»): تُنتظر بلا نقر ولا رجوع
        for p in sorted((HERE / "testdata").glob("loading_*.jpg")):
            try:
                self.loading_hashes.append(dhash(Frame(Image.open(p))))
            except Exception:                           # noqa: BLE001
                pass
        self._load_known_hashes()

    # ------------------------------------------------ أدوات عامة
    def log(self, msg):
        self.out.log(msg)

    def elapsed_min(self):
        return (time.time() - self.t_start) / 60.0

    def grab(self):
        im = self.dev.screencap()
        if im is None:
            return None
        return Frame(im)

    def tap(self, pt):
        if pt:
            self.dev.tap_std(pt[0], pt[1])

    def _load_known_hashes(self):
        for p in (HERE / "known_screens.json",):
            try:
                for h in json.loads(p.read_text(encoding="utf-8")):
                    self.hashes.append(hex_hash(h))
            except (OSError, ValueError):
                pass
        for p in sorted(self.out.dir.glob("new_*.jpg")):
            try:
                self.hashes.append(dhash(Frame(Image.open(p))))
                self.new_count += 1
            except Exception:                           # noqa: BLE001
                pass

    def is_loading(self, fr: Frame) -> bool:
        """شاشة التحميل (شعار اللعبة و«Loading.»): بصمتها قريبة جداً من الصورة المرجعية (المسافة صفر في
        اللقطات الحقيقية، وأقرب شاشة أخرى أكثر من 70 من 256)."""
        if not self.loading_hashes:
            return False
        h = dhash(fr)
        return any(int(np.count_nonzero(h != r)) <= 36 for r in self.loading_hashes)

    def is_nonet(self, fr: Frame) -> bool:
        """نافذة «No internet connection» وزرّ Retry (المسافة صفر في اللقطة الحقيقية، وأقرب شاشة أخرى 93 من 256)."""
        if not self.nonet_hashes:
            return False
        h = center_hash(fr)
        return any(int(np.count_nonzero(h != r)) <= 30 for r in self.nonet_hashes)

    def is_daily_popup(self, fr: Frame) -> bool:
        """نافذة «Daily Challenge» (من المرحلة 30): تقويم وزرّ «Play November 22». لغزها صفّ قوارير طويلة جداً بعدّاد 3 دقائق
        لا تقرؤه الرؤية، فيُغلق بزرّ X بدل الدخول (المسافة صفر في اللقطة الحقيقية، وأقرب شاشة أخرى 102 من 256)."""
        if not self.daily_hashes:
            return False
        h = center_hash(fr)
        return any(int(np.count_nonzero(h != r)) <= 30 for r in self.daily_hashes)

    def handle_nonet(self, fr: Frame):
        """النسخ الحديثة تشترط الإنترنت: يُلغى وضع الطيران (ولا يعود في هذا التشغيل) ثم يُضغط Retry."""
        now = time.time()
        if now - self.last_nonet_log > 60:
            self.last_nonet_log = now
            self.log("نافذة «لا يوجد إنترنت»: إلغاء وضع الطيران وضغط Retry")
        self.net_required = True
        if self.airplane_on:
            self.airplane(False)
            time.sleep(6)
        self.tap(self.vis.button(fr) or (236, 630))
        time.sleep(4)

    def same_screen(self, fr: Frame) -> int:
        """عدد مرات تكرار الشاشة نفسها (بصمة) على التوالي."""
        h = dhash(fr)
        last, n = self.repeat
        if last is not None and int(np.count_nonzero(h != last)) <= 8:
            self.repeat = (last, n + 1)
        else:
            self.repeat = (h, 1)
        return self.repeat[1]

    def save_repeat(self, fr, kind):
        if self.repeat_shots < 20:
            self.repeat_shots += 1
            self.out.save_jpg("repeat_%02d_%s.jpg" % (self.repeat_shots, kind), fr.pil)

    def novelty(self, fr: Frame, kind: str):
        if kind == "level":
            return
        h = dhash(fr)
        if self.hashes:
            d = min(int(np.count_nonzero(h != k)) for k in self.hashes)
            if d <= NOVEL_DIST:
                return
        self.hashes.append(h)
        self.new_count += 1
        name = "new_%03d_%s.jpg" % (self.new_count, kind)
        if self.out.save_jpg(name, fr.pil):
            self.log("شاشة جديدة لم تُرَ من قبل: %s" % name)

    # ------------------------------------------------ git والتحكم عن بعد
    def git(self, *args, timeout=60, cwd=None):
        try:
            p = subprocess.run(["git"] + list(args), cwd=str(cwd or ROOT), stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=timeout)
            return p.returncode, p.stdout.decode("utf-8", "replace")
        except (subprocess.TimeoutExpired, OSError) as e:
            return 1, str(e)

    def setup_publisher(self):
        """شجرة عمل git منفصلة للنشر: تُنسخ إليها research/emu/out ثم commit/rebase/push،
        فلا تُلمس شجرة العمل الأصلية ولا تتوقف الحلقة أثناء مشكلات الشبكة."""
        if not self.git_enabled:
            return
        with self.git_lock:
            if PUB_DIR.exists():
                shutil.rmtree(PUB_DIR, ignore_errors=True)
            self.git("worktree", "prune")
            rc, o = self.git("worktree", "add", "--detach", str(PUB_DIR), "HEAD", timeout=120)
        self.pub_ok = rc == 0
        if not self.pub_ok:
            self.log("تعذّر إنشاء شجرة النشر (%s)؛ النشر من الشجرة الأصلية" % o.strip()[-120:])

    def _sync_out(self, force=False):
        """ينسخ الملفات الجديدة أو المعدّلة منذ آخر نسخ (أو منذ آخر رفع ناجح مع force).
        ملف حذفه صاحب المشروع من الفرع لا يُعاد ما لم يتغيّر محلياً."""
        dst = PUB_DIR / OUT_REL
        dst.mkdir(parents=True, exist_ok=True)
        ref = self.pushed_sig if force else self.copied_sig
        with self.out.lock:
            for p in self.out.dir.iterdir():
                if p.name.startswith(".") or not p.is_file():
                    continue
                st = p.stat()
                sig = (st.st_size, st.st_mtime_ns)
                if ref.get(p.name) != sig:
                    shutil.copy2(p, dst / p.name)
                    self.copied_sig[p.name] = sig

    def fetch_cmd(self):
        """يقرأ cmd.txt من origin (بلا لمس شجرة العمل). يعيد (seq، الأسطر) أو None."""
        with self.git_lock:
            rc, _ = self.git("fetch", "-q", "origin", CFG["branch"], timeout=60)
            if rc != 0:
                return None
            rc, txt = self.git("show", "FETCH_HEAD:%s" % CMD_REL, timeout=20)
        if rc != 0:
            return (0, [])
        lines = [ln.strip() for ln in txt.splitlines()]
        lines = [ln for ln in lines if ln and not ln.startswith("#")]
        seq = 0
        if lines and lines[0].split()[0] == "seq":
            try:
                seq = int(lines[0].split()[1])
            except (IndexError, ValueError):
                seq = 0
            lines = lines[1:]
        return seq, lines

    def poll_remote(self):
        r = self.fetch_cmd()
        if r is None:
            return
        seq, lines = r
        if self.last_seq is None:
            self.last_seq = seq
            self.log("التحكم عن بعد: seq الحالي %d (يُعتبر منفَّذاً)" % seq)
            return
        if seq > self.last_seq:
            self.last_seq = seq
            self.cmdq.put((seq, lines))

    def publish(self, msg):
        if not self.git_enabled:
            return False
        if not self.pub_ok:
            return self.publish_inplace(msg)
        with self.git_lock:
            self._sync_out()
            g = lambda *a, **k: self.git(*a, cwd=PUB_DIR, **k)   # noqa: E731
            g("add", "-A", OUT_REL)
            g("commit", "-q", "-m", msg)
            for _ in range(6):
                rc, _o = g("fetch", "-q", "origin", CFG["branch"], timeout=120)
                if rc == 0:
                    rc, _o = g("rebase", "-q", "FETCH_HEAD", timeout=120)
                    if rc != 0:                       # تعارض: نسخة الفرع ثم ملفاتنا فوقها
                        g("rebase", "--abort")
                        g("reset", "-q", "--hard", "FETCH_HEAD")
                        self._sync_out(force=True)
                        g("add", "-A", OUT_REL)
                        g("commit", "-q", "-m", msg)
                    rc, _o = g("push", "-q", "origin", "HEAD:%s" % CFG["branch"], timeout=120)
                    if rc == 0:
                        self.pushed_sig = dict(self.copied_sig)
                        self.last_publish = time.time()
                        return True
                time.sleep(4)
        self.log("فشل الرفع")
        return False

    def publish_inplace(self, msg):
        with self.out.lock, self.git_lock:
            self.git("add", "-A", OUT_REL)
            rc, _ = self.git("commit", "-q", "-m", msg)
            if rc != 0:
                return
            for _ in range(6):
                rc1, o1 = self.git("-c", "rebase.autoStash=true", "pull", "-q", "--rebase",
                                   "origin", CFG["branch"], timeout=120)
                if rc1 != 0:
                    self.git("rebase", "--abort")
                if rc1 == 0:
                    rc2, o2 = self.git("push", "-q", "origin", "HEAD:%s" % CFG["branch"], timeout=120)
                    if rc2 == 0:
                        self.last_publish = time.time()
                        return
                time.sleep(4)
        self.log("فشل الرفع")

    def remote_thread(self):
        while not self.stop:
            try:
                self.poll_remote()
                if time.time() - self.last_publish > CFG["publish_sec"]:
                    self.write_state()
                    self.publish("بوت المحاكي: %d مرحلة مكتملة (%.0f دقيقة)"
                                 % (self.levels_done, self.elapsed_min()))
                    self.last_publish = time.time()
            except Exception as e:                      # noqa: BLE001
                self.log("خطأ في خيط التحكم: %r" % e)
            for _ in range(int(CFG["poll_sec"] * 2)):
                if self.stop:
                    break
                time.sleep(0.5)

    def run_commands(self):
        while True:
            try:
                seq, lines = self.cmdq.get_nowait()
            except queue.Empty:
                return
            self.log("تنفيذ أوامر الدفعة %d: %s" % (seq, " ; ".join(lines)[:300]))
            for ln in lines:
                a = ln.split()
                if not a:
                    continue
                c = a[0].lower()
                try:
                    if c == "pause":
                        self.paused = True
                    elif c == "resume":
                        self.paused = False
                        self.unknown_streak = 0
                    elif c == "stop":
                        self.stop = True
                    elif c == "tap":
                        self.dev.tap(int(a[1]), int(a[2]))
                    elif c == "swipe":
                        self.dev.swipe(int(a[1]), int(a[2]), int(a[3]), int(a[4]),
                                       int(a[5]) if len(a) > 5 else 300)
                    elif c == "wait":
                        time.sleep(min(120.0, float(a[1])))
                    elif c == "shot":
                        fr = self.grab()
                        if fr:
                            self.out.save_jpg("%03d_%s.jpg" % (seq, a[1] if len(a) > 1 else "shot"),
                                              fr.pil, force=True)
                    elif c == "back":
                        self.dev.key(4)
                    elif c == "key":
                        self.dev.key(a[1])
                    elif c == "launch":
                        self.dev.launch()
                    elif c == "relaunch":
                        self.dev.force_stop()
                        time.sleep(2)
                        self.dev.launch()
                    elif c == "logcat":
                        self.dump_logcat("%03d_logcat.txt" % seq, int(a[1]) if len(a) > 1 else 250)
                    elif c == "top":
                        self.out.write("%03d_top.txt" % seq, self.dev.focus() + "\n")
                    elif c == "booster" and len(a) > 1:
                        fr = self.grab()
                        if fr:
                            self.tap(self.vis.boosters(fr).get(a[1]))
                    elif c == "airplane":
                        self.airplane(len(a) < 2 or a[1].lower() in ("on", "1", "true"))
                    elif c == "minutes":
                        self.deadline = self.t_start + float(a[1]) * 60
                        self.log("مهلة جديدة: %s دقيقة من البداية" % a[1])
                    elif c == "pause_home":
                        self.pause_home = True
                        self.log("سيتوقف البوت عند الواجهة الرئيسية التالية (للاستكشاف بالأوامر)")
                    elif c == "update":
                        self.self_update()
                    elif c == "skip":
                        if self.lv:
                            self.lv.plan = None
                            self.lv.bad.clear()
                            self.lv.ban.clear()
                    else:
                        self.log("أمر غير معروف: %s" % ln)
                except (IndexError, ValueError) as e:
                    self.log("أمر غير صالح: %s (%r)" % (ln, e))
            fr = self.grab()
            if fr:
                self.out.save_jpg("%03d_end.jpg" % seq, fr.pil, force=True)
            self.write_state()
            threading.Thread(target=self.publish, args=("بوت المحاكي: الدفعة %d" % seq,),
                             daemon=True).start()

    def self_update(self):
        """أمر «update»: يجلب research/emu/bot من الفرع ثم يعيد تشغيل البوت في العملية نفسها (os.execv) بلا تثبيت ولا
        إعادة تشغيل للعبة، بما بقي من الوقت وعدد المراحل المكتملة. هكذا يُصلَح خطأ في القراءة دون خسارة تقدّم اللعبة."""
        rc, o = self.git("fetch", "-q", "origin", CFG["branch"], timeout=120)
        if rc == 0:
            rc, o = self.git("checkout", "FETCH_HEAD", "--", "research/emu/bot", timeout=60)
        if rc != 0:
            self.log("تعذّر تحديث الكود: %s" % o.strip()[-200:])
            return
        left = max(1.0, (self.deadline - time.time()) / 60.0)
        self.log("تحديث كود البوت وإعادة تشغيله (%.0f دقيقة باقية، %d مرحلة مكتملة)" % (left, self.levels_done))
        self.write_state()
        self.publish("بوت المحاكي: تحديث الكود")
        self.stop = True
        argv = [sys.executable, str(HERE / "driver.py"), "--no-setup", "--minutes", "%.1f" % left,
                "--levels-done", str(self.levels_done)]
        sys.stdout.flush()
        os.execv(sys.executable, argv)

    def dump_logcat(self, name, n):
        try:
            with open("/tmp/bot_logcat.txt", "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            keep = [ln for ln in lines if any(k in ln.lower() for k in (
                "unity", "magicsort", "fatal", "androidruntime", "crash", "anr", "activitymanager",
                "activitytaskmanager"))]
            self.out.write(name, "".join(keep[-n:]))
        except OSError as e:
            self.out.write(name, "logcat unavailable: %r\n" % e)

    # ------------------------------------------------ الحالة
    def write_state(self):
        lv = self.lv
        lines = [
            "done %s" % (self.last_seq if self.last_seq is not None else 0),
            "الحالة: %s" % ("متوقف مؤقتاً" if self.paused else ("انتهى" if self.stop else "يلعب")),
            "مراحل مكتملة: %d" % self.levels_done,
            "الوقت: %.0f دقيقة من %.0f" % (self.elapsed_min(), (self.deadline - self.t_start) / 60),
            "آخر شاشة: %s" % self.last_kind,
            "الشاشات: %s" % dict(self.kinds),
            "صور محفوظة: %d/%d، شاشات جديدة: %d" % (self.out.images, self.out.max_images, self.new_count),
        ]
        if lv:
            hidden = sum(1 for t in lv.last_state["tubes"] for c in t["layers"] if c == "?")
            lines.append("المرحلة الحالية: %d (حركات %d، مخفي %d، إخفاقات %d، أدوات %s، %.1f دقيقة)"
                         % (lv.n, lv.moves, hidden, lv.fails, lv.boosters or "-",
                            (time.time() - lv.t0) / 60))
            lines.append("الحالة المقروءة: %s" % solver.describe(lv.last_state))
        self.out.write("state.txt", "\n".join(lines) + "\n")
        self.last_state_write = time.time()

    # ------------------------------------------------ الإعداد
    def setup(self):
        d = self.dev
        self.log("انتظار الجهاز...")
        d.run(["wait-for-device"], timeout=300)
        for _ in range(60):
            if d.sh("getprop sys.boot_completed") == "1":
                break
            time.sleep(2)
        self.log("الشاشة: %s، الكثافة: %s، ABI: %s" % (d.sh("wm size"), d.sh("wm density"),
                                                     d.sh("getprop ro.product.cpu.abilist")))
        d.start_logcat("/tmp/bot_logcat.txt")
        for c in ("settings put secure immersive_mode_confirmations confirmed",
                  "settings put system screen_off_timeout 2147483647",
                  "svc power stayon true", "input keyevent 82"):
            d.sh(c)
        if not d.installed():
            self.install_game()
        else:
            self.log("اللعبة مثبّتة مسبقاً")
        if CFG["airplane"] == "start":
            self.airplane()
        d.launch()
        self.log("شُغّلت اللعبة؛ انتظار أول شاشة تفاعلية")
        t_end = time.time() + 600
        tos_taps = 0
        last_focus = time.time()
        while time.time() < t_end:
            time.sleep(5)
            if time.time() - last_focus > 30:
                # اللعبة قد تُغلق أثناء أول تحميل (رأيناها مرة): تُشغَّل من جديد بدل انتظار المهلة كلها
                last_focus = time.time()
                f = d.focus()
                if f and PKG not in f:
                    self.log("اللعبة ليست في الواجهة أثناء الإقلاع؛ تشغيلها من جديد")
                    d.launch()
                    continue
            fr = self.grab()
            if fr is None:
                continue
            kind = self.vis.classify(fr)
            if kind != "unknown":
                self.log("أول شاشة: %s" % kind)
                self.out.save_jpg("000_first_%s.jpg" % kind, fr.pil)
                break
            if time.time() > t_end - 540 and tos_taps < 2 and not self.is_loading(fr):
                tos = self.vis._pt(self.vis._safe("find_tos", fr.arr))
                if tos:
                    tos_taps += 1
                    self.tap(tos)
        else:
            self.log("لم تظهر شاشة تفاعلية خلال 10 دقائق؛ يكمل المحرّك على أي حال")
        # after_load: يُفعَّل وضع الطيران عند أول شاشة لغز (اللعبة حمّلت كل شيء)

    def airplane(self, on=True):
        d = self.dev
        self.airplane_on = on
        if on:
            cmds = ("cmd connectivity airplane-mode enable", "settings put global airplane_mode_on 1",
                    "am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true",
                    "svc wifi disable", "svc data disable")
        else:
            cmds = ("cmd connectivity airplane-mode disable", "settings put global airplane_mode_on 0",
                    "am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false",
                    "svc wifi enable", "svc data enable")
        for c in cmds:
            d.sh(c)
        self.log("وضع الطيران: %s" % d.sh("settings get global airplane_mode_on"))

    def install_game(self):
        g = Path(CFG["game_dir"])
        apks = sorted(g.glob("*.apk"))
        if not apks:
            self.log("لا توجد ملفات APK في %s" % g)
            return False
        base = g / ("%s.apk" % PKG)
        if not base.exists():
            base = max([p for p in apks if not p.name.startswith("config.")] or apks,
                       key=lambda p: p.stat().st_size)
        splits = [p for p in apks if p.name.startswith("config.")]
        abi_keys = ("arm64_v8a", "armeabi_v7a", "armeabi", "x86_64", "x86", "mips64", "mips")
        abi_splits = {k: p for p in splits for k in abi_keys if p.name == "config.%s.apk" % k}
        # ملف المعمارية: أول معمارية يدعمها الجهاز (بترتيب abilist) ولها ملف في الحزمة. النسخ الحديثة من اللعبة فيها
        # arm64_v8a وحده، فتحتاج محاكي x86_64 (يترجم arm64 من Android 11)؛ محاكي x86 لا يشغّلها («libmain.so not found»).
        dev_abis = [a.strip().replace("-", "_") for a in self.dev.sh("getprop ro.product.cpu.abilist").split(",") if a.strip()]
        abi = [abi_splits[a] for a in dev_abis if a in abi_splits][:1]
        if not abi:
            self.log("تحذير: لا ملف معمارية يناسب الجهاز (%s) بين %s" % (",".join(dev_abis), sorted(abi_splits)))
        rest = [p for p in splits if p not in abi_splits.values()]
        tries = [[base] + abi + rest, [base] + abi, apks, [base]]
        seen = set()
        for files in tries:
            key = tuple(str(p) for p in files)
            if key in seen:
                continue
            seen.add(key)
            rc, out = self.dev.run(["install-multiple", "-r", "-g"] + [str(p) for p in files],
                                   timeout=400)
            self.log("تثبيت (%s): %s" % (" ".join(p.name for p in files), out.strip()[-160:]))
            if "Success" in out:
                obb = g / "Android" / "obb"
                if obb.exists():
                    self.dev.run(["push", str(obb) + "/.", "/sdcard/Android/obb/"], timeout=400)
                return True
        return False

    # ------------------------------------------------ الحلقة
    def run(self, max_iters=None):
        if self.git_enabled:
            threading.Thread(target=self.remote_thread, daemon=True).start()
        self.write_state()
        iters = 0
        fr = None
        while not self.stop and time.time() < self.deadline:
            iters += 1
            if max_iters is not None and iters > max_iters:
                return                         # للاختبارات: بلا إنهاء
            self.run_commands()
            if self.stop:
                break
            if self.paused:
                if time.time() - self.last_state_write > 30:
                    self.write_state()
                time.sleep(2)
                fr = None
                continue
            try:
                if fr is None:
                    fr = self.grab()
                if fr is None:
                    self.log("فشلت اللقطة؛ إعادة المحاولة")
                    self.dev.run(["wait-for-device"], timeout=60)
                    time.sleep(3)
                    continue
                if self.is_nonet(fr):
                    self.kinds["nonet"] += 1
                    self.handle_nonet(fr)
                    fr = None
                    continue
                if self.is_daily_popup(fr):
                    self.kinds["daily"] += 1
                    if time.time() - self.last_daily_log > 300:
                        self.last_daily_log = time.time()
                        self.out.save_jpg("daily_popup_%s.jpg" % time.strftime("%H%M%S"), fr.pil)
                        self.log("نافذة التحدّي اليومي: إغلاق (لغزه بعدّاد وقوارير طويلة لا يلعبها البوت)")
                    self.tap(self.vis.close(fr) or (422, 96))
                    time.sleep(2)
                    fr = None
                    continue
                kind = self.vis.classify(fr)
                self.kinds[kind] += 1
                self.last_kind = kind
                self.novelty(fr, kind)
                if time.time() - self.last_state_write > 20:
                    self.write_state()
                if kind == "level" and self.airplane_on is None and CFG["airplane"] == "after_load" \
                        and not self.net_required:
                    self.airplane(True)
                if kind in ("button", "close") and self.same_screen(fr) > 6:
                    self.log("الشاشة نفسها (%s) تتكرّر رغم النقر؛ تصعيد" % kind)
                    self.save_repeat(fr, kind)
                    self.dev.key(4) if self.repeat_escalations % 2 == 0 else \
                        self.dev.tap_std(fr.arr.shape[1] // 2, int(STD_H * 0.62))
                    self.repeat_escalations += 1
                    self.repeat = (None, 0)
                    time.sleep(2)
                    fr = None
                    continue
                if kind == "button" and self.pause_home and self.vis._safe("is_home", fr.arr, default=False):
                    self.pause_home = False
                    self.paused = True
                    self.out.save_jpg("home_paused_%s.jpg" % time.strftime("%H%M%S"), fr.pil, force=True)
                    self.log("توقف عند الواجهة الرئيسية (pause_home): الأوامر التالية تستكشف، ثم resume")
                    self.write_state()
                    threading.Thread(target=self.publish, args=("بوت المحاكي: توقف عند الواجهة",), daemon=True).start()
                    fr = None
                    continue
                if kind == "level":
                    fr = self.on_level(fr)
                elif kind == "button":
                    fr = self.on_button(fr)
                elif kind == "close":
                    fr = self.on_close(fr)
                else:
                    fr = self.on_unknown(fr, kind)
            except Exception as e:                      # noqa: BLE001
                self.log("خطأ في الحلقة: %r | %s" % (e, traceback.format_exc(limit=5).replace("\n", " | ")))
                time.sleep(2)
                fr = None
        self.finish()

    def finish(self):
        self.stop = True
        self.log("انتهى البوت: %d مرحلة مكتملة في %.0f دقيقة" % (self.levels_done, self.elapsed_min()))
        fr = self.grab()
        if fr:
            self.out.save_jpg("zz_final.jpg", fr.pil, force=True)
        self.write_state()
        self.publish("بوت المحاكي: النهاية — %d مرحلة مكتملة" % self.levels_done)

    # ------------------------------------------------ المراحل
    def leave_level(self, why):
        lv = self.lv
        if lv is None or not lv.active:
            return
        lv.active = False
        if lv.maybe_won:
            self.win(why)

    def win(self, why, inferred=False):
        lv = self.lv
        if lv is None or lv.result:
            return
        lv.result = "win-inferred" if inferred else "win"
        self.levels_done += 1
        self.just_won_at = time.time()
        self.expect_new = True
        dt = time.time() - lv.t0
        self.log("فوز بالمرحلة %d (%s): %d حركة في %.0f ث، أدوات %s"
                 % (lv.n, why, lv.moves, dt, lv.boosters or "-"))
        self.out.append("levels.jsonl", json.dumps({
            "n": lv.n, "result": lv.result, "moves": lv.moves, "sec": round(dt),
            "boosters": lv.boosters, "undos": lv.undos, "stuck": lv.stuck,
            "start": compact_state(lv.start_state)}, ensure_ascii=False) + "\n")

    def new_level(self, fr, st, n=None):
        n = n or self.vis.level_number(fr) or self.level_hint or (self.levels_done + 1)
        self.level_hint = None
        self.lv = LevelCtx(n, st, time.time())
        self.lv.memory = self.memory_by_sig.setdefault(self.lv.start_sig, {})
        self.expect_new = False
        self.out.save_jpg("L%03d_start.jpg" % n, fr.pil)
        if self.close_frame is not None and time.time() - self.close_frame.t < 30:
            self.out.save_jpg("feat_L%03d.jpg" % n, self.close_frame.pil)
            self.log("نافذة قبل المرحلة %d (ميزة جديدة؟): feat_L%03d.jpg" % (n, n))
        self.close_frame = None
        self.log("بداية المرحلة %d: %d قارورة، سعات %s، مخفي %d"
                 % (n, len(st["tubes"]), sorted(Counter(t["cap"] for t in st["tubes"]).items()),
                    sum(1 for t in st["tubes"] for c in t["layers"] if c == "?")))
        self.log("حالة المرحلة %d: %s" % (n, json.dumps(compact_state(st), ensure_ascii=False)))

    def on_level(self, fr):
        st = self.vis.parse(fr)
        lv = self.lv
        if not st or not st["tubes"]:
            time.sleep(0.8)
            return None
        self.unknown_streak = 0
        self.close_waits = 0
        # لقطة مشكوك فيها (أثناء صبّ/احتفال/يد التعليم): أعد التصوير مرتين ثم اعتمدها
        if st["warnings"] and self.warn_retries < 2:
            self.warn_retries += 1
            time.sleep(0.6)
            return self.grab()
        self.warn_retries = 0
        if lv is None or self.expect_new:
            self.new_level(fr, st)
            lv = self.lv
        elif not compatible(lv.last_state, st, lv.extra_tubes):
            lv.incompat += 1
            if lv.incompat < 2:
                time.sleep(0.8)
                return self.grab()
            ln = self.vis.level_number(fr)       # رقم المرحلة من العنوان إن قُرئ
            same = (ln == lv.n) if ln is not None else \
                (solver.state_key(st) == lv.start_sig and not lv.maybe_won)
            if same:
                self.log("المرحلة %d أُعيدت من البداية (ذاكرة %d طبقة مكشوفة)" % (lv.n, len(lv.memory)))
                self.new_level(fr, st, n=lv.n)
            else:
                self.win("لغز جديد على الشاشة", inferred=not lv.maybe_won)
                self.new_level(fr, st, n=ln)
            lv = self.lv
        lv.incompat = 0
        lv.active = True
        key = solver.state_key(st)

        # ---- التحقق من الحركة السابقة
        moved = lv.pending is not None
        verdict = None
        if lv.pending:
            prev, mv, expected, retries = lv.pending
            if len(st["tubes"]) != len(prev["tubes"]) and retries < 3:
                lv.pending = (prev, mv, expected, retries + 1)
                time.sleep(0.7)
                return self.grab()
            verdict, revealed = compare(prev, expected, with_memory(st, lv.memory))
            if verdict == "ok":
                for (k, p, c) in revealed:
                    lv.memory[(k, p)] = c
            if verdict == "nochange" and retries < 1:
                lv.pending = (prev, mv, expected, retries + 1)
                time.sleep(0.6)
                return self.grab()
            lv.pending = None
            if verdict == "nochange":
                lv.fails += 1
                pk = solver.state_key(prev)
                lv.bad.setdefault(pk, set()).add(mv)
                lv.badcount[mv] += 1
                if lv.badcount[mv] >= 2:
                    lv.ban.add(mv)
                lv.plan = None
                self.log("لا تقدّم بعد الحركة %s (إخفاق %d)" % (mv, lv.fails))
            else:
                lv.fails = 0
                lv.moves += 1
                if verdict != "ok" or revealed:
                    lv.plan = None
                if verdict == "different":
                    self.log("الحالة بعد %s تختلف عن المتوقَّع؛ إعادة التخطيط" % (mv,))
        lv.last_state = st
        stp = with_memory(st, lv.memory)
        lv.visited.add(key)
        lv.visited.add(solver.state_key(stp))

        # ---- قارورة مرفوعة بقيت مختارة (بعد نقرة ضائعة): أنزِلها
        li = lifted_index(st) if (not moved or verdict == "nochange") else None
        if li is not None and lv.lift_fixes < 6:
            lv.lift_fixes += 1
            t = st["tubes"][li]
            self.log("القارورة %d مرفوعة؛ نقرة لإنزالها" % li)
            self.dev.tap_std(t["x"], t["y"])
            time.sleep(0.6)
            return self.grab()

        # ---- محلولة؟ ننتظر نافذة الفوز
        if solver.is_solved(stp):
            lv.maybe_won = True
            if lv.solved_since is None:
                lv.solved_since = time.time()
            if time.time() - lv.solved_since > 8:
                return self.solved_but_running(fr, st)
            time.sleep(1.0)
            return self.grab()
        lv.solved_since = None
        lv.maybe_won = False

        if lv.fails >= 3:
            return self.stuck(fr, st, "3 إخفاقات متتالية")
        if time.time() - lv.t0 > CFG["level_max_min"] * 60 and lv.stuck < 99:
            self.log("المرحلة %d تجاوزت %.0f دقيقة" % (lv.n, CFG["level_max_min"]))
            lv.stuck = 99
            self.save_stuck(fr, "timeout")
            return self.restart_level()

        # ---- التخطيط (بالذاكرة: الطبقات المخفية التي رأيناها من قبل تُعامل كمعروفة)
        key = solver.state_key(stp)
        if not (lv.plan and lv.plan_key == key):
            info = {}
            lv.plan = solver.plan(stp, bad_moves=lv.bad_for(key), avoid=lv.visited,
                                  time_limit=CFG["plan_sec"], info=info)
            lv.plan_key = key
            if lv.moves == 0 or not lv.plan or info.get("mode") not in ("pimc",):
                self.log("خطة المرحلة %d: %d حركة (%s، %s ms)%s"
                         % (lv.n, len(lv.plan), info.get("mode"), info.get("ms"),
                            "" if lv.plan else " — لا حركة مفيدة"))
        if not lv.plan:
            return self.stuck(fr, st, "لا خطة")
        i, j = lv.plan.pop(0)
        return self.do_move(stp, i, j)

    def do_move(self, st, i, j):
        lv = self.lv
        k = (solver.state_key(st), (i, j))
        lv.attempts[k] += 1
        if lv.attempts[k] >= 3:                # الحركة نفسها من الحالة نفسها 3 مرات: سيئة
            lv.bad.setdefault(k[0], set()).add((i, j))
        expected = solver.apply_move(st, i, j)
        a, b = st["tubes"][i], st["tubes"][j]
        if hasattr(self.dev, "tap2_std"):
            self.dev.tap2_std((a["x"], a["y"]), (b["x"], b["y"]), CFG["tap_gap"])
        else:
            self.dev.tap_std(a["x"], a["y"])
            time.sleep(CFG["tap_gap"])
            self.dev.tap_std(b["x"], b["y"])
        lv.pending = (st, (i, j), expected, 0)
        if expected is not None:
            lv.plan_key = solver.state_key(expected)
            if solver.is_solved(expected):
                lv.maybe_won = True
        time.sleep(CFG["pour_wait"])
        return self.grab()

    def save_stuck(self, fr, tag):
        lv = self.lv
        if lv and lv.stuck_shots < 3 and self.stuck_total < 150:
            lv.stuck_shots += 1
            self.stuck_total += 1
            self.out.save_jpg("stuck_L%03d_%d_%s.jpg" % (lv.n, lv.stuck_shots, tag), fr.pil)

    def stuck(self, fr, st, why):
        lv = self.lv
        lv.stuck += 1
        lv.fails = 0
        self.log("المرحلة %d عالقة (%s): %s" % (lv.n, why, solver.describe(st)))
        self.save_stuck(fr, "s%d" % lv.stuck)
        # كل القوارير أحادية اللون ولون مقسوم بين قارورتين: غالباً سعة الطويلة مقروءة أقل
        # من الحقيقة، فجرّب الدمج المباشر قبل الأدوات
        mono = all(len(set(t["layers"])) <= 1 and "?" not in t["layers"] for t in st["tubes"])
        if mono and lv.merge_tries < 6:
            return self.solved_but_running(fr, st)
        # عدد طبقات لون لا يناسب سعة القوارير: قراءة خاطئة غالباً، فأعد التصوير قبل الأدوات
        if suspicious_counts(st) and lv.reparse < 3:
            lv.reparse += 1
            self.log("أعداد الألوان غير منطقية (قراءة خاطئة؟): إعادة التصوير")
            lv.plan = None
            time.sleep(1.0)
            return self.grab()
        bp = self.vis.boosters(fr)
        reset = False
        if "add" not in lv.boosters:
            lv.boosters.append("add")
            self.log("أداة: قارورة إضافية")
            self.tap(bp["add"])
            lv.extra_tubes += 1
            time.sleep(2.0)
            reset = True
        elif "shuffle" not in lv.boosters:
            lv.boosters.append("shuffle")
            lv.memory.clear()                  # الخلط يغيّر مواضع الطبقات
            tgt = self.shuffle_target(st)
            self.log("أداة: خلط ثم اختيار القارورة %s" % (tgt,))
            self.tap(bp["shuffle"])
            time.sleep(1.3)
            if tgt is not None:
                t = st["tubes"][tgt]
                self.dev.tap_std(t["x"], t["y"])
            time.sleep(2.5)
            reset = True
        elif lv.undos < 6:
            lv.undos += 1
            self.log("أداة: تراجع (%d)" % lv.undos)
            self.tap(bp["undo"])
            time.sleep(1.3)
            reset = True
        else:
            return self.random_move(st)
        if reset:
            lv.plan = None
            lv.bad.clear()
            lv.ban.clear()
            lv.badcount.clear()
            lv.pending = None
            lv.lift_fixes = 0
        return self.grab()

    @staticmethod
    def shuffle_target(st):
        best = None
        for k, t in enumerate(st["tubes"]):
            L = t["layers"]
            if not L:
                continue
            runs = sum(1 for p in range(len(L)) if p == 0 or L[p] != L[p - 1] or L[p] == "?")
            if runs <= 1 and len(L) == t["cap"]:
                continue
            sc = runs + L.count("?")
            if best is None or sc > best[0]:
                best = (sc, k)
        return best[1] if best else None

    def random_move(self, st):
        lv = self.lv
        lv.random_moves += 1
        moves = [m for m in solver.legal_moves(st) if m not in lv.ban]
        fresh = []
        for m in moves:
            nxt = solver.apply_move(st, *m)
            if nxt is not None and solver.state_key(nxt) not in lv.visited:
                fresh.append(m)
        pool = fresh or moves
        if not pool:
            self.log("لا حركة قانونية إطلاقاً؛ إعادة المرحلة")
            return self.restart_level()
        m = random.choice(pool)
        self.log("حركة عشوائية %s (%d)" % (m, lv.random_moves))
        if lv.random_moves % 8 == 0:
            lv.undos = 0                       # جرّب التراجع مجدداً لاحقاً
        return self.do_move(st, *m)

    def solved_but_running(self, fr, st):
        """الحلّال يرى اللغز محلولاً واللعبة لم تنتهِ (سعة أو لون مقروء خطأ): جرّب الدمج."""
        lv = self.lv
        lv.merge_tries += 1
        self.save_stuck(fr, "solved")
        tubes = st["tubes"]
        pairs = []
        for i, a in enumerate(tubes):
            for j, b in enumerate(tubes):
                if i != j and a["layers"] and b["layers"] and a["layers"][-1] == b["layers"][-1]:
                    pairs.append((len(a["layers"]), -b["cap"], i, j))
        pairs.sort()
        if pairs and lv.merge_tries <= 2 * len(pairs):
            _, _, i, j = pairs[(lv.merge_tries - 1) % len(pairs)]
            self.log("محلولة بنظر الحلّال واللعبة مستمرة: دمج تجريبي %s" % ((i, j),))
            a, b = tubes[i], tubes[j]
            self.dev.tap_std(a["x"], a["y"])
            time.sleep(CFG["tap_gap"])
            self.dev.tap_std(b["x"], b["y"])
            time.sleep(CFG["pour_wait"])
            lv.solved_since = time.time() - 6
            return self.grab()
        lv.solved_since = None
        return self.stuck(fr, st, "محلولة بنظر الحلّال فقط")

    def restart_level(self):
        """آخر حل: زرّ الرجوع (قد يفتح نافذة الخروج؛ تعالجها الحلقة)."""
        self.dev.key(4)
        time.sleep(2)
        if self.lv:
            self.lv.plan = None
            self.lv.pending = None
            self.lv.t0 = time.time()
        return None

    # ------------------------------------------------ الشاشات الأخرى
    def on_button(self, fr):
        self.unknown_streak = 0
        self.leave_level("button")
        self.close_frame = None
        # زرّ الواجهة «Level N» (أو رأس نافذة الفوز): رقم المرحلة التالية يؤكّد الفوز
        ln = self.vis.level_number(fr)
        if ln is not None:
            lv = self.lv
            if lv is not None and lv.result is None and ln > lv.n:
                self.win("الواجهة تعرض المرحلة %d" % ln, inferred=not lv.maybe_won)
            if lv is None or ln > lv.n:            # رأس نافذة الفوز يعرض المرحلة المنتهية نفسها
                self.level_hint = ln
        pt = self.vis.button(fr)
        if pt:
            self.tap(pt)
            time.sleep(2.0)
        else:
            time.sleep(1.0)
        return None

    def on_close(self, fr):
        self.unknown_streak = 0
        self.leave_level("close")
        self.close_frame = fr                  # آخر صورة للنافذة (بعد اكتمال ظهورها)
        # نافذة الفوز تظهر أولاً بلا Continue: انتظر قبل X
        if time.time() - self.just_won_at < 8 and self.close_waits < 3:
            self.close_waits += 1
            time.sleep(1.5)
            return self.grab()
        self.close_waits = 0
        pt = self.vis.close(fr)
        if pt:
            self.tap(pt)
            time.sleep(1.5)
        else:
            time.sleep(1.0)
        return None

    def on_unknown(self, fr, kind):
        """تحميل، احتفال، متجر، شاشة Android...: انتظار أولاً، ثم تصعيد بطيء بالزمن
        (زرّ الرجوع أثناء التحميل قد يغلق اللعبة، فلا يُضغط قبل 35 ثانية)."""
        self.leave_level(kind)
        now = time.time()
        if self.is_loading(fr):
            # التحميل الأول على المحاكي (ترجمة arm64) يأخذ نحو 6 دقائق: لا نقر ولا رجوع ولا إعادة تشغيل
            if self.loading_since is None:
                self.loading_since = now
                self.log("شاشة التحميل: انتظار بلا نقر")
            if now - self.loading_since < CFG["loading_max_sec"]:
                self.unknown_streak = 0
                time.sleep(5)
                return None
            self.log("التحميل طال أكثر من %.0f دقيقة؛ إعادة تشغيل اللعبة" % (CFG["loading_max_sec"] / 60))
            self.loading_since = None
            self.dev.force_stop()
            time.sleep(2)
            self.dev.launch()
            time.sleep(25)
            return None
        if self.loading_since is not None:
            self.log("انتهى التحميل بعد %.0f ثانية" % (now - self.loading_since))
            self.loading_since = None
        if self.unknown_streak == 0:
            self.unknown_since = now
            self.unknown_acts = 0
        self.unknown_streak += 1
        dur = now - self.unknown_since
        if now - self.last_unknown_shot > 60 and self.unknown_shots < 80 and dur > 6:
            self.last_unknown_shot = now
            self.unknown_shots += 1
            self.out.save_jpg("unknown_%03d.jpg" % self.unknown_shots, fr.pil)
        if now - self.last_focus_check > 20:
            self.last_focus_check = now
            f = self.dev.focus()
            if f and PKG not in f:
                self.log("اللعبة ليست في الواجهة (%s)؛ تشغيلها" % f.replace("\n", " ")[:120])
                self.dev.launch()
                self.unknown_streak = 0
                time.sleep(15)
                return None
            if "Not Responding" in f:
                self.log("نافذة «لا يستجيب»: انتظار")
                self.dev.key(4)
        # تعليم بسهم أصفر يشير إلى ما يجب لمسه (صورة اللاعب قبل «الفرق» مثلاً): يُلمس الهدف بعد ثانيتين من ثبات الشاشة
        if self.unknown_streak == 1:
            self.arrow_taps = 0                # شاشة مجهولة جديدة: محاولات السهم من جديد
        if dur >= 2 and now - self.last_arrow_tap > 4 and self.arrow_taps < 3:
            tgt = self.vis._pt(self.vis._safe("find_tutorial_arrow", fr.arr))
            if tgt:
                # ثلاث محاولات على الأكثر لكل شاشة مجهولة (سهم كاذب لا يمنع التصعيد المعتاد إلى الرجوع وإعادة التشغيل)
                self.arrow_taps += 1
                self.last_arrow_tap = now
                self.log("سهم تعليم: لمس الهدف %s" % (tgt,))
                if self.arrow_shots < 10:
                    self.arrow_shots += 1
                    self.out.save_jpg("tutorial_%02d.jpg" % self.arrow_shots, fr.pil)
                self.tap(tgt)
                time.sleep(2)
                return None
        # الأفعال بحسب مدة بقاء الشاشة مجهولة (كل فعل مرة واحدة في موعده)
        steps = [(25, "tap"), (35, "back"), (65, "tap"), (95, "back"), (125, "tap"), (155, "back")]
        if self.unknown_acts < len(steps) and dur >= steps[self.unknown_acts][0]:
            act = steps[self.unknown_acts][1]
            self.unknown_acts += 1
            if act == "tap":
                self.tap(TOS_POINT if self.elapsed_min() < 8 else (fr.arr.shape[1] // 2, int(STD_H * 0.62)))
            else:
                self.dev.key(4)
            time.sleep(2)
            return None
        if dur >= 180:
            self.log("شاشة مجهولة منذ 3 دقائق؛ إعادة تشغيل اللعبة")
            self.dev.force_stop()
            time.sleep(2)
            self.dev.launch()
            self.unknown_streak = 0
            time.sleep(25)
            return None
        time.sleep(3)
        return None


# ============================================================== التجربة الجافة
def offline(folder, vis_mod, limit=None, verbose=False, plan_sec=None):
    """يشغّل classify/parse/plan على لقطات محفوظة بلا adb، ويطبع سطراً لكل صورة."""
    out = Out(Path(os.environ.get("BOT_OFFLINE_OUT", "/tmp/bot_offline_out")), 0, quiet=True)
    vis = Vision(vis_mod, out)
    files = sorted(glob.glob(os.path.join(folder, "*.jpg")) + glob.glob(os.path.join(folder, "*.png")))
    if limit:
        files = files[:limit]
    kinds = Counter()
    hashes = []
    novel = 0
    plans = {"level": 0, "parsed": 0, "planned": 0, "solved_sim": 0, "stuck": 0, "solved": 0}
    max_ms = 0.0
    tot_ms = 0.0
    for f in files:
        name = os.path.basename(f)
        try:
            fr = Frame(Image.open(f))
        except Exception as e:                          # noqa: BLE001
            print("%-30s تعذّرت القراءة: %r" % (name, e))
            continue
        t = time.perf_counter()
        kind = vis.classify(fr)
        kinds[kind] += 1
        line = "%-30s %-8s" % (name, kind)
        if kind != "level":
            h = dhash(fr)
            d = min([int(np.count_nonzero(h != k)) for k in hashes] or [999])
            if d > NOVEL_DIST:
                hashes.append(h)
                novel += 1
                line += " [جديدة d=%s]" % (d if d < 999 else "-")
        if kind == "level":
            plans["level"] += 1
            st = vis.parse(fr)
            if not st or not st["tubes"]:
                line += " parse=فشل"
            else:
                plans["parsed"] += 1
                caps = Counter(t_["cap"] for t_ in st["tubes"])
                hid = sum(1 for t_ in st["tubes"] for c in t_["layers"] if c == "?")
                info = {}
                t1 = time.perf_counter()
                mv = solver.plan(st, info=info, time_limit=plan_sec or CFG["plan_sec"])
                ms = (time.perf_counter() - t1) * 1000
                max_ms = max(max_ms, ms)
                tot_ms += ms
                sim = ""
                if solver.is_solved(st):
                    plans["solved"] += 1
                    sim = " (محلولة)"
                elif mv:
                    plans["planned"] += 1
                    cur = st
                    for (i, j) in mv:
                        cur = solver.apply_move(cur, i, j)
                        if cur is None:
                            break
                    if cur is not None and solver.is_solved(cur):
                        plans["solved_sim"] += 1
                        sim = " (تحلّها كاملة)"
                    a, b = st["tubes"][mv[0][0]], st["tubes"][mv[0][1]]
                    sim += " أول نقرتين: (%d,%d)->(%d,%d) جهاز %s->%s" % (
                        a["x"], a["y"], b["x"], b["y"], to_dev(a["x"], a["y"]), to_dev(b["x"], b["y"]))
                else:
                    plans["stuck"] += 1
                    sim = " (لا حركة)"
                line += " قوارير=%d سعات=%s مخفي=%d تحذيرات=%d خطة=%d %s %.0fms%s" % (
                    len(st["tubes"]), dict(caps), hid, len(st["warnings"]), len(mv),
                    info.get("mode"), ms, sim)
                if verbose:
                    line += "\n      " + solver.describe(st) + "\n      moves=" + str(mv[:12])
        elif kind == "button":
            pt = vis.button(fr)
            line += " زر=%s جهاز=%s" % (pt, to_dev(*pt) if pt else None)
        elif kind == "close":
            pt = vis.close(fr)
            line += " X=%s جهاز=%s" % (pt, to_dev(*pt) if pt else None)
        line += "  [%.0fms]" % ((time.perf_counter() - t) * 1000)
        print(line)
    print("\nالملخص: %d صورة، الأنواع %s، شاشات غير اللغز المختلفة (بصمة) %d"
          % (len(files), dict(kinds), novel))
    print("اللغز: %d لقطة، قُرئت %d، محلولة أصلاً %d، لها خطة %d (منها تحلّ اللغز كاملاً في النموذج %d)، "
          "بلا حركة %d؛ زمن الحلّال: أقصى %.0f ms، متوسط %.0f ms"
          % (plans["level"], plans["parsed"], plans["solved"], plans["planned"], plans["solved_sim"],
             plans["stuck"], max_ms, tot_ms / max(1, plans["parsed"])))
    if vis.errs:
        print("أخطاء vision: %s" % dict(vis.errs))
    return 0


def to_dev(x, y, H=2280, W=1080):
    s = H / float(STD_H)
    return max(0, min(W - 1, int(round(x * s)))), max(0, min(H - 1, int(round(y * s))))


def make_known_hashes(folder, vis_mod, path):
    """يولّد known_screens.json من لقطات قديمة (الشاشات غير اللغز فقط)."""
    vis = Vision(vis_mod, Out(Path("/tmp/bot_offline_out"), 0, quiet=True))
    hs = []
    for f in sorted(glob.glob(os.path.join(folder, "*.jpg"))):
        fr = Frame(Image.open(f))
        if vis.classify(fr) == "level":
            continue
        h = dhash(fr)
        if all(int(np.count_nonzero(h != k)) > NOVEL_DIST for k in hs):
            hs.append(h)
    Path(path).write_text(json.dumps([hash_hex(h) for h in hs]), encoding="utf-8")
    print("كُتبت %d بصمة في %s" % (len(hs), path))


# ============================================================== الدخول
def main(argv=None):
    ap = argparse.ArgumentParser(description="بوت Magic Sort الذاتي")
    ap.add_argument("--offline", metavar="DIR", help="تجربة جافة على لقطات محفوظة بلا adb")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--vision", metavar="PATH", help="مسار بديل لـ vision.py (للاختبار)")
    ap.add_argument("--minutes", type=float, default=None)
    ap.add_argument("--levels-done", type=int, default=0, help="عدد المراحل المكتملة قبل «update»")
    ap.add_argument("--no-git", action="store_true", help="بلا نشر git (تجربة محلية مع adb)")
    ap.add_argument("--no-setup", action="store_true", help="بلا تثبيت/تشغيل (اللعبة تعمل)")
    ap.add_argument("--make-known", metavar="DIR", help="توليد known_screens.json من لقطات")
    ap.add_argument("--serial", default=None)
    args = ap.parse_args(argv)

    vis_mod = load_vision(args.vision)
    if args.make_known:
        make_known_hashes(args.make_known, vis_mod, HERE / "known_screens.json")
        return 0
    if args.offline:
        return offline(args.offline, vis_mod, args.limit, args.verbose)

    out = Out(ROOT / OUT_REL, CFG["max_images"])
    dev = Device(args.serial)
    git_on = not args.no_git
    bot = Bot(dev, Vision(vis_mod, out), out, args.minutes or CFG["minutes"], git=git_on)
    bot.levels_done = args.levels_done
    if git_on and os.environ.get("GITHUB_ACTIONS") == "true":
        bot.git("config", "user.name", "emu-bot")
        bot.git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    bot.log("بدء البوت: %.0f دقيقة، الفرع %s" % (args.minutes or CFG["minutes"], CFG["branch"]))
    if git_on:
        bot.setup_publisher()
        bot.poll_remote()                      # يسجّل الـ seq الحالي كمنفَّذ
    if not args.no_setup:
        bot.setup()
    bot.publish("بوت المحاكي: بدأ اللعب")
    bot.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
