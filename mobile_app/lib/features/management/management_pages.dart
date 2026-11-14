import 'package:flutter/material.dart';

import '../../localization/strings.dart';
import '../../models/models.dart';
import '../../services/api.dart';
import '../../shared/ui.dart';
import '../parents/parent_pages.dart';
import '../teachers/teacher_pages.dart';

// ---- home --------------------------------------------------------------------------------------------------------------------
class ManagementHome extends StatelessWidget {
  const ManagementHome({super.key, required this.goTo});
  final void Function(String) goTo;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final session = SessionScope.of(context);
    final api = session.api;
    return Loader<(List<Report>, List<Post>)>(
      load: () async {
        final reports = await api.getCached('/api/platform/review/reports');
        final sections = await api.getCached('/api/platform/manager/materials');
        return Cached((parseList(reports.data, Report.fromJson), parseList(sections.data, Post.fromJson)), fromCache: reports.fromCache || sections.fromCache);
      },
      builder: (context, d, reload) {
        final (reports, sections) = d;
        Widget tile(IconData icon, int n, String label, String tab, [Color color = brandBlue]) =>
            Expanded(child: StatTile(icon: icon, value: '$n', label: label, color: color, onTap: () => goTo(tab)));
        return RefreshIndicator(
          onRefresh: reload,
          child: ListView(padding: const EdgeInsets.all(16), children: [
            HeroCard(title: s.fill('welcome', session.username ?? '')),
            Row(children: [
              tile(Icons.hourglass_bottom, reports.length, s.get('toReview'), 'review', const Color(0xFF8A5200)),
              const SizedBox(width: 10),
              tile(Icons.school_outlined, sections.length, s.get('sectionsCount'), 'course'),
            ]),
            Row(children: [
              tile(Icons.visibility_off_outlined, sections.where((p) => p.hidden).length, s.get('hiddenCount'), 'course', const Color(0xFF6B7785)),
              const Expanded(child: SizedBox()),
            ]),
            const SizedBox(height: 14),
            Row(children: [
              Expanded(child: QuickAction(icon: Icons.fact_check_outlined, label: s.get('reviewReports'), primary: true, onTap: () => goTo('review'))),
              const SizedBox(width: 10),
              Expanded(child: QuickAction(icon: Icons.add, label: s.get('newSection'), onTap: () => goTo('course'))),
            ]),
          ]),
        );
      },
    );
  }
}

// ---- reports waiting for the management --------------------------------------------------------------------------------------
class ReviewReports extends StatelessWidget {
  const ReviewReports({super.key});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<List<Report>>(
      load: () async {
        final r = await api.getCached('/api/platform/review/reports');
        return Cached(parseList(r.data, Report.fromJson), fromCache: r.fromCache);
      },
      builder: (context, reports, reload) {
        if (reports.isEmpty) return EmptyNote(s.get('noReportsToReview'));
        return RefreshIndicator(
          onRefresh: reload,
          child: ListView(padding: const EdgeInsets.all(12), children: [
            for (final r in reports)
              Card(
                child: ListTile(
                  leading: const CircleAvatar(backgroundColor: brandSoft, child: Icon(Icons.description_outlined, color: brandBlue)),
                  title: Text(r.title, style: const TextStyle(fontWeight: FontWeight.bold)),
                  subtitle: Text([if (r.childName.isNotEmpty) r.childName, formatDate(r.createdAt)].join(' · ')),
                  trailing: const StatusPill('submitted'),
                  onTap: () async {
                    final done = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => _ReviewPage(r)));
                    if (done == true) await reload();
                  },
                ),
              ),
          ]),
        );
      },
    );
  }
}

class _ReviewPage extends StatefulWidget {
  const _ReviewPage(this.report);
  final Report report;
  @override
  State<_ReviewPage> createState() => _ReviewPageState();
}

class _ReviewPageState extends State<_ReviewPage> {
  bool _busy = false;

