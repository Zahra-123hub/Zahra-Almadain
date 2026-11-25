import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../config/config.dart';
import '../../localization/strings.dart';
import '../../services/api.dart';
import '../../shared/ui.dart';

// The admin area of the app: the same work as the admin page of the website (/admin/), on the same server endpoints.
// Every action is checked again by the server; hiding something here is only comfort.
//
// The texts of this area are written here in the three languages (Arabic, German, English) with `_t`.

String _t(BuildContext context, String ar, String de, String en) {
  final code = S.of(context).code;
  return code == 'ar' ? ar : (code == 'de' ? de : en);
}

Map<String, dynamic> _m(Object? v) => v is Map ? v.cast<String, dynamic>() : <String, dynamic>{};
List<Map<String, dynamic>> _l(Object? v) => [for (final x in (v is List ? v : const [])) if (x is Map) x.cast<String, dynamic>()];
String _str(Object? v) => v == null ? '' : '$v';

/// "2026-11-23 14:05" from an ISO time, in local time.
String _when(Object? iso) {
  final d = DateTime.tryParse(_str(iso));
  if (d == null) return _str(iso);
  final l = d.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${l.year}-${two(l.month)}-${two(l.day)} ${two(l.hour)}:${two(l.minute)}';
}

const _good = Color(0xFF1E7A45);
const _bad = Color(0xFFB3402F);
const _muted = Color(0xFF5B6878);

/// Loads one address and builds a scrolling page from it; pull down to load again.
Widget _load(BuildContext context, String path, Widget Function(BuildContext, dynamic, Future<void> Function()) builder, {Map<String, String>? query, Key? key}) {
  final api = SessionScope.of(context).api;
  return Loader<dynamic>(key: key, load: () async => Cached<dynamic>(await api.get(path, query: query)), builder: builder);
}

/// Runs a change on the server and tells the person how it went.
Future<bool> _run(BuildContext context, Future<dynamic> Function() action, {String? done}) async {
  try {
    await action();
    if (context.mounted && done != null) toast(context, done);
    return true;
  } on ApiException catch (e) {
    if (context.mounted) toast(context, e.detail.isNotEmpty ? e.detail : problemText(context, e));
    return false;
  }
}

/// A small figure card: a label and a number.
class _Kpi extends StatelessWidget {
  const _Kpi(this.label, this.value, {this.tone});
  final String label;
  final String value;
  final Color? tone;
  @override
  Widget build(BuildContext context) => Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Text(label, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5, color: _muted, fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            Text(value, textDirection: TextDirection.ltr, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: tone)),
          ]),
        ),
      );
}

/// Figure cards in a grid that wraps on small screens.
Widget _kpis(List<Widget> cards) => LayoutBuilder(builder: (context, c) {
      final cols = (c.maxWidth / 170).floor().clamp(2, 6);
      final w = (c.maxWidth - (cols - 1) * 10) / cols;
      return Wrap(spacing: 10, runSpacing: 10, children: [for (final k in cards) SizedBox(width: w, child: k)]);
    });

/// A white card with a title and its content.
class _Box extends StatelessWidget {
  const _Box({required this.title, required this.child, this.hint, this.trailing});
  final String title;
  final String? hint;
  final Widget child;
  final Widget? trailing;
  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              Expanded(child: Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800))),
              ?trailing,
            ]),
            if (hint != null) Padding(padding: const EdgeInsets.only(top: 4), child: Text(hint!, style: const TextStyle(fontSize: 12.5, color: _muted, height: 1.4))),
            const SizedBox(height: 12),
            child,
          ]),
        ),
      );
}

/// One line "label ...... value".
Widget _row(String label, String value, {bool ltr = false}) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(child: Text(label, style: const TextStyle(color: _muted))),
        const SizedBox(width: 12),
        Flexible(child: Text(value, textAlign: TextAlign.end, textDirection: ltr ? TextDirection.ltr : null, style: const TextStyle(fontWeight: FontWeight.w700))),
      ]),
    );

Widget _empty(String text) => Padding(padding: const EdgeInsets.all(12), child: Text(text, textAlign: TextAlign.center, style: const TextStyle(color: _muted)));

/// Pages with a tab bar on top (control centre, accounts, children, website).
class _Tabbed extends StatelessWidget {
  const _Tabbed({required this.tabs, required this.pages});
  final List<String> tabs;
  final List<Widget> pages;
  @override
  Widget build(BuildContext context) => DefaultTabController(
        length: tabs.length,
        child: Column(children: [
          Material(
            color: Colors.white,
            child: TabBar(isScrollable: true, tabAlignment: TabAlignment.start, tabs: [for (final t in tabs) Tab(text: t)]),
          ),
          Expanded(child: TabBarView(children: pages)),
        ]),
      );
}

const _roleNames = {
  'admin': ['مدير', 'Admin', 'Admin'],
  'manager': ['إدارة', 'Leitung', 'Management'],
  'teacher': ['معلمة', 'Lehrerin', 'Teacher'],
  'accountant': ['محاسب', 'Buchhaltung', 'Accountant'],
  'parent': ['ولي أمر', 'Eltern', 'Parent'],
};
String _role(BuildContext context, String r) {
  final n = _roleNames[r];
  return n == null ? r : _t(context, n[0], n[1], n[2]);
}

// =================================================================================================================================
// control centre
// =================================================================================================================================
class AdminControlPage extends StatelessWidget {
  const AdminControlPage({super.key});
  @override
  Widget build(BuildContext context) => _Tabbed(
        tabs: [
          _t(context, 'نظرة عامة', 'Übersicht', 'Overview'),
          _t(context, 'المعلمات', 'Lehrerinnen', 'Teachers'),
          _t(context, 'الأطفال', 'Kinder', 'Children'),
          _t(context, 'الأنشطة', 'Aktivität', 'Activity'),
          _t(context, 'النظام', 'System', 'System'),
          _t(context, 'الصلاحيات', 'Rechte', 'Permissions'),
        ],
        pages: const [_ControlOverview(), _ControlTeachers(), _ControlChildren(), _ControlActivity(), _ControlSystem(), _ControlGrants()],
      );
}

const _taskText = {
  'requests_pending': ['طلبات تسجيل بانتظار الموافقة', 'Anmeldeanträge warten', 'Registration requests waiting'],
  'accounts_pending': ['حسابات بانتظار الموافقة', 'Konten warten auf Freigabe', 'Accounts waiting for approval'],
  'reports_in_review': ['تقارير بانتظار المراجعة', 'Berichte warten auf Prüfung', 'Reports waiting for review'],
  'failed_sign_ins': ['محاولات دخول فاشلة في 24 ساعة', 'Fehlgeschlagene Anmeldungen (24 h)', 'Failed sign-ins in 24 hours'],
  'children_missing_info': ['أطفال تنقصهم معلومات', 'Kinder mit fehlenden Angaben', 'Children with missing information'],
  'invoices_unpaid': ['فواتير غير مسددة', 'Offene Rechnungen', 'Unpaid invoices'],
};

class _ControlOverview extends StatelessWidget {
  const _ControlOverview();
  @override
  Widget build(BuildContext context) => _load(context, '/api/admin/control/overview', (context, data, reload) {
        final d = _m(data);
        final p = _m(d['people']);
        final tasks = _l(d['tasks']);
        final f = d['finance'] == null ? null : _m(d['finance']);
        final sys = _m(d['system']);
        int n(Object? v) => (v as num? ?? 0).toInt();
        return ListView(padding: const EdgeInsets.all(12), children: [
          _Box(
            title: '${_t(context, 'نظرة عامة', 'Übersicht', 'Overview')} · ${_str(d['today'])}',
            child: _kpis([
              _Kpi(_t(context, 'أطفال نشطون', 'Aktive Kinder', 'Active children'), '${n(p['children_active'])}'),
              _Kpi(_t(context, 'جدد في 30 يوماً', 'Neu in 30 Tagen', 'New in 30 days'), '${n(p['children_new_30d'])}'),
              _Kpi(_t(context, 'موظفون نشطون', 'Aktives Personal', 'Active staff'), '${n(p['employees_active'])}'),
              _Kpi(_t(context, 'المعلمات', 'Lehrerinnen', 'Teachers'), '${n(p['teachers'])}'),
              _Kpi(_t(context, 'حسابات الأهالي', 'Elternkonten', 'Parent accounts'), '${n(p['parents'])}'),
              _Kpi(_t(context, 'بانتظار الموافقة', 'Warten auf Freigabe', 'Waiting for approval'), '${n(p['accounts_pending']) + n(p['requests_pending'])}', tone: n(p['accounts_pending']) + n(p['requests_pending']) > 0 ? _bad : null),
              _Kpi(_t(context, 'تقارير للمراجعة', 'Berichte zu prüfen', 'Reports to review'), '${n(p['reports_in_review'])}', tone: n(p['reports_in_review']) > 0 ? _bad : null),
            ]),
          ),
          _Box(
            title: _t(context, 'يحتاج انتباهك', 'Braucht deine Aufmerksamkeit', 'Needs your attention'),
            child: tasks.isEmpty
                ? _empty(_t(context, 'لا توجد مهام مفتوحة', 'Keine offenen Aufgaben', 'No open tasks'))
                : Column(children: [
                    for (final t in tasks)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(Icons.flag_rounded, color: t['priority'] == 'high' ? _bad : (t['priority'] == 'medium' ? const Color(0xFFB7791F) : _muted)),
                        title: Text(() {
                          final x = _taskText[t['kind']];
                          return x == null ? _str(t['kind']) : _t(context, x[0], x[1], x[2]);
                        }()),
                        trailing: Text('${n(t['count'])}', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                      ),
                  ]),
          ),
          if (f != null)
            _Box(
              title: _t(context, 'المال هذا الشهر، لكل عملة على حدة', 'Geld in diesem Monat, je Währung', 'Money this month, each currency apart'),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                for (final code in ['SYP', 'USD']) ...[
                  Padding(padding: const EdgeInsets.only(top: 6, bottom: 6), child: Text(code, style: const TextStyle(fontWeight: FontWeight.w800))),
                  _kpis([
                    _Kpi(_t(context, 'الإيرادات', 'Einnahmen', 'Income'), _str(_m(_m(f['currencies'])[code])['income'])),
                    _Kpi(_t(context, 'المصروفات', 'Ausgaben', 'Expenses'), _str(_m(_m(f['currencies'])[code])['expense'])),
                    _Kpi(_t(context, 'الفائض / العجز', 'Überschuss / Fehlbetrag', 'Surplus / deficit'), _str(_m(_m(f['currencies'])[code])['surplus'])),
                    _Kpi(_t(context, 'متبقٍّ على الفواتير', 'Offen auf Rechnungen', 'Open on invoices'), _str(_m(_m(f['currencies'])[code])['open_invoices'])),
                  ]),
                ],
              ]),
            ),
          _Box(
            title: _t(context, 'النظام', 'System', 'System'),
            child: Column(children: [
              _row(_t(context, 'آخر فحص ناجح', 'Letzte erfolgreiche Prüfung', 'Last successful check'), sys['last_success_at'] == null ? '—' : _when(sys['last_success_at']), ltr: true),
              _row(_t(context, 'دخول فاشل (24 ساعة)', 'Fehlgeschlagene Anmeldungen (24 h)', 'Failed sign-ins (24 h)'), _str(sys['failed_sign_ins_24h'])),
            ]),
          ),
        ]);
      });
}

class _ControlTeachers extends StatefulWidget {
  const _ControlTeachers();
  @override
  State<_ControlTeachers> createState() => _ControlTeachersState();
}

class _ControlTeachersState extends State<_ControlTeachers> {
  DateTime _day = DateTime.now();
  String get _dayText => '${_day.year}-${_day.month.toString().padLeft(2, '0')}-${_day.day.toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) => Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
          child: Row(children: [
            Text(_t(context, 'اليوم', 'Tag', 'Day'), style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(width: 10),
            OutlinedButton.icon(
              icon: const Icon(Icons.calendar_today_outlined, size: 18),
              label: Text(_dayText, textDirection: TextDirection.ltr),
              onPressed: () async {
                final d = await showDatePicker(context: context, initialDate: _day, firstDate: DateTime(2024), lastDate: DateTime.now());
                if (d != null) setState(() => _day = d);
              },
            ),
          ]),
        ),
        Expanded(
          child: _load(context, '/api/admin/control/teachers/activity', key: ValueKey(_dayText), query: {'day': _dayText}, (context, data, reload) {
            final d = _m(data);
            final list = _l(d['teachers']);
            return ListView(padding: const EdgeInsets.all(12), children: [
              Text('${_t(context, 'معلمات نشطات في هذا اليوم', 'An diesem Tag aktiv', 'Active that day')}: ${_str(d['active'])}', style: const TextStyle(color: _muted)),
              const SizedBox(height: 8),
              if (list.isEmpty) _empty(_t(context, 'لا توجد معلمات', 'Keine Lehrerinnen', 'No teachers')),
              for (final t in list)
                _Box(
                  title: _str(t['name']),
                  hint: '${_t(context, 'آخر ظهور', 'Zuletzt gesehen', 'Last seen')}: ${t['last_seen'] == null ? _t(context, 'لم تدخل بعد', 'noch nie', 'never') : _when(t['last_seen'])}',
                  child: Column(children: [
                    _row(_t(context, 'تقارير أُنشئت', 'Berichte erstellt', 'Reports made'), _str(t['reports_created'])),
                    _row(_t(context, 'تقارير عُدّلت', 'Berichte geändert', 'Reports changed'), _str(t['reports_changed'])),
                    _row(_t(context, 'مسودات', 'Entwürfe', 'Drafts'), _str(t['drafts_open'])),
                    _row(_t(context, 'بانتظار المراجعة', 'In Prüfung', 'In review'), _str(t['reports_submitted_open'])),
                    _row(_t(context, 'أُعيدت', 'Zurückgegeben', 'Returned'), _str(t['returned_open'])),
                    _row(_t(context, 'منشورات', 'Beiträge', 'Posts'), _str(t['posts'])),
                    _row(_t(context, 'ملفات مرفوعة', 'Hochgeladene Dateien', 'Files uploaded'), _str(t['files_uploaded'])),
                  ]),
                ),
            ]);
          }),
        ),
      ]);
}

const _missingText = {
  'birth_date': ['تاريخ الميلاد', 'Geburtsdatum', 'birth date'],
  'group': ['المجموعة', 'Gruppe', 'group'],
  'guardian': ['ولي الأمر', 'Erziehungsberechtigte', 'guardian'],
};

class _ControlChildren extends StatelessWidget {
  const _ControlChildren();
  @override
  Widget build(BuildContext context) => _load(context, '/api/admin/control/children', (context, data, reload) {
        final d = _m(data);
        return ListView(padding: const EdgeInsets.all(12), children: [
          _kpis([
            _Kpi(_t(context, 'نشطون', 'Aktiv', 'Active'), _str(d['active'])),
            _Kpi(_t(context, 'جدد (30 يوماً)', 'Neu (30 Tage)', 'New (30 days)'), '${_l(d['new_last_30_days']).length}'),
            _Kpi(_t(context, 'غادروا (30 يوماً)', 'Ausgeschieden (30 Tage)', 'Left (30 days)'), '${_l(d['left_last_30_days']).length}'),
            _Kpi(_t(context, 'بلا تقرير منشور (30 يوماً)', 'Ohne veröffentlichten Bericht (30 Tage)', 'No published report (30 days)'), _str(d['without_published_report_30d'])),
          ]),
          const SizedBox(height: 12),
          _Box(
            title: _t(context, 'المجموعات', 'Gruppen', 'Groups'),
            child: Column(children: [
              if (_l(d['groups']).isEmpty) _empty(_t(context, 'لا توجد مجموعات', 'Keine Gruppen', 'No groups')),
              for (final g in _l(d['groups'])) _row(_str(g['name']).isEmpty ? _t(context, 'بلا مجموعة', 'ohne Gruppe', 'no group') : _str(g['name']), _str(g['children'])),
            ]),
          ),
          _Box(
            title: _t(context, 'معلومات ناقصة', 'Fehlende Angaben', 'Missing information'),
            child: Column(children: [
              if (_l(d['missing_information']).isEmpty) _empty(_t(context, 'كل البيانات مكتملة', 'Alles vollständig', 'Everything complete')),
              for (final c in _l(d['missing_information']))
                _row(_str(c['name']), [
                  for (final x in (c['missing'] as List? ?? const []))
                    () {
                      final m = _missingText['$x'];
                      return m == null ? '$x' : _t(context, m[0], m[1], m[2]);
                    }(),
                ].join('، ')),
            ]),
          ),
        ]);
      });
}

