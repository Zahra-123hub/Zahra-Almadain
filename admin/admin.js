var DATA = {settings:{}, gallery:[], news:[]}, tab = "gallery";
var API_BASE = (window.ZM_API_BASE || (/^(localhost|127.0.0.1)$/.test(location.hostname) ? "http://127.0.0.1:8001" : "https://zahra-123hub-almadain-api.onrender.com")).replace(/\/+$/, "");
var ADMIN_TOKEN = sessionStorage.getItem("zm-admin-session") || "";
// Teachers publish website content with their portal session; accounts and settings stay admin-only.
// An account may hold several roles (e.g. teacher + accountant): the tabs are the union of what its roles allow.
var TEACHER_MODE = false, ACCOUNTANT_MODE = false, PORTALS = [];
if(!ADMIN_TOKEN){
  try{ PORTALS = JSON.parse(sessionStorage.getItem("zm-portals") || "[]"); }catch(e){}
  var teacherSession = sessionStorage.getItem("zm-teacher-session") || "", accountantSession = sessionStorage.getItem("zm-accountant-session") || "";
  ADMIN_TOKEN = accountantSession || teacherSession;
  TEACHER_MODE = !!ADMIN_TOKEN && (PORTALS.length ? PORTALS.indexOf("teacher") !== -1 : !!teacherSession);
  ACCOUNTANT_MODE = !!ADMIN_TOKEN && (PORTALS.length ? PORTALS.indexOf("accountant") !== -1 : !!accountantSession);
  if(!TEACHER_MODE && !ACCOUNTANT_MODE) ADMIN_TOKEN = "";
  if(ACCOUNTANT_MODE && !TEACHER_MODE) tab = "fees";
}
// the portals this account may enter (shown as links in the header, like in the portals)
if(!PORTALS.length){ try{ PORTALS = JSON.parse(sessionStorage.getItem("zm-portals") || "[]"); }catch(e){} }
function clearSessions(){
  ADMIN_TOKEN = "";
  try{ sessionStorage.removeItem("zm-admin-session"); sessionStorage.removeItem("zm-teacher-session"); sessionStorage.removeItem("zm-accountant-session"); sessionStorage.removeItem("zm-parent-session"); sessionStorage.removeItem("zm-portals"); }catch(e){}
}
var ADMIN_LANG = localStorage.getItem("zm-admin-lang") === "en" ? "en" : "ar";
var FILE_RE = /^[0-9a-f]{32}\.(jpg|png|webp|gif|mp4|webm)$/;
var EN_TEXT = {
  "تعذّر الاتصال بالخادم. تحقق من إعداد رابط API واتصال الإنترنت.":"Could not connect to the server. Check the API URL and your internet connection.",
  "تعذّر تنفيذ العملية. حاول مرة أخرى.":"The operation failed. Please try again.",
  "تعذّر تنفيذ العملية على الخادم.":"The server could not complete the operation.",
  "تعذّر تنفيذ العملية على GitHub.":"The operation could not be completed on GitHub.",
  "انتهت جلسة الدخول. سجّل الدخول مرة أخرى.":"Your session expired. Please sign in again.",
  "لم يتم إعداد اتصال GitHub على الخادم.":"The GitHub connection is not configured on the server.",
  "رمز GitHub المخزن على الخادم غير صالح أو منتهي.":"The GitHub token stored on the server is invalid or expired.",
  "رمز GitHub يحتاج صلاحية Contents للقراءة والكتابة.":"The GitHub token needs Contents read and write permission.",
  "تعذّر الاتصال بـ GitHub من الخادم.":"The server could not connect to GitHub.",
  "انتهت مهلة الاتصال بـ GitHub. حاول مرة أخرى.":"The connection to GitHub timed out. Please try again.",
  "لم يتم العثور على المستودع أو الملف في GitHub.":"The repository or file was not found on GitHub.",
  "ملف content.json غير صالح أو تعذّر قراءته.":"content.json is invalid or could not be read.",
  "بنية ملف المحتوى غير صالحة.":"The content file has an invalid structure.",
  "الملف غير موجود.":"File not found.",
  "نوع العنصر غير صالح.":"Invalid item type.",
  "تعارضت تعديلات متزامنة. أعد المحاولة.":"Concurrent edits conflicted. Please try again.",
  "نوع الملف غير مدعوم.":"This file type is not supported.",
  "حجم الملف يتجاوز الحد المسموح (10 ميغابايت للصورة و25 ميغابايت للفيديو).":"The file exceeds the size limit (10 MB for images, 25 MB for videos).",
  "نوع الملف لا يطابق القسم المحدد.":"The file type does not match the selected section.",
  "عنصر المعرض غير موجود.":"Gallery item not found.",
  "العنوان والنص مطلوبان.":"A title and text are required.",
  "الخبر غير موجود.":"News item not found.",
  "لم يتم إعداد جلسات المسؤول على الخادم.":"Admin sessions are not configured on the server.",
  "سجّل الدخول إلى لوحة التحكم.":"Please sign in to the admin panel.",
  "لم يتم إعداد بيانات دخول المسؤول على الخادم.":"Admin login is not configured on the server.",
  "اسم المستخدم أو كلمة المرور غير صحيحة.":"Incorrect username or password.",
  "يجب أن يبدأ الرابط بـ https://":"Links must start with https://",
  "رقم الواتساب غير صالح.":"The WhatsApp number is invalid.",
  "تعليق يظهر تحت العنصر (اختياري)":"Caption shown under the item (optional)",
  "فيديوهات الهاتف بصيغة MOV لا تعمل. صدّرها بصيغة MP4.":"MOV videos from phones are not supported. Export them as MP4.",
  "لا توجد فيديوهات مرفوعة بعد.":"No videos uploaded yet.",
  "لا توجد صور مرفوعة بعد.":"No photos uploaded yet.",
  "لا توجد أخبار مضافة.":"No news added yet.",
  "إلغاء التعديل":"Cancel edit",
  "حذف الصورة الحالية":"Remove current image",
  "صورة (اختيارية)":"Image (optional)",
  "التصنيف (كلمة قصيرة)":"Category (short label)",
  "العنوان":"Title",
  "النص":"Text",
  "شريط إعلان أعلى الموقع":"Announcement banner",
  "رقم الهاتف الظاهر":"Display phone number",
  "رقم الواتساب بالصيغة الدولية، أرقام فقط":"WhatsApp number (international digits only)",
  "أوقات الدوام":"Opening hours",
  "رابط صفحة فيسبوك":"Facebook page URL",
  "رابط صفحة إنستغرام":"Instagram page URL",
  "البريد الإلكتروني":"Email address",
  "معلومات التواصل والإعلان":"Contact information and announcements",
  "الملفات":"Files", "الأمان":"Security", "ملفات المعلمات":"Teachers' files", "تصدير Excel":"Export to Excel", "تنزيل":"Download", "السابق":"Previous", "التالي":"Next",
  "لا توجد ملفات مرفوعة بعد.":"No files uploaded yet.", "تم حذف الملف.":"The file was deleted.", "الملف":"File", "صاحبه":"Owner", "الحجم":"Size", "التاريخ":"Date",
  "حسابات فعّالة":"Active accounts", "حسابات موقوفة":"Blocked accounts", "حسابات بانتظار الموافقة":"Accounts awaiting approval", "جلسات مفتوحة الآن":"Open sessions now",
  "تسجيلات دخول آخر ٢٤ ساعة":"Sign-ins in the last 24 hours", "محاولات دخول فاشلة آخر ٢٤ ساعة":"Failed sign-ins in the last 24 hours",
  "الحسابات الفعّالة حسب النوع":"Active accounts by type", "التخزين":"Storage", "ملفات خاصة":"Private files", "المساحة المستعملة":"Space used",
  "تصدير إلى Excel":"Export to Excel", "كل الأشهر":"All months", "اشتراكات الأطفال":"Children's fees",
  "يُنزَّل ملف بحسب السنة والشهر والعملة المختارة أعلاه. للطباعة أو PDF افتح الجدول الشهري واختر «طباعة» من المتصفح.":"A file is downloaded for the year, month and currency chosen above. To print or save a PDF, open the monthly sheet and choose Print in the browser.",
  "لوحة سير العمل":"Workflow board",
  "ما تم وما بقي، والخطوة التالية":"What is done, what is left, and the next step",
  "الإعدادات الأساسية":"Basic settings",
  "العملات وسعر الصرف والصندوق والبنود":"Currencies, exchange rate, cash box and items",
  "الموظفون والرواتب":"Staff and salaries",
  "بيانات الموظفين والرواتب المستحقة هذا الشهر":"Staff details and the salaries owed this month",
  "الأطفال والاشتراك الشهري والمتبقي على كل ولي أمر":"Children, monthly fee and what each parent still owes",
  "الإيرادات":"Income",
  "كل ما دخل الصندوق: الدفعات وغيرها":"Everything that came into the cash box: payments and others",
  "المصروفات والإيصالات":"Expenses and receipts",
  "كل ما خرج من الصندوق مع التاريخ والبيان والإيصال":"Everything that went out, with date, description and receipt",
  "دفع الرواتب":"Salary payments",
  "الرواتب المدفوعة فعلاً ومطابقتها بالمستحق":"Salaries actually paid, compared with what is owed",
  "المطابقة وجرد الصندوق":"Reconciliation and cash count",
  "عدّ الصندوق ومقارنته بالدفاتر":"Count the cash box and compare it with the books",
  "الملخص المالي":"Financial summary",
  "الرصيد الحالي والواردات والمصروفات":"Current balance, income and expenses",
  "التقارير":"Reports",
  "يومي وأسبوعي وشهري وسنوي":"Daily, weekly, monthly and yearly",
  "إغلاق الشهر":"Close the month",
  "مراجعة الشهر ثم قفله نهائياً":"Review the month, then lock it",
  "التصدير والأرشيف":"Export and archive",
  "ملف كامل للشهر المغلق وسجل التصدير":"A full file of the closed month and the export log",
  "معلّقة":"Pending",
  "قيد التنفيذ":"In progress",
  "مكتملة":"Complete",
  "تحديث الحالة":"Refresh status",
  "الشهر قيد العمل":"Month in work",
  "فحص قبل المتابعة":"Check before you continue",
  "فتح الخطوة":"Open step",
  "فتح":"Open",
  "الخطوة التالية":"Next step",
  "التالية":"Next",
  "الخطوة التالية في الترتيب":"Next in order",
  "التالي في الترتيب: ":"Next in order: ",
  "تعذّر تحميل حالة الشهر. تأكّد من الاتصال ثم حدّث الصفحة.":"The state of the month could not be loaded. Check the connection and reload the page.",
  "تعذّر تحميل حالة الشهر.":"The state of the month could not be loaded.",
  "🔒 هذا الشهر مغلق. يبقى التصدير والأرشفة والاطّلاع على التقارير.":"🔒 This month is closed. Exporting, archiving and reading reports remain possible.",
  "سعر الصرف":"Exchange rate",
  "كم ليرة سورية تساوي 1 دولار":"How many Syrian pounds equal 1 dollar",
  "ابتداءً من تاريخ":"Valid from",
  "حفظ سعر الصرف":"Save exchange rate",
  "تم حفظ سعر الصرف.":"The exchange rate is saved.",
  "لا يوجد سعر صرف محفوظ بعد. يلزم لتحويل المبالغ بين الدولار والليرة.":"No exchange rate is saved yet. It is needed to convert between dollars and pounds.",
  "الأسعار القديمة لا تتغير: كل عملية محوَّلة تحتفظ بسعر يومها.":"Old rates never change: every converted entry keeps the rate of its day.",
  "السعر":"Rate",
  "حفظ رصيد البداية":"Save opening balance",
  "بداية الحساب من شهر":"Accounting starts in month",
  "محدَّد":"Set",
  "غير محدَّد":"Not set",
  "تم حفظ رصيد البداية.":"The opening balance is saved.",
  "البنود (فئات الإيراد والمصروف)":"Items (income and expense categories)",
  "هذه هي البنود الثابتة للجداول. لأي شيء آخر أضف «بنداً مخصصاً» في الجدول اليومي باسمك.":"These are the fixed items of the sheets. For anything else add a custom item in the daily sheet.",
  "البند":"Item",
  "نوعه":"Type",
  "رسوم التسجيل والاشتراكات":"Registration and subscription fees",
  "المصروفات التشغيلية":"Operating expenses",
  "رواتب المدرسات والموظفين":"Salaries of teachers and staff",
  "الأنشطة والفعاليات":"Activities and events",
  "المشتريات والوسائل التعليمية":"Purchases and teaching aids",
  "البوفيه":"Buffet",
  "وسائل النقل (المواصلات)":"Transport",
  "الإعلانات والدعاية":"Advertising",
  "مصروفات نثرية / أخرى":"Petty cash / other",
  "إيراد · يُحسب تلقائياً من دفعات الأهل":"Income · calculated from the parents' payments",
  "مصروف":"Expense",
  "مصروف · يُحسب تلقائياً من الرواتب المدفوعة":"Expense · calculated from the paid salaries",
  "وارد أو صادر":"Income or expense",
  "تصفير البيانات المالية":"Reset the financial data",
  "الرواتب المستحقة للشهر":"Salaries owed for the month",
  "بعد تسجيل الموظفين ورواتبهم الأساسية أنشئ سطر راتب لكل موظف لهذا الشهر دفعة واحدة. يُسجَّل الدفع الفعلي في خطوة «دفع الرواتب».":"After the staff and their basic salaries are saved, create this month's salary line for every employee at once. The actual payment is recorded in the step Salary payments.",
  "إنشاء رواتب الشهر لكل الموظفين":"Create the month's salaries for all staff",
  "لا توجد رواتب جديدة لإنشائها: كل موظف لديه سطر لهذا الشهر، أو لم تُحفظ رواتب أساسية بعد.":"Nothing new to create: every employee already has a line for this month, or no basic salaries are saved yet.",
  "الأطفال وأولياء الأمور":"Children and parents",
  "دفعات أولياء الأمور تُسجَّل في خطوة «اشتراكات الأطفال» وتظهر هنا تلقائياً في بند الاشتراكات. سجّل هنا الإيرادات الأخرى (بوفيه، نقل، تبرعات...).":"Parents' payments are recorded in the step Children's fees and appear here automatically under the subscriptions item. Record the other income here (buffet, transport, donations...).",
  "تسجيل دفعة من ولي أمر":"Record a payment from a parent",
  "اليومي":"Daily",
  "الأسبوعي":"Weekly",
  "الشهري":"Monthly",
  "السنوي":"Yearly",
  "مراجعة الأسبوع":"Weekly check",
  "نظرة سريعة على الأسبوع دون إغلاقه: الوارد والصادر والدفعات والإيصالات الناقصة وجرد الصندوق. الإغلاق الملزم يتم شهرياً فقط.":"A quick look at the week without closing it: income, expenses, payments, missing receipts and the cash count. The binding closing is monthly only.",
  "أي يوم من الأسبوع":"Any day of the week",
  "التقرير السنوي":"Yearly report",
  "واردات ومصروفات كل شهر في السنة، لكل عملة على حدة. الأرقام من الجدول الشهري.":"Income and expenses of every month of the year, per currency. The numbers come from the monthly sheet.",
  "الشهر":"Month",
  "الوارد":"Income",
  "الصادر":"Expense",
  "الصافي":"Net",
  "المجموع":"Total",
  "سُجّلت حركات هذا الأسبوع":"Entries were recorded this week",
  "لم تُسجَّل أي حركة هذا الأسبوع":"No entry was recorded this week",
  "كل المصروفات لها إيصال":"All expenses have a receipt",
  "مصروفات بلا إيصال":"Expenses without a receipt",
  "أُجري جرد للصندوق":"A cash count was made",
  "لم يُجرَ جرد للصندوق":"No cash count was made",
  "لا فرق في الجرد":"No difference in the count",
  "يوجد فرق في الجرد":"There is a difference in the count",
  "أرشيف الأشهر":"Month archive",
  "لكل شهر ملف Excel كامل: الملخص والاشتراكات والرواتب والحركات مع عدد الإيصالات وجرد الصندوق. كل تصدير يُسجَّل باسم من أجراه وتاريخه. أفضل وقت للتصدير بعد إغلاق الشهر.":"Every month has a full Excel file: summary, fees, salaries, entries with the number of receipts, and cash counts. Every export is logged with who made it and when. The best time to export is after closing the month.",
  "مغلق":"Closed",
  "مفتوح":"Open",
  "لم ينتهِ بعد":"Not ended yet",
  "الحالة":"Status",
  "الأرقام عند الإغلاق":"Figures at closing",
  "آخر تصدير":"Last export",
  "ملف الشهر (Excel)":"Month file (Excel)",
  "نسخة مؤقتة":"Provisional copy",
  "تم تنزيل الملف وتسجيل التصدير.":"The file is downloaded and the export is logged.",
  "سجل التصدير":"Export log",
  "لم يُصدَّر أي شهر بعد.":"No month has been exported yet.",
  "تصدير سريع إلى Excel":"Quick export to Excel",
  "قائمة واحدة لأي شهر أو لكل السنة: الاشتراكات أو الرواتب أو سجل العمليات.":"One list for any month or the whole year: fees, salaries or the log.",
  "كل العملات":"All currencies",
  "العملة":"Currency",
  "سجل العمليات":"Log",
  "إيصال":"Receipt",
  "بلا إيصال":"No receipt",
  "إيصال ✓":"Receipt ✓",
  "إيصالات هذا السطر":"Receipts of this row",
  "يكفي رقم الإيصال أو ملف مرفوع ليُعدّ المصروف موثّقاً. الملفات: PDF أو صورة، حتى 3 ميغابايت، وبحد أقصى 5 لكل سطر.":"A receipt number or an uploaded file is enough to count the expense as documented. Files: PDF or picture, up to 3 MB, at most 5 per row.",
  "لا توجد ملفات إيصال لهذا السطر.":"No receipt files for this row.",
  "حفظ الرقم":"Save number",
  "رفع الإيصال":"Upload receipt",
  "تم حفظ رقم الإيصال.":"The receipt number is saved.",
  "تم رفع الإيصال.":"The receipt was uploaded.",
  "اختر ملف الإيصال أولاً (PDF أو صورة حتى 3 ميغابايت).":"Choose the receipt file first (PDF or picture up to 3 MB).",
  "رقم الإيصال الورقي":"Number of the paper receipt",
  "رقم الإيصال":"Receipt number",
  "ملف الإيصال":"Receipt file",
  "عرض للقراءة والطباعة فقط. للإدخال والتعديل استعمل خطوتي «الإيرادات» و«المصروفات».":"Read and print only. To enter or change data use the steps Income and Expenses.",
  "الرصيد الحالي والواردات والمصروفات وتطوّر الأشهر. الأرقام تتحدّث تلقائياً من الدفعات والرواتب والجداول.":"Current balance, income, expenses and the development of the months. The numbers update automatically from payments, salaries and sheets.",
  "قبل عدّ الصندوق راجع ما لم يكتمل بعد، ثم قارن النقود الفعلية برصيد الدفاتر.":"Before counting the cash box review what is not complete yet, then compare the real cash with the balance of the books.",
  "راجع قائمة الفحص، ثم أغلق الشهر المنتهي لتُحفظ أرقامه ويُقفل. لا يعيد فتحه إلا المدير.":"Go through the check list, then close the finished month so its figures are kept and locked. Only the administrator can open it again.",
  "خطوات المحاسبة":"Accounting steps",
  "السنة":"Year",
  "تحديث الآن من الإنترنت":"Update now from the internet",
  "العودة إلى السعر التلقائي":"Back to the automatic rate",
  "تعديل يدوي (اختياري)":"Change by hand (optional)",
  "تم تحديث سعر الصرف من الإنترنت.":"The exchange rate was updated from the internet.",
  "المصدر":"Source",
  "تلقائي":"Automatic",
  "يدوي":"Manual",
  "1 دولار (USD) =":"1 US dollar (USD) =",
  "100,000 ليرة (SYP) ≈":"100,000 pounds (SYP) ≈",
  "لم يتمكّن النظام من جلب سعر الصرف من الإنترنت الآن. جرّب «تحديث الآن»، أو أدخل السعر يدوياً.":"The system could not fetch the exchange rate from the internet right now. Try Update now, or enter the rate by hand.",
  "يعرف النظام سعر اليوم بنفسه: يجلبه من الإنترنت مرة واحدة كل يوم ويحفظه، ويحوّل به الدولار إلى ليرة والعكس. لا تحتاج إلى إدخاله. السعر اليدوي يتقدّم على التلقائي ليوم واحد فقط.":"The system knows today's rate by itself: it fetches it from the internet once a day and keeps it, and converts dollars to pounds and back with it. You do not need to enter it. A rate typed by hand wins over the automatic one for that day only.",
  "سعر اليوم مُدخل يدوياً. استعمل «العودة إلى السعر التلقائي» لاستبداله بسعر الإنترنت.":"Today's rate was entered by hand. Use Back to the automatic rate to replace it with the internet rate.",
  "تعذّر الوصول إلى مصدر أسعار الصرف الآن. جرّب بعد قليل أو أدخل السعر يدوياً.":"The exchange-rate source cannot be reached right now. Try again in a moment or enter the rate by hand.",
  "حفظ كل التعديلات":"Save all changes",
  "تم الحفظ.":"Saved.",
  "المبلغ غير صالح: اكتب أرقاماً إنجليزية فقط وبدون فواصل الآلاف (مثال: 30000.50).":"The amount is not valid: type English digits only and no thousands separators (example: 30000.50).",
  "اكتب في عدة أسطر ثم احفظها كلها بضغطة واحدة. التعديلات غير المحفوظة لا تضيع عند تحديث الجدول.":"Type in several rows, then save them all with one click. Unsaved edits are not lost when the table refreshes.",
  "الوارد":"Income",
  "الصادر":"Expense",
  "المبلغ":"Amount",
  "التفاصيل":"Details",
  "الملاحظات":"Notes",
  "اسم البند":"Item name",
  "خانتان عشريتان كحد أقصى":"two decimals at most",
  "الرقم كبير جداً":"the number is too large",
  "النص أطول من المسموح":"the text is longer than allowed",
  "قيمة غير مسموحة":"value not allowed",
  "مطلوب":"required",
  "قيمة غير صالحة":"invalid value",
  "— اختر الطفل —":"— choose the child —",
  "الطفل غير موجود في القائمة؟ إضافة الأطفال من مهام الإدارة (بوابة الإدارة).":"Child not in the list? Adding children is the work of the management (management portal).",
  "اختر الطفل من القائمة. إن لم يكن موجوداً فالإدارة هي التي تضيفه.":"Choose the child from the list. If the child is not there, the management adds them.",
  "الموظفون":"Employees",
  "الموظفون تضيفهم الإدارة، وهنا تُنشأ رواتب الشهر المستحقة":"The management adds the employees; here the salaries owed for the month are created",
  "الاشتراك الشهري والمتبقي على كل ولي أمر (الأطفال تضيفهم الإدارة)":"The monthly fee and what each parent still owes (children are added by the management)",
  "فتح بوابة الإدارة":"Open the management portal",
  "بعد أن تسجّل الإدارة الموظفين ورواتبهم الأساسية أنشئ سطر راتب لكل موظف لهذا الشهر دفعة واحدة. يُسجَّل الدفع الفعلي في خطوة «دفع الرواتب».":"After the management has saved the employees and their basic salaries, create this month's salary line for every employee at once. The actual payment is recorded in the step Salary payments.",
  "الموظفون المسجَّلون":"Saved employees",
  "لا يوجد موظفون مسجَّلون بعد. تضيفهم الإدارة.":"No employees are saved yet. The management adds them.",
  "المسمى الوظيفي":"Job title",
  "الراتب المعتاد":"Usual salary",
  "حساب الدخول":"Sign-in account",
  "إضافة الموظفين وتعديل بياناتهم ورواتبهم الأساسية وحذفهم من مهام الإدارة، وليست من مهام المحاسبة. هنا تختار من المسجَّلين فقط.":"Adding employees, changing their details and basic salaries and removing them is the work of the management, not of the accounting. Here you only pick from the saved people.",
  "إضافة الأطفال وأولياء أمورهم وتعديلهم من مهام الإدارة. هنا تحدّد الاشتراكات وتسجّل الدفعات للأطفال المسجَّلين فقط.":"Adding children and their parents and changing them is the work of the management. Here you set the fees and record the payments for saved children only.",
  "الموظف «":"The employee «",
  "الأدوار":"Roles", "العدد أكبر من المسموح":"more than allowed",
  "تصفير الجدول":"Zero the table",
  "يمسح الأجزاء المختارة من الشهر المعروض فتبدأ أرقامه من الصفر. الأطفال والموظفون والحسابات تبقى. لا يعمل على شهر مغلق ولا يمكن التراجع عنه، وكل تصفير يُسجَّل.":"Empties the chosen parts of the month shown so its figures start at zero. Children, employees and accounts stay. It does not work on a closed month, cannot be undone, and every reset is logged.",
  "تصفير الأجزاء المختارة":"Zero the chosen parts",
  "اختر شهراً محدداً أولاً.":"Choose a specific month first.",
  "اختر جزءاً واحداً على الأقل.":"Choose at least one part.",
  "كل أسطر الرواتب في هذا الشهر":"All salary lines of this month",
  "كل الاشتراكات والدفعات في هذا الشهر":"All fees and payments of this month",
  "الحركات المكتوبة في الجداول (اليومي والأسبوعي والشهري) وإيصالاتها":"The rows typed in the sheets (daily, weekly and monthly) and their receipts",
  "أسطر الرواتب":"Salary lines",
  "الاشتراكات والدفعات":"Fees and payments",
  "طباعة قسائم الرواتب (صفحة لكل موظف)":"Print payslips (one page per employee)",
  "قسيمة راتب":"Payslip",
  "لا توجد رواتب لطباعتها في هذه الفترة.":"There are no salaries to print in this period.",
  "تصفير الجداول للمدير فقط.":"Only the administrator can zero tables.",
  "جزء غير معروف.":"Unknown part.",
  "سجل هذا السطر":"History of this row",
  "لا توجد عمليات مسجّلة لهذا السطر.":"No actions are logged for this row.",
  "جارٍ التحميل…":"Loading…",
  "السجل":"History",
  "كل الأشخاص":"Everybody",
  "كل العمليات":"All actions",
  "الشخص":"Person",
  "العملية":"Action",
  "من تاريخ":"From",
  "إلى تاريخ":"To",
  "ابحث في التفاصيل":"Search the details",
  "لا توجد عمليات بهذه الشروط.":"No actions match.",
  "سجل العمليات":"Action log",
  "تصدير Excel":"Export to Excel",
  "من فعل ماذا ومتى. السجل للقراءة فقط. يرى المدير عمليات الجميع ويرى المحاسب عملياته هو.":"Who did what and when. The log is read only. The administrator sees everybody's actions; an accountant sees their own.",
  "حدّث الصفحة لترى آخر نسخة؛ إن حفظتَ مرة أخرى حلّت تعديلاتك محلّ تعديله.":"Refresh to see the latest version; if you save again your changes replace theirs.",
  "تصفير جدول":"Table zeroed",
  "مراجعة رسم":"Fee reviewed",
  "مراجعة راتب":"Salary reviewed",
  "إضافة موظف":"Employee added",
  "تعديل موظف":"Employee changed",
  "حذف موظف":"Employee removed",
  "إضافة طفل":"Child added",
  "تعديل طفل":"Child changed",
  "حذف طفل":"Child removed",
  "الزوّار":"Visitors",
  "آخر 7 أيام":"Last 7 days",
  "آخر 30 يوماً":"Last 30 days",
  "آخر 90 يوماً":"Last 90 days",
  "آخر سنة":"Last year",
  "الفترة":"Period",
  "هاتف":"Phone",
  "كمبيوتر":"Computer",
  "لوحي":"Tablet",
  "الزيارات":"Visits",
  "زيارات اليوم":"Visits today",
  "زوّار اليوم":"Visitors today",
  "زيارات آخر 7 أيام":"Visits in the last 7 days",
  "زوّار آخر 7 أيام":"Visitors in the last 7 days",
  "زيارات الفترة":"Visits in the period",
  "زوّار الفترة":"Visitors in the period",
  "الأزرق: زيارات. الأخضر: زوّار مختلفون في اليوم. الزائر يُعدّ مرة واحدة في اليوم، وعدد زوّار الفترة هو مجموع أيامها.":"Blue: visits. Green: different visitors per day. A visitor counts once a day, and the visitors of a period are the sum of its days.",
  "أكثر الصفحات":"Most visited pages",
  "الصفحة":"Page",
  "لا توجد زيارات بعد.":"No visits yet.",
  "من أين جاؤوا":"Where they came from",
  "الموقع":"Website",
  "مباشرة (رابط أو بلا مصدر)":"Direct (a link or no source)",
  "لا توجد بيانات.":"No data.",
  "الأجهزة":"Devices",
  "اللغات":"Languages",
  "اللغة":"Language",
  "من دخل إلى المنصة":"Who signed in to the platform",
  "الحساب":"Account",
  "النوع":"Type",
  "مرات الدخول":"Sign-ins",
  "آخر دخول":"Last sign-in",
  "لم يسجّل أحد الدخول في هذه الفترة.":"Nobody signed in during this period.",
  "زوّار الموقع العام مجهولون: يُعدّون ولا تُعرف أسماؤهم، ولا يُحفظ عنوانهم ولا اسم متصفحهم (بصمة تتغيّر كل يوم). الروبوتات لا تُحسب، ولا تُعدّ زيارات صفحات الدخول والإدارة. الأسماء تظهر فقط لمن سجّل الدخول إلى البوابات.":"Visitors of the public site are anonymous: they are counted, their names are not known, and neither their address nor their browser name is kept (a fingerprint that changes every day). Robots are not counted, and visits to the sign-in and admin pages are not counted. Names appear only for people who signed in to the portals.",
  "تأكيد اكتمال هذه الخطوة":"Confirm this step as complete",
  "إلغاء التأكيد":"Take the confirmation back",
  "تم تأكيد اكتمال الخطوة.":"The step is confirmed as complete.",
  "اكتملت تلقائياً من البيانات.":"Completed automatically from the data.",
  "لا يوجد تأكيد لهذه الخطوة.":"There is no confirmation for this step.",
  "هذه الخطوة تكتمل تلقائياً ولا تُؤكَّد يدوياً.":"This step completes by itself and is not confirmed by hand.",
  "تأكيد خطوة":"Step confirmed",
  "إلغاء تأكيد خطوة":"Step confirmation taken back",
  "بوابة المحاسبة":"Accounting portal",
  "لوحة المتابعة":"Overview",
  "أنجز خطوات الشهر بالترتيب، وتابع ما بقي دون أن تفوتك خطوة.":"Do the steps of the month in order and follow what is left, so no step is forgotten.",
  "الشهر مغلق":"Month closed",
  "الشهر مفتوح":"Month open",
  "خطوات مكتملة":"Steps complete",
  "نقاط تحتاج متابعة":"Points to follow up",
  "اشتراكات غير مسدّدة":"Fees not fully paid",
  "رواتب لم تُدفع":"Salaries not paid",
  "لوحة التحكم":"Control panel",
  "تسجيل الخروج":"Sign out", "مرحباً":"Hello", "تغيير كلمة المرور":"Change password",
  "اليوم":"today",
  "تم حفظ السعر الجديد":"The new rate is saved",
  "تنبيه: لا يوجد سعر محفوظ قبل هذا التاريخ، فاستُعمل أقدم سعر محفوظ بتاريخ":"Note: there is no stored rate before this date, so the oldest stored rate was used, dated",
  "سجل النظام":"System log", "ابحث في السجل (المستخدم، العملية، التفاصيل)":"Search the log (user, action, details)", "لا توجد عمليات مسجّلة بعد.":"No actions recorded yet.",
  "آخر ٥٠٠ عملية في المحاسبة والرسوم: من أجراها ومتى وماذا تغيّر. السجل للقراءة فقط ولا يمكن تعديله.":"The last 500 actions in accounting and fees: who did them, when and what changed. The log is read only.",
  "بوابة الإدارة":"Management portal", "إدارة":"Management", "إدارة (الأطفال والاعتماد والإعلانات)":"Management (children, approvals, notices)",
  "إضافة طفل":"Add a child", "الأطفال وأولياء الأمور":"Children and parents", "بيانات الطفل":"Child details", "اسم الطفل":"Child's name", "تاريخ الميلاد":"Date of birth",
  "الأب":"Father", "الأم":"Mother", "ولي أمر آخر":"Another guardian", "الصفة":"Role", "الهاتف":"Phone", "حساب بوابة الأهل":"Parents' portal account",
  "حفظ الطفل":"Save child", "＋ حفظ الطفل":"＋ Save child", "الأب والأم":"Father and mother", "ولي أمر واحد":"One parent", "حذف من القائمة":"Remove from list",
  "أضف الأب والأم، أو واحداً منهما فقط. اترك خانات الآخر فارغة إن لم يكن موجوداً.":"Add the father and the mother, or only one of them. Leave the other's fields empty if there is none.",
  "ابحث باسم الطفل أو ولي الأمر":"Search by child or parent name", "الأطفال":"Children",
  "استرداد":"Refund", "تسجيل استرداد للأهل":"Record a refund to the parents", "تسجيل الاسترداد":"Record refund", "السبب":"Reason", "سُلّم إلى":"Handed to",
  "تاريخ الاسترداد":"Refund date", "سبب الاسترداد":"Reason for the refund", "لمن سُلّم المبلغ":"Who received the money",
  "إغلاق الأشهر":"Closing months", "إغلاق الشهر":"Close month", "إعادة فتح":"Reopen", "مغلق":"Closed", "مفتوح":"Open", "لم ينتهِ بعد":"Not finished yet",
  "جرد الصندوق":"Cash count", "تسجيل الجرد":"Record count", "تاريخ الجرد":"Count date", "آخر العمليات":"Latest activity",
  "رواتب لم تُدفع هذا الشهر":"Salaries not paid this month",
  "إعدادات الموقع":"Website settings",
  "ما تغيّره هنا يظهر مباشرة في الموقع بعد الحفظ.":"What you change here appears on the website right after saving.",
  "هكذا يظهر الشريط":"How the banner looks",
  "— الشريط مخفي —":"— Banner hidden —",
  "تراجع عن التغييرات":"Discard changes",
  "كل التغييرات محفوظة":"All changes are saved",
  "لديك تغييرات غير محفوظة":"You have unsaved changes",
  "تحقق من الحقول المعلَّمة قبل الحفظ":"Check the marked fields before saving",
  "رقم الواتساب غير صالح (من 8 إلى 15 رقماً).":"The WhatsApp number is not valid (8 to 15 digits).",
  "عنوان البريد غير صالح.":"The email address is not valid.",
  "رسالة قصيرة تظهر فوق الموقع، مثل فتح التسجيل أو عطلة رسمية. اتركها فارغة لإخفاء الشريط.":"A short message shown above the website, such as open enrolment or a public holiday. Leave empty to hide it.",
  "تظهر في الموقع وفي أزرار الاتصال. إن تُرك حقل فارغاً يُستخدم الإعداد الافتراضي للروضة.":"Shown on the website and in the contact buttons. If a field is left empty, the kindergarten's default is used.",
  "الرابط الكامل لصفحة الروضة، ويبدأ بـ https":"The full link to the kindergarten's page, starting with https",
  "خيارات متقدمة، نادراً ما تحتاجها.":"Advanced options you will rarely need.",
  "يخفي الخبر الذي جاء مع الموقع، حين تنشر أخبارك الخاصة.":"Hides the news item that came with the website, once you publish your own.",
  "يخفي الصور الجاهزة، حين ترفع صور الروضة الحقيقية.":"Hides the ready-made photos, once you upload the kindergarten's real ones.",
  "نص الشريط":"Banner text",
  "يظهر في أعلى كل صفحات الموقع. اتركه فارغاً لإخفاء الشريط.":"Shown at the top of every page. Leave empty to hide the banner.",
  "يظهر للزوار كما تكتبه هنا.":"Shown to visitors exactly as typed here.",
  "رقم الواتساب":"WhatsApp number",
  "بالصيغة الدولية وأرقام فقط. يُملأ تلقائياً من رقم الهاتف إن تركته فارغاً.":"International format, digits only. Filled in from the phone number if left empty.",
  "اتركه فارغاً لإخفاء البريد من الموقع.":"Leave empty to hide the email from the website.",
  "شريط الإعلان":"Announcement banner",
  "رسالة قصيرة تظهر فوق الموقع، مثل فتح التسجيل أو عطلة رسمية.":"A short message shown above the website, such as open enrolment or a public holiday.",
  "التواصل وأوقات الدوام":"Contact and opening hours",
  "هذه البيانات تظهر في الموقع وفي أزرار الاتصال. إن تُرك حقل فارغاً يُستخدم الإعداد الافتراضي للروضة.":"Shown on the website and in the contact buttons. If a field is left empty, the kindergarten's default is used.",
  "حسابات التواصل الاجتماعي":"Social media",
  "يجب أن يكون الرابط كاملاً ويبدأ بـ https":"The link must be complete and start with https",
  "خيارات متقدمة: المحتوى الأصلي للموقع":"Advanced: original website content",
  "اخفِ الأخبار والصور التي جاءت مع الموقع، حين تنشر أخبارك وصورك الخاصة.":"Hide the news and photos that came with the website once you publish your own.",
  "المحتوى الأصلي للموقع":"Original website content",
  "إخفاء الخبر الافتتاحي الأصلي":"Hide the original opening announcement",
  "إخفاء الصور الأصلية في المعرض":"Hide the original gallery images",
  "الصور":"Photos",
  "الفيديو":"Videos",
  "الأخبار":"News",
  "الإعدادات":"Settings",
  "حسابات المنصة":"Platform accounts",
  "طلبات أولياء الأمور والمعلمات":"Parent and teacher accounts",
  "أنشئ حساب معلمة أو محاسب جديداً. يكون الحساب مفعّلاً فوراً.":"Create a teacher account. It will remain pending until you activate it.",
  "كلمة المرور الأولية (12 محرفاً على الأقل)":"Initial password (at least 12 characters)",
  "إنشاء حساب المعلمة":"Create teacher account",
  "الحسابات بانتظار التفعيل":"Accounts awaiting activation",
  "نشط":"Active",
  "بانتظار التفعيل":"Pending approval",
  "موقوف":"Disabled",
  "ولي أمر":"Parent",
  "معلمة":"Teacher",
  "تفعيل الحساب":"Activate account",
  "إيقاف الحساب":"Disable account",
  "لا توجد حسابات أولياء أمور أو معلمات.":"No parent or teacher accounts yet.",
  "تم إنشاء الحساب وتفعيله. يمكن تسجيل الدخول الآن.":"Teacher account created and active. She can sign in now.",
  "تم تحديث حالة الحساب.":"Account status updated.",
  "الاسم أو كلمة المرور غير صالحة.":"The username or password is invalid.",
  "هذا الاسم مستخدم بالفعل.":"That username is already in use.",
  "بانتظار موافقة إدارة الروضة.":"Waiting for kindergarten admin approval.",
  "تم تسجيل الحساب بنجاح. سيُفعّل بعد موافقة الإدارة.":"Account registered. It will be activated after admin approval.",
  "اسم المستخدم يحتوي على أحرف غير مدعومة.":"The username contains unsupported characters.",
  "لم يتم تهيئة أدوار المنصة. نفّذ ترحيلات قاعدة البيانات.":"Platform roles are not initialized. Run database migrations.",
  "لم يتم العثور على حساب ولي أمر أو معلمة.":"Parent or teacher account not found.",
  "تعذر إنشاء الحساب. تحقق من الاسم وكلمة المرور.":"Could not create account. Check the username and password.",
  "لوحة تحكم روضة زهرة المدائن":"Zahrat Al-Madayn Admin",
  "خروج":"Sign out",
  "عرض الموقع":"View website",
  "دخول":"Sign in",
  "دخول المسؤول":"Admin sign in",
  "اسم المستخدم":"Username",
  "كلمة المرور":"Password",
  "اختر ملف فيديو أولاً.":"Choose a video file first.",
  "اختر صورة واحدة أو أكثر أولاً.":"Choose one or more photos first.",
  "جارٍ الرفع":"Uploading",
  "تم رفع":"Uploaded",
  "صورة":"photo",
  "فيديو":"video",
  "صورة واحدة أو أكثر، تُصغَّر تلقائياً":"Photos (you can select multiple; they are resized automatically)",
  "ملف الفيديو (MP4 أو WebM، حتى 25 ميغابايت)":"Video file (MP4 or WebM, up to 25 MB)",
  "الصور (يمكن اختيار عدة صور، تُصغَّر تلقائياً)":"Photos (select multiple; they are resized automatically)",
  "تعليق":"Caption",
  "حذف":"Delete",
  "رفع الفيديو":"Upload video",
  "رفع الصور":"Upload photos",
  "رفع فيديو جديد":"Upload a new video",
  "رفع صور جديدة":"Upload new photos",
  "الفيديوهات المنشورة":"Published videos",
  "الصور المنشورة":"Published photos",
  "خبر":"News",
  "نشر الخبر":"Publish news",
  "حفظ التعديل":"Save changes",
  "خبر جديد":"New announcement",
  "تعديل الخبر":"Edit announcement",
  "اكتب العنوان والنص.":"Enter a title and text.",
  "تم نشر الخبر في الموقع.":"The announcement was published.",
  "الأخبار المنشورة":"Published news",
  "تعديل":"Edit",
  "مثال: يوم الرسم في الروضة":"Example: Art day at kindergarten",
  "مثال: التسجيل مفتوح للعام الدراسي الجديد":"Example: Enrollment is open for the new school year",
  "اتركه فارغاً لإخفاء الشريط.":"Leave blank to hide the banner.",
  "مثال: من الأحد إلى الخميس، 8:00 إلى 13:00":"Example: Sunday to Thursday, 8:00 AM to 1:00 PM",
  "مثال: 963985122704":"Example: 963985122704",
  "تم حفظ الإعدادات وطُبّقت على الموقع.":"Settings saved and applied to the website.",
  "أدخل اسم المستخدم وكلمة المرور.":"Enter your username and password.",
  "أدخل بيانات دخول لوحة التحكم التي أُعدّت على الخادم.":"Enter the admin login credentials configured on the server.",
  "اضغط مرة أخرى للتأكيد":"Click again to confirm",
  "التعليق":"Caption"
};

