import 'package:flutter/material.dart';

import '../../localization/strings.dart';
import '../../models/models.dart';
import '../../services/api.dart';
import '../../shared/ui.dart';
import '../common/common_pages.dart';

List<T> _list<T>(dynamic data, T Function(Map<String, dynamic>) make) =>
    (data as List).map((e) => make(e as Map<String, dynamic>)).toList();

// ---- shared small views -------------------------------------------------------------------------------------------------
class ReportCard extends StatelessWidget {
  const ReportCard(this.report, {super.key, this.childName});
  final Report report;
  final String? childName;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    Widget block(IconData icon, String label, String text) => Container(
          width: double.infinity,
          margin: const EdgeInsets.only(top: 10),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: brandSoft, borderRadius: BorderRadius.circular(12)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [Icon(icon, size: 18, color: brandBlue), const SizedBox(width: 6), Text(label, style: const TextStyle(fontWeight: FontWeight.w700, color: brandBlue))]),
            const SizedBox(height: 4),
            Text(text, style: const TextStyle(height: 1.5)),
          ]),
        );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: Text(report.title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 17, height: 1.3))),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(color: brandSoft, borderRadius: BorderRadius.circular(20)),
              child: Text(formatDate(report.day), style: const TextStyle(color: brandBlue, fontSize: 12, fontWeight: FontWeight.w500)),
            ),
          ]),
          if (childName != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(children: [const Icon(Icons.child_care, size: 16, color: brandAccent), const SizedBox(width: 4), Text(childName!, style: const TextStyle(color: brandBlue, fontWeight: FontWeight.w500))]),
            ),
          const SizedBox(height: 10),
          Text(report.body, style: const TextStyle(height: 1.55)),
          if (report.activities.isNotEmpty) block(Icons.palette_outlined, s.get('activities'), report.activities),
          if (report.meals.isNotEmpty) block(Icons.restaurant_outlined, s.get('meals'), report.meals),
        ]),
      ),
    );
  }
}

class PostCard extends StatelessWidget {
  const PostCard(this.post, {super.key, required this.filePath, this.onDelete});
  final Post post;
  final String Function(Post, FileInfo) filePath;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(post.title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16))),
            if (onDelete != null) IconButton(icon: const Icon(Icons.delete_outline), onPressed: onDelete),
          ]),
          Wrap(spacing: 8, children: [
            if (post.kind == 'material') Chip(visualDensity: VisualDensity.compact, avatar: const Icon(Icons.menu_book_outlined, size: 16), label: Text(s.get('learning'), style: const TextStyle(fontSize: 12))),
            Chip(
              visualDensity: VisualDensity.compact,
              label: Text(post.scope == 'child' ? '${s.get('private')}: ${post.childName}' : s.get('general'), style: const TextStyle(fontSize: 12)),
            ),
            Text('${post.author.isNotEmpty ? '${post.author} · ' : ''}${formatDate(post.createdAt)}', style: const TextStyle(color: Colors.grey, fontSize: 12)),
          ]),
          if (post.body.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text(post.body)),
          for (final f in post.files) FileTile(file: f, path: filePath(post, f)),
        ]),
      ),
    );
  }
}

