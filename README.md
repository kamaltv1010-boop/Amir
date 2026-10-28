<div dir="rtl">

# Noor نور ✦

<img src="Support/AppIcon.svg" width="120" alt="">

**Noor** متصفح ديال iPhone كيحمي الخصوصية ديالك، مكتوب بـ SwiftUI و WebKit (نفس المحرك ديال Safari). الأيقونة: درع فيه نجمة ديال الضو (نور).

## شنو كيدير

### الواجهة (النسخة 2)
- **شريط العنوان لتحت** بحال Safari: كليكي عليه، كتب رابط (مثلا `hespress.com`) ولا شي كلمة باش تقلب، وغادي يقترح عليك من المفضلة والسجل. ضغط مطوّل عليه باش تنسخ الرابط ولا **تلصق وتمشي**.
- **Onglets (علامات التبويب) 🗂️**: حل بزاف ديال الصفحات فنفس الوقت. البوطونة لي فيها الرقم كتوريك كاع الـ onglets بالتصاور ديالهم، وتقدر تسدهم ولا تحل جديد بـ **+**. ملي كتسد التطبيق وتعاود تحلو، الـ onglets كيرجعو.
- **Onglets خاصة 🕶️**: ما كتسجلش فالسجل، والـ cookies ديالها كيمشيو ملي كتسد آخر onglet خاص.
- **صفحة البداية**: بحث، **إحصائيات الخصوصية** بحال Brave (شحال من tracker تبلوكا، شحال من موقع تحل بـ HTTPS، وشحال د الوقت ربحتي)، والمفضلة ديالك.
- **السجل (History)**: فالقائمة ⋯ ← **المفضلة والسجل**، بالبحث وبالنهار.
- **البحث فالصفحة**، **التكبير (Zoom)** و **الوضع الليلي 🌙** لي كيرد المواقع غامقين.
- **رجوع / قدّام**: بالبوطونات، ولا سحب بصبعك من جنب الشاشة. وتقدر تجبد الصفحة لتحت باش تعاود تحمّلها.
- **المفضلة**، **مشاركة** الرابط، **نسخة الحاسوب** ديال المواقع، و **محرك البحث**: Google، DuckDuckGo ولا Bing. المفضلة والروابط المثبتة كيتسجلو بالعنوان الرسمي ديال الصفحة (الـ `canonical` اللي كيعلنو الموقع)، ولا بلا أكواد التتبع، ماشي بعنوان اللحظة بالـ paramètres ديالو (بحال رابط «ما بعد التسجيل»)، باش ملي تحلهم الموقع ما يعرفش من فين جيتي.

### الدروع (Shields) 🦁
- البوطونة البرتقالية 🛡️ لي فشريط العنوان كتبيّن شحال من tracker تبلوكا فهاد الصفحة. كليكي عليها باش **تطفي الدروع غير لهاد الموقع** إلا ما خدمش مزيان (حظر التتبع، HTTPS والحماية من البصمة كيطفاو غير فيه).
- **HTTPS أوتوماتيك 🔒**: المواقع لي كتحل بـ `http://` كتحل بـ `https://` إلا كان الموقع كيقبلها، وإلا كترجع لـ `http://` بوحدها.
- المواقع لي طفيتي فيها الدروع كتلقاهم فالإعدادات ← **مواقع بدروع متوقفة**.
- **مواقع تسجيل الدخول 🔑**: Instagram، Facebook، Messenger، Threads، WhatsApp، وحسابات Google و Apple و Microsoft كيتفحصو المتصفح مزيان ملي كتدخل ولا كتصاوب حساب، وإلا لقاو شي حاجة غريبة كيبلوكيو ولا كيبقاو يطلبو الكود. هاد المواقع كيشوفو الشاشة الحقيقية ديال الـ iPhone ديالك والـ User Agent ديال Safari على نفس الـ iPhone ونفس نسخة iOS (حيت كيقارنوهم مع الجهاز)، ولكن التشويش ديال Canvas و WebGL والصوت و ClientRects كيبقى خدام، فكل بروفايل كيبان ليهم تلفون آخر من نفس النوع. الـ trackers كيبقاو مبلوكيين. أما المواقع لي طفيتي فيها الدروع فكتشوف الـ iPhone كيف هو بالكامل.

