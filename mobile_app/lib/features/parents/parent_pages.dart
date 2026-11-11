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
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(report.title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16))),
            Text(formatDate(report.day), style: const TextStyle(color: Colors.grey, fontSize: 12)),
          ]),
          if (childName != null) Padding(padding: const EdgeInsets.only(top: 2), child: Text(childName!, style: const TextStyle(color: brandBlue))),
          const SizedBox(height: 8),
          Text(report.body),
          if (report.activities.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(s.get('activities'), style: const TextStyle(fontWeight: FontWeight.bold)),
            Text(report.activities),
          ],
          if (report.meals.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(s.get('meals'), style: const TextStyle(fontWeight: FontWeight.bold)),
            Text(report.meals),
          ],
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
          Card(
            color: brandBlue,
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Text(s.fill('welcome', session.username ?? ''), style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
            ),
          ),
          Row(children: [
            Expanded(child: _Tile(Icons.child_care, '${names.length}', s.get('myChildren'), () => goTo(1))),
            const SizedBox(width: 8),
            Expanded(child: _Tile(Icons.notifications_active_outlined, '$unread', s.get('unread'), () => goTo(4))),
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

class _Tile extends StatelessWidget {
  const _Tile(this.icon, this.number, this.label, this.onTap);
  final IconData icon;
  final String number;
  final String label;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Card(
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(children: [
              Icon(icon, color: brandBlue),
              Text(number, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
              Text(label, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12)),
            ]),
          ),
        ),
      );
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
          for (final p in items) PostCard(p, filePath: (post, f) => '/api/platform/parent/posts/${post.id}/files/${f.id}'),
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
