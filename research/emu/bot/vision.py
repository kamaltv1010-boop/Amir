# -*- coding: utf-8 -*-
"""رؤية بوت Magic Sort (بحث فقط): تصنيف الشاشة وقراءة حالة اللغز من لقطة.

كل الحساب على صورة مصغّرة إلى ارتفاع 1000 بكسل (العرض ≈ 473 لشاشة 1080×2280)،
والعتبات نسبية إلى عرض القارورة أو أبعاد الصورة. نقاط النقر بهذه الإحداثيات،
وتُحوَّل إلى الجهاز بالضرب في 2280/1000 (الدالة to_device). المكتبات: numpy وPillow فقط.

الواجهة:
    load(img)              -> مصفوفة RGB بارتفاع 1000 (يقبل مساراً أو PIL أو numpy أو bytes PNG)
    classify(img)          -> "level" | "button" | "lives" | "close" | "unknown"
    find_button(img)       -> (x, y) مركز الزرّ الرئيسي (أخضر كبير، أو «Hard Level» البنفسجي،
                              أو CONTINUE الرمادي في شروط الخدمة)، أو None؛ لا يعيد أزرار الأسعار
    find_close(img)        -> (x, y) مركز زرّ X الأحمر (بحلقة ذهبية)، أو None
    parse_level(img)       -> {"tubes": [{"x","y","cap","layers"}, ...], "warnings"?: [...]}
    debug_draw(img, state) -> صورة PIL عليها القوارير ونقاط النقر وأسماء الطبقات
    level_number(img)      -> رقم المرحلة (عنوان اللغز ومنه الصعبة والصعبة جداً، زرّ الواجهة، رأس نافذة الفوز) أو None
    level_badge(img)       -> "normal" | "hard" | "superhard" من عنوان شاشة اللغز، أو None
    find_boosters(img)     -> [(x, y), ...] أزرار الأدوات من اليسار (تراجع، خلط، قارورة)
    read_coins(img)        -> رصيد العملات من الحبّة أعلى اليسار (النوافذ والواجهة) أو None
    find_lives_popup(img)  -> {"refill", "close", "price", "timer"} لنافذة «More Lives» أو None
    find_give_up(img)      -> (x, y) «Give Up» في نافذة «No Available Moves»؛ find_play_on -> (x, y, الثمن) لـ «Play On»
    find_covers(img)       -> الستائر والأكياس وقوالب الجبس التي تغطي قوارير (تصير في parse_level قوارير "blocked")
    is_white_ad(img)       -> الإعلان التجريبي الأبيض (AppLovin MAX)؛ is_ad للإعلان الأسود
    find_ad_close(img)     -> (x, y) زرّ X صغير في زاوية علوية من إعلان (بعد عدّه التنازلي) أو None؛ لا يبحث في الأسفل («Install»)
    is_logo_overlay(img)   -> شعار «MAGIC SORT» فوق لوحة معتمة (احتفال الفوز؛ قد تتوقف اللعبة عنده)
    analyze(img)           -> {"kind", "level", ثم "state"+"boosters" أو "button" أو "close"}
    state_key(state)       -> مفتاح لمقارنة حالتين (تحقّق الاستقرار بين لقطتين)
    to_device(x, y)        -> إحداثيات الشاشة الحقيقية 1080×2280

صيغة الحالة (مشتركة مع solver.py):
    {"tubes": [{"x": int, "y": int, "cap": int, "layers": [str, ...]}, ...]}
    x,y نقطة النقر (مركز القارورة) بإحداثيات الارتفاع 1000، cap السعة بالطبقات،
    layers من الأسفل إلى الأعلى: اسم لون ثابت (PALETTE) أو "?" للطبقة المخفية؛ الفارغة [].
    الترتيب: الصف الأعلى من اليسار إلى اليمين ثم الصف التالي (القارورة الطويلة في صف قمّتها).
    مفاتيح إضافية اختيارية (لا يحتاجها الحلّال): في كل قارورة "tall" و"lifted" (مرفوعة/مختارة)
    و"box"؛ وفي الحالة "warnings" (غير فارغة = لقطة أثناء حركة أو شيء غير مألوف: أعد التصوير).
    المفاتيح والأبواب (من المرحلة 63): "keys" = مواضع الطبقات التي عليها ملصق مفتاح (من الأسفل) و"key_colors"
    ألوانها، والطبقة نفسها تُقرأ بلون سائلها الحقيقي؛ وفي الحالة "doors" = [{x,y,w,h,color}] أبواب خشبية بقفل
    ملوّن تخفي قوارير (لا تُعدّ قوارير). يحرّر المفتاحَ كشفُ طبقته (لا شيء بلون آخر فوقها) فيُفتح بابه.
    الستائر (من المرحلة 33 تقريباً) والأكياس (من 80 تقريباً) تغطي قارورة في خانتها: تُقرأ قارورة {"blocked": True، "cover": "curtain"|"bag"،
    "cover_color": لون أيقونة الستارة، "layers": []} بترتيب القراءة نفسه، فتبقى فهارس القوارير الأخرى حين تنكشف.
    والجبس (من المرحلة 100: قالب أبيض متشقّق بحجم قارورة) مثلها بـ "cover": "plaster": ينكسر حين تكتمل قارورة ظاهرة في الخانة
    المجاورة له في صفّه (يميناً أو يساراً؛ قاعدتها فتات جبس يُقرأ "clay")، وقاعدة الكسر في solver.plaster_breakers.
    "box" = [x0, أعلى، x1، أسفل] لكل قارورة (ومنها المغطّاة): منه يعرف الحلّال صفّ القارورة الطويلة وجاراتها.
    «Tag!» (من المرحلة 130): قارورة بشريط معقود حول عنقها وبطاقة ورقية يمين العنق عليها قارورة صغيرة بلون: لا يُصبّ فيها إلا
    ذلك اللون. تُقرأ "accept" = اسم اللون (من اللوحة) و"tag_box" = صندوق البطاقة، وطبقاتها تُقرأ كالعادة بنافذة يسار البطاقة.

القارورة الطويلة على حامل: قاعها مخفيّ، فيُقاس «الفراغ» (cap - عدد الطبقات) من قمة السائل
بدقة (هذا ما يحتاجه الحلّال)، والطبقات المرئية تقدير حتى الحامل. في المراحل 10..14 قيس
فراغها 4..8 وسعتها الكلية 10 أو 11 طبقة (ليست 8): ارتفاع الطبقة فيها كالعادية (0.585 من العرض).
"""
from __future__ import annotations

import io
from collections import Counter, deque

import numpy as np
from PIL import Image, ImageDraw

STD_H = 1000            # ارتفاع الصورة المعيارية
DEVICE_H = 2280         # ارتفاع شاشة المحاكي (pixel_4)

# ---------------------------------------------------------------- اللوحة
# ألوان السوائل كما قيست في لقطات المراحل 1..14 (الوسيط في منطقة مسطّحة من الطبقة).
PALETTE = {
    "red":      (195, 6, 2),
    "orange":   (228, 88, 0),
    "yellow":   (252, 192, 6),
    "green":    (113, 165, 2),
    "blue":     (21, 22, 190),
    "purple":   (94, 30, 142),
    "pink":     (254, 111, 216),
    "lavender": (92, 100, 165),
    "brown":    (114, 49, 42),      # لون جديد من المرحلة 15
    "cyan":     (0, 152, 215),      # لون جديد من المرحلة 17 (يشبه الزجاج: انظر glass_mask)
    "darkgreen": (12, 58, 2),       # من المرحلة 74 (كان يُسمّى c_10_7_1 أو c_11_7_1 فيبدو لونين)
    "plum":     (99, 0, 77),        # من المرحلة 74 (كان c_31_7_3)
    "mint":     (1, 206, 149),      # من المرحلة 99 (كان c_16_7_6؛ يشبه الزجاج: انظر glass_mask)
}
# لون خارج اللوحة (مرحلة لاحقة بلون جديد) يُسمّى آلياً بتقريب HSV دقيق: c_<hue>_<sat>_<val>
# (التصيير مسطّح، فاللون نفسه يعطي الاسم نفسه دائماً). أضِفه إلى PALETTE بعد رؤيته.
HIDDEN = "?"

# نسب هندسية للقارورة (بالنسبة إلى عرضها الخارجي w)، قيست على المراحل 1..14:
K_LAYER = 0.585      # ارتفاع الطبقة  (37.7 بكسل عند w=64.5)
K_ELL = 0.14         # فرق قمة الإهليلج العلوي عن خط الامتلاء
K_BOT = 0.13         # قاع السائل (في العمود الأوسط) فوق أسفل حافة الزجاج
K_TOP = 0.485        # قمة السائل في القارورة الممتلئة تحت قمة العنق
K_HEIGHT = 3.13      # ارتفاع القارورة العادية كلها (من العنق إلى القاع)
K_LIFT = 0.58        # القارورة المختارة ترتفع نحو 0.58w


# ---------------------------------------------------------------- أدوات عامة
def load(img) -> np.ndarray:
    """يعيد مصفوفة uint8 بشكل (1000, W, 3)."""
    if isinstance(img, np.ndarray):
        a = img
        if a.ndim == 2:
            a = np.stack([a] * 3, axis=-1)
        if a.shape[0] == STD_H:
            return a[..., :3].astype(np.uint8)
        im = Image.fromarray(a[..., :3].astype(np.uint8))
    elif isinstance(img, Image.Image):
        im = img
    elif isinstance(img, (bytes, bytearray)):
        im = Image.open(io.BytesIO(img))
    else:
        im = Image.open(img)
    im = im.convert("RGB")
    if im.height != STD_H:
        w = max(1, round(im.width * STD_H / im.height))
        im = im.resize((w, STD_H), Image.LANCZOS)
    return np.asarray(im, dtype=np.uint8)


def to_device(x, y, device_h: int = DEVICE_H):
    """إحداثيات الارتفاع 1000 -> بكسلات الجهاز."""
    s = device_h / STD_H
    return int(round(x * s)), int(round(y * s))


def _i16(a):
    return a.astype(np.int16)


def _shift_or(m, r):
    """تمدد ثنائي بنصف قطر r (مربع)."""
    if r <= 0:
        return m
    out = m.copy()
    H, W = m.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx == 0 and dy == 0:
                continue
            ys0, ys1 = max(dy, 0), H + min(dy, 0)
            xs0, xs1 = max(dx, 0), W + min(dx, 0)
            out[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx] |= m[ys0:ys1, xs0:xs1]
    return out


def _components(m):
    """مكوّنات متصلة (8-اتصال) بطريقة المقاطع الأفقية. تعيد قائمة قواميس."""
    H, W = m.shape
    parent = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    prev = []
    allruns = []
    rows = np.where(m.any(axis=1))[0]
    last_y = -2
    for y in rows:
        if y != last_y + 1:
            prev = []
        last_y = y
        d = np.diff(np.concatenate(([0], m[y].view(np.int8), [0])))
        starts = np.where(d == 1)[0]
        ends = np.where(d == -1)[0] - 1
        cur = []
        for s, e in zip(starts.tolist(), ends.tolist()):
            rid = len(parent)
            parent.append(rid)
            for ps, pe, pid in prev:
                if pe >= s - 1 and ps <= e + 1:
                    a, b = find(rid), find(pid)
                    if a != b:
                        parent[max(a, b)] = min(a, b)
            cur.append((s, e, rid))
            allruns.append((int(y), s, e, rid))
        prev = cur
    comps = {}
    for y, s, e, rid in allruns:
        r = find(rid)
        c = comps.get(r)
        if c is None:
            c = comps[r] = {"x0": s, "x1": e, "y0": y, "y1": y, "n": 0, "runs": []}
        if s < c["x0"]:
            c["x0"] = s
        if e > c["x1"]:
            c["x1"] = e
        if y > c["y1"]:
            c["y1"] = y
        c["n"] += e - s + 1
        c["runs"].append((y, s, e))
    return list(comps.values())