// ---- home ------------------------------------------------------------------------------------------------------------------
class ParentHome extends StatelessWidget {
  const ParentHome({super.key, required this.goTo});
  final void Function(int) goTo;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final session = SessionScope.of(context);
    final api = session.api;
    return Loader<Map<String, dynamic>>(
      load: () async {
        final children = await api.getCached('/api/platform/children');
        final notices = await api.getCached('/api/platform/announcements');
        final notes = await api.getCached('/api/platform/notifications');
        final reports = <Report>[];
        var cached = children.fromCache || notices.fromCache || notes.fromCache;
        final names = <String, String>{};
        for (final c in _list(children.data, Child.fromJson)) {
          names[c.id] = c.name;
          final r = await api.getCached('/api/platform/children/${c.id}/reports');
          cached = cached || r.fromCache;
          reports.addAll(_list(r.data, Report.fromJson).where((x) => x.status == 'published'));
        }
        reports.sort((a, b) => (b.day ?? DateTime(0)).compareTo(a.day ?? DateTime(0)));
        return Cached({'children': names, 'notices': _list(notices.data, Notice.fromJson), 'unread': (notes.data as Map)['unread'] ?? 0, 'reports': reports}, fromCache: cached);
      },
      builder: (context, d, reload) {
        final names = d['children'] as Map<String, String>;
        final reports = (d['reports'] as List<Report>).take(3).toList();
        final notices = (d['notices'] as List<Notice>).take(3).toList();
        final unread = (d['unread'] as num).toInt();
        return ListView(padding: const EdgeInsets.all(16), children: [
          HeroCard(title: s.fill('welcome', session.username ?? '')),
          Row(children: [
            Expanded(child: StatTile(icon: Icons.child_care, value: '${names.length}', label: s.get('myChildren'), onTap: () => goTo(1))),
            const SizedBox(width: 10),
            Expanded(child: StatTile(icon: Icons.notifications_active_outlined, value: '$unread', label: s.get('unread'), color: brandAccent, onTap: () => goTo(5))),
          ]),
          SectionTitle(s.get('newReports')),
          if (reports.isEmpty) Padding(padding: const EdgeInsets.all(12), child: Text(s.get('noReports'))),
          for (final r in reports) ReportCard(r, childName: names[r.childId]),
          if (notices.isNotEmpty) SectionTitle(s.get('notices')),
          NoticeCards(notices),
        ]);
      },
    );
  }
}

// ---- my children + reports ---------------------------------------------------------------------------------------------
class ParentChildren extends StatefulWidget {
  const ParentChildren({super.key});
  @override
  State<ParentChildren> createState() => _ParentChildrenState();
}

class _ParentChildrenState extends State<ParentChildren> {
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<List<Child>>(
      load: () async {
        final c = await api.getCached('/api/platform/children');
        return Cached(_list(c.data, Child.fromJson), fromCache: c.fromCache);
      },
      builder: (context, children, reload) {
        if (children.isEmpty) return EmptyNote(s.get('noChildren'));
        return ListView(padding: const EdgeInsets.all(12), children: [
          for (final c in children)
            Card(
              child: ListTile(
                leading: const CircleAvatar(backgroundColor: brandSoft, child: Icon(Icons.child_care, color: brandBlue)),
                title: Text(c.name, style: const TextStyle(fontWeight: FontWeight.bold)),
                subtitle: Text(s.get('reports')),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ChildReportsPage(child: c))),
              ),
            ),
        ]);
      },
    );
  }
}

class ChildReportsPage extends StatefulWidget {
  const ChildReportsPage({super.key, required this.child});
  final Child child;
  @override
  State<ChildReportsPage> createState() => _ChildReportsPageState();
}

class _ChildReportsPageState extends State<ChildReportsPage> {
  DateTime? _day;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Scaffold(
      appBar: AppBar(title: Text(widget.child.name), actions: [
        IconButton(
          icon: Icon(_day == null ? Icons.event : Icons.event_busy),
          tooltip: _day == null ? s.get('pickDate') : s.get('clear'),
          onPressed: () async {
            if (_day != null) {
              setState(() => _day = null);
              return;
            }
            final picked = await showDatePicker(context: context, initialDate: DateTime.now(), firstDate: DateTime(2020), lastDate: DateTime.now().add(const Duration(days: 1)));
            if (picked != null) setState(() => _day = picked);
          },
        ),
      ]),
      body: Loader<List<Report>>(
        load: () async {
          final c = await api.getCached('/api/platform/children/${widget.child.id}/reports');
          // only what the management / the teacher released; the server filters as well
          return Cached(_list(c.data, Report.fromJson).where((r) => r.status == 'published').toList(), fromCache: c.fromCache);
        },
        builder: (context, reports, reload) {
          final shown = _day == null ? reports : reports.where((r) => r.day != null && formatDate(r.day) == formatDate(_day)).toList();
          if (shown.isEmpty) return EmptyNote(s.get('noReports'));
          return ListView(padding: const EdgeInsets.all(12), children: [if (_day != null) Chip(label: Text(formatDate(_day))), for (final r in shown) ReportCard(r)]);
        },
      ),
    );
  }
}