class _ControlSystem extends StatelessWidget {
  const _ControlSystem();
  @override
  Widget build(BuildContext context) => _load(context, '/api/admin/control/system', (context, data, reload) {
        final s = _m(data);
        final db = _m(s['database']);
        final mig = _m(s['migrations']);
        Widget line(String label, bool? ok, String text) => ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.circle, size: 14, color: ok == true ? _good : (ok == false ? _bad : const Color(0xFFB8C2CE))),
              title: Text(label),
              trailing: Text(text, textDirection: TextDirection.ltr, style: const TextStyle(fontWeight: FontWeight.w700)),
            );
        final failures = _l(s['recent_failures']);
        return ListView(padding: const EdgeInsets.all(12), children: [
          _Box(
            title: _t(context, 'حالة النظام', 'Systemstatus', 'System status'),
            hint: _t(context, 'ما لا يستطيع النظام فحصه يظهر رمادياً ولا يظهر أبداً كأنه سليم.', 'Was das System nicht prüfen kann, ist grau und nie als „in Ordnung" gezeigt.', 'What cannot be checked is grey, never shown as fine.'),
            child: Column(children: [
              line(_t(context, 'الخادم', 'Server', 'Server'), true, _t(context, 'يردّ', 'antwortet', 'answering')),
              line(_t(context, 'قاعدة البيانات', 'Datenbank', 'Database'), db['ok'] == true, db['ok'] == true ? '${_str(db['milliseconds'])} ms' : _t(context, 'لا يمكن الوصول', 'nicht erreichbar', 'not reachable')),
              line(_t(context, 'إصدار قاعدة البيانات', 'Datenbankversion', 'Database version'), mig['known'] == true ? mig['ok'] == true : null, mig['known'] == true ? _str(mig['current']) : _t(context, 'غير معروف', 'unbekannt', 'not available')),
              line(_t(context, 'آخر فحص ناجح', 'Letzte erfolgreiche Prüfung', 'Last successful check'), s['last_success_at'] == null ? null : true, s['last_success_at'] == null ? '—' : _when(s['last_success_at'])),
              line(_t(context, 'دخول فاشل في 24 ساعة', 'Fehlgeschlagene Anmeldungen (24 h)', 'Failed sign-ins in 24 h'), ((s['failed_sign_ins_24h'] as num?) ?? 0) < 3, _str(s['failed_sign_ins_24h'])),
            ]),
          ),
          if (failures.isNotEmpty)
            _Box(
              title: _t(context, 'آخر الأعطال', 'Letzte Fehler', 'Latest failures'),
              child: Column(children: [for (final f in failures) _row(_when(f['at']), _str(f['details']))]),
            ),
        ]);
      });
}

class _ControlGrants extends StatefulWidget {
  const _ControlGrants();
  @override
  State<_ControlGrants> createState() => _ControlGrantsState();
}

class _ControlGrantsState extends State<_ControlGrants> {
  int _round = 0;
  final _user = TextEditingController();
  String _grant = 'control.view';

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    final names = {
      'control.view': _t(context, 'لوحة المتابعة', 'Kontrollzentrale', 'Control centre'),
      'finance.view': _t(context, 'الأرقام المالية', 'Geldzahlen', 'Money figures'),
      'books.correct': _t(context, 'المحاسبة: تعديل وإلغاء', 'Buchhaltung: ändern und stornieren', 'Accounting: change and cancel'),
      'books.export': _t(context, 'المحاسبة: تصدير PDF', 'Buchhaltung: PDF-Export', 'Accounting: PDF export'),
    };
    return _load(context, '/api/admin/control/grants', key: ValueKey(_round), (context, data, reload) {
      final rows = _l(data);
      return ListView(padding: const EdgeInsets.all(12), children: [
        _Box(
          title: _t(context, 'منح صلاحية لحساب', 'Einem Konto ein Recht geben', 'Give an account a permission'),
          hint: _t(context, 'المدير (قسم الإدارة) لا يرى لوحة المتابعة إلا إذا منحته هنا. الأرقام المالية صلاحية منفصلة.', 'Die Leitung sieht die Kontrollzentrale nur, wenn du sie hier freigibst. Geldzahlen sind ein eigenes Recht.', 'A manager only sees the control centre when granted here. Money figures are a separate permission.'),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            TextField(controller: _user, textDirection: TextDirection.ltr, decoration: InputDecoration(labelText: _t(context, 'اسم المستخدم', 'Benutzername', 'Username'))),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: _grant,
              isExpanded: true,
              decoration: InputDecoration(labelText: _t(context, 'الصلاحية', 'Recht', 'Permission')),
              items: [for (final e in names.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
              onChanged: (v) => setState(() => _grant = v ?? _grant),
            ),
            const SizedBox(height: 12),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: FilledButton.icon(
                style: FilledButton.styleFrom(minimumSize: const Size(140, 46)),
                icon: const Icon(Icons.add_rounded),
                label: Text(_t(context, 'منح', 'Freigeben', 'Grant')),
                onPressed: () async {
                  if (_user.text.trim().isEmpty) return;
                  final ok = await _run(context, () => api.post('/api/admin/control/grants', {'username': _user.text.trim(), 'grant': _grant}), done: _t(context, 'تم المنح.', 'Freigegeben.', 'Granted.'));
                  if (ok) {
                    setState(() {
                      _user.clear();
                      _round++;
                    });
                  }
                },
              ),
            ),
          ]),
        ),
        _Box(
          title: _t(context, 'الصلاحيات الممنوحة', 'Vergebene Rechte', 'Granted permissions'),
          child: Column(children: [
            if (rows.isEmpty) _empty(_t(context, 'لم تُمنح صلاحيات فردية', 'Keine Einzelrechte vergeben', 'No individual permissions granted')),
            for (final g in rows)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(_str(g['username']), style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text('${names[g['grant']] ?? _str(g['grant'])} · ${_t(context, 'منحها', 'von', 'by')} ${_str(g['granted_by'])}'),
                trailing: IconButton(
                  tooltip: _t(context, 'سحب', 'Entziehen', 'Remove'),
                  icon: const Icon(Icons.remove_circle_outline, color: _bad),
                  onPressed: () async {
                    if (!await confirmDelete(context) || !context.mounted) return;
                    if (await _run(context, () => api.delete('/api/admin/control/grants/${g['id']}'))) await reload();
                  },
                ),
              ),
          ]),
        ),
      ]);
    });
  }
}

// =================================================================================================================================
// accounts and registration requests
// =================================================================================================================================
class AdminAccountsPage extends StatefulWidget {
  const AdminAccountsPage({super.key});
  @override
  State<AdminAccountsPage> createState() => _AdminAccountsPageState();
}

class _AdminAccountsPageState extends State<AdminAccountsPage> {
  int _round = 0;
  void _again() => setState(() => _round++);

  @override
  Widget build(BuildContext context) => Stack(children: [
        _Tabbed(
          tabs: [_t(context, 'الحسابات', 'Konten', 'Accounts'), _t(context, 'طلبات التسجيل', 'Anmeldeanträge', 'Registration requests')],
          pages: [_AccountsList(key: ValueKey('a$_round'), onChanged: _again), _RequestsList(key: ValueKey('r$_round'))],
        ),
        PositionedDirectional(
          end: 16,
          bottom: 16,
          child: FloatingActionButton.extended(
            heroTag: 'newAccount',
            icon: const Icon(Icons.person_add_alt_1_rounded),
            label: Text(_t(context, 'حساب جديد', 'Neues Konto', 'New account')),
            onPressed: () async {
              final made = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const _NewAccountPage()));
              if (made == true) _again();
            },
          ),
        ),
      ]);
}

class _AccountsList extends StatefulWidget {
  const _AccountsList({super.key, required this.onChanged});
  final VoidCallback onChanged;
  @override
  State<_AccountsList> createState() => _AccountsListState();
}

class _AccountsListState extends State<_AccountsList> {
  String _q = '';
  @override
  Widget build(BuildContext context) => _load(context, '/api/admin/platform/accounts', (context, data, reload) {
        final all = _l(data);
        final needle = _q.trim().toLowerCase();
        final rows = needle.isEmpty
            ? all
            : all.where((a) => '${a['username']} ${a['full_name'] ?? ''} ${a['guardian_name'] ?? ''}'.toLowerCase().contains(needle)).toList();
        return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 90), children: [
          SuggestSearchField(
            hint: _t(context, 'بحث بالاسم', 'Nach Namen suchen', 'Search by name'),
            searchOnType: true,
            suggestions: [for (final a in all) ...[a['username'], a['full_name'], a['guardian_name'], a['child_name']].whereType<String>()],
            onSearch: (v) => setState(() => _q = v),
          ),
          const SizedBox(height: 10),
          if (rows.isEmpty) _empty(_t(context, 'لا توجد حسابات', 'Keine Konten', 'No accounts')),
          for (final a in rows)
            Card(
              child: ListTile(
                leading: AvatarInitials(_str(a['full_name']).isNotEmpty ? _str(a['full_name']) : _str(a['username'])),
                title: Text(_str(a['username']), style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text([
                  [for (final r in (a['roles'] as List? ?? const [])) _role(context, '$r')].join(' + '),
                  if (_str(a['full_name']).isNotEmpty) _str(a['full_name']),
                  if (_str(a['guardian_name']).isNotEmpty) _str(a['guardian_name']),
                ].join(' · ')),
                trailing: _statusPill(context, _str(a['approval_status'])),
                onTap: () async {
                  final changed = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => _AccountPage(account: a)));
                  if (changed == true) await reload();
                },
              ),
            ),
        ]);
      });
}

Widget _statusPill(BuildContext context, String status) => switch (status) {
      'active' => Pill(_t(context, 'نشط', 'aktiv', 'active'), foreground: _good, background: const Color(0xFFE6F4EC)),
      'pending' => Pill(_t(context, 'بانتظار التفعيل', 'wartet', 'waiting'), foreground: const Color(0xFF8A5200), background: const Color(0xFFFDF1DD)),
      _ => Pill(_t(context, 'موقوف', 'gesperrt', 'disabled'), foreground: _bad, background: const Color(0xFFFCE9E6)),
    };

/// One account: name, language, roles; a new password; switch it on or off.
class _AccountPage extends StatefulWidget {
  const _AccountPage({required this.account});
  final Map<String, dynamic> account;
  @override
  State<_AccountPage> createState() => _AccountPageState();
}

class _AccountPageState extends State<_AccountPage> {
  late final _username = TextEditingController(text: _str(widget.account['username']));
  late final _fullName = TextEditingController(text: _str(widget.account['full_name']));
  late final _job = TextEditingController(text: _str(widget.account['job_title']));
  final _password = TextEditingController();
  late String _language = _str(widget.account['preferred_language']).isEmpty ? 'ar' : _str(widget.account['preferred_language']);
  late final Set<String> _roles = {for (final r in (widget.account['roles'] as List? ?? const [])) '$r'};
  late String _status = _str(widget.account['approval_status']);
  bool _busy = false;
  bool _changed = false;

  Future<void> _save() async {
    if (_roles.isEmpty) {
      toast(context, _t(context, 'اختر دوراً واحداً على الأقل.', 'Mindestens eine Rolle wählen.', 'Choose at least one role.'));
      return;
    }
    final api = SessionScope.of(context).api;
    setState(() => _busy = true);
    final ok = await _run(context, () => api.patch('/api/admin/platform/accounts/${widget.account['id']}', {
          'username': _username.text.trim(),
          'preferred_language': _language,
          'roles': _roles.toList(),
          'full_name': _fullName.text.trim(),
          'job_title': _job.text.trim(),
        }), done: _t(context, 'تم حفظ بيانات الحساب.', 'Konto gespeichert.', 'Account saved.'));
    if (mounted) setState(() => _busy = false);
    if (ok) _changed = true;
  }

  Future<void> _newPassword() async {
    final api = SessionScope.of(context).api;
    try {
      final res = _m(await api.post('/api/admin/platform/accounts/${widget.account['id']}/reset-password', _password.text.isEmpty ? {} : {'password': _password.text}));
      _password.clear();
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          title: Text('${_t(context, 'كلمة المرور الجديدة', 'Neues Passwort', 'New password')} · ${_str(res['username'])}'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            SelectableText(_str(res['password']), textDirection: TextDirection.ltr, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, letterSpacing: 1.5)),
            const SizedBox(height: 10),
            Text(_t(context, 'تظهر مرة واحدة فقط. أُنهيت جلسات هذا الحساب. سلّمها للمستخدم بطريقة آمنة.', 'Wird nur einmal gezeigt. Die Sitzungen dieses Kontos wurden beendet. Sicher weitergeben.', 'Shown once only. The sessions of this account were ended. Hand it over safely.'),
                style: const TextStyle(color: _muted)),
          ]),
          actions: [
            TextButton(onPressed: () => Clipboard.setData(ClipboardData(text: _str(res['password']))), child: Text(_t(context, 'نسخ', 'Kopieren', 'Copy'))),
            FilledButton(onPressed: () => Navigator.pop(context), child: Text(_t(context, 'تم', 'Fertig', 'Done'))),
          ],
        ),
      );
    } on ApiException catch (e) {
      if (mounted) toast(context, e.detail.isNotEmpty ? e.detail : problemText(context, e));
    }
  }

  Future<void> _setStatus(String status) async {
    final api = SessionScope.of(context).api;
    if (await _run(context, () => api.patch('/api/admin/platform/accounts/${widget.account['id']}/status', {'status': status}), done: _t(context, 'تم تحديث حالة الحساب.', 'Status geändert.', 'Status changed.'))) {
      setState(() => _status = status);
      _changed = true;
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.account;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.pop(context, _changed);
      },
      child: Scaffold(
        appBar: AppBar(title: Text(_str(a['username']))),
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: ListView(padding: const EdgeInsets.all(16), children: [
              if (_busy) const LinearProgressIndicator(),
              if (_str(a['guardian_name']).isNotEmpty)
                FormSection(
                  title: _t(context, 'بيانات ولي الأمر', 'Angaben der Eltern', 'Parent details'),
                  child: Column(children: [
                    _row(_t(context, 'الاسم', 'Name', 'Name'), _str(a['guardian_name'])),
                    _row(_t(context, 'الهاتف', 'Telefon', 'Phone'), _str(a['phone']), ltr: true),
                    _row(_t(context, 'البريد', 'E-Mail', 'Email'), _str(a['email']), ltr: true),
                    _row(_t(context, 'الطفل', 'Kind', 'Child'), _str(a['child_name'])),
                  ]),
                ),
              FormSection(
                title: _t(context, 'الحالة', 'Status', 'Status'),
                trailing: _statusPill(context, _status),
                child: Align(
                  alignment: AlignmentDirectional.centerStart,
                  child: _status == 'active'
                      ? OutlinedButton.icon(
                          style: OutlinedButton.styleFrom(foregroundColor: _bad, minimumSize: const Size(160, 44)),
                          icon: const Icon(Icons.block),
                          label: Text(_t(context, 'إيقاف الحساب', 'Konto sperren', 'Disable account')),
                          onPressed: () => _setStatus('disabled'),
                        )
                      : FilledButton.icon(
                          style: FilledButton.styleFrom(minimumSize: const Size(160, 44)),
                          icon: const Icon(Icons.check_circle_outline),
                          label: Text(_t(context, 'تفعيل الحساب', 'Konto freigeben', 'Activate account')),
                          onPressed: () => _setStatus('active'),
                        ),
                ),
              ),
              FormSection(
                title: _t(context, 'البيانات', 'Angaben', 'Details'),
                child: Column(children: [
                  TextField(controller: _username, textDirection: TextDirection.ltr, decoration: InputDecoration(labelText: _t(context, 'اسم المستخدم', 'Benutzername', 'Username'))),
                  const SizedBox(height: 10),
                  TextField(controller: _fullName, maxLength: 120, decoration: InputDecoration(labelText: _t(context, 'الاسم الكامل', 'Vollständiger Name', 'Full name'))),
                  TextField(controller: _job, maxLength: 80, decoration: InputDecoration(labelText: _t(context, 'المسمى الوظيفي', 'Tätigkeit', 'Job title'))),
                  DropdownButtonFormField<String>(
                    initialValue: _language,
                    decoration: InputDecoration(labelText: _t(context, 'اللغة', 'Sprache', 'Language')),
                    items: const [DropdownMenuItem(value: 'ar', child: Text('العربية')), DropdownMenuItem(value: 'en', child: Text('English')), DropdownMenuItem(value: 'de', child: Text('Deutsch'))],
                    onChanged: (v) => setState(() => _language = v ?? _language),
                  ),
                ]),
              ),
              FormSection(
                title: _t(context, 'الأدوار (يمكن اختيار أكثر من دور)', 'Rollen (mehrere möglich)', 'Roles (several possible)'),
                child: Column(children: [
                  for (final r in _roleNames.keys)
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      controlAffinity: ListTileControlAffinity.leading,
                      value: _roles.contains(r),
                      title: Text(_role(context, r)),
                      onChanged: (v) => setState(() => v == true ? _roles.add(r) : _roles.remove(r)),
                    ),
                ]),
              ),
              FormSection(
                title: _t(context, 'كلمة مرور جديدة', 'Neues Passwort', 'New password'),
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Text(_t(context, 'لا يمكن عرض كلمة المرور الحالية. اترك الحقل فارغاً لتُولَّد تلقائياً (12 محرفاً على الأقل).', 'Das aktuelle Passwort lässt sich nicht anzeigen. Leer lassen, dann wird eines erzeugt (mindestens 12 Zeichen).', 'The current password cannot be shown. Leave empty to generate one (at least 12 characters).'),
                      style: const TextStyle(color: _muted, fontSize: 12.5)),
                  const SizedBox(height: 8),
                  TextField(controller: _password, textDirection: TextDirection.ltr, decoration: InputDecoration(labelText: _t(context, 'كلمة المرور (اختياري)', 'Passwort (optional)', 'Password (optional)'))),
                  const SizedBox(height: 10),
                  Align(
                    alignment: AlignmentDirectional.centerStart,
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(minimumSize: const Size(200, 44)),
                      icon: const Icon(Icons.key_rounded),
                      label: Text(_t(context, 'تعيين كلمة المرور الجديدة', 'Neues Passwort setzen', 'Set the new password')),
                      onPressed: _newPassword,
                    ),
                  ),
                ]),
              ),
            ]),
          ),
        ),
        bottomNavigationBar: BottomActionBar(children: [
          Expanded(child: FilledButton(onPressed: _busy ? null : _save, child: Text(_t(context, 'حفظ البيانات', 'Speichern', 'Save')))),
        ]),
      ),
    );
  }
}

