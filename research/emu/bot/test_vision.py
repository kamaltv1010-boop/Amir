# -*- coding: utf-8 -*-
"""اختبارات انحدار لرؤية بوت Magic Sort على لقطات حقيقية من الجلسة السابقة (المراحل 1..14).

التشغيل:  python3 test_vision.py        (يطبع دقة كل صورة ويفشل إن اختلف شيء)
     أو:  python3 -m pytest -q test_vision.py

الصور في testdata/ بمقاس 473×1000 (كما يصغّرها البوت). القيم المتوقعة رُوجعت بالعين
على صور التشخيص (debug_draw). للقارورة الطويلة يُختبر «الفراغ» (cap - عدد الطبقات)
بدقة لأنه ما يحتاجه الحلّال، وعدد الطبقات المرئية نفسه تقدير (الحامل يخفي القاع).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vision  # noqa: E402

DATA = os.path.join(HERE, "testdata")
TOL = 8  # سماحية نقطة النقر بالبكسل (ارتفاع 1000)

# (x, y, cap, "طبقات من الأسفل", {خيارات})
LEVELS = {
    "L041_clay_full": [  # طين أمام قاع قوارير فيها سائل (يستمرّ خلفه)؛ السائل الخزامي يشبه لون الزجاج
        (40, 374, 4, 'purple purple purple', {"clay": True}),
        (118, 374, 4, 'yellow yellow yellow', {"clay": True}),
        (196, 374, 4, 'blue blue'),
        (274, 374, 4, '? pink pink'),
        (352, 374, 4, 'lavender lavender', {"clay": True}),
        (431, 374, 4, 'green green', {"clay": True}),
        (40, 636, 4, 'blue orange pink'),
        (118, 636, 4, 'green brown lavender lavender'),
        (196, 636, 4, '? orange'),
        (274, 636, 4, '? red red red'),
        (353, 636, 4, 'red yellow blue green'),
        (431, 636, 4, 'brown orange brown orange'),
    ],
    "L040_clay": [  # «الطين» (المرحلة 40): أربع قوارير فارغة بشظايا طين في قاعها تخفي حافة القاع
        (66, 392, 4, 'pink blue lavender blue'),
        (134, 392, 4, 'orange green green green'),
        (202, 392, 4, '', {"clay": True}),
        (270, 392, 4, '', {"clay": True}),
        (338, 392, 4, 'orange pink purple'),
        (406, 392, 4, 'lavender yellow blue orange'),
        (32, 618, 4, 'blue pink lavender'),
        (100, 618, 4, 'yellow lavender purple purple'),
        (168, 618, 4, '', {"clay": True}),
        (236, 618, 4, '', {"clay": True}),
        (304, 618, 4, 'red purple pink'),
        (372, 618, 4, 'green yellow orange yellow'),
        (440, 618, 4, 'red red red'),
    ],
    "L017_cyan": [  # لون سماوي جديد يشبه الزجاج، وقارورتان عملاقتان (سعة 17) على طرفي ثلاثة صفوف
        (65, 521, 17, 'yellow', {"tall": True, "free": 1}),
        (134, 336, 4, '? yellow blue blue'),
        (202, 334, 4, ''),
        (270, 335, 4, ''),
        (338, 336, 4, 'orange orange orange orange'),
        (406, 523, 17, 'lavender', {"tall": True, "free": 1}),
        (134, 540, 4, 'green green green'),
        (202, 540, 4, 'brown brown'),
        (270, 541, 4, 'pink pink pink pink'),
        (338, 541, 4, 'green lavender brown red'),
        (134, 746, 4, 'purple purple purple purple'),
        (202, 744, 4, '? blue'),
        (270, 746, 4, 'cyan cyan cyan'),
        (338, 746, 4, '? brown red red'),
    ],
    "L016_3rows": [  # ثلاثة صفوف وقارورة عملاقة (سعة 16) في الوسط؛ شريط الأدوات أوطأ (0.92)
        (100, 334, 4, 'red yellow blue green'),
        (168, 334, 4, 'purple orange orange purple'),
        (236, 522, 17, 'purple purple purple purple', {"tall": True, "free": 13}),  # سعة العملاقة بثلاثة صفوف 17 (كما في L017)
        (304, 335, 4, 'purple pink red orange'),
        (372, 334, 4, 'purple blue yellow lavender'),
        (100, 539, 4, 'green purple green yellow'),
        (168, 539, 4, 'green purple purple purple'),
        (304, 539, 4, 'lavender lavender lavender purple'),
        (372, 539, 4, 'blue purple pink pink'),
        (168, 744, 4, 'pink red purple yellow'),
        (304, 744, 4, 'purple orange red blue'),
    ],
    "L015_brown": [  # لون جديد (بنّي) من المرحلة 15
        (40, 375, 4, 'red yellow blue yellow'),
        (118, 375, 4, 'green green purple purple'),
        (196, 375, 4, ''),
        (274, 375, 4, ''),
        (353, 375, 4, 'orange pink blue green'),
        (431, 374, 4, 'lavender orange green lavender'),
        (79, 636, 4, 'purple ? ? red'),
        (157, 636, 4, 'yellow ? ? blue'),
        (236, 636, 4, 'brown ? ? orange'),
        (314, 636, 4, 'pink ? ? blue'),
        (392, 636, 4, 'brown ? ? pink'),
    ],
    "001_end": [  # التعليم: يد بيضاء تغطي قاع القارورة اليسرى
        (179, 506, 4, 'red red red'),
        (292, 506, 4, 'red'),
    ],
    "002_after3s": [
        (146, 506, 4, 'red red'),
        (236, 506, 4, 'red red yellow yellow'),
        (326, 506, 4, 'yellow yellow'),
    ],
    "002_picked": [  # قارورة مرفوعة + اليد فوق القارورة اليمنى (طبقتها قد تُقرأ "?")
        (179, 468, 4, 'red red red', {"lifted": True}),
        (292, 505, 4, 'red', {"alt": ['?']}),
    ],
    "003_a_pick": [  # مرفوعة + علامتا ✔/✖ فوق القوارير
        (146, 506, 4, 'red red'),
        (236, 468, 4, 'red red yellow yellow', {"lifted": True}),
        (326, 506, 4, 'yellow yellow'),
    ],
    "004_c_3s": [
        (78, 506, 4, 'red yellow blue yellow'),
        (157, 506, 4, 'red red blue blue'),
        (236, 506, 4, 'red yellow blue yellow'),
        (314, 506, 4, ''),
        (393, 506, 4, ''),
    ],
    "010_a_level5": [
        (45, 506, 4, 'red yellow blue red'),
        (121, 506, 4, 'red blue red blue'),
        (198, 506, 4, 'green blue green yellow'),
        (274, 506, 4, 'green green yellow yellow'),
        (350, 506, 4, ''),
        (426, 506, 4, ''),
    ],
    "012_b_level6": [
        (112, 375, 4, 'red yellow blue yellow'),
        (194, 375, 4, 'red blue red red'),
        (277, 375, 4, 'blue yellow green blue'),
        (360, 375, 4, 'purple yellow green green'),
        (145, 636, 4, 'green purple purple purple'),
        (236, 636, 4, ''),
        (326, 636, 4, ''),
    ],
    "016_b_solved": [
        (112, 375, 4, 'red yellow blue'),
        (194, 375, 4, 'yellow green blue yellow'),
        (277, 374, 4, 'red'),
        (360, 375, 4, 'blue green blue'),
        (146, 636, 4, 'red purple red yellow'),
        (236, 636, 4, 'green green'),
        (326, 636, 4, 'purple purple purple'),
    ],
    "019_a_pick_hidden": [  # طبقات مخفية + قارورة مرفوعة في الصف الثاني
        (112, 375, 4, 'red yellow yellow blue'),
        (194, 375, 4, 'green purple yellow blue'),
        (277, 375, 4, 'green green orange red'),
        (360, 375, 4, 'orange purple blue yellow'),
        (112, 598, 4, '? ? ? purple', {"lifted": True}),
        (194, 636, 4, '? ? ? purple'),
        (276, 636, 4, ''),
        (360, 636, 4, ''),
    ],
    "022_a_state": [
        (112, 375, 4, 'red yellow yellow blue'),
        (194, 375, 4, 'green purple yellow blue'),
        (277, 375, 4, 'green green green'),
        (360, 375, 4, 'orange purple blue yellow'),
        (112, 636, 4, '? red red red'),
        (194, 636, 4, 'blue'),
        (277, 636, 4, 'purple purple'),
        (360, 636, 4, 'orange orange'),
    ],
    "024_b_level8": [
        (112, 374, 4, '? ? ? red'),
        (194, 375, 4, '? ? ? blue'),
        (277, 374, 4, '? ? ? purple'),
        (360, 374, 4, '? ? ? yellow'),
        (112, 636, 4, 'yellow yellow green green'),
        (194, 636, 4, 'orange orange orange blue'),
        (276, 636, 4, ''),
        (360, 636, 4, ''),
    ],
    "028_a_state": [  # قوارير مكتملة بسدادات ذهبية
        (112, 375, 4, 'purple'),
        (194, 375, 4, 'green green green'),
        (277, 374, 4, '? ? purple'),
        (360, 374, 4, '? blue'),
        (112, 638, 4, 'yellow yellow yellow yellow'),
        (194, 638, 4, 'orange orange orange orange'),
        (276, 636, 4, 'blue blue blue'),
        (360, 638, 4, 'red red red red'),
    ],
    "030_c_level9": [  # المخفي في الوسط والقاع ظاهر
        (112, 375, 4, 'red ? ? yellow'),
        (194, 375, 4, 'green ? ? green'),
        (277, 375, 4, 'yellow ? ? orange'),
        (360, 375, 4, 'blue ? ? red'),
        (112, 636, 4, 'purple ? ? orange'),
        (194, 636, 4, 'purple ? ? green'),
        (276, 636, 4, ''),
        (360, 636, 4, ''),
    ],
    "036_a_state": [
        (112, 375, 4, 'red red'),
        (194, 375, 4, 'orange orange'),
        (277, 375, 4, 'yellow ? orange'),
        (360, 376, 4, 'blue blue blue blue'),
        (112, 636, 4, 'purple ? red'),
        (194, 636, 4, 'purple purple purple'),
        (276, 638, 4, 'green green green green'),
        (360, 636, 4, 'yellow yellow yellow'),
    ],
    "040_a_level10": [  # القارورة الطويلة في الوسط: تحتاج 8 بنفسجيات
        (79, 380, 4, 'red yellow red yellow'),
        (157, 380, 4, 'blue green red purple'),
        (236, 486, 11, 'purple purple purple', {"tall": True, "free": 8}),
        (314, 380, 4, 'orange orange purple orange'),
        (392, 380, 4, 'green purple blue pink'),
        (79, 640, 4, 'blue red yellow purple'),
        (157, 640, 4, 'blue purple green pink'),
        (314, 640, 4, 'purple pink orange purple'),
        (392, 640, 4, 'pink purple yellow green'),
    ],
    "042_b_level11": [  # قارورتان طويلتان على الطرفين: كل واحدة تحتاج 6
        (40, 497, 10, 'orange orange orange orange', {"tall": True, "free": 6}),
        (118, 374, 4, 'red yellow blue green'),
        (196, 374, 4, 'yellow purple yellow orange'),
        (274, 375, 4, 'yellow blue orange pink'),
        (353, 375, 4, 'pink red red purple'),
        (431, 498, 10, 'yellow yellow yellow yellow', {"tall": True, "free": 6}),
        (118, 636, 4, 'green green blue orange'),
        (196, 636, 4, 'purple pink pink green'),
        (274, 636, 4, 'orange yellow yellow orange'),
        (354, 636, 4, 'orange purple blue red'),
    ],
    "044_b_level12": [
        (40, 500, 10, 'blue blue blue blue', {"tall": True, "free": 6}),
        (118, 374, 4, 'red yellow blue green'),
        (196, 375, 4, 'purple yellow red orange'),
        (274, 375, 4, 'blue orange pink pink'),
        (353, 375, 4, 'yellow yellow lavender purple'),
        (431, 375, 4, 'blue orange pink lavender'),
        (118, 636, 4, '? ? ? green'),
        (197, 636, 4, '? ? red'),
        (274, 636, 4, ''),
        (353, 636, 4, '? ? purple'),
        (431, 636, 4, '? ? ? blue'),
    ],
    "049_a_state": [  # بقيت زرقاوان: الفراغ 2
        (40, 500, 10, 'blue blue blue blue blue blue blue blue', {"tall": True, "free": 2}),
        (118, 375, 4, 'red red red red'),
        (196, 376, 4, 'purple purple purple purple'),
        (274, 375, 4, ''),
        (353, 376, 4, 'yellow yellow yellow yellow'),
        (431, 375, 4, 'blue orange orange orange'),
        (118, 637, 4, 'lavender lavender lavender lavender'),
        (196, 636, 4, 'orange'),
        (275, 636, 4, 'green green green'),
        (353, 637, 4, 'pink pink pink pink'),
        (431, 636, 4, '? blue'),
    ],
    "050_c_level13": [  # قارورتان طويلتان في الوسط تمتدّان على الصفين
        (40, 375, 4, 'red ? ? green'),
        (118, 374, 4, 'yellow ? ? blue'),
        (196, 500, 10, 'green green green green green green', {"tall": True, "free": 4}),
        (274, 498, 10, 'purple purple purple purple purple purple', {"tall": True, "free": 4}),
        (353, 375, 4, 'purple ? ? green'),
        (431, 375, 4, 'blue ? ? orange'),
        (40, 636, 4, 'lavender orange pink yellow'),
        (118, 636, 4, 'lavender purple yellow purple'),
        (354, 636, 4, 'red pink lavender green'),
        (431, 636, 4, 'orange pink purple red'),
    ],
    "055_a_state": [
        (40, 375, 4, 'red yellow'),
        (118, 374, 4, 'yellow ? green'),
        (196, 500, 10, 'green green green green green green green green green', {"tall": True, "free": 1}),
        (274, 498, 10, 'purple purple purple purple purple purple purple', {"tall": True, "free": 3}),
        (353, 375, 4, 'purple orange orange'),
        (431, 376, 4, 'blue blue blue blue'),
        (40, 636, 4, 'lavender orange pink pink'),
        (118, 636, 4, 'lavender purple yellow yellow'),
        (354, 636, 4, 'red pink lavender lavender'),
        (431, 636, 4, 'orange pink purple red'),
    ],
    "056_c_level14": [  # مرحلة HARD: القارورة الطويلة يمين الصف الأعلى تحتاج 7
        (40, 380, 4, '? ? ? green'),
        (118, 380, 4, '? ? ? blue'),
        (196, 380, 4, '? ? ? yellow'),
        (274, 380, 4, '? ? ? red'),
        (353, 380, 4, '? ? ? lavender'),
        (431, 490, 11, 'blue blue blue blue', {"tall": True, "free": 7}),
        (40, 640, 4, 'blue blue orange'),
        (118, 640, 4, 'purple pink pink'),
        (196, 640, 4, 'green orange lavender'),
        (274, 640, 4, 'orange green pink'),
        (353, 640, 4, 'green lavender red'),
    ],
    "058_end": [  # بعد «قارورة إضافية»: تخطيط مضغوط (عرض 56 بدل 64) + قارورة فارغة جديدة
        (32, 394, 4, '? ? ? green'),
        (100, 394, 4, '? ? ? blue'),
        (169, 395, 4, '? ? ? yellow'),
        (238, 394, 4, '? ? ? red'),
        (306, 395, 4, '? ? ? lavender'),
        (374, 490, 11, 'blue blue blue blue', {"tall": True, "free": 7}),
        (32, 623, 4, 'blue blue orange'),
        (100, 623, 4, 'purple pink pink'),
        (169, 623, 4, 'green orange lavender'),
        (238, 623, 4, 'orange green pink'),
        (306, 623, 4, 'green lavender red'),
        (440, 623, 4, ''),
    ],
}

# لقطات تعليم فيها اليد: تحذير «occluded» مقبول
ALLOW_WARN = {"001_end", "002_picked"}

# (التصنيف، نقطة find_button أو None، نقطة find_close أو None) — None في النقطة = لا يُختبر
SCREENS = {
    "home_superhard": ("button", (236, 786), None),     # الواجهة: «Super Hard Level 19» الأحمر (×5)
    "home_portal40": ("button", (236, 786), None),      # واجهة الحلقة 40: بوّابة خضراء متوهّجة فوق زرّ «Level 40»
    "nomoves_popup": ("unknown", None, None),           # «No Available Moves»: Play On (900) وGive Up (find_give_up)
    "continue_paid": ("close", None, (428, 215)),       # «Continue?» بعد Give Up: «Play On 900» يصرف العملات، فيُغلق بـ X
    "strike_board_row": ("close", None, None),          # لوحة Strike Show: صفّ اللاعب الأخضر بعرض الشاشة ليس زرّاً
    "ad_install": ("unknown", None, None),              # إعلان بملء الشاشة بعد مرحلة (is_ad): رجوع ثم زاويتا الإغلاق
    "tos_3536": ("button", (236, 660), None),           # شروط الخدمة في النسخة 0.0.3536 (لوحة 36 وزرّ 73)
    "L016_3rows": ("level", None, None),                # شريط الأدوات عند 0.92 (ثلاثة صفوف)
    "nonet_popup": ("button", (236, 630), None),        # «No internet connection» وزرّ Retry
    "loading_splash": ("unknown", None, None),          # شاشة التحميل (النسخة 0.0.3536)
    "000_launch_120s": ("button", (236, 660), None),   # شروط الخدمة: CONTINUE رمادي
    "000_launch_10s": ("unknown", None, None),          # شاشة سوداء أثناء التحميل
    "005_d_3s": ("unknown", None, None),                # ألعاب نارية بعد الفوز
    "030_a_win": ("button", (236, 652), (415, 272)),    # نافذة الفوز: Continue (وفيها X)
    "017_b_4s": ("close", None, (415, 272)),            # نافذة الفوز قبل ظهور Continue
    "030_b_home": ("button", (236, 786), None),         # الواجهة: Level 9 الأخضر
    "056_b_home": ("button", (236, 789), None),         # الواجهة: Hard Level 14 البنفسجي
    "008_a_settings": ("close", None, (402, 85)),       # الإعدادات: فيها Support أخضر لكنها close
    "009_b_profile": ("close", None, (402, 85)),
    "038_b_home": ("close", None, (408, 96)),           # الرحلة Journey
    "039_a_level10": ("close", None, (418, 110)),       # نافذة ميزة جديدة Giant Bottle
    "007_a_shop": ("unknown", None, None),              # المتجر: أزرار أسعار خضراء (لا تُضغط)
    "013_a_solved": ("unknown", None, None),            # شاشة Android (انهارت اللعبة)
    "014_a_relaunch_25s": ("unknown", None, None),      # شاشة التحميل
    "057_b_shuffle_1s": ("unknown", None, None),        # وضع اختيار الخلط (معتم)
}


# رقم المرحلة المتوقع (None = لا يُقرأ، مثل «Levels 1 - 4» أو شاشات بلا رقم)
LEVEL_NUMBERS = {
    "010_a_level5": 5, "012_b_level6": 6, "019_a_pick_hidden": 7, "024_b_level8": 8,
    "030_c_level9": 9, "040_a_level10": 10, "042_b_level11": 11, "044_b_level12": 12,
    "050_c_level13": 13, "056_c_level14": 14, "058_end": 14,
    "030_b_home": 9, "056_b_home": 14, "030_a_win": 8,
    "001_end": None, "002_after3s": None, "008_a_settings": None, "007_a_shop": None,
}


def _path(name):
    return os.path.join(DATA, name + ".jpg")


def _near(p, q, tol=TOL):
    return p is not None and q is not None and abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


def check_level(name):
    """يعيد (عدد القوارير الصحيحة، المتوقع، الطبقات الصحيحة، كل الطبقات، أخطاء)."""
    exp = LEVELS[name]
    st = vision.parse_level(_path(name))
    got = st["tubes"]
    errs = []
    if vision.classify(_path(name)) != "level":
        errs.append("classify != level")
    warns = st.get("warnings", [])
    if warns and not (name in ALLOW_WARN and all(w.startswith(("occluded", "hidden top")) for w in warns)):
        errs.append("warnings: %s" % warns)
    if len(got) != len(exp):
        errs.append("tube count %d != %d" % (len(got), len(exp)))
    ok_t = ok_l = tot_l = 0
    for i, e in enumerate(exp):
        x, y, cap, layers = e[:4]
        opt = e[4] if len(e) > 4 else {}
        layers = layers.split()
        tot_l += max(1, len(layers))
        if i >= len(got):
            continue
        t = got[i]
        good = True
        if not _near((t["x"], t["y"]), (x, y)):
            errs.append("tube %d tap %s != %s" % (i, (t["x"], t["y"]), (x, y)))
            good = False
        if bool(t.get("tall")) != bool(opt.get("tall")):
            errs.append("tube %d tall=%s" % (i, t.get("tall")))
            good = False
        if bool(t.get("lifted")) != bool(opt.get("lifted")):
            errs.append("tube %d lifted=%s" % (i, t.get("lifted")))
            good = False
        if bool(t.get("clay")) != bool(opt.get("clay")):
            errs.append("tube %d clay=%s" % (i, t.get("clay")))
            good = False
        if opt.get("tall"):
            free = t["cap"] - len(t["layers"])
            if free != opt["free"]:
                errs.append("tall %d free %d != %d" % (i, free, opt["free"]))
                good = False
            if set(t["layers"]) != set(layers):
                errs.append("tall %d color %s != %s" % (i, set(t["layers"]), set(layers)))
                good = False
            if t["layers"] == layers and t["cap"] == cap:
                ok_l += max(1, len(layers))
            elif set(t["layers"]) == set(layers) and free == opt["free"]:
                ok_l += max(1, len(layers))   # الفراغ واللون صحيحان (العدد المرئي تقدير)
        else:
            if t["cap"] != cap:
                errs.append("tube %d cap %d != %d" % (i, t["cap"], cap))
                good = False
            alts = [layers] + [a.split() if isinstance(a, str) else a for a in opt.get("alt", [])]
            if t["layers"] in alts:
                ok_l += max(1, len(layers))
            else:
                errs.append("tube %d layers %s != %s" % (i, t["layers"], layers))
                good = False
                ok_l += sum(1 for a, b in zip(t["layers"], layers) if a == b)
        ok_t += int(good)
    return ok_t, len(exp), ok_l, tot_l, errs


def check_screen(name):
    cls, btn, cls_pt = SCREENS[name]
    errs = []
    c = vision.classify(_path(name))
    if c != cls:
        errs.append("classify %s != %s" % (c, cls))
    if btn is not None and not _near(vision.find_button(_path(name)), btn):
        errs.append("find_button %s != %s" % (vision.find_button(_path(name)), btn))
    if cls_pt is not None and not _near(vision.find_close(_path(name)), cls_pt):
        errs.append("find_close %s != %s" % (vision.find_close(_path(name)), cls_pt))
    if name == "007_a_shop" and vision.find_button(_path(name)) is not None:
        errs.append("shop: find_button must not return a price button")
    return errs


# ---------------------------------------------------------------- pytest
def test_levels():
    bad = {}
    for name in LEVELS:
        errs = check_level(name)[4]
        if errs:
            bad[name] = errs
    assert not bad, bad


def test_screens():
    bad = {n: e for n in SCREENS for e in [check_screen(n)] if e}
    assert not bad, bad


def test_level_numbers():
    bad = {n: (vision.level_number(_path(n)), e) for n, e in LEVEL_NUMBERS.items()
           if vision.level_number(_path(n)) != e}
    assert not bad, bad


def test_animation_frame_warns():
    st = vision.parse_level(_path("004_b_last_pour"))
    assert st.get("warnings"), "a pouring frame must carry warnings"


def test_palette_consistency():
    """كل عيّنة باسم لون من اللوحة قريبة من مرجعها، وأقرب لونين مختلفين متباعدان."""
    import numpy as np
    for name in LEVELS:
        a = vision.load(_path(name))
        st = vision.parse_level(a)
        for t in st["tubes"]:
            if "_B" not in t:
                continue
            w = t["_h"] / vision.K_LAYER
            for k, c in enumerate(t["layers"]):
                if c == "?" or c not in vision.PALETTE:
                    continue
                rgb = vision._sample(a, t["x"], w, t["_B"] - (k + 0.5) * t["_h"], t["_h"])
                if rgb is None:
                    continue
                d = np.sqrt(((vision._srgb_to_lab(rgb) - vision._srgb_to_lab(np.array(vision.PALETTE[c], float))) ** 2).sum())
                assert d < 10, (name, c, rgb, d)
    labs = vision._PAL_LAB
    dmin = min(float(np.sqrt(((labs[i] - labs[j]) ** 2).sum()))
               for i in range(len(labs)) for j in range(i + 1, len(labs)))
    assert dmin > 20, dmin


def test_tutorial_arrow():
    """سهم التعليم الأصفر الصاعد يشير إلى صورة اللاعب (نحو 55، 74): الهدف فوق قمته على الصورة."""
    pt = vision.find_tutorial_arrow(_path("tutorial_arrow_up"))
    assert pt is not None and abs(pt[0] - 57) <= 12 and 50 <= pt[1] <= 110, pt
    # صفحات التبويب المضيئة (الفرق، المتجر، الواجهة) ليست تعليماً: أزرارها البرتقالية لا تُعدّ أسهماً
    for n in ("teams_page", "007_a_shop", "home_events"):
        assert vision.find_tutorial_arrow(_path(n)) is None, n


def test_give_up_and_booster_badges():
    """«No Available Moves»: يُلمس «Give Up» لا «Play On» (900 عملة)؛ وأداة بلا شارة حمراء نفدت (ثمنها بالعملات)."""
    pt = vision.find_give_up(_path("nomoves_popup"))
    assert pt is not None and abs(pt[0] - 350) <= 15 and abs(pt[1] - 820) <= 15, pt
    for n in SCREENS:
        if n != "nomoves_popup":
            assert vision.find_give_up(_path(n)) is None, n
    for n in LEVELS:
        assert vision.find_give_up(_path(n)) is None, n
    assert vision.booster_free(_path("L041_clay_full")) == [True, True, False]   # القارورة الإضافية: 900 عملة
    assert vision.booster_free(_path("L040_clay")) == [True, True, True]


def test_is_ad():
    """إعلان بملء الشاشة (أسود وزرّ «Install»)؛ لا شاشة لعب ولا تحميل ولا واجهة."""
    assert vision.is_ad(_path("ad_install"))
    for n in list(SCREENS) + list(LEVELS):
        if n != "ad_install":
            assert not vision.is_ad(_path(n)), n


def test_is_home():
    """الواجهة الرئيسية (زرّ «Level N» وشريط التبويبات) لأمر pause_home؛ ونوافذ الأحداث واللعب والمتجر ليست هي."""
    for n in ("home_superhard", "home_events", "056_b_home", "030_b_home", "home_portal40"):
        assert vision.is_home(_path(n)), n
    for n in ("popup_strikeshow", "popup_magicstreak", "L016_3rows", "030_a_win", "007_a_shop", "nonet_popup", "038_b_home"):
        assert not vision.is_home(_path(n)), n


# المرحلة 74 (مفاتيح وأبواب خشبية بأقفال ملوّنة): (x, y, "طبقات من الأسفل", مواضع المفاتيح، ألوانها)؛ القارورة الطويلة
# بلونها وفراغها فقط. رُوجعت بالعين: طبقة المفتاح تُقرأ بلون سائلها (كانت c_05_6_4 وc_03_6_6)، والأخضر الداكن والبرقوقي
# لونان من اللوحة (كانا c_10_7_1/c_11_7_1 وc_31_7_3)، والأبواب ليست قوارير. L074_door_key وL074_buried_key لقطتان أثناء
# انزلاق الشاشة (يصنّفها classify «unknown») لكن القوارير في مواضعها.
KEY_LEVELS = {
    "L074_keys": ([
        (64, 332, 'purple lavender pink cyan'), (133, 332, '? brown yellow yellow'), (201, 332, '? cyan'),
        (270, 332, '? red ? blue', [1], ["green"]), (339, 332, '? pink ? pink'), (407, 332, 'red cyan yellow purple'),
        (64, 538, 'darkgreen red red'), (133, 538, 'blue brown brown brown'),
        (202, 621, 'orange', None, None, 1), (270, 643, 'plum', None, None, 0),
        (338, 537, 'orange blue'), (407, 538, 'green green'),
    ], [(101, 646, 67, 198, "green"), (306, 646, 67, 198, "gold")]),
    "L074_door_key": ([   # باب مزدوج كبير بقفل أزرق يغطي ثلاث خانات أعلى اليمين، ومفتاح ذهبي على طبقة زرقاء
        (64, 331, 'orange blue plum plum', [1], ["gold"]), (134, 332, '? cyan cyan cyan'), (201, 332, '? orange ? blue'),
        (64, 537, 'darkgreen red red lavender'), (133, 537, 'orange darkgreen purple purple'),
        (202, 622, 'pink', None, None, 2), (270, 621, 'green', None, None, 2),
        (338, 537, 'yellow'), (407, 537, 'yellow brown brown'),
    ], [(236, 235, 206, 197, "blue"), (101, 647, 67, 185, "green"), (306, 647, 67, 185, "gold")]),
    "L074_buried_key": ([  # البوت صبّ الأخضر الداكن فوق طبقة المفتاح (دفنه): ما يجب أن يتجنّبه الحلّال
        (64, 331, 'purple lavender'), (133, 332, '? brown yellow yellow'), (201, 332, '? cyan cyan'),
        (270, 332, '? red darkgreen darkgreen', [1], ["green"]), (338, 332, '? pink pink pink'),
        (407, 332, 'red cyan yellow purple'), (64, 537, 'darkgreen red red'), (133, 537, 'blue brown brown brown'),
        (202, 622, 'orange', None, None, 1), (270, 641, 'plum', None, None, 0),
        (339, 537, 'orange blue blue'), (407, 537, 'green green'),
    ], [(101, 647, 67, 185, "green"), (306, 647, 67, 185, "gold")]),
    "L064_key_doors": ([   # المرحلة 64: بابان (أزرق يغطي أربع خانات وذهبي خانتين) والمفتاح الأزرق على بني تحت بني وأصفر
        (40, 636, 'brown lavender lavender lavender'), (118, 636, 'brown brown yellow', [0], ["blue"]),
        (196, 636, 'cyan cyan cyan'), (274, 636, 'green green'), (353, 636, 'red pink pink pink'), (431, 636, ''),
    ], [(0, 264, 315, 226, "blue"), (317, 264, 153, 226, "gold")]),
    "L061_key_flying": ([  # المرحلة 61: المفتاح الوردي يطير من قارورة بقيت فيها طبقته وحدها (كُشفت ولم تُصبّ)
        (40, 375, 'yellow'), (118, 376, 'green green green green'), (196, 376, 'pink'), (275, 375, 'lavender red'),
        (353, 358, 'purple purple purple purple'), (431, 376, 'orange orange orange orange'),
    ], [(39, 526, 395, 225, "pink")]),
}


def test_keys_and_doors():
    """طبقات المفاتيح بلونها الحقيقي ومواضعها، وأبواب الخشب بألوان أقفالها، ولا قوارير وهمية على الأبواب."""
    bad = {}
    for name, (tubes, doors) in KEY_LEVELS.items():
        st = vision.parse_level(_path(name))
        got, errs = st["tubes"], []
        if len(got) != len(tubes):
            errs.append("tube count %d != %d" % (len(got), len(tubes)))
        for i, (e, t) in enumerate(zip(tubes, got)):
            x, y, layers = e[0], e[1], e[2].split()
            keys = e[3] if len(e) > 3 and e[3] is not None else []
            kcol = e[4] if len(e) > 4 and e[4] is not None else []
            if not _near((t["x"], t["y"]), (x, y)):
                errs.append("tube %d tap %s != %s" % (i, (t["x"], t["y"]), (x, y)))
            if len(e) > 5:                      # طويلة: اللون والفراغ
                if not t.get("tall") or set(t["layers"]) != set(layers) or t["cap"] - len(t["layers"]) != e[5]:
                    errs.append("tall %d %s/%d" % (i, t["layers"], t["cap"]))
            elif t["layers"] != layers:
                errs.append("tube %d layers %s != %s" % (i, t["layers"], layers))
            if t.get("keys", []) != keys or t.get("key_colors", []) != kcol:
                errs.append("tube %d keys %s %s != %s %s" % (i, t.get("keys"), t.get("key_colors"), keys, kcol))
        gd = [(d["x"], d["y"], d["w"], d["h"], d["color"]) for d in st.get("doors", [])]
        if len(gd) != len(doors) or any(abs(a[k] - b[k]) > 8 for a, b in zip(gd, doors) for k in range(4)) \
                or [d[4] for d in gd] != [d[4] for d in doors]:
            errs.append("doors %s != %s" % (gd, doors))
        if any(w.startswith("unknown color") for w in st.get("warnings", [])):
            errs.append("unknown colors: %s" % st["warnings"])
        if errs:
            bad[name] = errs
    assert not bad, bad
    # ولا مفاتيح ولا أبواب في لقطات المراحل القديمة (لا إيجابيات كاذبة)
    for name in LEVELS:
        st = vision.parse_level(_path(name))
        assert not st.get("doors"), (name, st.get("doors"))
        assert not any(t.get("keys") for t in st["tubes"]), name


def test_device_mapping():
    assert vision.to_device(236, 500) == (538, 1140)


# ---------------------------------------------------------------- التشغيل السابع (المرحلة 99) — unittest أيضاً
import unittest  # noqa: E402

# لقطات حقيقية من التشغيلين السادس والسابع (انظر أسماءها): عناوين عادية وصعبة وصعبة جداً، ونافذتا «More Lives» و«No
# Available Moves»، وستائر وأكياس تغطي قوارير. كل لقطات LEVELS وKEY_LEVELS وSCREENS القديمة بلا شيء من هذا.
RUN7_LEVEL_NUMBERS = {"L089_superhard": 89, "L090_bags": 90, "L091_curtains": 91, "L094_hard_covers": 94,
                      "L099_superhard_doors": 99, "L099_bag_keys_mint": 99}
RUN7_BADGES = {"L089_superhard": "superhard", "L099_superhard_doors": "superhard", "L099_bag_keys_mint": "superhard",
               "L094_hard_covers": "hard", "056_c_level14": "hard", "058_end": "hard",
               "L090_bags": "normal", "L091_curtains": "normal", "010_a_level5": "normal", "050_c_level13": "normal",
               "L074_keys": "hard", "030_b_home": None, "nomoves_playon_1950": None, "lives_refill_ad": None}
RUN7_COINS = {"nomoves_playon_1950": 1950, "lives_refill_ad": 1950, "lives_refill_free": 1950, "nomoves_popup": 1900,
              "continue_paid": 1330, "home_superhard": 1440, "L090_bags": None, "L099_superhard_doors": None,
              "030_a_win": None}
# (رقم القارورة، x، y، النوع، لون أيقونة الستارة)
RUN7_COVERS = {
    "L090_bags": [(0, 99, 331, "bag", None), (2, 236, 331, "bag", None), (4, 374, 331, "bag", None),
                  (5, 99, 537, "bag", None), (9, 374, 537, "bag", None), (11, 236, 743, "bag", None)],
    "L091_curtains": [(0, 100, 320, "curtain", "red"), (1, 168, 320, "curtain", "orange"), (2, 236, 320, "curtain", "brown"),
                      (3, 304, 320, "curtain", "orange"), (5, 100, 525, "curtain", "brown"),
                      (9, 100, 730, "curtain", "brown")],
    "L094_hard_covers": [(5, 98, 521, "curtain", "red"), (6, 168, 537, "bag", None), (8, 304, 537, "bag", None),
                         (9, 372, 521, "curtain", "lavender"), (10, 134, 743, "bag", None), (11, 202, 743, "bag", None),
                         (12, 270, 743, "bag", None), (13, 338, 743, "bag", None)],
    "L099_bag_keys_mint": [(8, 236, 743, "bag", None)],
    "L099_curtains_bag": [(0, 103, 315, "curtain", "red"), (4, 378, 315, "curtain", "purple"), (12, 236, 742, "bag", None)],
    "L099_superhard_doors": [],
}
RUN7_TUBES = {"L090_bags": 13, "L091_curtains": 13, "L094_hard_covers": 14, "L099_bag_keys_mint": 11,
              "L099_curtains_bag": 15, "L099_superhard_doors": 6}


def _all_testdata():
    return sorted(os.path.splitext(n)[0] for n in os.listdir(DATA) if n.endswith(".jpg"))


class TestRun7Vision(unittest.TestCase):
    def test_level_numbers_hard_and_superhard(self):
        """عنوان المرحلة يُقرأ في العادية والصعبة (بنفسجي وشريط HARD) والصعبة جداً (أحمر وشريط SUPER HARD): كان «9» يُقرأ
        «3» بإزاحة نصف بكسل فبقي عنوان المرحلة 99 بلا رقم ساعات وانجرف العدّاد."""
        for name, n in RUN7_LEVEL_NUMBERS.items():
            self.assertEqual(vision.level_number(_path(name)), n, name)

    def test_level_badge(self):
        for name, b in RUN7_BADGES.items():
            self.assertEqual(vision.level_badge(_path(name)), b, name)

    def test_read_coins(self):
        for name, n in RUN7_COINS.items():
            self.assertEqual(vision.read_coins(_path(name)), n, name)

    def test_lives_popup(self):
        """«More Lives»: «Refill 900» الأخضر وX، والعدّاد 15:00 و09:16؛ وزرّ الإعلان «+1 Life» أو «Free Lives» تحته لا
        يُعاد أبداً. لا تُعرف في أي لقطة أخرى (و«Continue?» بزرّها الأخضر بالعملات وX ليست هي)."""
        for name, timer in (("lives_refill_ad", 900), ("lives_refill_free", 556)):
            lp = vision.find_lives_popup(_path(name))
            self.assertIsNotNone(lp, name)
            self.assertTrue(_near(lp["refill"], (236, 523)), lp)
            self.assertTrue(_near(lp["close"], (424, 182)), lp)
            self.assertEqual((lp["price"], lp["timer"]), (900, timer), name)
            self.assertEqual(vision.classify(_path(name)), "lives", name)
            self.assertGreater(lp["refill"][1], 0.45 * 1000)      # الأخضر فوق زرّ الإعلان (نحو y=650)
            self.assertLess(lp["refill"][1], 600)
        for name in _all_testdata():
            if not name.startswith("lives_"):
                self.assertIsNone(vision.find_lives_popup(_path(name)), name)
                self.assertNotEqual(vision.classify(_path(name)), "lives", name)

    def test_play_on(self):
        for name in ("nomoves_playon_1950", "nomoves_popup"):
            p = vision.find_play_on(_path(name))
            self.assertIsNotNone(p, name)
            self.assertTrue(_near(p[:2], (124, 820)), p)
            self.assertEqual(p[2], 900, name)
            gu = vision.find_give_up(_path(name))
            self.assertTrue(gu is not None and gu[0] > p[0] + 150, (name, gu))
        for name in _all_testdata():
            if name not in ("nomoves_playon_1950", "nomoves_popup"):
                self.assertIsNone(vision.find_play_on(_path(name)), name)

    def test_covers_are_blocked_tubes(self):
        """الستائر والأكياس قوارير محجوبة في خاناتها بترتيب القراءة (layers فارغة، لا تحذيرات)، ولون أيقونة الستارة."""
        for name, exp in RUN7_COVERS.items():
            st = vision.parse_level(_path(name))
            self.assertEqual(len(st["tubes"]), RUN7_TUBES[name], name)
            got = [(k, t["x"], t["y"], t["cover"], t["cover_color"]) for k, t in enumerate(st["tubes"]) if t.get("blocked")]
            self.assertEqual(len(got), len(exp), (name, got))
            for g, e in zip(got, exp):
                self.assertEqual((g[0], g[3], g[4]), (e[0], e[3], e[4]), (name, got))
                self.assertTrue(_near(g[1:3], e[1:3]), (name, g, e))
            for t in st["tubes"]:
                if t.get("blocked"):
                    self.assertEqual(t["layers"], [], name)
            self.assertFalse(st.get("warnings"), (name, st.get("warnings")))
        for name in list(LEVELS) + list(KEY_LEVELS):
            st = vision.parse_level(_path(name))
            self.assertFalse(any(t.get("blocked") for t in st["tubes"]), name)

    def test_mint_and_full_board_level99(self):
        """السائل النعناعي (1/206/149) لون من اللوحة لا c_16_7_6، ولا يُعدّ زجاجاً (كان يشوّه قوارير المرحلة 99)."""
        st = vision.parse_level(_path("L099_bag_keys_mint"))
        L = [t["layers"] for t in st["tubes"]]
        self.assertEqual(L[0], ["mint", "mint"])
        self.assertEqual(L[4], ["brown", "mint", "brown", "mint"])
        self.assertEqual([k for k, t in enumerate(st["tubes"]) if t.get("keys")], [6, 7])
        self.assertEqual(len(st["doors"]), 2)
        st = vision.parse_level(_path("L099_superhard_doors"))
        self.assertEqual([t["layers"] for t in st["tubes"]],
                         [[], ["blue", "plum", "cyan", "mint"], ["blue", "brown", "mint", "cyan"], [],
                          ["brown", "mint", "brown", "mint"], ["blue", "brown", "purple", "blue"]])
        self.assertFalse(st.get("warnings"))

    def test_legacy_checks(self):
        """اختبارات pytest القديمة في هذا الملف تجري أيضاً مع unittest discover."""
        for fn in (test_levels, test_screens, test_level_numbers, test_animation_frame_warns, test_palette_consistency,
                   test_tutorial_arrow, test_give_up_and_booster_badges, test_is_ad, test_is_home, test_keys_and_doors,
                   test_device_mapping):
            fn()


# ---------------------------------------------------------------- التشغيل التاسع (المراحل 100..110)
# لقطات حقيقية من التشغيل التاسع. الجبس (من المرحلة 100): قالب أبيض متشقّق في خانة قارورة يُقرأ قارورة محجوبة
# {"blocked": True, "cover": "plaster", "layers": []} بترتيب القراءة؛ وقراءات القوارير الظاهرة هي نفسها قبل كشف الجبس (قورنت
# بالكود السابق على 1138 لقطة: لا فرق في أي قارورة غير جبس). جاراته بفتات جبس في قاعدتها تُقرأ "clay" كما كانت.
# (x, y, "plaster") للجبس، و(x, y, السعة، "طبقات من الأسفل"، {خيارات}) للظاهرة، و(x, y, "curtain", لون الأيقونة) للستارة.
PLASTER_LEVELS = {
    "L100_plaster": [
        (40, 375, 4, "orange red blue blue"), (118, 375, 4, "blue blue", {"clay"}), (198, 381, "plaster"),
        (276, 381, "plaster"), (353, 375, 4, "yellow yellow", {"clay"}), (432, 381, "plaster"),
        (42, 642, "plaster"), (118, 637, 4, "red red", {"clay"}), (198, 642, "plaster"), (276, 642, "plaster"),
        (353, 637, 4, "green green", {"clay"}), (431, 636, 4, "orange purple green green"),
    ],
    "L104_plaster_hard": [
        (66, 336, "plaster"), (133, 332, 4, "purple purple", {"clay"}), (202, 336, "plaster"), (271, 336, "plaster"),
        (338, 332, 4, "blue blue", {"clay"}), (408, 336, "plaster"),
        (66, 542, "plaster"), (133, 536, 4, "pink pink", {"clay"}), (201, 538, 4, "lavender darkgreen orange blue"),
        (270, 537, 4, "red cyan darkgreen brown"), (339, 536, 4, "plum plum", {"clay"}), (408, 542, "plaster"),
        (201, 743, 4, "lavender cyan green orange"), (270, 743, 4, "orange cyan lavender blue"),
    ],
    "L108_plaster": [
        (100, 336, "plaster"), (168, 330, 4, "cyan cyan", {"clay"}), (237, 336, "plaster"),
        (304, 330, 4, "yellow yellow", {"clay"}), (374, 336, "plaster"),
        (100, 542, "plaster"), (167, 537, 4, "green green", {"clay"}), (237, 542, "plaster"),
        (304, 536, 4, "orange orange", {"clay"}), (374, 542, "plaster"),
        (133, 743, 4, "yellow yellow lavender"), (201, 743, 4, "red green green"), (270, 743, 4, "pink purple cyan"),
        (339, 743, 4, "orange orange red"),
    ],
    # المرحلة 108 بعد اكتمال الأخضر (السدادة الذهبية): انكسر الجبس عن جارتيه في الصف الثاني فظهرتا بطبقاتهما (ومنها مخفي)
    "L108_plaster_broken": [
        (100, 336, "plaster"), (167, 330, 4, "cyan cyan cyan", {"clay"}), (237, 336, "plaster"),
        (304, 330, 4, "yellow yellow", {"clay"}), (374, 336, "plaster"),
        (98, 537, 4, "? ? blue blue"), (167, 537, 4, "green green green green"), (236, 537, 4, "pink cyan darkgreen"),
        (304, 536, 4, "orange orange", {"clay"}), (374, 542, "plaster"),
        (133, 743, 4, "yellow yellow lavender"), (201, 743, 4, "pink"), (270, 743, 4, "pink purple"),
        (339, 743, 4, "orange orange red red"),
    ],
    # الصعبة جداً: ستائر وجبس معاً (القماش الوردي والجبس الأبيض لا يختلطان)
    "L109_plaster_curtains": [
        (168, 315, "curtain", "red"), (236, 315, "curtain", "darkgreen"), (304, 315, "curtain", "green"),
        (98, 521, "curtain", "blue"), (168, 542, "plaster"), (236, 536, 4, "plum plum", {"clay"}), (306, 542, "plaster"),
        (372, 521, "curtain", "red"),
        (64, 743, 4, "darkgreen red green"), (133, 743, 4, "lavender purple cyan"), (201, 743, 4, "purple orange purple"),
        (270, 743, 4, "plum purple red"), (339, 743, 4, "red red green"), (408, 743, 4, "darkgreen cyan plum"),
    ],
    # قارورة طويلة على صفّين بقاعدة من فتات الجبس بين قالبين في صفّ قاعدتها
    "L110_plaster_tall": [
        (40, 375, 4, "? ? ? blue"), (118, 499, 10, "blue blue blue blue", {"tall"}), (196, 374, 4, "? ? ? brown"),
        (276, 381, "plaster"), (353, 374, 4, "pink pink", {"clay"}), (432, 381, "plaster"),
        (42, 642, "plaster"), (198, 642, "plaster"), (274, 636, 4, "pink purple blue blue"),
        (353, 636, 4, "blue purple purple pink"), (431, 636, 4, "purple blue brown blue"),
    ],
}
NO_PLASTER = ["L101_door_no_plaster", "L105_hidden_no_plaster", "L107_bags_no_plaster"]
WHITE_ADS = ["ad_applovin_test", "ad_applovin_letterbox"]           # إعلان AppLovin التجريبي الأبيض بنسختيه
LOGOS = ["logo_cauldron_m", "logo_magic_sort", "005_d_3s"]           # شعار «MAGIC SORT» فوق لوحة معتمة (ومنه الألعاب النارية)
# شاشات التشغيل التاسع التي مرّ بها البوت كما يجب: (التصنيف، نقطة الزرّ أو X أو هدف «السهم» التي يلمسها السائق)
RUN9_SCREENS = {
    "journey_tap_to_claim": ("unknown", "arrow", (302, 234)),   # «Journey Rewards — Tap to Claim»: لمسة «السهم» تستلمها
    "continue_streak": ("close", "close", (428, 215)),          # «Continue?» بعد «Give Up»: X لا «Play On 900»
    "continue_life": ("close", "close", (428, 215)),
    "level_failed_try_again": ("button", "button", (236, 652)),  # «Level Failed!»: «Try Again»
    "broom_streak": ("close", "close", (412, 74)),
    "race_jetpack": ("close", "close", (411, 76)),
    "race_lost_continue": ("button", "button", (236, 916)),
    "superhard_intro": ("button", "button", (236, 652)),
    "journey_page": ("close", "close", (408, 96)),
}


def _x_glyph(a, cx, cy, size, color, width=3, ring=False, kind="x"):
    """يرسم رمزاً صغيراً على نسخة من الصورة: X (ومعه دائرة اختيارياً)، أو مثلث «▶» ممتلئ، أو «+»."""
    from PIL import Image, ImageDraw
    im = Image.fromarray(a.copy())
    d = ImageDraw.Draw(im)
    h = size // 2
    if kind == "x":
        d.line([(cx - h, cy - h), (cx + h, cy + h)], fill=color, width=width)
        d.line([(cx - h, cy + h), (cx + h, cy - h)], fill=color, width=width)
        if ring:
            r = int(h * 1.45)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)
    elif kind == "play":
        d.polygon([(cx - h, cy - h), (cx - h, cy + h), (cx + h, cy)], fill=color)
    elif kind == "plus":
        d.line([(cx, cy - h), (cx, cy + h)], fill=color, width=width)
        d.line([(cx - h, cy), (cx + h, cy)], fill=color, width=width)
    import numpy as np
    return np.asarray(im)


class TestRun9Vision(unittest.TestCase):
    def test_plaster_tubes(self):
        """قوالب الجبس قوارير محجوبة في خاناتها (العدد والمواضع)، والقوارير الظاهرة كما كانت تُقرأ، بلا تحذيرات."""
        for name, exp in PLASTER_LEVELS.items():
            st = vision.parse_level(_path(name))
            got = st["tubes"]
            self.assertEqual(len(got), len(exp), name)
            self.assertFalse(st.get("warnings"), (name, st.get("warnings")))
            for k, (e, t) in enumerate(zip(exp, got)):
                self.assertTrue(_near((t["x"], t["y"]), e[:2]), (name, k, (t["x"], t["y"]), e))
                if e[2] in ("plaster", "curtain"):
                    self.assertTrue(t.get("blocked"), (name, k))
                    self.assertEqual(t["cover"], e[2], (name, k))
                    self.assertEqual(t["layers"], [], (name, k))
                    self.assertEqual(t["cap"], 4, (name, k))
                    self.assertEqual(len(t["box"]), 4, (name, k))
                    if e[2] == "curtain":
                        self.assertEqual(t["cover_color"], e[3], (name, k))
                else:
                    opt = e[4] if len(e) > 4 else set()
                    self.assertFalse(t.get("blocked"), (name, k))
                    self.assertEqual((t["cap"], t["layers"]), (e[2], e[3].split()), (name, k))
                    self.assertEqual((bool(t.get("tall")), bool(t.get("clay"))), ("tall" in opt, "clay" in opt), (name, k))
            n = sum(1 for e in exp if e[2] == "plaster")
            self.assertEqual(sum(1 for t in got if t.get("cover") == "plaster"), n, name)

    def test_no_plaster_elsewhere(self):
        """لا جبس في لوحات بلا جبس (أبواب، مخفي، أكياس وقوارير طويلة بقاعدة فتات، ستائر، طين، مفاتيح)."""
        names = NO_PLASTER + list(LEVELS) + list(KEY_LEVELS) + list(RUN7_COVERS)
        for name in names:
            st = vision.parse_level(_path(name))
            self.assertFalse([t for t in st["tubes"] if t.get("cover") == "plaster"], name)
        st = vision.parse_level(_path("L107_bags_no_plaster"))
        self.assertEqual([t["cover"] for t in st["tubes"] if t.get("blocked")], ["bag"] * 4)

    def test_white_ad(self):
        """إعلان AppLovin التجريبي الأبيض (بنسختيه) إعلانٌ لا شاشة مجهولة عادية؛ ولا شيء آخر (ولا الإعلان الأسود) يُقرأ كذلك."""
        for name in WHITE_ADS:
            self.assertTrue(vision.is_white_ad(_path(name)), name)
            self.assertEqual(vision.classify(_path(name)), "unknown", name)
            self.assertFalse(vision.is_ad(_path(name)), name)
        for name in _all_testdata():
            if name not in WHITE_ADS:
                self.assertFalse(vision.is_white_ad(_path(name)), name)

    def test_ad_close_corner_x(self):
        """زرّ X صغير في زاوية علوية (فاتح على الشريط الأسود، أو داكن على الأبيض، أو داخل دائرة) يُعرف بمركزه؛ ولا «▶» ولا «+»
        ولا أي شيء في لقطة حقيقية (لا X فيها: لا لمسة إلا على X حقيقي، و«Install» في الأسفل خارج البحث)."""
        for name in _all_testdata():
            self.assertIsNone(vision.find_ad_close(_path(name)), name)
        a = vision.load(_path("ad_applovin_test"))
        b = vision.load(_path("ad_applovin_letterbox"))
        for img, cx, cy, col, ring in ((a, 440, 38, (235, 235, 235), False), (a, 36, 130, (90, 90, 90), False),
                                       (b, 40, 45, (220, 220, 220), True), (b, 432, 120, (240, 240, 240), False)):
            p = vision.find_ad_close(_x_glyph(img, cx, cy, 22, col, ring=ring))
            self.assertIsNotNone(p, (cx, cy, ring))
            self.assertTrue(abs(p[0] - cx) <= 4 and abs(p[1] - cy) <= 4, (p, cx, cy))
        for kind in ("play", "plus"):
            self.assertIsNone(vision.find_ad_close(_x_glyph(a, 440, 38, 22, (235, 235, 235), kind=kind)), kind)
        self.assertIsNone(vision.find_ad_close(_x_glyph(a, 236, 960, 22, (235, 235, 235))))   # أسفل الشاشة: لا يُبحث

    def test_logo_overlay(self):
        """شعار «MAGIC SORT» فوق لوحة معتمة (إطار القِدر والحرف M، والكلمتان، ومع الألعاب النارية) يُعرف؛ وما عداه لا (ومنه
        «Journey Rewards — Tap to Claim» ووضع الخلط المعتم ونوافذ «Continue?»)، فلا تُلمس حروفه الصفراء «سهماً»."""
        for name in LOGOS:
            self.assertTrue(vision.is_logo_overlay(_path(name)), name)
            self.assertEqual(vision.classify(_path(name)), "unknown", name)
        for name in _all_testdata():
            if name not in LOGOS:
                self.assertFalse(vision.is_logo_overlay(_path(name)), name)

    def test_run9_screens_unchanged(self):
        """شاشات التشغيل التاسع (الرحلة، السباق، «Continue?»، «Level Failed!»، سلسلة المكنسة، مقدّمة الصعبة جداً) تُصنَّف وتُلمس
        كما مرّ بها البوت؛ ولا واحدة منها إعلان أو شعار أو «لا حركات» أو نافذة أرواح."""
        for name, (cls, how, pt) in RUN9_SCREENS.items():
            p = _path(name)
            self.assertEqual(vision.classify(p), cls, name)
            got = {"arrow": vision.find_tutorial_arrow, "close": vision.find_close, "button": vision.find_button}[how](p)
            self.assertTrue(_near(got, pt), (name, got, pt))
            self.assertFalse(vision.is_ad(p) or vision.is_white_ad(p) or vision.is_logo_overlay(p), name)
            self.assertIsNone(vision.find_give_up(p), name)
            self.assertIsNone(vision.find_lives_popup(p), name)
        for name in ("continue_streak", "continue_life"):          # زرّها الأخضر «Play On 900» يصرف العملات: ليس زرّاً رئيسياً
            self.assertIsNone(vision.find_button(_path(name)), name)


if __name__ == "__main__":
    total_t = total_te = total_l = total_le = 0
    failed = False
    print("%-20s %8s %10s  %s" % ("image", "tubes", "layers", "errors"))
    for name in LEVELS:
        ok_t, n_t, ok_l, n_l, errs = check_level(name)
        total_t += ok_t
        total_te += n_t
        total_l += ok_l
        total_le += n_l
        failed |= bool(errs)
        print("%-20s %3d/%-4d %4d/%-5d  %s" % (name, ok_t, n_t, ok_l, n_l, "; ".join(errs) or "OK"))
    print("%-20s %3d/%-4d %4d/%-5d" % ("TOTAL", total_t, total_te, total_l, total_le))
    print()
    for name in SCREENS:
        errs = check_screen(name)
        failed |= bool(errs)
        print("%-20s %-8s %s" % (name, SCREENS[name][0], "; ".join(errs) or "OK"))
    for fn in (test_level_numbers, test_animation_frame_warns, test_palette_consistency, test_device_mapping):
        try:
            fn()
            print(fn.__name__, "OK")
        except AssertionError as ex:
            failed = True
            print(fn.__name__, "FAIL", ex)
    sys.exit(1 if failed else 0)
