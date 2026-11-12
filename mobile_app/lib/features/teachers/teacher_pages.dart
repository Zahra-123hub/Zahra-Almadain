import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../localization/strings.dart';
import '../../models/models.dart';
import '../../services/api.dart';
import '../../shared/ui.dart';
import '../common/common_pages.dart';
import '../parents/parent_pages.dart';

List<T> _list<T>(dynamic data, T Function(Map<String, dynamic>) make) =>
    (data as List).map((e) => make(e as Map<String, dynamic>)).toList();

String categoryOf(String filename) {
  final ext = filename.contains('.') ? filename.split('.').last.toLowerCase() : '';
  if (const ['jpg', 'jpeg', 'png', 'gif', 'webp'].contains(ext)) return 'image';
  if (const ['mp4', 'mov', 'webm', 'm4v'].contains(ext)) return 'video';
  if (const ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt'].contains(ext)) return 'document';
  return 'other';
}

String statusLabel(S s, String status) {
  switch (status) {
    case 'draft':
      return s.get('draft');
    case 'submitted':
      return s.get('submitted');
    case 'rejected':
      return s.get('returned');
    case 'published':
      return s.get('published');
    default:
      return status;
  }
}

Color statusColor(String status) {
  switch (status) {
    case 'published':
      return Colors.green;
    case 'submitted':
      return Colors.orange;
    case 'rejected':
      return Colors.red;
    default:
      return Colors.blueGrey;
  }
}

// ---- picking images / files ------------------------------------------------------------------------------------------------
/// Collects files chosen from the camera, the gallery or the file browser. The server checks type and size again.
class AttachmentPicker extends StatelessWidget {
  const AttachmentPicker({super.key, required this.files, required this.onChanged, this.max = 1000, this.allowAnyFile = true});
  final List<UploadFile> files;
  final void Function(List<UploadFile>) onChanged;
  final int max;
  final bool allowAnyFile;

  Future<void> _camera(BuildContext context) async {
    final shot = await ImagePicker().pickImage(source: ImageSource.camera, imageQuality: 85, maxWidth: 2400);
    if (shot != null) onChanged([...files, UploadFile(shot.path, shot.name)]);
  }

  Future<void> _gallery(BuildContext context) async {
    final picked = await ImagePicker().pickMultiImage(imageQuality: 85, maxWidth: 2400);
    onChanged([...files, ...picked.map((x) => UploadFile(x.path, x.name))].take(max).toList());
  }

  Future<void> _file(BuildContext context) async {
    final result = await FilePicker.pickFiles();
    if (result.isEmpty) return;
    onChanged([...files, ...result.where((f) => f.path != null).map((f) => UploadFile(f.path!, f.name))].take(max).toList());
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final full = files.length >= max;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Wrap(spacing: 8, children: [
        OutlinedButton.icon(onPressed: full ? null : () => _camera(context), icon: const Icon(Icons.photo_camera_outlined), label: Text(s.get('camera'))),
        OutlinedButton.icon(onPressed: full ? null : () => _gallery(context), icon: const Icon(Icons.photo_library_outlined), label: Text(s.get('gallery'))),
        if (allowAnyFile) OutlinedButton.icon(onPressed: full ? null : () => _file(context), icon: const Icon(Icons.attach_file), label: Text(s.get('file'))),
      ]),
      for (var i = 0; i < files.length; i++)
        ListTile(
          dense: true,
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.insert_drive_file_outlined),
          title: Text(files[i].name, maxLines: 1, overflow: TextOverflow.ellipsis),
          trailing: IconButton(icon: const Icon(Icons.close), onPressed: () => onChanged([...files]..removeAt(i))),
        ),
    ]);
  }
}

