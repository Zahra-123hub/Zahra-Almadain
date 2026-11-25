import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../localization/strings.dart';
import '../../models/models.dart';
import '../../services/api.dart';
import '../../services/session.dart';
import '../../shared/ui.dart';
import '../parents/parent_pages.dart';

// Everyday life of a child (the same server endpoints as the portals of the website):
//  - parents: one colourful home per child with tiles (child's data, reports, notes, things to bring, week plan, attendance,
//    news, messages, fees);
//  - kindergarten (teacher, management, admin): attendance, notes, things to bring, week plan, messages.
// The texts of these pages are written here in the three languages with `_t`.

String _t(BuildContext context, String ar, String de, String en) {
  final code = S.of(context).code;
  return code == 'ar' ? ar : (code == 'de' ? de : en);
}

Map<String, dynamic> _m(Object? v) => v is Map ? v.cast<String, dynamic>() : <String, dynamic>{};
List<Map<String, dynamic>> _l(Object? v) => [for (final x in (v is List ? v : const [])) if (x is Map) x.cast<String, dynamic>()];
String _s(Object? v) => v == null ? '' : '$v';
String _day(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// "2026-11-23 14:05" in local time.
String _when(Object? iso) {
  final d = DateTime.tryParse(_s(iso));
  if (d == null) return _s(iso);
  final l = d.isUtc ? d.toLocal() : DateTime.utc(d.year, d.month, d.day, d.hour, d.minute).toLocal();
  return '${_day(l)} ${l.hour.toString().padLeft(2, '0')}:${l.minute.toString().padLeft(2, '0')}';
}

const _muted = Color(0xFF5B6878);
const _good = Color(0xFF1E7A45);
const _bad = Color(0xFFB3402F);

List<String> _weekdays(BuildContext context) => [
      _t(context, 'الأحد', 'Sonntag', 'Sunday'),
      _t(context, 'الاثنين', 'Montag', 'Monday'),
      _t(context, 'الثلاثاء', 'Dienstag', 'Tuesday'),
      _t(context, 'الأربعاء', 'Mittwoch', 'Wednesday'),
      _t(context, 'الخميس', 'Donnerstag', 'Thursday'),
    ];

Widget _load(BuildContext context, String path, Widget Function(BuildContext, dynamic, Future<void> Function()) builder, {Map<String, String>? query, Key? key}) {
  final api = SessionScope.of(context).api;
  return Loader<dynamic>(key: key, load: () async => Cached<dynamic>(await api.get(path, query: query)), builder: builder);
}

Future<bool> _run(BuildContext context, Future<dynamic> Function() action, {String? done}) async {
  try {
    await action();
    if (context.mounted && done != null) toast(context, done);
    return true;
  } on ApiException catch (e) {
    if (context.mounted) toast(context, problemText(context, e));
    return false;
  }
}

Widget _empty(BuildContext context, IconData icon, String text) => ListView(children: [StateView(icon: icon, title: text)]);

/// A page with a title bar, the same width limit everywhere.
Widget _page(BuildContext context, String title, Widget body, {Widget? fab, List<Widget>? actions}) => Scaffold(
      appBar: AppBar(title: Text(title), actions: actions),
      floatingActionButton: fab,
      body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 820), child: body)),
    );

/// A date heading in lists ("📅 2026-11-23").
Widget _dateHead(String text) => Padding(
      padding: const EdgeInsets.fromLTRB(4, 14, 4, 8),
      child: Row(children: [
        const Icon(Icons.calendar_month_rounded, size: 18, color: _muted),
        const SizedBox(width: 6),
        Text(text, textDirection: TextDirection.ltr, style: const TextStyle(fontWeight: FontWeight.w800, color: _muted)),
      ]),
    );

// =================================================================================================================================
// parents: the home of one child
// =================================================================================================================================
class _Tile {
  const _Tile(this.label, this.icon, this.colors, this.open, {this.badge = 0});
  final String label;
  final IconData icon;
  final List<Color> colors;
  final Widget Function() open;
  final int badge;
}

class ChildHubPage extends StatefulWidget {
  const ChildHubPage({super.key, required this.child, this.embedded = false, this.top});
  final Child child;

  /// true: shown inside the parents' home (no own page, no back button).
  final bool embedded;

  /// Shown above the tiles (the choice between several children on the home page).
  final Widget? top;
  @override
  State<ChildHubPage> createState() => _ChildHubPageState();
}

class _ChildHubPageState extends State<ChildHubPage> {
  int _round = 0;

  @override
  Widget build(BuildContext context) {
    final c = widget.child;
    final hub = _load(context, '/api/platform/parent/children/${c.id}/overview', key: ValueKey('${c.id}$_round'), (context, data, reload) {
        final d = _m(data);
        final counts = _m(d['counts']);
        int n(String k) => (counts[k] as num? ?? 0).toInt();
        final tiles = _parentTiles(context, c, d, n);
        final today = _s(_m(d['today'])['attendance']);
        return CustomScrollView(slivers: [
          // on the home page: the same greeting card as the teachers' home, the child's name and today below it
          if (widget.embedded)
            SliverToBoxAdapter(
              child: _greetingCard(
                context,
                below: Wrap(spacing: 6, runSpacing: 4, children: [
                  Pill(_s(d['name']), icon: Icons.child_care_rounded),
                  if (_s(d['class_name']).isNotEmpty) Pill(_s(d['class_name']), icon: Icons.groups_2_outlined),
                  if (today.isNotEmpty) _attendancePill(context, today),
                ]),
              ),
            ),
          if (widget.top != null) SliverToBoxAdapter(child: widget.top),
          if (!widget.embedded)
          SliverToBoxAdapter(
            child: Container(
              padding: EdgeInsets.fromLTRB(16, MediaQuery.paddingOf(context).top + 8, 16, 20),
              decoration: const BoxDecoration(
                gradient: LinearGradient(colors: [Color(0xFFDCEBFB), Color(0xFFF4F7FB)], begin: Alignment.topCenter, end: Alignment.bottomCenter),
                borderRadius: BorderRadius.vertical(bottom: Radius.circular(28)),
              ),
              child: Row(children: [
                IconButton(onPressed: () => Navigator.maybePop(context), icon: const Icon(Icons.arrow_back_rounded)),
                const SizedBox(width: 4),
                AvatarInitials(_s(d['name']), size: 58),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(_s(d['name']), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                    const SizedBox(height: 4),
                    Wrap(spacing: 6, runSpacing: 4, children: [
                      if (_s(d['class_name']).isNotEmpty) Pill(_s(d['class_name']), icon: Icons.groups_2_outlined),
                      if (today.isNotEmpty) _attendancePill(context, today),
                    ]),
                  ]),
                ),
              ]),
            ),
          ),
          _tileGrid([
            for (final t in tiles)
              _TileCard(t, onTap: () async {
                await Navigator.push(context, MaterialPageRoute(builder: (_) => t.open()));
                if (mounted) setState(() => _round++);
              }),
          ]),
        ]);
      });
    return widget.embedded ? hub : Scaffold(body: hub);
  }
}

/// The nine tiles of a child's page. [c] is null while the parent account is not linked to a child yet.
List<_Tile> _parentTiles(BuildContext context, Child? c, Map<String, dynamic> d, int Function(String) n) => [
      _Tile(_t(context, 'بيانات الطفل', 'Daten des Kindes', 'Child details'), Icons.badge_rounded, const [Color(0xFF7FB3F0), Color(0xFF4F8EDC)], () => _ProfilePage(data: d)),
      _Tile(_t(context, 'التقارير اليومية', 'Tagesberichte', 'Daily reports'), Icons.description_rounded, const [Color(0xFF6FB7A8), Color(0xFF3E9483)], () => ChildReportsPage(child: c!)),
      _Tile(_t(context, 'ملاحظات', 'Lob & Notizen', 'Notes'), Icons.star_rounded, const [Color(0xFF8CC47A), Color(0xFF5FA34C)], () => _ParentNotesPage(child: c!), badge: n('notes_new')),
      _Tile(_t(context, 'أحضِر معك', 'Bitte mitbringen', 'Please bring'), Icons.backpack_rounded, const [Color(0xFFF2B65A), Color(0xFFE5952B)], () => _ParentBringPage(child: c!), badge: n('bring_open')),
      _Tile(_t(context, 'برنامج الأسبوع', 'Wochenplan', 'Week plan'), Icons.calendar_view_week_rounded, const [Color(0xFF8EB6F2), Color(0xFF5C8FE0)], () => _ParentPlanPage(child: c!)),
      _Tile(_t(context, 'الحضور', 'Anwesenheit', 'Attendance'), Icons.how_to_reg_rounded, const [Color(0xFFE57E6E), Color(0xFFCF5443)], () => _ParentAttendancePage(child: c!)),
      _Tile(_t(context, 'الأخبار', 'Neuigkeiten', 'News'), Icons.campaign_rounded, const [Color(0xFFB07CCB), Color(0xFF8E52B0)], () => _page(context, _t(context, 'الأخبار', 'Neuigkeiten', 'News'), const ParentPosts())),
      _Tile(_t(context, 'دردشة', 'Nachrichten', 'Messages'), Icons.chat_rounded, const [Color(0xFF5FB3A6), Color(0xFF368F81)], () => ParentChatsPage(child: c!), badge: n('messages_unread')),
      _Tile(_t(context, 'الرسوم', 'Gebühren', 'Fees'), Icons.receipt_long_rounded, const [Color(0xFFAEB4BC), Color(0xFF858D97)], () => _ParentFeesPage(child: c!), badge: n('invoices_open')),
    ];

/// The greeting on the home pages of parents and teachers: "Hello" with the user name, today's date and an optional line below.
Widget _greetingCard(BuildContext context, {Widget? below}) {
  final session = SessionScope.of(context);
  return Container(
    margin: const EdgeInsets.fromLTRB(16, 16, 16, 4),
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(gradient: const LinearGradient(colors: [Color(0xFFDCEBFB), Color(0xFFF4F7FB)]), borderRadius: BorderRadius.circular(24)),
    child: Row(children: [
      AvatarInitials(session.username ?? '?', size: 54),
      const SizedBox(width: 12),
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${_t(context, 'أهلاً', 'Hallo', 'Hello')} ${session.username ?? ''}', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text('${_weekdayName(context, _day(DateTime.now()))} · ${_day(DateTime.now())}', style: const TextStyle(color: _muted)),
          if (below != null) ...[const SizedBox(height: 8), below],
        ]),
      ),
    ]),
  );
}

/// The grid of coloured tiles, 2 to 5 per row depending on the width.
Widget _tileGrid(List<Widget> cards) => SliverPadding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      sliver: SliverLayoutBuilder(builder: (context, constraints) {
        final cols = (constraints.crossAxisExtent / 200).floor().clamp(2, 5);
        return SliverGrid.count(crossAxisCount: cols, mainAxisSpacing: 14, crossAxisSpacing: 14, childAspectRatio: 1.05, children: cards);
      }),
    );