  Future<void> _decide(String status) async {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    String note = '';
    if (status == 'rejected') {
      final typed = await askText(context, s.get('returnReport'), maxLength: 500, maxLines: 4, confirm: 'returnReport');
      if (typed == null || !mounted) return;
      note = typed;
    }
    setState(() => _busy = true);
    try {
      await api.patch('/api/platform/review/reports/${widget.report.id}', {'status': status, if (note.isNotEmpty) 'note': note});
      if (!mounted) return;
      toast(context, s.get(status == 'published' ? 'reportPublished' : 'reportReturned'));
      Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(widget.report.title)),
      body: ListView(padding: const EdgeInsets.all(12), children: [
        if (_busy) const Padding(padding: EdgeInsets.only(bottom: 12), child: LinearProgressIndicator()),
        ReportCard(widget.report, childName: widget.report.childName.isEmpty ? null : widget.report.childName, files: 'review'),
        const SizedBox(height: 12),
        FilledButton.icon(onPressed: _busy ? null : () => _decide('published'), icon: const Icon(Icons.send), label: Text(s.get('publishReport'))),
        const SizedBox(height: 10),
        OutlinedButton.icon(onPressed: _busy ? null : () => _decide('rejected'), icon: const Icon(Icons.undo), label: Text(s.get('returnReport'))),
      ]),
    );
  }
}

// ---- the course editor: sections and files, like Moodle's edit mode -------------------------------------------------------------
class CourseEditor extends StatelessWidget {
  const CourseEditor({super.key});

  static String _file(Post p, FileInfo f) => '/api/platform/manager/materials/${p.id}/files/${f.id}';

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<List<Post>>(
      load: () async {
        final r = await api.getCached('/api/platform/manager/materials');
        return Cached(parseList(r.data, Post.fromJson), fromCache: r.fromCache);
      },
      builder: (context, sections, reload) {
        Future<void> run(Future<dynamic> Function() action) async {
          try {
            await action();
            await reload();
          } on ApiException catch (e) {
            if (context.mounted) toast(context, e.problem == ApiProblem.bad && e.detail.isNotEmpty ? e.detail : problemText(context, e));
          }
        }

        Future<void> addFiles(Post p) async {
          final picked = await showDialog<List<UploadFile>>(context: context, builder: (_) => _FilesDialog(title: s.get('addFiles')));
          if (picked == null || picked.isEmpty) return;
          await run(() => api.multipart('/api/platform/manager/materials/${p.id}/files', {}, picked));
        }

        Future<void> rename(Post p, FileInfo f) async {
          final name = await askText(context, s.get('renameFile'), initial: f.filename);
          if (name == null || name.isEmpty || name == f.filename) return;
          await run(() => api.patch(_file(p, f), {'name': name}));
        }

        return Scaffold(
          backgroundColor: Colors.transparent,
          floatingActionButton: FloatingActionButton.extended(
            backgroundColor: brandAccent,
            icon: const Icon(Icons.add),
            label: Text(s.get('newSection')),
            onPressed: () async {
              final created = await showDialog<bool>(context: context, builder: (_) => const _SectionDialog());
              if (created == true) await reload();
            },
          ),
          body: sections.isEmpty
              ? EmptyNote(s.get('noSections'))
              : RefreshIndicator(
                  onRefresh: reload,
                  child: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 96), children: [
                    for (final (i, p) in sections.indexed)
                      MaterialSection(
                        p,
                        key: ValueKey('${p.id}-${p.hidden}-${p.title}-${p.files.length}'),
                        filePath: _file,
                        headerActions: [
                          PopupMenuButton<String>(
                            icon: const Icon(Icons.more_vert),
                            onSelected: (v) async {
                              switch (v) {
                                case 'edit':
                                  final saved = await showDialog<bool>(context: context, builder: (_) => _SectionDialog(section: p));
                                  if (saved == true) await reload();
                                case 'visible':
                                  await run(() => api.patch('/api/platform/manager/materials/${p.id}', {'hidden': !p.hidden}));
                                case 'up':
                                  await run(() => api.post('/api/platform/manager/materials/${p.id}/move', {'direction': 'up'}));
                                case 'down':
                                  await run(() => api.post('/api/platform/manager/materials/${p.id}/move', {'direction': 'down'}));
                                case 'add':
                                  await addFiles(p);
                                case 'delete':
                                  if (await confirmDelete(context)) await run(() => api.delete('/api/platform/manager/materials/${p.id}'));
                              }
                            },
                            itemBuilder: (_) => [
                              _item('edit', Icons.edit_outlined, s.get('editSection')),
                              _item('add', Icons.upload_file, s.get('addFiles')),
                              _item('visible', p.hidden ? Icons.visibility_outlined : Icons.visibility_off_outlined, s.get(p.hidden ? 'showSection' : 'hideSection')),
                              if (i > 0) _item('up', Icons.arrow_upward, s.get('moveUp')),
                              if (i < sections.length - 1) _item('down', Icons.arrow_downward, s.get('moveDown')),
                              _item('delete', Icons.delete_outline, s.get('deleteSection')),
                            ],
                          ),
                        ],
                        fileTrailing: (f) => PopupMenuButton<String>(
                          icon: const Icon(Icons.more_vert, size: 22),
                          onSelected: (v) async {
                            if (v == 'rename') {
                              await rename(p, f);
                            } else if (v == 'delete' && await confirmDelete(context)) {
                              await run(() => api.delete(_file(p, f)));
                            }
                          },
                          itemBuilder: (_) => [
                            _item('rename', Icons.drive_file_rename_outline, s.get('renameFile')),
                            _item('delete', Icons.delete_outline, s.get('deleteFile')),
                          ],
                        ),
                        footer: Padding(
                          padding: const EdgeInsets.fromLTRB(12, 4, 12, 4),
                          child: Align(alignment: AlignmentDirectional.centerStart, child: TextButton.icon(onPressed: () => addFiles(p), icon: const Icon(Icons.add), label: Text(s.get('addFiles')))),
                        ),
                      ),
                  ]),
                ),
        );
      },
    );
  }

  static PopupMenuItem<String> _item(String value, IconData icon, String label) =>
      PopupMenuItem(value: value, child: Row(children: [Icon(icon, size: 20), const SizedBox(width: 12), Flexible(child: Text(label))]));
}