// ---- home ------------------------------------------------------------------------------------------------------------------
class TeacherHome extends StatelessWidget {
  const TeacherHome({super.key, required this.goTo});
  final void Function(int) goTo;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final session = SessionScope.of(context);
    final api = session.api;
    return Loader<Map<String, dynamic>>(
      load: () async {
        final children = await api.getCached('/api/platform/teacher/children');
        final reports = await api.getCached('/api/platform/teacher/reports');
        final notices = await api.getCached('/api/platform/announcements');
        return Cached({
          'children': (children.data as List).length,
          'reports': _list(reports.data, Report.fromJson),
          'notices': _list(notices.data, Notice.fromJson),
        }, fromCache: children.fromCache || reports.fromCache || notices.fromCache);
      },
      builder: (context, d, reload) {
        final reports = d['reports'] as List<Report>;
        int count(String st) => reports.where((r) => r.status == st).length;
        Widget tile(IconData icon, int n, String label, int tab, [Color color = brandBlue]) =>
            Expanded(child: StatTile(icon: icon, value: '$n', label: label, color: color, onTap: () => goTo(tab)));
        return ListView(padding: const EdgeInsets.all(16), children: [
          HeroCard(title: s.fill('welcome', session.username ?? '')),
          Row(children: [tile(Icons.child_care, d['children'] as int, s.get('children'), 1), const SizedBox(width: 10), tile(Icons.edit_note, count('draft'), s.get('openReports'), 2, brandAccent)]),
          Row(children: [tile(Icons.hourglass_bottom, count('submitted'), s.get('submitted'), 2, const Color(0xFF3B7DD8)), const SizedBox(width: 10), tile(Icons.undo, count('rejected'), s.get('returned'), 2, const Color(0xFFD25B5B))]),
          if ((d['notices'] as List).isNotEmpty) SectionTitle(s.get('notices')),
          NoticeCards((d['notices'] as List<Notice>).take(3).toList()),
        ]);
      },
    );
  }
}

// ---- children ---------------------------------------------------------------------------------------------------------------
class TeacherChildren extends StatelessWidget {
  const TeacherChildren({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<List<Child>>(
      load: () async {
        final c = await api.getCached('/api/platform/teacher/children');
        return Cached(_list(c.data, Child.fromJson), fromCache: c.fromCache);
      },
      builder: (context, children, reload) {
        if (children.isEmpty) return EmptyNote(s.get('noChildren'));
        return ListView(padding: const EdgeInsets.all(12), children: [
          for (final c in children)
            Card(
              child: ListTile(
                leading: const CircleAvatar(backgroundColor: brandSoft, child: Icon(Icons.child_care, color: brandBlue)),
                title: Text(c.name),
                trailing: const Icon(Icons.add_circle_outline),
                onTap: () async {
                  final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => ReportEditor(presetChild: c, children: children)));
                  if (saved == true) await reload();
                },
              ),
            ),
        ]);
      },
    );
  }
}

// ---- reports -----------------------------------------------------------------------------------------------------------------
class TeacherReports extends StatelessWidget {
  const TeacherReports({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<(List<Report>, List<Child>)>(
      load: () async {
        final reports = await api.getCached('/api/platform/teacher/reports');
        final children = await api.getCached('/api/platform/teacher/children');
        return Cached((_list(reports.data, Report.fromJson), _list(children.data, Child.fromJson)), fromCache: reports.fromCache || children.fromCache);
      },
      builder: (context, d, reload) {
        final (reports, children) = d;
        final names = {for (final c in children) c.id: c.name};
        return Scaffold(
          backgroundColor: Colors.transparent,
          floatingActionButton: FloatingActionButton.extended(
            backgroundColor: brandAccent,
            icon: const Icon(Icons.add),
            label: Text(s.get('newReport')),
            onPressed: () async {
              final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => ReportEditor(children: children)));
              if (saved == true) await reload();
            },
          ),
          body: reports.isEmpty
              ? EmptyNote(s.get('noReports'))
              : ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 90), children: [
                  for (final r in reports)
                    Card(
                      child: ListTile(
                        title: Text(r.title, style: const TextStyle(fontWeight: FontWeight.bold)),
                        subtitle: Text('${names[r.childId] ?? ''} · ${formatDate(r.createdAt)}'),
                        trailing: Chip(
                          visualDensity: VisualDensity.compact,
                          label: Text(statusLabel(s, r.status), style: TextStyle(color: statusColor(r.status), fontSize: 12)),
                        ),
                        onTap: () async {
                          final editable = r.status == 'draft' || r.status == 'rejected';
                          if (editable) {
                            final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => ReportEditor(report: r, children: children)));
                            if (saved == true) await reload();
                          } else {
                            await Navigator.push(context, MaterialPageRoute(builder: (_) => Scaffold(appBar: AppBar(title: Text(r.title)), body: ListView(padding: const EdgeInsets.all(12), children: [ReportCard(r, childName: names[r.childId])]))));
                          }
                        },
                      ),
                    ),
                ]),
        );
      },
    );
  }
}