/// The parents' home: the tiles of the child right away; with several children a choice on top.
class ParentTilesHome extends StatefulWidget {
  const ParentTilesHome({super.key});
  @override
  State<ParentTilesHome> createState() => _ParentTilesHomeState();
}

class _ParentTilesHomeState extends State<ParentTilesHome> {
  String? _chosen;

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return Loader<List<Child>>(
      load: () async {
        final c = await api.getCached('/api/platform/children');
        return Cached(parseList(c.data, Child.fromJson), fromCache: c.fromCache);
      },
      builder: (context, children, reload) {
        if (children.isEmpty) {
          // the same home without a child: the tiles are there, the child's pages open once the kindergarten has linked the account
          final hint = _t(context, 'لم يُربط حسابك بطفل بعد. تربطه الروضة بعد الموافقة.', 'Dein Konto ist noch mit keinem Kind verbunden. Das macht die Kita.', 'Your account is not linked to a child yet. The kindergarten does that.');
          final tiles = _parentTiles(context, null, const {}, (_) => 0);
          return RefreshIndicator(
            onRefresh: () async => reload(),
            child: CustomScrollView(slivers: [
              SliverToBoxAdapter(
                child: _greetingCard(
                  context,
                  below: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Icon(Icons.info_outline_rounded, size: 18, color: Color(0xFF8A5200)),
                    const SizedBox(width: 6),
                    Expanded(child: Text(hint, style: const TextStyle(color: Color(0xFF8A5200), fontWeight: FontWeight.w600))),
                  ]),
                ),
              ),
              _tileGrid([
                for (final (i, t) in tiles.indexed)
                  _TileCard(t, onTap: () {
                    if (i == 6) {
                      Navigator.push(context, MaterialPageRoute(builder: (_) => t.open()));
                    } else {
                      toast(context, hint);
                    }
                  }),
              ]),
            ]),
          );
        }
        final child = children.firstWhere((c) => c.id == _chosen, orElse: () => children.first);
        final chooser = children.length < 2
            ? null
            : Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                child: Wrap(spacing: 8, runSpacing: 8, children: [
                  for (final c in children)
                    ChoiceChip(
                      avatar: CircleAvatar(child: Text(c.name.isEmpty ? '?' : c.name.characters.first)),
                      label: Text(c.name),
                      selected: c.id == child.id,
                      onSelected: (_) => setState(() => _chosen = c.id),
                    ),
                ]),
              );
        return ChildHubPage(key: ValueKey(child.id), child: child, embedded: true, top: chooser);
      },
    );
  }
}

/// The teachers' home: the same coloured tiles, each opening one page of the teacher area.
class TeacherTilesHome extends StatelessWidget {
  const TeacherTilesHome({super.key, required this.goTo});
  final void Function(String id) goTo;
  @override
  Widget build(BuildContext context) {
    final tiles = [
      (_t(context, 'أطفالي', 'Meine Kinder', 'My children'), Icons.child_care_rounded, const [Color(0xFF7FB3F0), Color(0xFF4F8EDC)], 'children'),
      (_t(context, 'التقارير اليومية', 'Tagesberichte', 'Daily reports'), Icons.description_rounded, const [Color(0xFF6FB7A8), Color(0xFF3E9483)], 'reports'),
      (_t(context, 'الحضور', 'Anwesenheit', 'Attendance'), Icons.how_to_reg_rounded, const [Color(0xFFE57E6E), Color(0xFFCF5443)], 'attendance'),
      (_t(context, 'ملاحظات وثناء', 'Lob & Notizen', 'Notes and praise'), Icons.star_rounded, const [Color(0xFF8CC47A), Color(0xFF5FA34C)], 'notes'),
      (_t(context, 'أحضِر معك', 'Bitte mitbringen', 'Please bring'), Icons.backpack_rounded, const [Color(0xFFF2B65A), Color(0xFFE5952B)], 'bring'),
      (_t(context, 'برنامج الأسبوع', 'Wochenplan', 'Week plan'), Icons.calendar_view_week_rounded, const [Color(0xFF8EB6F2), Color(0xFF5C8FE0)], 'plan'),
      (_t(context, 'دردشة الأهالي', 'Nachrichten der Eltern', 'Messages'), Icons.chat_rounded, const [Color(0xFF5FB3A6), Color(0xFF368F81)], 'messages'),
      (_t(context, 'المنشورات', 'Beiträge', 'Posts'), Icons.campaign_rounded, const [Color(0xFFB07CCB), Color(0xFF8E52B0)], 'posts'),
      (_t(context, 'المواد التعليمية', 'Materialien', 'Materials'), Icons.folder_rounded, const [Color(0xFFAEB4BC), Color(0xFF858D97)], 'files'),
    ];
    return CustomScrollView(slivers: [
      SliverToBoxAdapter(child: _greetingCard(context)),
      _tileGrid([
        for (final (label, icon, colors, id) in tiles) _TileCard(_Tile(label, icon, colors, () => const SizedBox()), onTap: () => goTo(id)),
      ]),
    ]);
  }
}

class _TileCard extends StatelessWidget {
  const _TileCard(this.tile, {required this.onTap});
  final _Tile tile;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(24),
          onTap: onTap,
          child: Ink(
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: tile.colors, begin: Alignment.topLeft, end: Alignment.bottomRight),
              borderRadius: BorderRadius.circular(24),
              boxShadow: [BoxShadow(color: tile.colors.last.withValues(alpha: 0.35), blurRadius: 14, offset: const Offset(0, 6))],
            ),
            child: Stack(children: [
              Center(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Icon(tile.icon, color: Colors.white, size: 44),
                    const SizedBox(height: 12),
                    Text(tile.label, textAlign: TextAlign.center, maxLines: 2, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16)),
                  ]),
                ),
              ),
              if (tile.badge > 0)
                PositionedDirectional(
                  top: 10,
                  end: 10,
                  child: Container(
                    constraints: const BoxConstraints(minWidth: 26),
                    height: 26,
                    padding: const EdgeInsets.symmetric(horizontal: 7),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(13)),
                    child: Text('${tile.badge}', style: TextStyle(fontWeight: FontWeight.w900, color: tile.colors.last)),
                  ),
                ),
            ]),
          ),
        ),
      );
}

Widget _attendancePill(BuildContext context, String status) => switch (status) {
      'present' => Pill(_t(context, 'حاضر اليوم', 'heute da', 'here today'), icon: Icons.check_circle_rounded, foreground: _good, background: const Color(0xFFE6F4EC)),
      'sick' => Pill(_t(context, 'مريض اليوم', 'heute krank', 'sick today'), icon: Icons.sick_outlined, foreground: _bad, background: const Color(0xFFFCE9E6)),
      'excused' => Pill(_t(context, 'غياب بعذر', 'entschuldigt', 'excused'), icon: Icons.event_busy_outlined, foreground: const Color(0xFF8A5200), background: const Color(0xFFFDF1DD)),
      _ => Pill(_t(context, 'غائب اليوم', 'heute nicht da', 'away today'), icon: Icons.cancel_outlined, foreground: _bad, background: const Color(0xFFFCE9E6)),
    };

String _statusText(BuildContext context, String status) => switch (status) {
      'present' => _t(context, 'حاضر', 'da', 'present'),
      'absent' => _t(context, 'غائب', 'nicht da', 'absent'),
      'sick' => _t(context, 'مريض', 'krank', 'sick'),
      'excused' => _t(context, 'بعذر', 'entschuldigt', 'excused'),
      _ => status,
    };

Color _statusColor(String status) => switch (status) {
      'present' => _good,
      'excused' => const Color(0xFFB7791F),
      _ => _bad,
    };

// ---- the child's data -----------------------------------------------------------------------------------------------------------
class _ProfilePage extends StatelessWidget {
  const _ProfilePage({required this.data});
  final Map<String, dynamic> data;
  @override
  Widget build(BuildContext context) {
    final guardians = _l(data['guardians']);
    String relation(String r) => switch (r) {
          'father' => _t(context, 'الأب', 'Vater', 'Father'),
          'mother' => _t(context, 'الأم', 'Mutter', 'Mother'),
          _ => _t(context, 'وليّ الأمر', 'Bezugsperson', 'Guardian'),
        };
    Widget line(String label, String value) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Row(children: [
            Expanded(child: Text(label, style: const TextStyle(fontWeight: FontWeight.w800, color: _muted))),
            Expanded(child: Text(value.isEmpty ? '—' : value, textAlign: TextAlign.end, style: const TextStyle(fontSize: 16))),
          ]),
        );
    return _page(
      context,
      _t(context, 'بيانات الطفل', 'Daten des Kindes', 'Child details'),
      ListView(padding: const EdgeInsets.all(20), children: [
        Center(child: AvatarInitials(_s(data['name']), size: 110)),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 6),
            child: Column(children: [
              line(_t(context, 'الاسم الكامل', 'Vollständiger Name', 'Full name'), _s(data['name'])),
              const Divider(height: 1),
              line(_t(context, 'المجموعة', 'Gruppe', 'Group'), _s(data['class_name'])),
              const Divider(height: 1),
              line(_t(context, 'تاريخ الميلاد', 'Geburtsdatum', 'Birth date'), _s(data['birth_date'])),
              const Divider(height: 1),
              line(_t(context, 'حالة التسجيل', 'Anmeldestatus', 'Registration'), data['status'] == 'active' ? _t(context, 'مسجّل', 'angemeldet', 'registered') : _t(context, 'غادر', 'abgemeldet', 'left')),
              for (final g in guardians) ...[const Divider(height: 1), line(relation(_s(g['relation'])), _s(g['name']))],
            ]),
          ),
        ),
      ]),
    );
  }
}

// ---- notes ----------------------------------------------------------------------------------------------------------------------
Widget _noteCard(BuildContext context, Map<String, dynamic> n, {VoidCallback? onDelete}) {
  final praise = n['kind'] == 'praise';
  final colors = praise ? const [Color(0xFF8CC47A), Color(0xFF5FA34C)] : const [Color(0xFF8EB6F2), Color(0xFF5C8FE0)];
  return Container(
    margin: const EdgeInsets.only(bottom: 10),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(gradient: LinearGradient(colors: colors), borderRadius: BorderRadius.circular(22), boxShadow: [BoxShadow(color: colors.last.withValues(alpha: 0.3), blurRadius: 12, offset: const Offset(0, 5))]),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(praise ? '⭐' : '📝', style: const TextStyle(fontSize: 26)),
      const SizedBox(width: 12),
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(_s(n['text']), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16, height: 1.4)),
          const SizedBox(height: 6),
          Text('${_s(n['author'])} · ${_when(n['created_at'])}', style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12.5)),
        ]),
      ),
      if (onDelete != null) IconButton(onPressed: onDelete, icon: const Icon(Icons.delete_outline, color: Colors.white)),
    ]),
  );
}