try{ localStorage.removeItem("zm-gh"); }catch(e){}
function up(name){ return FILE_RE.test(name || "") ? API_BASE + "/api/assets/" + name : ""; }
function sOf(v, n){ return typeof v === "string" ? v.slice(0, n) : ""; }
function byNew(a, b){ return (b.ts || 0) - (a.ts || 0); }
function uiText(value){ return ADMIN_LANG === "en" ? (EN_TEXT[value] || value) : value; }
function h(tag, a, kids){
  var e = document.createElement(tag);
  if(a) Object.keys(a).forEach(function(k){
    if(k === "class") e.className = a[k];
    else if(k === "text"){ e.dataset.arText = a[k]; e.textContent = uiText(a[k]); }
    else if(k === "placeholder" || k === "aria-label" || k === "title"){ e.dataset["ar" + k.split("-").map(function(part){ return part.charAt(0).toUpperCase() + part.slice(1); }).join("")] = a[k]; e.setAttribute(k, uiText(a[k])); }
    else if(k.slice(0,2) === "on") e.addEventListener(k.slice(2), a[k]); else e.setAttribute(k, a[k]);
  });
  (kids || []).forEach(function add(c){
    if(Array.isArray(c)) c.forEach(add);
    else if(typeof c === "string"){ var span = document.createElement("span"); span.dataset.arText = c; span.textContent = uiText(c); e.appendChild(span); }
    else if(c != null) e.append(c);
  });
  return e;
}
function fail(message){ return new Error(message); }
var SERVER_AR = {
  "Too many sign-in attempts. Try again later.":"محاولات دخول كثيرة. حاول مجدداً بعد 15 دقيقة.",
  "Password is too short.":"كلمة المرور قصيرة (12 حرفاً على الأقل).",
  "Password is too common or too easy to guess.":"كلمة المرور شائعة وسهلة التخمين. اختر كلمة أصعب.",
  "Password must not contain the username.":"يجب ألا تحتوي كلمة المرور على اسم المستخدم.",
  "Password must not be only digits.":"يجب ألا تكون كلمة المرور أرقاماً فقط.",
  "Password needs at least 6 different characters.":"استخدم 6 محارف مختلفة على الأقل.",
  "The current password is incorrect.":"كلمة المرور الحالية غير صحيحة.",
  "Choose a new password that differs from the current one.":"اختر كلمة مرور جديدة تختلف عن الحالية.",
  "ADMIN_PASSWORD is too weak. Set a password with at least 12 characters on the server.":"كلمة مرور المدير ضعيفة. عيّن كلمة مرور من 12 حرفاً على الأقل على الخادم (ADMIN_PASSWORD)."
};
function errText(e){
  if(e.message && SERVER_AR[e.message]) return SERVER_AR[e.message];
  if(e.message && /[\u0600-\u06FF]/.test(e.message)) return uiText(e.message);
  var arabicMessage = Object.keys(EN_TEXT).find(function(key){ return EN_TEXT[key] === e.message; });
  if(arabicMessage) return uiText(arabicMessage);
  if(e instanceof TypeError) return uiText("تعذّر الاتصال بالخادم. تحقق من إعداد رابط API واتصال الإنترنت.");
  if(e.message && e.message !== "تعذّر تنفيذ العملية على الخادم.") return e.message;
  return uiText("تعذّر تنفيذ العملية. حاول مرة أخرى.");
}
function setUiText(el, text){
  delete el.dataset.enText;
  if(ADMIN_LANG === "en"){
    Object.keys(EN_TEXT).some(function(ar){ if(EN_TEXT[ar] === text){ text = ar; return true; } return false; });
  }
  el.dataset.arText = text;
  el.textContent = uiText(text);
}
function setMsg(el, text, kind){
  setUiText(el, text); el.className = "a-msg" + (kind ? " " + kind : "");
  // a result that appears above or below what the person is looking at is also shown at the bottom of the screen
  if(kind && typeof accToast === "function" && el.getBoundingClientRect){
    var box = el.getBoundingClientRect();
    if(box.bottom < 0 || box.top > window.innerHeight) accToast(el.textContent, kind);
  }
}
function setMsgLanguages(el, ar, en, kind){
  el.dataset.arText = ar;
  el.dataset.enText = en;
  el.textContent = ADMIN_LANG === "en" ? en : ar;
  el.className = "a-msg" + (kind ? " " + kind : "");
}
function applyAdminLanguage(){
  document.documentElement.lang = ADMIN_LANG;
  document.documentElement.dir = ADMIN_LANG === "ar" ? "rtl" : "ltr";
  document.body.classList.toggle("lat", ADMIN_LANG === "en");
  document.title = uiText("لوحة تحكم روضة زهرة المدائن");
  document.querySelectorAll("[data-ar-text]").forEach(function(el){ el.textContent = ADMIN_LANG === "en" && el.dataset.enText ? el.dataset.enText : uiText(el.dataset.arText); });
  document.querySelectorAll("[data-ar-placeholder]").forEach(function(el){ el.setAttribute("placeholder", uiText(el.dataset.arPlaceholder)); });
  document.querySelectorAll("[data-ar-aria-label]").forEach(function(el){ el.setAttribute("aria-label", uiText(el.dataset.arAriaLabel)); });
  document.querySelectorAll("[data-ar-title]").forEach(function(el){ el.setAttribute("title", uiText(el.dataset.arTitle)); });
  document.querySelectorAll(".a-lang button").forEach(function(button){ button.setAttribute("aria-pressed", String((button.textContent === "ع" ? "ar" : "en") === ADMIN_LANG)); });
}
function languageSwitch(){
  var group = h("div", {class:"a-lang p-lang", role:"group", "aria-label":"اللغة / Language"});
  [["ar","العربية"],["en","English"]].forEach(function(choice){
    var button = h("button", {type:"button", lang:choice[0], "aria-pressed":String(ADMIN_LANG === choice[0]), text:choice[1]});
    button.addEventListener("click", function(){ setAdminLanguage(choice[0]); });
    group.appendChild(button);
  });
  return group;
}
function setAdminLanguage(lang){
  if(lang !== "ar" && lang !== "en" || lang === ADMIN_LANG) return;
  ADMIN_LANG = lang;
  try{ localStorage.setItem("zm-admin-lang", lang); }catch(e){}
  applyAdminLanguage();
}