/// A new account (teacher, accountant, management, parent or admin), active at once.
class _NewAccountPage extends StatefulWidget {
  const _NewAccountPage();
  @override
  State<_NewAccountPage> createState() => _NewAccountPageState();
}

class _NewAccountPageState extends State<_NewAccountPage> {
  String _kind = 'teacher';
  String? _child;
  List<Map<String, dynamic>> _children = [];
  final _fullName = TextEditingController();
  final _job = TextEditingController();
  final _username = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        final list = _l(await SessionScope.of(context).api.get('/api/admin/platform/children'));
        if (mounted) setState(() => _children = list);
      } catch (_) {}
    });
  }

  Future<void> _create() async {
    if (!RegExp(r'^[A-Za-z0-9_.\-]{3,80}$').hasMatch(_username.text.trim()) || _password.text.length < 12) {
      toast(context, _t(context, 'اسم المستخدم (3 أحرف لاتينية على الأقل) أو كلمة المرور (12 محرفاً على الأقل) غير صالحة.', 'Benutzername (mind. 3 lateinische Zeichen) oder Passwort (mind. 12 Zeichen) ungültig.', 'Username (3+ latin characters) or password (12+ characters) not valid.'));
      return;
    }
    final api = SessionScope.of(context).api;
    setState(() => _busy = true);
    final ok = await _run(context, () => api.post('/api/admin/platform/teacher-accounts', {
          'role': _kind,
          'full_name': _fullName.text.trim(),
          'job_title': _job.text.trim(),
          'child_id': _kind == 'parent' ? _child : null,
          'username': _username.text.trim(),
          'password': _password.text,
          'preferred_language': 'ar',
        }), done: _t(context, 'تم إنشاء الحساب وتفعيله.', 'Konto erstellt und freigegeben.', 'Account created and active.'));
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(_t(context, 'حساب جديد', 'Neues Konto', 'New account'))),
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: ListView(padding: const EdgeInsets.all(16), children: [
              if (_busy) const LinearProgressIndicator(),
              FormSection(
                title: _t(context, 'نوع الحساب', 'Art des Kontos', 'Kind of account'),
                child: Column(children: [
                  DropdownButtonFormField<String>(
                    initialValue: _kind,
                    isExpanded: true,
                    items: [for (final r in ['teacher', 'accountant', 'manager', 'parent', 'admin']) DropdownMenuItem(value: r, child: Text(_role(context, r)))],
                    onChanged: (v) => setState(() => _kind = v ?? _kind),
                  ),
                  if (_kind == 'parent') ...[
                    const SizedBox(height: 10),
                    DropdownButtonFormField<String?>(
                      initialValue: _child,
                      isExpanded: true,
                      decoration: InputDecoration(labelText: _t(context, 'الطفل (اختياري)', 'Kind (optional)', 'Child (optional)')),
                      items: [
                        DropdownMenuItem<String?>(value: null, child: Text(_t(context, '— بدون ربط الآن —', '— jetzt nicht verknüpfen —', '— not now —'))),
                        for (final c in _children) DropdownMenuItem<String?>(value: _str(c['id']), child: Text(_str(c['display_name']))),
                      ],
                      onChanged: (v) => setState(() => _child = v),
                    ),
                  ],
                ]),
              ),
              FormSection(
                title: _t(context, 'البيانات', 'Angaben', 'Details'),
                child: Column(children: [
                  TextField(controller: _fullName, maxLength: 120, decoration: InputDecoration(labelText: _t(context, 'الاسم الكامل', 'Vollständiger Name', 'Full name'))),
                  TextField(controller: _job, maxLength: 80, decoration: InputDecoration(labelText: _t(context, 'المسمى الوظيفي', 'Tätigkeit', 'Job title'))),
                  TextField(controller: _username, maxLength: 80, textDirection: TextDirection.ltr, decoration: InputDecoration(labelText: _t(context, 'اسم المستخدم', 'Benutzername', 'Username'))),
                  TextField(controller: _password, maxLength: 256, textDirection: TextDirection.ltr, decoration: InputDecoration(labelText: _t(context, 'كلمة المرور الأولية (12 محرفاً على الأقل)', 'Erstes Passwort (mindestens 12 Zeichen)', 'First password (at least 12 characters)'))),
                ]),
              ),
            ]),
          ),
        ),
        bottomNavigationBar: BottomActionBar(children: [
          Expanded(child: FilledButton(onPressed: _busy ? null : _create, child: Text(_t(context, 'إنشاء الحساب', 'Konto erstellen', 'Create account')))),
        ]),
      );
}

class _RequestsList extends StatelessWidget {
  const _RequestsList({super.key});

  Future<void> _showCode(BuildContext context, Map<String, dynamic> result) async {
    final code = _str(result['registration_code']);
    final req = _m(result['request']);
    await showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text('${_t(context, 'رمز التسجيل', 'Anmeldecode', 'Registration code')} · ${_str(req['guardian_name'])}'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          SelectableText(code, textDirection: TextDirection.ltr, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: 4)),
          const SizedBox(height: 10),
          Text(
            req['email_sent'] == true
                ? _t(context, 'أُرسل الرمز إلى بريد ولي الأمر. يظهر هنا مرة واحدة فقط (صالح 7 أيام).', 'Der Code wurde per E-Mail geschickt. Er wird nur einmal gezeigt (7 Tage gültig).', 'The code was emailed. Shown once only (valid 7 days).')
                : _t(context, 'لم يُرسل البريد. سلّم الرمز إلى ولي الأمر يدوياً. يظهر هنا مرة واحدة فقط (صالح 7 أيام).', 'Keine E-Mail verschickt. Den Code selbst weitergeben. Er wird nur einmal gezeigt (7 Tage gültig).', 'No email sent. Hand the code over yourself. Shown once only (valid 7 days).'),
            style: const TextStyle(color: _muted),
          ),
        ]),
        actions: [
          TextButton(onPressed: () => Clipboard.setData(ClipboardData(text: code)), child: Text(_t(context, 'نسخ الرمز', 'Code kopieren', 'Copy code'))),
          FilledButton(onPressed: () => Navigator.pop(context), child: Text(_t(context, 'تم', 'Fertig', 'Done'))),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return _load(context, '/api/admin/platform/registration-requests', (context, data, reload) {
      final items = _l(data);
      return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 90), children: [
        Text(_t(context, 'عند الموافقة يُنشأ رمز تسجيل لمرة واحدة يُرسل إلى بريد ولي الأمر.', 'Bei Zustimmung entsteht ein einmaliger Anmeldecode, der an die Eltern geht.', 'Approving makes a one-time registration code sent to the parent.'), style: const TextStyle(color: _muted)),
        const SizedBox(height: 8),
        if (items.isEmpty) _empty(_t(context, 'لا توجد طلبات تسجيل.', 'Keine Anmeldeanträge.', 'No registration requests.')),
        for (final r in items)
          _Box(
            title: _str(r['guardian_name']),
            trailing: Pill(r['status'] == 'pending'
                ? _t(context, 'بانتظار القرار', 'offen', 'waiting')
                : r['status'] == 'approved'
                    ? (r['registered'] == true ? _t(context, 'سُجّل', 'registriert', 'registered') : _t(context, 'موافق عليه', 'zugestimmt', 'approved'))
                    : _t(context, 'مرفوض', 'abgelehnt', 'rejected')),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              _row(_t(context, 'الهاتف', 'Telefon', 'Phone'), _str(r['phone']), ltr: true),
              _row(_t(context, 'البريد', 'E-Mail', 'Email'), _str(r['email']), ltr: true),
              _row(_t(context, 'الطفل', 'Kind', 'Child'), '${_str(r['child_name'])}${_str(r['child_birth_date']).isEmpty ? '' : ' (${_str(r['child_birth_date'])})'}'),
              if (_str(r['relationship_to_child']).isNotEmpty) _row(_t(context, 'صلة القرابة', 'Verwandtschaft', 'Relationship'), _str(r['relationship_to_child'])),
              if (_str(r['notes']).isNotEmpty) _row(_t(context, 'ملاحظات', 'Notizen', 'Notes'), _str(r['notes'])),
              const SizedBox(height: 8),
              Wrap(spacing: 8, runSpacing: 8, children: [
                if (r['status'] == 'pending') ...[
                  FilledButton(
                    onPressed: () async {
                      try {
                        final res = _m(await api.post('/api/admin/platform/registration-requests/${r['id']}/decision', {'decision': 'approve'}));
                        if (context.mounted) await _showCode(context, res);
                        await reload();
                      } on ApiException catch (e) {
                        if (context.mounted) toast(context, e.detail.isNotEmpty ? e.detail : problemText(context, e));
                      }
                    },
                    child: Text(_t(context, 'موافقة وإنشاء الرمز', 'Zustimmen und Code erzeugen', 'Approve and make code')),
                  ),
                  OutlinedButton(
                    style: OutlinedButton.styleFrom(foregroundColor: _bad),
                    onPressed: () async {
                      if (await _run(context, () => api.post('/api/admin/platform/registration-requests/${r['id']}/decision', {'decision': 'reject'}), done: _t(context, 'تم رفض الطلب.', 'Antrag abgelehnt.', 'Request rejected.'))) await reload();
                    },
                    child: Text(_t(context, 'رفض', 'Ablehnen', 'Reject')),
                  ),
                ],
                if (r['status'] == 'approved' && r['registered'] != true)
                  OutlinedButton(
                    onPressed: () async {
                      try {
                        final res = _m(await api.post('/api/admin/platform/registration-requests/${r['id']}/new-code'));
                        if (context.mounted) await _showCode(context, res);
                        await reload();
                      } on ApiException catch (e) {
                        if (context.mounted) toast(context, e.detail.isNotEmpty ? e.detail : problemText(context, e));
                      }
                    },
                    child: Text(_t(context, 'رمز جديد', 'Neuer Code', 'New code')),
                  ),
                OutlinedButton(
                  onPressed: () async {
                    final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => _RequestEditPage(item: r)));
                    if (saved == true) await reload();
                  },
                  child: Text(_t(context, 'تعديل', 'Bearbeiten', 'Edit')),
                ),
                if (r['registered'] != true)
                  OutlinedButton(
                    style: OutlinedButton.styleFrom(foregroundColor: _bad),
                    onPressed: () async {
                      if (!await confirmDelete(context) || !context.mounted) return;
                      if (await _run(context, () => api.delete('/api/admin/platform/registration-requests/${r['id']}'), done: _t(context, 'تم حذف الطلب.', 'Antrag gelöscht.', 'Request deleted.'))) await reload();
                    },
                    child: Text(_t(context, 'حذف الطلب', 'Antrag löschen', 'Delete request')),
                  ),
              ]),
            ]),
          ),
      ]);
    });
  }
}

class _RequestEditPage extends StatefulWidget {
  const _RequestEditPage({required this.item});
  final Map<String, dynamic> item;
  @override
  State<_RequestEditPage> createState() => _RequestEditPageState();
}

class _RequestEditPageState extends State<_RequestEditPage> {
  static const _fields = ['guardian_name', 'email', 'phone', 'child_name', 'child_birth_date', 'relationship_to_child', 'notes'];
  late final Map<String, TextEditingController> _c = {for (final f in _fields) f: TextEditingController(text: _str(widget.item[f]))};
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final labels = {
      'guardian_name': _t(context, 'اسم ولي الأمر', 'Name der Eltern', 'Parent name'),
      'email': _t(context, 'البريد الإلكتروني', 'E-Mail', 'Email'),
      'phone': _t(context, 'رقم الهاتف', 'Telefon', 'Phone'),
      'child_name': _t(context, 'اسم الطفل', 'Name des Kindes', 'Child name'),
      'child_birth_date': _t(context, 'تاريخ ميلاد الطفل (YYYY-MM-DD)', 'Geburtsdatum (JJJJ-MM-TT)', 'Birth date (YYYY-MM-DD)'),
      'relationship_to_child': _t(context, 'صلة القرابة', 'Verwandtschaft', 'Relationship'),
      'notes': _t(context, 'ملاحظات', 'Notizen', 'Notes'),
    };
    return Scaffold(
      appBar: AppBar(title: Text(_t(context, 'تعديل الطلب', 'Antrag bearbeiten', 'Edit request'))),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(padding: const EdgeInsets.all(16), children: [
            if (_busy) const LinearProgressIndicator(),
            for (final f in _fields)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: TextField(
                  controller: _c[f],
                  maxLines: f == 'notes' ? 3 : 1,
                  textDirection: f == 'email' || f == 'phone' || f == 'child_birth_date' ? TextDirection.ltr : null,
                  decoration: InputDecoration(labelText: labels[f]),
                ),
              ),
          ]),
        ),
      ),
      bottomNavigationBar: BottomActionBar(children: [
        Expanded(
          child: FilledButton(
            onPressed: _busy
                ? null
                : () async {
                    final api = SessionScope.of(context).api;
                    setState(() => _busy = true);
                    final ok = await _run(context, () => api.patch('/api/admin/platform/registration-requests/${widget.item['id']}', {
                          'preferred_language': 'ar',
                          for (final f in _fields) f: _c[f]!.text.trim(),
                        }), done: _t(context, 'تم حفظ التعديلات.', 'Gespeichert.', 'Saved.'));
                    if (!context.mounted) return;
                    setState(() => _busy = false);
                    if (ok) Navigator.pop(context, true);
                  },
            child: Text(_t(context, 'حفظ التعديلات', 'Speichern', 'Save')),
          ),
        ),
      ]),
    );
  }
}

// =================================================================================================================================
// children and reports
// =================================================================================================================================
class AdminChildrenPage extends StatelessWidget {
  const AdminChildrenPage({super.key});
  @override
  Widget build(BuildContext context) => _Tabbed(
        tabs: [_t(context, 'تقارير للمراجعة', 'Berichte prüfen', 'Reports to review'), _t(context, 'الأطفال والمعلمات', 'Kinder und Lehrerinnen', 'Children and teachers')],
        pages: const [_ReportsReview(), _ChildrenAssign()],
      );
}

