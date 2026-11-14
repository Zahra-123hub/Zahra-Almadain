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

String categoryOf(String filename) {
  final ext = filename.contains('.') ? filename.split('.').last.toLowerCase() : '';
  if (const ['jpg', 'jpeg', 'png', 'gif', 'webp'].contains(ext)) return 'image';
  if (const ['mp4', 'mov', 'webm', 'm4v'].contains(ext)) return 'video';
  if (const ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt'].contains(ext)) return 'document';
  return 'other';
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
  final void Function(String) goTo;

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
          'reports': parseList(reports.data, Report.fromJson),
          'notices': parseList(notices.data, Notice.fromJson),
        }, fromCache: children.fromCache || reports.fromCache || notices.fromCache);
      },
      builder: (context, d, reload) {
        final reports = d['reports'] as List<Report>;
        int count(String st) => reports.where((r) => r.status == st).length;
        Widget tile(IconData icon, int n, String label, String tab, [Color color = brandBlue]) =>
            Expanded(child: StatTile(icon: icon, value: '$n', label: label, color: color, onTap: () => goTo(tab)));
        return ListView(padding: const EdgeInsets.all(16), children: [
          HeroCard(title: s.fill('welcome', session.username ?? '')),
          Row(children: [tile(Icons.child_care, d['children'] as int, s.get('children'), 'children'), const SizedBox(width: 10), tile(Icons.edit_note, count('draft'), s.get('openReports'), 'reports', const Color(0xFF42536A))]),
          Row(children: [tile(Icons.hourglass_bottom, count('submitted'), s.get('submitted'), 'reports', const Color(0xFF8A5200)), const SizedBox(width: 10), tile(Icons.undo, count('rejected'), s.get('returned'), 'reports', const Color(0xFFB3402F))]),
          const SizedBox(height: 14),
          Row(children: [
            Expanded(child: QuickAction(icon: Icons.add, label: s.get('newReport'), primary: true, onTap: () => goTo('children'))),
            const SizedBox(width: 10),
            Expanded(child: QuickAction(icon: Icons.folder_outlined, label: s.get('materials'), onTap: () => goTo('files'))),
          ]),
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
        return Cached(parseList(c.data, Child.fromJson), fromCache: c.fromCache);
      },
      builder: (context, children, reload) {
        if (children.isEmpty) return EmptyNote(s.get('noChildren'));
        return ListView(padding: const EdgeInsets.all(12), children: [
          for (final c in children)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Row(children: [
                    AvatarInitials(c.name, size: 56),
                    const SizedBox(width: 14),
                    Expanded(child: Text(c.name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
                  ]),
                  const SizedBox(height: 14),
                  FilledButton.icon(
                    style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(44)),
                    icon: const Icon(Icons.add, size: 20),
                    label: Text(s.get('newReport')),
                    onPressed: () async {
                      final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => ReportEditor(presetChild: c, children: children)));
                      if (saved == true) await reload();
                    },
                  ),
                ]),
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
        return Cached((parseList(reports.data, Report.fromJson), parseList(children.data, Child.fromJson)), fromCache: reports.fromCache || children.fromCache);
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
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                        leading: AvatarInitials(names[r.childId] ?? '?', size: 44),
                        title: Text(r.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                        subtitle: Text('${names[r.childId] ?? ''} · ${formatDate(r.createdAt)}'),
                        trailing: StatusPill(r.status),
                        onTap: () async {
                          final editable = r.status == 'draft' || r.status == 'rejected';
                          if (editable) {
                            final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => ReportEditor(report: r, children: children)));
                            if (saved == true) await reload();
                          } else {
                            await Navigator.push(context, MaterialPageRoute(builder: (_) => Scaffold(appBar: AppBar(title: Text(r.title)), body: ListView(padding: const EdgeInsets.all(12), children: [ReportCard(r, childName: names[r.childId], showStatus: true)]))));
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
  bool _dirty = false;

  /// The first change makes leaving the screen ask for a confirmation.
  void _touch() {
    if (!_dirty) setState(() => _dirty = true);
  }

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
      Future.microtask(_loadExisting);
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
      if (mounted) setState(() => _existing = parseList(data, FileInfo.fromJson));
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
      _dirty = false;
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
    final note = widget.report?.status == 'rejected' ? widget.report!.reviewNote : '';
    return PopScope(
      canPop: !_dirty || _busy,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        final navigator = Navigator.of(context);
        if (await confirmLeave(context)) navigator.pop();
      },
      child: Scaffold(
        appBar: AppBar(title: Text(widget.report == null ? s.get('newReport') : s.get('editReport'))),
        body: Column(children: [
          Expanded(
            child: AbsorbPointer(
              absorbing: _busy,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                if (_busy) const Padding(padding: EdgeInsets.only(bottom: 12), child: LinearProgressIndicator()),
                if (note.isNotEmpty)
                  Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(color: const Color(0xFFFDECEC), borderRadius: BorderRadius.circular(14)),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Icon(Icons.reply_outlined, color: Color(0xFFB3402F)),
                      const SizedBox(width: 8),
                      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(s.get('reviewNote'), style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFFB3402F))),
                        Text(note),
                      ])),
                    ]),
                  ),
                FormSection(
                  title: s.get('child'),
                  child: DropdownButtonFormField<String>(
                    initialValue: _childId,
                    decoration: InputDecoration(labelText: s.get('child')),
                    items: [for (final c in widget.children) DropdownMenuItem(value: c.id, child: Text(c.name))],
                    onChanged: widget.report == null ? (v) => setState(() => _childId = v) : null,
                  ),
                ),
                FormSection(
                  title: s.get('content'),
                  child: Column(children: [
                    TextField(controller: _title, maxLength: 120, onChanged: (_) { _touch(); _keepDraft(); }, decoration: InputDecoration(labelText: s.get('title'))),
                    const SizedBox(height: 8),
                    TextField(controller: _body, maxLength: 3000, minLines: 4, maxLines: 10, onChanged: (_) { _touch(); _keepDraft(); }, decoration: InputDecoration(labelText: s.get('text'))),
                    const SizedBox(height: 8),
                    TextField(controller: _activities, maxLength: 1000, minLines: 2, maxLines: 5, onChanged: (_) => _touch(), decoration: InputDecoration(labelText: s.get('activities'))),
                    const SizedBox(height: 8),
                    TextField(controller: _meals, maxLength: 500, minLines: 2, maxLines: 4, onChanged: (_) => _touch(), decoration: InputDecoration(labelText: s.get('meals'))),
                  ]),
                ),
                FormSection(
                  title: s.get('attachments'),
                  trailing: Text('${_existing.length + _files.length} / 5', style: const TextStyle(fontSize: 12.5, color: Color(0xFF6A7686))),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    for (final f in _existing) FileTile(file: f, path: '/api/platform/teacher/content/${f.id}/download'),
                    const SizedBox(height: 8),
                    AttachmentPicker(files: _files, max: 5 - _existing.length, onChanged: (v) => setState(() { _files = v; _dirty = true; })),
                  ]),
                ),
                if (_error != null)
                  Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(color: const Color(0xFFFDECEC), borderRadius: BorderRadius.circular(14)),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Icon(Icons.error_outline, size: 19, color: Color(0xFFB3402F)),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_error!, style: const TextStyle(color: Color(0xFF8A2D1F), height: 1.4))),
                    ]),
                  ),
                TextButton.icon(onPressed: _busy ? null : () => _save(parents: true), icon: const Icon(Icons.family_restroom), label: Text(s.get('sendParents'))),
                SizedBox(height: api.token == null ? 0 : 8),
              ]),
            ),
          ),
          BottomActionBar(children: [
            Expanded(child: OutlinedButton(style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(52)), onPressed: _busy ? null : () => _save(), child: Text(s.get('saveDraft')))),
            const SizedBox(width: 10),
            Expanded(flex: 2, child: FilledButton(onPressed: _busy ? null : () => _save(review: true), child: Text(s.get('sendReview')))),
          ]),
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
        return Cached((parseList(posts.data, Post.fromJson), parseList(children.data, Child.fromJson)), fromCache: posts.fromCache || children.fromCache);
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
class TeacherMaterials extends StatefulWidget {
  const TeacherMaterials({super.key});
  @override
  State<TeacherMaterials> createState() => _TeacherMaterialsState();
}