class ParentReports extends StatelessWidget {
  const ParentReports({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<List<(Report, String)>>(
      load: () async {
        final children = await api.getCached('/api/platform/children');
        var cached = children.fromCache;
        final all = <(Report, String)>[];
        for (final c in _list(children.data, Child.fromJson)) {
          final r = await api.getCached('/api/platform/children/${c.id}/reports');
          cached = cached || r.fromCache;
          for (final report in _list(r.data, Report.fromJson).where((x) => x.status == 'published')) {
            all.add((report, c.name));
          }
        }
        all.sort((a, b) => (b.$1.day ?? DateTime(0)).compareTo(a.$1.day ?? DateTime(0)));
        return Cached(all, fromCache: cached);
      },
      builder: (context, items, reload) {
        if (items.isEmpty) return EmptyNote(s.get('noReports'));
        return ListView(padding: const EdgeInsets.all(12), children: [for (final i in items) ReportCard(i.$1, childName: i.$2)]);
      },
    );
  }
}


// ---- learning material shown like a course page (a section with a list of files) ----------------------------------------------
const _courseTeal = Color(0xFF0E8FA6);

IconData _fileIcon(String ext, bool image) {
  if (image) return Icons.image_outlined;
  switch (ext) {
    case 'pdf':
      return Icons.picture_as_pdf_outlined;
    case 'zip':
    case 'rar':
    case '7z':
      return Icons.folder_zip_outlined;
    case 'mp4':
    case 'mov':
    case 'avi':
    case 'webm':
    case 'mkv':
      return Icons.smart_display_outlined;
    case 'mp3':
    case 'wav':
    case 'm4a':
      return Icons.audiotrack_outlined;
    case 'doc':
    case 'docx':
    case 'txt':
      return Icons.description_outlined;
    case 'xls':
    case 'xlsx':
    case 'csv':
      return Icons.table_chart_outlined;
    case 'ppt':
    case 'pptx':
      return Icons.slideshow_outlined;
    default:
      return Icons.insert_drive_file_outlined;
  }
}

/// One learning-material post as a section: round collapse button, big title, then one row per file (icon, name, TYPE).
class MaterialSection extends StatefulWidget {
  const MaterialSection(this.post, {super.key, required this.filePath, this.onDelete, this.headerActions = const [], this.fileTrailing, this.footer});
  final Post post;
  final String Function(Post, FileInfo) filePath;
  final VoidCallback? onDelete;
  final List<Widget> headerActions; // edit mode: menu in the header
  final Widget Function(FileInfo)? fileTrailing; // edit mode: menu at the end of a file row
  final Widget? footer; // edit mode: e.g. the add-files button
  @override
  State<MaterialSection> createState() => _MaterialSectionState();
}

class _MaterialSectionState extends State<MaterialSection> {
  bool _open = true;