# ---------------------------------------------------------------- الألوان
def _srgb_to_lab(rgb):
    """rgb: مصفوفة (...,3) بقيم 0..255 -> Lab."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


_PAL_NAMES = list(PALETTE)
_PAL_RGB = np.array([PALETTE[n] for n in _PAL_NAMES], dtype=np.float64)
_PAL_LAB = _srgb_to_lab(_PAL_RGB)


def is_hidden_rgb(rgb) -> bool:
    r, g, b = (float(v) for v in rgb)
    return max(r, g, b) < 42 and b < 34 and (b - r) < 22


def is_navy_rgb(rgb) -> bool:
    """خلفية اللعبة الكحلية أو داخل قارورة فارغة (مع لمعان الزجاج الخفيف)."""
    r, g, b = (float(v) for v in rgb)
    return b > 26 and b - r > 18 and b - g > 14 and max(r, g, b) < 105


def color_name(rgb, max_de: float = 20.0) -> str:
    """اسم ثابت للون سائل من PALETTE (أقرب لون بفرق ΔE ≤ max_de؛ أقل فرق بين لونين
    في اللوحة 22). لون بعيد عن كل اللوحة يُسمّى c_<hue/10>_<sat*8>_<val*8>."""
    if is_hidden_rgb(rgb):
        return HIDDEN
    lab = _srgb_to_lab(np.asarray(rgb, dtype=np.float64))
    d = np.sqrt(((_PAL_LAB - lab) ** 2).sum(axis=1))
    k = int(np.argmin(d))
    if d[k] <= max_de:
        return _PAL_NAMES[k]
    r, g, b = (float(v) / 255 for v in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    sat = 0 if mx == 0 else (mx - mn) / mx
    if mx == mn:
        hue = 0.0
    elif mx == r:
        hue = (60 * ((g - b) / (mx - mn)) + 360) % 360
    elif mx == g:
        hue = 60 * ((b - r) / (mx - mn)) + 120
    else:
        hue = 60 * ((r - g) / (mx - mn)) + 240
    return "c_%02d_%d_%d" % (int(hue // 10), min(7, int(sat * 8)), min(7, int(mx * 8)))


# ---------------------------------------------------------------- الأقنعة
def glass_mask(a):
    """حواف الزجاج: أزرق سماوي فاتح رفيع."""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    m = (B > 115) & (G > 70) & (B - R > 50) & (G - R > 20) & (R < 150)
    # السائل السماوي (من المرحلة 17، نحو 0/152/215) يشبه لون الزجاج: يُستثنى (حافة الزجاج أفتح أحمراً وأقل
    # تشبّعاً؛ 0.01% فقط من بكسلاتها في لقطات المراحل 5..16 تقع في هذا المدى)
    # والسائل النعناعي (المرحلة 99، نحو 1/206/149: أخضره أعلى من أزرقه، والزجاج بالعكس) كان نحو 40% من «الزجاج» في
    # لقطات المرحلة 99 فتتشوّه أشكال قواريره وتختفي أحياناً؛ وفي 212 لقطة لغز أخرى لا يمسّ الاستثناء إلا 0.2% من الزجاج أو أقل
    return m & ~((R < 60) & (G > 130) & (B > 195)) & ~((R < 90) & (G > 150) & (G - B > 25))


def green_mask(a):
    """أخضر الأزرار الزاهي (وجه الزرّ وظلّه السفلي)."""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (G > 140) & (G - R > 60) & (G - B > 110) & (R < 175)


def purple_btn_mask(a):
    """بنفسجي أزرار الأدوات أسفل شاشة اللعب."""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (B > 200) & (R > 95) & (R < 190) & (G < 120) & (B - G > 120) & (R - G > 40)


def red_x_mask(a):
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (R > 170) & (G < 110) & (B < 120) & (R - G > 110)


def stand_mask(a):
    """حامل القارورة الطويلة: صخور بيج فاتحة."""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (R > 150) & (G > 120) & (B > 110) & (R >= G) & (G >= B - 25) & (R - B < 80) & (R - B > 5)


# ---------------------------------------------------------------- كشف القوارير
def _merge_components(comps, W):
    """يدمج أجزاء القارورة الواحدة: نصفا القارورة الطويلة (مفتوحة من الأسفل خلف
    الحامل)، وأجزاء حافة انقطعت عمودياً (ضغط الصورة أو لمعان). لا يدمج قارورة
    كاملة مع ما فوقها/تحتها (مثل القارورة المرفوعة تحت قارورة الصف الأعلى)."""
    comps = [dict(c) for c in comps]

    def absorb(a, b):
        a["x0"] = min(a["x0"], b["x0"])
        a["x1"] = max(a["x1"], b["x1"])
        a["y0"] = min(a["y0"], b["y0"])
        a["y1"] = max(a["y1"], b["y1"])
        a["n"] += b["n"]
        a["runs"] = a["runs"] + b["runs"]

    changed = True
    while changed:
        changed = False
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                a, b = comps[i], comps[j]
                wa, wb = a["x1"] - a["x0"] + 1, b["x1"] - b["x0"] + 1
                ha, hb = a["y1"] - a["y0"] + 1, b["y1"] - b["y0"] + 1
                wm = max(a["x1"], b["x1"]) - min(a["x0"], b["x0"]) + 1
                if wm > 0.17 * W:
                    continue
                gap_x = max(a["x0"], b["x0"]) - min(a["x1"], b["x1"])
                ov_y = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
                hmin = min(ha, hb)
                side = gap_x <= 0.06 * W and hmin > 0 and ov_y >= 0.6 * hmin
                ov_x = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"]) + 1
                wmin = min(wa, wb)
                vert = (ov_x >= 0.8 * wmin and -ov_y <= 0.5 * wmin
                        and ha < 2.8 * wa and hb < 2.8 * wb and wmin >= 0.07 * W)
                if side or vert:
                    absorb(a, b)
                    del comps[j]
                    changed = True
                    break
            if changed:
                break
    return comps


def _tube_geometry(m, c):
    """يقيس الجدارين من حافة الزجاج داخل صندوق المكوّن: العمود الأكثر بكسلات في
    الثلث الأيسر ثم الأيمن من الجزء الأوسط ارتفاعاً (يتحمّل انقطاع الحافة)."""
    x0, x1, y0, y1 = c["x0"], c["x1"], c["y0"], c["y1"]
    sub = m[y0:y1 + 1, x0:x1 + 1]
    hgt, wid = sub.shape
    if wid < 8 or hgt < 20:
        return None
    mid = sub[int(hgt * 0.35):int(hgt * 0.80)]
    colsum = mid.sum(axis=0)
    k = max(2, int(wid * 0.35))
    li = int(np.argmax(colsum[:k]))
    ri = wid - k + int(np.argmax(colsum[wid - k:]))
    need = 0.25 * mid.shape[0]
    okl, okr = colsum[li] >= need, colsum[ri] >= need
    if not okl and not okr:
        return None
    # جدار واحد ضعيف (سائل ملاصق موّه الحافة): نأخذه من حدّ الصندوق (التمدد 2 بكسل)
    if not okl:
        li = 2
    if not okr:
        ri = wid - 3
    if ri - li < 0.5 * wid:
        return None
    return float(x0 + li), float(x0 + ri)


def _profile(a, cx, w, ya, yb, kx=(0.14, 0.20)):
    """وسيط الألوان أفقياً في نافذة وسطى من القارورة لكل سطر بين ya و yb (kx: امتداد النافذة يساراً ويميناً بعرض القارورة؛
    القارورة الموسومة تأخذ نافذة يسار المحور: بطاقتها يمين العنق)."""
    H, W = a.shape[:2]
    xa = int(round(cx - kx[0] * w))
    xb = int(round(cx + kx[1] * w)) + 1
    xa, xb = max(0, xa), min(W, xb)
    ya, yb = max(0, int(ya)), min(H, int(yb))
    if yb <= ya or xb <= xa:
        return np.zeros((0, 3))
    return np.median(a[ya:yb, xa:xb].astype(np.float64), axis=1)


_SAMPLE_WINS = ((0.15, 0.19), (0.30, 0.30))
_SAMPLE_WINS_LEFT = ((0.28, 0.02), (0.38, 0.04))     # يسار المحور: طبقة بجانب بطاقة «Tag!»


def _sample(a, cx, w, yc, h, wins=_SAMPLE_WINS):
    """لون نافذة الطبقة (الوسيط): عرض نحو ثلث القارورة حول المركز وارتفاع ±0.22h.
    تُستبعد بكسلات «اليد» البيضاء في مراحل التعليم؛ إن غطّت أكثر النافذة يُوسَّع
    العرض، وإن بقيت مغطاة تُعاد None (طبقة محجوبة)."""
    H, W = a.shape[:2]
    for kx0, kx1 in wins:
        xa = max(0, int(round(cx - kx0 * w)))
        xb = min(W, int(round(cx + kx1 * w)) + 1)
        ya = max(0, int(round(yc - 0.22 * h)))
        yb = min(H, int(round(yc + 0.22 * h)) + 1)
        if yb <= ya or xb <= xa:
            return None
        win = a[ya:yb, xa:xb].reshape(-1, 3).astype(np.int16)
        mn, mx = win.min(axis=1), win.max(axis=1)
        glove = (mn > 140) & (mx - mn < 75)
        keep = win[~glove]
        if keep.shape[0] >= 0.45 * win.shape[0]:
            return np.median(keep.astype(np.float64), axis=0)
    return None


def _is_content(rgb, bg_lab=None):
    """سائل أو إهليلج أو طبقة مخفية (وليس داخل قارورة فارغة/خلفية)."""
    if is_navy_rgb(rgb):
        return False
    if bg_lab is not None and not is_hidden_rgb(rgb):
        d = float(np.sqrt(((_srgb_to_lab(np.asarray(rgb, dtype=np.float64)) - bg_lab) ** 2).sum()))
        if d < 14:
            return False
    return True


def _first_content(prof, ya, run=4, bg_lab=None):
    """أول سطر يبدأ منه run أسطر متتالية «محتوى» (سائل/إهليلج/مخفي)."""
    cnt = 0
    for i, px in enumerate(prof):
        if _is_content(px, bg_lab):
            cnt += 1
            if cnt >= run:
                return ya + i - run + 1
        else:
            cnt = 0
    return None


def _bg_lab(a, tubes):
    """لون الخلفية حول القوارير (Lab)، لتمييز داخل القارورة الفارغة إن تغيّرت الخلفية."""
    H, W = a.shape[:2]
    if not tubes:
        return None
    y0 = int(min(t["y0"] for t in tubes))
    y1 = int(max(t["y1"] for t in tubes))
    cols = np.ones(W, dtype=bool)
    for t in tubes:
        cols[max(0, int(t["x0"]) - 4):min(W, int(t["x1"]) + 5)] = False
    if cols.sum() < 6 or y1 <= y0:
        return None
    px = a[y0:y1, cols].reshape(-1, 3).astype(np.int16)
    px = px[px.max(axis=1) < 120]
    if px.shape[0] < 200:
        return None
    return _srgb_to_lab(np.median(px.astype(np.float64), axis=0))


def detect_tubes(a, diag=None):
    """يعيد قائمة القوارير الخام: صناديق وهندسة، بلا قراءة الطبقات.
    diag (قاموس اختياري) يُملأ بـ "odd": عدد أشكال الزجاج الكبيرة المرفوضة
    (قارورة مائلة أثناء الصبّ، أو شكل جديد لا نعرفه)."""
    H, W = a.shape[:2]
    m = glass_mask(a)
    # منطقة اللعب فقط (تحت عنوان المرحلة وفوق شريط الأدوات)
    play = np.zeros_like(m)
    play[int(0.13 * H):play_bottom(a)] = True
    m &= play
    md = _shift_or(m, 2)
    comps = [c for c in _components(md) if c["y1"] - c["y0"] >= 0.04 * H]
    comps = _merge_components(comps, W)
    tubes = []
    odd = 0
    for c in comps:
        bw = c["x1"] - c["x0"] + 1
        bh = c["y1"] - c["y0"] + 1
        big = bh >= 0.06 * H and c["n"] >= 0.0006 * H * W
        ok = (0.07 * W <= bw <= 0.2 * W) and bh >= 0.12 * H
        g = _tube_geometry(m, c) if ok else None
        if g is not None:
            xl, xr = g
            w = xr - xl
            ratio = bh / max(w, 1.0)
            ok = w >= 0.07 * W and ratio >= 2.3
        else:
            ok = False
        if not ok:
            odd += int(big)
            continue
        cx = (xl + xr) / 2
        # قمة العنق وأسفل القاع من الحافة نفسها قرب المحور (نجمة ملتصقة بالجانب لا تغيّرهما)
        y0, y1 = c["y0"], c["y1"]
        ca, cb = int(round(cx - 0.3 * w)), int(round(cx + 0.3 * w)) + 1
        rows = np.flatnonzero(m[y0:y1 + 1, max(0, ca):cb].any(axis=1))
        if rows.size:
            y0c, y1c = y0 + int(rows[0]), y0 + int(rows[-1])
        else:
            y0c, y1c = y0, y1
        # الجداران (للقارورة الطويلة: نهاية الجدارين عند الحامل)
        wa = m[y0:y1 + 1, max(0, int(xl) - 2):int(xl) + 3].any(axis=1)
        wb = m[y0:y1 + 1, max(0, int(xr) - 2):int(xr) + 3].any(axis=1)
        wl = np.flatnonzero(wa | wb)
        ywall = y0 + int(wl[-1]) if wl.size else y1
        tubes.append({"x0": c["x0"], "x1": c["x1"], "y0": y0c, "y1": y1c, "ywall": ywall,
                      "xl": xl, "xr": xr, "w": w, "cx": cx, "ratio": ratio})
    out = []
    if tubes:
        # العرض المعياري: وسيط عروض القوارير
        wmed = float(np.median([t["w"] for t in tubes]))
        sm = stand_mask(a)
        for t in tubes:
            if abs(t["w"] - wmed) > 0.22 * wmed:
                odd += 1
                continue
            w = wmed if abs(t["w"] - wmed) < 0.06 * wmed else t["w"]
            t["w"] = w
            t["ratio"] = (max(t["y1"], t["ywall"]) - t["y0"]) / w
            tall = t["ratio"] > 4.3
            if tall:
                t["y1"] = max(t["y1"], t["ywall"])
            # حامل تحت القارورة الطويلة؟
            ys0, ys1 = t["y1"] - int(0.1 * w), min(H, t["y1"] + int(0.9 * w))
            xs0, xs1 = int(t["cx"] - 0.4 * w), int(t["cx"] + 0.4 * w)
            stand = sm[ys0:ys1, max(0, xs0):min(W, xs1)].mean() if ys1 > ys0 else 0.0
            t["stand"] = float(stand)
            t["tall"] = bool(tall)
            # «الطين» (من المرحلة 40): شظايا بيج أمام قاع القارورة (أعرض منها) يستمرّ السائل خلفها، وتخفي حافة
            # القاع قرب المحور (فلا يُعتمد y1). تُعرف بلونها في نافذة حول نهاية الجدارين؛ لا سائل يمرّ بقناعها
            t["clay"] = False
            if not tall:
                ya, yb = int(t["ywall"] - 0.25 * w), min(H, int(t["ywall"] + 0.55 * w))
                xa, xb = max(0, int(t["cx"] - 0.45 * w)), min(W, int(t["cx"] + 0.45 * w))
                if yb > ya and sm[ya:yb, xa:xb].mean() > 0.15:
                    t["clay"] = True
            out.append(t)
        # قاع قارورة الطين: من ارتفاع القوارير العادية (وسيطها) لا من الحافة المخفية
        hs = [t["y1"] - t["y0"] for t in out if not t["tall"] and not t["clay"]]
        for t in out:
            if t["clay"]:
                hn = float(np.median(hs)) if hs else K_HEIGHT * t["w"]
                t["y1"] = int(round(t["y0"] + hn))
                t["ratio"] = (t["y1"] - t["y0"]) / t["w"]
    if diag is not None:
        diag["odd"] = odd
    return out


def _group_rows(tubes):
    """يجمع القوارير في صفوف حسب القمة (القارورة المرفوعة تبقى في صفّها)."""
    if not tubes:
        return []
    w = float(np.median([t["w"] for t in tubes]))
    # مفتاح الصف: قمة القارورة (للعادية محسوبة من قاعها، وللطويلة قمة عنقها)
    for t in tubes:
        t["key"] = t["top"]
    order = sorted(tubes, key=lambda t: t["key"])
    rows = []
    for t in order:
        if rows and abs(t["key"] - rows[-1]["key"]) <= 1.0 * w:
            rows[-1]["items"].append(t)
            rows[-1]["key"] = float(np.median([u["key"] for u in rows[-1]["items"]]))
        else:
            rows.append({"key": t["key"], "items": [t]})
    for r in rows:
        r["items"].sort(key=lambda t: t["cx"])
    return rows


# ---------------------------------------------------------------- قراءة الحالة
def parse_level(img, debug: bool = False) -> dict:
    """يقرأ حالة اللغز. انظر رأس الملف لصيغة الحالة. "warnings" غير الفارغة تعني أن
    اللقطة قد تكون أثناء حركة (صبّ، اكتمال القارورة الطويلة، يد التعليم...)."""
    a = load(img)
    H, W = a.shape[:2]
    warnings = []
    diag = {}
    raw = detect_tubes(a, diag)
    if diag.get("odd"):
        warnings.append("unrecognized glass shapes: %d (animation?)" % diag["odd"])
    if not raw:
        warnings.append("no tubes")
        return {"tubes": [], "warnings": warnings}
    w = float(np.median([t["w"] for t in raw]))
    h = K_LAYER * w
    e = K_ELL * w

    # قمة القارورة: العادية تُحسب من القاع (حافة العنق قد لا تُلتقط كاملة)
    for t in raw:
        tw = t["w"]
        if t["tall"]:
            t["top"] = float(t["y0"])
            if t["stand"] < 0.08:
                warnings.append("tall tube without stand at x=%d" % t["cx"])
        else:
            t["top"] = float(min(t["y0"], t["y1"] - K_HEIGHT * tw))

    # القوارير المغطّاة (ستارة أو كيس) في خاناتها بترتيب القراءة نفسه، فلا تتغيّر فهارس القوارير حين تنكشف
    covers = []
    for c in find_covers(a, raw):
        covers.append({"cover": c, "top": float(c["y1"] - K_HEIGHT * w), "cx": (c["x0"] + c["x1"]) / 2.0, "w": w,
                       "tall": False, "x0": c["x0"], "x1": c["x1"], "y0": c["y0"], "y1": c["y1"]})

    # القارورة المرفوعة (المختارة): قاعها أعلى من أوطأ قاع في صفّها بنحو 0.58w
    rows = _group_rows(raw + covers)
    for r in rows:
        regs = [t for t in r["items"] if not t["tall"] and not t.get("cover")]
        base = max(t["y1"] for t in regs) if len(regs) >= 2 else None
        for t in r["items"]:
            t["lifted"] = bool(base is not None and not t["tall"] and not t.get("cover")
                               and base - t["y1"] > 0.6 * K_LIFT * t["w"])
        nl = sum(1 for t in r["items"] if t["lifted"])
        if nl > 1:
            warnings.append("several lifted tubes in a row (animation?)")

    bg = _bg_lab(a, raw)
    tubes_out = []
    for r in rows:
        for t in r["items"]:
            tubes_out.append(_cover_tube(t) if t.get("cover") else _read_tube(a, t, h, e, warnings, bg))
    caps = [t["cap"] for t in tubes_out if not t.get("tall") and not t.get("blocked")]
    for t in tubes_out:
        if t.get("blocked") and caps:
            t["cap"] = max(set(caps), key=caps.count)
    _check_counts(tubes_out, warnings)
    state = {"tubes": tubes_out}
    doors = find_doors(a, raw)
    if doors:
        state["doors"] = doors
    if warnings:
        state["warnings"] = warnings
    if debug:
        state["_geom"] = {"w": w, "h": h, "e": e}
    return state


def wood_mask(a):
    """خشب الأبواب (من المرحلة 63): بني برتقالي وبيج دافئ (السائل البرتقالي والأصفر يشبهانه: تُستثنى القوارير)."""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (R > 130) & (R - B > 60) & (R - G > 25) & (G - B > 15) & (G > 40)


def find_doors(img, tubes=None):
    """أبواب خشبية بقفل ملوّن تغطي خانات قوارير: [{x, y, w, h, color}] (x,y الزاوية العليا اليسرى).
    tubes: القوارير الخام (detect_tubes) لاستبعاد صناديقها (سائل برتقالي/أصفر يشبه الخشب)."""
    a = load(img)
    H, W = a.shape[:2]
    m = wood_mask(a)
    keep = np.zeros_like(m)
    keep[int(0.13 * H):play_bottom(a)] = True
    m &= keep
    for t in (tubes if tubes is not None else detect_tubes(a)):
        m[max(0, int(t["y0"]) - 3):int(t["y1"]) + 4, max(0, int(t["x0"]) - 3):int(t["x1"]) + 4] = False
    out = []
    for c in _components(_shift_or(m, 2)):
        bw, bh = c["x1"] - c["x0"] + 1, c["y1"] - c["y0"] + 1
        if bw < 0.1 * W or bh < 0.12 * H or c["n"] < 0.45 * bw * bh:
            continue
        # ألواح الباب بيج فاتح (السائل البرتقالي/الأصفر في قارورة مائلة أثناء الصبّ ليس فيه هذا اللون)
        box = _i16(a[c["y0"]:c["y1"] + 1, c["x0"]:c["x1"] + 1])
        R, G, B = box[..., 0], box[..., 1], box[..., 2]
        if float(((R > 200) & (G > 140) & (B > 90) & (R - B > 50)).mean()) < 0.1:
            continue
        # القفل في وسط الباب: بكسلات زاهية مشبّعة بصبغة غير صبغة الخشب
        xa, xb = c["x0"] + int(0.2 * bw), c["x1"] - int(0.2 * bw)
        ya, yb = c["y0"] + int(0.25 * bh), c["y1"] - int(0.25 * bh)
        reg = a[ya:yb, xa:xb].reshape(-1, 3).astype(np.float64)
        color = None
        if reg.size:
            mx, mn = reg.max(axis=1), reg.min(axis=1)
            sat = (mx - mn) / np.maximum(mx, 1)
            r, g, b = reg[:, 0], reg[:, 1], reg[:, 2]
            woodish = (r > g) & (g > b) & ((g - b) < 0.75 * (r - b)) & ((g - b) > 0.12 * (r - b))
            sel = (mx > 140) & (sat > 0.5) & ~woodish
            if sel.sum() >= 0.03 * len(reg):
                color = _hue_name(np.median(reg[sel], axis=0))
        out.append({"x": int(c["x0"]), "y": int(c["y0"]), "w": int(bw), "h": int(bh), "color": color})
    out.sort(key=lambda d: (d["y"], d["x"]))
    return out


def cloth_mask(a):
    """قماش الستارة الوردي الفاتح (من المرحلة 33 تقريباً): أحمره أعلى قليلاً من أخضره وأزرقه، وأزرقه ليس أقل من أخضره
    (الخشب والطين البيج أزرقهما أقل بكثير، والسائل الوردي أخضره منخفض)."""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (R > 185) & (R - G >= 12) & (R - G <= 80) & (R - B >= 5) & (R - B <= 70) & (B - G >= -12)


def bag_mask(a):
    """قماش الكيس البنفسجي (من المرحلة 80 تقريباً، بخيط وبطاقة ذهبية برقم؛ ينفجر بعد عدد من القوارير المرتّبة): ضوءه وظلّه."""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (B > 150) & (B - G > 90) & (R - G > 45) & (R > 85) & (G < 120)


def plaster_mask(a):
    """الجبس الأبيض الكريمي المتشقّق (من المرحلة 100) يغلّف قارورة في خانتها: قنواته الثلاث متقاربة وأدفأ قليلاً من الرمادي
    (وسيطه نحو 212/203/189: R-G≈10 وG-B≈12). قماش الستارة الوردي أحمره أعلى بكثير من أخضره (R-G≈40) وأزرقه فوق أخضره،
    والخشب وشظايا الطين أحمرها أبعد عن أزرقها، فلا تملأ صندوقاً بحجم قارورة. (حافة الجبس اليسرى البنفسجية خارج القناع:
    يُصحَّح عرضه بـ _plaster_box.)"""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return ((R > 140) & (G > 110) & (B > 100) & (R - G >= -6) & (R - G <= 28) & (G - B >= -4)
            & (R - B >= 0) & (R - B <= 50))


def _plaster_box(a, box):
    """حدّا قالب الجبس الأفقيان الحقيقيان: في الأسطر الوسطى من الصندوق (بلا العنق والقاعدة) يمتدّ كل سطر يساراً ويميناً ما
    دامت البكسلات فاتحة (الخلفية كحلية داكنة)، والوسيط يعطي الحدّين. القناع يفوّت حافته اليسرى البنفسجية (نحو 7 بكسلات) فكان
    مركزه يميل 5 بكسلات عن مركز الخانة."""
    x0, y0, x1, y1 = box
    H, W = a.shape[:2]
    h = y1 - y0 + 1
    light = a[max(0, y0 + int(0.35 * h)):min(H, y0 + int(0.80 * h)) + 1].max(axis=2) > 120
    if light.shape[0] == 0:
        return box
    lim = max(4, int(0.25 * (x1 - x0 + 1)))
    ls, rs = [], []
    for row in light:
        L = x0
        while L > 0 and x0 - L < lim and row[L - 1]:
            L -= 1
        R = x1
        while R < W - 1 and R - x1 < lim and row[R + 1]:
            R += 1
        ls.append(L)
        rs.append(R)
    return int(np.median(ls)), y0, int(np.median(rs)), y1


def find_covers(img, tubes=None):
    """قوارير مغطّاة لا تُرى محتوياتها: ستارة قماش وردية عليها أيقونة قارورة بلون (تنزاح حين يكتمل ذلك اللون)، وكيس بنفسجي
    مربوط ببطاقة رقم (ينفجر بعد ذلك العدد من القوارير المرتّبة)، وقالب جبس أبيض متشقّق (من المرحلة 100؛ ينكسر حين تكتمل
    قارورة ظاهرة في الخانة المجاورة له في صفّه). كلها بحجم قارورة في خانتها (عرض 0.13 وارتفاع 0.17 تقريباً من الشاشة).
    يعيد [{"kind": "curtain"|"bag"|"plaster"، x0, y0, x1, y1، "color": لون أيقونة الستارة أو None}].
    tubes: القوارير الخام (detect_tubes) لاستبعاد صناديقها (سائل وردي أو بنفسجي داخل الزجاج)."""
    a = load(img)
    H, W = a.shape[:2]
    keep = np.zeros((H, W), dtype=bool)
    keep[int(0.13 * H):play_bottom(a)] = True
    for t in (tubes if tubes is not None else detect_tubes(a)):
        keep[max(0, int(t["y0"]) - 3):int(t["y1"]) + 4, max(0, int(t["x0"]) - 3):int(t["x1"]) + 4] = False
    out = []
    for kind, mask in (("curtain", cloth_mask(a)), ("bag", bag_mask(a)), ("plaster", plaster_mask(a))):
        for b in _rect_blobs(mask & keep, W, H, 0.004):
            if not (0.09 * W <= b["w"] <= 0.17 * W and 0.12 * H <= b["h"] <= 0.23 * H and b["fill"] >= 0.6):
                continue
            x0, y0, x1, y1 = b["box"]
            if kind == "plaster":
                x0, y0, x1, y1 = _plaster_box(a, (x0, y0, x1, y1))
            if any(min(x1, c["x1"]) - max(x0, c["x0"]) > 0.5 * (x1 - x0) and min(y1, c["y1"]) - max(y0, c["y0"]) > 0.5 * (y1 - y0)
                   for c in out):
                continue                        # الخانة نفسها قُرئت غطاءً من نوع آخر
            w, h = x1 - x0 + 1, y1 - y0 + 1
            color = None
            if kind == "curtain":
                # أيقونة القارورة في وسط الستارة: بكسلات مشبّعة ليست قماشاً
                sub = a[y0 + int(0.25 * h):y0 + int(0.70 * h), x0 + int(0.2 * w):x1 + 1 - int(0.2 * w)].reshape(-1, 3)
                si = sub.astype(np.int16)
                mx, mn = si.max(axis=1), si.min(axis=1)
                sel = (~cloth_mask(sub[None])[0]) & ((mx - mn) > 0.45 * np.maximum(mx, 1)) & (mx > 60)
                if sel.sum() >= 15:
                    color = color_name(np.median(sub[sel].astype(np.float64), axis=0))
            elif kind == "bag" and _gold_mask(a[y0:y1 + 1, x0:x1 + 1]).mean() < 0.01:
                continue                        # كيس بلا بطاقته الذهبية: ليس كيساً
            out.append({"kind": kind, "x0": int(x0), "y0": int(y0), "x1": int(x1), "y1": int(y1), "color": color})
    out.sort(key=lambda c: (c["y0"], c["x0"]))
    return out


def _check_counts(tubes, warnings):
    """فحص معقولية: عدد طبقات كل لون الظاهرة لا يتجاوز سعة قارورة واحدة (4 عادة،
    أو سعة القارورة الطويلة التي فيها هذا اللون)."""
    cnt = Counter(c for t in tubes for c in t["layers"] if c != HIDDEN)
    tall_cap = {}
    for t in tubes:
        if t.get("tall") and t["layers"]:
            tall_cap[t["layers"][-1]] = max(tall_cap.get(t["layers"][-1], 0), t["cap"])
    reg_caps = [t["cap"] for t in tubes if not t.get("tall")] or [4]
    base = max(set(reg_caps), key=reg_caps.count)
    for c, n in cnt.items():
        if n > max(base, tall_cap.get(c, 0)):
            warnings.append("color %s appears %d times" % (c, n))
        if c.startswith("c_"):
            warnings.append("unknown color %s" % c)


def _fill_occluded(layers, warnings, cx):
    """طبقة محجوبة (يد التعليم) تأخذ لون أقرب طبقة مرئية فوقها أو تحتها."""
    if all(c is not None for c in layers):
        return
    warnings.append("occluded layer at x=%d" % cx)
    for i, c in enumerate(layers):
        if c is not None:
            continue
        cand = None
        for j in list(range(i + 1, len(layers))) + list(range(i - 1, -1, -1)):
            if layers[j] is not None and layers[j] != HIDDEN:
                cand = layers[j]
                break
        layers[i] = cand or HIDDEN


def _clay_top(a, cx, w, ya, yb):
    """أعلى سطر فيه شظايا طين (بيج) في وسط القارورة بين ya و yb، أو None."""
    H, W = a.shape[:2]
    ya, yb = max(0, int(ya)), min(H, int(yb))
    xa, xb = max(0, int(cx - 0.3 * w)), min(W, int(cx + 0.3 * w))
    if yb <= ya or xb <= xa:
        return None
    rows = stand_mask(a[ya:yb, xa:xb]).mean(axis=1)
    idx = np.flatnonzero(rows > 0.25)
    return float(ya + idx[0]) if idx.size else None


# ألوان المفاتيح والأقفال بمدى الصبغة (درجات): الحدّ الأعلى لكل اسم
KEY_HUES = ((12, "red"), (32, "orange"), (58, "gold"), (165, "green"), (250, "blue"), (292, "purple"),
            (345, "pink"), (361, "red"))


def _hue_name(rgb) -> str:
    r, g, b = (float(v) / 255 for v in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return "gray"
    if mx == r:
        hue = (60 * ((g - b) / (mx - mn)) + 360) % 360
    elif mx == g:
        hue = 60 * ((b - r) / (mx - mn)) + 120
    else:
        hue = 60 * ((r - g) / (mx - mn)) + 240
    for lim, name in KEY_HUES:
        if hue < lim:
            return name
    return "red"


def _key_layer(a, cx, w, yc, h):
    """طبقة عليها ملصق مفتاح (من المرحلة 63: مفتاح زاهٍ بحدّ داكن في وسط الطبقة، فيضلّل الوسيط فتُقرأ c_*).
    في نافذة الطبقة كلها: اللون الغالب من اللوحة يغطي الربع على الأقل، وبكسلات بعيدة عنه (ΔE>35) تغطي 18% فأكثر
    موزّعة في «صفوف مختلطة» (سائل على الجانبين والملصق في الوسط: نافذة تقطع حدّ طبقتين صفوفها كاملة اللون)،
    وفيها بكسلات زاهية مشبّعة (الملصق). يعيد (لون السائل، لون المفتاح) أو None."""
    H, W = a.shape[:2]
    xa, xb = max(0, int(round(cx - 0.36 * w))), min(W, int(round(cx + 0.36 * w)) + 1)
    ya, yb = max(0, int(round(yc - 0.40 * h))), min(H, int(round(yc + 0.40 * h)) + 1)
    if yb - ya < 6 or xb - xa < 6:
        return None
    win = a[ya:yb, xa:xb].astype(np.float64)
    hh, ww = win.shape[:2]
    px = win.reshape(-1, 3)
    lab = _srgb_to_lab(px)
    d = np.sqrt(((lab[:, None, :] - _PAL_LAB[None, :, :]) ** 2).sum(-1))
    nn, dm = d.argmin(axis=1), d.min(axis=1)
    cnt = np.bincount(nn[dm < 20], minlength=len(_PAL_NAMES))
    k0 = int(np.argmax(cnt))
    if cnt[k0] < 0.25 * len(px):
        return None
    dd = np.sqrt(((lab - _PAL_LAB[k0]) ** 2).sum(-1))
    # المستوى الأول: ملصق بلون آخر (ΔE>35). الثاني: مفتاح بلون الطبقة نفسها (وردي على وردي في المرحلة 63): ظلّه وحدّه
    # المشبّعان أبعد من ΔE 25، بصفوف مختلطة أكثر (يد التعليم البيضاء غير مشبّعة فلا تُعدّ)
    for thr, fmin, mmin in ((35, 0.18, 0.3), (25, 0.2, 0.4)):
        farv = dd > thr
        if farv.mean() < fmin:
            continue
        rowf = farv.reshape(hh, ww).mean(axis=1)
        if float(((rowf > 0.15) & (rowf < 0.85)).mean()) < mmin:
            continue
        fp = px[farv]
        mx, mn = fp.max(axis=1), fp.min(axis=1)
        sat = (mx - mn) / np.maximum(mx, 1)
        if thr == 35:
            glyph = (mx > 120) & (sat > 0.45)
        else:
            glyph = sat > 0.5
            if glyph.mean() < 0.5:
                continue
        if glyph.sum() < 0.08 * len(px):
            continue
        return _PAL_NAMES[k0], _hue_name(np.median(fp[glyph], axis=0))
    return None


# ---------------------------------------------------------------- «Tag!» (من المرحلة 130)
# قارورة موسومة: شريط معقود حول عنقها وبطاقة ورقية معلّقة يمين العنق عليها قارورة صغيرة بلون السائل الوحيد الذي يُصبّ فيها
# («Bottle with TAG can only be filled with the same colored water!»). تبدأ فارغة. البطاقة كانت تقع في نافذة العمود الأوسط
# (_profile حتى cx+0.20w) تحت قمة السائل الممكنة، فيعدّها _first_content «محتوى» عند السطر top+0.5w فتُقرأ القارورة ممتلئة
# أربع طبقات، وعيّنة كل طبقة داخل الزجاج الفارغ الكحلي الداكن (3، 8، 46) ليس في اللوحة فيُسمّى c_23_7_1 (التشغيل 14).

def paper_mask(a):
    """ورق البطاقة الكريمي الخوخي (إطارها وظهرها؛ داخلها فاتح أبيض): أحمر > أخضر > أزرق بفرق معتدل. السائل الأصفر أزرقه منخفض،
    والوردي أخضره منخفض، والجبس أحمره قريب من أزرقه (R-B ≤ 50 مع G-B صغير)، فلا تكوّن بطاقة بشكلها وموضعها."""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (R > 200) & (G > 165) & (B > 130) & (R - B >= 15) & (R - B <= 110) & (R >= G) & (G >= B - 10)


def _palette_vote(px, max_de=25.0, min_n=6):
    """أكثر لون من اللوحة بين البكسلات px (n×3) بفرق ΔE ≤ max_de، أو None إن قلّت عن min_n."""
    if len(px) == 0:
        return None
    lab = _srgb_to_lab(px.astype(np.float64))
    d = np.sqrt(((lab[:, None, :] - _PAL_LAB[None, :, :]) ** 2).sum(-1))
    nn, dm = d.argmin(axis=1), d.min(axis=1)
    cnt = np.bincount(nn[dm <= max_de], minlength=len(_PAL_NAMES))
    k = int(np.argmax(cnt))
    return _PAL_NAMES[k] if cnt[k] >= min_n else None


def _find_tag(a, cx, w, top):
    """بطاقة «Tag!» لقارورة عنقها على top ومركزها cx: مكوّن ورقي كبير يمين العنق (يبدأ قرب المحور ويتجاوز نصف العرض يميناً) بين
    top+0.2w وtop+1.3w. يعيد {"box": [x0، y0، x1، y1]، "accept": لون القارورة الصغيرة في البطاقة (أو لون الشريط احتياطاً)،
    "ribbon": لون الشريط أو None} أو None. القارورة الصغيرة في النصف السفلي من البطاقة (أعلاها ثقب يمرّ فيه الشريط)."""
    H, W = a.shape[:2]
    xa, xb = max(0, int(round(cx - 0.10 * w))), min(W, int(round(cx + 0.80 * w)))
    ya, yb = max(0, int(round(top + 0.15 * w))), min(H, int(round(top + 1.35 * w)))
    if xb - xa < 8 or yb - ya < 8:
        return None
    pm = paper_mask(a[ya:yb, xa:xb])
    if pm.sum() < 0.04 * w * w:
        return None
    # إطار البطاقة حلقة قد تنقطع (داخلها أبيض والقارورة الصغيرة): صندوق كل القطع الورقية غير الصغيرة معاً
    parts = [c for c in _components(_shift_or(pm, 1)) if c["n"] >= 0.012 * w * w]
    if not parts:
        return None
    bx0, bx1 = min(c["x0"] for c in parts), max(c["x1"] for c in parts)
    by0, by1 = min(c["y0"] for c in parts), max(c["y1"] for c in parts)
    x0, x1, y0, y1 = xa + bx0, xa + bx1, ya + by0, ya + by1
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    npaper = int(pm[by0:by1 + 1, bx0:bx1 + 1].sum())
    if not (npaper >= 0.05 * w * w and 0.35 * w <= bw <= 0.85 * w and 0.45 * w <= bh <= 1.1 * w
            and x0 > cx - 0.08 * w and x1 > cx + 0.45 * w and (x0 + x1) / 2 > cx + 0.15 * w):
        return None
    # القارورة الصغيرة: البكسلات غير الورقية في الثلثين السفليين من البطاقة الأقرب إلى لون من اللوحة
    # (إطار القارورة الصغيرة الزجاجي أزرق فاتح قريب من الخزامي: بفرق ΔE ≤ 25 كان يقارب السائل البنفسجي 97 مقابل 120، وبفرق ≤ 12
    # يبقى 20 مقابل 73؛ فالتصويت بعتبة ضيّقة أولاً ثم أوسع إن قلّ العدد)
    sub = a[y0 + int(0.35 * bh):y1 + 1, x0:x1 + 1]
    px = sub.reshape(-1, 3)[~paper_mask(sub).reshape(-1)]
    accept = None
    for thr in (12.0, 18.0, 25.0):
        accept = _palette_vote(px, max_de=thr, min_n=max(6, int(0.006 * w * w)))
        if accept is not None:
            break
    # الشريط حول العنق (بلون البطاقة نفسه، أفتح ومجدول) في الشريحة top+0.2w..top+0.45w؛ فوقها غطاء العنق الزجاجي وهو نفسه
    # قريب من الخزامي (lavender) فلا يدخل التصويت. حتى في القارورة غير الموسومة يعطي زجاج الشريحة نحو 0.06w² «خزامياً»، فالشريط
    # احتياط للون (حين لا تُقرأ القارورة الصغيرة) لا شرط للكشف: البطاقة بشكلها وموضعها هي الحاسمة
    ra, rb = max(0, int(round(top + 0.20 * w))), min(H, int(round(top + 0.45 * w)))
    rxa, rxb = max(0, int(round(cx - 0.55 * w))), min(W, int(round(cx + 0.45 * w)))
    ribbon = _palette_vote(a[ra:rb, rxa:rxb].reshape(-1, 3), max_de=30.0, min_n=int(0.04 * w * w)) if rb > ra else None
    if accept is None:
        sat = px.max(axis=1).astype(np.float64) - px.min(axis=1)
        sel = (sat > 0.35 * np.maximum(px.max(axis=1), 1)) & (px.max(axis=1) > 60)
        if ribbon is not None:
            accept = ribbon
        elif sel.sum() >= 6:
            accept = color_name(np.median(px[sel].astype(np.float64), axis=0))
    if accept is None:
        return None
    return {"box": [int(x0), int(y0), int(x1), int(y1)], "accept": accept, "ribbon": ribbon}


def _cover_tube(t):
    """قارورة تحت ستارة أو كيس: محجوبة ("blocked") لا يُصبّ منها ولا فيها ومحتواها مجهول (طبقات فارغة لا تعني فارغة)."""
    c = t["cover"]
    return {"x": int(round(t["cx"])), "y": int(round((t["top"] + c["y1"]) / 2)), "cap": 4, "layers": [],
            "tall": False, "lifted": False, "blocked": True, "cover": c["kind"], "cover_color": c.get("color"),
            "box": [int(c["x0"]), int(round(t["top"])), int(c["x1"]), int(c["y1"])]}


def _read_tube(a, t, h, e, warnings, bg=None):
    w = t["w"]
    cx = t["cx"]
    top = t["top"]
    x0, x1 = t["x0"], t["x1"]
    # «Tag!» (من المرحلة 130): البطاقة يمين العنق خارج قراءة السائل (نافذة العمود يسار المحور، وعيّنات الطبقات المجاورة لها كذلك)
    tag = _find_tag(a, cx, w, top)
    pkx = (0.26, 0.0) if tag else (0.14, 0.20)
    # الشريط حول العنق وظلّه الداكن ينتهيان نحو top+0.41..0.47w؛ و`top` في الموسومة مقدَّر من القاع وحده (الشريط يخفي
    # زجاج العنق) فيهتزّ بكسلاً أو اثنين: تبدأ النافذة بعد الحافة العليا للبطاقة المقيسة (الشريط ينتهي قبلها + 3 بكسلات)
    py0 = top + 0.40 * w if not tag else max(top + 0.43 * w, tag["box"][1] + 0.12 * w)

    def near_tag(yc):
        return tag is not None and yc - 0.40 * h <= tag["box"][3] + 2 and yc + 0.40 * h >= tag["box"][1] - 2

    def tag_info(out):
        if tag:
            out["accept"] = tag["accept"]       # اللون الوحيد الذي يُصبّ فيها
            out["tag_box"] = list(tag["box"])
            # (لا تحذير حين يخالف لونُ الشريط القارورةَ الصغيرة: الشريط الأزرق الداكن يُقرأ بنفسجياً — zz_final في التشغيل 14)
            if str(tag["accept"]).startswith("c_"):
                warnings.append("unknown tag color %s at x=%d" % (tag["accept"], cx))
        return out
    if not t["tall"] or t["stand"] < 0.08:
        # قاع القارورة ظاهر (العادية، أو الطويلة بعد اكتمالها وتحطّم حاملها)
        B = t["y1"] - K_BOT * w                 # قاع السائل في العمود الأوسط
        T = top + K_TOP * w                     # قمة السائل لو امتلأت
        capf = (B - T - e) / h
        cap = int(round(capf))
        if abs(capf - cap) > 0.3:
            warnings.append("cap %.2f at x=%d" % (capf, cx))
        cap = max(1, cap)
        yend = B + 0.05 * w
        if t.get("clay"):
            # الطين ليس سائلاً: يُقرأ المحتوى فوق أعلى شظاياه فقط (القارورة الفارغة تبقى فارغة)
            yc0 = _clay_top(a, cx, w, B - 2.2 * h, t["y1"])
            if yc0 is not None:
                yend = min(yend, yc0 - 2)
        prof = _profile(a, cx, w, py0, yend, pkx)
        ytop = _first_content(prof, py0, bg_lab=bg)
        if ytop is None:
            n = 0
        else:
            nf = (B - ytop - e) / h
            n = int(round(nf))
            if abs(nf - n) > 0.33:
                warnings.append("fill %.2f at x=%d" % (nf, cx))
            n = max(0, min(cap, n))
        layers = []
        keys, key_colors = [], []
        for k in range(n):
            yc = B - (k + 0.5) * h
            rgb = _sample(a, cx, w, yc, h, _SAMPLE_WINS_LEFT if near_tag(yc) else _SAMPLE_WINS)
            c = color_name(rgb) if rgb is not None else None
            # الطويلة بلا حامل: شظايا الاحتفال تشبه الملصق؛ وبجانب بطاقة «Tag!» قارورتها الصغيرة تشبهه أيضاً
            if c is not None and c != HIDDEN and not t["tall"] and not near_tag(yc):
                kl = _key_layer(a, cx, w, yc, h)
                if kl is not None:
                    c = kl[0]
                    keys.append(k)
                    key_colors.append(kl[1])
            layers.append(c)
        _fill_occluded(layers, warnings, cx)
        if layers and layers[-1] == HIDDEN:
            warnings.append("hidden top at x=%d" % cx)
        ytap = (top + t["y1"]) / 2
        out = {"x": int(round(cx)), "y": int(round(ytap)), "cap": cap, "layers": layers,
               "tall": bool(t["tall"]), "lifted": bool(t.get("lifted")),
               "box": [int(x0), int(round(top)), int(x1), int(t["y1"])],
               "_ytop": ytop, "_B": B, "_h": h, "_e": e}
        if t.get("clay"):
            out["clay"] = True                  # يُصبّ فيها ولا يُصبّ منها حتى تكتمل
        if keys:
            out["keys"] = keys                  # مواضع طبقات المفاتيح (من الأسفل)
            out["key_colors"] = key_colors
        return tag_info(out)
    # ---- القارورة الطويلة على حامل: القاع مخفيّ خلف الحامل
    T = top + K_TOP * w
    ystand = t["y1"]
    prof = _profile(a, cx, w, py0, ystand + 0.35 * w, pkx)
    ytop = _first_content(prof, py0, bg_lab=bg)
    # أين يبدأ الحامل في العمود الأوسط؟
    sm = stand_mask(a)
    xa, xb = int(cx - 0.15 * w), int(cx + 0.2 * w)
    yst = None
    for y in range(int(ystand - 0.3 * w), min(a.shape[0], int(ystand + 0.8 * w))):
        if sm[y, xa:xb].mean() > 0.5:
            yst = y
            break
    if yst is None:
        yst = ystand + 0.25 * w
    if ytop is None or ytop > yst - 0.2 * w:
        free = int(round((yst - T) / h))
        n = 0
        layers = []
    else:
        free = int(round((ytop - T) / h))
        n = int(round((yst + 0.15 * w - ytop - e) / h))
        n = max(1, n)
        # عيّنات من القمة إلى الأسفل حتى الحامل، وما خلف الحامل بلون آخر طبقة مرئية
        fill = ytop + e
        vis = []
        for j in range(n):
            yc = fill + (j + 0.5) * h
            if yc + 0.22 * h > yst:
                break
            rgb = _sample(a, cx, w, yc, h, _SAMPLE_WINS_LEFT if near_tag(yc) else _SAMPLE_WINS)
            vis.append(color_name(rgb) if rgb is not None else None)
        if not vis:
            rgb = _sample(a, cx, w, (ytop + e + yst) / 2, h)
            vis = [color_name(rgb) if rgb is not None else None]
        layers = list(reversed(vis))
        _fill_occluded(layers, warnings, cx)
        while len(layers) < n:
            layers.insert(0, layers[0])
    cap = n + max(0, free)
    ytap = (top + ystand) / 2
    return tag_info({"x": int(round(cx)), "y": int(round(ytap)), "cap": int(cap), "layers": layers,
                     "tall": True, "lifted": False,
                     "box": [int(x0), int(round(top)), int(x1), int(ystand)],
                     "_ytop": ytop, "_yst": yst, "_h": h, "_e": e})


# ---------------------------------------------------------------- الأزرار وتصنيف الشاشة
def _blobs(mask, min_area):
    md = _shift_or(mask, 1)
    return [c for c in _components(md) if c["n"] >= min_area]


def hard_btn_mask(a):
    """بنفسجي زرّ «Hard Level» في الواجهة الرئيسية (أغمق من أزرار الأدوات)."""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (B > 140) & (R > 70) & (G < 55) & (B - G > 110) & (R - G > 55)


def superhard_btn_mask(a):
    """أحمر زرّ «Super Hard Level» في الواجهة الرئيسية (من المرحلة 19؛ نحو 190/15/20)."""
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (R > 150) & (G < 70) & (B < 80) & (R - G > 110) & (R - B > 100)


def _rect_blobs(mask, W, H, min_area_frac=0.0015):
    res = []
    for c in _blobs(mask, int(min_area_frac * H * W)):
        bw = c["x1"] - c["x0"] + 1
        bh = c["y1"] - c["y0"] + 1
        fill = c["n"] / float(bw * bh)
        res.append({"x": (c["x0"] + c["x1"]) / 2.0, "y": (c["y0"] + c["y1"]) / 2.0,
                    "w": bw, "h": bh, "n": c["n"], "fill": fill,
                    "box": (c["x0"], c["y0"], c["x1"], c["y1"])})
    return res


def green_buttons(img):
    """كل الأزرار الخضراء: قائمة قواميس {x,y,w,h,n,fill,box} من الأكبر."""
    a = load(img)
    H, W = a.shape[:2]
    res = []
    for b in _rect_blobs(green_mask(a), W, H):
        if b["w"] < 0.06 * W or b["h"] < 0.025 * H or b["fill"] < 0.35:
            continue
        if b["w"] / b["h"] > 6 or b["h"] / b["w"] > 2.2:
            continue
        res.append(b)
    res.sort(key=lambda r: -r["n"])
    return res


def _is_main(b, W, H):
    # أعرض زرّ رئيسي نحو 0.6 من العرض؛ صفّ اللاعب الأخضر في لوحة Strike Show يمتدّ بعرض الشاشة تقريباً فليس زرّاً
    return 0.38 * W <= b["w"] <= 0.72 * W and b["h"] >= 0.05 * H and abs(b["x"] - W / 2) < 0.12 * W


def _paid(a, b):
    """زرّ أخضر يصرف العملات («Play On 900» في نافذة «Continue?»): فيه عملة ذهبية داخل الزرّ (بعيداً عن حوافه)."""
    x0, y0, x1, y1 = b["box"]
    w, h = x1 - x0, y1 - y0
    reg = _i16(a)[y0 + int(0.2 * h):y1 - int(0.2 * h), x0 + int(0.12 * w):x1 - int(0.12 * w)]
    if reg.size == 0:
        return False
    R, G, B = reg[..., 0], reg[..., 1], reg[..., 2]
    return float(((R > 200) & (G > 150) & (B < 90) & (R - B > 120)).mean()) > 0.015


def main_button(img):
    """الزرّ الرئيسي: أخضر كبير في وسط الشاشة، أو بنفسجي «Hard Level» كبير.
    يعيد (x, y, نوع) أو None. لا يُعدّ رئيسياً إن كانت في الشاشة أزرار خضراء أخرى
    متوسطة الحجم كثيرة (الإعدادات) أو أزرار أسعار (المتجر)."""
    a = load(img)
    H, W = a.shape[:2]
    gb = green_buttons(a)
    # توهّج المشهد (بوّابة الحلقة 40 الخضراء) كتلة شبه مربّعة ممتلئة دون النصف: ليست زرّاً، ولا تُحسب «زرّاً آخر»
    gb = [b for b in gb if b["fill"] >= 0.5]
    # زرّ يصرف العملات لا يُعدّ رئيسياً: تُغلق نافذته بـ X («Continue?» بعد «Give Up»)
    big = [b for b in gb if _is_main(b, W, H) and b["w"] >= 1.6 * b["h"] and not _paid(a, b)]
    others = [b for b in gb if b not in big and b["n"] >= 0.004 * H * W]
    if len(big) == 1 and len(others) <= 1:
        return int(round(big[0]["x"])), int(round(big[0]["y"])), "green"
    if not gb:
        for kind, mask in (("hard", hard_btn_mask(a)), ("superhard", superhard_btn_mask(a))):
            for b in _rect_blobs(mask, W, H, 0.01):
                if (_is_main(b, W, H) and b["h"] >= 0.07 * H and 0.45 * H < b["y"] < 0.92 * H
                        and b["fill"] > 0.45):
                    return int(round(b["x"])), int(round(b["y"])), kind
        tos = find_tos(a)
        if tos:
            return tos[0], tos[1], "tos"
    return None


def find_tos(img):
    """زرّ CONTINUE الرمادي في نافذة شروط الخدمة عند أول تشغيل: زرّ رمادي عريض فوقه لوحة رمادية بنصف إضاءته تقريباً.
    النسخ القديمة: لوحة 18 وزرّ 36؛ النسخة 0.0.3536: لوحة 36 وزرّ 73 (يُبحث في مدى إضاءة كل منهما على حدة حتى لا
    تلتصق اللوحة بالزرّ في قناع واحد)."""
    a = load(img)
    H, W = a.shape[:2]
    ai = _i16(a)
    R, G, B = ai[..., 0], ai[..., 1], ai[..., 2]
    neutral = (abs(R - G) < 7) & (abs(G - B) < 7)
    for lo, hi in ((28, 48), (55, 95)):
        gray = neutral & (R >= lo) & (R <= hi)
        for b in _rect_blobs(gray, W, H, 0.01):
            if not (b["w"] >= 0.5 * W and 0.045 * H <= b["h"] <= 0.12 * H and b["fill"] > 0.6):
                continue
            x0, y0, x1, y1 = b["box"]
            bv = float(np.median(ai[y0:y1 + 1, x0:x1 + 1][gray[y0:y1 + 1, x0:x1 + 1]][:, 0]))
            above = ai[max(0, y0 - int(0.06 * H)):max(1, y0 - int(0.01 * H)), x0:x1 + 1].reshape(-1, 3)
            if above.size == 0:
                continue
            pv = above[:, 0]
            panel = ((pv > 0.35 * bv) & (pv < 0.7 * bv) & (np.abs(above[:, 1] - pv) < 6)
                     & (np.abs(above[:, 2] - pv) < 6)).mean()
            if panel > 0.5:
                return int(round(b["x"])), int(round(b["y"]))
    return None


def booster_free(img):
    """لكل زرّ في شريط الأدوات من اليسار: هل عليه شارة عدد حمراء (أداة مملوكة)؟ حين تنفد يظهر مكانها ثمن بالعملات
    (القارورة الإضافية 900): False. None إن لم يُعرف الشريط."""
    a = load(img)
    bx = _bar_boxes(a)
    if bx is None:
        return None
    ai = _i16(a)
    out = []
    for b in bx:
        x0, x1 = int(b["x"] + 0.1 * b["w"]), int(b["x"] + 0.8 * b["w"])
        y0, y1 = int(b["y"] + 0.2 * b["h"]), int(b["y"] + 0.8 * b["h"])
        reg = ai[max(0, y0):y1, max(0, x0):x1]
        if reg.size == 0:
            out.append(False)
            continue
        R, G, B = reg[..., 0], reg[..., 1], reg[..., 2]
        out.append(bool(((R > 170) & (G < 80) & (B < 120) & (R - G > 110)).mean() > 0.1))
    return out


def is_ad(img) -> bool:
    """إعلان بملء الشاشة بين المراحل: الشاشة شبه سوداء كلها وزرّ فاتح («Install»، أخضر نعناعي) في أسفلها. (شاشة التحميل
    السوداء بلا شيء في أسفلها، وشاشات اللعبة ملوّنة.)"""
    a = load(img)
    H, W = a.shape[:2]
    if float((a.max(axis=2) < 28).mean()) < 0.8:
        return False
    bottom = a[int(0.86 * H):int(0.98 * H)]
    return 0.02 < float((bottom.max(axis=2) > 150).mean()) < 0.4


def is_white_ad(img) -> bool:
    """الإعلان التجريبي الأبيض (AppLovin MAX: «Congrats! You're seeing a test ad.»، مثلث وردي بإبهام، «MAX by APPLOVIN»، حلقة عدّ
    تنازلي، وزرّ «Install» أخضر أسفل اليمين): شريط علوي أسود ومساحة بيضاء كبيرة (نصف الشاشة أو أكثر في كل نسخه المرئية من
    التشغيلات 5..9) ومعها المثلث الوردي أو نصّ MAX الفيروزي الداكن. (is_ad للإعلان الأسود؛ شاشات اللعبة ملوّنة أو كحلية،
    وسطح مكتب Android الوردي بلا شريط أسود.)"""
    a = load(img)
    H, W = a.shape[:2]
    ai = _i16(a)
    mx, mn = ai.max(axis=2), ai.min(axis=2)
    if float((mx[:int(0.06 * H)] < 30).mean()) < 0.85 or float((mn > 215).mean()) < 0.35:
        return False
    R, G, B = ai[..., 0], ai[..., 1], ai[..., 2]
    pink = (R > 215) & (G > 140) & (G < 205) & (B > 140) & (B < 205) & (R - G > 35)
    teal = (R < 70) & (G > 40) & (G < 110) & (B > 60) & (B < 130) & (B - R > 25)
    return float(pink.mean()) >= 0.01 or float(teal.mean()) >= 0.004


def find_ad_close(img):
    """زرّ إغلاق صغير على شكل X في زاوية علوية من إعلان بملء الشاشة (يظهر بعد العدّ التنازلي): رمز فاتح على خلفية داكنة أو داكن
    على فاتحة، مربّع تقريباً (8..45 بكسل)، خطّاه القطريان ممتلئان وما بينهما فارغ (لا مثلث «▶ Google Play» ولا «+» ولا قرص
    ممتلئ؛ والدائرة حول X مقبولة). يعيد (x, y) مركزه أو None. لا يبحث خارج الزاويتين العلويتين أبداً («Install» في الأسفل)."""
    a = load(img)
    H, W = a.shape[:2]
    lum = _i16(a).max(axis=2)
    for xa, xb in ((0, int(0.2 * W)), (int(0.8 * W), W)):
        ya, yb = 0, int(0.2 * H)
        reg = lum[ya:yb, xa:xb]
        rh, rw = reg.shape
        # الرمز فاتح على داكن (شريط الإعلان الأسود) أو داكن على فاتح (مساحته البيضاء): الخلفية حوله تُفحص محلياً
        for glyph, bg in ((reg > 150, reg < 100), (reg < 110, reg > 170)):
            for c in _components(glyph):
                bw, bh = c["x1"] - c["x0"] + 1, c["y1"] - c["y0"] + 1
                if not (8 <= bw <= 45 and 8 <= bh <= 45 and 0.6 <= bw / float(bh) <= 1.6):
                    continue
                fill = c["n"] / float(bw * bh)
                if not 0.12 <= fill <= 0.7:
                    continue
                y0, y1, x0, x1 = max(0, c["y0"] - 5), min(rh, c["y1"] + 6), max(0, c["x0"] - 5), min(rw, c["x1"] + 6)
                frame = np.ones((y1 - y0, x1 - x0), dtype=bool)
                frame[c["y0"] - y0:c["y1"] - y0 + 1, c["x0"] - x0:c["x1"] - x0 + 1] = False
                if frame.sum() == 0 or float(bg[y0:y1, x0:x1][frame].mean()) < 0.7:
                    continue
                sub = glyph[c["y0"]:c["y1"] + 1, c["x0"]:c["x1"] + 1]

                def hit(fx, fy, sub=sub, bw=bw, bh=bh):
                    x, y = int(round(fx * (bw - 1))), int(round(fy * (bh - 1)))
                    return bool(sub[max(0, y - 1):y + 2, max(0, x - 1):x + 2].any())
                ts = (0.15, 0.3, 0.4, 0.6, 0.7, 0.85)
                diag = sum(hit(t, t) for t in ts) + sum(hit(t, 1 - t) for t in ts)
                off = sum(hit(fx, fy) for fx, fy in ((0.5, 0.22), (0.5, 0.78), (0.22, 0.5), (0.78, 0.5)))
                if diag < 11 or off > 1 or not hit(0.5, 0.5):
                    continue
                # X متناظر يميناً ويساراً وأعلى وأسفل (أيقونات شريط الحالة وحروف النصّ ليست كذلك)
                sym = min(float((sub & f).sum()) / max(1, (sub | f).sum()) for f in (sub[:, ::-1], sub[::-1, :]))
                if sym >= 0.45:
                    return int(round(xa + (c["x0"] + c["x1"]) / 2.0)), int(round(ya + (c["y0"] + c["y1"]) / 2.0))
    return None


def is_logo_overlay(img) -> bool:
    """شعار «MAGIC SORT» (قِدر بنفسجي وحروف بيضاء وصفراء بحدّ أزرق ملكي) فوق لوحة معتمة: جزء من احتفال الفوز يزول عادة في ثوانٍ،
    وقد يبقى فتتوقف اللعبة عنده (التشغيل التاسع: مرتان حتى إعادة التشغيل بعد 3 دقائق، مع لمسات «سهم» كاذبة على الحروف الصفراء).
    يُعرف بالعتمة حول وسط الشاشة، وحدّ الحروف الأزرق الملكي (أحمره شبه صفر، نحو 6/55/190: 1.6% من وسط الشاشة فأكثر في كل
    إطاراته، و0.7% أو أقل في كل شاشة معتمة أخرى من التشغيلات 2..9 كـ «Your Cards» و«Tap to Claim»)، وحروف فاتحة، ووسطه أفقياً."""
    a = load(img)
    H, W = a.shape[:2]
    if booster_bar(a):
        return False
    ai = _i16(a)
    mx = ai.max(axis=2)
    cy0, cy1, cx0, cx1 = int(0.30 * H), int(0.60 * H), int(0.10 * W), int(0.90 * W)
    outside = np.ones((H, W), dtype=bool)
    outside[cy0:cy1, cx0:cx1] = False
    if float((mx[outside] < 70).mean()) < 0.85:
        return False
    c = ai[cy0:cy1, cx0:cx1]
    R, G, B = c[..., 0], c[..., 1], c[..., 2]
    blue = (B > 150) & (R < 40) & (G > 25) & (G < 105) & (B - G > 90)
    if float(blue.mean()) < 0.012:
        return False
    letters = ((R > 215) & (G > 205) & (B > 195)) | ((R > 220) & (G > 150) & (B < 110) & (R - B > 130))
    if float(letters.mean()) < 0.04:
        return False
    # الوسط الأفقي للشعار كله (القِدر البنفسجي والحروف وحدّها): في إطار «M» يقع الحرف وحدّه الأزرق يسار القِدر
    purple = (B > 140) & (R > 90) & (G < 100) & (B - G > 80) & (R - G > 40)
    xs = np.nonzero(blue | letters | purple)[1]
    return abs(cx0 + float(xs.mean()) - W / 2.0) < 0.12 * W


def find_give_up(img):
    """نافذة «No Available Moves»: زرّ أخضر «Play On» بالعملات يساراً وزرّ برتقالي «Give Up» يميناً في صفّ واحد أسفل الشاشة.
    يعيد مركز «Give Up» (لا تُصرف العملات) أو None."""
    a = load(img)
    H, W = a.shape[:2]
    ai = _i16(a)
    R, G, B = ai[..., 0], ai[..., 1], ai[..., 2]
    orange = (R > 200) & (G > 50) & (G < 150) & (B < 90) & (R - G > 80)
    greens = [g for g in green_buttons(a) if g["x"] < 0.45 * W and g["w"] >= 0.3 * W and g["y"] > 0.7 * H]
    for b in _rect_blobs(orange, W, H, 0.004):
        if not (b["x"] > 0.55 * W and b["w"] >= 0.3 * W and 0.06 * H <= b["h"] <= 0.12 * H and b["y"] > 0.7 * H
                and b["fill"] > 0.5):
            continue
        if any(abs(g["y"] - b["y"]) < 0.03 * H for g in greens):
            return int(round(b["x"])), int(round(b["y"]))
    return None


def _gold_mask(a):
    a = _i16(a)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (R > 200) & (G > 140) & (B < 110) & (R - B > 110)


def _button_price(a, b):
    """الثمن المكتوب بالأبيض بعد العملة الذهبية داخل زرّ أخضر (b من green_buttons): «Play On 900»، «Refill 900»؛ أو None."""
    x0, y0, x1, y1 = b["box"]
    h = y1 - y0 + 1
    sub = a[y0 + int(0.15 * h):y1 + 1 - int(0.10 * h), x0:x1 + 1]   # بلا شارة «Add Bottle» الصفراء فوق الزرّ
    H, W = a.shape[:2]
    coins = [c for c in _rect_blobs(_gold_mask(sub), W, H, 0.0002)
             if 0.2 * h <= c["h"] <= 0.8 * h and 0.6 <= c["w"] / float(c["h"]) <= 1.6]
    if not coins:
        return None
    cx1 = max(coins, key=lambda c: c["n"])["box"][2]
    s = _read_digit_row(_white_text(sub[:, cx1 + 2:]), min_h=max(6, int(0.2 * h)))
    return int(s) if s else None


def read_coins(img):
    """رصيد العملات في الحبّة أعلى يسار نافذتي «No Available Moves» و«More Lives» (السائق لا يقرؤه إلا فيهما، وصحّت كل
    قراءاتهما وتنويعاتها): عملة ذهبية وعلى يمينها حبّة كريمية بأرقام بنّية داكنة. يعيد العدد أو None (ومنها شاشات بلا
    هذه الحبّة). لا يُعتمد في «Continue?»: الرقم 5 فيها قد يُقرأ 6 (590 ← 690؛ الفارق بين القالبين 5، حدّ القبول نفسه)."""
    a = load(img)
    H, W = a.shape[:2]
    reg = a[:int(0.2 * H), :int(0.5 * W)]
    ri = _i16(reg)
    cream = (ri[..., 0] > 200) & (ri[..., 1] > 180) & (ri[..., 2] > 130)
    gold = _gold_mask(reg)
    for b in sorted(_rect_blobs(cream, W, H, 0.001), key=lambda b: -b["n"]):
        if not (0.10 * W <= b["w"] <= 0.40 * W and 0.018 * H <= b["h"] <= 0.07 * H and b["w"] >= 2 * b["h"]):
            continue
        x0, y0, x1, y1 = b["box"]
        if gold[y0:y1 + 1, max(0, x0 - int(0.12 * W)):x0].mean() < 0.15:
            continue                    # بلا عملة ذهبية يسار الحبّة
        s = _read_digit_row(_dark_text(reg[y0:y1 + 1, x0:x1 + 1]), min_h=max(6, int(0.35 * b["h"])))
        if s:
            return int(s)
    return None


def _lives_timer(a, ya, yb):
    """عدّاد «Time to next life» (MM:SS بأرقام داكنة على حبّة كريمية بجانب ساعة ذهبية) بين ya و yb: الثواني أو None.
    السطر المقروء هو الأوطأ (فوقه نصّ «Time to next life» بالحروف)."""
    H, W = a.shape[:2]
    ya, yb = max(0, int(ya)), min(H, int(yb))
    xa, xb = int(0.15 * W), int(0.85 * W)
    if yb - ya < 10:
        return None
    sub = a[ya:yb, xa:xb]
    dark = _dark_text(sub)
    rows = np.flatnonzero(dark.sum(axis=1) >= 2)
    if rows.size == 0:
        return None
    # الأسطر: مقاطع متصلة من الصفوف التي فيها نصّ داكن (حواف اللوحة والزرّ أسطر رفيعة تُهمل)، من الأسفل
    cuts = np.flatnonzero(np.diff(rows) > 2)
    starts = [int(rows[0])] + [int(rows[c + 1]) for c in cuts]
    ends = [int(rows[c]) for c in cuts] + [int(rows[-1])]
    for s0, s1 in reversed(list(zip(starts, ends))):
        if not 0.010 * H <= s1 - s0 + 1 <= 0.035 * H:
            continue
        line = slice(max(0, s0 - 2), s1 + 3)
        gcols = np.flatnonzero(_gold_mask(sub[line]).sum(axis=0) >= 2)
        x0 = int(gcols[-1]) + 2 if gcols.size and gcols[-1] < 0.6 * sub.shape[1] else 0   # بعد الساعة الذهبية
        s = _read_digit_row(dark[line, x0:], min_h=8)
        if not s or not 3 <= len(s) <= 4:
            continue
        mm, ss = int(s[:-2]), int(s[-2:])
        if ss < 60 and mm < 60:
            return mm * 60 + ss
    return None


def find_lives_popup(img):
    """نافذة «More Lives» (نفدت الأرواح بعد إخفاقات المرحلة 99): قلب أحمر كبير برقمه في وسط لوحة كريمية، وتحته زرّ أخضر
    «Refill» بثمن بالعملات، وزرّ X أحمر أعلى اليمين؛ وتحت الأخضر زرّ «+1 Life» (إعلان) أو «Free Lives»: لا يُلمسان أبداً.
    يعيد {"refill": (x, y)، "close": (x, y)، "price": ثمن الملء أو None، "timer": ثواني الروح القادمة أو None} أو None.
    («Continue?» فيها لوحة كريمية وزرّ أخضر بالعملات وX لكن بلا قلب في الوسط.)"""
    a = load(img)
    H, W = a.shape[:2]
    if booster_bar(a):
        return None
    xc = find_close(a)
    if xc is None or xc[0] < 0.6 * W or xc[1] > 0.4 * H:
        return None
    ya, yb = int(0.18 * H), int(0.48 * H)
    ai = _i16(a[ya:yb])
    R, G, B = ai[..., 0], ai[..., 1], ai[..., 2]
    red = (R > 170) & (G < 90) & (B < 110) & (R - G > 110)
    hearts = [b for b in _rect_blobs(red, W, H, 0.003)
              if abs(b["x"] - W / 2.0) < 0.08 * W and 0.10 * W <= b["w"] <= 0.32 * W and 0.035 * H <= b["h"] <= 0.11 * H
              and 0.9 <= b["w"] / float(b["h"]) <= 2.2 and b["fill"] > 0.45]
    if not hearts:
        return None
    heart = max(hearts, key=lambda b: b["n"])
    hy1 = ya + heart["box"][3]
    greens = [g for g in green_buttons(a)
              if _paid(a, g) and abs(g["x"] - W / 2.0) < 0.1 * W and g["w"] >= 0.4 * W and hy1 < g["y"] < hy1 + 0.35 * H]
    if not greens:
        return None
    g = min(greens, key=lambda b: b["y"])
    return {"refill": (int(round(g["x"])), int(round(g["y"]))), "close": (int(xc[0]), int(xc[1])),
            "price": _button_price(a, g), "timer": _lives_timer(a, hy1 + 0.02 * H, g["box"][1] - 0.005 * H)}


def find_play_on(img):
    """زرّ «Play On» الأخضر في نافذة «No Available Moves» (يسار «Give Up» في صفّه؛ يضيف قارورة بثمن بالعملات، 900 في
    المرحلة 99): (x, y, الثمن أو None) أو None. لا يُلمس إلا بسياسة السائق."""
    a = load(img)
    H, W = a.shape[:2]
    gu = find_give_up(a)
    if gu is None:
        return None
    for g in green_buttons(a):
        if g["x"] < 0.45 * W and g["w"] >= 0.3 * W and g["y"] > 0.7 * H and abs(g["y"] - gu[1]) < 0.03 * H:
            return int(round(g["x"])), int(round(g["y"])), _button_price(a, g)
    return None


def level_badge(img):
    """نوع المرحلة من عنوانها في شاشة اللغز: "superhard" (إطار أحمر وشريط «SUPER HARD» وثلاث جماجم)، "hard" (إطار
    بنفسجي وردي وشريط «HARD» وجمجمة)، "normal" (إطار بنفسجي أزرق بلا شريط)، أو None خارج شاشة اللغز. يُقاس الشريط تحت
    العنوان (نحو 46% أحمر في الصعبة جداً و26..40% بنفسجي وردي في الصعبة وصفر في العادية، في 50 بداية مرحلة)."""
    a = load(img)
    H, W = a.shape[:2]
    if not booster_bar(a):
        return None
    ai = _i16(a[int(0.15 * H):int(0.222 * H), int(0.30 * W):int(0.70 * W)])
    R, G, B = ai[..., 0], ai[..., 1], ai[..., 2]
    rib = (slice(int(0.04 * H), None), slice(int(0.10 * W), int(0.30 * W)))
    red = (R > 150) & (G < 80) & (B < 90) & (R - G > 100)
    mag = (R > 110) & (B > 150) & (G < 90) & (B - G > 100) & (R - G > 50) & (B - R > -40)
    if red[rib].mean() > 0.15 or red.mean() > 0.06:
        return "superhard"
    if mag[rib].mean() > 0.10 or mag.mean() > 0.05:
        return "hard"
    return "normal"


def find_button(img):
    """مركز الزرّ الرئيسي (Level N / Continue / Claim / Hard Level / CONTINUE شروط
    الخدمة)، وإلا مركز أكبر زرّ أخضر كبير في وسط الشاشة، وإلا None.
    لا يعيد أبداً أزرار الأسعار الصغيرة الجانبية في المتجر."""
    a = load(img)
    H, W = a.shape[:2]
    mb = main_button(a)
    if mb:
        return mb[0], mb[1]
    for b in green_buttons(a):
        if _is_main(b, W, H) and not _paid(a, b):
            return int(round(b["x"])), int(round(b["y"]))
    return None


def _x_score(ai, cx, cy, size):
    """هل في الدائرة علامة X بيضاء بحلقة ذهبية؟ يعيد (أدنى بياض بين الاتجاهات القطرية
    الأربعة، أدنى احمرار بين المحاور الأربعة، نسبة الذهبي على حلقة حول الدائرة).
    قلوب الحياة («5» أو «∞») والشارات الحمراء ترسب في المحاور أو الحلقة."""
    def frac(x, y, test):
        x, y = int(round(x)), int(round(y))
        p = ai[max(0, y - 1):y + 2, max(0, x - 1):x + 2].reshape(-1, 3)
        if p.size == 0:
            return 0.0
        return float(test(p).mean())

    white = lambda p: (p[:, 0] > 190) & (p[:, 1] > 170) & (p[:, 2] > 160)
    red = lambda p: (p[:, 0] > 150) & (p[:, 1] < 110) & (p[:, 0] - p[:, 1] > 90)
    gold = lambda p: (p[:, 0] > 190) & (p[:, 1] > 130) & (p[:, 2] < 120) & (p[:, 0] - p[:, 2] > 90)
    diag = [np.mean([frac(cx + sx * k * size, cy + sy * k * size, white) for k in (0.08, 0.13, 0.18, 0.23)])
            for sx in (-1, 1) for sy in (-1, 1)]
    axis = [np.mean([frac(cx + dx * k * size, cy + dy * k * size, red) for k in (0.22, 0.28, 0.34)])
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))]
    ang = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    ring = np.mean([frac(cx + 0.6 * size * np.cos(t), cy + 0.6 * size * np.sin(t), gold) for t in ang])
    return float(min(diag)), float(min(axis)), float(ring)


def find_close(img):
    """مركز زرّ الإغلاق X (دائرة حمراء فيها X أبيض، بحلقة ذهبية)، أو None."""
    a = load(img)
    H, W = a.shape[:2]
    ai = _i16(a)
    best = None
    for b in _rect_blobs(red_x_mask(a), W, H, 0.0006):
        bw, bh = b["w"], b["h"]
        if not (0.075 * W <= bw <= 0.17 * W) or not (0.8 <= bw / float(bh) <= 1.25):
            continue
        if b["fill"] < 0.4:
            continue
        size = min(bw, bh)
        cx, cy = b["x"], b["y"]
        dg, ax, ring = _x_score(ai, cx, cy, size)
        if dg < 0.40 or ax < 0.72 or ring < 0.40:
            continue
        score = dg + ax + ring + 0.002 * size
        if best is None or score > best[0]:
            best = (score, cx, cy)
    if best is None:
        return None
    return int(round(best[1])), int(round(best[2]))


def booster_bar(img):
    """هل شريط الأدوات ظاهر؟ 2..5 أزرار بنفسجية مربعة (≈0.13 من العرض) في صف واحد
    قرب 0.85 من الارتفاع، متساوية التباعد وحول منتصف الشاشة. (أشرطة التبويب في
    الواجهة الرئيسية والمتجر مستطيلة وأوطأ، وأيقونات المتجر أصغر.)"""
    return _bar_boxes(load(img)) is not None


def _bar_boxes(a):
    """أزرار شريط الأدوات [{x, y (في الصورة كلها), w, h}...] أو None. الشريط قرب 0.85 من الارتفاع عادة،
    وينزل إلى نحو 0.92 حين تحتاج القوارير ثلاثة صفوف (المرحلة 16 وما بعدها)."""
    H, W = a.shape[:2]
    y0, y1 = int(0.76 * H), int(0.99 * H)
    pm = purple_btn_mask(a[y0:y1])
    boxes = []
    for b in _rect_blobs(pm, W, H):
        if (0.10 * W <= b["w"] <= 0.17 * W and 0.10 * W <= b["h"] <= 0.17 * W
                and 0.82 <= b["w"] / float(b["h"]) <= 1.22 and b["fill"] >= 0.45
                and 0.80 * H <= b["y"] + y0 <= 0.95 * H):
            boxes.append(dict(b, y=b["y"] + y0))
    if not (2 <= len(boxes) <= 5):
        return None
    ys = [b["y"] for b in boxes]
    if max(ys) - min(ys) > 0.015 * H:
        return None
    xs = sorted(b["x"] for b in boxes)
    gaps = np.diff(xs)
    if gaps.min() < 0.14 * W or gaps.max() > 1.6 * gaps.min() + 0.01 * W:
        return None
    if abs((xs[0] + xs[-1]) / 2 - W / 2) >= 0.1 * W:
        return None
    return sorted(boxes, key=lambda b: b["x"])


def play_bottom(a):
    """أسفل منطقة اللعب: فوق شريط الأدوات بقليل (0.83 من الارتفاع إن لم يظهر الشريط)."""
    H = a.shape[0]
    boxes = _bar_boxes(a)
    if not boxes:
        return int(0.83 * H)
    top = min(b["y"] - b["h"] / 2.0 for b in boxes)
    return int(max(0.83 * H, min(0.92 * H, top - 0.03 * H)))


def find_boosters(img):
    """مراكز أزرار الأدوات من اليسار إلى اليمين [(x, y), ...] (في المراحل الأولى:
    تراجع، خلط، قارورة إضافية)، أو [] إن لم يظهر الشريط."""
    boxes = _bar_boxes(load(img))
    if not boxes:
        return []
    return [(int(round(b["x"])), int(round(b["y"]))) for b in boxes]


def find_tutorial_arrow(img):
    """سهم التعليم الأصفر الكبير (اللعبة تعتّم الشاشة وتشير بسهم إلى ما يجب لمسه، مثل صورة اللاعب قبل «الفرق»).
    يعيد نقطة الهدف أمام رأس السهم (x, y) أو None. السهم أصفر ساطع ممدود (نسبة طوله إلى عرضه 1.4 فأكثر)، ورأسه
    الطرف الأعرض: السهم الصاعد هدفه فوق قمته بنحو 0.07 من الارتفاع، وكذلك النازل والأفقيان."""
    a = load(img)
    H, W = a.shape[:2]
    if tabbar_fraction(a) > 0.4:
        return None                    # شريط التبويبات مضيء: لا تعتيم تعليم (صفحة عادية مثل الفرق أو المتصدّرين)
    ai = _i16(a)
    R, G, B = ai[..., 0], ai[..., 1], ai[..., 2]
    m = (R > 215) & (G > 140) & (B < 110) & (R - B > 130)
    best = None
    for b in _rect_blobs(m, W, H, 0.0015):
        bw, bh = b["w"], b["h"]
        if max(bw, bh) / float(max(1, min(bw, bh))) < 1.4 or not (0.35 <= b["fill"] <= 0.8):
            continue
        bx0, by0, bx1, by1 = b["box"]
        if bx0 <= 2 or by0 <= 2 or bx1 >= W - 3 or by1 >= H - 3:   # أشرطة الواجهة عند الحواف ليست أسهماً
            continue
        if best is None or b["n"] > best["n"]:
            best = b
    if best is None:
        return None
    x0, y0, x1, y1 = best["box"]
    sub = m[y0:y1 + 1, x0:x1 + 1]
    d = int(round(0.07 * H))
    if best["h"] >= best["w"]:
        k = max(1, sub.shape[0] * 3 // 10)
        top, bot = sub[:k].sum(axis=1).mean(), sub[-k:].sum(axis=1).mean()
        cx = int(round((x0 + x1) / 2))
        return (cx, max(0, y0 - d)) if top >= bot else (cx, min(H - 1, y1 + d))
    k = max(1, sub.shape[1] * 3 // 10)
    left, right = sub[:, :k].sum(axis=0).mean(), sub[:, -k:].sum(axis=0).mean()
    cy = int(round((y0 + y1) / 2))
    return (max(0, x0 - d), cy) if left >= right else (min(W - 1, x1 + d), cy)


def tabbar_fraction(img) -> float:
    """نسبة البنفسجي في شريط التبويبات السفلي (0.935..0.99 من الارتفاع): نحو 0.68 في الواجهة الرئيسية والمتجر،
    وصفر تقريباً في اللعب والنوافذ المعتمة."""
    a = load(img)
    H = a.shape[0]
    band = _i16(a[int(0.935 * H):int(0.99 * H)])
    R, G, B = band[..., 0], band[..., 1], band[..., 2]
    return float(((B > 120) & (R > 60) & (G < 110) & (B - G > 60)).mean())


def is_home(img) -> bool:
    """الواجهة الرئيسية: شريط التبويبات ظاهر وزرّ «Level N» الرئيسي في أسفل الشاشة."""
    a = load(img)
    if tabbar_fraction(a) < 0.5:
        return False
    b = main_button(a)
    return b is not None and b[1] > 0.7 * a.shape[0]


def classify(img) -> str:
    """level: شاشة اللغز (شريط الأدوات ظاهر بلا تعتيم).
    button: فعلها الأساسي زرّ رئيسي واحد (Level N، Continue، Claim، Hard Level،
            أو CONTINUE الرمادي في نافذة شروط الخدمة عند أول تشغيل).
    lives: نافذة «More Lives» (find_lives_popup): لها سياسة خاصة في السائق (ملء بالعملات أو إغلاق وانتظار)، لا
           إغلاق متكرّر بزرّ X.
    close: فيها X وليس فيها زرّ رئيسي (نوافذ الميزات، الإعدادات، الملف، الرحلة...).
    unknown: غير ذلك (تحميل، متجر، شاشة Android، احتفال الفوز...).
    ملاحظة للسائق: نافذة الفوز تظهر أولاً بلا زرّ Continue ثانية تقريباً، فإن جاء
    "close" بعد فوز مباشرة فانتظر وأعد التصوير قبل ضغط X."""
    a = load(img)
    if booster_bar(a):
        return "level"
    if main_button(a) is not None:
        return "button"
    if find_close(a) is not None:
        return "lives" if find_lives_popup(a) is not None else "close"
    return "unknown"


# ---------------------------------------------------------------- رقم المرحلة
# قوالب الأرقام (12×16، كل سطر 3 خانات ست عشرية) من عناوين المراحل 5..14 في لقطات
# الجلسة السابقة؛ الرقم 1 يُعرف بنسبته (ضيّق).
_DIGITS = {
    '0': '0701f83fe7fef9ff8ff0ff0ff0ff0ff0ff9f7fe7fe3fc0f8',
    '2': '0e07f8ffcffefbe31e03e03e0fc1f83f07e0fffffffffffe',
    '3': '0f03fc7feffff0f10f01f0fe0fe0bf00f30ff9ffff7fe3fc',
    '4': '07e0fe0fe1fe1fe3fe79e79ef9ef9efffffffff03e01e01a',
    '5': '7fe7fe7fe7fe7807f07fc7fe7fe01f10ff9fffe7fe3fc0f0',
    '6': '0603fc7fe7fef90f00f70ffcffef1ef0ff0ff9e7fe7fe1f8',
    '7': 'ffffffffffff03f03e03e03e07c07c0780f80f81f01f0160',
    '8': '0e03fc7fef9ff0ff0f79e3fc7fef9ff0ff0ff9ffff7fe3fc',
    '9': '0e07f8ffcfbef1ee1ef1ef3ffff7fe01e01e73effc7f83f0',
}
_TW, _TH = 12, 16
_DIGIT_T = {d: np.array([[int(b) for b in format(int(h[i:i + 3], 16), "012b")]
                         for i in range(0, len(h), 3)], dtype=np.uint8)
            for d, h in _DIGITS.items()}
_SHIFT_COST = 4      # كلفة إزاحة الرمز بكسلاً واحداً قبل مقارنته بالقالب


_DIGIT_STATS = deque(maxlen=200)   # (أقل مسافة، الفارق عن الثاني) لآخر الأرقام المقروءة، للتشخيص


def _white_text(sub):
    s = _i16(sub)
    R, G, B = s[..., 0], s[..., 1], s[..., 2]
    return (R > 200) & (G > 185) & (B > 140) & (R - B < 100)


def _dark_text(sub):
    """نصّ بنّي داكن على كريمي (حبّة العملات، عدّاد الروح القادمة)."""
    s = _i16(sub)
    R, G, B = s[..., 0], s[..., 1], s[..., 2]
    return (R < 150) & (G < 120) & (B < 100) & (R - B > 5)


def _digit_dists(g):
    """مسافات الرمز g (ثنائي _TH×_TW) إلى قوالب الأرقام مرتّبة [(مسافة، رقم)]: الأدنى بين المطابقة المباشرة والمطابقة
    بعد إزاحة بكسل واحد في أي اتجاه + _SHIFT_COST. حدّ الرمز يختلف بين اللقطات بنصف بكسل فيتغيّر عمود كامل بعد التصغير
    («9» في «Level 90» و«Level 99» كانت أقرب إلى «3» فلم يُقرأ عنوان المرحلة 99 ساعات)، والكلفة تمنع «8» أن تُقرأ «5»
    مزاحة. جُرّبت على 224 عنواناً وزرّاً من خمسة تشغيلات: كلها صحيحة (كانت «Level 49» تُقرأ 43)."""
    H, W = g.shape
    shifts = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                s = np.zeros_like(g)
                s[max(0, dy):H + min(0, dy), max(0, dx):W + min(0, dx)] = \
                    g[max(0, -dy):H - max(0, dy), max(0, -dx):W - max(0, dx)]
                shifts.append(s)
    out = []
    for d, T in _DIGIT_T.items():
        e = int((g != T).sum())
        sh = min(int((s != T).sum()) for s in shifts)
        out.append((min(e, sh + _SHIFT_COST), d))
    out.sort()
    return out


def _glyph_digit(mask, c):
    """رقم المكوّن c (من _components) في القناع، أو None إن لم يُتأكد منه. الضيّق (العرض أقل من 0.62 من الارتفاع) «1»."""
    bw, bh = c["x1"] - c["x0"] + 1, c["y1"] - c["y0"] + 1
    if bw / float(bh) < 0.62:
        return "1"
    crop = mask[c["y0"]:c["y1"] + 1, c["x0"]:c["x1"] + 1].astype(np.uint8) * 255
    g = (np.asarray(Image.fromarray(crop).resize((_TW, _TH), Image.BILINEAR)) >= 128).astype(np.uint8)
    dist = _digit_dists(g)
    (d0, best), (d1, _) = dist[0], dist[1]
    _DIGIT_STATS.append((d0, d1 - d0))
    if d0 > 0.25 * _TW * _TH or d1 - d0 < 5:
        return None          # غير متأكد: الأفضل لا رقم على رقم خاطئ
    return best


def _read_digit_row(mask, min_h=8):
    """أرقام سطر واحد في قناع ثنائي: المكوّنات التي ارتفاعها قريب من وسيطها وعلى خطّ قاعدة واحد، من اليسار (تُهمل نقطتا
    «:» وحافة الحبّة وظلّها). يعيد نصّ الأرقام، أو None إن لم توجد أو لم يُتأكد من رقم منها."""
    comps = [c for c in _components(mask) if c["n"] >= 6 and c["y1"] - c["y0"] + 1 >= min_h]
    if not comps:
        return None
    hs = sorted(c["y1"] - c["y0"] + 1 for c in comps)
    hm = hs[len(hs) // 2]
    gl = [c for c in comps if 0.8 * hm <= c["y1"] - c["y0"] + 1 <= 1.25 * hm]
    if not gl:
        return None
    yb = float(np.median([c["y1"] for c in gl]))
    gl = sorted([c for c in gl if abs(c["y1"] - yb) <= 0.25 * hm], key=lambda c: c["x0"])
    if not 1 <= len(gl) <= 6:
        return None
    out = ""
    for c in gl:
        d = _glyph_digit(mask, c)
        if d is None:
            return None
        out += d
    return out


def _read_text_number(a, x0, y0, x1, y1):
    """يقرأ «Level N» في منطقة نصّ أبيض: يعيد N أو None (مثل «Levels 1 - 4»)."""
    H, W = a.shape[:2]
    x0, x1 = max(0, int(x0)), min(W, int(x1))
    y0, y1 = max(0, int(y0)), min(H, int(y1))
    if x1 - x0 < 20 or y1 - y0 < 8:
        return None
    wm = _white_text(a[y0:y1, x0:x1])
    comps = [c for c in _components(wm) if c["n"] >= 8]
    if not comps:
        return None
    hmax = max(c["y1"] - c["y0"] + 1 for c in comps)
    if hmax < 8:
        return None
    gl = [c for c in comps if c["y1"] - c["y0"] + 1 >= 0.6 * hmax]
    yb = float(np.median([c["y1"] for c in gl]))
    gl = sorted([c for c in gl if abs(c["y1"] - yb) <= 0.25 * hmax], key=lambda c: c["x0"])
    groups = [[gl[0]]] if gl else []
    for c in gl[1:]:
        if c["x0"] - groups[-1][-1]["x1"] > 0.35 * hmax:
            groups.append([c])
        else:
            groups[-1].append(c)
    if len(groups) != 2 or len(groups[0]) != 5 or not (1 <= len(groups[1]) <= 4):
        return None
    digits = ""
    for c in groups[1]:
        d = _glyph_digit(wm, c)
        if d is None:
            return None          # غير متأكد: الأفضل لا رقم على رقم خاطئ
        digits += d
    n = int(digits)
    return n if n > 0 else None


def level_number(img):
    """رقم المرحلة إن ظهر: عنوان شاشة اللغز، أو زرّ الواجهة الرئيسية (Level N / Hard
    Level N)، أو رأس نافذة الفوز. None إن لم يُقرأ (ومنها «Levels 1 - 4» في التعليم)."""
    a = load(img)
    H, W = a.shape[:2]
    if booster_bar(a):
        return _read_text_number(a, 0.25 * W, 0.15 * H, 0.75 * W, 0.23 * H)
    mb = main_button(a)
    if mb is not None and mb[2] in ("green", "hard"):
        for b in _rect_blobs(green_mask(a) if mb[2] == "green" else hard_btn_mask(a), W, H, 0.004):
            if abs(b["x"] - mb[0]) < 5 and abs(b["y"] - mb[1]) < 5:
                x0b, y0b, x1b, y1b = b["box"]
                n = _read_text_number(a, x0b, y0b, x1b + 1, y1b + 1)
                if n is not None:
                    return n
        # نافذة الفوز: «Level N» في الرأس البنفسجي فوق الزرّ
        if mb[2] == "green" and mb[1] < 0.75 * H:
            return _read_text_number(a, 0.25 * W, 0.22 * H, 0.75 * W, 0.31 * H)
    return None


# ---------------------------------------------------------------- واجهة مجمّعة للسائق
def analyze(img) -> dict:
    """كل ما يحتاجه السائق من لقطة واحدة (تُحمَّل مرة واحدة):
    {"kind": classify، "level": رقم المرحلة أو None،
     ومع level: "state" (parse_level) و"boosters"؛ ومع button: "button"؛ ومع close: "close"}"""
    a = load(img)
    kind = classify(a)
    out = {"kind": kind, "level": level_number(a)}
    if kind == "level":
        out["state"] = parse_level(a)
        out["boosters"] = find_boosters(a)
    elif kind == "button":
        out["button"] = find_button(a)
    elif kind == "close":
        out["close"] = find_close(a)
    return out


def state_key(state):
    """مفتاح قابل للمقارنة لحالتين (للتحقق من استقرار الشاشة بين لقطتين متتاليتين)."""
    return tuple((t["cap"], tuple(t["layers"]), bool(t.get("lifted"))) for t in state.get("tubes", []))


# ---------------------------------------------------------------- الرسم للتشخيص
_SHORT = {"red": "R", "orange": "O", "yellow": "Y", "green": "G", "blue": "B",
          "purple": "P", "pink": "K", "lavender": "L", "brown": "N", "cyan": "C", "?": "?"}


def debug_draw(img, state=None, scale: float = 1.6):
    a = load(img)
    if state is None:
        state = parse_level(a)
    im = Image.fromarray(a).convert("RGB")
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    s = scale
    for i, t in enumerate(state.get("tubes", [])):
        bx = t.get("box")
        col = (255, 60, 60) if t.get("lifted") else ((255, 200, 0) if t.get("tall") else (0, 255, 120))
        if bx:
            d.rectangle([bx[0] * s, bx[1] * s, bx[2] * s, bx[3] * s], outline=col, width=2)
        tb = t.get("tag_box")
        if tb:                                  # بطاقة «Tag!» ولونها المقبول
            d.rectangle([tb[0] * s, tb[1] * s, tb[2] * s, tb[3] * s], outline=(255, 160, 220), width=1)
            d.text((tb[0] * s, tb[3] * s + 2), "=" + str(t.get("accept"))[:8], fill=(255, 160, 220))
        x, y = t["x"] * s, t["y"] * s
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 0, 255), outline=(255, 255, 255))
        h = t.get("_h")
        lab = "%d c%d" % (i, t["cap"])
        if bx:
            d.text((bx[0] * s + 2, bx[1] * s - 12), lab, fill=(255, 255, 255))
        if h and t.get("layers"):
            if "_B" not in t and t.get("_ytop") is not None:
                fill = (t["_ytop"] + t["_e"])
                for j, name in enumerate(reversed(t["layers"])):
                    yc = fill + (j + 0.5) * h
                    d.text((t["x"] * s - 20, yc * s - 6), name[:6], fill=(255, 255, 255))
            elif "_B" in t:
                for k, name in enumerate(t["layers"]):
                    yc = t["_B"] - (k + 0.5) * h
                    d.text((t["x"] * s - 20, yc * s - 6), name[:6], fill=(255, 255, 255))
                    d.line([(bx[0] * s, (t["_B"] - (k + 1) * h) * s),
                            (bx[0] * s + 8, (t["_B"] - (k + 1) * h) * s)], fill=(255, 255, 255))
    y = 4
    for wmsg in state.get("warnings", [])[:8]:
        d.text((4, y), "! " + wmsg, fill=(255, 80, 80))
        y += 12
    return im


def summarize(state) -> str:
    """نص قصير للحالة: كل قارورة بأحرف ألوانها من الأسفل."""
    parts = []
    for t in state.get("tubes", []):
        s = "".join(_SHORT.get(c, "*") for c in t["layers"]) or "-"
        tag = "{%s}" % _SHORT.get(t["accept"], "*") if t.get("accept") else ""    # قارورة موسومة («Tag!»): لونها المقبول
        parts.append("%s/%d%s%s" % (s, t["cap"], tag, "^" if t.get("lifted") else ""))
    return " ".join(parts)


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        st = parse_level(p)
        print(p, classify(p), summarize(st), st.get("warnings", ""))
