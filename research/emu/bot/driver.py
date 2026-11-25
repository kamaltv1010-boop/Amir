#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""المحرّك الذاتي لبوت Magic Sort (بحث فقط، يعمل على مشغّل GitHub بجوار المحاكي).

الحلقة: لقطة adb -> تصغير إلى ارتفاع 1000 -> vision.classify -> فعل:
  level  : parse_level ثم solver.plan، وتُنفَّذ حركة واحدة (نقر المصدر ثم الهدف)،
           ثم لقطة جديدة للتحقق (الطبقات المخفية تنكشف). لا تقدّم = حركة سيئة؛
           بعد 3 إخفاقات: لقطة stuck_* ثم الأدوات (قارورة إضافية، ثم خلط، ثم تراجع).
  button : نقر find_button.   close : نقر find_close.
  lives  : نافذة «More Lives»: «Refill» مرة واحدة إن كفى الرصيد ثمنه (900)، وإلا X ثم لا يُضغط زرّ المرحلة (ولا يُلمس
           شيء في شاشة مجهولة) حتى موعد الروح القادمة (فحص كل دقيقة). لا يُلمس زرّ الإعلان «+1 Life» ولا «Free Lives» أبداً.
  unknown: لقطة unknown_* (محدودة)، ثم انتظار/رجوع/نقر الوسط (لا فوق زرّ يصرف العملات)/إعادة تشغيل اللعبة. ومنها
           «No Available Moves»: «Give Up» (ثم محاولة جديدة)، أو «Play On» (قارورة بـ 900) مرة في المحاولة إن كفى الرصيد
           ثمنه واحتياطي «Refill» بعده (900) وكانت المرحلة صعبة أو صعبة جداً بعنوانها أو أُخفقت مرتين في هذا التشغيل.
           والإعلانات المفروضة (on_ad: الأسود، والتجريبي الأبيض AppLovin بعد عدّه التنازلي) تُغلق فقط بالرجوع أو زرّ X في زاوية
           علوية ثم إعادة اللعبة بعد مهلة؛ وشعار «MAGIC SORT» فوق لوحة معتمة (on_logo) يُنتظر ثم رجوع ثم إعادة اللعبة.
رقم المرحلة من عنوانها (العادية والصعبة والصعبة جداً)؛ ولا «فوز» بتغيّر اللوحة وحده إلا إن ظنّ البوت اللغز محلولاً: غير
ذلك باب انفتح (استمرار المحاولة) أو إعادة المرحلة نفسها. الستائر والأكياس والجبس قوارير محجوبة ("blocked") لا يلمسها الحلّال؛
وانكسار الجبس (حين تكتمل جارته) يجعل القالب قارورة ظاهرة في خانته: استمرار للمحاولة نفسها («الجبس انكسر»)، وقبله (ثوانٍ بعد
إكمال الجارة) لا أدوات ولا حركة عشوائية ولا «إعادة» حين لا حركة، بل انتظار وإعادة تصوير.
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
import re
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
    "superhard_plan_x": _env("BOT_SUPERHARD_PLAN_X", 3.0, float),  # مضاعف وقت التخطيط وعقده في المراحل الصعبة جداً
    # كل «Give Up» في المرحلة نفسها يزيد التفكير خطوة حتى الحدّ (المرحلة 107 انسدّت أربع مرات بالميزانية العادية)
    "fail_plan_step": _env("BOT_FAIL_PLAN_STEP", 0.75, float),
    "fail_plan_max": _env("BOT_FAIL_PLAN_MAX", 4.0, float),
    "key_wait": _env("BOT_KEY_WAIT", 1.5, float),      # بعد حركة تحرّر مفتاحاً: طيرانه وانفتاح الباب
    # حارس المحاكي: اسم AVD الذي يشغّله reactivecircus/android-emulator-runner وخياراته (كما في emu-bot.yml)
    "emu_avd": _env("BOT_AVD", "test"),
    "emu_options": _env("BOT_EMU_OPTIONS", "-no-window -gpu swiftshader_indirect -no-snapshot -noaudio -no-boot-anim -feature -Vulkan"),
    # سياسة إعادات المحاكي بالتقدّم (emu_restart_policy؛ التشغيل 15: مات 9 مرات في نحو 190 دقيقة وتوقف البوت بعد 8 إعادات وأمامه
    # 110 دقائق وهو يفوز بين الأعطال): يُعاد ما دام البوت يتقدّم، ويتوقف بعد emu_fruitless_max إعادات متتالية بلا تقدّم،
    # أو عند emu_restarts إعادة في التشغيل (حدّ أمان سخيّ)، أو حين يبقى أقل من emu_restart_min_left دقيقة.
    "emu_restarts": _env("BOT_EMU_RESTARTS", 40, int),
    "emu_fruitless_max": _env("BOT_EMU_FRUITLESS_MAX", 3, int),
    "emu_progress_min": _env("BOT_EMU_PROGRESS_MIN", 15.0, float),  # دقائق لعب بعد إعادة تُحسب تقدّماً ولو بلا فوز
    "emu_restart_min_left": _env("BOT_EMU_RESTART_MIN_LEFT", 6.0, float),
    "emu_install_min": _env("BOT_EMU_INSTALL_MIN", 12.0, float),     # أقل وقت باقٍ لتثبيت اللعبة واستعادة حفظها بعد إعادة
    # إقلاع المحاكي بعد إعادته (التشغيل 16: لم يُقلع بعد عطل ثلاث مرات متتالية، كل مرة بعد انتظار 10 دقائق، فتوقف البوت وأمامه
    # 3.5 ساعة): الإقلاع العادي يُنتظر emu_boot_min دقيقة على الأكثر (الإعادات الناجحة تُقلع في أقل من دقيقة)، فإن فشل يُشغَّل مرة
    # بمحو البيانات (-wipe-data) ثم تُثبّت اللعبة وتُستعاد آخر نسخة احتياطية، إن بقي emu_wipe_boot_min + emu_install_min دقيقة؛
    # وإقلاعه بعد المحو (أول إقلاع أطول) يُنتظر حتى emu_wipe_boot_max دقيقة ولا يأكل وقت التثبيت. محاكٍ حيّ ظاهر في adb لم يُكمل
    # إقلاعه في emu_boot_min (بطيء لا معطوب) يُمدَّد له emu_boot_extend_min دقيقة قبل التفكير في المحو.
    "emu_boot_min": _env("BOT_EMU_BOOT_MIN", 6.0, float),
    "emu_boot_extend_min": _env("BOT_EMU_BOOT_EXTEND_MIN", 4.0, float),
    "emu_wipe": _env("BOT_EMU_WIPE", 1, int),                        # 0: بلا محاولة المحو
    "emu_wipe_boot_min": _env("BOT_EMU_WIPE_BOOT_MIN", 4.0, float),
    "emu_wipe_boot_max": _env("BOT_EMU_WIPE_BOOT_MAX", 10.0, float),
    "emu_avd_home": _env("BOT_AVD_HOME", ""),                        # مجلّد AVD (فارغ: ANDROID_AVD_HOME أو ~/.android/avd)
    # نسخة احتياطية بعد فوز جديد إن مضت هذه الدقائق على آخر نسخة (المحاكي قد يموت فجأة فيضيع تقدّم ما بعد آخر نسخة)
    "backup_win_min": _env("BOT_BACKUP_WIN_MIN", 10.0, float),
    # النسخة الاحتياطية تُحفظ أجزاءً مرتّبة (split_backup): GitHub يحذّر من ملف فوق 50 ميغا ويرفض ما فوق 100، والنسخة بلغت 77.6
    "backup_part_mb": _env("BOT_BACKUP_PART_MB", 40.0, float),
    "backup_max_mb": _env("BOT_BACKUP_MAX_MB", 400.0, float),       # أكبر نسخة تُقبل (أكبر منها: خطأ في adb backup)
    # بعد حركة تكمل جارة جبس: ينكسر الجبس بعد ثوانٍ (التشغيل التاسع: يظهر مكسوراً بعد 6..7 ث من النقر، وقائماً بعد 4 ث)
    "plaster_wait": _env("BOT_PLASTER_WAIT", 4.0, float),
    "plaster_grace": _env("BOT_PLASTER_GRACE", 10.0, float),  # «عالقة» قبل هذا بعد إكمال الجارة: انتظار الجبس لا الأدوات
    # الإعلان التجريبي الأبيض (AppLovin): انتظار عدّه التنازلي (نحو 9..15 ث) قبل X أو الرجوع، وإعادة اللعبة إن بقي بعد المهلة
    "ad_wait_sec": _env("BOT_AD_WAIT_SEC", 12.0, float),
    "ad_max_sec": _env("BOT_AD_MAX_SEC", 45.0, float),
    "ad_black_max_sec": _env("BOT_AD_BLACK_MAX_SEC", 90.0, float),   # الإعلان الأسود (يُغلق برجوع واحد عادة)
    # شعار «MAGIC SORT» فوق لوحة معتمة بعد الفوز: انتظار بلا لمس، ثم رجوع مرة، ثم إعادة اللعبة بعد مهلة أخرى
    "logo_wait_sec": _env("BOT_LOGO_WAIT_SEC", 40.0, float),
    "logo_back_sec": _env("BOT_LOGO_BACK_SEC", 15.0, float),
    # الثمنان حدّان أدنى: المقروء من الزرّ يُعتمد إن زاد عليهما فقط (قراءة «Play On 900» قد تُسقط صفراً فتصير 90)
    "refill_price": _env("BOT_REFILL_PRICE", 900, int),     # ثمن ملء الأرواح الأدنى (زرّ «Refill»)
    "play_on_price": _env("BOT_PLAY_ON_PRICE", 900, int),   # ثمن «Play On» (قارورة) الأدنى
    "play_on_reserve": _env("BOT_PLAY_ON_RESERVE", 900, int),  # يبقى بعد «Play On» لملء الأرواح مرة (0: «Play On» أولاً)
    "lives_wait_sec": _env("BOT_LIVES_WAIT_SEC", 300.0, float),  # انتظار الروح القادمة إن لم يُقرأ عدّادها
    "play_on_fails": _env("BOT_PLAY_ON_FAILS", 2, int),     # «Play On» في مرحلة عادية بعد هذا العدد من «Give Up» فيها
}
BOOSTER_DEFAULT = {"undo": (144, 854), "shuffle": (236, 854), "add": (328, 854)}


def plan_boost(badge, give_ups):
    """مضاعف وقت التخطيط وعقده: 3 في الصعبة جداً، و1 + 0.75 لكل «Give Up» سابق في المرحلة نفسها حتى 4 (الأكبر منهما).
    الإخفاق المتكرّر في مرحلة يعني أن الميزانية العادية لا تكفيها، وانتظار روح (15 دقيقة) أغلى بكثير من ثوانٍ من التفكير."""
    base = CFG["superhard_plan_x"] if badge == "superhard" else 1.0
    extra = min(CFG["fail_plan_max"], 1.0 + CFG["fail_plan_step"] * max(0, int(give_ups or 0)))
    return max(base, extra)