class _ReportsReview extends StatelessWidget {
  const _ReportsReview();
  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return _load(context, '/api/admin/platform/reports', (context, data, reload) {
      final reports = _l(data);
      return ListView(padding: const EdgeInsets.all(12), children: [
        Text(_t(context, 'تظهر التقارير للأهل فقط بعد نشرها من هنا.', 'Berichte sehen die Eltern erst, wenn sie hier veröffentlicht sind.', 'Parents see reports only once published here.'), style: const TextStyle(color: _muted)),
        const SizedBox(height: 8),
        if (reports.isEmpty) _empty(_t(context, 'لا توجد تقارير بانتظار المراجعة.', 'Keine Berichte zu prüfen.', 'No reports to review.')),
        for (final r in reports)
          _Box(
            title: _str(r['title']),
            hint: '${_t(context, 'الطفل', 'Kind', 'Child')}: ${_str(r['child_name'])} · ${_t(context, 'المعلمة', 'Lehrerin', 'Teacher')}: ${_str(r['author'])}',
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text(_str(r['body']), style: const TextStyle(height: 1.5)),
              const SizedBox(height: 12),
              Wrap(spacing: 8, runSpacing: 8, children: [
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: _good),
                  onPressed: () async {
                    if (await _run(context, () => api.patch('/api/admin/platform/reports/${r['id']}', {'status': 'published'}), done: _t(context, 'تم نشر التقرير للأهل.', 'Bericht veröffentlicht.', 'Report published.'))) await reload();
                  },
                  child: Text(_t(context, 'نشر للأهل', 'Für Eltern veröffentlichen', 'Publish to parents')),
                ),
                OutlinedButton(
                  onPressed: () async {
                    if (await _run(context, () => api.patch('/api/admin/platform/reports/${r['id']}', {'status': 'rejected'}), done: _t(context, 'أُعيد التقرير للمعلمة.', 'Bericht zurückgegeben.', 'Report returned.'))) await reload();
                  },
                  child: Text(_t(context, 'إرجاع للتعديل', 'Zur Überarbeitung zurück', 'Return for changes')),
                ),
              ]),
            ]),
          ),
      ]);
    });
  }
}

class _ChildrenAssign extends StatefulWidget {
  const _ChildrenAssign();
  @override
  State<_ChildrenAssign> createState() => _ChildrenAssignState();
}

class _ChildrenAssignState extends State<_ChildrenAssign> {
  late Future<(List<Map<String, dynamic>>, List<Map<String, dynamic>>)> _data = _fetch();

  Future<(List<Map<String, dynamic>>, List<Map<String, dynamic>>)> _fetch() async {
    final api = SessionScope.of(context).api;
    final children = _l(await api.get('/api/admin/platform/children'));
    final accounts = _l(await api.get('/api/admin/platform/accounts'));
    return (children, accounts);
  }

  Future<void> _reload() async {
    setState(() => _data = _fetch());
    await _data;
  }

  Future<String?> _pick(String title, List<Map<String, dynamic>> options) => showDialog<String>(
        context: context,
        builder: (_) => SimpleDialog(
          title: Text(title),
          children: [for (final o in options) SimpleDialogOption(onPressed: () => Navigator.pop(context, _str(o['id'])), child: Text(_str(o['username'])))],
        ),
      );

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return FutureBuilder<(List<Map<String, dynamic>>, List<Map<String, dynamic>>)>(
      future: _data,
      builder: (context, snap) {
        if (snap.hasError) return StateView.fromError(context, snap.error, onRetry: _reload);
        if (!snap.hasData) return const SkeletonList();
        final (children, accounts) = snap.data!;
        bool has(Map<String, dynamic> a, String role) => (a['roles'] as List? ?? const []).contains(role) && a['approval_status'] == 'active';
        final teachers = accounts.where((a) => has(a, 'teacher')).toList();
        final parents = accounts.where((a) => has(a, 'parent')).toList();
        return RefreshIndicator(
          onRefresh: _reload,
          child: ListView(padding: const EdgeInsets.all(12), children: [
            if (children.isEmpty) _empty(_t(context, 'لا توجد ملفات أطفال بعد.', 'Noch keine Kinder.', 'No children yet.')),
            for (final c in children)
              () {
                final linkedTeachers = _l(c['teachers']);
                final linkedParents = _l(c['parent_accounts']);
                final freeTeachers = teachers.where((t) => !linkedTeachers.any((x) => x['id'] == t['id'])).toList();
                final freeParents = parents.where((p) => !linkedParents.any((x) => x['id'] == p['id'])).toList();
                return _Box(
                  title: _str(c['display_name']),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(_t(context, 'ولي الأمر', 'Eltern', 'Parents'), style: const TextStyle(color: _muted, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 6),
                    Wrap(spacing: 6, runSpacing: 6, children: [
                      if (linkedParents.isEmpty) Pill(_t(context, 'لم يكتمل تسجيل ولي الأمر بعد', 'Noch keine Eltern verknüpft', 'No parent linked yet')),
                      for (final p in linkedParents)
                        InputChip(
                          label: Text(_str(p['username'])),
                          onDeleted: () async {
                            if (!await confirmDelete(context) || !context.mounted) return;
                            if (await _run(context, () => api.delete('/api/admin/platform/children/${c['id']}/parents/${p['id']}'))) await _reload();
                          },
                        ),
                      if (freeParents.isNotEmpty)
                        ActionChip(
                          avatar: const Icon(Icons.add, size: 18),
                          label: Text(_t(context, 'ربط ولي أمر', 'Eltern verknüpfen', 'Link a parent')),
                          onPressed: () async {
                            final id = await _pick(_t(context, 'اختر ولي أمر', 'Eltern wählen', 'Choose a parent'), freeParents);
                            if (id == null || !context.mounted) return;
                            if (await _run(context, () => api.post('/api/admin/platform/children/${c['id']}/parents', {'parent_id': id}), done: _t(context, 'تم الربط.', 'Verknüpft.', 'Linked.'))) await _reload();
                          },
                        ),
                    ]),
                    const SizedBox(height: 12),
                    Text(_t(context, 'المعلمات', 'Lehrerinnen', 'Teachers'), style: const TextStyle(color: _muted, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 6),
                    Wrap(spacing: 6, runSpacing: 6, children: [
                      if (linkedTeachers.isEmpty) Pill(_t(context, 'لا توجد معلمة معيّنة', 'Keine Lehrerin zugeordnet', 'No teacher assigned')),
                      for (final t in linkedTeachers)
                        InputChip(
                          label: Text(_str(t['username'])),
                          onDeleted: () async {
                            if (await _run(context, () => api.delete('/api/admin/platform/children/${c['id']}/teachers/${t['id']}'))) await _reload();
                          },
                        ),
                      if (freeTeachers.isNotEmpty)
                        ActionChip(
                          avatar: const Icon(Icons.add, size: 18),
                          label: Text(_t(context, 'تعيين معلمة', 'Lehrerin zuordnen', 'Assign a teacher')),
                          onPressed: () async {
                            final id = await _pick(_t(context, 'اختر معلمة', 'Lehrerin wählen', 'Choose a teacher'), freeTeachers);
                            if (id == null || !context.mounted) return;
                            if (await _run(context, () => api.post('/api/admin/platform/children/${c['id']}/teachers', {'teacher_id': id}), done: _t(context, 'تم التعيين.', 'Zugeordnet.', 'Assigned.'))) await _reload();
                          },
                        ),
                    ]),
                  ]),
                );
              }(),
          ]),
        );
      },
    );
  }
}

// =================================================================================================================================
// website content: images, videos, news, settings
// =================================================================================================================================
String _asset(Object? name) => '${AppConfig.apiBase}/api/assets/${_str(name)}';

class AdminWebsitePage extends StatefulWidget {
  const AdminWebsitePage({super.key});
  @override
  State<AdminWebsitePage> createState() => _AdminWebsitePageState();
}

class _AdminWebsitePageState extends State<AdminWebsitePage> {
  int _round = 0;
  void _again() => setState(() => _round++);

  @override
  Widget build(BuildContext context) => _load(context, '/api/admin/content', key: ValueKey(_round), (context, data, reload) {
        final d = _m(data);
        Future<void> refresh() async {
          _again();
        }

        return _Tabbed(
          tabs: [
            _t(context, 'الصور', 'Bilder', 'Images'),
            _t(context, 'الفيديو', 'Videos', 'Videos'),
            _t(context, 'الأخبار', 'Nachrichten', 'News'),
            _t(context, 'الإعدادات', 'Einstellungen', 'Settings'),
          ],
          pages: [
            _MediaTab(items: _l(d['gallery']).where((g) => g['kind'] != 'video').toList(), video: false, onChanged: refresh),
            _MediaTab(items: _l(d['gallery']).where((g) => g['kind'] == 'video').toList(), video: true, onChanged: refresh),
            _NewsTab(items: _l(d['news']), onChanged: refresh),
            _SettingsTab(settings: _m(d['settings']), onChanged: refresh),
          ],
        );
      });
}

int _byNew(Map<String, dynamic> a, Map<String, dynamic> b) => ((b['ts'] as num?) ?? 0).compareTo((a['ts'] as num?) ?? 0);

class _MediaTab extends StatefulWidget {
  const _MediaTab({required this.items, required this.video, required this.onChanged});
  final List<Map<String, dynamic>> items;
  final bool video;
  final Future<void> Function() onChanged;
  @override
  State<_MediaTab> createState() => _MediaTabState();
}

class _MediaTabState extends State<_MediaTab> {
  String? _progress;

  Future<void> _upload() async {
    final api = SessionScope.of(context).api;
    final allowed = widget.video ? const ['mp4', 'webm'] : const ['jpg', 'jpeg', 'png', 'webp', 'gif'];
    final picked = (await FilePicker.pickFiles()).where((f) => f.path != null && allowed.contains(fileExt(f.name))).toList();
    if (!mounted) return;
    if (picked.isEmpty) {
      toast(context, widget.video ? _t(context, 'اختر ملف فيديو MP4 أو WebM.', 'Ein MP4- oder WebM-Video wählen.', 'Choose an MP4 or WebM video.') : _t(context, 'اختر صورة (JPG أو PNG أو WebP أو GIF).', 'Ein Bild wählen (JPG, PNG, WebP, GIF).', 'Choose an image (JPG, PNG, WebP, GIF).'));
      return;
    }
    final caption = await askText(context, _t(context, 'تعليق يظهر تحت العنصر (اختياري)', 'Bildunterschrift (optional)', 'Caption (optional)'), maxLength: 120, confirm: 'save');
    if (caption == null || !mounted) return;
    var done = 0;
    try {
      for (final f in widget.video ? picked.take(1) : picked) {
        setState(() => _progress = '${done + 1} / ${picked.length}');
        await api.multipart('/api/admin/gallery', {'kind': widget.video ? 'video' : 'image', 'caption': caption}, [UploadFile(f.path!, f.name)], fileField: 'file');
        done++;
      }
      if (mounted) toast(context, _t(context, 'تم الرفع وظهر في الموقع.', 'Hochgeladen und auf der Webseite.', 'Uploaded and published.'));
    } on ApiException catch (e) {
      if (mounted) toast(context, e.detail.isNotEmpty ? e.detail : problemText(context, e));
    } finally {
      if (mounted) setState(() => _progress = null);
    }
    await widget.onChanged();
  }

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    final items = [...widget.items]..sort(_byNew);
    return ListView(padding: const EdgeInsets.all(12), children: [
      Row(children: [
        FilledButton.icon(
          style: FilledButton.styleFrom(minimumSize: const Size(170, 46)),
          icon: const Icon(Icons.upload_rounded),
          label: Text(widget.video ? _t(context, 'رفع فيديو', 'Video hochladen', 'Upload a video') : _t(context, 'رفع صور', 'Bilder hochladen', 'Upload images')),
          onPressed: _progress == null ? _upload : null,
        ),
        if (_progress != null) ...[const SizedBox(width: 12), const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)), const SizedBox(width: 8), Text(_progress!)],
      ]),
      if (widget.video)
        Padding(padding: const EdgeInsets.only(top: 6), child: Text(_t(context, 'MP4 أو WebM حتى 25 ميغابايت. فيديوهات MOV لا تعمل.', 'MP4 oder WebM bis 25 MB. MOV-Videos gehen nicht.', 'MP4 or WebM up to 25 MB. MOV does not work.'), style: const TextStyle(color: _muted, fontSize: 12.5))),
      const SizedBox(height: 12),
      if (items.isEmpty) _empty(widget.video ? _t(context, 'لا توجد فيديوهات بعد.', 'Noch keine Videos.', 'No videos yet.') : _t(context, 'لا توجد صور بعد.', 'Noch keine Bilder.', 'No images yet.')),
      LayoutBuilder(builder: (context, c) {
        final cols = (c.maxWidth / 220).floor().clamp(1, 5);
        final w = (c.maxWidth - (cols - 1) * 10) / cols;
        return Wrap(spacing: 10, runSpacing: 10, children: [
          for (final g in items)
            SizedBox(
              width: w,
              child: Card(
                margin: EdgeInsets.zero,
                clipBehavior: Clip.antiAlias,
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  AspectRatio(
                    aspectRatio: 4 / 3,
                    child: widget.video
                        ? Container(color: const Color(0xFF16406F), child: const Icon(Icons.play_circle_outline_rounded, color: Colors.white, size: 54))
                        : Image.network(_asset(g['asset']), fit: BoxFit.cover, errorBuilder: (_, _, _) => const ColoredBox(color: Color(0xFFEEF2F6), child: Icon(Icons.broken_image_outlined))),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(10, 8, 4, 8),
                    child: Row(children: [
                      Expanded(child: Text(_str(g['caption']).isEmpty ? '—' : _str(g['caption']), maxLines: 2, overflow: TextOverflow.ellipsis)),
                      IconButton(
                        tooltip: _t(context, 'تعديل التعليق', 'Unterschrift ändern', 'Edit caption'),
                        icon: const Icon(Icons.edit_outlined, size: 20),
                        onPressed: () async {
                          final text = await askText(context, _t(context, 'التعليق', 'Unterschrift', 'Caption'), initial: _str(g['caption']), maxLength: 120);
                          if (text == null || !context.mounted) return;
                          if (await _run(context, () => api.patch('/api/admin/gallery/${g['id']}', {'caption': text}))) await widget.onChanged();
                        },
                      ),
                      IconButton(
                        tooltip: _t(context, 'حذف', 'Löschen', 'Delete'),
                        icon: const Icon(Icons.delete_outline, size: 20, color: _bad),
                        onPressed: () async {
                          if (!await confirmDelete(context) || !context.mounted) return;
                          if (await _run(context, () => api.delete('/api/admin/gallery/${g['id']}'))) await widget.onChanged();
                        },
                      ),
                    ]),
                  ),
                ]),
              ),
            ),
        ]);
      }),
    ]);
  }
}

class _NewsTab extends StatelessWidget {
  const _NewsTab({required this.items, required this.onChanged});
  final List<Map<String, dynamic>> items;
  final Future<void> Function() onChanged;
  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    final list = [...items]..sort(_byNew);
    return ListView(padding: const EdgeInsets.all(12), children: [
      Align(
        alignment: AlignmentDirectional.centerStart,
        child: FilledButton.icon(
          style: FilledButton.styleFrom(minimumSize: const Size(160, 46)),
          icon: const Icon(Icons.add_rounded),
          label: Text(_t(context, 'خبر جديد', 'Neue Nachricht', 'New post')),
          onPressed: () async {
            if (await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const _NewsEditor())) == true) await onChanged();
          },
        ),
      ),
      const SizedBox(height: 12),
      if (list.isEmpty) _empty(_t(context, 'لا توجد أخبار مضافة.', 'Keine Nachrichten.', 'No news yet.')),
      for (final n in list)
        Card(
          child: ListTile(
            leading: _str(n['asset']).isEmpty
                ? const CircleAvatar(backgroundColor: Color(0xFFEAF1F8), child: Icon(Icons.campaign_outlined, color: Color(0xFF16406F)))
                : ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.network(_asset(n['asset']), width: 56, height: 56, fit: BoxFit.cover, errorBuilder: (_, _, _) => const Icon(Icons.image_outlined))),
            title: Text(_str(n['title']), style: const TextStyle(fontWeight: FontWeight.w700)),
            subtitle: Text(_str(n['tag'])),
            onTap: () async {
              if (await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => _NewsEditor(item: n))) == true) await onChanged();
            },
            trailing: IconButton(
              tooltip: _t(context, 'حذف', 'Löschen', 'Delete'),
              icon: const Icon(Icons.delete_outline, color: _bad),
              onPressed: () async {
                if (!await confirmDelete(context) || !context.mounted) return;
                if (await _run(context, () => api.delete('/api/admin/news/${n['id']}'))) await onChanged();
              },
            ),
          ),
        ),
    ]);
  }
}

class _NewsEditor extends StatefulWidget {
  const _NewsEditor({this.item});
  final Map<String, dynamic>? item;
  @override
  State<_NewsEditor> createState() => _NewsEditorState();
}

class _NewsEditorState extends State<_NewsEditor> {
  late final _tag = TextEditingController(text: widget.item == null ? 'خبر' : _str(widget.item!['tag']));
  late final _title = TextEditingController(text: _str(widget.item?['title']));
  late final _text = TextEditingController(text: _str(widget.item?['text']));
  UploadFile? _image;
  bool _removeImage = false;
  bool _busy = false;