class ReportEditor extends StatefulWidget {
  const ReportEditor({super.key, this.report, this.presetChild, required this.children});
  final Report? report;
  final Child? presetChild;
  final List<Child> children;
  @override
  State<ReportEditor> createState() => _ReportEditorState();
}

class _ReportEditorState extends State<ReportEditor> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  final _activities = TextEditingController();
  final _meals = TextEditingController();
  String? _childId;
  List<UploadFile> _files = [];
  List<FileInfo> _existing = [];
  bool _busy = false;
  String? _error;

  String get _draftKey => 'draft:report:${widget.report?.id ?? 'new'}';

  @override
  void initState() {
    super.initState();
    final r = widget.report;
    if (r != null) {
      _title.text = r.title;
      _body.text = r.body;
      _activities.text = r.activities;
      _meals.text = r.meals;
      _childId = r.childId;
      _loadExisting();
    } else {
      _childId = widget.presetChild?.id;
    }
    _restoreDraft();
  }

  // A text typed on this phone survives a closed app or a lost connection; removed after saving and at sign-out.
  Future<void> _restoreDraft() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_draftKey);
    if (saved == null) return;
    final m = jsonDecode(saved) as Map<String, dynamic>;
    if (_title.text.isEmpty && _body.text.isEmpty) {
      setState(() {
        _title.text = (m['title'] ?? '') as String;
        _body.text = (m['body'] ?? '') as String;
        _activities.text = (m['activities'] ?? '') as String;
        _meals.text = (m['meals'] ?? '') as String;
        _childId ??= m['child'] as String?;
      });
    }
  }

  Future<void> _keepDraft() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_draftKey, jsonEncode({'title': _title.text, 'body': _body.text, 'activities': _activities.text, 'meals': _meals.text, 'child': _childId}));
  }

  Future<void> _loadExisting() async {
    try {
      final api = SessionScope.of(context).api;
      final data = await api.get('/api/platform/teacher/reports/${widget.report!.id}/attachments');
      if (mounted) setState(() => _existing = _list(data, FileInfo.fromJson));
    } catch (_) {}
  }

  Future<void> _save({bool review = false, bool parents = false}) async {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    if (_childId == null || _title.text.trim().isEmpty || _body.text.trim().isEmpty) {
      setState(() => _error = s.get('required'));
      return;
    }
    if (parents) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
          content: Text(s.get('confirmParents')),
          actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.get('cancel'))), FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(90, 40)), onPressed: () => Navigator.pop(context, true), child: Text(s.get('sendParents')))],
        ),
      );
      if (ok != true) return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    await _keepDraft();
    final fields = {'title': _title.text.trim(), 'body': _body.text.trim(), 'activities': _activities.text.trim(), 'meals': _meals.text.trim()};
    try {
      // 1) store as a draft, 2) add attachments (they are only allowed on drafts), 3) send where the teacher chose
      String id = widget.report?.id ?? '';
      if (id.isEmpty) {
        final created = await api.post('/api/platform/teacher/reports', {...fields, 'child_id': _childId});
        id = (created as Map<String, dynamic>)['id'] as String;
      } else {
        await api.patch('/api/platform/teacher/reports/$id', {...fields, 'submit_for_review': false, 'publish_to_parents': false});
      }
      while (_files.isNotEmpty) {
        final file = _files.first;
        await api.multipart('/api/platform/teacher/content', {'category': 'report_attachment', 'report_id': id}, [file], fileField: 'file');
        _files = _files.sublist(1); // an upload that went through is not sent twice when the user retries
      }
      if (review || parents) {
        await api.patch('/api/platform/teacher/reports/$id', {...fields, 'submit_for_review': review, 'publish_to_parents': parents});
      }
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_draftKey);
      if (!mounted) return;
      toast(context, s.get('saved'));
      Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = e.problem == ApiProblem.bad && e.detail.isNotEmpty ? e.detail : problemText(context, e);
        if (e.problem == ApiProblem.offline && widget.report == null) _error = '${_error!}\n${s.get('draftLocal')}';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Scaffold(
      appBar: AppBar(title: Text(widget.report == null ? s.get('newReport') : s.get('editReport'))),
      body: AbsorbPointer(
        absorbing: _busy,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          DropdownButtonFormField<String>(
            initialValue: _childId,
            decoration: InputDecoration(labelText: s.get('child')),
            items: [for (final c in widget.children) DropdownMenuItem(value: c.id, child: Text(c.name))],
            onChanged: widget.report == null ? (v) => setState(() => _childId = v) : null,
          ),
          const SizedBox(height: 12),
          TextField(controller: _title, maxLength: 120, onChanged: (_) => _keepDraft(), decoration: InputDecoration(labelText: s.get('title'))),
          TextField(controller: _body, maxLength: 3000, minLines: 4, maxLines: 10, onChanged: (_) => _keepDraft(), decoration: InputDecoration(labelText: s.get('text'))),
          const SizedBox(height: 8),
          TextField(controller: _activities, maxLength: 1000, minLines: 2, maxLines: 5, decoration: InputDecoration(labelText: s.get('activities'))),
          TextField(controller: _meals, maxLength: 500, minLines: 2, maxLines: 4, decoration: InputDecoration(labelText: s.get('meals'))),
          SectionTitle(s.get('attachments')),
          for (final f in _existing) FileTile(file: f, path: '/api/platform/teacher/content/${f.id}/download'),
          AttachmentPicker(files: _files, max: 5 - _existing.length, onChanged: (v) => setState(() => _files = v)),
          if (_error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_error!, style: const TextStyle(color: Colors.red))),
          const SizedBox(height: 16),
          FilledButton.icon(onPressed: () => _save(), icon: const Icon(Icons.save_outlined), label: Text(s.get('saveDraft'))),
          const SizedBox(height: 8),
          FilledButton.icon(style: FilledButton.styleFrom(backgroundColor: brandAccent, foregroundColor: Colors.black), onPressed: () => _save(review: true), icon: const Icon(Icons.send_outlined), label: Text(s.get('sendReview'))),
          const SizedBox(height: 8),
          OutlinedButton.icon(style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)), onPressed: () => _save(parents: true), icon: const Icon(Icons.family_restroom), label: Text(s.get('sendParents'))),
          if (_busy) const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator())),
          SizedBox(height: api.token == null ? 0 : 24),
        ]),
      ),
    );
  }
}