class _TeacherMaterialsState extends State<TeacherMaterials> {
  final Set<String> _selected = {};

  /// Asks for a title and the audience, then turns the ticked private files into learning material for the parents.
  Future<void> _share(List<MaterialFile> items, List<Child> children, Future<void> Function() reload) async {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    final chosen = items.where((m) => _selected.contains(m.id)).toList();
    if (chosen.isEmpty) return;
    final first = chosen.first.filename;
    final title = TextEditingController(text: first.contains('.') ? first.substring(0, first.lastIndexOf('.')) : first);
    var scope = 'general';
    String? childId;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => StatefulBuilder(
        builder: (context, setLocal) => AlertDialog(
          title: Text(s.get('shareSelected')),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              TextField(controller: title, maxLength: 120, decoration: InputDecoration(labelText: s.get('title'))),
              const SizedBox(height: 8),
              SegmentedButton<String>(
                segments: [ButtonSegment(value: 'general', label: Text(s.get('general'))), ButtonSegment(value: 'child', label: Text(s.get('private')))],
                selected: {scope},
                onSelectionChanged: (v) => setLocal(() => scope = v.first),
              ),
              if (scope == 'child') ...[
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: childId,
                  decoration: InputDecoration(labelText: s.get('child')),
                  items: [for (final c in children) DropdownMenuItem(value: c.id, child: Text(c.name))],
                  onChanged: (v) => setLocal(() => childId = v),
                ),
              ],
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.get('cancel'))),
            FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(110, 44)), onPressed: () => Navigator.pop(context, true), child: Text(s.get('publish'))),
          ],
        ),
      ),
    );
    if (ok != true || !mounted) return;
    if (title.text.trim().isEmpty || (scope == 'child' && childId == null)) {
      toast(context, s.get('required'));
      return;
    }
    try {
      await api.post('/api/platform/teacher/content/share', {
        'content_ids': chosen.map((m) => m.id).toList(),
        'scope': scope,
        'title': title.text.trim(),
        if (scope == 'child') 'child_id': childId,
      });
      setState(_selected.clear);
      await reload();
      if (mounted) toast(context, s.get('saved'));
    } on ApiException catch (e) {
      if (mounted) toast(context, e.problem == ApiProblem.bad && e.detail.isNotEmpty ? e.detail : problemText(context, e));
    }
  }

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
        final mine = parseList(items.data, MaterialFile.fromJson).where((m) => m.category != 'report_attachment').toList();
        final shared = parseList(posts.data, Post.fromJson).where((p) => p.kind == 'material').toList();
        return Cached((mine, storage.data as Map<String, dynamic>, shared, parseList(children.data, Child.fromJson)),
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
              MaterialSection(
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
            if (items.isNotEmpty)
              _selected.isEmpty
                  ? Padding(padding: const EdgeInsets.fromLTRB(4, 0, 4, 6), child: Text(s.get('selectToShare'), style: TextStyle(color: Colors.grey.shade700, fontSize: 13)))
                  : Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: FilledButton.icon(
                        onPressed: () => _share(items, children, reload),
                        icon: const Icon(Icons.family_restroom),
                        label: Text('${s.get('shareSelected')} (${_selected.length})'),
                      ),
                    ),
            if (items.isEmpty) Padding(padding: const EdgeInsets.all(24), child: Center(child: Text(s.get('noFiles')))),
            for (final m in items)
              Card(
                color: _selected.contains(m.id) ? const Color(0xFFF2F7FC) : null,
                child: ListTile(
                  contentPadding: const EdgeInsetsDirectional.fromSTEB(8, 6, 4, 6),
                  leading: Row(mainAxisSize: MainAxisSize.min, children: [
                    Checkbox(value: _selected.contains(m.id), onChanged: (v) => setState(() => v == true ? _selected.add(m.id) : _selected.remove(m.id))),
                    FileTypePlate(filename: m.filename, isImage: m.mediaType.startsWith('image/'), size: 40),
                  ]),
                  title: Text(m.filename, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Wrap(spacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
                      Pill(s.get('private'), icon: Icons.lock_outline, foreground: const Color(0xFF42536A)),
                      Text(formatSize(m.size), style: const TextStyle(fontSize: 12, color: Color(0xFF6A7686))),
                    ]),
                  ),
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