class _ParentNotesPage extends StatelessWidget {
  const _ParentNotesPage({required this.child});
  final Child child;
  @override
  Widget build(BuildContext context) => _page(
        context,
        _t(context, 'كل الملاحظات', 'Lob & Notizen', 'All notes'),
        _load(context, '/api/platform/parent/children/${child.id}/notes', (context, data, reload) {
          final notes = _l(data);
          if (notes.isEmpty) return _empty(context, Icons.star_outline_rounded, _t(context, 'لا توجد ملاحظات بعد.', 'Noch keine Notizen.', 'No notes yet.'));
          return ListView(padding: const EdgeInsets.all(16), children: [for (final n in notes) _noteCard(context, n)]);
        }),
      );
}

// ---- things to bring ------------------------------------------------------------------------------------------------------------
Widget _bringCard(BuildContext context, Map<String, dynamic> b, {VoidCallback? onDelete}) {
  final due = _s(b['due_on']);
  final past = due.isNotEmpty && due.compareTo(_day(DateTime.now())) < 0;
  final colors = past ? const [Color(0xFFC9CED6), Color(0xFFA9B0BA)] : const [Color(0xFFF2B65A), Color(0xFFE5952B)];
  final target = _s(b['child']).isNotEmpty ? _s(b['child']) : (_s(b['class_name']).isNotEmpty ? _s(b['class_name']) : _t(context, 'كل المجموعات', 'alle Gruppen', 'every group'));
  return Container(
    margin: const EdgeInsets.only(bottom: 12),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(gradient: LinearGradient(colors: colors), borderRadius: BorderRadius.circular(22), boxShadow: [BoxShadow(color: colors.last.withValues(alpha: 0.3), blurRadius: 12, offset: const Offset(0, 5))]),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        const Icon(Icons.event_rounded, color: Colors.white, size: 18),
        const SizedBox(width: 6),
        Expanded(child: Text('${_t(context, 'مطلوب يوم', 'Gebraucht am', 'Needed on')}: ${due.isEmpty ? '—' : due}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700))),
        if (onDelete != null) IconButton(onPressed: onDelete, icon: const Icon(Icons.delete_outline, color: Colors.white)),
      ]),
      const SizedBox(height: 6),
      Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Icon(Icons.backpack_rounded, color: Colors.white, size: 30),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(_s(b['title']), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 17)),
            if (_s(b['body']).isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text(_s(b['body']), style: const TextStyle(color: Colors.white, height: 1.4))),
            const SizedBox(height: 6),
            Text('$target · ${_s(b['author'])}', style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12.5)),
          ]),
        ),
      ]),
    ]),
  );
}

class _ParentBringPage extends StatelessWidget {
  const _ParentBringPage({required this.child});
  final Child child;
  @override
  Widget build(BuildContext context) => _page(
        context,
        _t(context, 'أحضِر معك', 'Bitte mitbringen', 'Please bring'),
        _load(context, '/api/platform/parent/children/${child.id}/bring', (context, data, reload) {
          final items = _l(data);
          if (items.isEmpty) return _empty(context, Icons.backpack_outlined, _t(context, 'لا يوجد ما يلزم إحضاره.', 'Nichts mitzubringen.', 'Nothing to bring.'));
          return ListView(padding: const EdgeInsets.all(16), children: [
            for (final b in items) ...[
              _dateHead(_s(b['created_at']).length >= 10 ? _s(b['created_at']).substring(0, 10) : ''),
              _bringCard(context, b),
            ],
          ]);
        }),
      );
}

// ---- the week plan --------------------------------------------------------------------------------------------------------------
Widget _planView(BuildContext context, List<Map<String, dynamic>> entries) {
  final days = _weekdays(context);
  final today = (DateTime.now().weekday % 7); // Sunday = 0
  return ListView(padding: const EdgeInsets.all(16), children: [
    for (var d = 0; d < 5; d++)
      Card(
        color: d == today ? const Color(0xFFEAF1F8) : null,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              Text(days[d], style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
              if (d == today) ...[const SizedBox(width: 8), Pill(_t(context, 'اليوم', 'Heute', 'Today'))],
            ]),
            const SizedBox(height: 8),
            if (!entries.any((e) => e['weekday'] == d)) Text(_t(context, 'لا شيء مخطط', 'Nichts geplant', 'Nothing planned'), style: const TextStyle(color: _muted)),
            for (final e in entries.where((e) => e['weekday'] == d))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(
                    width: 28,
                    height: 28,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(color: const Color(0xFF5C8FE0), borderRadius: BorderRadius.circular(9)),
                    child: Text(_s(e['position']), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(_s(e['title']), style: const TextStyle(fontWeight: FontWeight.w700)),
                      if (_s(e['detail']).isNotEmpty) Text(_s(e['detail']), style: const TextStyle(color: _muted, fontSize: 13)),
                    ]),
                  ),
                ]),
              ),
          ]),
        ),
      ),
  ]);
}

class _ParentPlanPage extends StatelessWidget {
  const _ParentPlanPage({required this.child});
  final Child child;
  @override
  Widget build(BuildContext context) => _page(
        context,
        _t(context, 'برنامج الأسبوع', 'Wochenplan', 'Week plan'),
        _load(context, '/api/platform/parent/children/${child.id}/plan', (context, data, reload) {
          final entries = _l(_m(data)['entries']);
          if (entries.isEmpty) return _empty(context, Icons.calendar_view_week_outlined, _t(context, 'لم يُنشر برنامج الأسبوع بعد.', 'Noch kein Wochenplan.', 'No week plan yet.'));
          return _planView(context, entries);
        }),
      );
}

// ---- attendance -----------------------------------------------------------------------------------------------------------------
class _ParentAttendancePage extends StatefulWidget {
  const _ParentAttendancePage({required this.child});
  final Child child;
  @override
  State<_ParentAttendancePage> createState() => _ParentAttendancePageState();
}

class _ParentAttendancePageState extends State<_ParentAttendancePage> {
  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  int _round = 0;

  Future<void> _report() async {
    var day = DateTime.now();
    var status = 'sick';
    final note = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => StatefulBuilder(
        builder: (context, set) => AlertDialog(
          title: Text(_t(context, 'الإبلاغ عن غياب', 'Abwesenheit melden', 'Report an absence')),
          content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            SegmentedButton<String>(
              segments: [
                ButtonSegment(value: 'sick', label: Text(_t(context, 'مريض', 'krank', 'sick')), icon: const Icon(Icons.sick_outlined)),
                ButtonSegment(value: 'absent', label: Text(_t(context, 'غائب', 'nicht da', 'away')), icon: const Icon(Icons.event_busy_outlined)),
              ],
              selected: {status},
              onSelectionChanged: (v) => set(() => status = v.first),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              icon: const Icon(Icons.calendar_today_outlined),
              label: Text(_day(day), textDirection: TextDirection.ltr),
              onPressed: () async {
                final d = await showDatePicker(context: context, initialDate: day, firstDate: DateTime.now(), lastDate: DateTime.now().add(const Duration(days: 60)));
                if (d != null) set(() => day = d);
              },
            ),
            const SizedBox(height: 8),
            TextField(controller: note, maxLength: 300, decoration: InputDecoration(labelText: _t(context, 'ملاحظة (اختياري)', 'Notiz (optional)', 'Note (optional)'))),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: Text(S.of(context).get('cancel'))),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(_t(context, 'إرسال', 'Senden', 'Send'))),
          ],
        ),
      ),
    );
    if (ok != true || !mounted) return;
    final api = SessionScope.of(context).api;
    if (await _run(context, () => api.post('/api/platform/parent/children/${widget.child.id}/absence', {'day': _day(day), 'status': status, 'note': note.text.trim()}),
        done: _t(context, 'وصل الإبلاغ إلى الروضة.', 'Die Kita wurde benachrichtigt.', 'The kindergarten was told.'))) {
      setState(() => _round++);
    }
  }

  @override
  Widget build(BuildContext context) {
    final key = '${_month.year}-${_month.month.toString().padLeft(2, '0')}';
    return _page(
      context,
      _t(context, 'الحضور', 'Anwesenheit', 'Attendance'),
      Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
          child: Row(children: [
            IconButton(onPressed: () => setState(() => _month = DateTime(_month.year, _month.month - 1)), icon: const Icon(Icons.chevron_left_rounded)),
            Expanded(child: Text(key, textAlign: TextAlign.center, textDirection: TextDirection.ltr, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800))),
            IconButton(onPressed: () => setState(() => _month = DateTime(_month.year, _month.month + 1)), icon: const Icon(Icons.chevron_right_rounded)),
          ]),
        ),
        Expanded(
          child: _load(context, '/api/platform/parent/children/${widget.child.id}/attendance', key: ValueKey('$key$_round'), query: {'month': key}, (context, data, reload) {
            final d = _m(data);
            final counts = _m(d['counts']);
            final days = _l(d['days']);
            return ListView(padding: const EdgeInsets.all(16), children: [
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final st in const ['present', 'absent', 'sick', 'excused'])
                  Chip(
                    avatar: CircleAvatar(backgroundColor: _statusColor(st), radius: 6),
                    label: Text('${_statusText(context, st)}: ${_s(counts[st] ?? 0)}'),
                  ),
              ]),
              const SizedBox(height: 10),
              if (days.isEmpty) Padding(padding: const EdgeInsets.all(20), child: Text(_t(context, 'لا توجد تسجيلات في هذا الشهر.', 'Keine Einträge in diesem Monat.', 'No entries this month.'), textAlign: TextAlign.center, style: const TextStyle(color: _muted))),
              for (final r in days.reversed)
                Card(
                  child: ListTile(
                    leading: CircleAvatar(backgroundColor: _statusColor(_s(r['status'])).withValues(alpha: 0.15), child: Icon(r['status'] == 'present' ? Icons.check_rounded : Icons.close_rounded, color: _statusColor(_s(r['status'])))),
                    title: Text('${_weekdayName(context, _s(r['day']))} · ${_s(r['day'])}'),
                    subtitle: Text([_statusText(context, _s(r['status'])), if (r['by_parent'] == true) _t(context, 'أبلغتم عنه', 'von euch gemeldet', 'reported by you'), if (_s(r['note']).isNotEmpty) _s(r['note'])].join(' · ')),
                  ),
                ),
            ]);
          }),
        ),
      ]),
      fab: FloatingActionButton.extended(onPressed: _report, icon: const Icon(Icons.sick_outlined), label: Text(_t(context, 'الإبلاغ عن غياب', 'Abwesenheit melden', 'Report an absence'))),
    );
  }
}