  Future<void> _save() async {
    if (_title.text.trim().isEmpty || _text.text.trim().isEmpty) {
      toast(context, _t(context, 'اكتب العنوان والنص.', 'Titel und Text eintragen.', 'Enter the title and the text.'));
      return;
    }
    final api = SessionScope.of(context).api;
    setState(() => _busy = true);
    final item = widget.item;
    final ok = await _run(
      context,
      () => api.multipart(
        item == null ? '/api/admin/news' : '/api/admin/news/${item['id']}',
        {'tag': _tag.text.trim(), 'title': _title.text.trim(), 'text': _text.text.trim(), if (_removeImage) 'remove_image': '1'},
        [?_image],
        fileField: 'file',
      ),
      done: _t(context, 'تم نشر الخبر في الموقع.', 'Nachricht veröffentlicht.', 'News published.'),
    );
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    final hasImage = _str(widget.item?['asset']).isNotEmpty;
    return Scaffold(
      appBar: AppBar(title: Text(widget.item == null ? _t(context, 'خبر جديد', 'Neue Nachricht', 'New post') : _t(context, 'تعديل الخبر', 'Nachricht bearbeiten', 'Edit post'))),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(padding: const EdgeInsets.all(16), children: [
            if (_busy) const LinearProgressIndicator(),
            TextField(controller: _tag, maxLength: 30, decoration: InputDecoration(labelText: _t(context, 'التصنيف (كلمة قصيرة)', 'Kategorie (kurzes Wort)', 'Tag (short word)'))),
            TextField(controller: _title, maxLength: 120, decoration: InputDecoration(labelText: _t(context, 'العنوان', 'Titel', 'Title'))),
            TextField(controller: _text, maxLength: 1500, maxLines: 8, minLines: 4, decoration: InputDecoration(labelText: _t(context, 'النص', 'Text', 'Text'))),
            const SizedBox(height: 8),
            Wrap(spacing: 10, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
              OutlinedButton.icon(
                icon: const Icon(Icons.image_outlined),
                label: Text(_image == null ? _t(context, 'صورة (اختيارية)', 'Bild (optional)', 'Image (optional)') : _image!.name),
                onPressed: () async {
                  final f = await FilePicker.pickFile();
                  if (f == null || f.path == null) return;
                  if (!const ['jpg', 'jpeg', 'png', 'webp', 'gif'].contains(fileExt(f.name))) {
                    if (context.mounted) toast(context, _t(context, 'اختر صورة (JPG أو PNG أو WebP أو GIF).', 'Ein Bild wählen (JPG, PNG, WebP, GIF).', 'Choose an image (JPG, PNG, WebP, GIF).'));
                    return;
                  }
                  setState(() => _image = UploadFile(f.path!, f.name));
                },
              ),
              if (hasImage)
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Checkbox(value: _removeImage, onChanged: (v) => setState(() => _removeImage = v ?? false)),
                  Text(_t(context, 'حذف الصورة الحالية', 'Aktuelles Bild entfernen', 'Remove the current image')),
                ]),
            ]),
          ]),
        ),
      ),
      bottomNavigationBar: BottomActionBar(children: [
        Expanded(child: FilledButton(onPressed: _busy ? null : _save, child: Text(widget.item == null ? _t(context, 'نشر الخبر', 'Veröffentlichen', 'Publish') : _t(context, 'حفظ التعديل', 'Speichern', 'Save')))),
      ]),
    );
  }
}

class _SettingsTab extends StatefulWidget {
  const _SettingsTab({required this.settings, required this.onChanged});
  final Map<String, dynamic> settings;
  final Future<void> Function() onChanged;
  @override
  State<_SettingsTab> createState() => _SettingsTabState();
}

class _SettingsTabState extends State<_SettingsTab> {
  static const _keys = ['announce', 'phone', 'whatsapp', 'email', 'hours', 'facebook', 'instagram'];
  late final Map<String, TextEditingController> _c = {for (final k in _keys) k: TextEditingController(text: _str(widget.settings[k]))};
  late bool _hideNews = widget.settings['hideDefaultNews'] == true;
  late bool _hideGallery = widget.settings['hideDefaultGallery'] == true;
  bool _busy = false;

  String? _problem() {
    final wa = _c['whatsapp']!.text.replaceAll(RegExp(r'\D'), '');
    if (wa.isNotEmpty && (wa.length < 8 || wa.length > 15)) return _t(context, 'رقم الواتساب غير صالح (من 8 إلى 15 رقماً).', 'WhatsApp-Nummer ungültig (8 bis 15 Ziffern).', 'WhatsApp number not valid (8 to 15 digits).');
    final mail = _c['email']!.text.trim();
    if (mail.isNotEmpty && !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(mail)) return _t(context, 'عنوان البريد غير صالح.', 'E-Mail-Adresse ungültig.', 'Email address not valid.');
    for (final k in ['facebook', 'instagram']) {
      final v = _c[k]!.text.trim();
      if (v.isNotEmpty && !RegExp(r'^https://\S+\.\S+', caseSensitive: false).hasMatch(v)) return _t(context, 'يجب أن يكون الرابط كاملاً ويبدأ بـ https', 'Der Link muss vollständig sein und mit https beginnen.', 'The link must be complete and start with https.');
    }
    return null;
  }

  Future<void> _save() async {
    final problem = _problem();
    if (problem != null) {
      toast(context, problem);
      return;
    }
    final api = SessionScope.of(context).api;
    final body = <String, dynamic>{for (final k in _keys) k: _c[k]!.text.trim(), 'hideDefaultNews': _hideNews, 'hideDefaultGallery': _hideGallery};
    body['whatsapp'] = (body['whatsapp'] as String).replaceAll(RegExp(r'\D'), '');
    setState(() => _busy = true);
    await _run(context, () => api.put('/api/admin/settings', body), done: _t(context, 'تم حفظ الإعدادات وطُبّقت على الموقع.', 'Einstellungen gespeichert und auf der Webseite.', 'Settings saved and live.'));
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final labels = {
      'announce': _t(context, 'نص شريط الإعلان (فارغ = مخفي)', 'Text des Hinweisbands (leer = aus)', 'Banner text (empty = hidden)'),
      'phone': _t(context, 'رقم الهاتف الظاهر', 'Angezeigte Telefonnummer', 'Phone number shown'),
      'whatsapp': _t(context, 'رقم الواتساب (أرقام فقط، دولي)', 'WhatsApp-Nummer (nur Ziffern, international)', 'WhatsApp number (digits, international)'),
      'email': _t(context, 'البريد الإلكتروني', 'E-Mail', 'Email'),
      'hours': _t(context, 'أوقات الدوام', 'Öffnungszeiten', 'Opening hours'),
      'facebook': _t(context, 'رابط فيسبوك', 'Facebook-Link', 'Facebook link'),
      'instagram': _t(context, 'رابط إنستغرام', 'Instagram-Link', 'Instagram link'),
    };
    const ltr = {'phone', 'whatsapp', 'email', 'facebook', 'instagram'};
    return ListView(padding: const EdgeInsets.all(12), children: [
      if (_busy) const LinearProgressIndicator(),
      _Box(
        title: _t(context, 'إعدادات الموقع', 'Einstellungen der Webseite', 'Website settings'),
        hint: _t(context, 'ما تغيّره هنا يظهر مباشرة في الموقع بعد الحفظ.', 'Was du hier änderst, steht nach dem Speichern sofort auf der Webseite.', 'Changes show on the website right after saving.'),
        child: Column(children: [
          for (final k in _keys)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: TextField(
                controller: _c[k],
                maxLength: k == 'announce' || k == 'hours' ? 200 : 300,
                textDirection: ltr.contains(k) ? TextDirection.ltr : null,
                decoration: InputDecoration(labelText: labels[k]),
              ),
            ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: _hideNews,
            onChanged: (v) => setState(() => _hideNews = v),
            title: Text(_t(context, 'إخفاء الخبر الافتتاحي الأصلي', 'Ursprüngliche Start-Nachricht ausblenden', 'Hide the original first news')),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: _hideGallery,
            onChanged: (v) => setState(() => _hideGallery = v),
            title: Text(_t(context, 'إخفاء الصور الأصلية في المعرض', 'Ursprüngliche Galeriebilder ausblenden', 'Hide the original gallery images')),
          ),
          const SizedBox(height: 10),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(180, 46)), onPressed: _busy ? null : _save, child: Text(_t(context, 'حفظ الإعدادات', 'Einstellungen speichern', 'Save settings'))),
          ),
        ]),
      ),
    ]);
  }
}

// =================================================================================================================================
// activity log
// =================================================================================================================================
const _domains = {
  'all': ['كل المجالات', 'Alle Bereiche', 'All areas'],
  'finance': ['المال', 'Geld', 'Money'],
  'security': ['الأمان', 'Sicherheit', 'Security'],
  'account': ['الحسابات والأشخاص', 'Konten und Personen', 'Accounts and people'],
  'report': ['التقارير', 'Berichte', 'Reports'],
  'content': ['المحتوى', 'Inhalte', 'Content'],
  'system': ['النظام', 'System', 'System'],
};

class AdminLogPage extends StatefulWidget {
  const AdminLogPage({super.key});
  @override
  State<AdminLogPage> createState() => _AdminLogPageState();
}

class _AdminLogPageState extends State<AdminLogPage> {
  String _domain = 'all';
  String _actor = '';
  String _q = '';
  List<String> _actors = [];
  final _search = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadActors());
  }

  Future<void> _loadActors() async {
    try {
      final names = await SessionScope.of(context).api.get('/api/admin/activity/actors', query: {'domain': _domain}) as List;
      if (mounted) setState(() => _actors = [for (final n in names) '$n']);
    } catch (_) {}
  }

  Map<String, String> get _query => {'limit': '200', 'domain': _domain, if (_actor.isNotEmpty) 'actor_name': _actor, if (_q.isNotEmpty) 'q': _q};

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    String dn(String k) {
      final x = _domains[k];
      return x == null ? k : _t(context, x[0], x[1], x[2]);
    }

    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
        child: Wrap(spacing: 10, runSpacing: 10, crossAxisAlignment: WrapCrossAlignment.center, children: [
          SizedBox(
            width: 200,
            child: DropdownButtonFormField<String>(
              initialValue: _domain,
              isExpanded: true,
              decoration: InputDecoration(labelText: _t(context, 'المجال', 'Bereich', 'Area')),
              items: [for (final k in _domains.keys) DropdownMenuItem(value: k, child: Text(dn(k)))],
              onChanged: (v) {
                setState(() {
                  _domain = v ?? 'all';
                  _actor = '';
                });
                _loadActors();
              },
            ),
          ),
          SizedBox(
            width: 200,
            child: DropdownButtonFormField<String>(
              key: ValueKey('actor$_domain${_actors.length}'),
              initialValue: _actor,
              isExpanded: true,
              decoration: InputDecoration(labelText: _t(context, 'المستخدم', 'Benutzer', 'User')),
              items: [
                DropdownMenuItem(value: '', child: Text(_t(context, 'كل المستخدمين', 'Alle', 'Everybody'))),
                for (final n in _actors) DropdownMenuItem(value: n, child: Text(n)),
              ],
              onChanged: (v) => setState(() => _actor = v ?? ''),
            ),
          ),
          SizedBox(
            width: 220,
            child: SuggestSearchField(
              controller: _search,
              label: _t(context, 'بحث', 'Suche', 'Search'),
              suggestions: _actors,
              onSearch: (v) => setState(() => _q = v),
            ),
          ),
          OutlinedButton.icon(
            icon: const Icon(Icons.table_view_outlined),
            label: Text(_t(context, 'تصدير Excel', 'Excel-Export', 'Export Excel')),
            onPressed: () => openPrivateFile(context, api, '/api/admin/activity/export.xlsx', 'system-log.xlsx', query: _query..remove('limit')),
          ),
        ]),
      ),
      Expanded(
        child: _load(context, '/api/admin/activity', key: ValueKey('$_domain|$_actor|$_q'), query: _query, (context, data, reload) {
          final rows = _l(data);
          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: rows.isEmpty ? 1 : rows.length,
            separatorBuilder: (_, _) => const SizedBox(height: 6),
            itemBuilder: (context, i) {
              if (rows.isEmpty) return _empty(_t(context, 'لا توجد إجراءات', 'Keine Einträge', 'No activity'));
              final r = rows[i];
              return Card(
                margin: EdgeInsets.zero,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Expanded(child: Text(_str(r['actor']), style: const TextStyle(fontWeight: FontWeight.w800))),
                      Text(_when(r['at']), textDirection: TextDirection.ltr, style: const TextStyle(fontSize: 12, color: _muted)),
                    ]),
                    const SizedBox(height: 4),
                    Wrap(spacing: 6, runSpacing: 4, children: [Pill(dn(_str(r['domain']))), Pill(_str(r['action']))]),
                    if (_str(r['reason']).isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text(_str(r['reason']))),
                    if (_str(r['details']).isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text(_str(r['details']), style: const TextStyle(fontSize: 12.5, color: _muted))),
                  ]),
                ),
              );
            },
          );
        }),
      ),
    ]);
  }
}

// =================================================================================================================================
// visitors
// =================================================================================================================================
class AdminVisitorsPage extends StatefulWidget {
  const AdminVisitorsPage({super.key});
  @override
  State<AdminVisitorsPage> createState() => _AdminVisitorsPageState();
}

class _AdminVisitorsPageState extends State<AdminVisitorsPage> {
  String _days = '30';

  @override
  Widget build(BuildContext context) {
    final periods = {
      '7': _t(context, 'آخر 7 أيام', 'Letzte 7 Tage', 'Last 7 days'),
      '30': _t(context, 'آخر 30 يوماً', 'Letzte 30 Tage', 'Last 30 days'),
      '90': _t(context, 'آخر 90 يوماً', 'Letzte 90 Tage', 'Last 90 days'),
      '365': _t(context, 'آخر سنة', 'Letztes Jahr', 'Last year'),
    };
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
        child: Align(
          alignment: AlignmentDirectional.centerStart,
          child: SizedBox(
            width: 220,
            child: DropdownButtonFormField<String>(
              initialValue: _days,
              decoration: InputDecoration(labelText: _t(context, 'الفترة', 'Zeitraum', 'Period')),
              items: [for (final e in periods.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
              onChanged: (v) => setState(() => _days = v ?? _days),
            ),
          ),
        ),
      ),
      Expanded(
        child: _load(context, '/api/admin/platform/visits', key: ValueKey(_days), query: {'days': _days}, (context, data, reload) {
          final d = _m(data);
          final series = _l(d['series']);
          final top = series.fold<num>(1, (m, s) => ((s['views'] as num?) ?? 0) > m ? (s['views'] as num) : m);
          final devices = _m(d['devices']);
          Widget table(List<Map<String, dynamic>> rows, String Function(Map<String, dynamic>) name, String empty) => Column(children: [
                if (rows.isEmpty) _empty(empty),
                for (final r in rows) _row(name(r), _str(r['views']), ltr: true),
              ]);
          return ListView(padding: const EdgeInsets.all(12), children: [
            _kpis([
              _Kpi(_t(context, 'زيارات اليوم', 'Aufrufe heute', 'Views today'), _str(_m(d['today'])['views']), tone: _good),
              _Kpi(_t(context, 'زوّار اليوم', 'Besucher heute', 'Visitors today'), _str(_m(d['today'])['visitors'])),
              _Kpi(_t(context, 'زيارات 7 أيام', 'Aufrufe 7 Tage', 'Views 7 days'), _str(_m(d['week'])['views'])),
              _Kpi(_t(context, 'زوّار 7 أيام', 'Besucher 7 Tage', 'Visitors 7 days'), _str(_m(d['week'])['visitors'])),
              _Kpi(_t(context, 'زيارات الفترة', 'Aufrufe Zeitraum', 'Views in period'), _str(_m(d['period'])['views'])),
              _Kpi(_t(context, 'زوّار الفترة', 'Besucher Zeitraum', 'Visitors in period'), _str(_m(d['period'])['visitors'])),
            ]),
            const SizedBox(height: 12),
            if (series.isNotEmpty)
              _Box(
                title: _t(context, 'الزيارات اليومية', 'Aufrufe pro Tag', 'Views per day'),
                hint: _t(context, 'الأزرق: زيارات · الأخضر: زوّار', 'Blau: Aufrufe · Grün: Besucher', 'Blue: views · green: visitors'),
                child: SizedBox(
                  height: 140,
                  child: Directionality(
                    textDirection: TextDirection.ltr,
                    child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                      for (final s in series)
                        Expanded(
                          child: Tooltip(
                            message: '${_str(s['day'])}: ${_str(s['views'])} / ${_str(s['visitors'])}',
                            child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                              Expanded(child: Container(height: 2 + 130 * (((s['views'] as num?) ?? 0) / top), color: const Color(0xFF2D5FC4))),
                              Expanded(child: Container(height: 2 + 130 * (((s['visitors'] as num?) ?? 0) / top), color: const Color(0xFF7DC243))),
                            ]),
                          ),
                        ),
                    ]),
                  ),
                ),
              ),
            _Box(title: _t(context, 'أكثر الصفحات', 'Meistbesuchte Seiten', 'Top pages'), child: table(_l(d['pages']), (r) => _str(r['path']), _t(context, 'لا توجد زيارات بعد.', 'Noch keine Aufrufe.', 'No views yet.'))),
            _Box(title: _t(context, 'من أين جاؤوا', 'Woher sie kamen', 'Where they came from'), child: table(_l(d['sources']), (r) => _str(r['host']).isEmpty ? _t(context, 'مباشرة', 'direkt', 'direct') : _str(r['host']), '—')),
            _Box(
              title: _t(context, 'الأجهزة', 'Geräte', 'Devices'),
              child: Column(children: [
                _row(_t(context, 'هاتف', 'Telefon', 'Phone'), _str(devices['mobile'] ?? 0)),
                _row(_t(context, 'كمبيوتر', 'Computer', 'Computer'), _str(devices['desktop'] ?? 0)),
                _row(_t(context, 'لوحي', 'Tablet', 'Tablet'), _str(devices['tablet'] ?? 0)),
              ]),
            ),
            _Box(title: _t(context, 'اللغات', 'Sprachen', 'Languages'), child: table(_l(d['languages']), (r) => _str(r['lang']).isEmpty ? '—' : _str(r['lang']), '—')),
            _Box(
              title: _t(context, 'من دخل إلى المنصة', 'Wer sich angemeldet hat', 'Who signed in'),
              hint: '${_t(context, 'دخلوا خلال آخر 30 دقيقة', 'In den letzten 30 Minuten angemeldet', 'Signed in in the last 30 minutes')}: ${_str(d['signed_in_recently'])}',
              child: Column(children: [
                if (_l(d['sign_ins']).isEmpty) _empty(_t(context, 'لم يسجّل أحد الدخول في هذه الفترة.', 'Niemand angemeldet.', 'Nobody signed in.')),
                for (final p in _l(d['sign_ins']))
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(_str(p['username']), style: const TextStyle(fontWeight: FontWeight.w700)),
                    subtitle: Text('${[for (final r in (p['roles'] as List? ?? const [])) _role(context, '$r')].join(' + ')} · ${_t(context, 'مرات', 'Mal', 'times')}: ${_str(p['times'])}'),
                    trailing: Text(_when(p['last_at']), textDirection: TextDirection.ltr, style: const TextStyle(fontSize: 12, color: _muted)),
                  ),
              ]),
            ),
          ]);
        }),
      ),
    ]);
  }
}