  @override
  Widget build(BuildContext context) {
    final post = widget.post;
    final api = SessionScope.of(context).api;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      color: post.hidden ? const Color(0xFFF1F3F5) : null,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24), side: const BorderSide(color: Color(0xFFDDE3EA))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        InkWell(
          onTap: () => setState(() => _open = !_open),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
            child: Row(children: [
              Container(
                width: 44,
                height: 44,
                decoration: const BoxDecoration(color: Color(0xFFE9ECEF), shape: BoxShape.circle),
                child: Icon(_open ? Icons.keyboard_arrow_down : Icons.keyboard_arrow_up, size: 28, color: const Color(0xFF1B2533)),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(post.title, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, height: 1.25, color: post.hidden ? Colors.grey.shade600 : null)),
                  if (post.hidden) Padding(padding: const EdgeInsets.only(top: 4), child: Row(mainAxisSize: MainAxisSize.min, children: [Icon(Icons.visibility_off_outlined, size: 16, color: Colors.grey.shade600), const SizedBox(width: 4), Text(S.of(context).get('hiddenFromParents'), style: TextStyle(fontSize: 13, color: Colors.grey.shade600))])),
                ]),
              ),
              if (widget.onDelete != null) IconButton(icon: const Icon(Icons.delete_outline), onPressed: widget.onDelete),
              ...widget.headerActions,
            ]),
          ),
        ),
        if (_open) ...[
          if (post.body.isNotEmpty) Padding(padding: const EdgeInsets.fromLTRB(20, 0, 20, 8), child: Text(post.body, style: TextStyle(color: Colors.grey.shade700, height: 1.5))),
          for (var i = 0; i < post.files.length; i++) ...[
            Divider(height: 1, indent: 16, endIndent: 16, color: Colors.grey.shade300),
            Builder(builder: (context) {
              final f = post.files[i];
              final dot = f.filename.lastIndexOf('.');
              final base = dot > 0 ? f.filename.substring(0, dot) : f.filename;
              final ext = dot > 0 ? f.filename.substring(dot + 1).toLowerCase() : '';
              return InkWell(
                onTap: () => openPrivateFile(context, api, widget.filePath(post, f), f.filename),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                  child: Row(children: [
                    Icon(_fileIcon(ext, f.isImage), color: _courseTeal, size: 30),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Text.rich(
                        TextSpan(children: [
                          TextSpan(text: base, style: const TextStyle(fontSize: 17)),
                          if (ext.isNotEmpty) TextSpan(text: '   ${ext.toUpperCase()}', style: TextStyle(fontSize: 13, color: Colors.grey.shade700)),
                        ]),
                      ),
                    ),
                    if (widget.fileTrailing != null) widget.fileTrailing!(f),
                  ]),
                ),
              );
            }),
          ],
          if (post.files.isEmpty && post.body.isEmpty) const SizedBox(height: 8),
          if (widget.footer != null) widget.footer!,
          const SizedBox(height: 4),
        ],
      ]),
    );
  }
}

// ---- learning material (from the teachers) -----------------------------------------------------------------------------------
class ParentLearning extends StatelessWidget {
  const ParentLearning({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<List<Post>>(
      load: () async {
        final posts = await api.getCached('/api/platform/parent/posts');
        return Cached(_list(posts.data, Post.fromJson).where((p) => p.kind == 'material').toList(), fromCache: posts.fromCache);
      },
      builder: (context, items, reload) {
        if (items.isEmpty) return EmptyNote(s.get('noLearning'));
        return ListView(padding: const EdgeInsets.all(12), children: [
          for (final p in items) MaterialSection(p, filePath: (post, f) => '/api/platform/parent/posts/${post.id}/files/${f.id}'),
        ]);
      },
    );
  }
}

// ---- posts and notices -----------------------------------------------------------------------------------------------------
class ParentPosts extends StatelessWidget {
  const ParentPosts({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<(List<Post>, List<Notice>)>(
      load: () async {
        final posts = await api.getCached('/api/platform/parent/posts');
        final notices = await api.getCached('/api/platform/announcements');
        return Cached((_list(posts.data, Post.fromJson), _list(notices.data, Notice.fromJson)), fromCache: posts.fromCache || notices.fromCache);
      },
      builder: (context, d, reload) {
        final (all, notices) = d;
        final posts = all.where((p) => p.kind != 'material').toList();
        if (posts.isEmpty && notices.isEmpty) return EmptyNote(s.get('noPosts'));
        return ListView(padding: const EdgeInsets.all(12), children: [
          if (notices.isNotEmpty) SectionTitle(s.get('notices')),
          NoticeCards(notices),
          if (posts.isNotEmpty) SectionTitle(s.get('posts')),
          for (final p in posts) PostCard(p, filePath: (post, f) => '/api/platform/parent/posts/${post.id}/files/${f.id}'),
        ]);
      },
    );
  }
}