String _weekdayName(BuildContext context, String iso) {
  final d = DateTime.tryParse(iso);
  if (d == null) return '';
  final i = d.weekday % 7;
  if (i > 4) return i == 5 ? _t(context, 'الجمعة', 'Freitag', 'Friday') : _t(context, 'السبت', 'Samstag', 'Saturday');
  return _weekdays(context)[i];
}

// ---- fees -----------------------------------------------------------------------------------------------------------------------
class _ParentFeesPage extends StatelessWidget {
  const _ParentFeesPage({required this.child});
  final Child child;
  @override
  Widget build(BuildContext context) => _page(
        context,
        _t(context, 'الرسوم', 'Gebühren', 'Fees'),
        _load(context, '/api/platform/parent/children/${child.id}/fees', (context, data, reload) {
          final invoices = _l(_m(data)['invoices']);
          if (invoices.isEmpty) return _empty(context, Icons.receipt_long_outlined, _t(context, 'لا توجد فواتير.', 'Keine Rechnungen.', 'No invoices.'));
          String money(Map<String, dynamic> pair, String cur) => '${_s(pair[cur == 'USD' ? 'usd' : 'syp'])} $cur';
          return ListView(padding: const EdgeInsets.all(16), children: [
            for (final i in invoices)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    Row(children: [
                      Expanded(child: Text('${_s(i['number'])} · ${_s(i['issued_on'])}', textDirection: TextDirection.ltr, textAlign: TextAlign.start, style: const TextStyle(fontWeight: FontWeight.w800))),
                      switch (_s(i['status'])) {
                        'paid' => Pill(_t(context, 'مدفوعة', 'bezahlt', 'paid'), foreground: _good, background: const Color(0xFFE6F4EC)),
                        'partial' => Pill(_t(context, 'مدفوعة جزئياً', 'teilweise bezahlt', 'partly paid'), foreground: const Color(0xFF8A5200), background: const Color(0xFFFDF1DD)),
                        _ => Pill(_t(context, 'غير مدفوعة', 'offen', 'unpaid'), foreground: _bad, background: const Color(0xFFFCE9E6)),
                      },
                    ]),
                    if (_s(i['description']).isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text(_s(i['description']), style: const TextStyle(color: _muted))),
                    const Divider(height: 22),
                    for (final item in _l(i['items']))
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 3),
                        child: Row(children: [Expanded(child: Text(_s(item['description']))), Text(money(item, _s(i['currency'])), textDirection: TextDirection.ltr)]),
                      ),
                    const Divider(height: 22),
                    _feeLine(_t(context, 'المجموع', 'Summe', 'Total'), money(_m(i['total']), _s(i['currency'])), bold: true),
                    _feeLine(_t(context, 'المدفوع', 'Bezahlt', 'Paid'), money(_m(i['paid']), _s(i['currency']))),
                    _feeLine(_t(context, 'المتبقي', 'Offen', 'Open'), money(_m(i['open']), _s(i['currency'])), color: i['status'] == 'paid' ? null : _bad, bold: true),
                    if (_l(i['payments']).isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Text(_t(context, 'الدفعات', 'Zahlungen', 'Payments'), style: const TextStyle(fontWeight: FontWeight.w700, color: _muted)),
                      for (final p in _l(i['payments'])) _feeLine(_s(p['booked_on']), '${_s(p['amount'])} ${_s(p['currency'])}'),
                    ],
                  ]),
                ),
              ),
          ]);
        }),
      );
}

Widget _feeLine(String label, String value, {bool bold = false, Color? color}) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(children: [
        Expanded(child: Text(label, style: TextStyle(fontWeight: bold ? FontWeight.w800 : FontWeight.w500))),
        Text(value, textDirection: TextDirection.ltr, style: TextStyle(fontWeight: bold ? FontWeight.w800 : FontWeight.w500, color: color)),
      ]),
    );

// =================================================================================================================================
// chats, like WhatsApp: one conversation = one child, one parent account and one teacher (or the kindergarten's management).
// The management sees every conversation and may write in each; the parents are told so at the top of the chat.
// =================================================================================================================================
const _waHead = Color(0xFF008069);
const _waGreen = Color(0xFF00A884);
const _waBack = Color(0xFFEFE7DE);
const _waMine = Color(0xFFD9FDD3);
const _waTick = Color(0xFF53BDEB);
const _waGrey = Color(0xFF667781);
const _avatarColors = [Color(0xFF4F8EDC), Color(0xFF3E9483), Color(0xFFCF5443), Color(0xFF8E52B0), Color(0xFFE5952B), Color(0xFF5FA34C), Color(0xFF368F81), Color(0xFFB0527A)];

Color _colorOf(String name) => _avatarColors[name.codeUnits.fold<int>(0, (a, b) => a + b) % _avatarColors.length];

/// The local time of a server timestamp.
DateTime? _local(Object? iso) {
  final d = DateTime.tryParse(_s(iso));
  if (d == null) return null;
  return d.isUtc ? d.toLocal() : DateTime.utc(d.year, d.month, d.day, d.hour, d.minute, d.second).toLocal();
}

String _clock(DateTime d) => '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';

/// "Today", "Yesterday", the weekday in the last week, else the date.
String _dayLabel(BuildContext context, DateTime d) {
  final now = DateTime.now();
  final diff = DateTime(now.year, now.month, now.day).difference(DateTime(d.year, d.month, d.day)).inDays;
  if (diff == 0) return _t(context, 'اليوم', 'Heute', 'Today');
  if (diff == 1) return _t(context, 'أمس', 'Gestern', 'Yesterday');
  if (diff > 1 && diff < 7) return _weekdayName(context, _day(d));
  return _day(d);
}

/// The time shown in a list of chats: the clock today, else the day.
String _listTime(BuildContext context, Object? iso) {
  final d = _local(iso);
  if (d == null) return '';
  final now = DateTime.now();
  return d.year == now.year && d.month == now.month && d.day == now.day ? _clock(d) : _dayLabel(context, d);
}

String _roleWord(BuildContext context, String role) => switch (role) {
      'teacher' => _t(context, 'معلمة', 'Lehrerin', 'Teacher'),
      'manager' || 'admin' || 'office' => _t(context, 'إدارة الروضة', 'Kitaleitung', 'Management'),
      'parent' => _t(context, 'وليّ الأمر', 'Eltern', 'Parent'),
      _ => '',
    };

Widget _chatAvatar(String name, {IconData? icon, double size = 50}) => CircleAvatar(
      radius: size / 2,
      backgroundColor: icon != null ? _waHead : _colorOf(name),
      child: icon != null
          ? Icon(icon, color: Colors.white, size: size * 0.5)
          : Text(name.isEmpty ? '?' : name.characters.first.toUpperCase(), style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: size * 0.4)),
    );

Widget _ticks(Map<String, dynamic> m, {double size = 16}) => m['pending'] == true
    ? Icon(Icons.schedule_rounded, size: size - 2, color: _waGrey)
    : Icon(m['read'] == true ? Icons.done_all_rounded : Icons.done_rounded, size: size, color: m['read'] == true ? _waTick : _waGrey);

/// One line in a list of chats: avatar, name, time, the last message (with ticks when it was ours) and the unread count.
Widget _chatRow(
  BuildContext context, {
  required String title,
  String tag = '',
  IconData? icon,
  Map<String, dynamic>? last,
  required bool lastIsOurs,
  int unread = 0,
  String empty = '',
  required VoidCallback onTap,
}) {
  final hasNew = unread > 0;
  return InkWell(
    onTap: onTap,
    child: Padding(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
      child: Row(children: [
        _chatAvatar(title, icon: icon),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 16.5, fontWeight: FontWeight.w700))),
              if (last != null) Text(_listTime(context, last['created_at']), style: TextStyle(fontSize: 12, color: hasNew ? _waGreen : _waGrey, fontWeight: hasNew ? FontWeight.w800 : FontWeight.w500)),
            ]),
            if (tag.isNotEmpty) Text(tag, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5, color: _waHead, fontWeight: FontWeight.w700)),
            const SizedBox(height: 3),
            Row(children: [
              if (last != null && lastIsOurs) ...[_ticks(last), const SizedBox(width: 3)],
              Expanded(
                child: Text(last == null ? empty : _s(last['body']).replaceAll('\n', ' '),
                    maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(color: hasNew ? const Color(0xFF111B21) : _waGrey, fontWeight: hasNew ? FontWeight.w600 : FontWeight.w400)),
              ),
              if (hasNew)
                Container(
                  margin: const EdgeInsetsDirectional.only(start: 6),
                  constraints: const BoxConstraints(minWidth: 22),
                  height: 22,
                  padding: const EdgeInsets.symmetric(horizontal: 6),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(color: _waGreen, borderRadius: BorderRadius.circular(11)),
                  child: Text('$unread', style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w800)),
                ),
            ]),
          ]),
        ),
      ]),
    ),
  );
}

/// A search field on top of a list of chats.
Widget _chatSearch(BuildContext context, ValueChanged<String> onChanged) => Padding(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
      child: TextField(
        onChanged: onChanged,
        decoration: InputDecoration(
          hintText: _t(context, 'بحث...', 'Suchen...', 'Search...'),
          prefixIcon: const Icon(Icons.search_rounded),
          isDense: true,
          filled: true,
          fillColor: const Color(0xFFF0F2F5),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: const BorderSide(color: _waGreen)),
        ),
      ),
    );

// ---- one conversation ---------------------------------------------------------------------------------------------------------
class ChatPage extends StatefulWidget {
  const ChatPage._({
    required this.title,
    required this.subtitle,
    required this.notice,
    this.icon,
    required this.listPath,
    required this.query,
    required this.send,
    required this.staffSide,
  });

  /// A parent writing to one teacher ([to] = her account id) or to the management ([to] = "office") about one child.
  factory ChatPage.parent({required Child child, required String to, required String title, required String subtitle, required String notice, IconData? icon}) => ChatPage._(
        title: title,
        subtitle: subtitle,
        notice: notice,
        icon: icon,
        listPath: '/api/platform/parent/children/${child.id}/messages',
        query: {'to': to},
        send: (api, body) => api.post('/api/platform/parent/children/${child.id}/messages', {'body': body, 'to': to}),
        staffSide: false,
      );

  /// The kindergarten writing to one parent about one child. [to]: empty = the writer's own conversation, "office" = the
  /// management's, else a teacher's account id (the management looking into her conversation).
  factory ChatPage.staff({required String childId, required String parentId, required String to, required String title, required String subtitle, required String notice}) => ChatPage._(
        title: title,
        subtitle: subtitle,
        notice: notice,
        listPath: '/api/platform/staff/conversations/$childId/$parentId',
        query: {'to': to},
        send: (api, body) => api.post('/api/platform/staff/messages', {'child_id': childId, 'parent_id': parentId, 'body': body, 'to': to}),
        staffSide: true,
      );