// ---- posts -------------------------------------------------------------------------------------------------------------------
class TeacherPosts extends StatelessWidget {
  const TeacherPosts({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<(List<Post>, List<Child>)>(
      load: () async {
        final posts = await api.getCached('/api/platform/teacher/posts');
        final children = await api.getCached('/api/platform/teacher/children');
        return Cached((_list(posts.data, Post.fromJson), _list(children.data, Child.fromJson)), fromCache: posts.fromCache || children.fromCache);
      },
      builder: (context, d, reload) {
        final (posts, children) = d;
        return Scaffold(
          backgroundColor: Colors.transparent,
          floatingActionButton: FloatingActionButton.extended(
            backgroundColor: brandAccent,
            icon: const Icon(Icons.add),
            label: Text(s.get('newPost')),
            onPressed: () async {
              final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => PostComposer(children: children)));
              if (saved == true) await reload();
            },
          ),
          body: posts.isEmpty
              ? EmptyNote(s.get('noPosts'))
              : ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 90), children: [
                  for (final p in posts)
                    PostCard(
                      p,
                      filePath: (post, f) => '/api/platform/teacher/content/${f.id}/download',
                      onDelete: () async {
                        final ok = await showDialog<bool>(
                          context: context,
                          builder: (_) => AlertDialog(
                            content: Text(s.get('confirmDelete')),
                            actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.get('cancel'))), TextButton(onPressed: () => Navigator.pop(context, true), child: Text(s.get('delete')))],
                          ),
                        );
                        if (ok != true) return;
                        try {
                          await api.delete('/api/platform/teacher/posts/${p.id}');
                          await reload();
                        } catch (e) {
                          if (context.mounted) toast(context, problemText(context, e));
                        }
                      },
                    ),
                ]),
        );
      },
    );
  }
}