// =================================================================================================================================
// teachers' private files
// =================================================================================================================================
class AdminFilesPage extends StatelessWidget {
  const AdminFilesPage({super.key});
  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return _load(context, '/api/admin/platform/files', (context, data, reload) {
      final d = _m(data);
      final limit = (d['limit_bytes'] as num? ?? 0).toInt();
      final items = _l(d['items']);
      return ListView(padding: const EdgeInsets.all(12), children: [
        Text(_t(context, 'الملفات الخاصة التي رفعتها المعلمات. لكل معلمة حدّ 250 ميغابايت.', 'Private Dateien der Lehrerinnen. Je Lehrerin bis 250 MB.', 'Private files of the teachers. Up to 250 MB each.'), style: const TextStyle(color: _muted)),
        const SizedBox(height: 10),
        if (_l(d['owners']).isNotEmpty)
          _kpis([
            for (final o in _l(d['owners'])) _Kpi('${_str(o['owner'])} · ${_str(o['files'])}', '${formatSize((o['bytes'] as num? ?? 0).toInt())} / ${formatSize(limit)}'),
          ]),
        const SizedBox(height: 10),
        if (items.isEmpty) _empty(_t(context, 'لا توجد ملفات مرفوعة بعد.', 'Noch keine Dateien.', 'No files yet.')),
        for (final f in items)
          Card(
            child: ListTile(
              leading: FileTypePlate(filename: _str(f['name'])),
              title: Text(_str(f['name']), maxLines: 1, overflow: TextOverflow.ellipsis),
              subtitle: Text('${_str(f['owner'])} · ${formatSize((f['size'] as num? ?? 0).toInt())} · ${_str(f['created_at']).length >= 10 ? _str(f['created_at']).substring(0, 10) : _str(f['created_at'])}'),
              onTap: () => openPrivateFile(context, api, '/api/admin/platform/files/${f['id']}/download', _str(f['name'])),
              trailing: IconButton(
                tooltip: _t(context, 'حذف', 'Löschen', 'Delete'),
                icon: const Icon(Icons.delete_outline, color: _bad),
                onPressed: () async {
                  if (!await confirmDelete(context) || !context.mounted) return;
                  if (await _run(context, () => api.delete('/api/admin/platform/files/${f['id']}'), done: _t(context, 'تم حذف الملف.', 'Datei gelöscht.', 'File deleted.'))) await reload();
                },
              ),
            ),
          ),
      ]);
    });
  }
}

// =================================================================================================================================
// security
// =================================================================================================================================
class AdminSecurityPage extends StatelessWidget {
  const AdminSecurityPage({super.key});
  @override
  Widget build(BuildContext context) => _load(context, '/api/admin/platform/security', (context, data, reload) {
        final d = _m(data);
        final failed = (d['failed_sign_ins_24h'] as num? ?? 0).toInt();
        const roleTitles = {
          'parent': ['أولياء الأمور', 'Eltern', 'Parents'],
          'teacher': ['المعلمات', 'Lehrerinnen', 'Teachers'],
          'manager': ['الإدارة', 'Leitung', 'Management'],
          'accountant': ['المحاسبون', 'Buchhaltung', 'Accountants'],
          'admin': ['المدراء', 'Admins', 'Admins'],
        };
        return ListView(padding: const EdgeInsets.all(12), children: [
          Text(
            _t(context, 'أرقام فقط. كثرة المحاولات الفاشلة في وقت قصير تعني أن أحداً يخمّن كلمات المرور؛ الموقع يحجب العنوان تلقائياً.', 'Nur Zahlen. Viele Fehlversuche in kurzer Zeit heißen: Jemand rät Passwörter; die Adresse wird automatisch gesperrt.', 'Numbers only. Many failed attempts in a short time mean someone is guessing passwords; the address is blocked automatically.'),
            style: const TextStyle(color: _muted),
          ),
          const SizedBox(height: 10),
          _kpis([
            _Kpi(_t(context, 'حسابات فعّالة', 'Aktive Konten', 'Active accounts'), _str(d['accounts_active']), tone: _good),
            _Kpi(_t(context, 'حسابات موقوفة', 'Gesperrte Konten', 'Disabled accounts'), _str(d['accounts_blocked'])),
            _Kpi(_t(context, 'بانتظار الموافقة', 'Warten auf Freigabe', 'Waiting for approval'), _str(d['accounts_pending'])),
            _Kpi(_t(context, 'جلسات مفتوحة الآن', 'Offene Sitzungen', 'Open sessions'), _str(d['sessions_open'])),
            _Kpi(_t(context, 'تسجيلات دخول (24 ساعة)', 'Anmeldungen (24 h)', 'Sign-ins (24 h)'), _str(d['sign_ins_24h'])),
            _Kpi(_t(context, 'محاولات فاشلة (24 ساعة)', 'Fehlversuche (24 h)', 'Failed attempts (24 h)'), '$failed', tone: failed > 10 ? _bad : null),
          ]),
          const SizedBox(height: 12),
          _Box(
            title: _t(context, 'الحسابات الفعّالة حسب النوع', 'Aktive Konten nach Art', 'Active accounts by kind'),
            child: Column(children: [
              for (final e in _m(d['by_role']).entries)
                _row(() {
                  final r = roleTitles[e.key];
                  return r == null ? e.key : _t(context, r[0], r[1], r[2]);
                }(), _str(e.value)),
            ]),
          ),
          _Box(
            title: _t(context, 'التخزين', 'Speicher', 'Storage'),
            child: Column(children: [
              _row(_t(context, 'ملفات خاصة', 'Private Dateien', 'Private files'), _str(d['files'])),
              _row(_t(context, 'المساحة المستعملة', 'Belegter Platz', 'Space used'), formatSize((d['stored_bytes'] as num? ?? 0).toInt()), ltr: true),
            ]),
          ),
        ]);
      });
}

// =================================================================================================================================
// children records, staff and groups (the management portal of the website)
// =================================================================================================================================
class AdminPeoplePage extends StatelessWidget {
  const AdminPeoplePage({super.key});
  @override
  Widget build(BuildContext context) => _Tabbed(
        tabs: [_t(context, 'ملفات الأطفال', 'Kinderakten', 'Children records'), _t(context, 'الموظفون', 'Personal', 'Staff'), _t(context, 'المجموعات', 'Gruppen', 'Groups')],
        pages: const [_KidsTab(), _StaffTab(), _GroupsTab()],
      );
}

class _KidsTab extends StatefulWidget {
  const _KidsTab();
  @override
  State<_KidsTab> createState() => _KidsTabState();
}

class _KidsTabState extends State<_KidsTab> {
  int _round = 0;
  String _q = '';

  Future<void> _open(Map<String, dynamic>? child, List<Map<String, dynamic>> parents) async {
    final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => _KidEditor(child: child, parents: parents)));
    if (saved == true) setState(() => _round++);
  }

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return Loader<(List<Map<String, dynamic>>, List<Map<String, dynamic>>)>(
      key: ValueKey(_round),
      load: () async => Cached((_l(await api.get('/api/admin/people/children')), _l(await api.get('/api/admin/people/parent-accounts')))),
      builder: (context, data, reload) {
        final (kids, parents) = data;
        final word = _q.trim().toLowerCase();
        final shown = word.isEmpty
            ? kids
            : kids.where((k) => '${k['name']} ${[for (final g in _l(k['guardians'])) '${g['name']} ${g['phone']}'].join(' ')}'.toLowerCase().contains(word)).toList();
        return ListView(padding: const EdgeInsets.all(12), children: [
          Row(children: [
            Expanded(
              child: SuggestSearchField(
                hint: _t(context, 'بحث عن طفل أو ولي أمر', 'Kind oder Eltern suchen', 'Search a child or parent'),
                searchOnType: true,
                suggestions: [
                  for (final k in kids) ...[k['name'], k['class_name'], for (final g in _l(k['guardians'])) ...[g['name'], g['phone']]].whereType<String>(),
                ],
                onSearch: (v) => setState(() => _q = v),
              ),
            ),
            const SizedBox(width: 10),
            FilledButton.icon(
              style: FilledButton.styleFrom(minimumSize: const Size(0, 48)),
              icon: const Icon(Icons.add_rounded),
              label: Text(_t(context, 'طفل جديد', 'Neues Kind', 'New child')),
              onPressed: () => _open(null, parents),
            ),
          ]),
          const SizedBox(height: 10),
          if (kids.isEmpty) _empty(_t(context, 'لا يوجد أطفال بعد.', 'Noch keine Kinder.', 'No children yet.')),
          for (final k in shown)
            Card(
              child: ListTile(
                leading: AvatarInitials(_str(k['name'])),
                title: Text(_str(k['name']), style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text([
                    if (_str(k['class_name']).isNotEmpty) _str(k['class_name']),
                    if (_str(k['birth_date']).isNotEmpty) _str(k['birth_date']),
                    for (final g in _l(k['guardians'])) _str(g['name']),
                  ].join(' · ')),
                  const SizedBox(height: 4),
                  Wrap(spacing: 6, runSpacing: 4, children: [
                    for (final g in _l(k['guardians']))
                      Pill(
                        '${_str(g['name'])}: ${_str(g['account_username']).isEmpty ? _t(context, 'بلا حساب', 'ohne Konto', 'no account') : _str(g['account_username'])}',
                        icon: _str(g['account_id']).isEmpty ? Icons.link_off_rounded : Icons.link_rounded,
                        foreground: _str(g['account_id']).isEmpty ? const Color(0xFF8A5200) : _good,
                        background: _str(g['account_id']).isEmpty ? const Color(0xFFFDF1DD) : const Color(0xFFE6F4EC),
                      ),
                  ]),
                ]),
                isThreeLine: true,
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => _open(k, parents),
              ),
            ),
        ]);
      },
    );
  }
}

/// One guardian block: father / other guardian, or mother. Empty fields mean "this parent is not entered".
class _GuardianFields {
  _GuardianFields(Map<String, dynamic>? saved, this.relations)
      : id = saved == null ? null : _str(saved['id']),
        relation = saved == null ? relations.first : _str(saved['relation']),
        name = TextEditingController(text: _str(saved?['name'])),
        phone = TextEditingController(text: _str(saved?['phone'])),
        email = TextEditingController(text: _str(saved?['email'])),
        account = _str(saved?['account_id']).isEmpty ? null : _str(saved?['account_id']);
  final List<String> relations;
  final String? id;
  String relation;
  final TextEditingController name;
  final TextEditingController phone;
  final TextEditingController email;
  String? account;

  bool get used => name.text.trim().isNotEmpty || phone.text.trim().isNotEmpty || email.text.trim().isNotEmpty || account != null;
  Map<String, dynamic> body() => {
        if (id != null && id!.isNotEmpty) 'id': id,
        'relation': relation,
        'name': name.text.trim(),
        'phone': phone.text.trim(),
        'email': email.text.trim(),
        'account_id': account,
      };
}