async function request(path, options){
  options = options || {};
  var headers = new Headers(options.headers || {});
  if(ADMIN_TOKEN) headers.set("Authorization", "Bearer " + ADMIN_TOKEN);
  if(options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  var response = await fetch(API_BASE + path, Object.assign({}, options, {headers: headers}));
  var result = null;
  try{ result = await response.json(); }catch(e){}
  if(!response.ok){
    var detail = result && result.detail;
    if(Array.isArray(detail)) throw fail(validationText(detail));
    throw fail(detail ? detail : "تعذّر تنفيذ العملية على الخادم.");
  }
  return result;
}
/* The server's list of field problems, said in words the person can act on. */
function validationText(problems){
  var NAMES = {income:"الوارد", expense:"الصادر", amount:"المبلغ", details:"التفاصيل", note:"الملاحظات", person:"الاسم", item_label:"اسم البند", receipt_no:"رقم الإيصال", base:"الراتب", bonus:"المكافأة", advance:"السلفة", deduction:"الخصم", name:"الاسم", paid_by:"من سلّم الراتب", roles:"الأدوار"};
  return problems.map(function(item){
    var field = item.loc && item.loc.length ? item.loc[item.loc.length - 1] : "";
    var type = String(item.type || "");
    var why = /decimal_max_places|decimal_places/.test(type) ? "خانتان عشريتان كحد أقصى" : /max_digits|decimal_max_digits|whole_digits/.test(type) ? "الرقم كبير جداً" :
      /string_too_long/.test(type) ? "النص أطول من المسموح" : /too_long/.test(type) ? "العدد أكبر من المسموح" : /greater_than|less_than|too_small|too_big/.test(type) ? "قيمة غير مسموحة" : /missing/.test(type) ? "مطلوب" : "قيمة غير صالحة";
    return (NAMES[field] || field || "") + (NAMES[field] || field ? ": " : "") + why;
  }).join("، ");
}
async function api(method, url, body){
  var resource = url.replace("/admin/api/", "");
  var path = "/api/admin/" + resource;
  return request(path, {
    method: method,
    body: body == null ? undefined : (body instanceof FormData ? body : JSON.stringify(body))
  });
}
var fill = null;
async function reload(){ DATA = await api("GET", "/admin/api/content"); if(fill) fill(); }
function twoStep(label, action){
  var b = h("button", {type:"button", class:"a-btn danger", text:label}), armed = false, t;
  b.addEventListener("click", function(){
    if(!armed){ armed = true; setUiText(b, "اضغط مرة أخرى للتأكيد"); t = setTimeout(function(){ armed = false; setUiText(b, label); }, 4000); return; }
    clearTimeout(t); b.disabled = true; action().then(null, function(e){ b.disabled = false; armed = false; setUiText(b, label); alert(errText(e)); });
  });
  return b;
}

function tabMedia(kind){
  var isVid = kind === "video", msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var file = h("input", {type:"file", id:"a-file", accept: isVid ? "video/mp4,video/webm" : "image/jpeg,image/png,image/webp,image/gif"});
  if(!isVid) file.multiple = true;
  var cap = h("input", {type:"text", id:"a-cap", maxlength:"120", placeholder:"مثال: يوم الرسم في الروضة"});
  var go = h("button", {type:"button", class:"a-btn sun", text: isVid ? "رفع الفيديو" : "رفع الصور"});
  go.addEventListener("click", async function(){
    var files = Array.prototype.slice.call(file.files || []);
    if(!files.length){ setMsg(msg, isVid ? "اختر ملف فيديو أولاً." : "اختر صورة واحدة أو أكثر أولاً.", "err"); return; }
    go.disabled = true; var done = 0;
    try{
      for(var i = 0; i < files.length; i++){
        setMsgLanguages(msg, "جارٍ الرفع " + (i + 1) + " من " + files.length + "…", "Uploading " + (i + 1) + " of " + files.length + "…");
        var fd = new FormData(); fd.append("file", files[i]); fd.append("kind", kind); fd.append("caption", cap.value);
        await api("POST", "/admin/api/gallery", fd); done++;
      }
      setMsgLanguages(msg, "تم رفع " + done + (isVid ? " فيديو" : " صورة") + " وظهر في الموقع.", done + (isVid ? " video(s) uploaded and published." : " photo(s) uploaded and published."), "ok");
      file.value = ""; cap.value = ""; await reload();
    }catch(e){ setMsg(msg, (done ? (ADMIN_LANG === "en" ? done + " uploaded. " : "تم رفع " + done + " فقط. ") : "") + errText(e), "err"); }
    go.disabled = false;
  });
  var form = h("div", {class:"a-card"}, [
    h("h3", {text: isVid ? "رفع فيديو جديد" : "رفع صور جديدة"}),
    h("label", {for:"a-file", text: isVid ? "ملف الفيديو (MP4 أو WebM، حتى 25 ميغابايت)" : "الصور (يمكن اختيار عدة صور، تُصغَّر تلقائياً)"}), file,
    h("label", {for:"a-cap", text:"تعليق يظهر تحت العنصر (اختياري)"}), cap,
    isVid ? h("p", {class:"hint", text:"فيديوهات الهاتف بصيغة MOV لا تعمل. صدّرها بصيغة MP4."}) : null,
    h("div", {class:"a-row"}, [go]), msg]);
  var list = h("div", {class:"a-grid"});
  fill = function(){
    list.innerHTML = "";
    var items = DATA.gallery.filter(function(g){ return isVid ? g.kind === "video" : g.kind !== "video"; }).sort(byNew);
    if(!items.length){ list.appendChild(h("p", {class:"hint", text: isVid ? "لا توجد فيديوهات مرفوعة بعد." : "لا توجد صور مرفوعة بعد."})); return; }
    items.forEach(function(g){
      var media = isVid ? h("video", {src:up(g.asset), controls:"", preload:"metadata"}) : h("img", {src:up(g.asset), alt:sOf(g.caption, 120), loading:"lazy"});
      var caption = h("input", {type:"text", maxlength:"120", value:sOf(g.caption, 120), placeholder:"تعليق", "aria-label":"التعليق"});
      caption.addEventListener("change", function(){ api("PATCH", "/admin/api/gallery/" + g.id, {caption:caption.value}).catch(function(e){ alert(errText(e)); }); });
      list.appendChild(h("div", {class:"a-item"}, [media, h("div", {class:"b"}, [caption, twoStep("حذف", function(){ return api("DELETE", "/admin/api/gallery/" + g.id).then(reload); })])]));
    });
  };
  fill();
  return h("div", {}, [form, h("h3", {text:isVid ? "الفيديوهات المنشورة" : "الصور المنشورة"}), list]);
}

function tabNews(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"}), editing = null;
  var tag = h("input", {type:"text", id:"n-tag", maxlength:"30", value:"خبر"}), title = h("input", {type:"text", id:"n-title", maxlength:"120"});
  var text = h("textarea", {id:"n-text", maxlength:"1500"}), file = h("input", {type:"file", id:"n-file", accept:"image/jpeg,image/png,image/webp,image/gif"});
  var rm = h("input", {type:"checkbox", id:"n-rm"}), rmRow = h("label", {class:"a-check", hidden:""}, [rm, "حذف الصورة الحالية"]);
  var save = h("button", {type:"button", class:"a-btn sun", text:"نشر الخبر"}), cancel = h("button", {type:"button", class:"a-btn ghost", text:"إلغاء التعديل", hidden:""});
  var head = h("h3", {text:"خبر جديد"});
  function reset(){ editing = null; tag.value = "خبر"; title.value = ""; text.value = ""; file.value = ""; rm.checked = false; rmRow.hidden = true; cancel.hidden = true; setUiText(save, "نشر الخبر"); setUiText(head, "خبر جديد"); }
  cancel.addEventListener("click", function(){ reset(); setMsg(msg, ""); });
  save.addEventListener("click", async function(){
    if(!title.value.trim() || !text.value.trim()){ setMsg(msg, "اكتب العنوان والنص.", "err"); return; }
    save.disabled = true;
    try{
      var fd = new FormData(); fd.append("tag", tag.value); fd.append("title", title.value); fd.append("text", text.value);
      if(file.files && file.files[0]) fd.append("file", file.files[0]);
      if(rm.checked) fd.append("remove_image", "1");
      await api("POST", editing ? "/admin/api/news/" + editing.id : "/admin/api/news", fd);
      reset(); setMsg(msg, "تم نشر الخبر في الموقع.", "ok"); await reload();
    }catch(e){ setMsg(msg, errText(e), "err"); }
    save.disabled = false;
  });
  var form = h("div", {class:"a-card"}, [head,
    h("label", {for:"n-tag", text:"التصنيف (كلمة قصيرة)"}), tag, h("label", {for:"n-title", text:"العنوان"}), title,
    h("label", {for:"n-text", text:"النص"}), text, h("label", {for:"n-file", text:"صورة (اختيارية)"}), file, rmRow,
    h("div", {class:"a-row"}, [save, cancel]), msg]);
  var list = h("div", {class:"a-card"});
  fill = function(){
    list.innerHTML = ""; list.appendChild(h("h3", {text:"الأخبار المنشورة"}));
    var items = DATA.news.slice().sort(byNew);
    if(!items.length) list.appendChild(h("p", {class:"hint", text:"لا توجد أخبار مضافة."}));
    items.forEach(function(n){
      var img = up(n.asset) ? h("img", {src:up(n.asset), alt:""}) : null;
      var edit = h("button", {type:"button", class:"a-btn ghost", text:"تعديل"});
      edit.addEventListener("click", function(){
        editing = n; tag.value = sOf(n.tag, 30); title.value = sOf(n.title, 120); text.value = sOf(n.text, 1500); file.value = ""; rm.checked = false;
        rmRow.hidden = !n.asset; cancel.hidden = false; setUiText(save, "حفظ التعديل"); setUiText(head, "تعديل الخبر"); form.scrollIntoView({behavior:"smooth", block:"start"});
      });
      list.appendChild(h("div", {class:"a-news"}, [img, h("div", {class:"t"}, [h("b", {text:sOf(n.title, 120)}), h("span", {text:sOf(n.tag, 30)})]),
        h("div", {class:"a-row", style:"margin:0"}, [edit, twoStep("حذف", function(){ return api("DELETE", "/admin/api/news/" + n.id).then(reload); })])]));
    });
  };
  fill();
  return h("div", {}, [form, list]);
}

function tabSettings(){
  var s = DATA.settings, msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var ICONS = {
    banner:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11v2a1 1 0 0 0 1 1h2l5 4V6L6 10H4a1 1 0 0 0-1 1zm13.5 1a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v2.1a7 7 0 0 1 0 13.4v2.1a9 9 0 0 0 0-17.6z"/></svg>',
    contact:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1z"/></svg>',
    social:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10.6 13.4a1 1 0 0 1 0-1.4l3-3a3 3 0 0 1 4.2 4.2l-2 2a3 3 0 0 1-3.4.6l1.2-1.2a1 1 0 0 0 .8-.3l2-2a1 1 0 0 0-1.4-1.4l-3 3a1 1 0 0 1-1.4.5zm2.8-2.8a1 1 0 0 1 0 1.4l-3 3a3 3 0 0 1-4.2-4.2l2-2a3 3 0 0 1 3.4-.6l-1.2 1.2a1 1 0 0 0-.8.3l-2 2a1 1 0 0 0 1.4 1.4l3-3a1 1 0 0 1 1.4-.5z"/></svg>',
    adv:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.4 13a7.6 7.6 0 0 0 0-2l2-1.6-2-3.4-2.4 1a7.4 7.4 0 0 0-1.7-1L15 3.4h-4L10.7 6a7.4 7.4 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.6a7.6 7.6 0 0 0 0 2l-2 1.6 2 3.4 2.4-1c.5.4 1.1.7 1.7 1l.3 2.6h4l.3-2.6c.6-.3 1.2-.6 1.7-1l2.4 1 2-3.4zM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"/></svg>'
  };
  var saveBtn = h("button", {type:"button", class:"a-btn sun save", text:"حفظ الإعدادات", disabled:"disabled"});
  var resetBtn = h("button", {type:"button", class:"a-btn ghost", text:"تراجع عن التغييرات", hidden:"hidden"});
  var state = h("span", {class:"a-set-state", text:"كل التغييرات محفوظة"});
  var bar = h("div", {class:"a-set-bar"}, [state, h("div", {class:"a-row", style:"margin:0"}, [resetBtn, saveBtn])]);
  var fields = [];
  function field(id, label, key, type, ph, hint, opts){
    opts = opts || {};
    var input = h("input", {type:type || "text", id:id, value:sOf(s[key], 300), placeholder:ph || "", maxlength:String(opts.max || 300), autocomplete:"off"});
    if(opts.ltr) input.dir = "ltr";
    var err = h("p", {class:"a-set-err", role:"alert", hidden:"hidden"});
    var f = {key:key, input:input, err:err, check:opts.check, saved:input.value, node:null};
    f.node = h("div", {class:"a-set-field"}, [h("label", {for:id, text:label}), input, hint ? h("p", {class:"hint", text:hint}) : null, err]);
    input.addEventListener("input", refresh);
    fields.push(f);
    return f;
  }
  var urlCheck = function(v){ return !v || /^https:\/\/\S+\.\S+/i.test(v) ? "" : "يجب أن يكون الرابط كاملاً ويبدأ بـ https"; };
  var F = {
    announce: field("s-ann", "نص الشريط", "announce", "text", "مثال: التسجيل مفتوح للعام الدراسي الجديد", "", {max:200}),
    phone: field("s-ph", "رقم الهاتف الظاهر", "phone", "text", "+963 985 122 704", "يظهر للزوار كما تكتبه هنا.", {ltr:true}),
    whatsapp: field("s-wa", "رقم الواتساب", "whatsapp", "text", "963985122704", "بالصيغة الدولية وأرقام فقط. يُملأ تلقائياً من رقم الهاتف إن تركته فارغاً.", {ltr:true, check:function(v){ var d = v.replace(/\D/g, ""); return !d || (d.length >= 8 && d.length <= 15) ? "" : "رقم الواتساب غير صالح (من 8 إلى 15 رقماً)."; }}),
    email: field("s-em", "البريد الإلكتروني", "email", "email", "info@zahratalmadain.com", "اتركه فارغاً لإخفاء البريد من الموقع.", {ltr:true, check:function(v){ return !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? "" : "عنوان البريد غير صالح."; }}),
    hours: field("s-hr", "أوقات الدوام", "hours", "text", "من الأحد إلى الخميس، 8:00 إلى 13:00", "", {max:200}),
    facebook: field("s-fb", "رابط صفحة فيسبوك", "facebook", "url", "https://www.facebook.com/…", "", {ltr:true, check:urlCheck}),
    instagram: field("s-ig", "رابط صفحة إنستغرام", "instagram", "url", "https://www.instagram.com/…", "", {ltr:true, check:urlCheck})
  };
  // live preview of the banner as visitors see it, plus a counter
  var bannerText = h("span", {class:"a-banner-text"});
  var banner = h("div", {class:"a-banner-prev"}, [h("small", {text:"هكذا يظهر الشريط"}), bannerText]);
  var counter = h("span", {class:"a-set-count", dir:"ltr"});
  F.announce.node.appendChild(counter);
  F.announce.node.appendChild(banner);
  // the WhatsApp number follows the phone number until it has been typed by hand
  var waByHand = !!F.whatsapp.input.value;
  F.whatsapp.input.addEventListener("input", function(){ waByHand = !!F.whatsapp.input.value; });
  F.phone.input.addEventListener("input", function(){
    var digits = F.phone.input.value.replace(/\D/g, "");
    if(!waByHand) F.whatsapp.input.value = digits.length >= 8 && digits.length <= 15 ? digits : "";
  });
  function toggle(label, hint, on){
    var box = h("input", {type:"checkbox", role:"switch"}); box.checked = !!on; box.dataset.saved = box.checked ? "1" : "";
    box.addEventListener("change", refresh);
    return {box:box, node:h("label", {class:"a-switch"}, [box, h("span", {class:"track"}), h("span", {class:"txt"}, [h("b", {text:label}), h("small", {text:hint})])])};
  }
  var hn = toggle("إخفاء الخبر الافتتاحي الأصلي", "يخفي الخبر الذي جاء مع الموقع، حين تنشر أخبارك الخاصة.", s.hideDefaultNews);
  var hg = toggle("إخفاء الصور الأصلية في المعرض", "يخفي الصور الجاهزة، حين ترفع صور الروضة الحقيقية.", s.hideDefaultGallery);
  function section(icon, title, hint, nodes){
    var ic = h("span", {class:"a-set-ic"}); ic.innerHTML = ICONS[icon];
    return h("section", {class:"a-card a-set-sec"}, [h("header", {}, [ic, h("div", {}, [h("h3", {text:title}), hint ? h("p", {class:"hint", text:hint}) : null])]), h("div", {class:"a-set-grid"}, nodes)]);
  }
  function refresh(){
    var dirty = hn.box.checked !== !!hn.box.dataset.saved || hg.box.checked !== !!hg.box.dataset.saved, bad = false;
    fields.forEach(function(f){
      var v = f.input.value.trim(), problem = f.check ? f.check(v) : "";
      f.err.hidden = !problem; setUiText(f.err, problem); f.input.classList.toggle("bad", !!problem); f.input.setAttribute("aria-invalid", problem ? "true" : "false");
      if(problem) bad = true;
      if(v !== f.saved.trim()) dirty = true;
    });
    var text = F.announce.input.value.trim();
    counter.textContent = text.length + " / 200";
    setUiText(bannerText, text || "— الشريط مخفي —"); banner.classList.toggle("off", !text);
    saveBtn.disabled = !dirty || bad; resetBtn.hidden = !dirty;
    bar.classList.toggle("dirty", dirty);
    setUiText(state, bad ? "تحقق من الحقول المعلَّمة قبل الحفظ" : dirty ? "لديك تغييرات غير محفوظة" : "كل التغييرات محفوظة");
    if(dirty) setMsg(msg, "", "");
  }
  resetBtn.addEventListener("click", function(){
    fields.forEach(function(f){ f.input.value = f.saved; });
    [hn, hg].forEach(function(t){ t.box.checked = !!t.box.dataset.saved; });
    waByHand = !!F.whatsapp.input.value; refresh();
  });
  saveBtn.addEventListener("click", async function(){
    var body = {hideDefaultNews:hn.box.checked, hideDefaultGallery:hg.box.checked};
    Object.keys(F).forEach(function(k){ body[k] = F[k].input.value.trim(); });
    body.whatsapp = body.whatsapp.replace(/\D/g, "");
    F.whatsapp.input.value = body.whatsapp;
    saveBtn.disabled = true;
    try{
      DATA.settings = await api("PUT", "/admin/api/settings", body);
      fields.forEach(function(f){ f.saved = f.input.value.trim(); });
      [hn, hg].forEach(function(t){ t.box.dataset.saved = t.box.checked ? "1" : ""; });
      refresh(); setMsg(msg, "تم حفظ الإعدادات وطُبّقت على الموقع.", "ok");
    }catch(e){ setMsg(msg, errText(e), "err"); saveBtn.disabled = false; }
  });
  fill = null;
  var page = h("div", {class:"a-settings"}, [
    h("div", {class:"a-set-head"}, [h("h2", {text:"إعدادات الموقع"}), h("p", {class:"hint", text:"ما تغيّره هنا يظهر مباشرة في الموقع بعد الحفظ."})]),
    section("banner", "شريط الإعلان", "رسالة قصيرة تظهر فوق الموقع، مثل فتح التسجيل أو عطلة رسمية. اتركها فارغة لإخفاء الشريط.", [F.announce.node]),
    section("contact", "التواصل وأوقات الدوام", "تظهر في الموقع وفي أزرار الاتصال. إن تُرك حقل فارغاً يُستخدم الإعداد الافتراضي للروضة.", [F.phone.node, F.whatsapp.node, F.email.node, F.hours.node]),
    section("social", "حسابات التواصل الاجتماعي", "الرابط الكامل لصفحة الروضة، ويبدأ بـ https", [F.facebook.node, F.instagram.node]),
    section("adv", "المحتوى الأصلي للموقع", "خيارات متقدمة، نادراً ما تحتاجها.", [hn.node, hg.node]),
    msg, bar]);
  setTimeout(refresh, 0);
  return page;
}

/* Long lists are shown a page at a time. `render(rows)` builds the table for one page. */
function paginate(rows, size, render){
  var page = 0, box = h("div", {}), controls = h("div", {class:"a-row a-pager"});
  function draw(){
    var pages = Math.max(1, Math.ceil(rows.length / size));
    if(page >= pages) page = pages - 1;
    box.innerHTML = ""; controls.innerHTML = "";
    box.appendChild(render(rows.slice(page * size, page * size + size)));
    if(pages > 1){
      var back = h("button", {type:"button", class:"a-btn ghost", text:"السابق", onclick:function(){ page--; draw(); }});
      back.disabled = page === 0;
      controls.appendChild(back);
      controls.appendChild(h("span", {class:"hint", text:(page + 1) + " / " + pages + "  ·  " + rows.length}));
      var next = h("button", {type:"button", class:"a-btn ghost", text:"التالي", onclick:function(){ page++; draw(); }});
      next.disabled = page === pages - 1;
      controls.appendChild(next);
    }
  }
  draw();
  return h("div", {}, [box, controls]);
}
/* A file from the server (with the sign-in header) saved on the computer. */
async function downloadFile(path, filename){
  var headers = new Headers();
  if(ADMIN_TOKEN) headers.set("Authorization", "Bearer " + ADMIN_TOKEN);
  var response = await fetch(API_BASE + path, {headers: headers});
  if(!response.ok){
    var result = null;
    try{ result = await response.json(); }catch(e){}
    throw fail(result && result.detail ? result.detail : "تعذّر تنزيل الملف.");
  }
  var url = URL.createObjectURL(await response.blob());
  var link = document.createElement("a");
  link.href = url; link.download = filename;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(function(){ URL.revokeObjectURL(url); }, 1500);
}
function sizeText(bytes){ return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.ceil(bytes / 1024)) + " KB"; }