class PostComposer extends StatefulWidget {
  const PostComposer({super.key, required this.children, this.material = false});
  final List<Child> children;
  final bool material;
  @override
  State<PostComposer> createState() => _PostComposerState();
}

class _PostComposerState extends State<PostComposer> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  String _scope = 'general';
  String? _childId;
  late bool _material = widget.material;
  List<UploadFile> _files = [];
  bool _busy = false;
  String? _error;

  Future<void> _send() async {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    if (_title.text.trim().isEmpty || (_body.text.trim().isEmpty && _files.isEmpty) || (_scope == 'child' && _childId == null)) {
      setState(() => _error = s.get('required'));
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await api.multipart('/api/platform/teacher/posts', {
        'scope': _scope,
        'kind': _material ? 'material' : 'post',
        'title': _title.text.trim(),
        'body': _body.text.trim(),
        if (_scope == 'child') 'child_id': _childId!,
      }, _files);
      if (!mounted) return;
      toast(context, s.get('saved'));
      Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = e.problem == ApiProblem.bad && e.detail.isNotEmpty ? e.detail : problemText(context, e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(s.get(widget.material ? 'newMaterial' : 'newPost'))),
      body: AbsorbPointer(
        absorbing: _busy,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          SegmentedButton<String>(
            segments: [ButtonSegment(value: 'general', label: Text(s.get('general'))), ButtonSegment(value: 'child', label: Text(s.get('private')))],
            selected: {_scope},
            onSelectionChanged: (v) => setState(() => _scope = v.first),
          ),
          if (!widget.material) SwitchListTile(contentPadding: EdgeInsets.zero, value: _material, onChanged: (v) => setState(() => _material = v), title: Text(s.get('forParents'))),
          if (_scope == 'child') ...[
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _childId,
              decoration: InputDecoration(labelText: s.get('child')),
              items: [for (final c in widget.children) DropdownMenuItem(value: c.id, child: Text(c.name))],
              onChanged: (v) => setState(() => _childId = v),
            ),
          ],
          const SizedBox(height: 12),
          TextField(controller: _title, maxLength: 120, decoration: InputDecoration(labelText: s.get('title'))),
          TextField(controller: _body, maxLength: 3000, minLines: 4, maxLines: 10, decoration: InputDecoration(labelText: s.get('text'))),
          SectionTitle(s.get('attachments')),
          AttachmentPicker(files: _files, onChanged: (v) => setState(() => _files = v)),
          if (_error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_error!, style: const TextStyle(color: Colors.red))),
          const SizedBox(height: 16),
          FilledButton.icon(onPressed: _send, icon: const Icon(Icons.send_outlined), label: Text(s.get('publish'))),
          if (_busy) const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator())),
        ]),
      ),
    );
  }
}

