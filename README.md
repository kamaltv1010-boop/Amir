<div dir="rtl">

# Amir Browser 🌐

متصفح ديال iPhone، مكتوب بـ SwiftUI و WebKit (نفس المحرك ديال Safari).

## شنو كيدير

- **شريط العنوان**: كتب رابط (مثلا `hespress.com`) ولا شي كلمة باش تقلب عليها فـ Google.
- **رجوع / قدّام**: بالبوطونات، ولا سحب بصبعك من جنب الشاشة.
- **إعادة التحميل / إيقاف**، وتقدر تجبد الصفحة لتحت باش تعاود تحمّلها.
- **شريط التقدّم** كيبيّن فين وصل التحميل.
- **المفضلة**: زيد صفحة، حيدها، ولا رتّب الليستة.
- **مشاركة** الرابط (WhatsApp، Messages…).
- **نسخة الحاسوب** ديال المواقع (Request Desktop Website).
- **محرك البحث**: Google، DuckDuckGo ولا Bing.
- **مسح بيانات التصفح** (cookies و cache).
- كيتفكّر **آخر صفحة** كنتي فيها.
- **الحماية من البصمة (fingerprint)**: المواقع كتقدر تعرف التلفون ديالك حتى بلا cookies. المتصفح كيحمي 5 ديال الحوايج، وكل وحدة عندها البوطونة ديالها فالقائمة `⋯ > البصمة`:
  - **Canvas** و **WebGL**: تشويش ما كيبانش فالتصاور لي كتقرا المواقع.
  - **الصوت**: تبديل صغير بزاف فالصوت لي كيتحسب (ما كيتسمعش).
  - **حجم الشاشة**: المواقع كتشوف الحجم ديال واحد من 20 iPhone حقيقي (من SE حتى 16 Pro Max).
  - **User Agent**: المواقع كتشوف Safari ديال واحد من نفس الـ 20 iPhone، بنسخة iOS لي كيخدم بيها بصح (من iOS 16 حتى iOS 26). **تغيير الكل** كيختار نفس الـ iPhone للشاشة والـ User Agent باش يكونو متوافقين.

  كل موقع كيشوف قيم مختلفة، و **تغيير الكل** كيبدّلهم كاملين. تقدر تطفي ولا تشعل كل وحدة من الإعدادات.
- **جلسة جديدة 🔥**: فالقائمة ⋯، كتمسح الـ cookies وكل البيانات ديال المواقع، كتسد كل الصفحات، وكتبدّل كل البصمات. وإلا شعلتي **مسح كل شيء عند الخروج** فالإعدادات، هادشي كيوقع بوحدو كل مرة كتسد فيها التطبيق.
- **تثبيت الروابط 📌**: ضغط مطوّل على أي رابط ← **تثبيت الرابط**، ولا من القائمة ⋯ ← **تثبيت هذه الصفحة**. الروابط المثبتة كتبان تحت شريط العنوان، وضغط مطوّل عليها باش تحيدها.
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

- `INFOPLIST_KEY_CFBundleDisplayName`: السمية لي كتبان تحت الأيقونة (دابا `Amir`).
- `PRODUCT_BUNDLE_IDENTIFIER`: الـ Bundle ID.

## الملفات

| الملف | شنو فيه |
|---|---|
| `AmirBrowser/BrowserView.swift` | الواجهة: شريط العنوان، الصفحة، والبوطونات لتحت |
| `AmirBrowser/BrowserModel.swift` | كيتحكم فـ WKWebView: التحميل، الأخطاء، الروابط، التنبيهات ديال JavaScript |
| `AmirBrowser/AddressResolver.swift` | كيقرر واش داكشي لي كتبتي رابط ولا بحث |
| `AmirBrowser/SearchEngine.swift` | Google / DuckDuckGo / Bing |
| `AmirBrowser/BookmarkStore.swift` و `BookmarksView.swift` | المفضلة |
| `AmirBrowser/SettingsView.swift` | الإعدادات |
| `AmirBrowser/FingerprintProtection.swift` | الحماية من البصمة (Canvas، WebGL، الصوت، الشاشة، User Agent) |
| `AmirBrowser/Localizable.xcstrings` | الترجمة (عربية، فرنسية، إنجليزية) |
| `AmirBrowser/InfoPlist.xcstrings` | الرسائل لي كيطلب بيهم التطبيق الإذن (الكاميرا، الميكرو، الصور) |
| `.github/workflows/build-ipa.yml` | البناء الأوتوماتيكي ديال `.ipa` بلا توقيع |
| `.github/workflows/testflight.yml` | التوقيع والرفع لـ TestFlight |

</div>