/* Visitors of the public site (anonymous, counted) and the people who signed in to the portals (with their names). */
function tabVisitors(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var body = h("div", {});
  var days = accSelect([["7", "آخر 7 أيام"], ["30", "آخر 30 يوماً"], ["90", "آخر 90 يوماً"], ["365", "آخر سنة"]], "30");
  var ROLES = {teacher:"معلمة", accountant:"محاسب", parent:"ولي أمر", admin:"مدير", manager:"إدارة"};
  var DEVICES = {mobile:"هاتف", desktop:"كمبيوتر", tablet:"لوحي"};
  function kpi(label, value, cls){ return h("div", {class:"a-kpi " + (cls || "")}, [h("span", {text:label}), h("strong", {text:String(value)})]); }
  function chart(series){
    var max = Math.max.apply(null, series.map(function(s){ return s.views; }).concat([1]));
    var W = 720, H = 200, base = H - 26, band = (W - 20) / series.length, bar = Math.max(2, Math.min(18, band / 2 - 1));
    var svg = ['<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="الزيارات اليومية" style="width:100%;height:auto;direction:ltr">'];
    series.forEach(function(s, i){
      var x = 10 + i * band, hv = Math.round(s.views / max * (base - 12)), hu = Math.round(s.visitors / max * (base - 12));
      svg.push('<rect x="' + x + '" y="' + (base - hv) + '" width="' + bar + '" height="' + hv + '" rx="2" fill="#2D5FC4"><title>' + esc(s.day) + " — " + s.views + '</title></rect>');
      svg.push('<rect x="' + (x + bar + 1) + '" y="' + (base - hu) + '" width="' + bar + '" height="' + hu + '" rx="2" fill="#7DC243"><title>' + esc(s.day) + " — " + s.visitors + '</title></rect>');
    });
    svg.push('<line x1="6" y1="' + base + '" x2="' + (W - 6) + '" y2="' + base + '" stroke="currentColor" opacity=".35"/>');
    if(series.length){ svg.push('<text x="10" y="' + (H - 8) + '" font-size="11" fill="currentColor">' + esc(series[0].day) + '</text><text x="' + (W - 10) + '" y="' + (H - 8) + '" font-size="11" text-anchor="end" fill="currentColor">' + esc(series[series.length - 1].day) + '</text>'); }
    svg.push("</svg>");
    var box = document.createElement("div");
    box.innerHTML = svg.join("");
    return box;
  }
  function table(heads, rows, empty){
    if(!rows.length) return h("div", {class:"a-empty", text:empty});
    return h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact"}, [
      h("thead", {}, [h("tr", {}, heads.map(function(t){ return h("th", {text:t}); }))]), h("tbody", {}, rows)]))]);
  }
  async function load(){
    body.innerHTML = "";
    try{
      var d = await request("/api/admin/platform/visits?days=" + days.value);
      body.appendChild(h("div", {class:"a-card"}, [h("h3", {text:"الزيارات"}),
        h("div", {class:"a-kpis"}, [kpi("زيارات اليوم", d.today.views, "good"), kpi("زوّار اليوم", d.today.visitors), kpi("زيارات آخر 7 أيام", d.week.views), kpi("زوّار آخر 7 أيام", d.week.visitors),
          kpi("زيارات الفترة", d.period.views), kpi("زوّار الفترة", d.period.visitors)]),
        h("p", {class:"hint", text:"الأزرق: زيارات. الأخضر: زوّار مختلفون في اليوم. الزائر يُعدّ مرة واحدة في اليوم، وعدد زوّار الفترة هو مجموع أيامها."}), chart(d.series)]));
      body.appendChild(h("div", {class:"a-card"}, [h("h3", {text:"أكثر الصفحات"}), table(["الصفحة", "الزيارات"], d.pages.map(function(p){ return h("tr", {}, [h("td", {class:"name", dir:"ltr", text:p.path}), h("td", {class:"num", text:String(p.views)})]); }), "لا توجد زيارات بعد."),
        h("h4", {text:"من أين جاؤوا"}), table(["الموقع", "الزيارات"], d.sources.map(function(p){ return h("tr", {}, [h("td", {class:"name", dir:"ltr", text:p.host || uiText("مباشرة (رابط أو بلا مصدر)")}), h("td", {class:"num", text:String(p.views)})]); }), "لا توجد بيانات."),
        h("h4", {text:"الأجهزة"}), h("div", {class:"a-kpis"}, Object.keys(DEVICES).map(function(key){ return kpi(DEVICES[key], d.devices[key] || 0); })),
        h("h4", {text:"اللغات"}), table(["اللغة", "الزيارات"], d.languages.map(function(p){ return h("tr", {}, [h("td", {class:"name", dir:"ltr", text:p.lang || "—"}), h("td", {class:"num", text:String(p.views)})]); }), "لا توجد بيانات.")]));
      body.appendChild(h("div", {class:"a-card"}, [h("h3", {text:"من دخل إلى المنصة"}),
        h("p", {class:"hint", text:"أسماء الحسابات التي سجّلت الدخول إلى البوابات في هذه الفترة (معلمات، أولياء أمور، محاسبون...). الآن: " + d.signed_in_recently + " حساب دخل خلال آخر 30 دقيقة."}),
        table(["الحساب", "النوع", "مرات الدخول", "آخر دخول"], d.sign_ins.map(function(p){
          return h("tr", {}, [h("td", {class:"name", text:p.username}), h("td", {text:p.roles.map(function(r){ return ROLES[r] || r; }).join(" + ") || "—"}), h("td", {class:"num", text:String(p.times)}), h("td", {dir:"ltr", text:accWhen(p.last_at)})]);
        }), "لم يسجّل أحد الدخول في هذه الفترة.")]));
    }catch(error){ setMsg(msg, errText(error), "err"); }
  }
  days.addEventListener("change", load);
  load();
  fill = null;
  return h("section", {}, [h("div", {class:"a-card"}, [h("h3", {text:"الزوّار"}),
    h("p", {class:"hint", text:"زوّار الموقع العام مجهولون: يُعدّون ولا تُعرف أسماؤهم، ولا يُحفظ عنوانهم ولا اسم متصفحهم (بصمة تتغيّر كل يوم). الروبوتات لا تُحسب، ولا تُعدّ زيارات صفحات الدخول والإدارة. الأسماء تظهر فقط لمن سجّل الدخول إلى البوابات."}),
    accField("الفترة", days), msg]), body]);
}

