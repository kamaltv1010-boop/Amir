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
- الروابط بحال `tel:` و `mailto:` كتحل فالتطبيق المناسب.
- الواجهة بالعربية، الفرنسية والإنجليزية، على حساب لغة التلفون.

## كيفاش تحطو فـ iPhone ديالك

Apple ما كتخليش تزيد تطبيق فـ iPhone إلا من App Store، ولا إلا وقّعتيه (sign) بـ Apple ID ديالك. عندك جوج طرق:

### الطريقة 1: عندك Mac

1. نزّل **Xcode** من App Store (فابور، خاص Xcode 16 ولا كثر).
2. حل الملف `AmirBrowser.xcodeproj`.
3. كليكي على المشروع ← target **AmirBrowser** ← **Signing & Capabilities** ← فـ **Team** ختار Apple ID ديالك (ولا **Add an Account**).
4. إلا قالك الـ **Bundle Identifier** ماشي متوفر، بدّلو لشي حاجة خاصة بيك (مثلا `com.smitek.browser`).
5. ركّب الـ iPhone بالكابل، ختارو من الفوق، وكليكي على ▶️ (**Run**).
6. فالـ iPhone:
   - **Settings ← Privacy & Security ← Developer Mode**: شعلو، والتلفون غادي يعاود يشعل (iOS 16 ولا كثر).
   - **Settings ← General ← VPN & Device Management** ← ختار الحساب ديالك ← **Trust**.

### الطريقة 2: ما عندكش Mac (عندك Windows)

GitHub كيبني ليك التطبيق بوحدو (ملف `.ipa`) على Mac ديالو، فكل مرة كتبدّل الكود.

1. فالـ repo سير لـ **Actions** ← **Build IPA** ← ختار آخر run فيه ✅.
2. لتحت، فـ **Artifacts**، نزّل **AmirBrowser-ipa** وفكّ الـ zip: غادي تلقى `AmirBrowser.ipa`.
3. نزّل **Sideloadly** من [sideloadly.io](https://sideloadly.io). فـ Windows خاصك تا **iTunes** و **iCloud** ديال الموقع ديال Apple (ماشي ديال Microsoft Store).
4. ركّب الـ iPhone بالكابل، جرّ `AmirBrowser.ipa` لـ Sideloadly، دخّل Apple ID ديالك، وكليكي **Start**.
5. فالـ iPhone دير نفس الخطوة 6 ديال الطريقة 1 (Developer Mode + Trust).

> ⚠️ **مهم:** بـ Apple ID فابور، التطبيق كيخدم **7 أيام** ومن بعد خاصك تعاود تركّبو (Sideloadly كيقدر يجدّدو ليك). وما تقدرش تركّب أكثر من 3 تطبيقات بهاد الطريقة فنفس الوقت. إلا بغيتيه يبقى عام كامل، خاصك **Apple Developer Program** (99$ فالعام).
>
> 🔒 إلا ما بغيتيش تدخّل Apple ID ديالك الأساسي فـ Sideloadly، صاوب Apple ID آخر غير لهاد الغرض.

## بدّل السمية ولا الـ Bundle ID

فـ Xcode ← target **AmirBrowser** ← **Build Settings**:

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
| `AmirBrowser/Localizable.xcstrings` | الترجمة (عربية، فرنسية، إنجليزية) |
| `.github/workflows/build-ipa.yml` | البناء الأوتوماتيكي ديال `.ipa` |

</div>