/// Picks files to add to an existing section.
class _FilesDialog extends StatefulWidget {
  const _FilesDialog({required this.title});
  final String title;
  @override
  State<_FilesDialog> createState() => _FilesDialogState();
}

class _FilesDialogState extends State<_FilesDialog> {
  List<UploadFile> _files = [];
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return AlertDialog(
      title: Text(widget.title),
      content: SingleChildScrollView(child: AttachmentPicker(files: _files, onChanged: (v) => setState(() => _files = v))),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(s.get('cancel'))),
        FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(110, 44)), onPressed: _files.isEmpty ? null : () => Navigator.pop(context, _files), child: Text(s.get('save'))),
      ],
    );
  }
}

/// Creates a new section, or edits the title and description of an existing one.
class _SectionDialog extends StatefulWidget {
  const _SectionDialog({this.section});
  final Post? section;
  @override
  State<_SectionDialog> createState() => _SectionDialogState();
}

class _SectionDialogState extends State<_SectionDialog> {
  late final _title = TextEditingController(text: widget.section?.title ?? '');
  late final _body = TextEditingController(text: widget.section?.body ?? '');
  List<UploadFile> _files = [];
  bool _hidden = false;
  bool _busy = false;

  Future<void> _save() async {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    if (_title.text.trim().isEmpty) {
      toast(context, s.get('required'));
      return;
    }
    setState(() => _busy = true);
    try {
      if (widget.section == null) {
        await api.multipart('/api/platform/manager/materials', {'title': _title.text.trim(), 'body': _body.text.trim(), 'hidden': '$_hidden'}, _files);
      } else {
        await api.patch('/api/platform/manager/materials/${widget.section!.id}', {'title': _title.text.trim(), 'body': _body.text.trim()});
      }
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) toast(context, e.problem == ApiProblem.bad && e.detail.isNotEmpty ? e.detail : problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final isNew = widget.section == null;
    return AlertDialog(
      title: Text(s.get(isNew ? 'newSection' : 'editSection')),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (_busy) const Padding(padding: EdgeInsets.only(bottom: 12), child: LinearProgressIndicator()),
            TextField(controller: _title, maxLength: 120, decoration: InputDecoration(labelText: s.get('sectionTitle'))),
            TextField(controller: _body, maxLines: 3, maxLength: 3000, decoration: InputDecoration(labelText: s.get('description'))),
            if (isNew) ...[
              SwitchListTile(contentPadding: EdgeInsets.zero, title: Text(s.get('hideSection')), value: _hidden, onChanged: (v) => setState(() => _hidden = v)),
              AttachmentPicker(files: _files, onChanged: (v) => setState(() => _files = v)),
            ],
          ]),
        ),
      ),
      actions: [
        TextButton(onPressed: _busy ? null : () => Navigator.pop(context), child: Text(s.get('cancel'))),
        FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(110, 44)), onPressed: _busy ? null : _save, child: Text(s.get('save'))),
      ],
    );
  }
}