  final String title;
  final String subtitle;
  final String notice;
  final IconData? icon;
  final String listPath;
  final Map<String, String> query;
  final Future<dynamic> Function(ApiClient api, String body) send;

  /// true: the kindergarten's messages are "ours" (right side, green), false: the parent's.
  final bool staffSide;

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _text = TextEditingController();
  final _focus = FocusNode();
  List<Map<String, dynamic>>? _messages;
  final List<Map<String, dynamic>> _pending = [];
  Object? _error;
  Timer? _poll;
  bool _hasText = false;

  @override
  void initState() {
    super.initState();
    _text.addListener(() {
      final has = _text.text.trim().isNotEmpty;
      if (has != _hasText) setState(() => _hasText = has);
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _reload());
    // new messages come in by themselves while the chat is open
    _poll = Timer.periodic(const Duration(seconds: 6), (_) => _reload());
  }

  @override
  void dispose() {
    _poll?.cancel();
    _text.dispose();
    _focus.dispose();
    super.dispose();
  }

  bool _ours(Map<String, dynamic> m) => widget.staffSide ? m['from_parent'] != true : m['from_parent'] == true;

  Future<void> _reload() async {
    try {
      final list = _l(await SessionScope.of(context).api.get(widget.listPath, query: widget.query));
      if (mounted) {
        setState(() {
          _messages = list;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted && _messages == null) setState(() => _error = e);
    }
  }

  Future<void> _send() async {
    final body = _text.text.trim();
    if (body.isEmpty) return;
    // shown at once with a clock, replaced by the saved message
    final draft = <String, dynamic>{
      'body': body,
      'from_parent': !widget.staffSide,
      'mine': true,
      'pending': true,
      'created_at': DateTime.now().toUtc().toIso8601String(),
    };
    setState(() => _pending.add(draft));
    _text.clear();
    _focus.requestFocus();
    try {
      await widget.send(SessionScope.of(context).api, body);
      await _reload();
    } on ApiException catch (e) {
      if (mounted) {
        toast(context, problemText(context, e));
        if (_text.text.isEmpty) _text.text = body;
      }
    }
    if (mounted) setState(() => _pending.remove(draft));
  }

  Widget _dateChip(String text) => Center(
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 8),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
          decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.92), borderRadius: BorderRadius.circular(8), boxShadow: const [BoxShadow(color: Color(0x14000000), blurRadius: 2, offset: Offset(0, 1))]),
          child: Text(text, style: const TextStyle(fontSize: 12.5, color: Color(0xFF54656F), fontWeight: FontWeight.w600)),
        ),
      );

  Widget _bubble(BuildContext context, Map<String, dynamic> m, {required bool firstOfGroup}) {
    final ours = _ours(m);
    final d = _local(m['created_at']);
    // the name of who wrote it: on the parents' side for every kindergarten message; on the kindergarten's side when it was
    // written by someone else of the kindergarten (the management in a teacher's chat, the teacher seen by the management)
    final showName = firstOfGroup && (widget.staffSide ? (ours && m['mine'] != true && m['pending'] != true) : !ours);
    final name = _s(m['sender']);
    final role = _roleWord(context, _s(m['sender_role']));
    final width = MediaQuery.sizeOf(context).width;
    final radius = Radius.circular(firstOfGroup ? 2 : 12);
    return Align(
      alignment: ours ? AlignmentDirectional.centerEnd : AlignmentDirectional.centerStart,
      child: GestureDetector(
        onLongPress: () async {
          await Clipboard.setData(ClipboardData(text: _s(m['body'])));
          if (context.mounted) toast(context, _t(context, 'تم نسخ الرسالة.', 'Nachricht kopiert.', 'Message copied.'));
        },
        child: Container(
          constraints: BoxConstraints(maxWidth: (width * 0.78).clamp(220, 560)),
          margin: EdgeInsets.only(top: firstOfGroup ? 6 : 2),
          padding: const EdgeInsets.fromLTRB(10, 6, 10, 5),
          decoration: BoxDecoration(
            color: ours ? _waMine : Colors.white,
            borderRadius: BorderRadiusDirectional.only(
              topStart: ours ? const Radius.circular(12) : radius,
              topEnd: ours ? radius : const Radius.circular(12),
              bottomStart: const Radius.circular(12),
              bottomEnd: const Radius.circular(12),
            ),
            boxShadow: const [BoxShadow(color: Color(0x1A000000), blurRadius: 1.5, offset: Offset(0, 1))],
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            if (showName && name.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 2),
                child: Text(role.isEmpty ? name : '$name · $role', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: _colorOf(name))),
              ),
            Wrap(
              alignment: WrapAlignment.end,
              crossAxisAlignment: WrapCrossAlignment.end,
              spacing: 10,
              children: [
                Text(_s(m['body']), style: const TextStyle(fontSize: 15.5, height: 1.35, color: Color(0xFF111B21))),
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Text(d == null ? '' : _clock(d), textDirection: TextDirection.ltr, style: const TextStyle(fontSize: 11.5, color: _waGrey)),
                    if (ours) ...[const SizedBox(width: 3), _ticks(m)],
                  ]),
                ),
              ],
            ),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final messages = [...?_messages, ..._pending];
    // the conversation from the top, with a date chip whenever the day changes
    final items = <Widget>[
      Center(
        child: Container(
          margin: const EdgeInsets.fromLTRB(24, 8, 24, 6),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(color: const Color(0xFFFFEECD), borderRadius: BorderRadius.circular(8)),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.lock_outline_rounded, size: 15, color: Color(0xFF54656F)),
            const SizedBox(width: 6),
            Flexible(child: Text(widget.notice, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12.5, color: Color(0xFF54656F)))),
          ]),
        ),
      ),
    ];
    String? lastDay;
    Map<String, dynamic>? previous;
    for (final m in messages) {
      final d = _local(m['created_at']);
      final day = d == null ? '' : _day(d);
      if (day != lastDay) {
        items.add(_dateChip(d == null ? '' : _dayLabel(context, d)));
        lastDay = day;
        previous = null;
      }
      final first = previous == null || _ours(previous) != _ours(m) || _s(previous['sender']) != _s(m['sender']);
      items.add(_bubble(context, m, firstOfGroup: first));
      previous = m;
    }
    return Scaffold(
      backgroundColor: _waBack,
      appBar: AppBar(
        backgroundColor: _waHead,
        foregroundColor: Colors.white,
        titleSpacing: 0,
        title: Row(children: [
          _chatAvatar(widget.title, icon: widget.icon, size: 40),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(widget.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w700)),
              if (widget.subtitle.isNotEmpty) Text(widget.subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white70, fontSize: 12.5)),
            ]),
          ),
        ]),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 900),
          child: Column(children: [
            Expanded(
              child: _messages == null && _error != null
                  ? StateView.fromError(context, _error, onRetry: _reload)
                  : _messages == null
                      ? const Center(child: CircularProgressIndicator())
                      : ListView(
                          reverse: true,
                          padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
                          children: [
                            if (messages.isEmpty) _dateChip(_t(context, 'لا توجد رسائل بعد. اكتب أول رسالة 👋', 'Noch keine Nachrichten. Schreib die erste 👋', 'No messages yet. Say hello 👋')),
                            ...items.reversed,
                          ],
                        ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
                child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  Expanded(
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(26), boxShadow: const [BoxShadow(color: Color(0x14000000), blurRadius: 2, offset: Offset(0, 1))]),
                      child: TextField(
                        controller: _text,
                        focusNode: _focus,
                        minLines: 1,
                        maxLines: 5,
                        maxLength: 2000,
                        textInputAction: TextInputAction.send,
                        onSubmitted: (_) => _send(),
                        decoration: InputDecoration(
                          counterText: '',
                          hintText: _t(context, 'اكتب رسالة', 'Nachricht', 'Message'),
                          filled: false,
                          border: InputBorder.none,
                          enabledBorder: InputBorder.none,
                          focusedBorder: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(vertical: 13),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  Material(
                    color: _hasText ? _waGreen : const Color(0xFF8FCFC0),
                    shape: const CircleBorder(),
                    child: InkWell(
                      customBorder: const CircleBorder(),
                      onTap: _hasText ? _send : null,
                      child: const SizedBox(width: 50, height: 50, child: Icon(Icons.send_rounded, color: Colors.white)),
                    ),
                  ),
                ]),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

// ---- the parents: whom to write to ----------------------------------------------------------------------------------------------
class ParentChatsPage extends StatefulWidget {
  const ParentChatsPage({super.key, required this.child});
  final Child child;
  @override
  State<ParentChatsPage> createState() => _ParentChatsPageState();
}

class _ParentChatsPageState extends State<ParentChatsPage> {
  int _round = 0;
  String _search = '';

  @override
  Widget build(BuildContext context) {
    final c = widget.child;
    final office = _t(context, 'إدارة الروضة', 'Kitaleitung', 'Management');
    return Scaffold(
      appBar: AppBar(
        backgroundColor: _waHead,
        foregroundColor: Colors.white,
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(_t(context, 'الدردشة', 'Chats', 'Chats'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
          Text(c.name, style: const TextStyle(color: Colors.white70, fontSize: 12.5)),
        ]),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: _load(context, '/api/platform/parent/children/${c.id}/contacts', key: ValueKey(_round), (context, data, reload) {
            final rows = _l(data).where((r) {
              final q = _search.trim().toLowerCase();
              if (q.isEmpty) return true;
              final name = _s(r['role']) == 'office' ? office : _s(r['name']);
              return name.toLowerCase().contains(q) || _s(_m(r['last'])['body']).toLowerCase().contains(q);
            }).toList();
            return RefreshIndicator(
              onRefresh: reload,
              child: ListView(children: [
                _chatSearch(context, (v) => setState(() => _search = v)),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
                  child: Text(_t(context, 'اكتب لمعلمة طفلك أو لإدارة الروضة. الإدارة تستطيع الاطلاع على كل المحادثات.', 'Schreib einer Lehrerin oder der Kitaleitung. Die Kitaleitung kann alle Gespräche sehen.', 'Write to a teacher or to the management. The management can see every chat.'),
                      style: const TextStyle(color: _waGrey, fontSize: 12.5)),
                ),
                for (final r in rows) ...[
                  _chatRow(
                    context,
                    title: _s(r['role']) == 'office' ? office : _s(r['name']),
                    tag: _s(r['role']) == 'office' ? '' : _roleWord(context, 'teacher') + (r['gone'] == true ? ' · ${_t(context, 'لم تعد في الروضة', 'nicht mehr da', 'has left')}' : ''),
                    icon: _s(r['role']) == 'office' ? Icons.apartment_rounded : null,
                    last: r['last'] == null ? null : _m(r['last']),
                    lastIsOurs: _m(r['last'])['from_parent'] == true,
                    unread: (r['unread'] as num? ?? 0).toInt(),
                    empty: _t(context, 'اضغط لبدء المحادثة', 'Tippen, um zu schreiben', 'Tap to start a chat'),
                    onTap: () async {
                      final isOffice = _s(r['role']) == 'office';
                      final title = isOffice ? office : _s(r['name']);
                      await Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => ChatPage.parent(
                            child: c,
                            to: _s(r['with']),
                            title: title,
                            subtitle: '${isOffice ? '' : '${_roleWord(context, 'teacher')} · '}${c.name}',
                            icon: isOffice ? Icons.apartment_rounded : null,
                            notice: isOffice
                                ? _t(context, 'محادثتك مع إدارة الروضة حول ${c.name}.', 'Dein Gespräch mit der Kitaleitung über ${c.name}.', 'Your chat with the management about ${c.name}.')
                                : _t(context, 'محادثتك مع $title حول ${c.name}. إدارة الروضة تستطيع الاطلاع عليها.', 'Dein Gespräch mit $title über ${c.name}. Die Kitaleitung kann es sehen.',
                                    'Your chat with $title about ${c.name}. The management can see it.'),
                          ),
                        ),
                      );
                      if (mounted) setState(() => _round++);
                    },
                  ),
                  const Divider(height: 1, indent: 76),
                ],
              ]),
            );
          }),
        ),
      ),
    );
  }
}