// ---- teaching material --------------------------------------------------------------------------------------------------------
class TeacherMaterials extends StatelessWidget {
  const TeacherMaterials({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<(List<MaterialFile>, Map<String, dynamic>, List<Post>, List<Child>)>(
      load: () async {
        final items = await api.getCached('/api/platform/teacher/content');
        final storage = await api.getCached('/api/platform/teacher/storage');
        final posts = await api.getCached('/api/platform/teacher/posts');
        final children = await api.getCached('/api/platform/teacher/children');
        final mine = _list(items.data, MaterialFile.fromJson).where((m) => m.category != 'report_attachment').toList();
        final shared = _list(posts.data, Post.fromJson).where((p) => p.kind == 'material').toList();
        return Cached((mine, storage.data as Map<String, dynamic>, shared, _list(children.data, Child.fromJson)),
            fromCache: items.fromCache || storage.fromCache || posts.fromCache || children.fromCache);
      },
      builder: (context, d, reload) {
        final (items, storage, shared, children) = d;
        final used = (storage['used_bytes'] as num).toInt();
        final limit = (storage['limit_bytes'] as num).toInt();
        return Scaffold(
          backgroundColor: Colors.transparent,
          floatingActionButton: FloatingActionButton.extended(
            backgroundColor: brandAccent,
            icon: const Icon(Icons.upload_file),
            label: Text(s.get('uploadFile')),
            onPressed: () async {
              final forParents = await showModalBottomSheet<bool>(
                context: context,
                builder: (_) => SafeArea(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    ListTile(leading: const Icon(Icons.family_restroom, color: brandBlue), title: Text(s.get('shareWithParents')), onTap: () => Navigator.pop(context, true)),
                    ListTile(leading: const Icon(Icons.lock_outline, color: brandBlue), title: Text(s.get('privateFile')), onTap: () => Navigator.pop(context, false)),
                  ]),
                ),
              );
              if (forParents == null || !context.mounted) return;
              if (forParents) {
                final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => PostComposer(children: children, material: true)));
                if (saved == true) await reload();
                return;
              }
              final f = await FilePicker.pickFile();
              if (f == null || f.path == null) return;
              try {
                await api.multipart('/api/platform/teacher/content', {'category': categoryOf(f.name)}, [UploadFile(f.path!, f.name)], fileField: 'file');
                await reload();
              } on ApiException catch (e) {
                if (context.mounted) toast(context, e.problem == ApiProblem.bad && e.detail.isNotEmpty ? e.detail : problemText(context, e));
              }
            },
          ),
          body: ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 90), children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${s.get('storage')}: ${formatSize(used)} / ${formatSize(limit)}'),
                  const SizedBox(height: 8),
                  LinearProgressIndicator(value: limit == 0 ? 0 : (used / limit).clamp(0, 1).toDouble(), minHeight: 8, borderRadius: BorderRadius.circular(8)),
                ]),
              ),
            ),
            if (shared.isNotEmpty) SectionTitle(s.get('sharedWithParents')),
            for (final p in shared)
              PostCard(
                p,
                filePath: (post, f) => '/api/platform/teacher/content/${f.id}/download',
                onDelete: () async {
                  final ok = await showDialog<bool>(
                    context: context,
                    builder: (_) => AlertDialog(
                      content: Text(s.get('confirmDelete')),
                      actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.get('cancel'))), TextButton(onPressed: () => Navigator.pop(context, true), child: Text(s.get('delete')))],
                    ),
                  );
                  if (ok != true) return;
                  try {
                    await api.delete('/api/platform/teacher/posts/${p.id}');
                    await reload();
                  } catch (e) {
                    if (context.mounted) toast(context, problemText(context, e));
                  }
                },
              ),
            SectionTitle(s.get('myPrivateFiles')),
            if (items.isEmpty) Padding(padding: const EdgeInsets.all(24), child: Center(child: Text(s.get('noFiles')))),
            for (final m in items)
              Card(
                child: ListTile(
                  leading: Icon(m.mediaType.startsWith('image/') ? Icons.image_outlined : Icons.insert_drive_file_outlined),
                  title: Text(m.filename, maxLines: 1, overflow: TextOverflow.ellipsis),
                  subtitle: Text(formatSize(m.size)),
                  onTap: () => openPrivateFile(context, api, '/api/platform/teacher/content/${m.id}/download', m.filename),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () async {
                      final ok = await showDialog<bool>(
                        context: context,
                        builder: (_) => AlertDialog(
                          content: Text(s.get('confirmDelete')),
                          actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.get('cancel'))), TextButton(onPressed: () => Navigator.pop(context, true), child: Text(s.get('delete')))],
                        ),
                      );
                      if (ok != true) return;
                      try {
                        await api.delete('/api/platform/teacher/content/${m.id}');
                        await reload();
                      } catch (e) {
                        if (context.mounted) toast(context, problemText(context, e));
                      }
                    },
                  ),
                ),
              ),
          ]),
        );
      },
    );
  }
}