String _dayOf(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

class _KidEditor extends StatefulWidget {
  const _KidEditor({required this.child, required this.parents});
  final Map<String, dynamic>? child;
  final List<Map<String, dynamic>> parents;
  @override
  State<_KidEditor> createState() => _KidEditorState();
}

class _KidEditorState extends State<_KidEditor> {
  late final _name = TextEditingController(text: _str(widget.child?['name']));
  late final _group = TextEditingController(text: _str(widget.child?['class_name']));
  late String _birth = _str(widget.child?['birth_date']);
  late final _first = _GuardianFields(_l(widget.child?['guardians']).where((g) => g['relation'] != 'mother').firstOrNull, const ['father', 'guardian']);
  late final _mother = _GuardianFields(_l(widget.child?['guardians']).where((g) => g['relation'] == 'mother').firstOrNull, const ['mother']);
  bool _busy = false;

  String _relName(String r) => switch (r) {
        'father' => _t(context, 'الأب', 'Vater', 'Father'),
        'mother' => _t(context, 'الأم', 'Mutter', 'Mother'),
        _ => _t(context, 'وليّ أمر آخر', 'Andere Bezugsperson', 'Other guardian'),
      };

  Widget _block(String title, _GuardianFields g) => FormSection(
        title: title,
        child: Column(children: [
          if (g.relations.length > 1)
            DropdownButtonFormField<String>(
              initialValue: g.relation,
              decoration: InputDecoration(labelText: _t(context, 'صلة القرابة', 'Beziehung', 'Relation')),
              items: [for (final r in g.relations) DropdownMenuItem(value: r, child: Text(_relName(r)))],
              onChanged: (v) => setState(() => g.relation = v ?? g.relation),
            ),
          TextField(controller: g.name, maxLength: 120, onChanged: (_) => setState(() {}), decoration: InputDecoration(labelText: _t(context, 'الاسم الكامل', 'Vollständiger Name', 'Full name'))),
          TextField(controller: g.phone, maxLength: 40, onChanged: (_) => setState(() {}), textDirection: TextDirection.ltr, keyboardType: TextInputType.phone, decoration: InputDecoration(labelText: _t(context, 'الهاتف', 'Telefon', 'Phone'))),
          TextField(controller: g.email, maxLength: 254, onChanged: (_) => setState(() {}), textDirection: TextDirection.ltr, keyboardType: TextInputType.emailAddress, decoration: InputDecoration(labelText: _t(context, 'البريد', 'E-Mail', 'Email'))),
          DropdownButtonFormField<String?>(
            key: ValueKey('${g.relation}-${g.account}'),
            initialValue: g.account,
            isExpanded: true,
            decoration: InputDecoration(labelText: _t(context, 'حساب الدخول', 'Anmeldekonto', 'Sign-in account')),
            items: [
              DropdownMenuItem<String?>(value: null, child: Text(_t(context, '— بلا حساب —', '— ohne Konto —', '— no account —'))),
              for (final a in widget.parents) DropdownMenuItem<String?>(value: _str(a['id']), child: Text(_accountLabel(a), overflow: TextOverflow.ellipsis)),
            ],
            onChanged: (v) => setState(() => g.account = v),
          ),
          _linkState(g),
        ]),
      );

  /// "mona · Mona Parent · Sam": the user name with what is known about the person.
  String _accountLabel(Map<String, dynamic> a) => [
        _str(a['username']),
        if (_str(a['name']).isNotEmpty) _str(a['name']),
        if (a['children'] is List && (a['children'] as List).isNotEmpty) (a['children'] as List).join('، '),
      ].join(' · ');

  /// A parent account that fits the father / mother entered here (same phone, e-mail or name) and is not used by the other one.
  (Map<String, dynamic>, String)? _match(_GuardianFields g) {
    final other = identical(g, _first) ? _mother.account : _first.account;
    String digits(String v) => v.replaceAll(RegExp(r'\D'), '');
    bool samePhone(String a, String b) {
      final da = digits(a), db = digits(b);
      return da.length >= 7 && db.length >= 7 && da.substring(da.length - (da.length < 9 ? da.length : 9)) == db.substring(db.length - (db.length < 9 ? db.length : 9));
    }

    for (final a in widget.parents) {
      if (_str(a['id']) == other) continue;
      final email = g.email.text.trim().toLowerCase();
      if (email.isNotEmpty && _str(a['email']).toLowerCase() == email) return (a, _t(context, 'نفس البريد', 'gleiche E-Mail', 'same e-mail'));
      if (samePhone(g.phone.text, _str(a['phone']))) return (a, _t(context, 'نفس رقم الهاتف', 'gleiche Telefonnummer', 'same phone number'));
      final name = g.name.text.trim().toLowerCase();
      if (name.length > 2 && _str(a['name']).toLowerCase() == name) return (a, _t(context, 'نفس الاسم', 'gleicher Name', 'same name'));
    }
    return null;
  }

  Widget _note(IconData icon, Color color, Color background, String text, {Widget? action}) => Container(
        margin: const EdgeInsets.only(top: 10),
        padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
        decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(14)),
        child: Row(children: [
          Icon(icon, color: color),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: TextStyle(color: color, fontWeight: FontWeight.w600))),
          ?action,
        ]),
      );

  /// Under the account field: linked (the parent sees the child), a matching account to link with one tap, or an invitation.
  Widget _linkState(_GuardianFields g) {
    if (g.account != null) {
      final a = widget.parents.where((p) => _str(p['id']) == g.account).firstOrNull;
      final saved = _str(_l(widget.child?['guardians']).where((x) => _str(x['id']) == g.id).firstOrNull?['account_id']) == g.account;
      return _note(
        Icons.verified_rounded,
        _good,
        const Color(0xFFE6F4EC),
        saved
            ? _t(context, 'مرتبط بالحساب ${_str(a?['username'])}: يرى الطفل في التطبيق والبوابة.', 'Mit ${_str(a?['username'])} verbunden: sieht das Kind in App und Portal.', 'Linked with ${_str(a?['username'])}: sees the child in the app and the portal.')
            : _t(context, 'سيُربط بالحساب ${_str(a?['username'])} عند الحفظ.', 'Wird beim Speichern mit ${_str(a?['username'])} verbunden.', 'Linked with ${_str(a?['username'])} when you save.'),
      );
    }
    final match = _match(g);
    if (match != null) {
      final (a, why) = match;
      return _note(
        Icons.person_search_rounded,
        const Color(0xFF16406F),
        const Color(0xFFEAF1F8),
        _t(context, 'حساب مناسب: ${_str(a['username'])} ($why)', 'Passendes Konto: ${_str(a['username'])} ($why)', 'Matching account: ${_str(a['username'])} ($why)'),
        action: FilledButton(onPressed: () => setState(() => g.account = _str(a['id'])), child: Text(_t(context, 'ربط', 'Verbinden', 'Link'))),
      );
    }
    final child = widget.child;
    if (child == null) {
      return _note(Icons.info_outline_rounded, _muted, const Color(0xFFF1F3F6),
          _t(context, 'بعد حفظ الطفل يمكنك إرسال دعوة لإنشاء حساب.', 'Nach dem Speichern kannst du eine Einladung für ein Konto senden.', 'After saving you can send an invitation to create an account.'));
    }
    return _note(
      Icons.mark_email_unread_outlined,
      const Color(0xFF8A5200),
      const Color(0xFFFDF1DD),
      _t(context, 'لا يوجد حساب بعد. أرسل دعوة: ينشئ وليّ الأمر حسابه ويُربط بالطفل تلقائياً.', 'Noch kein Konto. Einladung senden: Der Elternteil legt sein Konto an und ist sofort mit dem Kind verbunden.',
          'No account yet. Send an invitation: the parent creates an account and is linked to the child at once.'),
      action: FilledButton.tonal(onPressed: () => _invite(g), child: Text(_t(context, 'دعوة', 'Einladen', 'Invite'))),
    );
  }

  Future<void> _invite(_GuardianFields g) async {
    final child = widget.child;
    if (child == null) return;
    final api = SessionScope.of(context).api;
    Map<String, dynamic>? made;
    final ok = await _run(context, () async => made = _m(await api.post('/api/admin/people/children/${child['id']}/invite', {'relation': g.relation})));
    if (!ok || made == null || !mounted) return;
    final code = _str(made!['code']), link = _str(made!['link']);
    final who = g.name.text.trim();
    final kid = _str(child['name']);
    final message = _t(
      context,
      'مرحباً${who.isEmpty ? '' : ' $who'}،\nأنشئ حسابك في روضة زهرة المدائن لمتابعة $kid (التقارير، الحضور، الدردشة مع المعلمات):\n$link\nرمز التسجيل: $code (صالح 7 أيام)',
      'Hallo${who.isEmpty ? '' : ' $who'},\nlege dein Konto bei der Kita Zahrat Al-Madain an, um $kid zu begleiten (Berichte, Anwesenheit, Chat mit den Lehrerinnen):\n$link\nCode: $code (7 Tage gültig)',
      'Hello${who.isEmpty ? '' : ' $who'},\ncreate your account at Zahrat Al-Madain kindergarten to follow $kid (reports, attendance, chat with the teachers):\n$link\nCode: $code (valid for 7 days)',
    );
    await showDialog<void>(
      context: context,
      builder: (dialog) => AlertDialog(
        icon: const Icon(Icons.mark_email_read_rounded, color: _good, size: 36),
        title: Text(_t(context, 'الدعوة جاهزة', 'Einladung bereit', 'Invitation ready')),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(_t(context, 'أرسل هذه الرسالة لوليّ الأمر (واتساب أو رسالة). عند إنشاء الحساب يُربط بالطفل وبهذه الخانة تلقائياً.',
              'Schick diese Nachricht dem Elternteil (WhatsApp oder SMS). Beim Anlegen des Kontos wird es automatisch mit dem Kind und diesem Eintrag verbunden.',
              'Send this message to the parent (WhatsApp or SMS). The new account is linked to the child and to this entry automatically.')),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(color: const Color(0xFFF1F3F6), borderRadius: BorderRadius.circular(12)),
            child: SelectableText(code, textAlign: TextAlign.center, textDirection: TextDirection.ltr, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, letterSpacing: 3)),
          ),
          const SizedBox(height: 8),
          SelectableText(link, textAlign: TextAlign.center, textDirection: TextDirection.ltr, style: const TextStyle(color: _muted, fontSize: 12.5)),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog), child: Text(_t(context, 'إغلاق', 'Schließen', 'Close'))),
          FilledButton.icon(
            icon: const Icon(Icons.copy_rounded),
            label: Text(_t(context, 'نسخ الرسالة', 'Nachricht kopieren', 'Copy the message')),
            onPressed: () async {
              final copied = _t(context, 'نُسخت الرسالة. الصقها في واتساب.', 'Kopiert. In WhatsApp einfügen.', 'Copied. Paste it into WhatsApp.');
              await Clipboard.setData(ClipboardData(text: message));
              if (dialog.mounted) toast(dialog, copied);
            },
          ),
        ],
      ),
    );
  }

  Future<void> _save() async {
    final guardians = [_first, _mother].where((g) => g.used).toList();
    if (_name.text.trim().length < 2) {
      toast(context, _t(context, 'اكتب اسم الطفل.', 'Namen des Kindes eintragen.', 'Enter the name of the child.'));
      return;
    }
    if (guardians.isEmpty) {
      toast(context, _t(context, 'أدخل أحد الوالدين على الأقل.', 'Mindestens ein Elternteil eintragen.', 'Enter at least one parent.'));
      return;
    }
    if (guardians.any((g) => g.name.text.trim().length < 2)) {
      toast(context, _t(context, 'اكتب اسم كل وليّ أمر أدخلت بياناته.', 'Für jeden eingetragenen Elternteil den Namen eintragen.', 'Enter a name for every parent you filled in.'));
      return;
    }
    final api = SessionScope.of(context).api;
    final body = {'name': _name.text.trim(), 'class_name': _group.text.trim(), 'birth_date': _birth.isEmpty ? null : _birth, 'guardians': [for (final g in guardians) g.body()]};
    setState(() => _busy = true);
    final child = widget.child;
    final ok = await _run(context, () => child == null ? api.post('/api/admin/people/children', body) : api.patch('/api/admin/people/children/${child['id']}', body),
        done: _t(context, 'تم الحفظ.', 'Gespeichert.', 'Saved.'));
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    final child = widget.child;
    return Scaffold(
      appBar: AppBar(
        title: Text(child == null ? _t(context, 'طفل جديد', 'Neues Kind', 'New child') : _str(child['name'])),
        actions: [
          if (child != null)
            IconButton(
              tooltip: _t(context, 'إزالة من القائمة', 'Von der Liste nehmen', 'Remove from the list'),
              icon: const Icon(Icons.delete_outline),
              onPressed: () async {
                if (!await confirmDelete(context) || !context.mounted) return;
                final api = SessionScope.of(context).api;
                if (await _run(context, () => api.delete('/api/admin/people/children/${child['id']}'), done: _t(context, 'أُزيل الطفل من القائمة.', 'Kind von der Liste genommen.', 'Child removed from the list.')) && context.mounted) {
                  Navigator.pop(context, true);
                }
              },
            ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(padding: const EdgeInsets.all(16), children: [
            if (_busy) const LinearProgressIndicator(),
            FormSection(
              title: _t(context, 'الطفل', 'Kind', 'Child'),
              child: Column(children: [
                TextField(controller: _name, maxLength: 120, decoration: InputDecoration(labelText: _t(context, 'اسم الطفل', 'Name des Kindes', 'Name of the child'))),
                TextField(controller: _group, maxLength: 60, decoration: InputDecoration(labelText: _t(context, 'المجموعة / الصف', 'Gruppe / Klasse', 'Group / class'))),
                Row(children: [
                  Expanded(child: Text('${_t(context, 'تاريخ الميلاد', 'Geburtsdatum', 'Birth date')}: ${_birth.isEmpty ? '—' : _birth}')),
                  TextButton(
                    onPressed: () async {
                      final d = await showDatePicker(context: context, initialDate: DateTime.tryParse(_birth) ?? DateTime(DateTime.now().year - 4), firstDate: DateTime(2010), lastDate: DateTime.now());
                      if (d != null) setState(() => _birth = _dayOf(d));
                    },
                    child: Text(_t(context, 'اختيار', 'Wählen', 'Choose')),
                  ),
                  if (_birth.isNotEmpty) IconButton(onPressed: () => setState(() => _birth = ''), icon: const Icon(Icons.close_rounded)),
                ]),
              ]),
            ),
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(_t(context, 'أدخل أحد الوالدين أو كليهما. يبقى الحقل فارغاً إن كان للطفل وليّ أمر واحد.', 'Einen oder beide Elternteile eintragen. Leer lassen, wenn es nur einen gibt.', 'Enter one or both parents. Leave empty if there is only one.'), style: const TextStyle(color: _muted)),
            ),
            for (final a in _l(widget.child?['other_accounts']))
              if (_first.account != _str(a['id']) && _mother.account != _str(a['id']))
                Card(
                  color: const Color(0xFFEAF1F8),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(
                          _t(context, 'الحساب ${_str(a['username'])} مرتبط بالطفل لكنه غير مسجّل عند الأب أو الأم.', 'Das Konto ${_str(a['username'])} ist mit dem Kind verbunden, steht aber bei keinem Elternteil.',
                              'The account ${_str(a['username'])} is linked to the child but stands at no parent.'),
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      Wrap(spacing: 8, children: [
                        OutlinedButton(onPressed: () => setState(() => _first.account = _str(a['id'])), child: Text(_t(context, 'للأب / وليّ الأمر', 'Zum Vater', 'To the father'))),
                        OutlinedButton(onPressed: () => setState(() => _mother.account = _str(a['id'])), child: Text(_t(context, 'للأم', 'Zur Mutter', 'To the mother'))),
                      ]),
                    ]),
                  ),
                ),
            _block(_t(context, 'الأب / وليّ الأمر', 'Vater / Bezugsperson', 'Father / guardian'), _first),
            _block(_t(context, 'الأم', 'Mutter', 'Mother'), _mother),
          ]),
        ),
      ),
      bottomNavigationBar: BottomActionBar(children: [
        Expanded(child: FilledButton(onPressed: _busy ? null : _save, child: Text(_t(context, 'حفظ', 'Speichern', 'Save')))),
      ]),
    );
  }
}

class _StaffTab extends StatefulWidget {
  const _StaffTab();
  @override
  State<_StaffTab> createState() => _StaffTabState();
}

class _StaffTabState extends State<_StaffTab> {
  int _round = 0;

  Future<void> _open(Map<String, dynamic>? person, List<Map<String, dynamic>> accounts) async {
    final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => _StaffEditor(person: person, accounts: accounts)));
    if (saved == true) setState(() => _round++);
  }

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return Loader<(List<Map<String, dynamic>>, List<Map<String, dynamic>>)>(
      key: ValueKey(_round),
      load: () async => Cached((_l(await api.get('/api/admin/people/employees')), _l(await api.get('/api/admin/people/staff-accounts')))),
      builder: (context, data, reload) {
        final (staff, accounts) = data;
        return ListView(padding: const EdgeInsets.all(12), children: [
          Wrap(spacing: 10, runSpacing: 10, children: [
            FilledButton.icon(
              style: FilledButton.styleFrom(minimumSize: const Size(0, 46)),
              icon: const Icon(Icons.person_add_alt_1_rounded),
              label: Text(_t(context, 'موظف جديد', 'Neue Person', 'New staff member')),
              onPressed: () => _open(null, accounts),
            ),
            OutlinedButton.icon(
              icon: const Icon(Icons.picture_as_pdf_outlined),
              label: Text(_t(context, 'القائمة PDF (الكل)', 'Liste als PDF (alle)', 'List as PDF (all)')),
              onPressed: () => openPrivateFile(context, api, '/api/admin/people/employees/export.pdf', 'staff-all.pdf', query: {'scope': 'all'}),
            ),
            OutlinedButton.icon(
              icon: const Icon(Icons.picture_as_pdf_outlined),
              label: Text(_t(context, 'القائمة PDF (النشطون)', 'Liste als PDF (aktive)', 'List as PDF (active)')),
              onPressed: () => openPrivateFile(context, api, '/api/admin/people/employees/export.pdf', 'staff-active.pdf', query: {'scope': 'active'}),
            ),
          ]),
          const SizedBox(height: 10),
          if (staff.isEmpty) _empty(_t(context, 'لا يوجد موظفون بعد.', 'Noch kein Personal.', 'No staff yet.')),
          for (final p in staff)
            Card(
              child: ListTile(
                leading: AvatarInitials(_str(p['name'])),
                title: Text(_str(p['name']), style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text([
                  if (_str(p['job_title']).isNotEmpty) _str(p['job_title']),
                  if (p['salary'] != null) '${_str(p['salary'])} ${_str(p['salary_currency'])}',
                  if (_str(p['account_username']).isNotEmpty) _str(p['account_username']),
                ].join(' · ')),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => _open(p, accounts),
              ),
            ),
        ]);
      },
    );
  }
}

class _StaffEditor extends StatefulWidget {
  const _StaffEditor({required this.person, required this.accounts});
  final Map<String, dynamic>? person;
  final List<Map<String, dynamic>> accounts;
  @override
  State<_StaffEditor> createState() => _StaffEditorState();
}

class _StaffEditorState extends State<_StaffEditor> {
  late final _name = TextEditingController(text: _str(widget.person?['name']));
  late final _job = TextEditingController(text: _str(widget.person?['job_title']));
  late final _salary = TextEditingController(text: _str(widget.person?['salary']));
  late final _phone = TextEditingController(text: _str(widget.person?['phone']));
  late final _notes = TextEditingController(text: _str(widget.person?['notes']));
  late String _currency = _str(widget.person?['salary_currency']).isEmpty ? 'SYP' : _str(widget.person?['salary_currency']);
  late String? _account = _str(widget.person?['account_id']).isEmpty ? null : _str(widget.person?['account_id']);
  late String _hired = _str(widget.person?['hired_on']);
  bool _busy = false;