// =================================================================================================================================
// the kindergarten
// =================================================================================================================================

/// The children with their groups and parent accounts (for every staff page).
Future<(List<Map<String, dynamic>>, List<String>)> _staffChildren(ApiClient api) async {
  final d = _m(await api.get('/api/platform/staff/children'));
  return (_l(d['children']), [for (final g in (d['groups'] as List? ?? const [])) '$g']);
}

/// One entry for management and admin: the five everyday pages as tiles.
class StaffEverydayHub extends StatelessWidget {
  const StaffEverydayHub({super.key});
  @override
  Widget build(BuildContext context) {
    final tiles = [
      _Tile(_t(context, 'الحضور', 'Anwesenheit', 'Attendance'), Icons.how_to_reg_rounded, const [Color(0xFFE57E6E), Color(0xFFCF5443)], () => _page(context, _t(context, 'الحضور', 'Anwesenheit', 'Attendance'), const StaffAttendancePage())),
      _Tile(_t(context, 'ملاحظات', 'Lob & Notizen', 'Notes'), Icons.star_rounded, const [Color(0xFF8CC47A), Color(0xFF5FA34C)], () => _page(context, _t(context, 'ملاحظات', 'Lob & Notizen', 'Notes'), const StaffNotesPage())),
      _Tile(_t(context, 'أحضِر معك', 'Bitte mitbringen', 'Please bring'), Icons.backpack_rounded, const [Color(0xFFF2B65A), Color(0xFFE5952B)], () => _page(context, _t(context, 'أحضِر معك', 'Bitte mitbringen', 'Please bring'), const StaffBringPage())),
      _Tile(_t(context, 'برنامج الأسبوع', 'Wochenplan', 'Week plan'), Icons.calendar_view_week_rounded, const [Color(0xFF8EB6F2), Color(0xFF5C8FE0)], () => _page(context, _t(context, 'برنامج الأسبوع', 'Wochenplan', 'Week plan'), const StaffPlanPage())),
      _Tile(_t(context, 'دردشة الأهالي', 'Nachrichten der Eltern', 'Messages'), Icons.chat_rounded, const [Color(0xFF5FB3A6), Color(0xFF368F81)], () => _page(context, _t(context, 'دردشة الأهالي', 'Nachrichten der Eltern', 'Messages'), const StaffMessagesPage())),
    ];
    return LayoutBuilder(builder: (context, c) {
      final cols = (c.maxWidth / 220).floor().clamp(2, 5);
      return GridView.count(
        padding: const EdgeInsets.all(16),
        crossAxisCount: cols,
        mainAxisSpacing: 14,
        crossAxisSpacing: 14,
        childAspectRatio: 1.05,
        children: [for (final t in tiles) _TileCard(t, onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => t.open())))],
      );
    });
  }
}

// ---- attendance -----------------------------------------------------------------------------------------------------------------
class StaffAttendancePage extends StatefulWidget {
  const StaffAttendancePage({super.key});
  @override
  State<StaffAttendancePage> createState() => _StaffAttendancePageState();
}

class _StaffAttendancePageState extends State<StaffAttendancePage> {
  DateTime _dayValue = DateTime.now();
  String _group = '*';
  List<String> _groups = [];
  List<Map<String, dynamic>>? _rows;
  final Map<String, String> _changes = {};
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        final (_, groups) = await _staffChildren(SessionScope.of(context).api);
        if (mounted) setState(() => _groups = groups);
      } catch (_) {}
      await _reload();
    });
  }

  Future<void> _reload() async {
    setState(() => _rows = null);
    try {
      final d = _m(await SessionScope.of(context).api.get('/api/platform/staff/attendance', query: {'day': _day(_dayValue), 'class_name': _group}));
      if (mounted) {
        setState(() {
          _rows = _l(d['rows']);
          _changes.clear();
        });
      }
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    }
  }

  Future<void> _save() async {
    if (_changes.isEmpty) return;
    setState(() => _busy = true);
    final api = SessionScope.of(context).api;
    final ok = await _run(context, () => api.put('/api/platform/staff/attendance', {
          'day': _day(_dayValue),
          'entries': [for (final e in _changes.entries) {'child_id': e.key, 'status': e.value}],
        }), done: _t(context, 'حُفظ الحضور.', 'Anwesenheit gespeichert.', 'Attendance saved.'));
    if (mounted) setState(() => _busy = false);
    if (ok) await _reload();
  }

  void _allPresent() {
    for (final r in _rows ?? const <Map<String, dynamic>>[]) {
      if (r['status'] == null) _changes[_s(r['child_id'])] = 'present';
    }
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final rows = _rows;
    return Scaffold(
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
          child: Wrap(spacing: 10, runSpacing: 10, crossAxisAlignment: WrapCrossAlignment.center, children: [
            OutlinedButton.icon(
              icon: const Icon(Icons.calendar_today_outlined, size: 18),
              label: Text('${_weekdayName(context, _day(_dayValue))} · ${_day(_dayValue)}'),
              onPressed: () async {
                final d = await showDatePicker(context: context, initialDate: _dayValue, firstDate: DateTime(2024), lastDate: DateTime.now());
                if (d != null) {
                  setState(() => _dayValue = d);
                  await _reload();
                }
              },
            ),
            SizedBox(
              width: 200,
              child: DropdownButtonFormField<String>(
                initialValue: _group,
                isDense: true,
                decoration: InputDecoration(labelText: _t(context, 'المجموعة', 'Gruppe', 'Group')),
                items: [
                  DropdownMenuItem(value: '*', child: Text(_t(context, 'كل المجموعات', 'Alle Gruppen', 'Every group'))),
                  for (final g in _groups) DropdownMenuItem(value: g, child: Text(g.isEmpty ? _t(context, 'بلا مجموعة', 'ohne Gruppe', 'no group') : g)),
                ],
                onChanged: (v) async {
                  setState(() => _group = v ?? '*');
                  await _reload();
                },
              ),
            ),
            TextButton.icon(onPressed: rows == null ? null : _allPresent, icon: const Icon(Icons.done_all_rounded), label: Text(_t(context, 'الباقون حاضرون', 'Rest als da', 'Others present'))),
          ]),
        ),
        Expanded(
          child: rows == null
              ? const Center(child: CircularProgressIndicator())
              : rows.isEmpty
                  ? StateView(icon: Icons.child_care_outlined, title: _t(context, 'لا يوجد أطفال.', 'Keine Kinder.', 'No children.'))
                  : ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 90), children: [
                      for (final r in rows)
                        () {
                          final id = _s(r['child_id']);
                          final current = _changes[id] ?? _s(r['status']);
                          return Card(
                            child: Padding(
                              padding: const EdgeInsets.all(12),
                              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                                Row(children: [
                                  AvatarInitials(_s(r['name']), size: 36),
                                  const SizedBox(width: 10),
                                  Expanded(child: Text(_s(r['name']), style: const TextStyle(fontWeight: FontWeight.w700))),
                                  if (_s(r['class_name']).isNotEmpty) Pill(_s(r['class_name'])),
                                ]),
                                if (r['by_parent'] == true)
                                  Padding(
                                    padding: const EdgeInsets.only(top: 6),
                                    child: Text('${_t(context, 'أبلغ الأهل', 'Eltern meldeten', 'Parents reported')}: ${_statusText(context, _s(r['status']))}${_s(r['note']).isEmpty ? '' : ' · ${_s(r['note'])}'}',
                                        style: const TextStyle(color: _bad, fontSize: 12.5)),
                                  ),
                                const SizedBox(height: 8),
                                Wrap(spacing: 6, runSpacing: 6, children: [
                                  for (final st in const ['present', 'absent', 'sick', 'excused'])
                                    ChoiceChip(
                                      label: Text(_statusText(context, st)),
                                      selected: current == st,
                                      selectedColor: _statusColor(st).withValues(alpha: 0.2),
                                      onSelected: (on) => setState(() => _changes[id] = on ? st : ''),
                                    ),
                                ]),
                              ]),
                            ),
                          );
                        }(),
                    ]),
        ),
      ]),
      floatingActionButton: _changes.isEmpty
          ? null
          : FloatingActionButton.extended(
              onPressed: _busy ? null : _save,
              icon: const Icon(Icons.save_rounded),
              label: Text('${_t(context, 'حفظ', 'Speichern', 'Save')} (${_changes.length})'),
            ),
    );
  }
}

// ---- notes ----------------------------------------------------------------------------------------------------------------------
class StaffNotesPage extends StatefulWidget {
  const StaffNotesPage({super.key});
  @override
  State<StaffNotesPage> createState() => _StaffNotesPageState();
}

class _StaffNotesPageState extends State<StaffNotesPage> {
  String _q = '';
  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return Loader<(List<Map<String, dynamic>>, List<String>)>(
      load: () async => Cached(await _staffChildren(api)),
      builder: (context, data, reload) {
        final (children, _) = data;
        final shown = _q.isEmpty ? children : children.where((c) => '${c['name']} ${c['class_name']}'.toLowerCase().contains(_q.toLowerCase())).toList();
        return ListView(padding: const EdgeInsets.all(12), children: [
          SuggestSearchField(
            hint: _t(context, 'ابحث عن طفل', 'Kind suchen', 'Find a child'),
            searchOnType: true,
            suggestions: [for (final c in children) _s(c['name'])],
            onSearch: (v) => setState(() => _q = v),
          ),
          const SizedBox(height: 10),
          for (final c in shown)
            Card(
              child: ListTile(
                leading: AvatarInitials(_s(c['name'])),
                title: Text(_s(c['name']), style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text(_s(c['class_name'])),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => _StaffChildNotes(child: c))),
              ),
            ),
        ]);
      },
    );
  }
}