NOVEL_DIST = 28        # بصمة 256 بت: نوافذ الفوز بينها ≤32، والشاشات المختلفة ≥73
PUB_DIR = Path(os.environ.get("BOT_PUB_DIR", "/tmp/bot_pub"))   # شجرة git منفصلة للنشر
STATE_FILE = Path(os.environ.get("BOT_STATE_FILE", "/tmp/bot_state.json"))   # عدّادات السياسات عبر أمر «update»
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

    def adb_state(self) -> str:
        """حالة الجهاز في «adb devices»: device أو offline أو unauthorized، أو "" إن لم يكن موجوداً."""
        try:
            p = subprocess.run([self.adb, "devices"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
        except (subprocess.TimeoutExpired, OSError):
            return ""
        for line in p.stdout.decode("utf-8", "replace").splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and (self.serial is None or parts[0] == self.serial):
                return parts[1]
        return ""

    def restart_adb(self):
        """إعادة تشغيل خادم adb (يفقد الاتصال بالمحاكي أحياناً فتفشل كل لقطة)."""
        for args in (["kill-server"], ["start-server"]):
            try:
                subprocess.run([self.adb] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            except (subprocess.TimeoutExpired, OSError):
                pass

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
                d = {"x": int(t["x"]), "y": int(t["y"]), "cap": int(t.get("cap") or 4),
                     "layers": [c if isinstance(c, str) else "?" for c in (t.get("layers") or [])],
                     "tall": bool(t.get("tall", False)), "lifted": bool(t.get("lifted", False)),
                     "clay": bool(t.get("clay", False))}
                ks = [int(p) for p in (t.get("keys") or []) if 0 <= int(p) < len(d["layers"])]
                if ks:                                   # طبقات المفاتيح (من المرحلة 63) تصل إلى الحلّال
                    d["keys"] = ks
                    if t.get("key_colors"):
                        d["key_colors"] = [str(c) for c in t["key_colors"]]
                if isinstance(t.get("accept"), str) and t["accept"]:
                    d["accept"] = t["accept"]            # «Tag!» (من المرحلة 130): لا يُصبّ فيها إلا هذا اللون
                if t.get("blocked"):                     # تحت ستارة أو كيس أو جبس: محتواها مجهول ولا تُلمس
                    d["blocked"] = True
                    d["layers"] = []
                    d.pop("keys", None)
                    d.pop("accept", None)
                    if t.get("cover"):
                        d["cover"] = str(t["cover"])
                    if t.get("cover_color"):
                        d["cover_color"] = str(t["cover_color"])
                bx = t.get("box")
                if isinstance(bx, (list, tuple)) and len(bx) == 4:
                    try:
                        d["box"] = [int(v) for v in bx]  # صفّ القارورة الطويلة وجارات الجبس في الحلّال
                    except (TypeError, ValueError):
                        pass
                tubes.append(d)
            except (KeyError, TypeError, ValueError):
                return None
        out = {"tubes": tubes, "warnings": list(st.get("warnings") or [])}
        if st.get("doors"):
            out["doors"] = list(st["doors"])
        return out

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

    def badge(self, fr):
        """نوع المرحلة من عنوانها: "normal" | "hard" | "superhard" أو None."""
        b = self._safe("level_badge", fr.arr)
        return b if b in ("normal", "hard", "superhard") else None

    def coins(self, fr):
        """رصيد العملات من الحبّة أعلى اليسار (النوافذ والواجهة) أو None."""
        n = self._safe("read_coins", fr.arr)
        return n if isinstance(n, int) and 0 <= n < 10 ** 7 else None

    def lives_popup(self, fr):
        """نافذة «More Lives»: {"refill": (x, y)، "close": (x, y)، "price": int|None، "timer": ثوانٍ|None} أو None."""
        d = self._safe("find_lives_popup", fr.arr)
        if not isinstance(d, dict):
            return None
        refill, close = self._pt(d.get("refill")), self._pt(d.get("close"))
        if not refill or not close:
            return None
        price, timer = d.get("price"), d.get("timer")
        return {"refill": refill, "close": close,
                "price": price if isinstance(price, int) and price > 0 else None,
                "timer": float(timer) if isinstance(timer, (int, float)) and timer >= 0 else None}

    def play_on(self, fr):
        """زرّ «Play On» في نافذة «No Available Moves»: ((x, y)، الثمن أو None) أو None."""
        p = self._safe("find_play_on", fr.arr)
        pt = self._pt(p)
        if not pt:
            return None
        try:
            price = int(p[2]) if len(p) > 2 and p[2] else None
        except (TypeError, ValueError):
            price = None
        return pt, price

    def paid_at(self, fr, pt) -> bool:
        """هل تقع النقطة داخل زرّ أخضر يصرف العملات؟ (نقطة الوسط (236,620) في نافذة «Continue?» داخل «Play On 900»، فلا
        تلمسها نقرات التصعيد العمياء.) خطأ في فحص الثمن يُعدّ «يصرف» (الرجوع بدل النقر)."""
        gb = self._safe("green_buttons", fr.arr)
        if not isinstance(gb, list):
            return False
        for b in gb:
            try:
                x0, y0, x1, y1 = b["box"]
                if x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1 and self._safe("_paid", fr.arr, b, default=True):
                    return True
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        return False

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


def remember_tags(st, tags):
    """ذاكرة الوسوم بالموضع («Tag!»، من المرحلة 130): `tags` = [[س، ص، لون]] لكل قارورة موسومة رُئيت في هذه المحاولة (تُحدَّث
    هنا). قارورة في خانة وسم معروف لم يُقرأ وسمها في هذه اللقطة (بطاقة حجبها صبّ أو حركة) يُعاد إليها وسمها ما دامت فارغة أو
    كل طبقاتها بلونه (وإلا فليست هي). يعيد (الحالة، عدد القوارير التي أُعيد وسمها)."""
    for t in st["tubes"]:
        if t.get("accept") and not t.get("blocked"):
            for r in tags:
                if _pos_near(r[0], r[1], t):
                    r[0], r[1], r[2] = t["x"], t["y"], t["accept"]
                    break
            else:
                tags.append([t["x"], t["y"], t["accept"]])
    filled = 0
    tubes = []
    for t in st["tubes"]:
        if not t.get("accept") and not t.get("blocked"):
            for x, y, acc in tags:
                if _pos_near(x, y, t) and all(c == acc for c in t["layers"]):
                    t = dict(t, accept=acc)
                    filled += 1
                    break
        tubes.append(t)
    if not filled:
        return st, 0
    out = dict(st)
    out["tubes"] = tubes
    return out, filled


def rebase_tags(tags, ref, st, mp):
    """ذاكرة الوسوم بمواضع اللوحة الجديدة حين تتغيّر المواضع (باب، قارورة إضافية، «Play On»: الصفّ يُعاد ترتيبه): تُبنى من
    القوارير الموسومة في `ref` (تحمل `accept` من الرؤية أو من remember_tags) بالمطابقة `mp` {فهرس في ref: فهرس في st}، وتُحذف
    المداخل القديمة كلها (مدخل بموضع قديم قد يقع على قارورة عادية أو على القارورة الإضافية الفارغة فيعطيها وسماً خطأً).
    تُعدَّل `tags` في مكانها وتُعاد."""
    tubes = st["tubes"]
    new = []
    for k, t in enumerate(ref["tubes"]):
        j = mp.get(k)
        if t.get("accept") and j is not None and 0 <= j < len(tubes):
            new.append([tubes[j]["x"], tubes[j]["y"], t["accept"]])
    tags[:] = new
    return tags


def tags_summary(st) -> str:
    """«القارورة 1: lavender، القارورة 4: purple» للقوارير الموسومة (للسجل)، أو ""."""
    return "، ".join("القارورة %d: %s" % (k, t["accept"]) for k, t in enumerate(st["tubes"]) if t.get("accept"))


def color_counts(st):
    return Counter(c for t in st["tubes"] for c in t["layers"])


def covered(st) -> bool:
    """في اللوحة قوارير مغطّاة (ستارة/كيس/جبس) أو أبواب: ترتيب الظاهر وحده ليس فوزاً."""
    return bool(st.get("doors")) or any(t.get("blocked") for t in st["tubes"])


COVER_AR = {"curtain": "ستارة", "bag": "كيس", "plaster": "جبس"}


def cover_summary(st) -> str:
    """«ستارة 2، جبس 4» لأنواع القوارير المغطّاة في اللوحة (للسجل)."""
    c = Counter(COVER_AR.get(t.get("cover"), "غطاء") for t in st["tubes"] if t.get("blocked"))
    return "، ".join("%s %d" % kv for kv in sorted(c.items()))


def plaster_breaks(old, new):
    """فهارس قوالب جبس انكسرت بين لوحتين بالعدد نفسه من القوارير: خانة كانت جبساً في `old` وصارت قارورة ظاهرة في `new` في
    الموضع نفسه تقريباً (الفهارس لا تتغيّر: القالب قارورة في ترتيب القراءة). العدد المختلف (قالب لم يُقرأ ثم ظهرت قارورته) يمرّ
    بمسار الأبواب (door_map أو slot_map)."""
    to, tn = old["tubes"], new["tubes"]
    if len(to) != len(tn):
        return []
    return [k for k, (a, b) in enumerate(zip(to, tn))
            if a.get("blocked") and a.get("cover") == "plaster" and not b.get("blocked") and _near(a, b)]


def full_tube(t) -> bool:
    """قارورة ظاهرة ممتلئة بلون واحد معروف (مكتملة: تُسدّ بسدادة ذهبية، وتكسر الجبس المجاور إن كانت كاسرته)."""
    L = t.get("layers") or []
    try:
        return not t.get("blocked") and bool(L) and len(L) >= int(t["cap"]) and len(set(L)) == 1 and L[0] != "?"
    except (KeyError, TypeError, ValueError):
        return False


def mask_tubes(st, ref, idx):
    """نسخة من `st` تعود فيها القوارير `idx` كما في `ref` (جبس انكسر بعد الحركة: يُحكم على الحركة نفسها بلا طبقاته الجديدة)."""
    out = dict(st)
    out["tubes"] = [ref["tubes"][k] if k in idx else t for k, t in enumerate(st["tubes"])]
    return out


def compatible(old, new, extra_tubes=0) -> bool:
    """هل `new` استمرار للغز `old` نفسه (لا مرحلة جديدة)؟ الألوان لا تتغيّر بالحركات، إلا قارورة مغطّاة انكشفت في
    خانتها (العدد نفسه): طبقاتها جديدة فلا تُحسب في الموازنة."""
    no, nn = len(old["tubes"]), len(new["tubes"])
    if not (no - 1 <= nn <= no + 1 + extra_tubes):
        return False
    co, cn = color_counts(old), color_counts(new)
    if no == nn:
        for a, b in zip(old["tubes"], new["tubes"]):
            if a.get("blocked") and not b.get("blocked"):
                cn.subtract(b["layers"])
        cn = +cn                                    # بلا الأعداد الصفرية والسالبة
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
    hidden = cnt.pop("?", 0) + sum(t["cap"] for t in tubes if t.get("blocked"))   # المغطّاة طبقات مجهولة
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
    # المغطّاة لا تُرفع، ونقطتها مقدّرة من غطائها (قد تختلف عن صفّها)
    normal = sorted([(k, t) for k, t in enumerate(tubes)
                     if t["cap"] == base and not t.get("tall") and not t.get("blocked")],
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
    out = []
    for t in st["tubes"]:
        d = {"x": t["x"], "y": t["y"], "cap": t["cap"], "layers": t["layers"]}
        if t.get("keys"):
            d["keys"] = t["keys"]
        if t.get("accept"):
            d["accept"] = t["accept"]
        if t.get("blocked"):
            d["blocked"] = t.get("cover") or True
            if t.get("cover_color"):
                d["cover_color"] = t["cover_color"]
        out.append(d)
    return out


def _same_tube(a, b) -> bool:
    """القارورة نفسها قبل انفتاح باب وبعده: الطبقات نفسها (مخفية انكشفت أو لون من الذاكرة بقي "?" مقبول).
    المغطّاة تطابق المغطّاة فقط (لا قارورة فارغة)."""
    if bool(a.get("blocked")) != bool(b.get("blocked")):
        return False
    if a.get("accept") and b.get("accept") and a["accept"] != b["accept"]:
        return False                                # وسمان مختلفان («Tag!»): قارورتان مختلفتان ولو تشابهت طبقاتهما
    la, lb = a["layers"], b["layers"]
    if len(la) != len(lb):
        return False
    return all(x == y or x == "?" or y == "?" for x, y in zip(la, lb))


def _near(a, b) -> bool:
    """الخانة نفسها تقريباً (نقطتا النقر؛ القارورة الإضافية تضغط اللوحة بضع بكسلات)."""
    try:
        return abs(a["x"] - b["x"]) <= 24 and abs(a["y"] - b["y"]) <= 45
    except (KeyError, TypeError):
        return False


def _slot_score(a, b) -> float:
    if a.get("blocked") or b.get("blocked"):
        if a.get("blocked") and b.get("blocked"):
            return 3.0 if _near(a, b) else 1.0
        return 1.0 if (a.get("blocked") and _near(a, b)) else 0.0      # غطاء انكشف في خانته
    if _same_tube(a, b):
        return 3.0 if _near(a, b) else 2.0
    if not _near(a, b):
        return 0.0
    pre = 0
    for x, y in zip(a["layers"], b["layers"]):
        if x == y or x == "?" or y == "?":
            pre += 1
        else:
            break
    return 1.5 if pre else 1.0


def slot_map(old, new):
    """مطابقة تقريبية {فهرس قديم: فهرس جديد} حين تتغيّر اللوحة ولا تكفي door_map (باب وغطاء معاً، صبّ أثناء الانفتاح،
    قراءة ناقصة): تحفظ ترتيب القراءة وتعظّم مجموع الدرجات: المحتوى نفسه في الخانة نفسها 3، المحتوى نفسه بعد إعادة
    التوزيع 2، الخانة نفسها بقاع متّفق 1.5 (المخفي لا يتحرّك)، الخانة نفسها وحدها 1 (ومنها غطاء انكشف)."""
    to, tn = old["tubes"], new["tubes"]
    no, nn = len(to), len(tn)
    S = [[0.0] * (nn + 1) for _ in range(no + 1)]
    sc = [[_slot_score(to[a], tn[b]) for b in range(nn)] for a in range(no)]
    for a in range(no - 1, -1, -1):
        for b in range(nn - 1, -1, -1):
            v = max(S[a + 1][b], S[a][b + 1])
            if sc[a][b] > 0:
                v = max(v, sc[a][b] + S[a + 1][b + 1])
            S[a][b] = v
    mp, a, b = {}, 0, 0
    while a < no and b < nn:
        if sc[a][b] > 0 and abs(S[a][b] - (sc[a][b] + S[a + 1][b + 1])) < 1e-9:
            mp[a] = b
            a += 1
            b += 1
        elif S[a + 1][b] >= S[a][b + 1]:
            a += 1
        else:
            b += 1
    return mp


def remap_memory(memory, mp, new):
    """ذاكرة الطبقات المكشوفة بفهارس اللوحة الجديدة: تُنقل المطابَقة فقط، ويُترك ما لم يعد "?" بلونها في موضعه."""
    out = {}
    tubes = new["tubes"]
    for (k, p), c in memory.items():
        j = mp.get(k)
        if j is None or j >= len(tubes) or tubes[j].get("blocked"):
            continue
        L = tubes[j]["layers"]
        if p < len(L) and L[p] in ("?", c):
            out[(j, p)] = c
    return out


def door_map(old, new):
    """انفتح باب (من المرحلة 63): قوارير جديدة ظهرت وبقيت القديمة كما هي. تعيد {فهرس قديم: فهرس جديد} بمطابقة
    تحفظ ترتيب القراءة (الأبواب تُدرج قوارير بين القديمة وقد تتغيّر المسافات)، أو None إن لم تكن هذه الحالة."""
    to, tn = old["tubes"], new["tubes"]
    no, nn = len(to), len(tn)
    if nn <= no or no == 0:
        return None
    # أطول تطابق محافظ على الترتيب (LCS)، وبين التطابقات المتساوية أكثرها في الخانة نفسها: المخفي "?" يطابق أي لون، فقارورة
    # باب جديدة قد «تطابق» قديمة (المرحلة 124: [darkgreen,?,?,lavender] و[?,brown,?,lavender]) والموضع يحسم (القديمة لا تتحرّك)
    same = [[_same_tube(to[a], tn[b]) for b in range(nn)] for a in range(no)]
    L = [[(0, 0)] * (nn + 1) for _ in range(no + 1)]
    for a in range(no - 1, -1, -1):
        for b in range(nn - 1, -1, -1):
            v = max(L[a + 1][b], L[a][b + 1])
            if same[a][b]:
                m, nr = L[a + 1][b + 1]
                v = max(v, (m + 1, nr + (1 if _near(to[a], tn[b]) else 0)))
            L[a][b] = v
    if L[0][0][0] < no:
        return None
    mp, a, b = {}, 0, 0
    while a < no and b < nn:
        if same[a][b]:
            m, nr = L[a + 1][b + 1]
            if L[a][b] == (m + 1, nr + (1 if _near(to[a], tn[b]) else 0)):
                mp[a] = b
                a += 1
                b += 1
                continue
        if L[a + 1][b] >= L[a][b + 1]:
            a += 1
        else:
            b += 1
    return mp if len(mp) == no else None


# ============================================================== ذاكرة كل بداية (التشغيل 12، المرحلة 124)
# بعد «Give Up» تعود المرحلة بإحدى بدايات قليلة، والبداية نفسها تفتح أبوابها عن القوارير نفسها في المواضع نفسها كل مرة، والبوت
# حتمي فكان يعيد الخط الخاسر نفسه. لكل بداية (رقم المرحلة + state_key بدايتها): عدد محاولاتها الفاشلة (منه التناوب والتنويع)،
# وحالات آخر طريق مسدود (لا يُعاد إليها)، وما خلف كل باب (هوية المفتاح بالموضع: س، ص لقارورته وطبقته).
SIG_MAX = 40          # أقصى عدد بدايات محفوظة (الأقدم استعمالاً يُحذف)
SIG_DEAD_MAX = 40     # أقصى عدد حالات «طريق مسدود» لكل بداية (الأحدث يبقى)
SIG_DOORS_MAX = 16    # أقصى عدد أبواب معروفة لكل بداية
DEAD_TAIL = 5         # الحالة العالقة الأخيرة والأربع قبلها (حالة البداية لا تُحفظ أبداً: مفترق كل الخطوط)


def sig_id(n, sig) -> str:
    """معرّف نصّي ثابت لبداية مرحلة (مفتاح JSON): «رقم المرحلة:بصمة state_key بدايتها»."""
    import hashlib
    h = hashlib.sha1(json.dumps(sig, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    return "%s:%s" % (n, h)


def new_sig_rec(n):
    # dead: مفاتيح state_key للطريق المسدود كما سُجّلت؛ dead_st: حالاته المختصرة [[س، ص، سعة، [طبقات]]، ...] تُملأ «?» فيها بما
    # عُرف بعدها (الحلّال يرى الطبقة معروفة فلا يطابق مفتاحها الخام بـ «?»)
    return {"n": n, "fails": 0, "dead": [], "dead_st": [], "doors": [], "mem": [], "t": time.time()}


def _sk_tuple(x):
    """state_key من JSON (قوائم) إلى صفوف كما يعيدها solver.state_key (والقارورة الموسومة بلون وسمها عنصراً ثالثاً)."""
    out = []
    for e in x:
        if len(e) not in (2, 3):
            raise ValueError(e)
        row = (int(e[0]), tuple(str(v) for v in e[1]))
        out.append(row + (str(e[2]),) if len(e) == 3 else row)
    return tuple(out)


def clean_sig_rec(d):
    """سجلّ بداية مقروء من ملف الحالة بعد التحقق من كل حقل (الحقول الغائبة أو التالفة تعود فارغة: لا يتوقف البوت)."""
    if not isinstance(d, dict):
        return None
    rec = new_sig_rec(d.get("n"))
    try:
        rec["n"] = int(d.get("n"))
    except (TypeError, ValueError):
        return None
    try:
        rec["fails"] = max(0, int(d.get("fails") or 0))
    except (TypeError, ValueError):
        pass
    try:
        rec["t"] = float(d.get("t") or 0.0)
    except (TypeError, ValueError):
        rec["t"] = 0.0
    for sk in d.get("dead") or ():
        try:
            rec["dead"].append(_sk_tuple(sk))
        except (TypeError, ValueError):
            continue
    rec["dead"] = rec["dead"][-SIG_DEAD_MAX:]
    for ds in d.get("dead_st") or ():
        try:
            rec["dead_st"].append([[int(r[0]), int(r[1]), int(r[2]), [str(v) for v in r[3]]] + ([str(r[4])] if len(r) > 4 else [])
                                   for r in ds])
        except (TypeError, ValueError):
            continue
    rec["dead_st"] = rec["dead_st"][-SIG_DEAD_MAX:]
    for dr in d.get("doors") or ():
        try:
            keys = [[int(x), int(y), int(p)] for x, y, p in dr["keys"]]
            tubes = []
            for t in dr["tubes"]:
                tt = {"x": int(t["x"]), "y": int(t["y"]), "cap": int(t["cap"]), "layers": [str(c) for c in t["layers"]]}
                if t.get("keys"):
                    tt["keys"] = [int(p) for p in t["keys"]]
                if isinstance(t.get("accept"), str) and t["accept"]:
                    tt["accept"] = t["accept"]
                tubes.append(tt)
            if keys and tubes:
                rec["doors"].append({"keys": keys, "tubes": tubes})
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    rec["doors"] = rec["doors"][:SIG_DOORS_MAX]
    for m in d.get("mem") or ():
        try:
            k, p, c = m
            rec["mem"].append([int(k), int(p), str(c)])
        except (TypeError, ValueError):
            continue
    return rec


def _pos_near(x, y, t) -> bool:
    try:
        return abs(float(x) - float(t["x"])) <= 24 and abs(float(y) - float(t["y"])) <= 45
    except (KeyError, TypeError, ValueError):
        return False


def _released(layers, p) -> bool:
    """قاعدة تحرّر المفتاح (solver._key_block في (None، 0)): خرجت طبقته من القارورة، أو كل ما فوقها بلونها (لا مخفي)."""
    if p >= len(layers):
        return True
    c = layers[p]
    return c != "?" and all(x == c for x in layers[p:])


def door_record(ref, st, mp, vanished=None):
    """باب انفتح بين `ref` (قبله) و`st` (بعده) بالمطابقة `mp`: ([[س، ص، طبقة] لكل مفتاح تحرّر]، [قوارير جديدة كما قُرئت أول
    مرة])، أو None إن لم يُعرف المفتاح (قارورة إضافية مثلاً) أو لا قوارير جديدة ذات طبقات. `vanished`: مفاتيح اختفت من قواريرها
    منذ آخر باب (لقطة بين طيران المفتاح وانفتاح الباب اعتُمدت فصارت ref بلا المفتاح): تُنسب إليها حين لا مفتاح محرَّراً في ref."""
    rt, nt = ref["tubes"], st["tubes"]
    freed = []
    for a, t in enumerate(rt):
        b = mp.get(a)
        if b is None or not t.get("keys") or b >= len(nt):
            continue
        after = nt[b]
        for p in t["keys"]:
            try:
                p = int(p)
            except (TypeError, ValueError):
                continue
            if p not in (after.get("keys") or ()) and _released(after.get("layers") or [], p):
                freed.append([int(round(t["x"])), int(round(t["y"])), p])
    used = set(mp.values())
    tubes = []
    for k, t in enumerate(nt):
        if k in used or t.get("blocked") or not t.get("layers"):
            continue
        d = {"x": int(round(t["x"])), "y": int(round(t["y"])), "cap": int(t["cap"]), "layers": list(t["layers"])}
        if t.get("keys"):
            d["keys"] = [int(p) for p in t["keys"]]
        if t.get("accept"):
            d["accept"] = t["accept"]                # قارورة باب موسومة: القيد نفسه في بحث الأبواب
        tubes.append(d)
    if not freed and vanished:
        freed = [list(k) for k in vanished]
    if not freed or not tubes:
        return None
    return freed, tubes


def _key_near(a, b) -> bool:
    return a[2] == b[2] and abs(a[0] - b[0]) <= 24 and abs(a[1] - b[1]) <= 45


def _match_tubes(old, new):
    """قوارير الباب نفسه بالخانة والسعة (كل قارورة جديدة تطابق قارورة قديمة واحدة، والعدد نفسه): [(قديمة، جديدة)] أو None."""
    if len(old) != len(new):
        return None
    pairs, used = [], set()
    for t in new:
        hit = None
        for i, r in enumerate(old):
            if i not in used and _pos_near(t["x"], t["y"], r) and int(r["cap"]) == int(t["cap"]):
                hit = i
                break
        if hit is None:
            return None
        used.add(hit)
        pairs.append((old[hit], t))
    return pairs


def merge_door(doors, keys, tubes):
    """يضيف باباً إلى ذاكرة البداية. هوية الباب خانات قواريره (لا مفاتيحه: ملصق مفتاح لم يُقرأ في لقطة الباب، أو بابان في
    لقطة واحدة، يعطيان مجموعة مفاتيح أخرى للقوارير نفسها): إن طابقت قواريره سجلاً بالخانة والسعة فهو «معروف»، ومفاتيحه التقاطع
    بين القراءتين (أو الأحدث إن لم تتقاطعا) وطبقاته الأحدث حيث قُرئت (المخفي "?" لا يمحو لوناً معروفاً). وسجلّ قديم يتداخل معه
    بالخانة ولا يطابقه يُحذف (القراءة الأحدث تصحّحه). يعيد "new" | "known" | "replaced" | "full"."""
    for d in doors:
        pairs = _match_tubes(d["tubes"], tubes)
        if pairs is None:
            continue
        both = [list(k) for k in d["keys"] if any(_key_near(k, q) for q in keys)]
        d["keys"] = both or [list(k) for k in keys]
        for r, t in pairs:
            if len(r["layers"]) == len(t["layers"]):
                r["layers"] = [n if n != "?" else c for c, n in zip(r["layers"], t["layers"])]
            else:
                r["layers"] = list(t["layers"])
            if t.get("keys"):
                r["keys"] = [int(p) for p in t["keys"]]
            else:
                r.pop("keys", None)
            if t.get("accept"):
                r["accept"] = t["accept"]
        return "known"
    over = [d for d in doors if any(_pos_near(t["x"], t["y"], r) for t in tubes for r in d["tubes"])]
    for d in over:
        doors.remove(d)
    if len(doors) >= SIG_DOORS_MAX:
        return "full"
    doors.append({"keys": [list(k) for k in keys], "tubes": [dict(t, layers=list(t["layers"])) for t in tubes]})
    return "replaced" if over else "new"


def _door_tube(doors, t):
    """قارورة باب معروف في موضع القارورة t (والسعة نفسها)، أو None."""
    for d in doors:
        for r in d["tubes"]:
            if _pos_near(t["x"], t["y"], r) and int(r["cap"]) == int(t["cap"]):
                return r
    return None


def learn_door_layers(doors, st, revealed) -> int:
    """طبقات مخفية انكشفت في قوارير أبواب معروفة تُكتب في ذاكرة الأبواب (المخفي لا يتحرّك: موضعه ثابت). يعيد عددها."""
    n = 0
    for (k, p, c) in revealed:
        if not (0 <= k < len(st["tubes"])) or c == "?":
            continue
        r = _door_tube(doors, st["tubes"][k])
        if r is not None and p < len(r["layers"]) and r["layers"][p] == "?":
            r["layers"][p] = c
            n += 1
    return n


def fill_from_doors(doors, st, idx, memory) -> int:
    """قوارير باب انفتح الآن (`idx` بفهارس `st`): الطبقات المخفية التي عُرفت في محاولة سابقة تدخل الذاكرة. يعيد عددها."""
    n = 0
    for k in idx:
        t = st["tubes"][k]
        r = _door_tube(doors, t)
        if r is None:
            continue
        for p, c in enumerate(r["layers"]):
            if p < len(t["layers"]) and t["layers"][p] == "?" and c != "?" and (k, p) not in memory:
                memory[(k, p)] = c
                n += 1
    return n


def known_doors(st, doors):
    """ذاكرة الأبواب -> مواصفات solver.plan(doors=...) بفهارس الحالة الحالية (بالموضع: الفهارس تتغيّر حين تنفتح الأبواب).
    يُعتمد الباب ما دام مفتاحه ظاهراً على قارورته (لم يطر)، ومفتاح داخل قارورة باب مغلق معروف يفتح باباً آخر معروفاً (قوارير
    الأبواب تُلحق بعد قوارير الحالة بترتيب المواصفات)."""
    tubes = st["tubes"]
    ext = [(t.get("x"), t.get("y"), set(t.get("keys") or ()), bool(t.get("blocked"))) for t in tubes]
    out = []
    pending = list(doors or ())
    changed = True
    while changed and pending:
        changed = False
        for d in list(pending):
            # قارورة باب في خانة قارورة ظاهرة الآن أو قارورة باب قُبل قبله: سجلّ خاطئ أو باب انفتح، لا يدخل المسألة (لا قوارير وهمية)
            if any(_pos_near(t["x"], t["y"], {"x": tx, "y": ty}) for t in d["tubes"] for tx, ty, _k, _b in ext):
                pending.remove(d)
                continue
            idxs = []
            for x, y, p in d["keys"]:
                hit = None
                for k, (tx, ty, ks, blk) in enumerate(ext):
                    if not blk and p in ks and _pos_near(x, y, {"x": tx, "y": ty}):
                        hit = k
                        break
                if hit is None:
                    break
                idxs.append((hit, p))
            else:
                for t in d["tubes"]:
                    ext.append((t["x"], t["y"], set(t.get("keys") or ()), False))
                out.append({"keys": idxs, "tubes": [dict(t, layers=list(t["layers"])) for t in d["tubes"]]})
                pending.remove(d)
                changed = True
    return out


def compact_tubes(st):
    """الحالة مختصرة لحفظ «الطريق المسدود»: [[س، ص، سعة، [طبقات]]] للقوارير غير المغطّاة (كما في state_key)؛ والموسومة
    («Tag!») بلون وسمها عنصراً خامساً."""
    return [[int(round(t["x"])), int(round(t["y"])), int(t["cap"]), list(t["layers"])] + ([t["accept"]] if t.get("accept") else [])
            for t in st["tubes"] if not t.get("blocked")]


def fill_known(tubes_c, know):
    """حالة مختصرة تُملأ «?» فيها بما عُرف بالموضع `know` = [(س، ص، سعة، طبقة، لون)] (المخفي لا يتحرّك: خانته وطبقته ثابتتان
    ما دام مخفياً). يعيد الحالة (dict لـ state_key)."""
    out = []
    for row in tubes_c:
        x, y, cap, layers = row[:4]
        L = list(layers)
        for p, c in enumerate(L):
            if c != "?":
                continue
            for kx, ky, kc, kp, col in know:
                if kp == p and kc == cap and abs(kx - x) <= 24 and abs(ky - y) <= 45:
                    L[p] = col
                    break
        d = {"x": x, "y": y, "cap": cap, "layers": L}
        if len(row) > 4 and row[4]:
            d["accept"] = row[4]
        out.append(d)
    return {"tubes": out}


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
        self.dead_restarts = 0         # «إعادة» بالرجوع متتالية بلا حركة بينها (Magic Sort قد يتجاهل الرجوع)
        self.reparse = 0
        self.attempts = Counter()      # (state_key، حركة) -> عدد المحاولات
        self.active = True
        self.result = None
        self.start_sig = solver.state_key(st)
        self.memory = {}               # (قارورة، موضع) -> لون طبقة مخفية انكشفت
        self.doors_opened = 0          # أبواب انفتحت في هذه المحاولة (قوارير ظهرت بلا إعادة)
        self.door_wait = 0
        self.plasters_broken = 0       # قوالب جبس انكسرت في هذه المحاولة
        self.plaster_expect = 0.0      # وقت آخر حركة أكملت جارة جبس (ينكسر بعدها بثوانٍ؛ يُصفَّر حين يُرى الانكسار)
        self.plaster_waits = 0         # إعادات تصوير «عالقة» بانتظار جبس اكتملت جارته (تُصفَّر بإكمال جارة أو انكسار)
        self.plaster_seen = False      # قُرئ قالب جبس في هذه المرحلة (وسم «الجبس انكسر» لقارورة جديدة بلا قالب مقروء)
        self.badge = None              # نوع المرحلة من عنوانها: normal | hard | superhard
        self.play_ons = 0              # «Play On» (قارورة بالعملات) في هذه المحاولة
        self.history = []              # [(state_key، state_key بالذاكرة، compact_tubes)] بالترتيب: آخرها «الطريق المسدود»
        self.hist_base = 0             # عدد ما حُذف من أول history (الفهارس المطلقة)
        self.door_idx = -1             # الفهرس المطلق لأول حالة بعد آخر باب انفتح (لا يدخل الطريق المسدود هي ولا ما قبلها)
        self.vanished = []             # مفاتيح [س، ص، طبقة] اختفت من قواريرها (تحرّرت) منذ آخر باب: لنسبة الباب حين يظهر
        self.sig_id = sig_id(n, self.start_sig)
        self.tags = []                 # [[س، ص، لون]] القوارير الموسومة («Tag!») التي رُئيت (remember_tags)
        self.tag_fills = 0             # لقطات أُعيد فيها وسم لم يُقرأ (للسجل)
        self.sig_attempt = 0           # محاولات هذه البداية الفاشلة قبل هذه (منها التناوب والتنويع)
        self.dead_noted = False        # سُجّل «الطريق المسدود» لهذه المحاولة
        self.dead_replans = set()      # حالات خُطّط لها من جديد بدون ذاكرة الطريق المسدود فلم يُعثر على شيء

    def bad_for(self, key):
        return set(self.bad.get(key, set())) | self.ban


EMU_LOG = "/tmp/emulator_restart.log"   # مخرجات المحاكي الذي يشغّله البوت (start_emulator)؛ آخر أسطره في السجل عند فشل الإقلاع
MEMINFO = "/proc/meminfo"


def kill_emulators():
    """يقتل عملية المحاكي العالقة (qemu) ومشغّلها، إن وُجدا."""
    for pat in ("qemu-system", "emulator -avd"):
        try:
            subprocess.run(["pkill", "-9", "-f", pat], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        except (subprocess.TimeoutExpired, OSError):
            pass


def start_emulator(log_path=None, wipe=False):
    """يشغّل المحاكي من جديد في الخلفية بالـ AVD والخيارات نفسها التي يستعملها emu-bot.yml (بياناته باقية: -no-snapshot لا يمحوها،
    فاللعبة وتقدّمها في مكانهما). wipe: يضيف -wipe-data فيبدأ المحاكي فارغاً بلا اللعبة (restart_emulator بعد إقلاع فاشل).
    مخرجاته تُضاف إلى log_path (EMU_LOG) بعد سطر فاصل بالوقت؛ وإن تعذّرت الكتابة فيه (قرص ممتلئ) يُشغَّل على أي حال ومخرجاته
    إلى العدم. True إن شُغّل، None إن لم يوجد الأمر emulator، False إن وُجد وتعذّر تشغيله (OSError)."""
    log_path = log_path or EMU_LOG
    sdk = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or ""
    exe = os.path.join(sdk, "emulator", "emulator") if sdk else ""
    if not (exe and os.path.exists(exe)):
        exe = shutil.which("emulator") or ""
    if not exe:
        return None
    args = [exe, "-avd", CFG["emu_avd"]] + CFG["emu_options"].split() + (["-wipe-data"] if wipe else [])
    log = None
    try:
        log = open(log_path, "ab")                  # المحاكي يرث نسخته من الملف؛ نسخة البوت تُغلق
    except OSError:
        pass
    if log is not None:
        try:
            log.write(("\n=== %s %s ===\n" % (time.strftime("%H:%M:%S"), " ".join(args[1:]))).encode("utf-8"))
            log.flush()
        except OSError:                             # ENOSPC/EIO: الفاصل لا يمنع التشغيل
            pass
    try:
        subprocess.Popen(args, stdout=log if log is not None else subprocess.DEVNULL, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    finally:
        if log is not None:
            try:
                log.close()
            except OSError:
                pass
    return True


PROC = "/proc"
EMU_PATTERNS = ("qemu-system", "emulator -avd")      # كأنماط kill_emulators


def emulator_procs():
    """عمليات المحاكي من /proc: [(pid، الحالة R/S/D/Z...، ppid، الاسم comm)]؛ تطابق أنماط kill_emulators في سطر الأمر، أو
    الاسم (الزومبي سطر أمره فارغ: qemu-system-x86 أو emulator). None إن تعذّرت قراءة /proc (فيُفحص بـ pgrep)."""
    try:
        entries = [e for e in os.listdir(PROC) if e.isdigit()]
    except OSError:
        return None
    me = os.getpid()
    found = []
    for e in entries:
        pid = int(e)
        if pid == me:
            continue
        try:
            with open(os.path.join(PROC, e, "stat"), "rb") as f:
                st = f.read().decode("utf-8", "replace")
        except OSError:
            continue                                    # انتهت أثناء القراءة
        l, r = st.find("("), st.rfind(")")
        if l < 0 or r < l:
            continue
        comm = st[l + 1:r]
        rest = st[r + 1:].split()
        if len(rest) < 2:
            continue
        state = rest[0]
        try:
            ppid = int(rest[1])
        except ValueError:
            ppid = -1
        try:
            with open(os.path.join(PROC, e, "cmdline"), "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            cmd = ""
        if any(p in cmd for p in EMU_PATTERNS) or comm.startswith("qemu-system") or comm == "emulator":
            found.append((pid, state, ppid, comm))
    return found


def reap_emulator_zombies() -> list:
    """يحصد أبناء البوت الموتى من المحاكي (حالة Z وppid = البوت). بعد التحديث الساخن (os.execv) يبقى المحاكي الذي شغّله
    start_emulator قبله ابناً للعملية بلا كائن Popen يحصده، فيبقى زومبي بعد موته: pgrep وفحص pid في أقفال AVD يرونه حيّاً
    (التشغيل 16). waitpid لكل pid بعينه لا -1 (لا يُحصد ابن لـ subprocess مثل git في خيط النشر). يعيد [(pid، الاسم)]."""
    reaped = []
    me = os.getpid()
    for pid, state, ppid, comm in emulator_procs() or []:
        if state == "Z" and ppid == me:
            try:
                got, _ = os.waitpid(pid, os.WNOHANG)
            except (ChildProcessError, OSError):
                continue
            if got == pid:
                reaped.append((pid, comm))
    return reaped


def emulator_running():
    """هل عملية المحاكي حيّة؟ True/False، وNone إن تعذّر الفحص. من /proc (الزومبي Z والميت X ليسا حياة)، وإلا بـ pgrep."""
    procs = emulator_procs()
    if procs is not None:
        return any(state not in ("Z", "X", "x") for _, state, _, _ in procs)
    try:
        for pat in EMU_PATTERNS:
            p = subprocess.run(["pgrep", "-f", pat], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if p.returncode == 0:
                return True
            if p.returncode != 1:                       # 1: لا عملية؛ غيره خطأ في الفحص
                return None
        return False
    except (subprocess.TimeoutExpired, OSError):
        return None


def emulator_proc_summary() -> str:
    """سطر التشخيص عن عملية المحاكي: حيّة أو غائبة، وحالة كل عملية من /proc (R/S/D/Z، والزومبي ابن البوت أم لا)."""
    procs = emulator_procs()
    running = emulator_running()
    head = {True: "حيّة", False: "غائبة", None: "تعذّر فحصها"}[running]
    if procs:
        me = os.getpid()
        head += " (%s)" % "، ".join("%s %d %s%s" % (c, pid, st, " ابن البوت" if pp == me else "") for pid, st, pp, c in procs[:6])
    return "عملية المحاكي: " + head


def avd_dir(avd=None) -> Path:
    """مجلّد AVD: <emu_avd_home في CFG أو ANDROID_AVD_HOME، وإلا أول موجود من ANDROID_USER_HOME/avd وANDROID_EMULATOR_HOME/avd
    و~/.android/avd (ترتيب بحث المحاكي)>/<avd>.avd."""
    name = "%s.avd" % (avd or CFG["emu_avd"])
    home = CFG.get("emu_avd_home") or os.environ.get("ANDROID_AVD_HOME")
    if home:
        return Path(home) / name
    cands = [os.path.join(os.environ[k], "avd") for k in ("ANDROID_USER_HOME", "ANDROID_EMULATOR_HOME") if os.environ.get(k)]
    cands.append(os.path.join(os.path.expanduser("~"), ".android", "avd"))
    for c in cands:
        if (Path(c) / name).is_dir():
            return Path(c) / name
    return Path(cands[0]) / name


def clear_avd_locks(avd=None) -> list:
    """يحذف ملفات القفل *.lock التي يتركها محاكٍ قُتل بـ kill -9 في مجلّد AVD (يُستدعى بعد kill_emulators). يعيد أسماء ما حُذف."""
    removed = []
    try:
        locks = sorted(avd_dir(avd).glob("*.lock"))
    except OSError:
        return removed
    for p in locks:
        try:
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
            removed.append(p.name)
        except OSError:
            pass
    return removed


def tail_lines(path, n=15, max_bytes=64 * 1024, width=220) -> list:
    """آخر n سطراً غير فارغ من ملف (يقرأ آخر max_bytes فقط)؛ [] إن غاب أو تعذّرت قراءته."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            data = f.read()
    except OSError:
        return []
    lines = [l.rstrip() for l in data.decode("utf-8", "replace").splitlines() if l.strip()]
    return [l[-width:] for l in lines[-n:]] if n > 0 else []


EMU_LOCK_RE = re.compile(r"another emulator instance|multiple emulators with the same avd", re.I)


def emu_log_mentions_lock(log_path=None) -> bool:
    """هل يذكر سجلّ آخر تشغيل للمحاكي (ما بعد آخر سطر فاصل «=== » في EMU_LOG) رفضه لمحاكٍ آخر بالـ AVD نفسه؟"""
    lines = tail_lines(log_path or EMU_LOG, 200, max_bytes=128 * 1024, width=400)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("=== "):
            lines = lines[i + 1:]
            break
    return any(EMU_LOCK_RE.search(l) for l in lines)


def _existing(path):
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    return p


def host_resources(avd=None) -> str:
    """سطر واحد: المساحة الحرّة في أنظمة ملفات مجلّد AVD و/tmp والمنزل (shutil.disk_usage، كـ df -h)، والذاكرة المتاحة والـ swap
    (/proc/meminfo، كـ free -m). ما تعذّرت قراءته يُكتب كذلك ولا يرفع خطأ."""
    parts, seen = [], {}
    for label, path in (("AVD", avd_dir(avd)), ("/tmp", "/tmp"), ("~", os.path.expanduser("~"))):
        try:
            p = _existing(path)
            dev = os.stat(p).st_dev
            if dev in seen:
                parts[seen[dev]][0].append(label)
                continue
            du = shutil.disk_usage(p)
            seen[dev] = len(parts)
            parts.append([[label], "%.1f من %.1f غ.ب حرّة (%d%%)" % (du.free / 2 ** 30, du.total / 2 ** 30,
                                                                    round(100.0 * du.free / du.total) if du.total else 0)])
        except (OSError, ValueError):
            parts.append([[label], "تعذّرت قراءته"])
    disk = "، ".join("%s: %s" % ("+".join(lbl), txt) for lbl, txt in parts)
    try:
        mem = {}
        with open(MEMINFO, encoding="utf-8", errors="replace") as f:
            for line in f:
                k, _, v = line.partition(":")
                if v.strip().split()[:1]:
                    mem[k.strip()] = int(v.strip().split()[0]) // 1024      # ك.ب ← م.ب
        ram = "متاحة %d من %d م.ب" % (mem.get("MemAvailable", mem.get("MemFree", 0)), mem.get("MemTotal", 0))
        if mem.get("SwapTotal"):
            ram += "، swap حرّة %d من %d" % (mem.get("SwapFree", 0), mem["SwapTotal"])
    except (OSError, ValueError):
        ram = "تعذّرت قراءتها"
    return "القرص: %s؛ الذاكرة: %s" % (disk, ram)


def avd_summary(avd=None) -> str:
    """سطر عن مجلّد AVD: حجم userdata-qemu.img (الظاهر والمخصّص فعلاً) وملفات القفل الباقية."""
    d = avd_dir(avd)
    try:
        if not d.is_dir():
            return "مجلّد AVD غير موجود: %s" % d
        bits = []
        for name in ("userdata-qemu.img", "userdata-qemu.img.qcow2"):
            f = d / name
            if f.exists():
                st = f.stat()
                bits.append("%s %.2f غ.ب (مخصّص %.2f)" % (name, st.st_size / 2 ** 30,
                                                         getattr(st, "st_blocks", 0) * 512 / 2 ** 30))
        locks = sorted(p.name for p in d.glob("*.lock"))
        bits.append("أقفال: %s" % ("، ".join(locks) if locks else "لا شيء"))
        return "مجلّد AVD %s: %s" % (d.name, "، ".join(bits))
    except OSError as e:
        return "مجلّد AVD %s: تعذّرت قراءته (%r)" % (d, e)


def emulator_diagnostics(full=True, log_path=None, avd=None, tail=15) -> list:
    """أسطر تشخيص المحاكي للسجل (رخيصة، ولا ترفع خطأ أبداً): الموارد (host_resources)، وحالة عملية المحاكي، ومع full مجلّد AVD
    (avd_summary)؛ ثم آخر tail سطراً من مخرجات المحاكي (EMU_LOG: لماذا لم يُقلع، أو لماذا مات المحاكي السابق)."""
    log_path = log_path or EMU_LOG
    lines = []
    for fn in (lambda: host_resources(avd),
               emulator_proc_summary,
               (lambda: avd_summary(avd)) if full else None):
        if fn is None:
            continue
        try:
            lines.append(fn())
        except Exception as e:                          # noqa: BLE001
            lines.append("تشخيص: خطأ %r" % e)
    tl = tail_lines(log_path, tail)
    if tl:
        lines.append("آخر %d سطراً من سجلّ المحاكي (%s):" % (len(tl), log_path))
        lines.extend("  | " + l for l in tl)
    elif tail > 0:
        lines.append("سجلّ المحاكي %s غير موجود أو فارغ" % log_path)
    return lines


# ============================================================== النسخة الاحتياطية أجزاءً
# النسخة الاحتياطية لبيانات اللعبة (adb backup) تُحفظ أجزاءً مرتّبة أصغر من 50 ميغا لكل منها، فلا يرفض GitHub رفعها:
#   game_backup.ab.part00، game_backup.ab.part01، ...    (تُجمع بالترتيب: cat game_backup.ab.part* > game_backup.ab)
#   game_backup.ab.manifest.json                          (الحجم وsha256 للنسخة كلها ولكل جزء: تحقّق الاستعادة)
# الملف الواحد game_backup.ab لا يُرفع بعد الآن (يُحذف من out/ عند أول نسخة بأجزاء)، لكن الاستعادة ما زالت تقبله في save/
# (حفظ التشغيلات السابقة). البوت يكتب في research/emu/out ويستعيد من research/emu/save (وإلا من out).
#
# أرشفة تشغيل منتهٍ (يدوياً بـ bash من جذر المستودع، بعد أن ينتهي التشغيل ويُسحب الفرع؛ runN-Lxxx وN يُبدَّلان): ينقل النسخة إلى
# save/ إن وُجدت في out/ ثم ينقل out/ كله إلى runs/. الحفظ القديم في save/ لا يُحذف (git rm) إلا بعد التحقق من وجود بديله في
# out/: ملف الوصف (نسخة أجزاء) أو الملف الواحد (كود ما قبل الأجزاء، مثل التشغيل 16)؛ وتشغيل بلا نسخة (بلا فوز، أو فشلت كل نسخه
# كالتشغيل 10) يُبقي save/ كما هو. git rm يحذف الحفظ القديم كله (الملف الواحد والأجزاء وملف الوصف) فلا يبقى جزء زائد من نسخة أكبر.
# الأوامر سلسلة واحدة (&&): إن فشل أمر فلا commit ولا push، والرجوع: git reset -q --hard HEAD
# --- أوامر الأرشفة (بداية)
#   O=research/emu/out; S=research/emu/save; R=research/emu/runs/runN-Lxxx
#   if [ -f "$O/game_backup.ab.manifest.json" ]; then
#     git rm -r -q --ignore-unmatch "$S/game_backup.ab*" && mkdir -p "$S" &&
#       git mv "$O/game_backup.ab.manifest.json" "$O"/game_backup.ab.part* "$S/"
#   elif [ -f "$O/game_backup.ab" ]; then
#     git rm -r -q --ignore-unmatch "$S/game_backup.ab*" && mkdir -p "$S" && git mv "$O/game_backup.ab" "$S/"
#   else
#     echo "لا نسخة في out/: يبقى save/ كما هو"
#   fi && git mv "$O" "$R" && git commit -q -m "أرشفة التشغيل N" && git push
# --- أوامر الأرشفة (نهاية)   (يجرّبها TestArchiveCommands على مستودع مؤقت)
BACKUP_NAME = "game_backup.ab"
BACKUP_MANIFEST = BACKUP_NAME + ".manifest.json"
BACKUP_PART_RE = re.compile(r"^game_backup\.ab\.part(\d{2,})$")
BACKUP_MAGIC = b"ANDROID BACKUP"


def backup_part_name(i) -> str:
    return "%s.part%02d" % (BACKUP_NAME, i)


def is_backup_file(name) -> bool:
    """ملفات النسخة الاحتياطية في مجلد (الملف الواحد القديم، والأجزاء، وملف الوصف)؛ لا الملفات المؤقتة المبدوءة بنقطة."""
    return name in (BACKUP_NAME, BACKUP_MANIFEST) or bool(BACKUP_PART_RE.match(name))


def backup_parts_in(d: Path):
    """الأجزاء الموجودة في المجلد: [(الرقم، المسار)] مرتّبة بالرقم."""
    found = []
    try:
        for p in Path(d).iterdir():
            m = BACKUP_PART_RE.match(p.name)
            if m and p.is_file():
                found.append((int(m.group(1)), p))
    except OSError:
        return []
    return sorted(found)


def _sha256_file(path, chunk=1 << 20):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def split_backup(src, dest_dir, part_bytes, meta=None) -> dict:
    """يقسم ملف النسخة src إلى أجزاء مرتّبة في dest_dir، كل جزء part_bytes بايت على الأكثر (الأخير أصغر أو مساوٍ)، مع ملف
    الوصف (الحجم وsha256 للكل ولكل جزء، وmeta). تُكتب الأجزاء أولاً بأسماء مؤقتة مبدوءة بنقطة (لا ينسخها النشر) ثم تُعاد تسميتها
    كلها وملف الوصف آخراً، ثم تُحذف الأجزاء الأعلى الباقية من نسخة أكبر والملف الواحد القديم. يعيد ملف الوصف (dict)."""
    import hashlib
    src, dest_dir = Path(src), Path(dest_dir)
    part_bytes = int(part_bytes)
    if part_bytes <= 0:
        raise ValueError("part_bytes")
    total = src.stat().st_size
    if total <= 0:
        raise ValueError("نسخة فارغة")
    dest_dir.mkdir(parents=True, exist_ok=True)
    whole = hashlib.sha256()
    parts, tmps = [], []
    try:
        with open(src, "rb") as f:
            i = 0
            while True:
                name = backup_part_name(i)
                tmp = dest_dir / (".%s.tmp" % name)
                h, size = hashlib.sha256(), 0
                with open(tmp, "wb") as g:
                    tmps.append(tmp)
                    while size < part_bytes:
                        b = f.read(min(1 << 20, part_bytes - size))
                        if not b:
                            break
                        g.write(b)
                        h.update(b)
                        whole.update(b)
                        size += len(b)
                if size == 0:                      # الحجم مضاعف تام لحجم الجزء: لا جزء فارغ في آخرها
                    tmps.pop()
                    os.remove(tmp)
                    break
                parts.append({"name": name, "size": size, "sha256": h.hexdigest()})
                i += 1
                if size < part_bytes:
                    break
        if sum(pt["size"] for pt in parts) != total:
            raise OSError("تغيّر حجم النسخة أثناء تقسيمها")
        man = {"format": 1, "name": BACKUP_NAME, "size": total, "sha256": whole.hexdigest(),
               "part_bytes": part_bytes, "parts": parts}
        if meta:
            man.update({k: v for k, v in meta.items() if k not in man})
        mtmp = dest_dir / (".%s.tmp" % BACKUP_MANIFEST)
        tmps.append(mtmp)
        mtmp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        for pt in parts:
            os.replace(dest_dir / (".%s.tmp" % pt["name"]), dest_dir / pt["name"])
        os.replace(mtmp, dest_dir / BACKUP_MANIFEST)
        tmps = []
    finally:
        for t in tmps:
            try:
                os.remove(t)
            except OSError:
                pass
    keep = {pt["name"] for pt in parts}
    for _n, p in backup_parts_in(dest_dir):
        if p.name not in keep:
            os.remove(p)
    legacy = dest_dir / BACKUP_NAME
    if legacy.exists():
        os.remove(legacy)
    return man


def join_backup(src_dir, out_path):
    """يجمع النسخة من مجلد إلى out_path. يعيد (المسار، الوصف) إن صحّت، أو (None، السبب) إن لم توجد أو تلفت:
    - ملف وصف: الأجزاء التي يسمّيها كلها بالترتيب، وحجم كل جزء وبصمته ثم حجم الكل وبصمته يجب أن تطابقه؛
    - أجزاء بلا ملف وصف: متتالية من 00 بلا فجوة (لا تحقق من البصمة)؛
    - الملف الواحد القديم game_backup.ab (حفظ ما قبل الأجزاء): يُعاد مساره كما هو بلا نسخ.
    وفي كل حال يجب أن تبدأ النسخة بـ «ANDROID BACKUP» (ترويسة adb backup)."""
    import hashlib
    src_dir, out_path = Path(src_dir), Path(out_path)

    def magic_ok(p):
        try:
            with open(p, "rb") as f:
                return f.read(len(BACKUP_MAGIC)) == BACKUP_MAGIC
        except OSError:
            return False

    parts = backup_parts_in(src_dir)
    mpath = src_dir / BACKUP_MANIFEST
    if mpath.exists() or parts:
        man = None
        if mpath.exists():
            try:
                man = json.loads(mpath.read_text(encoding="utf-8"))
                names = [pt["name"] for pt in man["parts"]]
                if not names or any(not BACKUP_PART_RE.match(str(n)) for n in names):
                    raise ValueError(names)
                int(man["size"])
            except (OSError, ValueError, KeyError, TypeError) as e:
                return None, "ملف الوصف تالف (%r)" % (e,)
            plist = [(pt["name"], src_dir / pt["name"], pt) for pt in man["parts"]]
        else:
            nums = [n for n, _p in parts]
            if nums != list(range(len(nums))):
                return None, "أجزاء بلا ملف وصف وفيها فجوة (%s)" % ",".join("%02d" % n for n in nums)
            plist = [(p.name, p, None) for _n, p in parts]
        for name, p, _pt in plist:
            if not p.is_file():
                return None, "الجزء %s غائب" % name
        whole = hashlib.sha256()
        total = 0
        tmp = out_path.with_name("." + out_path.name + ".tmp")
        try:
            with open(tmp, "wb") as g:
                for name, p, pt in plist:
                    h, size = hashlib.sha256(), 0
                    with open(p, "rb") as f:
                        while True:
                            b = f.read(1 << 20)
                            if not b:
                                break
                            g.write(b)
                            h.update(b)
                            whole.update(b)
                            size += len(b)
                    if pt is not None and (size != int(pt.get("size", -1)) or h.hexdigest() != pt.get("sha256")):
                        raise ValueError("الجزء %s تالف (الحجم %d، المتوقع %s)" % (name, size, pt.get("size")))
                    total += size
            if man is not None and (total != int(man["size"]) or whole.hexdigest() != man.get("sha256")):
                raise ValueError("النسخة المجموعة لا تطابق ملف الوصف (الحجم %d، المتوقع %s)" % (total, man["size"]))
            if not magic_ok(tmp):
                raise ValueError("النسخة المجموعة لا تبدأ بترويسة adb backup")
            os.replace(tmp, out_path)
        except (OSError, ValueError) as e:
            try:
                os.remove(tmp)
            except OSError:
                pass
            return None, str(e) if isinstance(e, ValueError) else "خطأ في القراءة (%r)" % (e,)
        how = "تحقّق الحجم والبصمة" if man is not None else "بلا ملف وصف: لا تحقق من البصمة"
        return out_path, "%d جزء، %d ك.ب، %s" % (len(plist), total // 1024, how)
    legacy = src_dir / BACKUP_NAME
    if legacy.is_file() and legacy.stat().st_size > 2048:
        if not magic_ok(legacy):
            return None, "الملف الواحد لا يبدأ بترويسة adb backup"
        return legacy, "ملف واحد (صيغة ما قبل الأجزاء)، %d ك.ب" % (legacy.stat().st_size // 1024)
    return None, "لا نسخة"


def verify_backup(path, chunk=1 << 20):
    """هل ملف adb backup كامل؟ adb backup يعود بنجاح ويترك ملفاً مقطوعاً إن مات المحاكي أثناء النقل أو قُتل بعد مهلته، فلا يكفي
    الحجم. تُقرأ أسطر الترويسة الأربعة («ANDROID BACKUP»، الإصدار، علم الضغط، «none»: البوت لا يشفّر)، ثم يُفكّ تيار zlib كله
    (علم الضغط 1) ويُشترط أن ينتهي التيار (eof) بلا بيانات بعده، أو (بلا ضغط) أن يكون أرشيف tar بكتل 512 كاملة. ثم يُشترط في
    الحالين أن ينتهي tar بكتلتي الأصفار (finalizeBackup في Android). يعيد (ok، السبب)."""
    import zlib
    try:
        with open(path, "rb") as f:
            head = [f.readline(64) for _ in range(4)]
            if head[0] != BACKUP_MAGIC + b"\n":
                return False, "لا ترويسة adb backup"
            try:
                int(head[1].strip())
                comp = int(head[2].strip())
            except ValueError:
                return False, "ترويسة تالفة (%r)" % (b"".join(head[1:3]),)
            if head[3].strip() != b"none":
                return False, "نسخة مشفّرة أو ترويسة تالفة (%r)" % (head[3].strip()[:20],)
            if comp not in (0, 1):
                return False, "علم ضغط غريب (%d)" % comp
            d = zlib.decompressobj() if comp else None
            total, tail = 0, b""
            while True:
                b = f.read(chunk)
                if not b:
                    break
                if d is not None:
                    if d.eof:
                        return False, "بيانات بعد نهاية تيار الضغط"
                    try:
                        b = d.decompress(b)
                    except zlib.error as e:
                        return False, "تيار الضغط تالف (%s)" % (e,)
                total += len(b)
                tail = (tail + b)[-1024:]
            if d is not None:
                try:
                    rest = d.flush()
                except zlib.error as e:
                    return False, "تيار الضغط تالف (%s)" % (e,)
                total += len(rest)
                tail = (tail + rest)[-1024:]
                if not d.eof:
                    return False, "مقطوعة: تيار الضغط لم يكتمل (%d ك.ب بعد الفكّ)" % (total // 1024)
                if d.unused_data:
                    return False, "بيانات بعد نهاية تيار الضغط"
            if total < 1024 or total % 512:
                return False, "مقطوعة: أرشيف tar ليس كتلاً كاملة (%d بايت)" % total
            if tail.count(0) != 1024:
                return False, "مقطوعة: أرشيف tar بلا كتلتي النهاية"
    except OSError as e:
        return False, "خطأ في القراءة (%r)" % (e,)
    return True, "كاملة (%d ك.ب بعد الفكّ)" % (total // 1024)


def find_backup(dirs, out_path, log=None):
    """أول نسخة صالحة من المجلدات بالترتيب (save ثم out). في كل مجلد: الأجزاء (أو الملف الواحد إن لم توجد)، وإن تلفت الأجزاء
    وبجانبها ملف واحد قديم صالح فهو بديلها. يعيد (المسار، الوصف) أو (None، None)؛ log يُعطى سبب رفض كل مصدر."""
    for d in dirs:
        d = Path(d)
        path, info = join_backup(d, out_path)
        if path is not None:
            return path, "%s/: %s" % (d.name, info)
        if info != "لا نسخة" and log:
            log("نسخة احتياطية مرفوضة في %s/: %s" % (d.name, info))
        legacy = d / BACKUP_NAME
        if info != "لا نسخة" and legacy.is_file() and legacy.stat().st_size > 2048:
            with open(legacy, "rb") as f:
                if f.read(len(BACKUP_MAGIC)) == BACKUP_MAGIC:
                    return legacy, "%s/: ملف واحد قديم بدل الأجزاء التالفة، %d ك.ب" % (d.name, legacy.stat().st_size // 1024)
    return None, None


def emu_restart_policy(restarts, fruitless, won_since, minutes_since, minutes_left, cfg=None):
    """قرار إعادة تشغيل المحاكي الميت (recover_device). المدخلات: restarts إعادات هذا التشغيل حتى الآن، fruitless إعادات متتالية
    لم يتبعها تقدّم، won_since المراحل المكتملة منذ آخر إعادة، minutes_since دقائق اللعب منذ عودة المحاكي في آخر إعادة، minutes_left
    ما بقي من وقت التشغيل. «التقدّم» بعد إعادة: فوز بمرحلة واحدة على الأقل، أو emu_progress_min دقيقة لعب (المحاكي سليم ولو
    انتظر البوت الأرواح)؛ وأول عطل في التشغيل لا تسبقه إعادة فلا يُحسب بلا تقدّم.
    يعيد (allow, fruitless_new, reason): هل يُعاد المحاكي، والعدّاد الجديد، وسبباً عربياً للسجل."""
    cfg = cfg or CFG
    progress = won_since > 0 or minutes_since >= cfg["emu_progress_min"]
    if restarts == 0 or progress:
        fruitless = 0
    else:
        fruitless += 1
    if restarts == 0:
        why = "أول عطل في التشغيل"
    elif won_since > 0:
        why = "تقدّم منذ الإعادة السابقة: %d مرحلة في %.0f دقيقة" % (won_since, minutes_since)
    elif progress:
        why = "تقدّم منذ الإعادة السابقة: %.0f دقيقة لعب بلا عطل" % minutes_since
    else:
        why = "بلا تقدّم منذ الإعادة السابقة (%.0f دقيقة بلا فوز)؛ إعادات متتالية بلا تقدّم: %d من %d" % (
            minutes_since, fruitless, cfg["emu_fruitless_max"])
    if minutes_left < cfg["emu_restart_min_left"]:
        return False, fruitless, "بقي %.1f دقيقة فقط من التشغيل (أقل من %.0f): لا فائدة من إعادة المحاكي" % (
            minutes_left, cfg["emu_restart_min_left"])
    if restarts >= cfg["emu_restarts"]:
        return False, fruitless, "بلغت إعادات المحاكي حدّ الأمان (%d إعادة في التشغيل)" % restarts
    if fruitless >= cfg["emu_fruitless_max"]:
        return False, fruitless, "%d إعادات متتالية للمحاكي بلا أي تقدّم (لا فوز ولا %.0f دقيقة لعب بعد أيّ منها)" % (
            fruitless, cfg["emu_progress_min"])
    return True, fruitless, why


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
        self.cap_fails = 0             # لقطات فاشلة متتالية (حارس المحاكي: recover_device)
        self.emu_restarts = 0          # إعادات تشغيل المحاكي في هذا التشغيل
        self.emu_fruitless = 0         # إعادات متتالية لم يتبعها تقدّم (emu_restart_policy)
        self.emu_restart_at = self.t_start  # متى عاد المحاكي (أو فشلت إعادته) آخر مرة
        self.emu_restart_levels = 0    # المراحل المكتملة عند آخر إعادة
        self.last_ok_grab = self.t_start  # آخر لقطة ناجحة: «دقائق اللعب» بعد إعادة تنتهي عندها لا عند قرار الحارس
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
        self.sig_data = {}             # sig_id -> سجلّ البداية (new_sig_rec: المحاولات، الطريق المسدود، الأبواب، الذاكرة)
        self.sig_mem = {}              # sig_id -> ذاكرة طبقات بدايتها (القاموس نفسه في memory_by_sig) للحفظ قبل التحديث
        self.legacy_fail_levels = set()  # مراحل خسرها بوت قبل التحديث بكود بلا "sigs": لا تُعاد محاولته الحتمية الخاسرة
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
        self.last_tab_home = 0.0       # آخر ضغط على تبويب «Home» من صفحة تبويب أخرى
        self.tab_home_taps = 0         # ضغطات «Home» في الشاشة المجهولة الحالية (الثالثة تلمس موضع «Level N»)
        self.last_ad_act = 0.0          # آخر محاولة لإغلاق إعلان بملء الشاشة
        self.ad_acts = 0
        self.ad_kind = None             # "black" | "white" للإعلان الظاهر الآن
        self.ad_since = 0.0             # منذ متى يظهر هذا الإعلان (لمهلة إعادة التشغيل)
        self.ad_last = None             # آخر لقطة فيها إعلان (فجوة أكثر من 20 ث = إعلان جديد)
        self.logo_since = 0.0           # شعار «MAGIC SORT» فوق لوحة معتمة: منذ متى
        self.logo_last = None
        self.logo_backs = 0
        self.last_backup = time.time()  # آخر نسخة احتياطية لبيانات اللعبة (backup_app)
        self.backup_levels = 0         # عدد المراحل المكتملة عند آخر نسخة احتياطية ناجحة
        self.final_backup_done = False
        self.backups_saved = 0         # نسخ حُفظت في هذا التشغيل (الاستعادة بعدها من out/ لأنها أحدث من save/)
        self.backup_hold = False       # لا نسخ احتياطية حتى نهاية التشغيل: أُعيد تثبيت اللعبة ولم تُستعد نسختها (restore_after_install)
        self.restore_had_backup = False  # آخر restore_app وجدت نسخة صالحة (فشلها يضيّع تقدّماً، لا مجرد بداية من 1)
        self.start_probe = None        # (عدد القوارير، مفتاح الحالة) في أول قراءة لمرحلة جديدة: تُعتمد حين تتكرّر
        self.start_probe_tries = 0
        self.start_same = 0            # قراءات متتالية مطابقة لـ start_probe
        self.arrow_shots = 0
        self.net_required = False      # ظهرت نافذة «No internet connection»: لا وضع طيران بعدها
        self.restart_n = None          # رقم المرحلة التي ستُعاد (بعد «Give Up» أو إعادة مكتشفة) إن لم يُقرأ العنوان
        self.saved_starts = set()      # مراحل حُفظت لقطة بدايتها (إعادة المرحلة لا تستهلك صوراً جديدة)
        self.level_fails = Counter()   # رقم المرحلة -> مرات «Give Up» فيها في هذا التشغيل
        self.coins = None              # آخر رصيد عملات مقروء
        self.lives_until = 0.0         # لا يُضغط زرّ المرحلة قبل هذا الوقت (الأرواح نفدت ولا عملات للملء)
        self.last_refill_tap = -1e9    # آخر ضغط على «Refill» (لا ضغطة ثانية إن عادت النافذة بعدها مباشرة)
        self.refills = 0
        self.last_lives_log = 0.0
        self.lives_shots = 0
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
            local = set()
            for p in self.out.dir.iterdir():
                if p.name.startswith(".") or not p.is_file():
                    continue
                local.add(p.name)
                st = p.stat()
                sig = (st.st_size, st.st_mtime_ns)
                if ref.get(p.name) != sig:
                    shutil.copy2(p, dst / p.name)
                    self.copied_sig[p.name] = sig
            # ملفات النسخة الاحتياطية تتبع out/ تماماً: الجزء الأعلى الباقي من نسخة أكبر والملف الواحد القديم (لا يُرفع ملف فوق
            # 50 ميغا) يُحذفان من شجرة النشر أيضاً فيُسجَّل حذفهما في الـ commit
            for p in dst.iterdir():
                if is_backup_file(p.name) and p.name not in local and p.is_file():
                    try:
                        p.unlink()
                    except OSError:
                        pass
                    self.copied_sig.pop(p.name, None)

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
                    elif c == "backup":
                        self.backup_app()
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
        self.save_counters()                   # بعد النشر (قد يطول) حتى يبقى الملف حديثاً عند قراءته
        sys.stdout.flush()
        os.execv(sys.executable, argv)

    def save_counters(self):
        """قبل os.execv في أمر «update»: عدّادات السياسات التي لا تُقرأ من الشاشة (مرات «Give Up» لكل مرحلة، موعد الروح
        القادمة، آخر «Refill»، الرصيد) في ملف مؤقت يقرؤه البوت الجديد مرة واحدة، فلا تعود صفراً بعد كل تحديث ساخن."""
        try:
            tmp = STATE_FILE.with_name("." + STATE_FILE.name + ".tmp")
            tmp.write_text(json.dumps({
                "t": time.time(), "level_fails": {str(k): int(v) for k, v in self.level_fails.items()},
                "lives_until": float(self.lives_until), "last_refill_tap": float(self.last_refill_tap),
                "refills": int(self.refills), "coins": self.coins, "sigs": self.sigs_json(),
                "emu": [int(self.emu_restarts), int(self.emu_fruitless), float(self.emu_restart_at),
                        int(self.emu_restart_levels)],
                "backups": int(self.backups_saved), "backup_hold": bool(self.backup_hold)}), encoding="utf-8")
            os.replace(tmp, STATE_FILE)
        except (OSError, TypeError, ValueError) as e:
            self.log("تعذّر حفظ العدّادات قبل التحديث: %r" % e)

    def sigs_json(self):
        """سجلّات البدايات بصيغة JSON (ذاكرة الطبقات من sig_mem: مفاتيحها صفوف)."""
        out = {}
        for sid, rec in self.sig_data.items():
            d = dict(rec)
            mem = self.sig_mem.get(sid)
            if mem is not None:
                d["mem"] = [[k, p, c] for (k, p), c in sorted(mem.items())]
            out[sid] = d
        return out

    def load_sigs(self, d) -> int:
        """سجلّات البدايات من ملف الحالة؛ الملف القديم بلا "sigs" أو سجلّ تالف يُهمل بصمت."""
        n = 0
        sigs = d.get("sigs") if isinstance(d, dict) else None
        if not isinstance(sigs, dict):
            return 0
        for sid, raw in list(sigs.items())[:SIG_MAX]:
            rec = clean_sig_rec(raw)
            if rec is not None and isinstance(sid, str):
                self.sig_data[sid] = rec
                n += 1
        return n

    def load_counters(self, max_age=600.0) -> bool:
        """بعد «update» (--no-setup): عدّادات البوت السابق إن كان ملفها أحدث من 10 دقائق، ثم يُحذف (لا يُقرأ مرتين). أي خطأ
        يُهمل بصمت: البدء بعدّادات صفرية كما كان أفضل من توقف البوت."""
        try:
            d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        try:
            STATE_FILE.unlink()
        except OSError:
            pass
        try:
            if not (isinstance(d, dict) and 0 <= time.time() - float(d.get("t", 0)) < max_age):
                return False
            fails = {int(k): int(v) for k, v in (d.get("level_fails") or {}).items()}
            lives_until = float(d.get("lives_until") or 0.0)
            last_refill = float(d.get("last_refill_tap", -1e9))
            refills = int(d.get("refills") or 0)
            coins = None if d.get("coins") is None else int(d["coins"])
        except (TypeError, ValueError, AttributeError):
            return False
        self.level_fails.update(fails)
        self.lives_until, self.last_refill_tap, self.refills = lives_until, last_refill, refills
        if coins is not None:
            self.coins = coins
        try:
            # إعادات المحاكي قبل التحديث الساخن: حدّ الأمان وعدّاد «بلا تقدّم» لا يعودان صفراً بعد «update»
            er, ef, eat, elv = d["emu"]
            self.emu_restarts, self.emu_fruitless = max(0, int(er)), max(0, int(ef))
            self.emu_restart_at, self.emu_restart_levels = float(eat), min(int(elv), self.levels_done)
        except (KeyError, TypeError, ValueError):
            pass
        try:
            # نسخ هذا التشغيل قبل التحديث: بعدها تستعيد restore_app من out/ (الأحدث) لا من save/ (حفظ بداية التشغيل)
            self.backups_saved = max(self.backups_saved, int(d.get("backups") or 0))
        except (TypeError, ValueError):
            pass
        # منع النسخ بعد استعادة فاشلة (restore_after_install) يبقى بعد التحديث الساخن
        self.backup_hold = self.backup_hold or bool(d.get("backup_hold"))
        try:
            nsig = self.load_sigs(d)
        except Exception:                               # noqa: BLE001
            nsig = 0
        if not isinstance(d.get("sigs"), dict):
            # ملف من كود بلا ذاكرة البدايات: أول محاولة لكل بداية في هذه المراحل كانت ستكون الاستدعاء الحتمي نفسه الذي خسر
            self.legacy_fail_levels = {n for n, v in self.level_fails.items() if v > 0}
        self.log("عدّادات ما قبل التحديث: «Give Up» لكل مرحلة %s، انتظار الأرواح %.0f ث، الرصيد %s، ذاكرة %d بداية"
                 % (dict(self.level_fails) or "-", max(0.0, self.lives_until - time.time()),
                    self.coins if self.coins is not None else "?", nsig))
        return True

    def confirm_backup_dialog(self, tries=25):
        """نافذة تأكيد adb backup/restore (com.android.backupconfirm): يُلمس زرّ الموافقة («Back up my data» أو «Restore my
        data») بموضعه من uiautomator. يعيد True إن لُمس."""
        import re
        pat = re.compile(r'resource-id="com\.android\.backupconfirm:id/button_allow"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
        for _ in range(tries):
            time.sleep(1.5)
            self.dev.sh("uiautomator dump /sdcard/bot_ui.xml", timeout=30)
            xml = self.dev.sh("cat /sdcard/bot_ui.xml", timeout=20)
            m = pat.search(xml)
            if m:
                x1, y1, x2, y2 = (int(v) for v in m.groups())
                self.dev.tap((x1 + x2) // 2, (y1 + y2) // 2)
                return True
        return False

    def backup_app(self):
        """أمر «backup» (وتلقائياً كل 45 دقيقة وبعد فوز جديد وقبل النهاية): نسخة احتياطية لبيانات اللعبة بلا APK (adb backup)
        تُحفظ أجزاءً مرتّبة أصغر من 50 ميغا في out/ (split_backup: game_backup.ab.partNN وملف الوصف؛ انظر أوامر الأرشفة فوق
        BACKUP_NAME) وتُرفع مع المخرجات، حتى يستعيدها تشغيل لاحق على محاكٍ جديد (restore_app) فيكمل من المرحلة نفسها بدل البدء
        من 1. تطلب تأكيداً على الشاشة يُلمس آلياً. لا تُؤخذ مع backup_hold (اللعبة لم تُستعد بعد إعادة تثبيتها: نسختها تكتب
        حالة المرحلة 1 فوق آخر نسخة سليمة في out/)."""
        self.last_backup = time.time()
        if self.backup_hold:
            self.log("لا تُكتب نسخة فوق آخر نسخة سليمة: اللعبة لم تُستعد بعد إعادة تثبيتها (backup_hold حتى نهاية التشغيل)")
            return False
        tmp = "/tmp/game_backup.ab"
        try:
            os.remove(tmp)
        except OSError:
            pass
        try:
            p = subprocess.Popen(self.dev._cmd(["backup", "-f", tmp, "-noapk", PKG]),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            self.log("تعذّرت النسخة الاحتياطية: %r" % e)
            return False
        ok = self.confirm_backup_dialog()
        try:
            p.wait(timeout=300)
        except subprocess.TimeoutExpired:
            p.kill()
        return self.store_backup(tmp, ok)

    def store_backup(self, tmp, confirmed=True) -> bool:
        """يحفظ ملف adb backup المؤقت أجزاءً في out/ (تحت قفل الإخراج، فلا ينسخ النشر مجموعة ناقصة). True إن حُفظ. الأرشيف
        يُتحقق من اكتماله أولاً (verify_backup): نسخة قطعها موت المحاكي أو مهلة adb لا تحلّ محلّ آخر نسخة سليمة في out/ ولا تُغيّر
        backup_levels (فتُعاد المحاولة بعد backup_win_min دقيقة)."""
        size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        saved = False
        complete, why = (False, "")
        if 2048 < size < CFG["backup_max_mb"] * 1024 * 1024:
            complete, why = verify_backup(tmp)
            if not complete:
                self.log("نسخة احتياطية غير كاملة (%d ك.ب، التأكيد %s): %s؛ تبقى النسخة السابقة كما هي"
                         % (size // 1024, confirmed, why))
        if complete:
            try:
                with self.out.lock:
                    man = split_backup(tmp, self.out.dir, CFG["backup_part_mb"] * 1024 * 1024,
                                       meta={"levels_done": self.levels_done, "time": time.strftime("%Y-%m-%d %H:%M:%S")})
                self.log("نسخة احتياطية لبيانات اللعبة: %d ك.ب في %d جزء (%d مرحلة مكتملة)"
                         % (size // 1024, len(man["parts"]), self.levels_done))
                self.backup_levels = self.levels_done
                self.backups_saved += 1
                saved = True
            except (OSError, ValueError) as e:
                self.log("تعذّر حفظ النسخة الاحتياطية أجزاءً: %r" % (e,))
        elif not why:
            self.log("لم تُحفظ النسخة الاحتياطية (الحجم %d بايت، التأكيد %s)" % (size, confirmed))
        time.sleep(2)
        if PKG not in self.dev.focus():
            self.dev.launch()
        return saved

    def restore_app(self):
        """تشغيل جديد على محاكٍ فارغ: يستعيد بيانات اللعبة من نسخة سابقة قبل أول تشغيل لها، فتكمل من مرحلتها: أجزاء
        research/emu/save (تُجمع وتُتحقق ببصمتها) أو ملفها الواحد القديم، وإلا out/ (find_backup). وبعد نسخة حُفظت في هذا التشغيل
        (محاكٍ أُعيد ففقد اللعبة) out/ أولاً لأنها أحدث. adb restore يطلب تأكيداً على الشاشة يُلمس آلياً."""
        dirs = (HERE.parent / "save", self.out.dir)
        if self.backups_saved:
            dirs = dirs[::-1]
        src, info = find_backup(dirs, Path("/tmp/game_backup_restore.ab"), self.log)
        self.restore_had_backup = src is not None
        if src is None:
            self.log("لا نسخة احتياطية صالحة: اللعبة تبدأ من المرحلة 1")
            return False
        complete, why = verify_backup(src)
        if not complete:
            # نسخة من كود ما قبل التحقق (store_backup لا يحفظ المقطوعة الآن): تُستعاد على أي حال، فبعضها خير من المرحلة 1
            self.log("تحذير: النسخة المستعادة غير كاملة (%s)؛ قد يستعيد adb جزءاً من البيانات فقط" % why)
        try:
            p = subprocess.Popen(self.dev._cmd(["restore", str(src)]), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            self.log("تعذّرت الاستعادة: %r" % e)
            return False
        ok = self.confirm_backup_dialog()
        timed_out = False
        try:
            p.wait(timeout=300)
        except subprocess.TimeoutExpired:
            p.kill()
            timed_out = True
        if ok and timed_out:
            # قُتل adb restore بعد 300 ث: قد تكون البيانات مستعادة جزئياً، فلا تُعدّ استعادة (restore_after_install يعيدها)
            self.log("استعادة بيانات اللعبة من %s: انتهت مهلة adb restore بعد التأكيد (لم تكتمل)" % info)
            return False
        self.log("استعادة بيانات اللعبة من %s: %s" % (info, "تمت" if ok else "لم يظهر التأكيد"))
        return ok

    def restore_after_install(self, until=None) -> bool:
        """بعد تثبيت اللعبة على محاكٍ فارغ (أول التشغيل، أو محاكٍ أُعيد أو مُحيت بياناته): restore_app، ومرة ثانية إن فشلت وكانت
        هناك نسخة صالحة وبقي 6 دقائق قبل until. بعد استعادة ناجحة: last_backup = الآن وbackup_levels = levels_done (لا نسخة فورية من
        حالة مستعادة أقدم يُكتب في وصفها levels_done الحالي). وإن بقيت لم تُستعد ونسخة صالحة موجودة: backup_hold حتى نهاية التشغيل،
        فلا تحلّ نسخة من لعبة تبدأ من المرحلة 1 محلّ آخر نسخة سليمة في out/ (ولا تنقلها الأرشفة إلى save/)."""
        ok = self.restore_app()
        if not ok and self.restore_had_backup and (until is None or until - time.time() > 6 * 60):
            self.log("لم تُستعد النسخة الاحتياطية بعد تثبيت اللعبة: محاولة ثانية")
            ok = self.restore_app()
        if ok:
            self.last_backup = time.time()
            self.backup_levels = self.levels_done
        elif self.restore_had_backup:
            self.backup_hold = True
            self.log("لا تُكتب نسخة فوق آخر نسخة سليمة حتى نهاية التشغيل: اللعبة لم تُستعد بعد تثبيتها (تبدأ من المرحلة 1)")
        return bool(ok)

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
            lines.append("المرحلة الحالية: %d%s (حركات %d، مخفي %d، إخفاقات %d، أدوات %s، %.1f دقيقة)"
                         % (lv.n, {"hard": " صعبة", "superhard": " صعبة جداً"}.get(lv.badge, ""), lv.moves, hidden,
                            lv.fails, lv.boosters or "-", (time.time() - lv.t0) / 60))
            lines.append("الحالة المقروءة: %s" % solver.describe(lv.last_state))
        wait = self.lives_until - time.time()
        lines.append("العملات: %s، «Give Up» لكل مرحلة: %s%s"
                     % (self.coins if self.coins is not None else "?", dict(self.level_fails) or "-",
                        "، انتظار الأرواح %.0f دقيقة" % (wait / 60) if wait > 0 else ""))
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
            self.restore_after_install(self.deadline)
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

    def install_game(self, until=None):
        """يثبّت حزمة اللعبة (محاولات بتركيبات الملفات). until: وقت لا تتجاوزه المحاولات (restart_emulator قرب نهاية التشغيل)."""
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
            tmo = 400
            if until is not None:
                tmo = min(400, int(until - time.time()))
                if tmo < 30:
                    self.log("تثبيت اللعبة: نفدت المهلة")
                    return False
            rc, out = self.dev.run(["install-multiple", "-r", "-g"] + [str(p) for p in files],
                                   timeout=tmo)
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
            # نسخة احتياطية لتقدّم اللعبة (يكمل منها التشغيل التالي): بعد فوز جديد إن مضت backup_win_min دقيقة على آخر نسخة،
            # وكل 45 دقيقة، وقبل النهاية بـ 6 دقائق. (التشغيل العاشر: مات المحاكي ثلاث مرات ولم تُحفظ نسخة بعد المرحلة 109، فيعيد
            # التشغيل التالي المراحل 109-112.)
            if self.git_enabled and self.levels_done > 0 and not self.backup_hold and (
                    time.time() - self.last_backup > 45 * 60
                    or (self.levels_done > self.backup_levels
                        and time.time() - self.last_backup > CFG["backup_win_min"] * 60)
                    or (self.deadline - time.time() < 6 * 60 and not self.final_backup_done)):
                if self.deadline - time.time() < 6 * 60:
                    self.final_backup_done = True
                self.backup_app()
                fr = None
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
                    self.cap_fails += 1
                    self.log("فشلت اللقطة؛ إعادة المحاولة (%d)" % self.cap_fails)
                    if self.recover_device():
                        continue
                    self.dev.run(["wait-for-device"], timeout=20)
                    time.sleep(3)
                    continue
                self.cap_fails = 0
                self.last_ok_grab = time.time()
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
                if kind in ("button", "close") and self.lives_waiting():
                    self.repeat = (None, 0)    # انتظار الأرواح المقصود ليس «تكراراً رغم النقر» (ولا رجوع بعده)
                elif kind in ("button", "close") and self.same_screen(fr) > 6:
                    self.log("الشاشة نفسها (%s) تتكرّر رغم النقر؛ تصعيد" % kind)
                    self.save_repeat(fr, kind)
                    mid = (fr.arr.shape[1] // 2, int(STD_H * 0.62))
                    # نقرة الوسط لا تلمس زرّاً يصرف العملات («Play On 900» في «Continue?» بعد «Give Up»): رجوع بدلها
                    if self.repeat_escalations % 2 == 0 or self.vis.paid_at(fr, mid):
                        self.dev.key(4)
                    else:
                        self.dev.tap_std(*mid)
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
                elif kind == "lives":
                    fr = self.on_lives(fr)
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
        if self.level_hint is None:
            self.level_hint = lv.n + 1         # إن لم يُقرأ عنوان المرحلة التالية ولا زرّها (لا levels_done + 1)
        dt = time.time() - lv.t0
        self.log("فوز بالمرحلة %d (%s): %d حركة في %.0f ث، أدوات %s"
                 % (lv.n, why, lv.moves, dt, lv.boosters or "-"))
        self.out.append("levels.jsonl", json.dumps({
            "n": lv.n, "result": lv.result, "moves": lv.moves, "sec": round(dt),
            "boosters": lv.boosters, "undos": lv.undos, "stuck": lv.stuck, "badge": lv.badge,
            "fails": self.level_fails.get(lv.n, 0),
            "start": compact_state(lv.start_state)}, ensure_ascii=False) + "\n")
        self.write_state()                     # عدد المراحل في state.txt يتبع كل فوز فوراً

    def new_level(self, fr, st, n=None):
        # الرقم: العنوان المقروء أولاً (يُقرأ في الصعبة والصعبة جداً أيضاً)، ثم الرقم المعطى (إعادة المرحلة نفسها)، ثم زرّ
        # الواجهة، ثم رقم المرحلة المُعادة بعد «Give Up»، وآخر شيء العدّاد. (التشغيل السابع: العنوان الأحمر لم يُقرأ فصار
        # كل «Give Up» في المرحلة 99 «فوزاً» وانجرف العدّاد إلى 30..69 والشاشة تقول 99.)
        ln = self.vis.level_number(fr)
        if ln is not None and n is not None and ln != n:
            self.log("العنوان يعرض المرحلة %d لا %d: يُعتمد العنوان" % (ln, n))
        n = ln or n or self.level_hint or self.restart_n or (self.levels_done + 1)
        self.level_hint = None
        self.restart_n = None
        self.lv = LevelCtx(n, st, time.time())
        self.lv.badge = self.vis.badge(fr)
        self.lv.memory = self.memory_by_sig.setdefault(self.lv.start_sig, {})
        rec = self.sig_rec(self.lv.sig_id, n)
        if not self.lv.memory and rec.get("mem"):
            for k, p, c in rec["mem"]:
                self.lv.memory[(k, p)] = c
        self.sig_mem[self.lv.sig_id] = self.lv.memory
        self.lv.sig_attempt = rec["fails"]
        self.expect_new = False
        if n not in self.saved_starts:
            self.saved_starts.add(n)
            self.out.save_jpg("L%03d_start.jpg" % n, fr.pil)
        if self.close_frame is not None and time.time() - self.close_frame.t < 30:
            self.out.save_jpg("feat_L%03d.jpg" % n, self.close_frame.pil)
            self.log("نافذة قبل المرحلة %d (ميزة جديدة؟): feat_L%03d.jpg" % (n, n))
        self.close_frame = None
        nb = sum(1 for t in st["tubes"] if t.get("blocked"))
        self.log("بداية المرحلة %d%s: %d قارورة، سعات %s، مخفي %d%s"
                 % (n, {"hard": " (صعبة)", "superhard": " (صعبة جداً)"}.get(self.lv.badge, ""), len(st["tubes"]),
                    sorted(Counter(t["cap"] for t in st["tubes"] if not t.get("blocked")).items()),
                    sum(1 for t in st["tubes"] for c in t["layers"] if c == "?"),
                    "، مغطّاة %d (%s)" % (nb, cover_summary(st)) if nb else ""))
        remember_tags(st, self.lv.tags)
        if self.lv.tags:
            self.log("وسوم المرحلة %d («Tag!»: لا يُصبّ في القارورة إلا لون بطاقتها): %s" % (n, tags_summary(st)))
        br = solver.plaster_breakers(st)
        if br:
            self.log("جبس المرحلة %d: %s" % (n, "؛ ".join(
                "القالب %d ينكسر بامتلاء %s" % (p, "، ".join("القارورة %d" % k for k in ks) if ks else "جار لم ينكشف بعد")
                for p, ks in sorted(br.items()))))
        self.log("حالة المرحلة %d: %s" % (n, json.dumps(compact_state(st), ensure_ascii=False)))
        if rec["fails"] or rec["doors"]:
            self.log("المرحلة %d: البداية نفسها للمرة %d (%s، %d حالة طريق مسدود، %d باب معروف، %d طبقة مخفية معروفة)"
                     % (n, rec["fails"] + 1, "المفاتيح أولاً" if rec["fails"] % 2 == 0 else "بلا «المفاتيح أولاً»",
                        len(rec["dead"]), len(rec["doors"]), len(self.lv.memory)))

    def plan_params(self, lv, stp):
        """وسائط solver.plan الخاصة بهذه البداية: keys_first بالتناوب (المحاولة الأولى «المفاتيح أولاً» كما كان)، وavoid = حالات
        هذه المحاولة + الطريق المسدود المحفوظ، وdoors من ذاكرة الأبواب بفهارس الحالة الآن، وبذرة وتنويع بعدد المحاولات الفاشلة."""
        rec = self.sig_data.get(lv.sig_id) or {}
        att = lv.sig_attempt
        dead = set(rec.get("dead") or ())
        if rec.get("dead_st"):
            # «?» في حالات الطريق المسدود صارت معروفة غالباً (طبقات الأبواب، وذاكرة البداية والمحاولة): الحلّال يراها ملوّنة
            know = self.hidden_knowledge(lv, rec)
            if know:
                for tc in rec["dead_st"]:
                    try:
                        dead.add(solver.state_key(fill_known(tc, know)))
                    except (TypeError, ValueError):
                        continue
        # حالة البداية والحالة الآن ليستا طريقاً مسدوداً أبداً (سجلّات قديمة قد تحوي البداية: التشغيل 17)
        dead.discard(lv.start_sig)
        try:
            dead.discard(solver.state_key(stp))
        except (KeyError, TypeError, ValueError):
            pass
        doors = known_doors(stp, rec["doors"]) if rec.get("doors") else []
        return {"keys_first": att % 2 == 0,
                "avoid": (lv.visited | dead) if dead else lv.visited,
                "doors": doors or None,
                "seed": None if att == 0 else (int(lv.sig_id.split(":")[1][:8], 16) + 7919 * att) & 0xFFFFFFFF,
                "vary": att}

    def hidden_knowledge(self, lv, rec):
        """ما يُعرف من الطبقات المخفية بالموضع [(س، ص، سعة، طبقة، لون)]: ذاكرة البداية (بخانات البداية)، وذاكرة المحاولة (بخانات
        اللوحة الآن؛ لا بعد الخلط: مواضعها تغيّرت)، وطبقات الأبواب المعروفة."""
        out = []

        def add(tubes, mem):
            for (k, p), c in mem.items():
                if 0 <= k < len(tubes) and c != "?":
                    t = tubes[k]
                    out.append((t["x"], t["y"], int(t["cap"]), p, c))
        try:
            add(lv.start_state["tubes"], self.memory_by_sig.get(lv.start_sig) or {})
            if "shuffle" not in lv.boosters:
                add(lv.last_state["tubes"], lv.memory or {})
            for d in rec.get("doors") or ():
                for r in d["tubes"]:
                    for p, c in enumerate(r["layers"]):
                        if c != "?":
                            out.append((r["x"], r["y"], int(r["cap"]), p, c))
        except (KeyError, TypeError, ValueError):
            pass
        return out

    def sig_rec(self, sid, n):
        """سجلّ البداية (يُنشأ إن لم يوجد)؛ لا تزيد البدايات على SIG_MAX (يُحذف الأقدم استعمالاً)."""
        rec = self.sig_data.get(sid)
        if rec is None:
            rec = self.sig_data[sid] = new_sig_rec(n)
            if n in self.legacy_fail_levels:
                # تحديث ساخن من كود بلا "sigs" والمرحلة خسرت قبله: محاولتها السابقة غير محفوظة، فلا يُعاد خطّها الحتمي (المرحلة
                # 124: البداية السماوية لُعبت ثلاث مرات بـ «المفاتيح أولاً» والبذرة نفسها حتى الانسداد نفسه)
                rec["fails"] = 1
                self.log("المرحلة %s: بداية بلا سجلّ بعد التحديث والمرحلة خسرت قبله (%d «Give Up»): تُعدّ محاولتها الثانية"
                         % (n, self.level_fails.get(n, 0)))
            while len(self.sig_data) > SIG_MAX:
                old = min(self.sig_data, key=lambda k: self.sig_data[k].get("t", 0.0))
                self.sig_data.pop(old, None)
                self.sig_mem.pop(old, None)
        rec["t"] = time.time()
        return rec

    def note_dead_end(self, lv):
        """«Give Up»: محاولة فاشلة أخرى لهذه البداية، وآخر الحالات قبل الانسداد طريق لا يُعاد إليه في محاولاتها التالية."""
        if lv.dead_noted:                      # مرة واحدة في المحاولة (النافذة قد تُقرأ مرتين)
            return
        lv.dead_noted = True
        rec = self.sig_rec(lv.sig_id, lv.n)
        rec["fails"] += 1
        dead = rec["dead"]
        dead_st = rec.setdefault("dead_st", [])
        seen = set(dead)
        added = 0
        # الذيل بعد آخر باب انفتح: حالة انفتاح الباب وما قبلها ممرّ إجباري للخط كله (المرحلة 124: الانسداد بعد 4 حركات من الباب
        # الثاني)، فمنعها يُسقط ذاكرة الأبواب من كل تخطيط قبله
        h = lv.history
        start = max(0, len(h) - DEAD_TAIL, lv.door_idx + 1 - lv.hist_base)
        cut = start > max(0, len(h) - DEAD_TAIL)
        # حالة البداية لا تُحفظ أبداً (منعها يقصّ في المحاولة التالية كل حركة أولى: التشغيل 17، المرحلة 154)، وما بعدها يُحفظ
        # ولو كانت المحاولة قصيرة: منعه يغيّر الافتتاح الخاسر، وplan_params وطريق الحلّال البديل وإعادة التخطيط بدون الذاكرة
        # (plan_level) لا تتركها تُفرغ الخطة
        never = {lv.start_sig}
        if lv.hist_base == 0 and h:
            never.update(h[0][:2])
        tail = [h[idx] for idx in range(start, len(h))]
        # الحركة الأخيرة لم تُقرأ لوحتها قبل النافذة (lv.pending): حالتها المتوقّعة هي الحالة العالقة الحقيقية، لا آخر لوحة مقروءة
        # (التشغيل 17، 04:18:21: «3 حالة جديدة» = البداية وحالتان، والحالة بعد (5، 3) لم تُقرأ)
        stuck = "آخر لوحة مقروءة"
        if lv.pending is not None and lv.pending[2] is not None:
            try:
                pk = solver.state_key(lv.pending[2])
                tail.append((pk, pk, compact_tubes(lv.pending[2])))
                stuck = "الحالة بعد الحركة الأخيرة %s (لم تُقرأ)" % (lv.pending[1],)
            except (KeyError, TypeError, ValueError):
                pass
        for entry in tail:
            new = False
            for sk in entry[:2]:
                if sk in never:
                    continue
                if sk not in seen:
                    seen.add(sk)
                    dead.append(sk)
                    added += 1
                    new = True
            if new and len(entry) > 2 and entry[2] is not None:
                dead_st.append(entry[2])
        del dead[:-SIG_DEAD_MAX]
        del dead_st[:-SIG_DEAD_MAX]
        self.log("المرحلة %d: طريق مسدود محفوظ لهذه البداية (%d حالة جديدة%s، الحالة العالقة: %s، %d محفوظة، محاولاتها الفاشلة %d، "
                 "أبواب معروفة %d)" % (lv.n, added, "، بعد آخر باب انفتح" if cut else "", stuck,
                                       len(dead), rec["fails"], len(rec["doors"])))

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
            # بداية المرحلة: القوارير تدخل الشاشة متتابعة؛ تُعتمد الحالة حين تثبت بين لقطتين بينهما ثانية (قراءة مبكرة ناقصة
            # كانت تبدو لغزاً بلا حلّ فيصرف البوت «قارورة إضافية» ثم يظنّ المرحلة أُعيدت)
            # (صفّ القوارير السفلي قد يدخل بعد العلوي بأكثر من ثانية: ثلاث قراءات متطابقة بينها 1.2 ثانية)
            sig = (len(st["tubes"]), solver.state_key(st))
            self.start_same = self.start_same + 1 if sig == self.start_probe else 0
            if self.start_same < 2 and self.start_probe_tries < 6:
                self.start_probe = sig
                self.start_probe_tries += 1
                time.sleep(1.2)
                return self.grab()
            self.start_probe, self.start_probe_tries, self.start_same = None, 0, 0
            self.new_level(fr, st)
            lv = self.lv
        elif self.door_ref(st) is not None:
            # باب انفتح (مفتاح طار إلى قفله) أو قارورة إضافية: قوارير جديدة والقديمة كما هي (بعد الحركة الأخيرة) —
            # استمرار للمحاولة نفسها لا «إعادة من البداية» (كانت تمحو الذاكرة والأدوات وعدّاد الحركات)
            if lv.door_wait < 1:
                lv.door_wait += 1                # حركة الباب والقوارير الداخلة: لقطة أخرى بعد قليل
                time.sleep(1.2)
                return self.grab()
            lv.door_wait = 0
            self.door_opened(st, *self.door_ref(st))
        elif not compatible(lv.last_state, st, lv.extra_tubes):
            # تغيّر كبير في اللوحة. الفوز الحقيقي يمرّ دائماً بنافذة الفوز أو زرّ الواجهة (on_button يؤكّده بالرقم)، فلا
            # «فوز» هنا إلا إن ظنّ البوت اللغز محلولاً؛ وإلا فهو باب انفتح (قوارير أكثر) أو إعادة المرحلة نفسها. (التشغيل
            # السابع: باب كبير انفتح فتغيّرت المواضع والعنوان الأحمر لم يُقرأ، فسُجّل «فوز» ومُحيت ذاكرة المحاولة.)
            lv.door_wait = 0
            lv.incompat += 1
            no, nn = len(lv.last_state["tubes"]), len(st["tubes"])
            # بلا مغادرة شاشة اللغز لا تُعاد المرحلة: قارورة اختفت = قراءة ناقصة غالباً، فلقطة ثالثة قبل الحكم
            need = 3 if (lv.active and nn <= no) else 2
            if lv.incompat < need:
                time.sleep(0.8)
                return self.grab()
            ln = self.vis.level_number(fr)       # رقم المرحلة من العنوان إن قُرئ
            if ln is not None and ln != lv.n:
                # المرحلة التالية مباشرة فوز حقيقي فاتت نافذته (maybe_won قد يكون خاطئاً بعد حركات «لا تقدّم»، وزرّ «Super Hard»
                # في الواجهة لا يُقرأ رقمه)؛ أما رقم أبعد أو أقل فتصحيح لانجراف العدّاد بلا فوز (30..69 في التشغيل السابع)
                if lv.maybe_won or ln == lv.n + 1:
                    self.win("لغز جديد على الشاشة: المرحلة %d" % ln, inferred=not lv.maybe_won)
                else:
                    self.log("العنوان يعرض المرحلة %d والعدّاد %d بلا نافذة فوز: يُعتمد العنوان بلا فوز" % (ln, lv.n))
                self.new_level(fr, st, n=ln)
            elif ln is None and lv.maybe_won:
                self.win("لغز جديد على الشاشة")
                self.new_level(fr, st)
            elif nn > no:
                self.door_remap(st)              # المرحلة نفسها وقوارير أكثر: باب أو غطاء انفتح، استمرار بلا إعادة
            else:
                self.log("المرحلة %d أُعيدت من البداية (%s، ذاكرة %d طبقة مكشوفة)"
                         % (lv.n, "العنوان نفسه" if ln is not None else "العنوان غير مقروء", len(lv.memory)))
                self.restart_n = lv.n            # بداية جديدة للمرحلة نفسها: تُعتمد حين تثبت اللوحة
                self.expect_new = True
                self.start_probe, self.start_probe_tries, self.start_same = None, 0, 0
                lv.incompat = 0
                time.sleep(0.6)
                return self.grab()
            lv = self.lv
        lv.incompat = 0
        lv.active = True
        if lv.tags and len(lv.last_state["tubes"]) != len(st["tubes"]):
            # عدد القوارير تغيّر بلا مسار الباب (فرع shifted أدناه): الوسوم بالموضع تُنقل بالمطابقة قبل أن تُطبَّق على غير قواريرها
            rebase_tags(lv.tags, lv.last_state, st, slot_map(lv.last_state, st))
        st, nfill = remember_tags(st, lv.tags)
        if nfill:
            lv.tag_fills += 1
            if lv.tag_fills <= 3:
                self.log("ذاكرة الوسوم: %d قارورة لم يُقرأ وسمها في هذه اللقطة فأُعيد إليها وسم خانتها" % nfill)
        key = solver.state_key(st)

        # ---- جبس انكسر (اكتملت جارته): القالب صار قارورة ظاهرة في خانته بالفهرس نفسه، استمرار للمحاولة نفسها
        broke = plaster_breaks(lv.last_state, st)

        # ---- التحقق من الحركة السابقة
        moved = lv.pending is not None
        verdict = None
        if lv.pending:
            prev, mv, expected, retries = lv.pending
            if len(st["tubes"]) != len(prev["tubes"]) and retries < 3:
                lv.pending = (prev, mv, expected, retries + 1)
                time.sleep(0.7)
                return self.grab()
            # طبقات القارورة التي ظهرت من الجبس جديدة: يُحكم على الحركة بلوحة تبقى فيها تلك الخانة جبساً كما كانت
            cur = mask_tubes(st, prev, set(broke)) if broke and len(st["tubes"]) == len(prev["tubes"]) else st
            verdict, revealed = compare(prev, expected, with_memory(cur, lv.memory))
            if verdict == "ok":
                for (k, p, c) in revealed:
                    lv.memory[(k, p)] = c
                rec = self.sig_data.get(lv.sig_id)
                # لا بعد الخلط: ما ينكشف في خانة قارورة باب ليس طبقتها المخفية الأصلية (ولا يُصحَّح أبداً)
                if (revealed and rec and rec["doors"] and "shuffle" not in lv.boosters
                        and learn_door_layers(rec["doors"], st, revealed)):
                    self.log("ذاكرة الأبواب: طبقة مخفية انكشفت في قارورة باب معروف (للمحاولات التالية)")
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
        blk_old = [bool(t.get("blocked")) for t in lv.last_state["tubes"]]
        blk_new = [bool(t.get("blocked")) for t in st["tubes"]]
        # غطاء انكشف في خانته (جبس انكسر، ستارة انزاحت، كيس انفجر) لا يغيّر الفهارس: تبقى الذاكرة نفسها (مشتركة مع
        # memory_by_sig فتبقى ما ينكشف بعده للمحاولة التالية بعد «Give Up»)
        same = {k for k, (a, b) in enumerate(zip(lv.last_state["tubes"], st["tubes"]))
                if a.get("blocked") and not b.get("blocked") and _near(a, b)}
        shifted = len(blk_old) != len(blk_new) or any(a != b and k not in same
                                                       for k, (a, b) in enumerate(zip(blk_old, blk_new)))
        if shifted and lv.memory:
            # عدد القوارير تغيّر بلا باب (قارورة لم تُقرأ في لقطة)، أو تبدّلت المغطّاة بغير انكشاف في خانتها (قالب لم يُقرأ وآخر
            # انكسر): الذاكرة بفهارس اللوحة الجديدة بالموضع، وإلا طُبّقت على غير قواريرها
            lv.memory = remap_memory(lv.memory, slot_map(lv.last_state, st), st)
        if any(t.get("blocked") and t.get("cover") == "plaster" for t in st["tubes"]):
            lv.plaster_seen = True
        if broke:
            lv.plasters_broken += len(broke)
            lv.plaster_expect, lv.plaster_waits = 0.0, 0      # الانكسار المنتظَر حدث (لا انتظار بعده لقالب آخر بلا كاسرة مكتملة)
            lv.plan = None                      # قارورة جديدة ظاهرة (ومعها كاسرات جديدة ربما): تخطيط من جديد
            left = sum(1 for t in st["tubes"] if t.get("blocked") and t.get("cover") == "plaster")
            self.log("الجبس انكسر في المرحلة %d: %s؛ باقٍ %d قالب، استمرار المحاولة نفسها بلا إعادة"
                     % (lv.n, "، ".join("القارورة %d (%d،%d) ← [%s]" % (k, st["tubes"][k]["x"], st["tubes"][k]["y"],
                                                                        ",".join(st["tubes"][k]["layers"])) for k in broke),
                        left))
        self.track_vanished(lv, st)
        lv.last_state = st
        stp = with_memory(st, lv.memory)
        lv.visited.add(key)
        lv.visited.add(solver.state_key(stp))
        entry = (key, solver.state_key(stp), compact_tubes(st))
        if not lv.history or lv.history[-1][:2] != entry[:2]:
            lv.history.append(entry)
            if len(lv.history) > 64:
                lv.hist_base += len(lv.history) - 64
                del lv.history[:-64]
        if lv.badge is None:
            lv.badge = self.vis.badge(fr)

        # ---- قارورة مرفوعة بقيت مختارة (بعد نقرة ضائعة): أنزِلها
        li = lifted_index(st) if (not moved or verdict == "nochange") else None
        if li is not None and lv.lift_fixes < 6:
            lv.lift_fixes += 1
            t = st["tubes"][li]
            self.log("القارورة %d مرفوعة؛ نقرة لإنزالها" % li)
            self.dev.tap_std(t["x"], t["y"])
            time.sleep(0.6)
            return self.grab()

        # ---- محلولة؟ ننتظر نافذة الفوز (أو انكشاف المغطّاة والأبواب: ترتيب الظاهر وحده ليس فوزاً). إلا جبساً قائماً تكتمل
        # جارته بخطة (طويلة أحادية غير مكتملة تُصبّ في كاسرة فارغة؛ المكتملة مسدودة): يُخطَّط له بدل الانتظار
        solved = solver.is_solved(stp)
        if solved and any(t.get("blocked") and t.get("cover") == "plaster" for t in st["tubes"]):
            pinfo = {}
            if solver.plan(stp, time_limit=0.5, max_nodes=10000, info=pinfo) and pinfo.get("mode") == "plaster":
                solved = False
                lv.solved_since = None
        if solved:
            lv.maybe_won = not covered(st)
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
            self.plan_level(lv, stp, key)
        if not lv.plan:
            return self.stuck(fr, st, "لا خطة")
        i, j = lv.plan.pop(0)
        return self.do_move(stp, i, j)

    def plan_level(self, lv, stp, key):
        """خطة الحالة `stp` (مفتاحها key) في lv.plan، بوسائط بدايتها (plan_params). ذاكرة الطريق المسدود لا تُبقي البوت بلا خطة
        وفي اللوحة حركات (التشغيل 17، المرحلة 154): إن قصّت هي الخط المحسِّن (info["dead_blocked"]) فطريق بديل بعيداً عنها أولاً
        (detour)، ثم تخطيط من جديد بدونها؛ وفي غير ذلك تبقى الخطة الفارغة لـ stuck() وأدواتها كما في المحاولة الأولى."""
        info = {}
        # الصعبة جداً: ثلاثة أضعاف الوقت والعقد (البوت ينتظر الأرواح أكثر مما يفكّر، والمرحلة 99 تنسدّ في آخر كل محاولة)،
        # وكل «Give Up» في المرحلة نفسها يزيده (plan_boost)
        fails = self.level_fails.get(lv.n, 0)
        boost = plan_boost(lv.badge, fails)
        # الاستراتيجية بعدد محاولات هذه البداية الفاشلة (لا المرحلة كلها): «المفاتيح أولاً» وبدونه بالتناوب، وبذرة وكسر تعادل
        # آخران في كل محاولة، وحالات الطريق المسدود السابق ممنوعة؛ والمحاولة الأولى لكل بداية كما كانت (المرحلة 124: البداية
        # نفسها لُعبت ثلاث مرات بالخط نفسه وانسدّت في الموضع نفسه)
        pp = self.plan_params(lv, stp)
        doors = pp["doors"]
        # حالات الطريق المسدود المحفوظة وحدها (لا حالات هذه المحاولة): الحلّال يلجأ إلى الطريق البديل فقط إن قصّت هي الخط المحسِّن
        dead = (pp["avoid"] - lv.visited) if pp["avoid"] is not lv.visited else set()
        lv.plan = solver.plan(stp, bad_moves=lv.bad_for(key), time_limit=CFG["plan_sec"] * boost,
                              max_nodes=int(40000 * boost), info=info, detour=dead or False, **pp)
        if info.get("mode") == "progress-detour" and lv.plan:
            self.log("المرحلة %d: لا خطة تتجنّب الطريق المسدود المحفوظ بالبحوث المعتادة؛ طريق بديل بعيداً عنه (%d حركة)"
                     % (lv.n, len(lv.plan)))
        if not hasattr(lv, "dead_replans"):
            lv.dead_replans = set()
        if not lv.plan and info.get("dead_blocked") and key not in lv.dead_replans:
            # الطريق المسدود المحفوظ قصّ كل خط محسِّن ولا طريق بديل: تخطيط من جديد بحالات هذه المحاولة وحدها (مرة لكل حالة؛ وإن
            # لم يُعثر على شيء فلا يُعاد في دورات stuck التالية)
            pp = dict(pp, avoid=lv.visited)
            info = {}
            lv.plan = solver.plan(stp, bad_moves=lv.bad_for(key), time_limit=CFG["plan_sec"] * boost,
                                  max_nodes=int(40000 * boost), info=info, **pp)
            if not lv.plan:
                lv.dead_replans.add(key)
            self.log("المرحلة %d: الخطة بذاكرة الطريق المسدود فارغة (قصّت كل خط محسِّن)؛ تخطيط من جديد بدونها (%d حالة مسدودة "
                     "مُهملة): %d حركة (%s)" % (lv.n, len(dead), len(lv.plan), info.get("mode")))
        lv.plan_key = key
        if lv.moves == 0 or not lv.plan or info.get("mode") not in ("pimc",):
            self.log("خطة المرحلة %d: %d حركة (%s، %s ms)%s%s"
                     % (lv.n, len(lv.plan), info.get("mode"), info.get("ms"),
                        "، أبواب معروفة %d (%s)" % (len(doors), {
                            "doors-full": "حل كامل", "hidden": "معرفة ناقصة: المنطق المعتاد",
                            "none": "بحث الأبواب بلا حل: المنطق المعتاد"}.get(info.get("doors_res"), "-"))
                        if doors else "",
                        "" if lv.plan else " — لا حركة مفيدة"))

    @staticmethod
    def track_vanished(lv, st):
        """مفاتيح اختفت من قواريرها بين اللوحة السابقة وهذه (العدد نفسه والخانة نفسها) وقاعدتها متحقّقة: طارت إلى أقفالها، وقد
        تُعتمد لقطة قبل انفتاح الباب فتصير الحالة المرجعية بلا المفتاح (door_record يستعملها حينئذ). ومفتاح عاد للقراءة يُحذف."""
        old = lv.last_state["tubes"]
        if len(old) != len(st["tubes"]):
            return
        for a, t in enumerate(old):
            b = st["tubes"][a]
            if not _near(t, b):
                continue
            for p in t.get("keys") or ():
                try:
                    kk = [int(round(t["x"])), int(round(t["y"])), int(p)]
                except (TypeError, ValueError):
                    continue
                if p not in (b.get("keys") or ()) and _released(b.get("layers") or [], int(p)):
                    if kk not in lv.vanished:
                        lv.vanished.append(kk)
            for p in b.get("keys") or ():
                kk = [int(round(b["x"])), int(round(b["y"])), int(p)]
                lv.vanished = [v for v in lv.vanished if not _key_near(v, kk)]

    def door_ref(self, st):
        """(الحالة المرجعية، المطابقة) إن كانت `st` هي الحالة السابقة (أو المتوقَّعة بعد الحركة المعلّقة) وقد ظهرت
        بينها قوارير جديدة؛ وإلا None."""
        lv = self.lv
        if lv is None or len(st["tubes"]) <= len(lv.last_state["tubes"]):
            return None
        refs = []
        if lv.pending is not None and lv.pending[2] is not None:
            refs.append(with_memory(lv.pending[2], lv.memory))
        refs.append(with_memory(lv.last_state, lv.memory))
        for ref in refs:
            mp = door_map(ref, st)
            if mp is not None:
                return ref, mp
        return None

    def door_opened(self, st, ref, mp, record=True):
        """باب انفتح أثناء المحاولة: تُنقل ذاكرة الطبقات المكشوفة إلى الفهارس الجديدة (القوارير الجديدة تُدرج بين
        القديمة)، وتبقى المحاولة (الحركات والأدوات والوقت) بلا «إعادة من البداية»."""
        lv = self.lv
        old_n = len(ref["tubes"])
        mem = remap_memory(lv.memory, mp, st)
        if lv.tags:
            rebase_tags(lv.tags, ref, st, mp)  # الوسوم بالموضع تتبع قواريرها (القارورة الإضافية تعيد ترتيب الصفّ)
        lv.memory = mem                        # قاموس جديد: ذاكرة بداية المرحلة (بفهارسها القديمة) تبقى لإعادتها
        lv.doors_opened += 1
        if lv.pending is not None:             # الحركة التي حرّرت المفتاح نجحت
            lv.moves += 1
            lv.fails = 0
            lv.pending = None
        lv.plan = None
        lv.ban.clear()                         # حركات بفهارس قديمة
        lv.bad.clear()
        lv.last_state = st
        nk = sum(len(t.get("keys") or ()) for t in st["tubes"])
        door_note = self.remember_door(ref, st, mp, record)
        lv.vanished = []
        lv.door_idx = lv.hist_base + len(lv.history)      # الحالة التالية في history هي ما بعد الباب
        # جبس انكسر وقالبه لم يُقرأ قبل ذلك (قارورة جديدة بين القديمة)، أو انكسر في خانته مع تغيّر آخر في اللوحة
        broke = [mp[k] for k, t in enumerate(ref["tubes"]) if k in mp and t.get("blocked") and t.get("cover") == "plaster"
                 and not st["tubes"][mp[k]].get("blocked")]
        newk = [k for k in range(len(st["tubes"])) if k not in set(mp.values())]
        # المغطّاة التي عادت إلى القراءة ليست انكساراً، ولا القارورة الفارغة (أداة «قارورة إضافية» أو «Play On»)
        newk_open = [k for k in newk if not st["tubes"][k].get("blocked") and st["tubes"][k]["layers"]]
        # والقارورة الجديدة جبس لم يُقرأ قالبه فقط بلا مفتاح ولا باب في اللوحة السابقة (وإلا فهي خلف باب ولو في المرحلة قوالب)،
        # و«بجوار مكتملة» في مراحل الجبس وحدها (قالب قُرئ فيها، أو من المرحلة 100): قارورة فاتت قراءتها ثم عادت ليست جبساً
        doorish = bool(ref.get("doors")) or any(t.get("keys") for t in ref["tubes"])
        missed = newk_open if newk_open and not doorish and (
            any(t.get("cover") == "plaster" for t in ref["tubes"]) or time.time() - lv.plaster_expect < 30
            or ((lv.plaster_seen or lv.n >= 100) and self.beside_complete(ref, st, newk_open))) else []
        if broke or missed:
            lv.plasters_broken += len(broke) + len(missed)
            lv.plaster_expect, lv.plaster_waits = 0.0, 0      # الانكسار المنتظَر حدث
            self.log("الجبس انكسر في المرحلة %d (%s): %d → %d قارورة، ذاكرة %d طبقة؛ استمرار بلا إعادة"
                     % (lv.n, "، ".join(["القارورة %d في خانة قالب" % k for k in broke]
                                        + ["القارورة %d جديدة (قالب لم يُقرأ؟)" % k for k in missed]
                                        + ["القارورة %d جديدة (باب انفتح؟)" % k for k in newk_open if k not in missed]),
                        old_n, len(st["tubes"]), len(mem)))
        elif newk and not newk_open and any(st["tubes"][k].get("blocked") for k in newk):
            self.log("المرحلة %d: قارورة مغطّاة عادت إلى القراءة (%s، %d → %d قارورة)؛ استمرار بلا إعادة"
                     % (lv.n, cover_summary({"tubes": [st["tubes"][k] for k in newk]}), old_n, len(st["tubes"])))
        else:
            self.log("المرحلة %d: قوارير جديدة (باب انفتح؟ %d → %d قارورة، ذاكرة %d طبقة، مفاتيح باقية %d)؛ استمرار بلا إعادة%s"
                     % (lv.n, old_n, len(st["tubes"]), len(mem), nk, door_note))
        self.log("حالة المرحلة %d بعد الباب: %s" % (lv.n, json.dumps(compact_state(st), ensure_ascii=False)))

    def remember_door(self, ref, st, mp, record=True) -> str:
        """ذاكرة الأبواب لهذه البداية: المفتاح الذي تحرّر (بموضع قارورته وطبقته) -> القوارير الجديدة كما قُرئت أول مرة؛ وطبقات
        مخفية فيها عُرفت في محاولة سابقة تدخل ذاكرة هذه المحاولة. يعيد ملاحظة للسجل."""
        lv = self.lv
        rec = self.sig_data.get(lv.sig_id)
        if rec is None:
            return ""
        if "shuffle" in lv.boosters:
            return "، ذاكرة الأبواب متوقفة في هذه المحاولة (بعد الخلط)"
        note = ""
        try:
            newk = [k for k in range(len(st["tubes"])) if k not in set(mp.values())]
            got = door_record(ref, st, mp, lv.vanished) if record else None
            if not record:
                note = "، ذاكرة الأبواب: لا يُسجَّل الباب (مطابقة تقريبية)"
            elif got:
                keys, tubes = got
                how = merge_door(rec["doors"], keys, tubes)
                note = "، ذاكرة الأبواب: المفتاح %s ← %d قارورة (%s)" % (
                    "، ".join("(%d،%d طبقة %d)" % tuple(k) for k in keys), len(tubes),
                    {"new": "جديد", "known": "معروف", "replaced": "صحّح سجلاً قديماً", "full": "الذاكرة ممتلئة"}[how])
            elif any(st["tubes"][k]["layers"] and not st["tubes"][k].get("blocked") for k in newk) and (
                    ref.get("doors") or any(t.get("keys") for t in ref["tubes"])):
                note = "، تعذّر نسب الباب إلى مفتاح (لا مفتاح محرَّر في اللوحة السابقة): لم يُسجَّل"
            filled = fill_from_doors(rec["doors"], st, newk, lv.memory)
            if filled:
                note += "، %d طبقة مخفية معروفة من محاولة سابقة" % filled
        except (KeyError, TypeError, ValueError, IndexError) as e:
            note = "، تعذّرت ذاكرة الأبواب: %r" % (e,)
        return note

    @staticmethod
    def beside_complete(ref, st, newk) -> bool:
        """قارورة جديدة بجوار قارورة مكتملة في صفّها (قالب جبس لم تقرأه الرؤية انكسر)، حين لا مفاتيح ولا أبواب في اللوحة السابقة."""
        if ref.get("doors") or any(t.get("keys") for t in ref["tubes"]):
            return False
        try:
            probe = {"tubes": [dict(t, blocked=True, cover="plaster", layers=[]) if k in newk else t
                               for k, t in enumerate(st["tubes"])]}
            adj = solver.plaster_breakers(probe)
        except Exception:                               # noqa: BLE001
            return False
        return any(full_tube(st["tubes"][j]) for k in newk for j in adj.get(k, []))

    def door_remap(self, st):
        """قوارير أكثر في المرحلة نفسها ولم تطابق door_map (باب كبير وغطاء معاً، صبّ أثناء الانفتاح، مواضع تغيّرت): استمرار
        المحاولة نفسها (الحركات والأدوات والوقت)، وتُنقل ذاكرة الطبقات المكشوفة بمطابقة تقريبية بالمحتوى والخانة."""
        lv = self.lv
        ref = lv.pending[2] if (lv.pending is not None and lv.pending[2] is not None) else lv.last_state
        mp = slot_map(with_memory(ref, lv.memory), st)
        if lv.pending is not None and lv.pending[2] is not None and len(mp) < len(ref["tubes"]):
            mp2 = slot_map(with_memory(lv.last_state, lv.memory), st)
            if len(mp2) > len(mp):
                ref, mp = lv.last_state, mp2
        self.log("المرحلة %d: لوحة أكبر لا تطابق ما قبلها تماماً (طوبقت %d من %d قارورة بالمحتوى والخانة)"
                 % (lv.n, len(mp), len(ref["tubes"])))
        self.door_opened(st, ref, mp, record=False)    # المطابقة تقريبية: لا يُسجَّل في ذاكرة الأبواب

    def do_move(self, st, i, j):
        lv = self.lv
        lv.dead_restarts = 0
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
            if solver.is_solved(expected) and not covered(expected):
                lv.maybe_won = True
        wait = CFG["pour_wait"]
        try:
            if solver.key_freed(st, i, j):
                wait += CFG["key_wait"]        # المفتاح يطير إلى قفله ثم ينفتح الباب: لا تُقرأ اللوحة أثناء ذلك
                self.log("الحركة %s تحرّر مفتاحاً؛ انتظار الباب" % ((i, j),))
            elif solver.breaker_completed(st, i, j):
                wait += CFG["plaster_wait"]    # تمتلئ الجارة ثم ينكسر الجبس بعد ثوانٍ: لا تُقرأ اللوحة أثناء ذلك
                lv.plaster_expect = time.time()
                lv.plaster_waits = 0
                self.log("الحركة %s تكمل جارة الجبس؛ انتظار انكساره" % ((i, j),))
        except Exception:
            pass
        time.sleep(wait)
        return self.grab()

    def save_stuck(self, fr, tag):
        lv = self.lv
        if lv and lv.stuck_shots < 3 and self.stuck_total < 150:
            lv.stuck_shots += 1
            self.stuck_total += 1
            self.out.save_jpg("stuck_L%03d_%d_%s.jpg" % (lv.n, lv.stuck_shots, tag), fr.pil)

    def plaster_pending(self, st) -> bool:
        """قالب جبس قائم يُنتظر انكساره: حركة أكملت جارته منذ أقل من plaster_grace ثانية، أو له كاسرة مكتملة الآن."""
        lv = self.lv
        if lv is None or not any(t.get("blocked") and t.get("cover") == "plaster" for t in st["tubes"]):
            return False
        if time.time() - lv.plaster_expect < CFG["plaster_grace"]:
            return True
        try:
            br = solver.plaster_breakers(st)
        except Exception:                               # noqa: BLE001
            return False
        return any(full_tube(st["tubes"][k]) for ks in br.values() for k in ks)

    def stuck(self, fr, st, why):
        lv = self.lv
        # جبس قائم اكتملت جارته منذ قليل أو جارته مكتملة الآن: ينكسر وحده بعد ثوانٍ (3..7 في التشغيل التاسع) فتظهر قارورته، فلا أداة
        # ولا حركة عشوائية ولا «إعادة» قبله بل إعادة تصوير بعدّاد محدود (الأساس كان ينجو صدفةً بإعادة تصوير «الأعداد غير المنطقية»)
        if lv.plaster_waits < 6 and self.plaster_pending(st):
            lv.plaster_waits += 1
            lv.fails = 0
            lv.plan = None
            self.log("المرحلة %d بلا حركة (%s) وجارة الجبس مكتملة ولم ينكسر بعد: انتظار وإعادة التصوير بلا أدوات (%d)"
                     % (lv.n, why, lv.plaster_waits))
            time.sleep(1.0)
            return self.grab()
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
        # أداة بلا شارة عدد حمراء نفدت ويظهر مكانها ثمنها بالعملات (القارورة 900): لا تُشترى
        free = self.vis._safe("booster_free", fr.arr)
        skip = set()
        if isinstance(free, list) and len(free) >= 2:
            skip = {name for name, k in (("undo", 0), ("shuffle", len(free) // 2), ("add", len(free) - 1)) if not free[k]}
            if skip:
                self.log("أدوات نفدت (ثمنها بالعملات، لا تُشترى): %s" % ", ".join(sorted(skip)))
        reset = False
        if "add" not in lv.boosters and "add" not in skip:
            lv.boosters.append("add")
            self.log("أداة: قارورة إضافية")
            self.tap(bp["add"])
            lv.extra_tubes += 1
            time.sleep(2.0)
            reset = True
        elif "shuffle" not in lv.boosters and "shuffle" not in skip:
            lv.boosters.append("shuffle")
            # الخلط يغيّر مواضع الطبقات: ذاكرة جديدة لهذه المحاولة (ذاكرة البداية المحفوظة تبقى صحيحة لبدايتها ولا يدخلها ما
            # ينكشف بعد الخلط)
            lv.memory = {}
            tgt = self.shuffle_target(st)
            self.log("أداة: خلط ثم اختيار القارورة %s" % (tgt,))
            self.tap(bp["shuffle"])
            time.sleep(1.3)
            if tgt is not None:
                t = st["tubes"][tgt]
                self.dev.tap_std(t["x"], t["y"])
            time.sleep(2.5)
            reset = True
        elif lv.undos < 6 and "undo" not in skip:
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
        # الحركة العشوائية لا تعود إلى الطريق المسدود المحفوظ لهذه البداية ما وُجدت غيرها (التشغيل 17، المرحلة 154: (5، 3)
        # العشوائية نفسها أنهت أكثر من محاولة)
        try:
            pp = self.plan_params(lv, st)
            dead = (pp["avoid"] - lv.visited) if pp["avoid"] is not lv.visited else set()
        except (KeyError, TypeError, ValueError, AttributeError):
            dead = set()
        fresh, alive = [], []
        for m in moves:
            nxt = solver.apply_move(st, *m)
            if nxt is None:
                continue
            k = solver.state_key(nxt)
            if k in dead:
                continue
            alive.append(m)
            if k not in lv.visited:
                fresh.append(m)
        pool = fresh or alive or moves
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
        """آخر حل: زرّ الرجوع (قد يفتح نافذة الخروج؛ تعالجها الحلقة). Magic Sort قد يتجاهل الرجوع داخل المرحلة (التشغيل
        السابع: 40 دقيقة في المرحلة 99 تتكرّر فيها «لا حركة قانونية» كل 8 ثوانٍ)، فبعد 4 محاولات بلا حركة بينها تُعاد اللعبة
        نفسها (force-stop ثم تشغيل)، فتُفتح المرحلة نفسها من جديد."""
        lv = self.lv
        if lv is not None:
            lv.dead_restarts += 1
            if lv.dead_restarts >= 4:
                self.log("الرجوع لم يُعِد المرحلة %d (%d محاولات)؛ إعادة تشغيل اللعبة" % (lv.n, lv.dead_restarts))
                lv.dead_restarts = 0
                lv.plan = None
                lv.pending = None
                self.dev.force_stop()
                time.sleep(2)
                self.dev.launch()
                time.sleep(25)
                return None
        self.dev.key(4)
        time.sleep(2)
        if lv is not None:
            lv.plan = None
            lv.pending = None
            lv.t0 = time.time()
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
        if self.lives_waiting():
            # الأرواح نفدت: لا يُضغط «Level N» ولا «Try Again» حتى موعد الروح القادمة (فحص كل دقيقة على الأكثر)
            rem = self.lives_until - time.time()
            if time.time() - self.last_lives_log > 300:
                self.last_lives_log = time.time()
                self.log("انتظار الأرواح: باقي %.0f دقيقة قبل زرّ المرحلة" % (rem / 60))
            time.sleep(min(60.0, max(1.0, rem)))
            return None
        pt = self.vis.button(fr)
        if pt:
            self.tap(pt)
            time.sleep(2.0)
        else:
            time.sleep(1.0)
        return None

    def lives_waiting(self) -> bool:
        return time.time() < self.lives_until

    def on_lives(self, fr):
        """نافذة «More Lives» (الأرواح نفدت بعد إخفاقات متكرّرة): إن كفى الرصيد ثمن «Refill» (900) يُضغط مرة واحدة، وإلا
        تُغلق بزرّ X ولا يُضغط زرّ المرحلة حتى موعد الروح القادمة (عدّاد النافذة، أو 5 دقائق إن لم يُقرأ). لا يُلمس أبداً
        «+1 Life» (إعلان) ولا «Free Lives». (التشغيل السابع: أُغلقت كأي نافذة X فبقي البوت ينتظر نحو ربع ساعة لكل روح.)"""
        self.unknown_streak = 0
        self.leave_level("lives")
        self.close_frame = None
        lp = self.vis.lives_popup(fr)
        if lp is None:
            return self.on_close(fr)
        now = time.time()
        coins = self.vis.coins(fr)
        if coins is not None:
            self.coins = coins
        price = max(lp["price"] or 0, CFG["refill_price"])   # قراءة أقل من الثمن المعروف مقطوعة (90 بدل 900)
        if self.lives_shots < 6:
            self.lives_shots += 1
            self.out.save_jpg("lives_%02d.jpg" % self.lives_shots, fr.pil)
        if coins is not None and coins >= price and now - self.last_refill_tap > 90:
            self.last_refill_tap = now
            self.refills += 1
            self.lives_until = 0.0
            self.log("نافذة «More Lives»: ملء الأرواح بـ %d عملة (الرصيد %d، المرة %d)" % (price, coins, self.refills))
            self.tap(lp["refill"])
            time.sleep(3.0)
            return None
        if coins is None:
            why = "الرصيد غير مقروء"
        elif coins < price:
            why = "الرصيد %d أقل من %d" % (coins, price)
        else:
            why = "الملء قبل قليل لم يُغلقها"
        wait = (lp["timer"] + 10) if lp["timer"] is not None else CFG["lives_wait_sec"]
        wait = max(60.0, min(16 * 60.0, wait))
        self.lives_until = now + wait
        self.last_lives_log = now
        self.log("نافذة «More Lives» (%s): إغلاق بـ X وانتظار %.1f دقيقة للروح القادمة (لا إعلان ولا «Free Lives»)"
                 % (why, wait / 60))
        self.tap(lp["close"])
        time.sleep(2.0)
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

    def recover_device(self) -> bool:
        """حارس المحاكي، على عدد اللقطات الفاشلة المتتالية (cap_fails؛ كل واحدة نحو 25 ثانية بانتظار wait-for-device): عند 3 يُعاد
        تشغيل خادم adb أولاً؛ وعند 4 ثم كل 4 يُعاد تشغيل المحاكي نفسه ثم اللعبة ما دامت سياسة التقدّم تسمح (emu_restart_policy:
        يُعاد ما دام البوت يفوز أو يلعب بين الأعطال، ويتوقف بعد emu_fruitless_max إعادات متتالية بلا تقدّم، أو عند حدّ الأمان
        emu_restarts، أو قرب نهاية الوقت)؛ وحين ترفض يتوقف البوت فينتهي التشغيل وتُنشر النتائج بدل الدوران ساعات. (التشغيل العاشر:
        مات المحاكي ولم يعد فبقي البوت يعيد المحاولة أكثر من ساعتين؛ والتشغيل 15: الحدّ الثابت 8 أوقف بوتاً يتقدّم وأمامه 110
        دقائق.) True إن فعل شيئاً يستحق إعادة التصوير فوراً."""
        n = self.cap_fails
        if n == 3:
            state = self.dev.adb_state()
            self.log("الجهاز لا يردّ (حالة adb: %s)؛ إعادة تشغيل خادم adb" % (state or "غائب"))
            self.dev.restart_adb()
            self.dev.run(["wait-for-device"], timeout=30)
            return True
        if n >= 4 and n % 4 == 0:
            now = time.time()
            won = self.levels_done - self.emu_restart_levels
            # دقائق اللعب من عودة المحاكي إلى آخر لقطة ناجحة: لا يدخل فيها زمن العطل الحالي (اللقطات الفاشلة، وإعادة adb،
            # ومحاولة نسخة على محاكٍ ميت)، وإعادة لم تتبعها لقطة ناجحة تعطي صفراً
            since = max(0.0, self.last_ok_grab - self.emu_restart_at) / 60.0
            left = (self.deadline - now) / 60.0
            allow, self.emu_fruitless, why = emu_restart_policy(self.emu_restarts, self.emu_fruitless, won, since, left)
            if allow:
                self.emu_restarts += 1
                self.log("المحاكي لا يردّ: إعادة تشغيله رقم %d (%s)" % (self.emu_restarts, why))
                self.log_host_oom()
                # مهلة الإعادة: ما بقي من التشغيل ناقص دقيقة، فلا تتجاوز الإعادةُ deadline (المحاكي قد لا يُقلع، أو تغيب اللعبة)
                ok = self.restart_emulator(budget=self.deadline - time.time() - 60)
                self.emu_restart_at = time.time()
                self.emu_restart_levels = self.levels_done
                if ok:
                    self.cap_fails = 0
                return True
            self.log("المحاكي لا يردّ ولن يُعاد تشغيله: %s؛ إيقاف البوت لينتهي التشغيل وتُنشر النتائج (%d إعادة، %d مرحلة مكتملة)"
                     % (why, self.emu_restarts, self.levels_done))
            self.stop = True
            return True
        return False

    def log_host_oom(self):
        """تشخيص: هل قتل نظام المضيف عملية المحاكي لنفاد الذاكرة؟ (dmesg بـ sudo -n إن سُمح؛ أي خطأ يُهمل)."""
        try:
            p = subprocess.run(["sudo", "-n", "dmesg"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
            lines = [l for l in p.stdout.decode("utf-8", "replace").splitlines()
                     if re.search(r"oom|killed process|qemu", l, re.I)]
            if lines:
                self.log("سجلّ المضيف (dmesg): " + " | ".join(l.strip()[-160:] for l in lines[-3:]))
            else:
                self.log("سجلّ المضيف (dmesg): لا أثر لنفاد الذاكرة")
        except (subprocess.TimeoutExpired, OSError):
            pass

    def log_emu_diag(self, full=True):
        """تشخيص المحاكي في السجل (emulator_diagnostics): موجز عند كل إعادة (الموارد وحالة العملية وآخر 3 أسطر من سجلّه)، وكامل عند
        فشل الإقلاع (ومعه مجلّد AVD وآخر 15 سطراً، وآخر 200 سطر في out/emulator_log.txt). لا يرفع خطأ أبداً."""
        try:
            for line in emulator_diagnostics(full=full, tail=15 if full else 3):
                self.log("تشخيص المحاكي: " + line)
            if full:
                tl = tail_lines(EMU_LOG, 200, max_bytes=256 * 1024, width=400)
                if tl:
                    self.out.write("emulator_log.txt", "\n".join(tl) + "\n")
        except Exception as e:                          # noqa: BLE001
            self.log("تعذّر تشخيص المحاكي: %r" % e)

    def prepare_emulator(self) -> bool:
        """قبل كل تشغيل للمحاكي: يقتله، ويحصد زومبي المحاكي الذي شغّله البوت قبل تحديث ساخن (reap_emulator_zombies)، ثم يحذف أقفال
        AVD الباقية فقط إن لم تبقَ عملية محاكٍ حيّة (emulator_running ليست True؛ تُقتل مرة ثانية قبل الحكم). False إن بقيت عملية
        حيّة: لا تُحذف أقفالها، فلا يفتح محاكيان صور AVD نفسها."""
        running = None
        for attempt in range(2):
            kill_emulators()
            time.sleep(3 if attempt == 0 else 8)
            for pid, comm in reap_emulator_zombies():
                self.log("حُصد محاكٍ ميت (زومبي) من قبل التحديث الساخن: %s pid %d" % (comm, pid))
            running = emulator_running()
            if running is not True:
                break
            if attempt == 0:
                self.log("عملية المحاكي ما زالت حيّة بعد قتلها: قتلها مرة أخرى")
        if running is True:
            self.log("بقيت عملية محاكٍ حيّة بعد قتلها مرتين: لا تُحذف أقفال AVD (%s)" % emulator_proc_summary())
            return False
        locks = clear_avd_locks()
        if locks:
            self.log("حُذفت أقفال AVD باقية من المحاكي المقتول: %s" % "، ".join(locks))
        return True

    def boot_emulator(self, wait, wipe=False):
        """يجهّز الطريق (prepare_emulator) ويشغّل المحاكي (wipe: بمحو بياناته) وينتظر إقلاعه wait ثانية على الأكثر (wait_boot).
        True إن أقلع، False إن لم يُقلع، None إن لم يوجد الأمر emulator. self.boot_info: why (start: تعذّر تشغيله، exited: انتهت
        عمليته، timeout)، seen (ظهر في adb)، alive (حالة العملية عند نهاية المهلة)، stuck (بقيت عملية قديمة حيّة)، t0."""
        self.boot_info = info = {"why": "", "seen": False, "alive": None, "stuck": False, "t0": time.time()}
        info["stuck"] = not self.prepare_emulator()
        started = start_emulator(wipe=True) if wipe else start_emulator()
        if started is None:
            return None
        if not started:
            self.log("تعذّر تشغيل الأمر emulator (خطأ نظام)")
            info["why"] = "start"
            return False
        info["t0"] = time.time()
        self.dev.restart_adb()
        return self.wait_boot(info["t0"] + max(0.0, wait), wipe)

    def wait_boot(self, stop_at, wipe=False):
        """ينتظر sys.boot_completed حتى stop_at بالاستطلاع: wait-for-device بمهلة 20 ثانية حتى يظهر الجهاز (لا انتظار حاجب طويل
        لمحاكٍ خرج فوراً)، وفحص عملية المحاكي من t0 + 30 كل 20 ثانية (يكفّ إن انتهت). يحدّث self.boot_info."""
        d = self.dev
        info = self.boot_info
        t0 = info["t0"]
        next_check = max(time.time(), t0 + 30)
        while time.time() < stop_at:
            if not info["seen"]:
                rc, _ = d.run(["wait-for-device"], timeout=max(5, min(20, int(stop_at - time.time()))))
                info["seen"] = rc == 0
            if info["seen"] and d.sh("getprop sys.boot_completed", timeout=10) == "1":
                self.log("أقلع المحاكي%s بعد %.0f ثانية" % (" بعد محو بياناته" if wipe else "", time.time() - t0))
                return True
            if time.time() >= next_check:
                next_check = time.time() + 20
                if emulator_running() is False:
                    self.log("عملية المحاكي انتهت بعد %.0f ثانية من تشغيله دون إقلاع" % (time.time() - t0))
                    info["why"] = "exited"
                    return False
            time.sleep(2)
        info["why"] = "timeout"
        info["alive"] = emulator_running()
        return False

    def restart_emulator(self, budget=None) -> bool:
        """يقتل المحاكي العالق ويشغّله من جديد (boot_emulator)، وينتظر إقلاعه emu_boot_min دقيقة، ويعيد إعدادات الشاشة، ثم يشغّل
        اللعبة (وتثبّتها مع استعادة الحفظ إن غابت). True إن عاد الجهاز وشُغّلت اللعبة. budget: أقصى ثوانٍ للإعادة كلها
        (recover_device: ما بقي من التشغيل)؛ انتظار الإقلاع يُقصَّر بها، ولا يبدأ تثبيت اللعبة واستعادة حفظها إلا إن بقي منها
        emu_install_min دقيقة (لا تثبيت بلا استعادة: لعبة من المرحلة 1 تكتب نسختها فوق نسخة out/)، وتعيد False حين تنفد.
        إن لم يُقلع (التشغيل 16: ثلاث إعادات متتالية لم تُقلع) يُكتب التشخيص في السجل، ثم بالترتيب: محاكٍ حيّ ظاهر في adb يُمدَّد
        انتظاره emu_boot_extend_min دقيقة (بطيء لا معطوب)؛ وسجلّ يذكر محاكياً آخر بالـ AVD نفسه (قفل باقٍ أو زومبي بعد التحديث
        الساخن) يُعاد إقلاعه عادياً مرة بعد الحصد وحذف الأقفال (المحو لا يعالج القفل)؛ وإلا يُشغَّل مرة بمحو بياناته (-wipe-data) إن
        بقي emu_wipe_boot_min + emu_install_min دقيقة ولم تبقَ عملية قديمة حيّة: اللعبة تغيب فتُثبَّت وتُستعاد آخر نسخة احتياطية
        (يضيع تقدّم ما بعدها). إعادة بالمحو أعادت اللعبة إعادةٌ عادية (True)، وفشلها بلا ثمرة (False). محاكٍ أقلع وبقي بلا اللعبة
        (فشل التثبيت مرتين أو لا وقت له) يوقف البوت: لقطات سطح مكتب Android لا تُعدّ عطلاً فلا تعود recover_device."""
        d = self.dev
        end = time.time() + (budget if budget is not None else 1e9)

        def left():
            return end - time.time()
        if left() <= 0:
            self.log("لا وقت لإعادة تشغيل المحاكي قبل نهاية التشغيل")
            return False
        self.log("إعادة تشغيل المحاكي (المرة %d، حدّ الأمان %d)..." % (self.emu_restarts, CFG["emu_restarts"]))
        self.log_emu_diag(full=False)
        booted = self.boot_emulator(min(left(), CFG["emu_boot_min"] * 60))
        if booted is None:
            self.log("تعذّر تشغيل المحاكي: لم يُعثر على الأمر emulator")
            self.log_emu_diag(full=True)
            return False
        wiped = False
        if not booted:
            self.log("المحاكي لم يكمل إقلاعه بعد إعادة تشغيله%s" % ("" if left() > 0 else " (نفدت مهلة الإعادة: نهاية التشغيل قريبة)"))
            self.log_emu_diag(full=True)
            info = self.boot_info
            ext = min(CFG["emu_boot_extend_min"] * 60, left())
            if info["why"] == "timeout" and info["seen"] and info["alive"] is True and not info["stuck"] and ext >= 60:
                self.log("المحاكي حيّ وظاهر في adb لكنه لم يُكمل إقلاعه: تمديد الانتظار %.0f دقيقة بدل محو بياناته" % (ext / 60))
                booted = self.wait_boot(time.time() + ext)
                if not booted:
                    self.log("المحاكي لم يكمل إقلاعه حتى بعد التمديد")
            if not booted and emu_log_mentions_lock():
                self.log("سجلّ المحاكي يذكر محاكياً آخر بالـ AVD نفسه (قفل باقٍ أو زومبي بعد التحديث الساخن): حصد وحذف الأقفال ثم "
                         "إقلاع عادي ثانٍ بدل محو البيانات")
                booted = self.boot_emulator(min(left(), CFG["emu_boot_min"] * 60)) if left() > 60 else False
                if booted is None:
                    return False
                if not booted:
                    self.log("المحاكي لم يكمل إقلاعه في المحاولة العادية الثانية")
                    self.log_emu_diag(full=True)
                    if emu_log_mentions_lock():
                        self.log("ما زال المحاكي يرفض التشغيل لمحاكٍ آخر بالـ AVD نفسه: محو البيانات لا يعالج ذلك")
                        return False
        if not booted:
            if not CFG["emu_wipe"]:
                return False
            if self.boot_info.get("stuck"):
                self.log("عملية محاكٍ قديمة ما زالت حيّة: لا محو للبيانات (قد تفتح صور AVD نفسها)")
                return False
            need = (CFG["emu_wipe_boot_min"] + CFG["emu_install_min"]) * 60
            if left() < need:
                self.log("لا وقت لتشغيل المحاكي بمحو بياناته ثم تثبيت اللعبة واستعادة الحفظ (بقي %.1f دقيقة، يلزم %.0f)"
                         % (max(0.0, left()) / 60, need / 60))
                return False
            self.log("محاولة أخيرة: تشغيل المحاكي بمحو بياناته (-wipe-data) ثم تثبيت اللعبة واستعادة آخر نسخة احتياطية "
                     "(يضيع تقدّم ما بعد آخر نسخة)")
            # نافذة إقلاعه لا تأكل وقت التثبيت والاستعادة (ودقيقة هامشاً للإعدادات)
            wait = min(CFG["emu_wipe_boot_max"] * 60, left() - CFG["emu_install_min"] * 60 - 60)
            booted = self.boot_emulator(wait, wipe=True)
            if not booted:
                self.log("المحاكي لم يُقلع حتى بعد محو بياناته")
                self.log_emu_diag(full=True)
                return False
            wiped = True
        for c in ("settings put global window_animation_scale 0", "settings put global transition_animation_scale 0",
                  "settings put global animator_duration_scale 0",
                  "settings put secure immersive_mode_confirmations confirmed",
                  "settings put system screen_off_timeout 2147483647", "svc power stayon true", "input keyevent 82"):
            d.sh(c)
        d.raw_ok = True
        try:
            d.start_logcat("/tmp/bot_logcat.txt")
        except Exception:                               # noqa: BLE001
            pass
        restored = None
        if not d.installed():
            if left() < CFG["emu_install_min"] * 60:
                self.log("اللعبة غير مثبّتة بعد إعادة المحاكي، ولم يبقَ وقت لتثبيتها واستعادة الحفظ (%.1f دقيقة)" % (left() / 60))
                return self.stop_without_game()
            self.log("اللعبة غير مثبّتة بعد إعادة المحاكي%s: تثبيتها واستعادة الحفظ" % (" (مُحيت بياناته)" if wiped else ""))
            ok = self.install_game(until=end)
            if not ok and left() >= CFG["emu_install_min"] * 60:
                self.log("تعذّر تثبيت اللعبة بعد إعادة المحاكي: محاولة ثانية")
                ok = self.install_game(until=end)
            if not ok:
                self.log("تعذّر تثبيت اللعبة بعد إعادة المحاكي")
                return self.stop_without_game()
            restored = self.restore_after_install(end)
        if wiped and self.airplane_on:
            self.airplane(True)                         # المحو أعاد إعدادات الجهاز كلها
        d.launch()
        self.unknown_streak = 0
        if wiped:
            self.log("عاد المحاكي بعد محو بياناته: ثُبّتت اللعبة و%s؛ قد يضيع تقدّم ما بعد آخر نسخة احتياطية"
                     % ("استُعيدت آخر نسخة احتياطية" if restored else "لم تُستعد نسخة احتياطية (تبدأ من حيث تبدأ)"))
        self.log("عاد المحاكي وشُغّلت اللعبة من جديد")
        time.sleep(25)
        return True

    def stop_without_game(self) -> bool:
        """المحاكي أقلع واللعبة غير مثبّتة: يوقف البوت (لقطات سطح مكتب Android تنجح فلا تعود recover_device، وon_unknown يشغّل لعبة
        غائبة حتى نهاية الوقت). يعيد False (إعادة بلا ثمرة)."""
        self.log("المحاكي يعمل بلا اللعبة بعد إعادته: إيقاف البوت لينتهي التشغيل وتُنشر النتائج")
        self.stop = True
        return False

    def relaunch(self, why):
        """إيقاف اللعبة ثم تشغيلها (تُفتح المرحلة الجارية نفسها أو الواجهة)."""
        self.log(why)
        self.dev.force_stop()
        time.sleep(2)
        self.dev.launch()
        self.unknown_streak = 0
        time.sleep(25)
        return None

    def on_ad(self, fr, kind):
        """إعلان بملء الشاشة فرضته اللعبة (البوت لا يطلب إعلاناً أبداً: لا «+1 Life» ولا «Free Lives» ولا «Install»).
        الأسود (is_ad): رجوع ثم زاويتا الإغلاق كما كان. الأبيض التجريبي (AppLovin MAX، is_white_ad): زرّ X في زاوية علوية
        (find_ad_close: يظهر بعد العدّ التنازلي) يُلمس متى ظهر، وإلا رجوع بعد مهلة العدّ (ad_wait_sec)، كل 5 ثوانٍ على الأكثر؛
        لا يُلمس وسطه ولا «Install».
        إن بقي الإعلان أكثر من ad_max_sec (الأبيض) أو ad_black_max_sec (الأسود) تُعاد اللعبة. (التشغيل التاسع: الأبيض بقي حتى
        مهلة الثلاث دقائق بنقرات تصعيد في وسطه، وشاشة تعليم معتمة ظُنّت إعلاناً أسود فدام الرجوع 25 دقيقة.)"""
        now = time.time()
        if self.ad_last is None or now - self.ad_last > 20 or self.ad_kind != kind:
            self.ad_since, self.ad_acts, self.ad_kind = now, 0, kind
            if kind == "white":
                self.log("إعلان تجريبي أبيض (AppLovin): انتظار عدّه التنازلي ثم زرّ الإغلاق أو الرجوع (لا «Install» أبداً)")
        self.ad_last = now
        el = now - self.ad_since
        if el > (CFG["ad_max_sec"] if kind == "white" else CFG["ad_black_max_sec"]):
            self.ad_last = None
            return self.relaunch("الإعلان %s باقٍ منذ %.0f ثانية؛ إعادة تشغيل اللعبة"
                                 % ("التجريبي الأبيض" if kind == "white" else "الأسود", el))
        if kind == "white":
            # زرّ X في زاوية علوية يعني أن العدّ انتهى: يُلمس متى ظهر؛ والرجوع بعد مهلة العدّ فقط
            x = self.vis._pt(self.vis._safe("find_ad_close", fr.arr)) if el >= 2 else None
            if (x or el >= CFG["ad_wait_sec"]) and now - self.last_ad_act > 5:
                self.last_ad_act = now
                self.ad_acts += 1
                if x:
                    self.log("الإعلان التجريبي: زرّ الإغلاق X في الزاوية %s (%d)" % (x, self.ad_acts))
                    self.tap(x)
                else:
                    self.log("الإعلان التجريبي: رجوع (%d)" % self.ad_acts)
                    self.dev.key(4)
        elif now - self.last_ad_act > 5:
            # الأسود: الرجوع يغلقه عادة بعد عدّه التنازلي، وإلا زرّ الإغلاق الصغير في زاوية علوية
            self.last_ad_act = now
            self.ad_acts += 1
            k = self.ad_acts % 3
            if self.ad_acts == 1 or k == 1:
                self.log("إعلان بملء الشاشة: رجوع (%d)" % self.ad_acts)
                self.dev.key(4)
            else:
                self.tap((455, 18) if k == 2 else (18, 18))
        self.unknown_streak = 0
        time.sleep(1.5)
        return None

    def on_logo(self, fr):
        """شعار «MAGIC SORT» فوق لوحة معتمة (جزء من احتفال الفوز يزول عادة في ثوانٍ): لا لمس حتى logo_wait_sec، ثم رجوع مرة
        واحدة، ثم إعادة تشغيل اللعبة بعد logo_back_sec أخرى. (التشغيل التاسع: بقي مرتين حتى مهلة الثلاث دقائق، ومعها ثلاث لمسات
        «سهم تعليم» كاذبة على حروفه الصفراء.)"""
        now = time.time()
        if self.logo_last is None or now - self.logo_last > 20:
            self.logo_since, self.logo_backs = now, 0
            self.log("شعار «MAGIC SORT» فوق لوحة معتمة (بعد الفوز): انتظار حتى %.0f ثانية بلا لمس" % CFG["logo_wait_sec"])
        self.logo_last = now
        el = now - self.logo_since
        if el >= CFG["logo_wait_sec"] + CFG["logo_back_sec"]:
            self.logo_last = None
            return self.relaunch("الشعار باقٍ منذ %.0f ثانية رغم الرجوع؛ إعادة تشغيل اللعبة" % el)
        if el >= CFG["logo_wait_sec"] and self.logo_backs == 0:
            self.logo_backs = 1
            self.log("الشعار باقٍ منذ %.0f ثانية: رجوع مرة واحدة" % el)
            self.dev.key(4)
        self.unknown_streak = 0
        time.sleep(2)
        return None

    def on_no_moves(self, fr, gu):
        """نافذة «No Available Moves»: «Give Up» افتراضياً (تُعاد المرحلة وتضيع روح). «Play On» الأخضر (قارورة إضافية
        بـ 900 عملة) فقط إن كفى الرصيد المقروء ثمنه واحتياطي ملء الأرواح بعده (play_on_reserve)، وكانت المرحلة صعبة أو صعبة
        جداً بعنوانها أو أُخفقت مرتين على الأقل في هذا التشغيل؛ ومرة واحدة في المحاولة. لا يُشترى غير ذلك أبداً (أثمان شريط
        الأدوات تبقى كما هي)."""
        lv = self.lv
        n = lv.n if lv else None
        fails = self.level_fails.get(n, 0) if n is not None else 0
        badge = lv.badge if lv else None
        po = self.vis.play_on(fr)
        coins = self.vis.coins(fr)
        if coins is not None:
            self.coins = coins
        price = max((po[1] if po else 0) or 0, CFG["play_on_price"])   # قراءة الزرّ قد تُسقط صفراً (90 بدل 900)
        # احتياطي لملء الأرواح مرة: بلا هذا يصرف «Play On» الرصيد كله (1950 ← 1050 ← 150) قبل نفاد الأرواح، فلا يُستعمل
        # «Refill» أبداً ويعود انتظار ربع ساعة لكل روح. إلا في الصعبة جداً: التشغيل الثامن في المرحلة 99 ينتهي كل محاولة بعد
        # انفتاح الأبواب كلها بـ «No Available Moves»، فقارورة إضافية عندها أنفع من خمس محاولات أخرى تنتهي مثلها
        reserve = 0 if badge == "superhard" else max(0, CFG["play_on_reserve"])
        hard = badge in ("hard", "superhard")
        eligible = hard or fails >= CFG["play_on_fails"]
        if (po and lv is not None and coins is not None and coins >= price + reserve and lv.play_ons < 1
                and eligible):
            why = ("مرحلة %s" % {"hard": "صعبة", "superhard": "صعبة جداً"}[badge]) if hard \
                else ("أُخفقت %d مرات" % fails)
            self.log("نافذة «No Available Moves» في المرحلة %d: «Play On» (قارورة إضافية بـ %d عملة، الرصيد %d، %s)"
                     % (n, price, coins, why))
            self.out.save_jpg("playon_L%03d_%d.jpg" % (n, fails), fr.pil)
            lv.play_ons += 1
            lv.extra_tubes += 1
            lv.boosters.append("playon")
            lv.plan = None
            lv.pending = None
            lv.fails = 0
            self.tap(po[0])
            time.sleep(2.5)
            return None
        if not po:
            why = "زرّ «Play On» لم يُعرف"
        elif coins is None:
            why = "الرصيد غير مقروء"
        elif coins < price:
            why = "الرصيد %d أقل من %d" % (coins, price)
        elif lv is not None and lv.play_ons:
            why = "«Play On» استُعمل في هذه المحاولة"
        elif not eligible or lv is None:
            why = "مرحلة %s وإخفاقاتها %d" % ({"normal": "عادية"}.get(badge, "غير معروفة النوع"), fails)
        else:
            why = "الرصيد %d لا يُبقي بعد ثمنه %d احتياطي ملء الأرواح %d" % (coins, price, reserve)
        self.log("نافذة «No Available Moves»%s: «Give Up» (%s)" % (" في المرحلة %d" % n if n else "", why))
        if n is not None:
            self.level_fails[n] += 1
            self.restart_n = n                 # ستُفتح المرحلة نفسها من جديد
            if lv is not None and lv.n == n:
                self.note_dead_end(lv)
            if self.level_fails[n] <= 3:
                self.out.save_jpg("nomoves_L%03d_%d.jpg" % (n, self.level_fails[n]), fr.pil)
        else:
            self.out.save_jpg("nomoves_%03d.jpg" % min(999, self.levels_done), fr.pil)
        self.tap(gu)
        # اللعبة تعيد المرحلة دائماً بعد «Give Up» (ثم X في «Continue?»): محاولة جديدة تُعتمد حين تثبت اللوحة، حتى لو بدأت
        # بالألوان نفسها (بدايات المرحلة 99 تتكرّر فيقبلها compatible)، فلا يبقى «Play On» محسوباً ولا الحظر والذاكرة والوقت
        self.expect_new = True
        self.start_probe, self.start_probe_tries, self.start_same = None, 0, 0
        time.sleep(2.5)
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
        # إعلان بملء الشاشة فرضته اللعبة بعد مرحلة (لا يطلب البوت إعلاناً أبداً): الأسود بزرّ «Install»، أو التجريبي الأبيض
        # (AppLovin MAX). لا يُلمس «Install» ولا وسط الإعلان أبداً (on_ad)
        white = bool(self.vis._safe("is_white_ad", fr.arr, default=False))
        if white or self.vis._safe("is_ad", fr.arr, default=False):
            return self.on_ad(fr, "white" if white else "black")
        self.ad_acts = 0
        # «No Available Moves»: «Give Up» ثم تُعاد المرحلة، إلا ما تقرّره on_no_moves («Play On» بالعملات)
        gu = self.vis._pt(self.vis._safe("find_give_up", fr.arr))
        if gu:
            self.unknown_streak = 0
            return self.on_no_moves(fr, gu)
        # شعار «MAGIC SORT» فوق لوحة معتمة (احتفال الفوز): انتظار بلا لمس، لا «سهم» على حروفه الصفراء ولا مهلة الثلاث دقائق
        if self.vis._safe("is_logo_overlay", fr.arr, default=False):
            return self.on_logo(fr)
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
                self.fg_fails = getattr(self, "fg_fails", 0) + 1
                if self.fg_fails >= 3:
                    # الإطلاق وحده لم يُرجعها ثلاث مرات (إعلان تجريبي أبيض فتح المتجر وبقيت مهمّته فوق اللعبة): إيقاف ثم إطلاق
                    self.fg_fails = 0
                    self.log("اللعبة ليست في الواجهة للمرة الثالثة (%s)؛ إيقافها ثم تشغيلها" % f.replace("\n", " ")[:120])
                    self.dev.force_stop()
                    time.sleep(2)
                else:
                    self.log("اللعبة ليست في الواجهة (%s)؛ تشغيلها" % f.replace("\n", " ")[:120])
                self.dev.launch()
                self.unknown_streak = 0
                time.sleep(15)
                return None
            self.fg_fails = 0
            if "Not Responding" in f:
                self.log("نافذة «لا يستجيب»: انتظار")
                self.dev.key(4)
        if self.lives_waiting():
            # الأرواح نفدت: لا «Home» ولا موضع «Level N» ولا سهم ولا نقر ورجوع بالزمن حتى موعد الروح القادمة (الواجهة بزرّ
            # «Super Hard» الأحمر تُقرأ «unknown» فكان مسار شريط التبويبات يفتح نافذة More Lives كل 23 ثانية)؛ وبعده تُعامل
            # الشاشة كمجهولة جديدة (تصعيد بطيء من أوله). فحص التركيز والإعلانات والتحميل قبل هذا كما هي.
            rem = self.lives_until - now
            if now - self.last_lives_log > 300:
                self.last_lives_log = now
                self.log("انتظار الأرواح (شاشة مجهولة): باقي %.0f دقيقة بلا لمس" % (rem / 60))
            self.unknown_streak = 0
            time.sleep(min(60.0, max(1.0, rem)))
            return None
        # تعليم بسهم أصفر يشير إلى ما يجب لمسه (صورة اللاعب قبل «الفرق» مثلاً): يُلمس الهدف بعد ثانيتين من ثبات الشاشة
        # صفحة تبويب غير الرئيسية (الفرق، المتصدّرون، المجموعة، المتجر): شريط التبويبات مضيء بلا زرّ «Level N»؛
        # العودة بزرّ «Home» في وسط الشريط
        if self.unknown_streak == 1:
            self.arrow_taps = 0                # شاشة مجهولة جديدة: محاولات السهم من جديد
            self.tab_home_taps = 0
        if dur >= 3 and now - self.last_tab_home > 6 and self.vis._safe("tabbar_fraction", fr.arr, default=0.0) > 0.5:
            self.last_tab_home = now
            self.tab_home_taps += 1
            if self.tab_home_taps <= 2:
                self.log("صفحة تبويب: العودة إلى الرئيسية")
                self.tap((236, 955))
            else:
                # «Home» لم يغيّر شيئاً: هي الواجهة الرئيسية نفسها بمشهد حلقة لم يُعرف زرّه؛ يُلمس موضع «Level N» المعتاد
                self.tab_home_taps = 0
                self.log("واجهة رئيسية لم يُعرف زرّها: لمس موضع «Level N»")
                self.tap((236, 786))
            time.sleep(2)
            return None
        if dur >= 2 and now - self.last_arrow_tap > 4 and self.arrow_taps < 3:
            tgt = self.vis._pt(self.vis._safe("find_tutorial_arrow", fr.arr))
            if tgt and now - self.last_focus_check > 5:
                # «سهم» في شاشة سطح مكتب Android (التشغيلان السادس والسابع: ثلاث لمسات على أيقونات المتجر والمتصفح بعد خروج
                # اللعبة): لا يُلمس شيء خارج اللعبة، بل تُشغَّل
                self.last_focus_check = now
                f = self.dev.focus()
                if f and PKG not in f:
                    self.log("سهم مزعوم واللعبة ليست في الواجهة (%s): لا لمس، تشغيلها" % f.replace("\n", " ")[:120])
                    self.dev.launch()
                    self.unknown_streak = 0
                    time.sleep(15)
                    return None
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
            pt = TOS_POINT if self.elapsed_min() < 8 else (fr.arr.shape[1] // 2, int(STD_H * 0.62))
            if act == "tap" and self.vis.paid_at(fr, pt):
                self.log("نقرة التصعيد فوق زرّ يصرف العملات %s: رجوع بدلها" % (pt,))
                act = "back"
            if act == "tap":
                self.tap(pt)
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
    plans = {"level": 0, "parsed": 0, "planned": 0, "solved_sim": 0, "stuck": 0, "solved": 0, "covered": 0}
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
                caps = Counter(t_["cap"] for t_ in st["tubes"] if not t_.get("blocked"))
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
                nb = sum(1 for t_ in st["tubes"] if t_.get("blocked"))
                npl = sum(1 for t_ in st["tubes"] if t_.get("blocked") and t_.get("cover") == "plaster")
                if nb:
                    plans["covered"] += 1
                if npl:
                    plans["plaster"] = plans.get("plaster", 0) + 1
                line += " رقم=%s نوع=%s قوارير=%d سعات=%s مخفي=%d مغطّاة=%d جبس=%d تحذيرات=%d خطة=%d %s %.0fms%s" % (
                    vis.level_number(fr), vis.badge(fr), len(st["tubes"]), dict(caps), hid, nb, npl,
                    len(st["warnings"]), len(mv), info.get("mode"), ms, sim)
                ntag = sum(1 for t_ in st["tubes"] if t_.get("accept"))
                if ntag:
                    line += " وسوم=%d" % ntag             # «Tag!»: قوارير لا يُصبّ فيها إلا لون بطاقتها
                if verbose:
                    line += "\n      " + solver.describe(st) + "\n      moves=" + str(mv[:12])
        elif kind == "button":
            pt = vis.button(fr)
            line += " زر=%s جهاز=%s رقم=%s" % (pt, to_dev(*pt) if pt else None, vis.level_number(fr))
        elif kind == "lives":
            lp = vis.lives_popup(fr)
            line += " أرواح: ملء=%s X=%s ثمن=%s عدّاد=%s عملات=%s" % (
                lp and lp["refill"], lp and lp["close"], lp and lp["price"], lp and lp["timer"], vis.coins(fr))
        elif kind == "close":
            pt = vis.close(fr)
            line += " X=%s جهاز=%s" % (pt, to_dev(*pt) if pt else None)
        if kind == "unknown":
            gu = vis._pt(vis._safe("find_give_up", fr.arr))
            if gu:
                po = vis.play_on(fr)
                line += " لا حركات: GiveUp=%s PlayOn=%s ثمن=%s عملات=%s" % (gu, po and po[0], po and po[1], vis.coins(fr))
            if vis._safe("is_white_ad", fr.arr, default=False):
                plans["white_ad"] = plans.get("white_ad", 0) + 1
                line += " إعلان-أبيض X=%s" % (vis._pt(vis._safe("find_ad_close", fr.arr)),)
            elif vis._safe("is_ad", fr.arr, default=False):
                line += " إعلان-أسود"
            elif vis._safe("is_logo_overlay", fr.arr, default=False):
                plans["logo"] = plans.get("logo", 0) + 1
                line += " شعار-MAGIC-SORT"
        line += "  [%.0fms]" % ((time.perf_counter() - t) * 1000)
        print(line)
    print("\nالملخص: %d صورة، الأنواع %s، شاشات غير اللغز المختلفة (بصمة) %d"
          % (len(files), dict(kinds), novel))
    print("اللغز: %d لقطة، قُرئت %d، محلولة أصلاً %d، لها خطة %d (منها تحلّ اللغز كاملاً في النموذج %d)، "
          "بلا حركة %d، فيها قوارير مغطّاة %d؛ زمن الحلّال: أقصى %.0f ms، متوسط %.0f ms"
          % (plans["level"], plans["parsed"], plans["solved"], plans["planned"], plans["solved_sim"],
             plans["stuck"], plans["covered"], max_ms, tot_ms / max(1, plans["parsed"])))
    print("فيها جبس %d لقطة؛ إعلان تجريبي أبيض %d؛ شعار «MAGIC SORT» فوق لوحة معتمة %d"
          % (plans.get("plaster", 0), plans.get("white_ad", 0), plans.get("logo", 0)))
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
    if args.no_setup:
        bot.load_counters()                    # بعد أمر «update»: عدّادات السياسات من البوت السابق
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