/* The system log: who did what in the money area (every change of fees, payments, payroll, closings). Read only, with filters. */
function tabLog(){
  fill = null;
  return h("section", {}, [accLogCard({title:"سجل النظام"})]);
}

/* The private files that teachers uploaded: who uses how much room, download and delete. */
function tabFiles(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var summary = h("div", {class:"a-kpis"});
  var body = h("div", {});
  function load(){
    request("/api/admin/platform/files").then(function(data){
      summary.innerHTML = "";
      if(!data.owners.length) summary.appendChild(h("div", {class:"a-empty", text:"لا توجد ملفات مرفوعة بعد."}));
      data.owners.forEach(function(o){ summary.appendChild(h("div", {class:"a-kpi"}, [h("span", {text:o.owner + " · " + o.files}), h("strong", {dir:"ltr", text:sizeText(o.bytes) + " / " + sizeText(data.limit_bytes)})])); });
      body.innerHTML = "";
      if(!data.items.length) return;
      body.appendChild(paginate(data.items, 20, function(part){
        return h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact"}, [
          h("thead", {}, [h("tr", {}, ["الملف", "صاحبه", "الحجم", "التاريخ", ""].map(function(t){ return h("th", {text:t}); }))]),
          h("tbody", {}, part.map(function(item){
            var actions = h("div", {class:"a-row"}, [
              h("button", {type:"button", class:"a-btn ghost", text:"تنزيل", onclick:function(){ downloadFile("/api/admin/platform/files/" + encodeURIComponent(item.id) + "/download", item.name).catch(function(error){ setMsg(msg, errText(error), "err"); }); }}),
              twoStep("حذف", async function(){ await request("/api/admin/platform/files/" + encodeURIComponent(item.id), {method:"DELETE"}); setMsg(msg, "تم حذف الملف.", "ok"); load(); })]);
            return h("tr", {}, [h("td", {dir:"auto", class:"name", text:item.name}), h("td", {text:item.owner}), h("td", {class:"num", dir:"ltr", text:sizeText(item.size)}), h("td", {dir:"ltr", text:String(item.created_at || "").slice(0, 10)}), h("td", {}, [actions])]);
          }))]))]);
      }));
    }).catch(function(error){ setMsg(msg, errText(error), "err"); });
  }
  load();
  fill = null;
  return h("section", {}, [h("div", {class:"a-card"}, [h("h3", {text:"ملفات المعلمات"}),
    h("p", {class:"hint", text:"الملفات الخاصة التي رفعتها المعلمات (مرفقات التقارير والمنشورات والمواد). لكل معلمة حدّ 250 ميغابايت. لا يظهر لأحد غير صاحبها والمدير."}), summary, msg, body])]);
}

/* A few numbers about accounts and sign-ins. No names, no passwords. */
function tabSecurity(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var box = h("div", {});
  var ROLE = {parent:"أولياء الأمور", teacher:"المعلمات", manager:"الإدارة", accountant:"المحاسبون", admin:"المدراء"};
  request("/api/admin/platform/security").then(function(d){
    function kpi(label, value, cls){ return h("div", {class:"a-kpi " + (cls || "")}, [h("span", {text:label}), h("strong", {dir:cls === "ltr" ? "ltr" : "auto", text:String(value)})]); }
    box.appendChild(h("div", {class:"a-kpis"}, [
      kpi("حسابات فعّالة", d.accounts_active, "good"), kpi("حسابات موقوفة", d.accounts_blocked), kpi("حسابات بانتظار الموافقة", d.accounts_pending),
      kpi("جلسات مفتوحة الآن", d.sessions_open), kpi("تسجيلات دخول آخر ٢٤ ساعة", d.sign_ins_24h), kpi("محاولات دخول فاشلة آخر ٢٤ ساعة", d.failed_sign_ins_24h, d.failed_sign_ins_24h > 10 ? "due" : "")]));
    box.appendChild(h("h4", {text:"الحسابات الفعّالة حسب النوع"}));
    box.appendChild(h("div", {class:"a-kpis"}, Object.keys(d.by_role).map(function(name){ return kpi(ROLE[name] || name, d.by_role[name]); })));
    box.appendChild(h("h4", {text:"التخزين"}));
    box.appendChild(h("div", {class:"a-kpis"}, [kpi("ملفات خاصة", d.files), kpi("المساحة المستعملة", sizeText(d.stored_bytes), "ltr")]));
  }).catch(function(error){ setMsg(msg, errText(error), "err"); });
  fill = null;
  return h("section", {}, [h("div", {class:"a-card"}, [h("h3", {text:"الأمان"}),
    h("p", {class:"hint", text:"أرقام فقط. عدد المحاولات الفاشلة الكبير في وقت قصير يعني أن أحداً يخمّن كلمات المرور؛ الموقع يحجب العنوان تلقائياً بعد عدة محاولات. لإيقاف حساب أو تغيير كلمة مروره استعمل تبويب «حسابات المنصة»."}), msg, box])]);
}