class _StaffChildNotes extends StatefulWidget {
  const _StaffChildNotes({required this.child});
  final Map<String, dynamic> child;
  @override
  State<_StaffChildNotes> createState() => _StaffChildNotesState();
}

class _StaffChildNotesState extends State<_StaffChildNotes> {
  int _round = 0;

  Future<void> _add(String kind) async {
    final text = await askText(context, kind == 'praise' ? _t(context, 'كلمة ثناء', 'Lob', 'Praise') : _t(context, 'ملاحظة', 'Notiz', 'Note'), maxLength: 500, maxLines: 4, confirm: 'save');
    if (text == null || text.trim().isEmpty || !mounted) return;
    final api = SessionScope.of(context).api;
    if (await _run(context, () => api.post('/api/platform/staff/children/${widget.child['id']}/notes', {'kind': kind, 'text': text.trim()}),
        done: _t(context, 'أُرسلت للأهل.', 'An die Eltern geschickt.', 'Sent to the parents.'))) {
      setState(() => _round++);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return _page(
      context,
      _s(widget.child['name']),
      Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
          child: Row(children: [
            Expanded(child: FilledButton.icon(style: FilledButton.styleFrom(backgroundColor: const Color(0xFF5FA34C)), onPressed: () => _add('praise'), icon: const Icon(Icons.star_rounded), label: Text(_t(context, 'ثناء ⭐', 'Lob ⭐', 'Praise ⭐')))),
            const SizedBox(width: 10),
            Expanded(child: OutlinedButton.icon(onPressed: () => _add('note'), icon: const Icon(Icons.edit_note_rounded), label: Text(_t(context, 'ملاحظة', 'Notiz', 'Note')))),
          ]),
        ),
        Expanded(
          child: _load(context, '/api/platform/staff/children/${widget.child['id']}/notes', key: ValueKey(_round), (context, data, reload) {
            final notes = _l(data);
            if (notes.isEmpty) return _empty(context, Icons.star_outline_rounded, _t(context, 'لا توجد ملاحظات بعد.', 'Noch keine Notizen.', 'No notes yet.'));
            return ListView(padding: const EdgeInsets.all(16), children: [
              for (final n in notes)
                _noteCard(context, n, onDelete: () async {
                  if (!await confirmDelete(context) || !context.mounted) return;
                  if (await _run(context, () => api.delete('/api/platform/staff/notes/${n['id']}'))) await reload();
                }),
            ]);
          }),
        ),
      ]),
    );
  }
}

// ---- things to bring ------------------------------------------------------------------------------------------------------------
class StaffBringPage extends StatefulWidget {
  const StaffBringPage({super.key});
  @override
  State<StaffBringPage> createState() => _StaffBringPageState();
}

class _StaffBringPageState extends State<StaffBringPage> {
  int _round = 0;

  Future<void> _new() async {
    final api = SessionScope.of(context).api;
    final (children, groups) = await _staffChildren(api);
    if (!mounted) return;
    final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => _BringForm(children: children, groups: groups)));
    if (saved == true) setState(() => _round++);
  }

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(heroTag: 'bring', onPressed: _new, icon: const Icon(Icons.add_rounded), label: Text(_t(context, 'جديد', 'Neu', 'New'))),
      body: _load(context, '/api/platform/staff/bring', key: ValueKey(_round), (context, data, reload) {
        final items = _l(data);
        if (items.isEmpty) return _empty(context, Icons.backpack_outlined, _t(context, 'لا يوجد شيء بعد.', 'Noch nichts.', 'Nothing yet.'));
        return ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 90), children: [
          for (final b in items)
            _bringCard(context, b, onDelete: () async {
              if (!await confirmDelete(context) || !context.mounted) return;
              if (await _run(context, () => api.delete('/api/platform/staff/bring/${b['id']}'))) await reload();
            }),
        ]);
      }),
    );
  }
}

class _BringForm extends StatefulWidget {
  const _BringForm({required this.children, required this.groups});
  final List<Map<String, dynamic>> children;
  final List<String> groups;
  @override
  State<_BringForm> createState() => _BringFormState();
}

class _BringFormState extends State<_BringForm> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  DateTime? _due = DateTime.now().add(const Duration(days: 1));
  String _target = 'all'; // all | group:<name> | child:<id>
  bool _busy = false;

  Future<void> _save() async {
    if (_title.text.trim().length < 2) {
      toast(context, _t(context, 'اكتب ما يجب إحضاره.', 'Eintragen, was mitgebracht werden soll.', 'Enter what to bring.'));
      return;
    }
    final api = SessionScope.of(context).api;
    setState(() => _busy = true);
    final ok = await _run(context, () => api.post('/api/platform/staff/bring', {
          'title': _title.text.trim(),
          'body': _body.text.trim(),
          'due_on': _due == null ? null : _day(_due!),
          'class_name': _target.startsWith('group:') ? _target.substring(6) : '',
          'child_id': _target.startsWith('child:') ? _target.substring(6) : null,
        }), done: _t(context, 'أُرسل للأهل.', 'An die Eltern geschickt.', 'Sent to the parents.'));
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(_t(context, 'أحضِر معك: جديد', 'Bitte mitbringen: neu', 'Please bring: new'))),
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: ListView(padding: const EdgeInsets.all(16), children: [
              if (_busy) const LinearProgressIndicator(),
              TextField(controller: _title, maxLength: 160, decoration: InputDecoration(labelText: _t(context, 'ماذا يُحضَر؟', 'Was wird gebraucht?', 'What to bring?'))),
              TextField(controller: _body, maxLength: 1000, maxLines: 4, minLines: 2, decoration: InputDecoration(labelText: _t(context, 'تفاصيل (اختياري)', 'Einzelheiten (optional)', 'Details (optional)'))),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _target,
                isExpanded: true,
                decoration: InputDecoration(labelText: _t(context, 'لمن؟', 'Für wen?', 'For whom?')),
                items: [
                  DropdownMenuItem(value: 'all', child: Text(_t(context, 'كل المجموعات', 'Alle Gruppen', 'Every group'))),
                  for (final g in widget.groups.where((g) => g.isNotEmpty)) DropdownMenuItem(value: 'group:$g', child: Text('${_t(context, 'مجموعة', 'Gruppe', 'Group')}: $g')),
                  for (final c in widget.children) DropdownMenuItem(value: 'child:${c['id']}', child: Text('${_t(context, 'طفل', 'Kind', 'Child')}: ${c['name']}')),
                ],
                onChanged: (v) => setState(() => _target = v ?? 'all'),
              ),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(child: Text('${_t(context, 'مطلوب يوم', 'Gebraucht am', 'Needed on')}: ${_due == null ? '—' : _day(_due!)}')),
                TextButton(
                  onPressed: () async {
                    final d = await showDatePicker(context: context, initialDate: _due ?? DateTime.now(), firstDate: DateTime.now().subtract(const Duration(days: 1)), lastDate: DateTime.now().add(const Duration(days: 120)));
                    if (d != null) setState(() => _due = d);
                  },
                  child: Text(_t(context, 'اختيار', 'Wählen', 'Choose')),
                ),
                if (_due != null) IconButton(onPressed: () => setState(() => _due = null), icon: const Icon(Icons.close_rounded)),
              ]),
            ]),
          ),
        ),
        bottomNavigationBar: BottomActionBar(children: [
          Expanded(child: FilledButton(onPressed: _busy ? null : _save, child: Text(_t(context, 'إرسال للأهل', 'An die Eltern senden', 'Send to the parents')))),
        ]),
      );
}

// ---- the week plan --------------------------------------------------------------------------------------------------------------
class StaffPlanPage extends StatefulWidget {
  const StaffPlanPage({super.key});
  @override
  State<StaffPlanPage> createState() => _StaffPlanPageState();
}

class _StaffPlanPageState extends State<StaffPlanPage> {
  List<String> _groups = [];
  String? _group;
  List<Map<String, dynamic>> _entries = [];
  bool _loaded = false;
  bool _dirty = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        final (_, groups) = await _staffChildren(SessionScope.of(context).api);
        if (!mounted) return;
        setState(() => _groups = groups);
        if (groups.isNotEmpty) await _open(groups.first);
      } on ApiException catch (e) {
        if (mounted) toast(context, problemText(context, e));
      }
    });
  }

  Future<void> _open(String group) async {
    setState(() {
      _group = group;
      _loaded = false;
    });
    try {
      final d = _m(await SessionScope.of(context).api.get('/api/platform/staff/plan', query: {'class_name': group}));
      if (mounted) {
        setState(() {
          _entries = _l(d['entries']);
          _loaded = true;
          _dirty = false;
        });
      }
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    }
  }

  Future<void> _edit(int weekday, [Map<String, dynamic>? entry]) async {
    final title = TextEditingController(text: _s(entry?['title']));
    final detail = TextEditingController(text: _s(entry?['detail']));
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(_weekdays(context)[weekday]),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: title, maxLength: 120, autofocus: true, decoration: InputDecoration(labelText: _t(context, 'النشاط', 'Aktivität', 'Activity'))),
          TextField(controller: detail, maxLength: 300, decoration: InputDecoration(labelText: _t(context, 'تفاصيل (اختياري)', 'Einzelheiten (optional)', 'Details (optional)'))),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(S.of(context).get('cancel'))),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(S.of(context).get('save'))),
        ],
      ),
    );
    if (ok != true || title.text.trim().isEmpty) return;
    setState(() {
      if (entry != null) {
        entry['title'] = title.text.trim();
        entry['detail'] = detail.text.trim();
      } else {
        final next = _entries.where((e) => e['weekday'] == weekday).length + 1;
        _entries.add({'weekday': weekday, 'position': next, 'title': title.text.trim(), 'detail': detail.text.trim()});
      }
      _dirty = true;
    });
  }

  void _remove(Map<String, dynamic> entry) {
    setState(() {
      _entries.remove(entry);
      final day = entry['weekday'];
      var i = 1;
      for (final e in _entries.where((e) => e['weekday'] == day)) {
        e['position'] = i++;
      }
      _dirty = true;
    });
  }

  Future<void> _save() async {
    final api = SessionScope.of(context).api;
    setState(() => _busy = true);
    final ok = await _run(context, () => api.put('/api/platform/staff/plan', {
          'class_name': _group ?? '',
          'entries': [for (final e in _entries) {'weekday': e['weekday'], 'position': e['position'], 'title': e['title'], 'detail': e['detail'] ?? ''}],
        }), done: _t(context, 'حُفظ برنامج الأسبوع ووصل للأهل.', 'Wochenplan gespeichert, die Eltern sehen ihn.', 'Week plan saved; the parents see it.'));
    if (mounted) setState(() => _busy = false);
    if (ok && mounted) setState(() => _dirty = false);
  }

  @override
  Widget build(BuildContext context) {
    final days = _weekdays(context);
    return Scaffold(
      floatingActionButton: _dirty ? FloatingActionButton.extended(heroTag: 'plan', onPressed: _busy ? null : _save, icon: const Icon(Icons.save_rounded), label: Text(_t(context, 'حفظ', 'Speichern', 'Save'))) : null,
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 90), children: [
        Text(_t(context, 'برنامج ثابت لكل مجموعة (الأحد إلى الخميس). يراه أهل أطفال المجموعة.', 'Ein fester Plan je Gruppe (Sonntag bis Donnerstag). Die Eltern der Gruppe sehen ihn.', 'A fixed plan per group (Sunday to Thursday). The parents of the group see it.'), style: const TextStyle(color: _muted)),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final g in _groups) ChoiceChip(label: Text(g.isEmpty ? _t(context, 'بلا مجموعة', 'ohne Gruppe', 'no group') : g), selected: _group == g, onSelected: (_) => _open(g)),
        ]),
        if (_groups.isEmpty) Padding(padding: const EdgeInsets.all(20), child: Text(_t(context, 'لا توجد مجموعات. تُكتب المجموعة في ملف الطفل.', 'Keine Gruppen. Die Gruppe wird in der Kinderakte eingetragen.', 'No groups. The group is set in the child record.'), style: const TextStyle(color: _muted))),
        if (_group != null && !_loaded) const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator())),
        if (_loaded)
          for (var d = 0; d < 5; d++)
            Card(
              margin: const EdgeInsets.only(top: 12),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Row(children: [
                    Expanded(child: Text(days[d], style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800))),
                    TextButton.icon(onPressed: () => _edit(d), icon: const Icon(Icons.add_rounded), label: Text(_t(context, 'نشاط', 'Aktivität', 'Activity'))),
                  ]),
                  for (final e in _entries.where((e) => e['weekday'] == d))
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: CircleAvatar(radius: 14, backgroundColor: const Color(0xFF5C8FE0), child: Text(_s(e['position']), style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w800))),
                      title: Text(_s(e['title'])),
                      subtitle: _s(e['detail']).isEmpty ? null : Text(_s(e['detail'])),
                      onTap: () => _edit(d, e),
                      trailing: IconButton(onPressed: () => _remove(e), icon: const Icon(Icons.delete_outline, color: _bad)),
                    ),
                ]),
              ),
            ),
      ]),
    );
  }
}