  Future<void> _save() async {
    if (_name.text.trim().length < 2) {
      toast(context, _t(context, 'اكتب الاسم.', 'Namen eintragen.', 'Enter the name.'));
      return;
    }
    final api = SessionScope.of(context).api;
    final body = <String, dynamic>{
      'name': _name.text.trim(),
      'job_title': _job.text.trim(),
      'salary_currency': _currency,
      'account_id': _account,
      'phone': _phone.text.trim(),
      'hired_on': _hired.isEmpty ? null : _hired,
      'notes': _notes.text.trim(),
      if (_salary.text.trim().isNotEmpty || widget.person != null) 'salary': _salary.text.trim().isEmpty ? null : _salary.text.trim(),
    };
    setState(() => _busy = true);
    final person = widget.person;
    try {
      final res = _m(person == null ? await api.post('/api/admin/people/employees', body) : await api.patch('/api/admin/people/employees/${person['id']}', body));
      if (!mounted) return;
      final followed = (res['updated_salary_rows'] as num? ?? 0).toInt();
      toast(context, followed > 0 ? '${_t(context, 'تم الحفظ. عُدّلت رواتب مسجّلة', 'Gespeichert. Angepasste Gehaltsbuchungen', 'Saved. Salary entries updated')}: $followed' : _t(context, 'تم الحفظ.', 'Gespeichert.', 'Saved.'));
      Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) toast(context, e.detail.isNotEmpty ? e.detail : problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final person = widget.person;
    return Scaffold(
      appBar: AppBar(
        title: Text(person == null ? _t(context, 'موظف جديد', 'Neue Person', 'New staff member') : _str(person['name'])),
        actions: [
          if (person != null)
            IconButton(
              tooltip: _t(context, 'إزالة من القائمة', 'Von der Liste nehmen', 'Remove from the list'),
              icon: const Icon(Icons.delete_outline),
              onPressed: () async {
                if (!await confirmDelete(context) || !context.mounted) return;
                final api = SessionScope.of(context).api;
                if (await _run(context, () => api.delete('/api/admin/people/employees/${person['id']}'), done: _t(context, 'أُزيل من القائمة.', 'Von der Liste genommen.', 'Removed from the list.')) && context.mounted) {
                  Navigator.pop(context, true);
                }
              },
            ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(padding: const EdgeInsets.all(16), children: [
            if (_busy) const LinearProgressIndicator(),
            FormSection(
              title: _t(context, 'البيانات', 'Angaben', 'Details'),
              child: Column(children: [
                TextField(controller: _name, maxLength: 120, decoration: InputDecoration(labelText: _t(context, 'الاسم الكامل', 'Vollständiger Name', 'Full name'))),
                TextField(controller: _job, maxLength: 80, decoration: InputDecoration(labelText: _t(context, 'المسمى الوظيفي', 'Tätigkeit', 'Job title'))),
                TextField(controller: _phone, maxLength: 40, textDirection: TextDirection.ltr, keyboardType: TextInputType.phone, decoration: InputDecoration(labelText: _t(context, 'الهاتف', 'Telefon', 'Phone'))),
                Row(children: [
                  Expanded(child: Text('${_t(context, 'تاريخ التعيين', 'Eingestellt am', 'Hired on')}: ${_hired.isEmpty ? '—' : _hired}')),
                  TextButton(
                    onPressed: () async {
                      final d = await showDatePicker(context: context, initialDate: DateTime.tryParse(_hired) ?? DateTime.now(), firstDate: DateTime(2000), lastDate: DateTime(DateTime.now().year + 1));
                      if (d != null) setState(() => _hired = _dayOf(d));
                    },
                    child: Text(_t(context, 'اختيار', 'Wählen', 'Choose')),
                  ),
                  if (_hired.isNotEmpty) IconButton(onPressed: () => setState(() => _hired = ''), icon: const Icon(Icons.close_rounded)),
                ]),
                TextField(controller: _notes, maxLength: 500, maxLines: 3, minLines: 1, decoration: InputDecoration(labelText: _t(context, 'ملاحظات', 'Notizen', 'Notes'))),
              ]),
            ),
            FormSection(
              title: _t(context, 'الراتب الشهري المعتاد', 'Übliches Monatsgehalt', 'Usual monthly salary'),
              child: Column(children: [
                TextField(controller: _salary, keyboardType: const TextInputType.numberWithOptions(decimal: true), textDirection: TextDirection.ltr, decoration: InputDecoration(labelText: _t(context, 'المبلغ (اختياري)', 'Betrag (optional)', 'Amount (optional)'))),
                const SizedBox(height: 10),
                SegmentedButton<String>(
                  segments: const [ButtonSegment(value: 'SYP', label: Text('SYP')), ButtonSegment(value: 'USD', label: Text('USD'))],
                  selected: {_currency},
                  onSelectionChanged: (v) => setState(() => _currency = v.first),
                ),
              ]),
            ),
            FormSection(
              title: _t(context, 'حساب الدخول (معلمة أو محاسب)', 'Anmeldekonto (Lehrerin oder Buchhaltung)', 'Sign-in account (teacher or accountant)'),
              child: DropdownButtonFormField<String?>(
                initialValue: _account,
                isExpanded: true,
                items: [
                  DropdownMenuItem<String?>(value: null, child: Text(_t(context, '— بلا حساب —', '— ohne Konto —', '— no account —'))),
                  for (final a in widget.accounts)
                    DropdownMenuItem<String?>(
                      value: _str(a['id']),
                      enabled: _str(a['linked_to']).isEmpty || _str(a['id']) == _account,
                      child: Text('${_str(a['username'])} (${[for (final r in (a['roles'] as List? ?? const [])) _role(context, '$r')].join(' + ')})${_str(a['linked_to']).isNotEmpty && _str(a['id']) != _account ? ' — ${_str(a['linked_to'])}' : ''}'),
                    ),
                ],
                onChanged: (v) => setState(() => _account = v),
              ),
            ),
          ]),
        ),
      ),
      bottomNavigationBar: BottomActionBar(children: [
        Expanded(child: FilledButton(onPressed: _busy ? null : _save, child: Text(_t(context, 'حفظ', 'Speichern', 'Save')))),
      ]),
    );
  }
}

class _GroupsTab extends StatelessWidget {
  const _GroupsTab();
  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return _load(context, '/api/admin/platform/groups', (context, data, reload) {
      final groups = _l(data);
      return ListView(padding: const EdgeInsets.all(12), children: [
        Text(_t(context, 'تنشأ المجموعة حين تكتبها في ملف طفل. يمكنك إعادة تسميتها هنا لكل أطفالها مرة واحدة.', 'Eine Gruppe entsteht, wenn du sie bei einem Kind einträgst. Hier benennst du sie für alle Kinder auf einmal um.', 'A group exists once you type it for a child. Rename it here for all its children at once.'), style: const TextStyle(color: _muted)),
        const SizedBox(height: 10),
        if (groups.isEmpty) _empty(_t(context, 'لا توجد مجموعات بعد.', 'Noch keine Gruppen.', 'No groups yet.')),
        for (final g in groups)
          Card(
            child: ListTile(
              leading: const Icon(Icons.groups_2_outlined),
              title: Text(_str(g['name']), style: const TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text('${_str(g['children'])} ${_t(context, 'أطفال', 'Kinder', 'children')}'),
              trailing: IconButton(
                tooltip: _t(context, 'إعادة تسمية', 'Umbenennen', 'Rename'),
                icon: const Icon(Icons.edit_outlined),
                onPressed: () async {
                  final next = await askText(context, _t(context, 'الاسم الجديد', 'Neuer Name', 'New name'), initial: _str(g['name']), maxLength: 60);
                  if (next == null || next.trim().isEmpty || next.trim() == _str(g['name']) || !context.mounted) return;
                  if (await _run(context, () => api.post('/api/admin/platform/groups/rename', {'old_name': _str(g['name']), 'new_name': next.trim()}))) await reload();
                },
              ),
            ),
          ),
      ]);
    });
  }
}

// =================================================================================================================================
// notices of the management (shown to parents and teachers)
// =================================================================================================================================
class AdminNoticesPage extends StatefulWidget {
  const AdminNoticesPage({super.key});
  @override
  State<AdminNoticesPage> createState() => _AdminNoticesPageState();
}

class _AdminNoticesPageState extends State<AdminNoticesPage> {
  int _round = 0;
  final _title = TextEditingController();
  final _body = TextEditingController();
  bool _busy = false;

  Future<void> _publish() async {
    if (_title.text.trim().isEmpty) return;
    final api = SessionScope.of(context).api;
    setState(() => _busy = true);
    final ok = await _run(context, () => api.post('/api/admin/platform/announcements', {'title': _title.text.trim(), 'body': _body.text.trim()}), done: _t(context, 'تم النشر.', 'Veröffentlicht.', 'Published.'));
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (ok) {
        _title.clear();
        _body.clear();
        _round++;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return _load(context, '/api/platform/announcements', key: ValueKey(_round), (context, data, reload) {
      final items = _l(data);
      return ListView(padding: const EdgeInsets.all(12), children: [
        _Box(
          title: _t(context, 'إعلان جديد', 'Neue Ankündigung', 'New notice'),
          hint: _t(context, 'يظهر للأهل والمعلمات ويصلهم إشعار.', 'Erscheint bei Eltern und Lehrerinnen, sie bekommen eine Benachrichtigung.', 'Shown to parents and teachers, who get a notification.'),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            TextField(controller: _title, maxLength: 120, decoration: InputDecoration(labelText: _t(context, 'العنوان', 'Titel', 'Title'))),
            TextField(controller: _body, maxLength: 2000, maxLines: 5, minLines: 2, decoration: InputDecoration(labelText: _t(context, 'النص', 'Text', 'Text'))),
            const SizedBox(height: 8),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: FilledButton.icon(
                style: FilledButton.styleFrom(minimumSize: const Size(140, 46)),
                icon: const Icon(Icons.campaign_outlined),
                label: Text(_t(context, 'نشر', 'Veröffentlichen', 'Publish')),
                onPressed: _busy ? null : _publish,
              ),
            ),
          ]),
        ),
        _Box(
          title: _t(context, 'الإعلانات المنشورة', 'Veröffentlichte Ankündigungen', 'Published notices'),
          child: Column(children: [
            if (items.isEmpty) _empty(_t(context, 'لا توجد إعلانات.', 'Keine Ankündigungen.', 'No notices.')),
            for (final n in items)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(_str(n['title']), style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text([if (_str(n['body']).isNotEmpty) _str(n['body']), _when(n['created_at'])].join('\n')),
                isThreeLine: _str(n['body']).isNotEmpty,
                trailing: IconButton(
                  tooltip: _t(context, 'حذف', 'Löschen', 'Delete'),
                  icon: const Icon(Icons.delete_outline, color: _bad),
                  onPressed: () async {
                    if (!await confirmDelete(context) || !context.mounted) return;
                    if (await _run(context, () => api.delete('/api/admin/platform/announcements/${n['id']}'))) await reload();
                  },
                ),
              ),
          ]),
        ),
      ]);
    });
  }
}

// =================================================================================================================================
// teachers' posts and materials (the teacher portal of the website, admin view)
// =================================================================================================================================
class AdminTeacherWorkPage extends StatelessWidget {
  const AdminTeacherWorkPage({super.key});
  @override
  Widget build(BuildContext context) => _Tabbed(
        tabs: [_t(context, 'كل المنشورات', 'Alle Beiträge', 'All posts'), _t(context, 'مواد المعلمات', 'Materialien', 'Materials')],
        pages: const [_AllPosts(), _AllMaterials()],
      );
}

class _AllPosts extends StatelessWidget {
  const _AllPosts();
  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return _load(context, '/api/platform/admin/posts', (context, data, reload) {
      final posts = _l(data);
      return ListView(padding: const EdgeInsets.all(12), children: [
        if (posts.isEmpty) _empty(_t(context, 'لا توجد منشورات.', 'Keine Beiträge.', 'No posts.')),
        for (final p in posts)
          _Box(
            title: _str(p['title']),
            hint: [
              p['scope'] == 'child' ? '${_t(context, 'خاص', 'Privat', 'Private')}${_str(p['child_name']).isEmpty ? '' : ' · ${_str(p['child_name'])}'}' : _t(context, 'عام', 'Für alle', 'General'),
              _str(p['author']).isNotEmpty ? _str(p['author']) : _str(p['author_username']),
              _str(p['created_at']).length >= 10 ? _str(p['created_at']).substring(0, 10) : '',
            ].where((x) => x.isNotEmpty).join(' · '),
            trailing: IconButton(
              tooltip: _t(context, 'حذف', 'Löschen', 'Delete'),
              icon: const Icon(Icons.delete_outline, color: _bad),
              onPressed: () async {
                if (!await confirmDelete(context) || !context.mounted) return;
                if (await _run(context, () => api.delete('/api/platform/admin/posts/${p['id']}'))) await reload();
              },
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              if (_str(p['body']).isNotEmpty) Text(_str(p['body']), style: const TextStyle(height: 1.5)),
              if (_l(p['files']).isNotEmpty) ...[
                const SizedBox(height: 8),
                Wrap(spacing: 6, runSpacing: 6, children: [
                  for (final f in _l(p['files']))
                    ActionChip(
                      avatar: const Icon(Icons.attach_file_rounded, size: 18),
                      label: Text('${_str(f['filename'])} · ${formatSize((f['size'] as num? ?? 0).toInt())}'),
                      onPressed: () => openPrivateFile(context, api, '/api/platform/admin/teacher-content/${f['id']}/download', _str(f['filename'])),
                    ),
                ]),
              ],
            ]),
          ),
      ]);
    });
  }
}

class _AllMaterials extends StatelessWidget {
  const _AllMaterials();
  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return _load(context, '/api/platform/admin/teacher-content', (context, data, reload) {
      final items = _l(data);
      return ListView(padding: const EdgeInsets.all(12), children: [
        if (items.isEmpty) _empty(_t(context, 'لا توجد ملفات.', 'Keine Dateien.', 'No files.')),
        for (final c in items)
          Card(
            child: ListTile(
              leading: FileTypePlate(filename: _str(c['filename'])),
              title: Text(_str(c['filename']), maxLines: 1, overflow: TextOverflow.ellipsis),
              subtitle: Text([_str(c['owner_username']), formatSize((c['size'] as num? ?? 0).toInt())].where((x) => x.isNotEmpty).join(' · ')),
              onTap: () => openPrivateFile(context, api, '/api/platform/admin/teacher-content/${c['id']}/download', _str(c['filename'])),
              trailing: IconButton(
                tooltip: _t(context, 'حذف', 'Löschen', 'Delete'),
                icon: const Icon(Icons.delete_outline, color: _bad),
                onPressed: () async {
                  if (!await confirmDelete(context) || !context.mounted) return;
                  if (await _run(context, () => api.delete('/api/platform/admin/teacher-content/${c['id']}'))) await reload();
                },
              ),
            ),
          ),
      ]);
    });
  }
}

// ---- control centre: activity of every area ---------------------------------------------------------------------------------------
class _ControlActivity extends StatefulWidget {
  const _ControlActivity();
  @override
  State<_ControlActivity> createState() => _ControlActivityState();
}

class _ControlActivityState extends State<_ControlActivity> {
  String _domain = 'all';
  @override
  Widget build(BuildContext context) {
    String dn(String k) {
      final x = _domains[k];
      return x == null ? k : _t(context, x[0], x[1], x[2]);
    }

    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
        child: Align(
          alignment: AlignmentDirectional.centerStart,
          child: SizedBox(
            width: 220,
            child: DropdownButtonFormField<String>(
              initialValue: _domain,
              decoration: InputDecoration(labelText: _t(context, 'المجال', 'Bereich', 'Area')),
              items: [for (final k in _domains.keys) DropdownMenuItem(value: k, child: Text(dn(k)))],
              onChanged: (v) => setState(() => _domain = v ?? 'all'),
            ),
          ),
        ),
      ),
      Expanded(
        child: _load(context, '/api/admin/control/activity', key: ValueKey(_domain), query: {'limit': '200', 'domain': _domain}, (context, data, reload) {
          final rows = _l(data);
          return ListView(padding: const EdgeInsets.all(12), children: [
            if (rows.isEmpty) _empty(_t(context, 'لا توجد إجراءات', 'Keine Einträge', 'No activity')),
            for (final r in rows)
              Card(
                child: ListTile(
                  title: Text('${_str(r['actor'])} · ${dn(_str(r['domain']))}', style: const TextStyle(fontWeight: FontWeight.w700)),
                  subtitle: Text([_str(r['action']), if (_str(r['reason']).isNotEmpty) _str(r['reason'])].join('\n')),
                  trailing: Text(_str(r['at_local']).replaceFirst('T', ' ').padRight(16).substring(0, 16), textDirection: TextDirection.ltr, style: const TextStyle(fontSize: 12, color: _muted)),
                ),
              ),
          ]);
        }),
      ),
    ]);
  }
}