function tabAccounts(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var username = h("input", {type:"text", id:"a-teacher-username", autocomplete:"username", minlength:"3", maxlength:"80", pattern:"[A-Za-z0-9_.\\-]{3,80}"});
  var password = h("input", {type:"password", id:"a-teacher-password", autocomplete:"new-password", minlength:"12", maxlength:"256"});
  var roleSelect = h("select", {id:"a-new-role", "aria-label":"نوع الحساب"});
  roleSelect.appendChild(new Option("معلمة", "teacher"));
  roleSelect.appendChild(new Option("محاسب", "accountant"));
  roleSelect.appendChild(new Option("إدارة (الأطفال والاعتماد والإعلانات)", "manager"));
  roleSelect.appendChild(new Option("ولي أمر", "parent"));
  roleSelect.appendChild(new Option("مدير (صلاحيات كاملة)", "admin"));
  var childSelect = h("select", {id:"a-new-child", "aria-label":"الطفل"});
  childSelect.appendChild(new Option("— بدون ربط الآن —", ""));
  var childRow = h("div", {hidden:"hidden"}, [h("label", {for:"a-new-child", text:"الطفل (يرى ولي الأمر تقاريره ومنشوراته الخاصة)"}), childSelect]);
  request("/api/admin/platform/children").then(function(list){
    list.forEach(function(c){ childSelect.appendChild(new Option(c.display_name, c.id)); });
  }).catch(function(){});
  roleSelect.addEventListener("change", function(){ childRow.hidden = roleSelect.value !== "parent"; });
  var fullNameInput = h("input", {type:"text", id:"a-new-fullname", maxlength:"120", autocomplete:"off", placeholder:"مثال: ريما صالح"});
  var jobInput = h("input", {type:"text", id:"a-new-job", maxlength:"80", autocomplete:"off", placeholder:"معلمة، محاسب..."});
  var create = h("button", {type:"submit", class:"a-btn sun", text:"إنشاء الحساب"});
  var form = h("form", {class:"a-card"}, [
    h("h3", {text:"أنشئ حساباً جديداً (معلمة، محاسب، ولي أمر أو مدير). يكون الحساب مفعّلاً فوراً."}),
    h("label", {for:"a-new-role", text:"نوع الحساب"}), roleSelect, childRow,
    h("label", {for:"a-new-fullname", text:"الاسم الكامل (يُحفظ كموظف مرتبط بالحساب)"}), fullNameInput,
    h("label", {for:"a-new-job", text:"المسمى الوظيفي"}), jobInput,
    h("label", {for:"a-teacher-username", text:"اسم المستخدم"}), username,
    h("label", {for:"a-teacher-password", text:"كلمة المرور الأولية (12 محرفاً على الأقل)"}), password,
    h("div", {class:"a-row"}, [create]), msg
  ]);
  var list = h("div", {class:"a-card"});
  var listBody = h("div", {});
  list.append(h("h3", {text:"طلبات أولياء الأمور والمعلمات"}), listBody);

  var reqCard = h("div", {class:"a-card"});
  var reqMsg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var reqCode = h("div", {});
  var reqBody = h("div", {});
  reqCard.append(h("h3", {text:"طلبات تسجيل أولياء الأمور"}),
    h("p", {class:"hint", text:"يرسل ولي الأمر بياناته من بوابة الأهل. عند الموافقة يُنشأ رمز تسجيل لمرة واحدة (صالح 7 أيام) يُرسل إلى بريده، ويظهر لك هنا مرة واحدة لتسلّمه يدوياً عند الحاجة."}),
    reqMsg, reqCode, reqBody);
  function showApprovalCode(result){
    var base = (window.location.origin.indexOf("http") === 0 ? window.location.origin : "https://zahra-123hub.github.io/Zahra-Almadain").replace(/\/admin.*$/, "");
    var link = base + "/login/?code=" + encodeURIComponent(result.registration_code);
    var sent = result.request.email_sent;
    reqCode.innerHTML = "";
    var codeBox = h("div", {style:"font-size:2rem;font-weight:800;letter-spacing:.18em;direction:ltr;text-align:center;padding:14px;margin:10px 0;border:2px dashed var(--sun);border-radius:14px", text:result.registration_code});
    var linkInput = h("input", {type:"text", readonly:"readonly", value:link, dir:"ltr", style:"width:100%"});
    reqCode.appendChild(h("div", {class:"a-card", style:"border:2px solid var(--sun)"}, [
      h("strong", {text:"تمت الموافقة على الطلب: " + result.request.guardian_name}),
      h("p", {class:"hint", text: sent ? "تم إنشاء رمز التسجيل تلقائياً وأُرسل إلى بريد ولي الأمر. يظهر هنا مرة واحدة فقط." : "تم إنشاء رمز التسجيل تلقائياً. لم يُرسل البريد (لم يُضبط الإرسال)، فسلّم الرمز إلى ولي الأمر يدوياً. يظهر هنا مرة واحدة فقط."}),
      codeBox,
      h("p", {class:"hint", text:"أو الرابط المباشر:"}),
      linkInput,
      h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn sun", text:"نسخ الرمز", onclick:function(){
        try{ navigator.clipboard.writeText(result.registration_code); }catch(e){}
      }})])
    ]));
  }
  async function decideRequest(id, decision){
    try{
      var result = await request("/api/admin/platform/registration-requests/" + encodeURIComponent(id) + "/decision", {
        method:"POST", body:JSON.stringify({decision:decision})
      });
      reqCode.innerHTML = "";
      if(decision === "approve") showApprovalCode(result);
      setMsg(reqMsg, decision === "approve" ? "تمت الموافقة وإنشاء رمز التسجيل." : "تم رفض الطلب.", "ok");
      await reloadRequests();
    }catch(error){ setMsg(reqMsg, errText(error), "err"); }
  }
  async function newCode(id){
    try{
      var result = await request("/api/admin/platform/registration-requests/" + encodeURIComponent(id) + "/new-code", {method:"POST"});
      reqCode.innerHTML = "";
      showApprovalCode(result);
      setMsg(reqMsg, "تم إنشاء رمز جديد، والرمز السابق لم يعد صالحاً.", "ok");
      await reloadRequests();
    }catch(error){ setMsg(reqMsg, errText(error), "err"); }
  }
  function editRequestForm(item, close){
    var fields = [
      ["guardian_name","اسم ولي الأمر","text"], ["email","البريد الإلكتروني","email"], ["phone","رقم الهاتف","tel"],
      ["child_name","اسم الطفل","text"], ["child_birth_date","تاريخ ميلاد الطفل","date"],
      ["relationship_to_child","صلة القرابة","text"], ["notes","ملاحظات","textarea"]
    ];
    var inputs = {};
    var formMsg = h("div", {class:"a-msg", role:"status"});
    var form = h("form", {style:"flex-basis:100%;width:100%;margin-top:12px"});
    fields.forEach(function(f){
      var input = f[2] === "textarea" ? h("textarea", {rows:"3", maxlength:"1000"}) : h("input", {type:f[2]});
      input.value = item[f[0]] || "";
      if(f[0] === "email" || f[0] === "phone") input.dir = "ltr";
      inputs[f[0]] = input;
      form.append(h("label", {text:f[1]}), input);
    });
    var save = h("button", {type:"submit", class:"a-btn sun", text:"حفظ التعديلات"});
    form.append(h("div", {class:"a-row"}, [save, h("button", {type:"button", class:"a-btn ghost", text:"إلغاء", onclick:close})]), formMsg);
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      save.disabled = true;
      var body = {preferred_language:"ar"};
      fields.forEach(function(f){ body[f[0]] = inputs[f[0]].value.trim(); });
      try{
        await request("/api/admin/platform/registration-requests/" + encodeURIComponent(item.id), {method:"PATCH", body:JSON.stringify(body)});
        setMsg(reqMsg, "تم حفظ التعديلات.", "ok");
        await reloadRequests();
      }catch(error){ setMsg(formMsg, errText(error), "err"); save.disabled = false; }
    });
    return form;
  }
  async function reloadRequests(){
    reqBody.innerHTML = "";
    try{
      var items = await request("/api/admin/platform/registration-requests");
      if(!items.length){ reqBody.appendChild(h("p", {class:"hint", text:"لا توجد طلبات تسجيل."})); return; }
      items.forEach(function(item){
        var statusText = item.status === "pending" ? "بانتظار القرار" : item.status === "approved" ? (item.registered ? "تم التسجيل وإنشاء الحساب" : "تمت الموافقة، بانتظار إكمال التسجيل") : "مرفوض";
        var details = [
          "الهاتف: " + item.phone,
          "البريد: " + item.email,
          "الطفل: " + item.child_name + (item.child_birth_date ? " (" + item.child_birth_date + ")" : ""),
          item.relationship_to_child ? "صلة القرابة: " + item.relationship_to_child : "",
          item.notes ? "ملاحظات: " + item.notes : ""
        ].filter(Boolean);
        var row = h("article", {class:"a-account-row"}, [
          h("div", {}, [
            h("strong", {text:item.guardian_name}),
            h("span", {class:"a-account-meta", text:statusText}),
            details.map(function(line){ return h("span", {class:"a-account-date", dir:"auto", text:line}); }),
            item.created_at ? h("time", {class:"a-account-date", text:new Date(item.created_at).toLocaleDateString(ADMIN_LANG === "ar" ? "ar" : "en")}) : null
          ])
        ]);
        var actions = h("div", {class:"a-row"});
        if(item.status === "pending"){
          actions.append(
            h("button", {type:"button", class:"a-btn sun", text:"موافقة وإنشاء الرمز", onclick:function(){ decideRequest(item.id, "approve"); }}),
            h("button", {type:"button", class:"a-btn danger", text:"رفض", onclick:function(){ decideRequest(item.id, "reject"); }})
          );
        }
        if(item.status === "approved" && !item.registered){
          actions.appendChild(h("button", {type:"button", class:"a-btn sun", text:"رمز جديد", onclick:function(){ newCode(item.id); }}));
        }
        var holder = h("div", {style:"flex-basis:100%;width:100%"});
        actions.appendChild(h("button", {type:"button", class:"a-btn ghost", text:"تعديل", onclick:function(){
          if(holder.firstChild){ holder.innerHTML = ""; return; }
          holder.appendChild(editRequestForm(item, function(){ holder.innerHTML = ""; }));
        }}));
        if(!item.registered){
          actions.appendChild(twoStep("حذف الطلب", async function(){
            await request("/api/admin/platform/registration-requests/" + encodeURIComponent(item.id), {method:"DELETE"});
            setMsg(reqMsg, "تم حذف الطلب.", "ok");
            await reloadRequests();
          }));
        }
        row.appendChild(actions);
        row.appendChild(holder);
        reqBody.appendChild(row);
      });
    }catch(error){ reqBody.appendChild(h("p", {class:"a-msg err", text:error.message || "تعذّر تنفيذ العملية على الخادم."})); }
  }
  reloadRequests();
  async function reloadAccounts(){
    listBody.innerHTML = "";
    try{
      var accounts = await request("/api/admin/platform/accounts");
      if(!accounts.length){ listBody.appendChild(h("p", {class:"hint", text:"لا توجد حسابات أولياء أمور أو معلمات."})); return; }
      accounts.forEach(function(account){
        var role = account.roles.map(function(r){ return ROLE_LABEL[r] || r; }).join(" + ");
        var status = account.approval_status === "active" ? "نشط" : account.approval_status === "pending" ? "بانتظار التفعيل" : "موقوف";
        var row = h("article", {class:"a-account-row"}, [
          h("div", {}, [
            h("strong", {text:account.username}),
            h("span", {class:"a-account-meta", text:role + " · " + status}),
            account.full_name ? h("span", {class:"a-account-date", dir:"auto", text:"الاسم: " + account.full_name + (account.job_title ? " · " + account.job_title : "")}) : null,
            account.guardian_name ? h("span", {class:"a-account-date", dir:"auto", text:"ولي الأمر: " + account.guardian_name + " · " + account.phone}) : null,
            account.guardian_name ? h("span", {class:"a-account-date", dir:"auto", text:"البريد: " + account.email + " · الطفل: " + account.child_name}) : null,
            account.created_at ? h("time", {class:"a-account-date", text:new Date(account.created_at).toLocaleDateString(ADMIN_LANG === "ar" ? "ar" : "en")}) : null
          ])
        ]);
        var editHolder = h("div", {style:"flex-basis:100%;width:100%"});
        var actions = h("div", {class:"a-row", style:"margin:0"}, [
          h("button", {type:"button", class:"a-btn ghost", text:"تعديل", onclick:function(){
            if(editHolder.firstChild){ editHolder.innerHTML = ""; return; }
            editHolder.appendChild(accountEditor(account, function(){ editHolder.innerHTML = ""; }));
          }})
        ]);
        if(account.approval_status !== "active"){
          actions.appendChild(h("button", {type:"button", class:"a-btn sun", text:"تفعيل الحساب", onclick:function(){
            updateStatus(account.id, "active");
          }}));
        } else {
          actions.appendChild(h("button", {type:"button", class:"a-btn danger", text:"إيقاف الحساب", onclick:function(){
            updateStatus(account.id, "disabled");
          }}));
        }
        row.appendChild(actions);
        row.appendChild(editHolder);
        listBody.appendChild(row);
      });
    }catch(error){ listBody.appendChild(h("p", {class:"a-msg err", text:error.message || "تعذّر تنفيذ العملية على الخادم."})); }
  }
  var ROLE_LABEL = {teacher:"معلمة", accountant:"محاسب", parent:"ولي أمر", admin:"مدير", manager:"مشرف"};
  /* Edit name/language/roles and set a new password. Existing passwords cannot be shown: they are
     stored as one-way hashes, so the admin sets or generates a new one, shown once. */
  function accountEditor(account, close){
    var username = h("input", {type:"text", maxlength:"80", value:account.username, dir:"ltr", autocomplete:"off", pattern:"[A-Za-z0-9_.\\-]{3,80}"});
    var fullName = h("input", {type:"text", maxlength:"120", value:account.full_name || "", placeholder:"الاسم الكامل"});
    var jobTitle = h("input", {type:"text", maxlength:"80", value:account.job_title || "", placeholder:"المسمى الوظيفي"});
    var language = h("select", {});
    [["ar", "العربية"], ["en", "English"]].forEach(function(o){ language.appendChild(new Option(o[1], o[0])); });
    language.value = account.preferred_language || "ar";
    var password = h("input", {type:"text", value:"", dir:"ltr", autocomplete:"new-password", placeholder:"اتركه فارغاً ليُولَّد تلقائياً"});
    var result = h("div", {});
    var roleBoxes = {};
    var rolesRow = h("div", {class:"a-field", style:"grid-column:1 / -1"}, [h("span", {text:"الأدوار (يمكن اختيار أكثر من دور)"})]);
    [["admin", "مدير"], ["manager", "إدارة"], ["teacher", "معلمة"], ["accountant", "محاسب"], ["parent", "ولي أمر"]].forEach(function(r){
      var box = h("input", {type:"checkbox"});
      box.checked = account.roles.indexOf(r[0]) !== -1;
      roleBoxes[r[0]] = box;
      rolesRow.appendChild(h("label", {class:"a-check-field"}, [box, h("span", {text:r[1]})]));
    });
    var form = h("form", {class:"a-form-grid", style:"margin-top:10px"}, [
      h("label", {class:"a-field"}, [h("span", {text:"اسم المستخدم"}), username]),
      h("label", {class:"a-field"}, [h("span", {text:"اللغة"}), language]),
      h("label", {class:"a-field"}, [h("span", {text:"الاسم الكامل (مرتبط بالحساب)"}), fullName]),
      h("label", {class:"a-field"}, [h("span", {text:"المسمى الوظيفي"}), jobTitle]),
      rolesRow,
      h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn sun", text:"حفظ البيانات"}), h("button", {type:"button", class:"a-btn ghost", text:"إغلاق", onclick:close})]),
      h("p", {class:"hint", style:"grid-column:1 / -1", text:"لا يمكن عرض كلمات المرور الحالية: تُحفظ بصيغة مشفّرة لا يمكن عكسها. يمكنك تعيين كلمة مرور جديدة أو توليدها وإعطاؤها للمستخدم."}),
      h("label", {class:"a-field", style:"grid-column:1 / -1"}, [h("span", {text:"كلمة مرور جديدة (12 محرفاً على الأقل)"}), password]),
      h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:"تعيين كلمة المرور الجديدة", onclick:async function(){
        try{
          var res = await request("/api/admin/platform/accounts/" + encodeURIComponent(account.id) + "/reset-password", {method:"POST", body:JSON.stringify(password.value ? {password:password.value} : {})});
          password.value = "";
          result.innerHTML = "";
          result.appendChild(h("div", {class:"a-card", style:"border:2px solid var(--sun)"}, [
            h("strong", {text:"كلمة المرور الجديدة للحساب " + res.username + " (تظهر مرة واحدة فقط):"}),
            h("div", {style:"font-size:1.6rem;font-weight:800;letter-spacing:.1em;direction:ltr;text-align:center;padding:12px;margin:10px 0;border:2px dashed var(--sun);border-radius:14px;user-select:all", text:res.password}),
            h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn sun", text:"نسخ", onclick:function(){ try{ navigator.clipboard.writeText(res.password); }catch(e){} }})]),
            h("p", {class:"hint", text:"أُنهيت جلسات هذا الحساب المفتوحة. سلّم كلمة المرور للمستخدم بطريقة آمنة ويُفضّل أن يغيّرها."})
          ]));
        }catch(error){ setMsg(msg, errText(error), "err"); }
      }})]),
      result
    ]);
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      var chosen = Object.keys(roleBoxes).filter(function(k){ return roleBoxes[k].checked; });
      if(!chosen.length){ setMsg(msg, "اختر دوراً واحداً على الأقل.", "err"); return; }
      try{
        await request("/api/admin/platform/accounts/" + encodeURIComponent(account.id), {method:"PATCH", body:JSON.stringify({username:username.value.trim(), preferred_language:language.value, roles:chosen, full_name:fullName.value.trim(), job_title:jobTitle.value.trim()})});
        setMsg(msg, "تم حفظ بيانات الحساب.", "ok");
        await reloadAccounts();
      }catch(error){ setMsg(msg, errText(error), "err"); }
    });
    return form;
  }
  async function updateStatus(accountId, status){
    try{
      await request("/api/admin/platform/accounts/" + encodeURIComponent(accountId) + "/status", {
        method:"PATCH", body:JSON.stringify({status:status})
      });
      setMsg(msg, "تم تحديث حالة الحساب.", "ok");
      await reloadAccounts();
    }catch(error){ setMsg(msg, errText(error), "err"); }
  }
  form.addEventListener("submit", async function(event){
    event.preventDefault();
    if(!/^[A-Za-z0-9_.-]{3,80}$/.test(username.value.trim()) || password.value.length < 12){
      setMsg(msg, "الاسم أو كلمة المرور غير صالحة.", "err"); return;
    }
    create.disabled = true;
    try{
      await request("/api/admin/platform/teacher-accounts", {
        method:"POST",
        body:JSON.stringify({
          role:roleSelect.value,
          full_name:fullNameInput.value.trim(),
          job_title:jobInput.value.trim(),
          child_id:(roleSelect.value === "parent" && childSelect.value) ? childSelect.value : null,
          username:username.value.trim(),
          password:password.value,
          preferred_language:"ar"
        })
      });
      username.value = ""; password.value = ""; fullNameInput.value = ""; jobInput.value = "";
      setMsg(msg, "تم إنشاء الحساب وتفعيله. يمكن تسجيل الدخول الآن.", "ok");
      await reloadAccounts();
    }catch(error){ setMsg(msg, errText(error), "err"); }
    create.disabled = false;
  });
  reloadAccounts();
  fill = null;
  return h("section", {}, [
    h("div", {class:"a-card"}, [
      h("h3", {text:"حسابات المنصة"}),
      h("p", {class:"hint", text:"تسجيل ولي الأمر برمز الدعوة ينشئ حساباً معلقاً. راجع الحساب ثم فعّله ليتمكن من الدخول. يمكنك أيضاً إنشاء حسابات المعلمات وإيقاف الحسابات عند الحاجة."})
    ]),
    reqCard,
    form,
    list
  ]);
}