// ---- messages: the kindergarten's chats with the parents --------------------------------------------------------------------------
/// A teacher sees her own chats; the management (and the admin) sees every chat: its own (the management's) and the teachers'.
class StaffMessagesPage extends StatefulWidget {
  const StaffMessagesPage({super.key});
  @override
  State<StaffMessagesPage> createState() => _StaffMessagesPageState();
}

class _StaffMessagesPageState extends State<StaffMessagesPage> {
  int _round = 0;
  String _search = '';
  String _filter = 'all'; // all / unread / office / teachers

  bool get _boss {
    final area = SessionScope.of(context).area;
    return area == Area.management || area == Area.admin;
  }

  String _notice(String withWhom, String child) {
    if (!_boss) {
      return _t(context, 'محادثتك مع أهل $child. إدارة الروضة تستطيع الاطلاع عليها.', 'Dein Gespräch mit den Eltern von $child. Die Kitaleitung kann es sehen.',
          'Your chat with the parents of $child. The management can see it.');
    }
    return withWhom == 'office'
        ? _t(context, 'محادثة إدارة الروضة مع أهل $child.', 'Gespräch der Kitaleitung mit den Eltern von $child.', 'The management\'s chat with the parents of $child.')
        : _t(context, 'محادثة معلمة مع أهل $child. ما تكتبه هنا يظهر باسمك.', 'Gespräch einer Lehrerin mit den Eltern von $child. Was du hier schreibst, erscheint mit deinem Namen.',
            'A teacher\'s chat with the parents of $child. What you write here shows your name.');
  }

  Future<void> _open(String childId, String parentId, String to, String child, String parent, String subtitle) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ChatPage.staff(childId: childId, parentId: parentId, to: to, title: '$parent · $child', subtitle: subtitle, notice: _notice(to.isEmpty ? 'me' : to, child)),
      ),
    );
    if (mounted) setState(() => _round++);
  }

  Future<void> _new() async {
    final api = SessionScope.of(context).api;
    final (children, _) = await _staffChildren(api);
    if (!mounted) return;
    final pairs = [for (final c in children) for (final p in _l(c['parents'])) (c, p)];
    if (pairs.isEmpty) {
      toast(context, _t(context, 'لا يوجد أولياء أمور لهم حساب بعد.', 'Noch keine Eltern mit Konto.', 'No parents with an account yet.'));
      return;
    }
    final picked = await showModalBottomSheet<(Map<String, dynamic>, Map<String, dynamic>)>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => _ParentPicker(pairs: pairs),
    );
    if (picked == null || !mounted) return;
    final (c, p) = picked;
    final to = _boss ? 'office' : '';
    await _open(_s(c['id']), _s(p['id']), to, _s(c['name']), _s(p['username']),
        _boss ? _t(context, 'باسم إدارة الروضة', 'als Kitaleitung', 'as the management') : _s(c['class_name']));
  }

  @override
  Widget build(BuildContext context) {
    final boss = _boss;
    final filters = [
      ('all', _t(context, 'الكل', 'Alle', 'All')),
      ('unread', _t(context, 'غير مقروءة', 'Ungelesen', 'Unread')),
      if (boss) ('office', _t(context, 'الإدارة', 'Kitaleitung', 'Management')),
      if (boss) ('teachers', _t(context, 'المعلمات', 'Lehrerinnen', 'Teachers')),
    ];
    return Scaffold(
      floatingActionButton: FloatingActionButton(
        heroTag: 'msg',
        backgroundColor: _waGreen,
        foregroundColor: Colors.white,
        tooltip: _t(context, 'محادثة جديدة', 'Neuer Chat', 'New chat'),
        onPressed: _new,
        child: const Icon(Icons.add_comment_rounded),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: _load(context, '/api/platform/staff/conversations', key: ValueKey(_round), (context, data, reload) {
            final all = _l(data);
            final q = _search.trim().toLowerCase();
            final rows = all.where((r) {
              final unread = (r['unread'] as num? ?? 0) > 0;
              final office = _s(r['with']) == 'office';
              final ok = switch (_filter) { 'unread' => unread, 'office' => office, 'teachers' => !office, _ => true };
              if (!ok) return false;
              if (q.isEmpty) return true;
              return [r['child'], r['parent'], r['staff'], _m(r['last'])['body']].any((v) => _s(v).toLowerCase().contains(q));
            }).toList();
            return RefreshIndicator(
              onRefresh: reload,
              child: ListView(padding: const EdgeInsets.only(bottom: 90), children: [
                _chatSearch(context, (v) => setState(() => _search = v)),
                Padding(
                  padding: const EdgeInsets.fromLTRB(12, 6, 12, 6),
                  child: Wrap(spacing: 8, runSpacing: 6, children: [
                    for (final (key, label) in filters)
                      ChoiceChip(
                        label: Text(label),
                        selected: _filter == key,
                        showCheckmark: false,
                        selectedColor: const Color(0xFFD9FDD3),
                        labelStyle: TextStyle(color: _filter == key ? const Color(0xFF008069) : _waGrey, fontWeight: FontWeight.w700),
                        shape: const StadiumBorder(side: BorderSide(color: Color(0xFFE2E6EA))),
                        onSelected: (_) => setState(() => _filter = key),
                      ),
                  ]),
                ),
                if (rows.isEmpty)
                  StateView(
                    icon: Icons.chat_bubble_outline_rounded,
                    title: all.isEmpty
                        ? _t(context, 'لا توجد محادثات بعد. ابدأ محادثة بالزر الأخضر.', 'Noch keine Chats. Starte einen mit dem grünen Knopf.', 'No chats yet. Start one with the green button.')
                        : _t(context, 'لا توجد نتائج.', 'Keine Treffer.', 'Nothing found.'),
                  ),
                for (final r in rows) ...[
                  _chatRow(
                    context,
                    title: '${_s(r['parent'])} · ${_s(r['child'])}',
                    tag: !boss
                        ? ''
                        : _s(r['with']) == 'office'
                            ? _t(context, 'إدارة الروضة', 'Kitaleitung', 'Management')
                            : '${_t(context, 'مع المعلمة', 'mit Lehrerin', 'with teacher')} ${_s(r['staff'])}',
                    last: _m(r['last']),
                    lastIsOurs: _m(r['last'])['from_parent'] != true,
                    unread: (r['unread'] as num? ?? 0).toInt(),
                    onTap: () => _open(
                      _s(r['child_id']),
                      _s(r['parent_id']),
                      boss ? _s(r['with']) : '',
                      _s(r['child']),
                      _s(r['parent']),
                      boss && _s(r['with']) != 'office' ? '${_t(context, 'مع المعلمة', 'mit Lehrerin', 'with teacher')} ${_s(r['staff'])}' : _roleWord(context, 'parent'),
                    ),
                  ),
                  const Divider(height: 1, indent: 76),
                ],
              ]),
            );
          }),
        ),
      ),
    );
  }
}

/// Choosing the parent to write to (searchable): child and parent account.
class _ParentPicker extends StatefulWidget {
  const _ParentPicker({required this.pairs});
  final List<(Map<String, dynamic>, Map<String, dynamic>)> pairs;
  @override
  State<_ParentPicker> createState() => _ParentPickerState();
}

class _ParentPickerState extends State<_ParentPicker> {
  String _q = '';
  @override
  Widget build(BuildContext context) {
    final q = _q.trim().toLowerCase();
    final shown = widget.pairs.where((pair) => q.isEmpty || _s(pair.$1['name']).toLowerCase().contains(q) || _s(pair.$2['username']).toLowerCase().contains(q)).toList();
    return SizedBox(
      height: MediaQuery.sizeOf(context).height * 0.75,
      child: Column(children: [
        Text(_t(context, 'محادثة جديدة', 'Neuer Chat', 'New chat'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
        _chatSearch(context, (v) => setState(() => _q = v)),
        Expanded(
          child: ListView(children: [
            for (final (c, p) in shown)
              ListTile(
                leading: _chatAvatar(_s(p['username']), size: 44),
                title: Text(_s(p['username']), style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text('${_roleWord(context, 'parent')} · ${_s(c['name'])}${_s(c['class_name']).isEmpty ? '' : ' · ${_s(c['class_name'])}'}'),
                onTap: () => Navigator.pop(context, (c, p)),
              ),
          ]),
        ),
      ]),
    );
  }
}