### الامتدادات (Extensions) 🧩
- **من Chrome Web Store مباشرة**: حل [chromewebstore.google.com](https://chromewebstore.google.com/) فـ Noor (القائمة ⋯ ← **الامتدادات** ← **سوق Chrome الإلكتروني**)، دخل لصفحة شي امتداد، وكليكي على **إضافة إلى نور** لي كتبان لتحت. Noor كينزّل الامتداد من نفس البلاصة لي كينزّل منها Chrome.
- ولا من ملف `.zip` ولا `.crx`، ولا dossier فيه `manifest.json`، محطوط فتطبيق **Files**: الإعدادات ← **الامتدادات** ← **إضافة من الملفات…**.
- خاص **iOS 18.4 ولا كثر**، حيت WebKit (المحرك ديال Safari) هو لي كيشغّلهم.
- الامتدادات لي كتبلوكي الإعلانات (بحال uBlock Origin Lite) ولا كتبدّل الشكل ديال الصفحات (بحال Dark Reader) غالبا كيخدمو. شي حوايج خاصة بـ Chrome بوحدو ما كتخدمش.
- كيخدمو حتى فالـ **onglets الخاصة**. تقدر تطفي هادشي من **السماح في علامات التبويب الخاصة**.
- البوطونات والـ pop-ups ديال الامتدادات كتلقاهم فالقائمة ⋯ ← **الامتدادات**.
- قبل ما يتزاد، التطبيق كيوريك شنو يقدر يدير الامتداد (المواقع لي يقدر يقرا ويبدّل، والصلاحيات).

### الخصوصية
- **الحماية من البصمة (fingerprint)**: المواقع كتقدر تعرف التلفون ديالك حتى بلا cookies. المتصفح كيحمي 6 ديال الحوايج، وكل وحدة عندها البوطونة ديالها فالقائمة `⋯ > البصمة`:
  - **Canvas** و **WebGL**: تشويش ما كيبانش فالتصاور لي كتقرا المواقع (`getImageData`، `toDataURL`، `readPixels`…)، غير فالحواف والتدرجات لي كيبان فيهم الجهاز؛ الأشكال والألوان الموحدة كتبقى كيف هي، باش الموقع لي كيرسم شكل بسيط ويتفحص البيكسلات ما يلقى والو. كيخدم حتى فالـ iframes الفارغين والنوافذ لي كتحلهم الصفحة.
  - **الصوت**: تبديل صغير بزاف فالصوت لي كيتحسب (ما كيتسمعش).
  - **ClientRects**: المواقع كتقيس الحجم والبلاصة ديال النصوص والعناصر بدقة كبيرة (`getBoundingClientRect` و `getClientRects`) باش تعرف الجهاز. المتصفح كيبدّل هاد القياسات بـ 0.00001 حتى 0.00002 pixel، حاجة ما كتبانش نهائيا.
  - **حجم الشاشة**: المواقع كتشوف الحجم ديال واحد من 20 iPhone حقيقي (من SE حتى 16 Pro Max).
  - **User Agent**: المواقع كتشوف Safari ديال واحد من نفس الـ 20 iPhone، بنسخة iOS لي كيخدم بيها بصح (من iOS 16 حتى iOS 26).
  - **بحال Safari بصح**: Apple كتعطي الـ service workers وquota كبيرة ديال التخزين غير لـ Safari وللمتصفحات لي عندها الإذن ديالها، ماشي للتطبيقات. موقع كيشوف User Agent ديال Safari بلا `navigator.serviceWorker` ولا بـ quota صغيرة كيحسبك متصفح داخل تطبيق وكيشك فيك (Instagram كيطلب "تأكيد أنك شخص حقيقي"). المتصفح كيعطي الصفحات الشكل ديال الـ service workers (التسجيل كيفشل بهدوء بحال متصفح كيمنعهم) وquota ديال متصفح، فكل الصفحات، حتى مع الدروع طافية. **تغيير الكل** كيختار نفس الـ iPhone للشاشة والـ User Agent باش يكونو متوافقين.

  كل موقع كيشوف قيم مختلفة، و **تغيير الكل** كيبدّلهم كاملين. تقدر تطفي ولا تشعل كل وحدة من الإعدادات.
- **وضع iPad 📱**: بوطونة فالقائمة ⋯. ملي كتشعلها، المواقع كتشوف Safari ديال واحد من 10 iPad حقيقيين (iPad، iPad mini، iPad Air و iPad Pro)، بنسخة iPadOS لي كيخدم بيها بصح، وكتشوف تا الشاشة ديال نفس الـ iPad إلا كانت حماية **حجم الشاشة** شاعلة. **User Agent جديد** و **تغيير الكل** كيختارو iPad آخر. كتبقى شاعلة حتى تطفيها، وكتخدم حتى إلا كانت حماية الـ User Agent طافية.
- **الحماية من التتبع 🛡️**: كيبلوكي Meta Pixel، و Facebook و Instagram فالمواقع الأخرى، و Google Analytics، TikTok، X، Snapchat وغيرهم (49 قاعدة فـ `TrackerRules.json`). Facebook و Instagram كيخدمو عادي فالمواقع ديالهم.
- **تنظيف الروابط 🔗**: كيحيد رموز التتبع بحال `fbclid` و `igshid` و `gclid` و `utm_…` من الروابط لي كتحل ولا كتشارك.
- **إخفاء فمبدّل التطبيقات 🙈**: ملي كتخرج من التطبيق، الصفحة ما كتبانش فالـ app switcher.
- **الملفات الشخصية (Profiles) 👤**: الإعدادات ← **الملفات الشخصية**. كل بروفايل عندو الـ cookies والبيانات ديال المواقع ديالو، السجل ديالو، الـ onglets ديالو، والبصمات ديالو (Canvas، WebGL، الصوت…)، بحال متصفح آخر: الحسابات ما كيتخلطوش بيناتهم. **ملف شخصي جديد** كيصاوب واحد ويحلو، وضغط على بروفايل كيبدّل ليه (كيسد الـ onglets ويحل ديالو)، والبوطونة 🗑️ كتمسحو مع كل البيانات ديالو، و**حذف كل الملفات الشخصية** كتمسح كلشي ما عدا الأول بضغطة وحدة. وباش ما تدخلش للإعدادات كل مرة، البروفايلات كاينين حتى فالقائمة ⋯ (**الملف الشخصي: …**) وفصفحة البداية تحت «Noor»: ضغطة كتبدّل، كتصاوب، ولا كتمسح. المفضلة، الروابط المثبتة، الامتدادات والإعدادات مشتركين بين البروفايلات. قبل iOS 17، غير البروفايل الأول كيحتافظ بالبيانات ديالو فالتلفون؛ الآخرين كيحتافظو بيها غير مدة ما التطبيق محلول.
- **جلسة جديدة 🔥**: فالقائمة ⋯، كتمسح الـ cookies وكل البيانات ديال المواقع والسجل ديال البروفايل المحلول، كتسد الـ onglets ديالو، وكتبدّل كل البصمات ديالو (الـ switches ديال الحماية كيبقاو كيف ما هما). البروفايلات الآخرين ما كيتقاسوش. وإلا شعلتي **مسح كل شيء عند الخروج** فالإعدادات، الـ cookies والبيانات والسجل كيبقاو غير فالذاكرة وعمرهم ما كيتسجلو فالتلفون، وكيمشيو ملي كتسد التطبيق.
- **ملفات تعريف الارتباط (Cookies) 🍪**: فالقائمة ⋯ ← **Cookies**. كتصدّر الـ cookies ديال الموقع لي راك فيه بصيغة header string (`name=value; name2=value2`) باش تنسخها، تشاركها ولا تسجلها فملف، ولا تستوردها من نص كتلصقو ولا من ملف. من بعد الاستيراد الصفحة كتعاود تتحمّل بالـ cookies الجداد. (كتخدم على الـ cookies ديالك فهاد المتصفح، بحال إضافة Cookie-Editor.)
- **تثبيت الروابط 📌**: ضغط مطوّل على أي رابط ← **تثبيت الرابط**، ولا من القائمة ⋯ ← **تثبيت هذه الصفحة**. الروابط المثبتة كتبان الفوق، وضغط مطوّل عليها باش تحلها فـ onglet جديد ولا تحيدها.
- ضغط مطوّل على أي رابط ← **فتح في علامة تبويب جديدة** ولا **فتح في علامة تبويب خاصة**.
- الروابط بحال `tel:` و `mailto:` كتحل فالتطبيق المناسب.
- الواجهة بالعربية، الفرنسية والإنجليزية، على حساب لغة التلفون.

## كيفاش تحطو فـ iPhone ديالك

Apple ما كتخليش تزيد تطبيق فـ iPhone إلا من App Store ولا TestFlight، ولا إلا وقّعتيه (sign) بـ Apple ID ديالك. عندك 3 طرق.

> 💡 المسارات ديال القوائم مكتوبين بالإنجليزية من اليسار لليمين، بحال `Settings > General > About`: كليكي على الأولى، من بعد الثانية، وهكذا.

### الطريقة 0: بلا حاسوب نهائيا (TestFlight)

خاصك حساب **Apple Developer Program** (99$ فالعام). كلشي كيتدار من الـ iPhone، والبناء والتوقيع كيديرهم GitHub على Mac ديالو.

**مرة وحدة فالبداية:**
1. سجّل الـ Bundle ID: [developer.apple.com/account/resources/identifiers/add/bundleId](https://developer.apple.com/account/resources/identifiers/add/bundleId). ختار **App IDs** ثم **App** ثم **Explicit**، وكتب `io.github.kamaltv1010-boop.AmirBrowser`.
2. وجّد التطبيق فـ [App Store Connect](https://appstoreconnect.apple.com/apps): `Apps > + > New App`. ختار iOS، سمية ما مستعملاش فـ App Store، والـ Bundle ID لي سجلتي، و SKU `amirbrowser`.
3. صاوب API key: [appstoreconnect.apple.com/access/integrations/api](https://appstoreconnect.apple.com/access/integrations/api). أول مرة ضغط **Request Access**. من بعد `Team Keys > Generate API Key`، و **Access** خاصو يكون **Admin**. نزّل الملف `.p8` (كيتنزّل مرة وحدة برك)، ونقل الـ **Key ID** والـ **Issuer ID**.
4. جيب الـ **Team ID** من [developer.apple.com/account](https://developer.apple.com/account#MembershipDetailsCard) فـ **Membership details**.
5. فـ GitHub حل `Settings > Secrets and variables > Actions > New repository secret`، وزيد 4 ديال الـ secrets:

| Name | Secret |
|---|---|
| `ASC_KEY_P8` | المحتوى كامل ديال الملف `.p8` |
| `ASC_KEY_ID` | الـ Key ID |
| `ASC_ISSUER_ID` | الـ Issuer ID |
| `APPLE_TEAM_ID` | الـ Team ID |

> 🔒 هاد الـ repo **public**. حط المفاتيح غير فـ Secrets، وعمّرك ما تكتبهم فشي ملف ولا فشي رسالة.

**كل مرة بغيتي نسخة جديدة:**
1. فـ GitHub حل `Actions > TestFlight > Run workflow`. كياخد بين 5 و10 دقايق.
2. Apple كتعالج النسخة بين 10 و30 دقيقة.
3. فـ App Store Connect حل `TestFlight > Internal Testing`، وجّد مجموعة وزيد فيها راسك (مرة وحدة برك).
4. نزّل **TestFlight** من App Store، وركّب منو التطبيق. كل نسخة كتخدم 90 يوم.

### الطريقة 1: عندك Mac

1. نزّل **Xcode** من App Store (فابور).
   > ⚠️ Xcode 27 لي فـ App Store خاصو macOS Tahoe 26.6 ولا كثر، وكيركّب غير على iPhone فيه **iOS 17 ولا كثر**. إلا كان الـ iPhone ديالك فـ iOS 15 ولا 16، ولا الـ Mac قديم، نزّل Xcode 26 ولا 16 من [developer.apple.com/download/all](https://developer.apple.com/download/all)، ولا استعمل الطريقة 2.
2. حل الملف `AmirBrowser.xcodeproj`.
3. فـ Xcode حل `AmirBrowser > Signing & Capabilities`، وفـ **Team** ختار Apple ID ديالك (ولا **Add an Account**).
4. إلا قالك الـ **Bundle Identifier** ماشي متوفر، بدّلو لشي حاجة خاصة بيك (مثلا `com.smitek.browser`).
5. ركّب الـ iPhone بالكابل، وفالتلفون ضغط **Trust This Computer**. ختار الـ iPhone من الفوق فـ Xcode وكليكي على ▶️ (**Run**).
   فـ iOS 16 ولا كثر، هاد المرة الأولى غادي تفشل وتقول ليك Developer Mode طافي. هادشي عادي، وهو لي كيبيّن الخيار فالتلفون.
6. فالـ iPhone حل `Settings > Privacy & Security > Developer Mode` وشعلو. التلفون غادي يعاود يشعل، ومن بعد ضغط **Enable** ودخّل الكود ديال التلفون.
7. رجع لـ Xcode وكليكي ▶️ (**Run**) مرة أخرى.
8. فالـ iPhone حل `Settings > General > VPN & Device Management`، ختار الحساب ديالك، وضغط **Trust**. دابا تقدر تحل التطبيق.

### الطريقة 2: ما عندكش Mac (عندك Windows)

GitHub كيبني ليك التطبيق بوحدو (ملف `.ipa`) على Mac ديالو، فكل مرة كتبدّل الكود.

1. فالـ repo حل `Actions > Build IPA` وختار آخر run فيه ✅.
2. لتحت، فـ **Artifacts**، نزّل **AmirBrowser-ipa** وفكّ الـ zip: غادي تلقى `AmirBrowser.ipa`.
3. نزّل **Sideloadly** من [sideloadly.io](https://sideloadly.io). فـ Windows خاصك تا **iTunes** و **iCloud**: نزّلهم من الروابط لي فالصفحة ديال Sideloadly (النسخ ديال الويب). إلا كانو عندك من Microsoft Store، حيدهم قبل وعاود شعّل الحاسوب.
4. ركّب الـ iPhone بالكابل، جرّ `AmirBrowser.ipa` لـ Sideloadly، دخّل Apple ID ديالك، وكليكي **Start**.
5. فالـ iPhone شعّل `Settings > Privacy & Security > Developer Mode` (التلفون غادي يعاود يشعل، ضغط **Enable**). من بعد حل `Settings > General > VPN & Device Management`، ختار الحساب ديالك، وضغط **Trust**.

> ⚠️ **مهم:** بـ Apple ID فابور، التطبيق كيخدم **7 أيام** ومن بعد خاصك تعاود تركّبو (Sideloadly كيقدر يجدّدو ليك). وما تقدرش تركّب أكثر من 3 تطبيقات بهاد الطريقة فنفس الوقت. إلا بغيتيه يبقى عام كامل، خاصك **Apple Developer Program** (99$ فالعام).
>
> 🔒 إلا ما بغيتيش تدخّل Apple ID ديالك الأساسي فـ Sideloadly، صاوب Apple ID آخر غير لهاد الغرض.

## بدّل السمية ولا الـ Bundle ID

فـ Xcode حل `AmirBrowser > Build Settings`:

- `INFOPLIST_KEY_CFBundleDisplayName`: السمية لي كتبان تحت الأيقونة (دابا `Noor`، وبالعربية `نور` من `AmirBrowser/InfoPlist.xcstrings`).
- `PRODUCT_BUNDLE_IDENTIFIER`: الـ Bundle ID.

## الملفات

| الملف | شنو فيه |
|---|---|
| `AmirBrowser/BrowserView.swift` | الواجهة: الصفحة، شريط العنوان، البوطونات لتحت والقائمة ⋯ |
| `AmirBrowser/BrowserModel.swift` | الـ onglets (عاديين وخاصين)، الإعدادات لي مشتركين بيناتهم، والجلسة الجديدة |
| `AmirBrowser/BrowserTab.swift` | onglet واحد: الـ WKWebView ديالو، التحميل، الأخطاء، HTTPS، الروابط والتنبيهات ديال JavaScript |
| `AmirBrowser/AddressEditor.swift` | الكتابة فشريط العنوان مع الاقتراحات |
| `AmirBrowser/StartPage.swift` و `TabOverview.swift` | صفحة البداية، وعرض كاع الـ onglets |
| `AmirBrowser/Shields.swift` و `ShieldsPanel.swift` | الدروع، HTTPS، الوضع الليلي، وعدّاد الـ trackers |
| `AmirBrowser/HistoryStore.swift` و `LibraryView.swift` | السجل والمفضلة |
| `AmirBrowser/ExtensionManager.swift` و `ExtensionsView.swift` | الامتدادات (WKWebExtension) |
| `AmirBrowser/Theme.swift` | الألوان والأيقونات المشتركة |
| `AmirBrowser/AddressResolver.swift` | كيقرر واش داكشي لي كتبتي رابط ولا بحث |
| `AmirBrowser/SearchEngine.swift` | Google / DuckDuckGo / Bing |
| `AmirBrowser/BookmarkStore.swift` | المفضلة والروابط المثبتة |
| `AmirBrowser/SettingsView.swift` | الإعدادات |
| `AmirBrowser/TrackingProtection.swift` و `TrackerRules.json` | حظر الـ trackers وتنظيف الروابط |
| `AmirBrowser/FingerprintProtection.swift` | الحماية من البصمة (Canvas، WebGL، الصوت، الشاشة، User Agent) |
| `AmirBrowser/Profiles.swift` | الملفات الشخصية: البيانات، السجل والبصمات ديال كل بروفايل |
| `AmirBrowser/Localizable.xcstrings` | الترجمة (عربية، فرنسية، إنجليزية) |
| `AmirBrowser/InfoPlist.xcstrings` | الرسائل لي كيطلب بيهم التطبيق الإذن (الكاميرا، الميكرو، الصور) |
| `.github/workflows/build-ipa.yml` | البناء الأوتوماتيكي ديال `.ipa` بلا توقيع |
| `.github/workflows/testflight.yml` | التوقيع والرفع لـ TestFlight |

</div>