function tabChildren(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var reportsBody = h("div", {});
  var childrenBody = h("div", {});
  var reportsCard = h("div", {class:"a-card"}, [h("h3", {text:"تقارير بانتظار المراجعة"}),
    h("p", {class:"hint", text:"تظهر التقارير للأهل فقط بعد نشرها من هنا. لا يرى الأهل إلا تقارير طفلهم."}), reportsBody]);
  var childrenCard = h("div", {class:"a-card"}, [h("h3", {text:"الأطفال والمعلمات"}),
    h("p", {class:"hint", text:"عيّن معلمة لكل طفل. لا تستطيع المعلمة كتابة تقرير إلا للأطفال المعيّنين لها."}), childrenBody]);
  async function loadReports(){
    reportsBody.innerHTML = "";
    try{
      var reports = await request("/api/admin/platform/reports");
      if(!reports.length){ reportsBody.appendChild(h("div", {class:"a-empty", text:"لا توجد تقارير بانتظار المراجعة."})); return; }
      reports.forEach(function(report){
        function review(status){
          return async function(){
            try{
              await request("/api/admin/platform/reports/" + encodeURIComponent(report.id), {method:"PATCH", body:JSON.stringify({status:status})});
              setMsg(msg, status === "published" ? "تم نشر التقرير للأهل." : "تم إرجاع التقرير للمعلمة للتعديل.", "ok");
              await loadReports();
            }catch(error){ setMsg(msg, errText(error), "err"); }
          };
        }
        reportsBody.appendChild(h("article", {class:"a-report"}, [
          h("h4", {dir:"auto", text:report.title}),
          h("div", {class:"a-meta"}, [
            h("span", {class:"a-tag", text:"الطفل: " + report.child_name}),
            h("span", {class:"a-tag", text:"المعلمة: " + report.author})
          ]),
          h("p", {class:"a-body", dir:"auto", text:report.body}),
          h("div", {class:"a-row"}, [
            h("button", {type:"button", class:"a-btn sun", text:"نشر للأهل", onclick:review("published")}),
            h("button", {type:"button", class:"a-btn ghost", text:"إرجاع للتعديل", onclick:review("rejected")})
          ])
        ]));
      });
    }catch(error){ reportsBody.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  async function loadChildren(){
    childrenBody.innerHTML = "";
    try{
      var results = await Promise.all([request("/api/admin/platform/children"), request("/api/admin/platform/accounts")]);
      var children = results[0];
      var teachers = results[1].filter(function(a){ return a.roles.indexOf("teacher") !== -1 && a.approval_status === "active"; });
      var parentAccounts = results[1].filter(function(a){ return a.roles.indexOf("parent") !== -1 && a.approval_status === "active"; });
      if(!children.length){ childrenBody.appendChild(h("div", {class:"a-empty", text:"لا توجد ملفات أطفال بعد. تُنشأ تلقائياً عند الموافقة على طلب تسجيل."})); return; }
      children.forEach(function(child){
        var teacherCell = h("dd", {});
        if(!child.teachers.length) teacherCell.appendChild(h("span", {class:"a-tag", text:"لا توجد معلمة معيّنة"}));
        child.teachers.forEach(function(teacher){
          teacherCell.appendChild(h("span", {class:"a-tag sun"}, [teacher.username, h("button", {type:"button", title:"إزالة التعيين", "aria-label":"إزالة التعيين", text:"✕", onclick:async function(){
            try{
              await request("/api/admin/platform/children/" + encodeURIComponent(child.id) + "/teachers/" + encodeURIComponent(teacher.id), {method:"DELETE"});
              await loadChildren();
            }catch(error){ setMsg(msg, errText(error), "err"); }
          }})]));
        });
        var parentCell = h("dd", {});
        var linkedParents = child.parent_accounts || [];
        if(linkedParents.length) linkedParents.forEach(function(parent){
          parentCell.appendChild(h("span", {class:"a-tag"}, [parent.username, h("button", {type:"button", title:"إلغاء الربط", "aria-label":"إلغاء الربط", text:"✕", onclick:async function(){
            if(!window.confirm("إلغاء ربط ولي الأمر بهذا الطفل؟")) return;
            try{
              await request("/api/admin/platform/children/" + encodeURIComponent(child.id) + "/parents/" + encodeURIComponent(parent.id), {method:"DELETE"});
              await loadChildren();
            }catch(error){ setMsg(msg, errText(error), "err"); }
          }})]));
        });
        else parentCell.appendChild(h("span", {class:"a-tag", text:"لم يكتمل تسجيل ولي الأمر بعد"}));
        var assignedIds = child.teachers.map(function(t){ return t.id; });
        var options = teachers.filter(function(t){ return assignedIds.indexOf(t.id) === -1; });
        var card = h("article", {class:"a-child"}, [
          h("div", {class:"a-child-head"}, [h("span", {class:"a-child-name", dir:"auto", text:child.display_name})]),
          h("dl", {}, [h("dt", {text:"ولي الأمر"}), parentCell, h("dt", {text:"المعلمات"}), teacherCell])
        ]);
        var linkedIds = linkedParents.map(function(p){ return p.id; });
        var parentOptions = parentAccounts.filter(function(p){ return linkedIds.indexOf(p.id) === -1; });
        if(parentOptions.length){
          var parentSelect = h("select", {"aria-label":"اختر ولي أمر"});
          parentOptions.forEach(function(p){ parentSelect.appendChild(new Option(p.username, p.id)); });
          card.appendChild(h("div", {class:"a-assign"}, [parentSelect, h("button", {type:"button", class:"a-btn sun", text:"ربط ولي أمر", onclick:async function(){
            if(!parentSelect.value) return;
            try{
              await request("/api/admin/platform/children/" + encodeURIComponent(child.id) + "/parents", {method:"POST", body:JSON.stringify({parent_id:parentSelect.value})});
              setMsg(msg, "تم ربط ولي الأمر بالطفل.", "ok");
              await loadChildren();
            }catch(error){ setMsg(msg, errText(error), "err"); }
          }})]));
        }
        if(options.length){
          var select = h("select", {"aria-label":"اختر معلمة"});
          options.forEach(function(t){ select.appendChild(new Option(t.username, t.id)); });
          card.appendChild(h("div", {class:"a-assign"}, [select, h("button", {type:"button", class:"a-btn sun", text:"تعيين معلمة", onclick:async function(){
            if(!select.value) return;
            try{
              await request("/api/admin/platform/children/" + encodeURIComponent(child.id) + "/teachers", {method:"POST", body:JSON.stringify({teacher_id:select.value})});
              setMsg(msg, "تم تعيين المعلمة.", "ok");
              await loadChildren();
            }catch(error){ setMsg(msg, errText(error), "err"); }
          }})]));
        } else {
          card.appendChild(h("p", {class:"hint", text:teachers.length ? "كل المعلمات معيّنات لهذا الطفل." : "أنشئ حساب معلمة أولاً من تبويب «حسابات المنصة»."}));
        }
        childrenBody.appendChild(card);
      });
    }catch(error){ childrenBody.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  loadReports(); loadChildren();
  fill = null;
  return h("section", {}, [msg, reportsCard, childrenCard]);
}

var MONTHS_AR = ["كانون الثاني","شباط","آذار","نيسان","أيار","حزيران","تموز","آب","أيلول","تشرين الأول","تشرين الثاني","كانون الأول"];
var CURRENCY_LABEL = {USD:"الدولار الأمريكي (USD)", SYP:"الليرة السورية (SYP)"};
var STATUS_LABEL = {paid:"مدفوع", partial:"مدفوع جزئياً", open:"غير مدفوع", review:"يحتاج مراجعة"};
/* On a phone a wide table becomes one card per row: every cell gets its column name as a caption. */
function labelCells(table){
  var heads = Array.prototype.map.call(table.querySelectorAll("thead th"), function(th){ return th.textContent; });
  Array.prototype.forEach.call(table.querySelectorAll("tbody tr"), function(tr){
    if(tr.classList.contains("a-detail-row")) return;
    Array.prototype.forEach.call(tr.children, function(td, i){ if(heads[i] && td.colSpan === 1 && !td.hasAttribute("data-label")) td.setAttribute("data-label", heads[i]); });
  });
  return table;
}
function localToday(){ var d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
function money(value){ if(value === null || value === undefined || value === "") return "—"; return Number(value).toLocaleString("en-US", {minimumFractionDigits:2, maximumFractionDigits:2}); }
function esc(value){ return String(value == null ? "" : value).replace(/[&<>"']/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }

function tabFees(){
  var now = new Date();
  var filters = {year:String(now.getFullYear()), month:String(now.getMonth() + 1), class_name:"", currency:"SYP", status:"", needs_review:""};
  var data = {rows:[], totals:{}, classes:[]};
  var viewer = {name:"", role:""};
  var openId = "";
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var tables = h("div", {});

  function field(label, input){ return h("label", {class:"a-field"}, [h("span", {text:label}), input]); }
  function select(options, value){
    var el = h("select", {});
    options.forEach(function(o){ el.appendChild(new Option(o[1], o[0])); });
    el.value = value;
    return el;
  }
  function numberInput(value, extra){ return h("input", Object.assign({type:"number", min:"0", step:"0.01", inputmode:"decimal", value:value || ""}, extra || {})); }
  function monthOptions(withAll){ return (withAll ? [["", "كل الأشهر"]] : []).concat(MONTHS_AR.map(function(name, i){ return [String(i + 1), name]; })); }
  var CURRENCY_OPTIONS = [["SYP","ليرة سورية (SYP)"], ["USD","دولار أمريكي (USD)"]];  // main currency first

  // ----- filters -------------------------------------------------------
  var fYear = h("input", {type:"number", min:"2000", max:"2100", value:filters.year});
  var fMonth = select(monthOptions(true), filters.month);
  var fClass = select([["", "كل الصفوف"]], "");
  var fCurrency = select([["", "كل العملات"]].concat(CURRENCY_OPTIONS), "SYP");
  var fStatus = select([["", "كل الحالات"], ["paid", "مدفوع"], ["partial", "مدفوع جزئياً"], ["open", "غير مدفوع"], ["review", "يحتاج مراجعة"]], "");
  var fReview = h("input", {type:"checkbox"});
  [fYear, fMonth, fClass, fCurrency, fStatus, fReview].forEach(function(el){ el.addEventListener("change", function(){ readFilters(); load(); }); });
  function readFilters(){
    filters.year = fYear.value; filters.month = fMonth.value; filters.class_name = fClass.value;
    filters.currency = fCurrency.value; filters.status = fStatus.value; filters.needs_review = fReview.checked ? "true" : "";
  }
  function fillClasses(){
    var current = filters.class_name;
    fClass.innerHTML = "";
    fClass.appendChild(new Option("كل الصفوف", ""));
    data.classes.forEach(function(name){ fClass.appendChild(new Option(name, name)); });
    fClass.value = data.classes.indexOf(current) !== -1 ? current : "";
    filters.class_name = fClass.value;
  }

  // ----- add charge / generate forms ----------------------------------
  var NEW_CHILD = "__new__";
  var addChild = select([[NEW_CHILD, "— اختر الطفل —"]], NEW_CHILD);
  var addName = h("input", {type:"text", maxlength:"120", placeholder:"الاسم الكامل للطفل", autocomplete:"off"});
  var addClass = h("input", {type:"text", maxlength:"60", placeholder:"مثال: الروضة الأولى / شعبة أ", list:"fee-classes", autocomplete:"off"});
  var classList = h("datalist", {id:"fee-classes"});
  var addMonth = select(monthOptions(false), filters.month);
  var addYear = h("input", {type:"number", min:"2000", max:"2100", value:filters.year});
  var addAmount = numberInput("", {required:"required"});
  var addCurrency = select(CURRENCY_OPTIONS, "SYP");
  var payAmount = numberInput("", {placeholder:"اتركه فارغاً إن لم يدفع بعد"});
  accLinkCurrency(addCurrency, [addAmount, payAmount], msg, function(){ return accMonthEnd(addYear.value, addMonth.value); });  // switching pound / dollar converts what was typed
  var payDate = h("input", {type:"date", value:localToday()});
  var payReceipt = h("input", {type:"text", maxlength:"40", dir:"ltr"});
  var payNote = h("input", {type:"text", maxlength:"500"});
  var payPayer = h("input", {type:"text", maxlength:"120", placeholder:"من دفع؟", autocomplete:"off", list:"acc-payers"});
  var addForm = h("form", {class:"a-card a-form-grid", hidden:"hidden"}, [
    h("h3", {text:"إضافة صف جديد إلى الجدول"}),
    field("الطفل", addChild), h("p", {class:"hint", text:"الطفل غير موجود في القائمة؟ إضافة الأطفال من مهام الإدارة (بوابة الإدارة)."}),
    field("الشهر", addMonth), field("السنة", addYear),
    field("الرسم المطلوب", addAmount), field("العملة", addCurrency),
    h("strong", {text:"دفعة أولى (اختياري)"}),
    field("المبلغ المدفوع", payAmount), field("تاريخ الدفع", payDate), field("رقم الإيصال", payReceipt), field("اسم الدافع", payPayer), field("ملاحظات", payNote),
    classList,
    h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn sun", text:"إضافة الصف"})])
  ]);
  addForm.addEventListener("submit", async function(event){
    event.preventDefault();
    var body = {year:Number(addYear.value), month:Number(addMonth.value), amount:addAmount.value, currency:addCurrency.value};
    if(addChild.value === NEW_CHILD){ setMsg(msg, "اختر الطفل من القائمة. إن لم يكن موجوداً فالإدارة هي التي تضيفه.", "err"); return; }
    body.child_id = addChild.value;
    if(payAmount.value && Number(payAmount.value) > 0){
      body.payment = {amount:payAmount.value, paid_on:payDate.value, receipt_no:payReceipt.value.trim() || null, note:payNote.value.trim(), payer_name:payPayer.value.trim()};
    }
    try{
      await request("/api/admin/fees/charges", {method:"POST", body:JSON.stringify(body)});
      setMsg(msg, "تمت إضافة الصف إلى الجدول.", "ok");
      addName.value = ""; addAmount.value = ""; payAmount.value = ""; payReceipt.value = ""; payNote.value = ""; payPayer.value = "";
      await reloadChildren(); await load();
    }catch(error){ setMsg(msg, errText(error), "err"); }
  });
  var genMonth = select(monthOptions(false), filters.month);
  var genYear = h("input", {type:"number", min:"2000", max:"2100", value:filters.year});
  var genAmount = numberInput("", {required:"required"});
  var genCurrency = select(CURRENCY_OPTIONS, "SYP");
  accLinkCurrency(genCurrency, [genAmount], msg, function(){ return accMonthEnd(genYear.value, genMonth.value); });
  var genClass = h("input", {type:"text", maxlength:"60", placeholder:"اتركه فارغاً لكل الصفوف"});
  var genForm = h("form", {class:"a-card a-form-grid", hidden:"hidden"}, [
    h("h3", {text:"إنشاء رسوم الشهر لجميع الأطفال"}),
    h("p", {class:"hint", text:"يُنشأ الرسم نفسه لكل طفل ليس له رسم في هذا الشهر وبهذه العملة."}),
    field("الشهر", genMonth), field("السنة", genYear), field("الرسم المطلوب", genAmount),
    field("العملة", genCurrency), field("الصف (اختياري)", genClass),
    h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn sun", text:"إنشاء الرسوم"})])
  ]);
  genForm.addEventListener("submit", async function(event){
    event.preventDefault();
    try{
      var result = await request("/api/admin/fees/generate", {method:"POST", body:JSON.stringify({
        year:Number(genYear.value), month:Number(genMonth.value), amount:genAmount.value, currency:genCurrency.value, class_name:genClass.value.trim()})});
      setMsg(msg, "تم إنشاء " + result.created + " رسم، وتخطّي " + result.skipped + " (موجود مسبقاً).", "ok"); await load();
    }catch(error){ setMsg(msg, errText(error), "err"); }
  });

  // ----- tables --------------------------------------------------------
  function badge(status){ return h("span", {class:"a-badge " + status, text:STATUS_LABEL[status]}); }
  function cell(text, cls){ return h("td", {class:cls || "", dir:"auto", text:text}); }

  function detailRow(row, columns){
    var box = h("td", {colspan:String(columns), class:"a-detail"});
    var list = h("div", {});
    if(!row.payments.length) list.appendChild(h("p", {class:"hint", text:"لا توجد دفعات بعد."}));
    row.payments.forEach(function(p){ list.appendChild(paymentLine(row, p)); });
    if(row.needs_review){
      box.appendChild(h("div", {class:"a-review-note"}, [
        h("p", {dir:"auto", text:"هذا السطر مستورد وفيه خانة غير واضحة. النص الأصلي: " + (row.raw_text || "—") + " · المصدر: " + (row.source || "—")}),
        h("button", {type:"button", class:"a-btn ghost", text:"تمت المراجعة", onclick:async function(){
          try{ await request("/api/admin/fees/charges/" + encodeURIComponent(row.id) + "/reviewed", {method:"POST"}); setMsg(msg, "تم تأكيد المراجعة.", "ok"); await load(); }
          catch(error){ setMsg(msg, errText(error), "err"); }
        }})]));
    }
    box.appendChild(list);
    box.appendChild(paymentForm(row, null));
    if(Number(row.paid) > 0) box.appendChild(refundForm(row));
    var amount = numberInput(row.amount);
    var cls = h("input", {type:"text", maxlength:"60", value:row.class_name});
    var canEditChild = viewer.role === "admin";
    var detailGrid = (h("div", {class:"a-form-grid"}, [
      field("تعديل الرسم المطلوب", amount),
      h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:"حفظ الرسم", onclick:async function(){
        try{ await request("/api/admin/fees/charges/" + encodeURIComponent(row.id), {method:"PATCH", body:JSON.stringify({amount:amount.value, expected_version:row.version})}); setMsg(msg, "تم تعديل الرسم.", "ok"); await load(); }
        catch(error){ setMsg(msg, errText(error), "err"); }
      }})]),
      field("الصف / الشعبة", cls),
      h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:"حفظ الصف", onclick:async function(){
        try{ await request("/api/admin/fees/children/" + encodeURIComponent(row.child_id), {method:"PATCH", body:JSON.stringify({class_name:cls.value})}); setMsg(msg, "تم حفظ الصف.", "ok"); await load(); }
        catch(error){ setMsg(msg, errText(error), "err"); }
      }}), twoStep("حذف الرسم", async function(){
        await request("/api/admin/fees/charges/" + encodeURIComponent(row.id), {method:"DELETE"}); openId = ""; setMsg(msg, "تم حذف الرسم.", "ok"); await load();
      })])
    ]));
    box.appendChild(detailGrid);
    box.appendChild(h("small", {class:"hint a-who", text:accWhoText(row)}));
    box.appendChild(accHistoryPanel("charge", row.id));
    if(!canEditChild){  // the class of a child belongs to the management
      detailGrid.removeChild(detailGrid.children[2]);
      var classButtons = detailGrid.children[2];
      if(classButtons && classButtons.firstChild) classButtons.removeChild(classButtons.firstChild);
    }
    return h("tr", {class:"a-detail-row"}, [box]);
  }
  function paymentLine(row, p){
    var line = h("div", {class:"a-pay-line"});
    function show(){
      line.innerHTML = "";
      line.append(
        h("span", {class:"a-tag", dir:"ltr", text:p.paid_on || "—"}),
        p.refund ? h("span", {class:"a-tag refund", text:"استرداد"}) : "",
        h("strong", {class:p.refund ? "refund" : "", text:money(p.amount) + " " + row.currency}),
        p.receipt_no ? h("span", {class:"a-tag", text:"إيصال " + p.receipt_no}) : "",
        p.payer_name ? h("span", {class:"a-tag sun", text:"دفعها: " + p.payer_name}) : h("span", {class:"hint", text:"الدافع غير مذكور"}),
        p.note ? h("span", {class:"hint", dir:"auto", text:p.note}) : "",
        p.created_by ? h("span", {class:"hint", text:"سجّلها: " + p.created_by}) : "",
        p.refund ? "" : h("button", {type:"button", class:"a-btn ghost", text:"تعديل", onclick:function(){ line.innerHTML = ""; line.appendChild(paymentForm(row, p, show)); }}),
        twoStep("حذف", async function(){
          await request("/api/admin/fees/payments/" + encodeURIComponent(p.id), {method:"DELETE"}); setMsg(msg, "تم حذف الدفعة.", "ok"); await load();
        })
      );
    }
    show();
    return line;
  }
  /* Money handed back to the parents: its own booking, the original payment stays. A reason is required. */
  function refundForm(row){
    var amount = numberInput("", {required:"required", placeholder:"حتى " + money(row.paid)});
    var date = h("input", {type:"date", value:localToday(), required:"required"});
    var reason = h("input", {type:"text", maxlength:"500", required:"required", placeholder:"سبب الاسترداد"});
    var payer = h("input", {type:"text", maxlength:"120", placeholder:"لمن سُلّم المبلغ", autocomplete:"off", list:"acc-payers"});
    var form = h("form", {class:"a-form-grid a-pay-form a-refund-form"}, [
      h("strong", {text:"تسجيل استرداد للأهل"}),
      field("المبلغ (" + row.currency + ")", amount), field("تاريخ الاسترداد", date), field("السبب", reason), field("سُلّم إلى", payer),
      h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn ghost", text:"تسجيل الاسترداد"})])
    ]);
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      if(!window.confirm("سيُسجَّل استرداد " + money(amount.value) + " " + row.currency + " كحركة مستقلة، وتبقى الدفعة الأصلية كما هي. المتابعة؟")) return;
      try{
        await request("/api/admin/fees/charges/" + encodeURIComponent(row.id) + "/refunds", {method:"POST", body:JSON.stringify({amount:amount.value, paid_on:date.value, note:reason.value.trim(), payer_name:payer.value.trim()})});
        setMsg(msg, "تم تسجيل الاسترداد.", "ok"); await load();
      }catch(error){ setMsg(msg, errText(error), "err"); }
    });
    return form;
  }
  function paymentForm(row, existing, cancel){
    var amount = numberInput(existing ? existing.amount : "", {required:"required", placeholder:existing ? "" : "المتبقي " + money(row.remaining)});
    var knownDate = !existing || !!existing.paid_on;  // an imported payment without a date may stay without one
    var date = h("input", Object.assign({type:"date", value:existing ? (existing.paid_on || "") : localToday()}, knownDate ? {required:"required"} : {}));
    var receipt = h("input", {type:"text", maxlength:"40", value:existing ? existing.receipt_no : "", dir:"ltr"});
    var note = h("input", {type:"text", maxlength:"500", value:existing ? existing.note : ""});
    var payer = h("input", {type:"text", maxlength:"120", value:existing ? existing.payer_name : "", placeholder:"مثال: الأب أحمد", autocomplete:"off", list:"acc-payers"});
    var buttons = [h("button", {type:"submit", class:"a-btn sun", text:existing ? "حفظ التعديل" : "تسجيل الدفعة"})];
    if(existing) buttons.push(h("button", {type:"button", class:"a-btn ghost", text:"إلغاء", onclick:cancel}));
    var form = h("form", {class:"a-form-grid a-pay-form"}, [
      h("strong", {text:existing ? "تعديل الدفعة" : "إضافة دفعة"}),
      field("المبلغ (" + row.currency + ")", amount), field("تاريخ الدفع", date), field("رقم الإيصال", receipt), field("اسم الدافع", payer), field("ملاحظات", note),
      h("div", {class:"a-row"}, buttons)
    ]);
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      var body = JSON.stringify({amount:amount.value, paid_on:date.value || null, receipt_no:receipt.value.trim() || null, note:note.value.trim(), payer_name:payer.value.trim()});
      try{
        await request(existing ? "/api/admin/fees/payments/" + encodeURIComponent(existing.id) : "/api/admin/fees/charges/" + encodeURIComponent(row.id) + "/payments",
          {method:existing ? "PATCH" : "POST", body:body});
        setMsg(msg, "تم حفظ الدفعة.", "ok"); await load();
      }catch(error){ setMsg(msg, errText(error), "err"); }
    });
    return form;
  }

  /* Rows flagged by the import can be corrected right in the table. */
  function inlineEdit(r){
    var name = h("input", {type:"text", maxlength:"120", value:r.child_name, placeholder:"اسم الطفل", "aria-label":"اسم الطفل"});
    var cls = h("input", {type:"text", maxlength:"60", value:r.class_name, placeholder:"الصف", "aria-label":"الصف"});
    var amount = numberInput(r.amount, {placeholder:"الرسم", "aria-label":"الرسم المطلوب"});
    var canEditChild = viewer.role === "admin";
    name.disabled = cls.disabled = !canEditChild;  // a wrong name or class is corrected by the management
    var save = h("button", {type:"button", class:"a-btn sun", text:"حفظ", onclick:async function(){
      try{
        if(canEditChild && name.value.trim().length < 2){ setMsg(msg, "اكتب اسم الطفل (حرفان على الأقل).", "err"); return; }
        if(amount.value !== "") await request("/api/admin/fees/charges/" + encodeURIComponent(r.id), {method:"PATCH", body:JSON.stringify({amount:amount.value, expected_version:r.version})});
        if(canEditChild) await request("/api/admin/fees/children/" + encodeURIComponent(r.child_id), {method:"PATCH", body:JSON.stringify({class_name:cls.value.trim(), display_name:name.value.trim()})});
        setMsg(msg, "تم حفظ التصحيح. اضغط «تمت المراجعة» بعد التأكد من السطر.", "ok"); await load();
      }catch(error){ setMsg(msg, errText(error), "err"); }
    }});
    return {name:name, cls:cls, amount:amount, save:save};
  }
  function currencyTable(code){
    var rows = data.rows.filter(function(r){ return r.currency === code; });
    var totals = data.totals[code] || {amount:"0", paid:"0", remaining:"0"};
    var headers = ["الرقم","اسم الطفل","الصف","الرسم المطلوب","المدفوع","المتبقي","تاريخ الدفع","رقم الإيصال","الدافع","ملاحظات",""];
    var thead = h("thead", {}, [h("tr", {}, headers.map(function(t){ return h("th", {text:t}); }))]);
    var tbody = h("tbody", {});
    rows.forEach(function(r, i){
      var edit = r.needs_review ? inlineEdit(r) : null;
      var tr = h("tr", {class:"a-fee-row " + r.status + (r.needs_review ? " review" : "")}, [
        cell(String(i + 1), "num"),
        edit ? h("td", {class:"name"}, [edit.name]) : h("td", {class:"name", dir:"auto"}, [r.child_name || "—"]),
        edit ? h("td", {}, [edit.cls]) : cell(r.class_name || "—"),
        edit ? h("td", {class:"num"}, [edit.amount]) : cell(money(r.amount), "num"), cell(money(r.paid), "num"),
        h("td", {class:"num"}, [h("div", {class:"a-remaining", text:money(r.remaining)}), badge(r.status)]),
        cell(r.last_paid_on || "—", "num"), cell(r.receipts.join("، ") || "—", "num"), cell(r.payers.join("، ") || "—"), cell(r.notes.join("؛ ") || "—"),
        h("td", {}, [edit ? edit.save : "", h("button", {type:"button", class:"a-btn " + (openId === r.id ? "ghost" : "sun"), text:openId === r.id ? "إغلاق" : "دفعة / تعديل", onclick:function(){ openId = openId === r.id ? "" : r.id; render(); }})])
      ]);
      tbody.appendChild(tr);
      if(openId === r.id) tbody.appendChild(detailRow(r, headers.length));
    });
    if(!rows.length) tbody.appendChild(h("tr", {}, [h("td", {colspan:String(headers.length), class:"a-empty", text:"لا توجد رسوم بهذه العملة."})]));
    var tfoot = h("tfoot", {}, [h("tr", {class:"a-total"}, [
      h("td", {colspan:"3", text:"الإجمالي العام (" + code + ")"}), cell(money(totals.amount), "num"), cell(money(totals.paid), "num"),
      cell(money(totals.remaining), "num"), h("td", {colspan:"5"})])]);
    return h("div", {class:"a-card"}, [
      h("h3", {text:"الرسوم بـ" + CURRENCY_LABEL[code]}),
      h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact"}, [thead, tbody, tfoot]))])
    ]);
  }
  function render(){
    tables.innerHTML = "";
    var shown = filters.currency ? [filters.currency] : ["SYP", "USD"];
    shown.forEach(function(code){ tables.appendChild(currencyTable(code)); });
  }

  // ----- data loading --------------------------------------------------
  async function load(){
    if(window.accLoadNames) accLoadNames();
    var q = [];
    ["year","month","class_name","currency","status","needs_review"].forEach(function(k){ if(filters[k]) q.push(k + "=" + encodeURIComponent(filters[k])); });
    try{
      data = await request("/api/admin/fees?" + q.join("&"));
      fillClasses(); render();
    }catch(error){ tables.innerHTML = ""; tables.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  async function init(){
    try{
      viewer = await request("/api/admin/fees/me");
    }catch(error){ setMsg(msg, errText(error), "err"); }
    await reloadChildren();
    load();
  }
  async function reloadChildren(){
    try{
      var list = await request("/api/admin/fees/children");
      var keep = addChild.value;
      addChild.innerHTML = "";
      addChild.appendChild(new Option("— اختر الطفل —", NEW_CHILD));
      list.forEach(function(c){ addChild.appendChild(new Option(c.display_name + (c.class_name ? " — " + c.class_name : ""), c.id)); });
      addChild.value = Array.prototype.some.call(addChild.options, function(o){ return o.value === keep; }) ? keep : NEW_CHILD;
      classList.innerHTML = "";
      list.map(function(c){ return c.class_name; }).filter(function(v, i, a){ return v && a.indexOf(v) === i; })
        .forEach(function(name){ classList.appendChild(new Option(name)); });
    }catch(error){ setMsg(msg, errText(error), "err"); }
  }

  // ----- printable report (A4 landscape, RTL) -------------------------
  function printReport(){
    var codes = filters.currency ? [filters.currency] : ["SYP", "USD"];
    var period = (filters.month ? MONTHS_AR[Number(filters.month) - 1] + " " : "") + (filters.year || "");
    var parts = codes.map(function(code){
      var rows = data.rows.filter(function(r){ return r.currency === code; });
      var t = data.totals[code] || {amount:"0", paid:"0", remaining:"0"};
      var body = rows.map(function(r, i){
        return "<tr><td>" + (i + 1) + "</td><td class='l'>" + esc(r.child_name) + "</td><td>" + esc(r.class_name || "—") + "</td><td class='n'>" + money(r.amount) +
          "</td><td class='n'>" + money(r.paid) + "</td><td class='n " + (Number(r.remaining) > 0 ? "due" : "") + "'>" + money(r.remaining) + "</td><td class='n'>" + esc(r.last_paid_on || "—") +
          "</td><td class='n'>" + esc(r.receipts.join("، ") || "—") + "</td><td class='l'>" + esc(r.payers.join("، ") || "—") + "</td><td class='l'>" + esc(r.notes.join("؛ ") || "—") + "</td></tr>";
      }).join("");
      return {code:code, cols:[5, 14, 11, 11, 11, 11, 9, 9, 11, 8], html:"<table><thead><tr><th>الرقم</th><th>اسم الطفل</th><th>الصف</th><th>الرسم المطلوب</th><th>المدفوع</th><th>المتبقي</th><th>تاريخ الدفع</th><th>رقم الإيصال</th><th>الدافع</th><th>ملاحظات</th></tr></thead><tbody>" +
        (body || "<tr><td colspan='10'>لا توجد بيانات</td></tr>") + "</tbody><tfoot><tr><td colspan='3'>الإجمالي العام (" + code + ")</td><td>" + money(t.amount) +
        "</td><td>" + money(t.paid) + "</td><td>" + money(t.remaining) + "</td><td colspan='4'></td></tr></tfoot></table>"};
    });
    accPrint("كشف اشتراكات ورسوم الأطفال", function(part){
      return "الفترة: " + esc(period) + " | العملة: " + esc(CURRENCY_LABEL[part.code]) + (filters.class_name ? " | الصف: " + esc(filters.class_name) : "");
    }, parts, msg);
  }

  var toolbar = h("div", {class:"a-row"}, [
    h("button", {type:"button", class:"a-btn sun", text:"＋ إضافة صف جديد", onclick:function(){ addForm.hidden = !addForm.hidden; genForm.hidden = true; }}),
    h("button", {type:"button", class:"a-btn ghost", text:"إنشاء رسوم الشهر للجميع", onclick:function(){ genForm.hidden = !genForm.hidden; addForm.hidden = true; }}),
    h("button", {type:"button", class:"a-btn", text:"تصدير PDF / طباعة", onclick:printReport})
  ]);
  var filterCard = h("div", {class:"a-card"}, [
    h("h3", {text:"الاشتراكات والرسوم"}),
    h("p", {class:"hint", text:"الدولار والليرة السورية يُحسبان كلٌّ على حدة ولا يُجمعان ولا يُحوَّلان. لحفظ الكشف كملف PDF اختر «حفظ كملف PDF» في نافذة الطباعة."}),
    h("div", {class:"a-form-grid"}, [field("السنة", fYear), field("الشهر", fMonth), field("الصف", fClass), field("العملة", fCurrency), field("الحالة", fStatus), h("label", {class:"a-field a-check-field"}, [fReview, h("span", {text:"فقط ما يحتاج مراجعة"})])]),
    toolbar, msg
  ]);
  init();
  fill = null;
  var resetBox = accResetCard({scopes:[["fees", "كل الاشتراكات والدفعات في هذا الشهر", true]], period:function(){ return {year:Number(filters.year), month:Number(filters.month)}; }, onDone:load});
  return h("section", {}, [filterCard, addForm, genForm, tables, resetBox]);
}

var TABS = [["gallery","الصور"],["video","الفيديو"],["news","الأخبار"],["children","الأطفال والتقارير"],["control","لوحة المتابعة"],["fees","المحاسبة"],["cashbook","دفتر الصندوق"],["accounts","حسابات المنصة"],["visitors","الزوّار"],["log","سجل النظام"],["files","الملفات"],["security","الأمان"],["settings","الإعدادات"]]
  .filter(function(t){
    if(!TEACHER_MODE && !ACCOUNTANT_MODE) return true;  // the admin sees everything
    return (TEACHER_MODE && ["gallery","video","news"].indexOf(t[0]) !== -1) || (ACCOUNTANT_MODE && (t[0] === "fees" || t[0] === "cashbook"));
  });
if(TABS.length && !TABS.some(function(t){ return t[0] === tab; })) tab = TABS[0][0];
/* "Hello <username>" in the top bar: the server admin's name is inside the session token, other accounts are looked up. */
function adminName(){
  try{
    var sub = JSON.parse(atob(ADMIN_TOKEN.split(".")[0].replace(/-/g, "+").replace(/_/g, "/"))).sub || "";
    if(sub && !/^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i.test(sub)) return Promise.resolve(sub);
  }catch(e){}
  return request("/api/platform/auth/me").then(function(me){ return me.username || ""; }).catch(function(){ return ""; });
}
function draw(){
  var root = document.getElementById("app"); root.innerHTML = "";
  // the admin area looks like the portals: the same header, the same pill navigation, the same cards and tiles
  var skin = true;  // the whole admin area wears the look of the portals
  var accounting = ACCOUNTANT_MODE || tab === "fees" || tab === "cashbook";
  document.body.classList.toggle("skin-portal", skin);
  document.body.classList.toggle("skin-solo", ACCOUNTANT_MODE && TABS.length <= 1);
  var out = h("button", {type:"button", class:"p-button outline", text:"تسجيل الخروج", onclick:function(){ clearSessions(); start(); }});
  var view = h("a", {class:"p-button sun", href:"../", target:"_blank", rel:"noopener", text:"عرض الموقع"});
  var switches = [];  // links to the other portals this account may use
  [["manager", "../management/", "بوابة الإدارة"], ["teacher", "../teachers/", "بوابة المعلمات"], ["parent", "../parents/", "بوابة أولياء الأمور"]].forEach(function(p){
    if(PORTALS.indexOf(p[0]) !== -1) switches.push(h("a", {class:"p-button outline", href:p[1], text:p[2]}));
  });
  var back = TEACHER_MODE && !PORTALS.length ? h("a", {class:"p-button outline", href:"../teachers/", text:"العودة إلى بوابتي"}) : null;
  var changePw = (TEACHER_MODE || ACCOUNTANT_MODE) ? h("button", {type:"button", class:"p-button outline", text:"تغيير كلمة المرور", onclick:function(){ toggleChangePassword(); }}) : null;
  var avatar = h("span", {class:"p-avatar", id:"a-avatar", hidden:"hidden"});
  var identity = h("div", {class:"p-account-identity", hidden:"hidden"}, [h("span", {class:"p-account-label", text:"مرحباً"}), h("strong", {id:"a-hello-name"})]);
  var tabs = h("div", {class:"a-tabs", role:"tablist"});
  TABS.forEach(function(t){
    var b = h("button", {type:"button", role:"tab", "aria-selected":String(tab === t[0]), text:t[1]});
    b.addEventListener("click", function(){ tab = t[0]; draw(); }); tabs.appendChild(b);
  });
  var main = h("div", {class:"a-main"}); fill = null;
  main.appendChild(tab === "video" ? tabMedia("video") : tab === "news" ? tabNews() : tab === "settings" ? tabSettings() : tab === "accounts" ? tabAccounts() : tab === "visitors" ? tabVisitors() : tab === "log" ? tabLog() : tab === "files" ? tabFiles() : tab === "security" ? tabSecurity() : tab === "children" ? tabChildren() : tab === "fees" ? tabAccounting() : tab === "cashbook" ? tabCashbook() : tab === "control" ? tabControl() : tabMedia("image"));
  adminName().then(function(name){
    if(!name) return;
    document.getElementById("a-hello-name").textContent = name;
    avatar.textContent = name.charAt(0).toUpperCase();
    avatar.hidden = false; identity.hidden = false;
  });
  var header = h("header", {class:"p-header"}, [h("div", {class:"p-header-inner"}, [
    h("a", {class:"p-brand", href:"../"}, [h("img", {src:"../images/logo.png?v=2", alt:"شعار روضة زهرة المدائن"}),
      h("div", {}, [h("h1", {text:accounting ? "بوابة المحاسبة" : "لوحة التحكم"}), h("span", {text:"روضة زهرة المدائن"})])]),
    h("div", {class:"p-actions"}, [avatar, identity, languageSwitch()].concat(switches, [back, changePw, view, out]))])]);
  root.append(header, h("div", {class:"a-tabswrap"}, [tabs]), main);
}
/* A signed-in teacher/accountant changes their own password here (the admin password lives on the server). */
function toggleChangePassword(){
  var main = document.querySelector(".a-main");
  if(!main) return;
  var existing = main.querySelector(".a-change-password");
  if(existing){ existing.remove(); return; }
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var current = h("input", {type:"password", autocomplete:"current-password", required:"required"});
  var fresh = h("input", {type:"password", autocomplete:"new-password", required:"required", minlength:"12"});
  var again = h("input", {type:"password", autocomplete:"new-password", required:"required", minlength:"12"});
  var form = h("form", {class:"a-card a-change-password", style:"border:2px solid var(--sun)"}, [
    h("h3", {text:"تغيير كلمة المرور"}),
    h("label", {text:"كلمة المرور الحالية"}), current,
    h("label", {text:"كلمة المرور الجديدة (12 حرفاً على الأقل، ليست شائعة، ولا تحتوي اسم المستخدم)"}), fresh,
    h("label", {text:"أعد كتابة كلمة المرور الجديدة"}), again,
    h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn sun", text:"حفظ"}), h("button", {type:"button", class:"a-btn ghost", text:"إلغاء", onclick:function(){ form.remove(); }})]),
    msg
  ]);
  form.addEventListener("submit", async function(event){
    event.preventDefault();
    if(fresh.value !== again.value){ setMsg(msg, "كلمتا المرور غير متطابقتين.", "err"); return; }
    try{
      await request("/api/platform/auth/change-password", {method:"POST", body:JSON.stringify({current_password:current.value, new_password:fresh.value})});
      current.value = fresh.value = again.value = "";
      setMsg(msg, "تم تغيير كلمة المرور، وأُنهيت جلساتك الأخرى.", "ok");
    }catch(error){ setMsg(msg, errText(error), "err"); }
  });
  main.insertBefore(form, main.firstChild);
  current.focus();
}
/* Sign out after 30 minutes without activity. */
(function idleGuard(){
  if(!ADMIN_TOKEN) return;
  var timer;
  function expire(){ clearSessions(); window.location.replace("../login/?expired=1"); }
  function reset(){ clearTimeout(timer); timer = setTimeout(expire, 30 * 60 * 1000); }
  ["click", "keydown", "mousemove", "touchstart", "scroll"].forEach(function(name){ window.addEventListener(name, reset, {passive:true}); });
  reset();
})();
function loginScreen(msg){
  var root = document.getElementById("app"); root.innerHTML = "";
  var err = h("div", {class:"a-msg err", role:"alert", text:msg || ""});
  var username = h("input", {type:"text", id:"l-user", value:"admin", autocomplete:"username"});
  var password = h("input", {type:"password", id:"l-pass", autocomplete:"current-password"});
  var go = h("button", {type:"button", class:"a-btn sun", text:"دخول"});
  go.addEventListener("click", async function(){
    if(!username.value.trim() || !password.value){ setMsg(err, "أدخل اسم المستخدم وكلمة المرور.", "err"); return; }
    go.disabled = true;
    try{
      var result = await request("/api/auth/login", {method:"POST", body:JSON.stringify({username:username.value.trim(), password:password.value})});
      ADMIN_TOKEN = result.access_token; sessionStorage.setItem("zm-admin-session", ADMIN_TOKEN);
      DATA = await loadContent(); draw();
    }catch(e){ ADMIN_TOKEN = ""; sessionStorage.removeItem("zm-admin-session"); go.disabled = false; setMsg(err, errText(e), "err"); }
  });
  root.append(h("div", {class:"a-main", style:"max-width:420px"}, [h("div", {class:"a-card"}, [
    h("div", {class:"a-login-tools"}, [languageSwitch()]),
    h("h3", {text:"دخول المسؤول"}), h("p", {class:"hint", text:"أدخل بيانات دخول لوحة التحكم التي أُعدّت على الخادم."}),
    h("label", {for:"l-user", text:"اسم المستخدم"}), username,
    h("label", {for:"l-pass", text:"كلمة المرور"}), password,
    h("div", {class:"a-row"}, [go]), err])]));
}
// If only the GitHub connection is missing (e.g. local testing), still open the dashboard
// so the platform accounts tab remains usable.
async function loadContent(){
  if(!TEACHER_MODE && ACCOUNTANT_MODE) return {settings:{}, gallery:[], news:[]};  // accountants do not use the site content
  try{ return await api("GET", "/admin/api/content"); }
  catch(e){
    if(e && e.message && /GitHub/.test(e.message)){
      tab = TEACHER_MODE ? "gallery" : "accounts";
      return {settings:{}, gallery:[], news:[]};
    }
    throw e;
  }
}
function start(){
  if(!ADMIN_TOKEN){ window.location.replace("../login/"); return; }
  loadContent().then(function(data){ DATA = data; draw(); }, function(e){
    clearSessions(); window.location.replace("../login/");
  });
}
applyAdminLanguage();
start();
