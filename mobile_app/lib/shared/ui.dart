import 'dart:io';

import 'package:flutter/material.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';

import '../localization/strings.dart';
import '../models/models.dart';
import '../services/api.dart';
import '../services/session.dart';

// ---- colours of the kindergarten (same dark blue as the websites' header) ---------------------------------------------
const brandBlue = Color(0xFF16406F);
const brandDeep = Color(0xFF0E2E52);
const brandSoft = Color(0xFFEAF1F8);
const brandAccent = Color(0xFFE8A33D);
const _ink = Color(0xFF1B2533);
const _line = Color(0xFFE3E9F0);

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: brandBlue, primary: brandBlue, secondary: brandAccent, surface: Colors.white);
  final base = ThemeData(colorScheme: scheme, useMaterial3: true, fontFamily: 'Tajawal');
  return base.copyWith(
    scaffoldBackgroundColor: const Color(0xFFF4F7FB),
    textTheme: base.textTheme.apply(bodyColor: _ink, displayColor: _ink),
    appBarTheme: const AppBarTheme(
      backgroundColor: brandBlue,
      foregroundColor: Colors.white,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(fontFamily: 'Tajawal', fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 8,
      shadowColor: const Color(0x33000000),
      height: 68,
      indicatorColor: brandSoft,
      iconTheme: WidgetStateProperty.resolveWith((s) => IconThemeData(color: s.contains(WidgetState.selected) ? brandBlue : const Color(0xFF7A8798), size: 26)),
      labelTextStyle: WidgetStateProperty.resolveWith((s) => TextStyle(fontFamily: 'Tajawal', fontSize: 12, fontWeight: s.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500, color: s.contains(WidgetState.selected) ? brandBlue : const Color(0xFF7A8798))),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 6),
      clipBehavior: Clip.antiAlias,
      shadowColor: const Color(0x14000000),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18), side: const BorderSide(color: _line)),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: brandSoft,
      side: BorderSide.none,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      labelStyle: const TextStyle(fontFamily: 'Tajawal', color: brandBlue, fontWeight: FontWeight.w500),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _line)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _line)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: brandBlue, width: 1.6)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(52),
        textStyle: const TextStyle(fontFamily: 'Tajawal', fontSize: 16, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: brandBlue,
        side: const BorderSide(color: brandBlue),
        textStyle: const TextStyle(fontFamily: 'Tajawal', fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: brandAccent,
      foregroundColor: Colors.black87,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    snackBarTheme: SnackBarThemeData(behavior: SnackBarBehavior.floating, backgroundColor: brandDeep, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
    dividerTheme: const DividerThemeData(color: _line, space: 1),
  );
}

/// Easy access to the session from any screen.
class SessionScope extends InheritedNotifier<Session> {
  const SessionScope({super.key, required Session session, required super.child}) : super(notifier: session);
  static Session of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<SessionScope>()!.notifier!;
}

String problemText(BuildContext context, Object error, {bool login = false}) {
  final s = S.of(context);
  if (error is ApiException) {
    switch (error.problem) {
      case ApiProblem.offline:
        return s.get('offline');
      case ApiProblem.unauthorized:
        return login ? s.get('wrongLogin') : s.get('sessionEnded');
      case ApiProblem.tooMany:
        return s.get('tooMany');
      case ApiProblem.pending:
        return s.get('pending');
      case ApiProblem.disabled:
        return s.get('disabled');
      default:
        return s.get('serverError');
    }
  }
  return s.get('serverError');
}

void toast(BuildContext context, String text) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(text)));
}

String formatDate(DateTime? d) {
  if (d == null) return '';
  String two(int n) => n.toString().padLeft(2, '0');
  return '${d.year}-${two(d.month)}-${two(d.day)}';
}

String formatSize(int bytes) {
  if (bytes >= 1024 * 1024) return '${(bytes / 1024 / 1024).toStringAsFixed(1)} MB';
  if (bytes >= 1024) return '${(bytes / 1024).round()} KB';
  return '$bytes B';
}

class OfflineBanner extends StatelessWidget {
  const OfflineBanner({super.key});
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        color: const Color(0xFFFFF4D6),
        padding: const EdgeInsets.all(8),
        child: Text(S.of(context).get('showingSaved'), textAlign: TextAlign.center, style: const TextStyle(fontSize: 12)),
      );
}

/// Loads something, shows a spinner, an error with a retry button, or the result. `fromCache` shows a small notice.
class Loader<T> extends StatefulWidget {
  const Loader({super.key, required this.load, required this.builder});
  final Future<Cached<T>> Function() load;
  final Widget Function(BuildContext, T data, Future<void> Function() reload) builder;
  @override
  State<Loader<T>> createState() => _LoaderState<T>();
}

class _LoaderState<T> extends State<Loader<T>> {
  Cached<T>? _value;
  Object? _error;
  bool _busy = true;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    setState(() => _busy = _value == null);
    try {
      final v = await widget.load();
      if (!mounted) return;
      setState(() {
        _value = v;
        _error = null;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_busy) return const Center(child: CircularProgressIndicator());
    if (_value == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.wifi_off, size: 40, color: Colors.grey.shade500),
            const SizedBox(height: 12),
            Text(problemText(context, _error ?? ''), textAlign: TextAlign.center),
            const SizedBox(height: 12),
            OutlinedButton(onPressed: _reload, child: Text(S.of(context).get('retry'))),
          ]),
        ),
      );
    }
    return Column(children: [
      if (_value!.fromCache) const OfflineBanner(),
      Expanded(child: RefreshIndicator(onRefresh: _reload, child: widget.builder(context, _value!.data, _reload))),
    ]);
  }
}

class EmptyNote extends StatelessWidget {
  const EmptyNote(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => ListView(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(32, 72, 32, 32),
          child: Column(children: [
            Container(
              width: 84,
              height: 84,
              decoration: const BoxDecoration(color: brandSoft, shape: BoxShape.circle),
              child: const Icon(Icons.inbox_outlined, size: 40, color: brandBlue),
            ),
            const SizedBox(height: 16),
            Text(text, style: TextStyle(color: Colors.grey.shade700, fontSize: 16), textAlign: TextAlign.center),
          ]),
        ),
      ]);
}

/// The kindergarten logo on a white rounded plate, for the dark top bar.
class LogoPlate extends StatelessWidget {
  const LogoPlate({super.key, this.height = 38});
  final double height;
  @override
  Widget build(BuildContext context) => Container(
        height: height,
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(10)),
        child: Image.asset('assets/logo.png', fit: BoxFit.contain),
      );
}

/// Title of a page in the top bar: logo plate next to the page name.
class BarTitle extends StatelessWidget {
  const BarTitle(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => Row(children: [
        const LogoPlate(),
        const SizedBox(width: 12),
        Expanded(child: Text(text, overflow: TextOverflow.ellipsis)),
      ]);
}

/// The welcome card at the top of the home pages.
class HeroCard extends StatelessWidget {
  const HeroCard({super.key, required this.title, this.subtitle});
  final String title;
  final String? subtitle;
  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.fromLTRB(20, 22, 20, 22),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          gradient: const LinearGradient(colors: [brandBlue, brandDeep], begin: Alignment.topRight, end: Alignment.bottomLeft),
          boxShadow: const [BoxShadow(color: Color(0x2916406F), blurRadius: 18, offset: Offset(0, 8))],
        ),
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700, height: 1.3)),
              if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 4), child: Text(subtitle!, style: const TextStyle(color: Color(0xCCFFFFFF), fontSize: 14))),
            ]),
          ),
          const SizedBox(width: 12),
          const LogoPlate(height: 54),
        ]),
      );
}

/// A small number card (children, unread messages, ...) that opens a tab.
class StatTile extends StatelessWidget {
  const StatTile({super.key, required this.icon, required this.value, required this.label, required this.onTap, this.color = brandBlue});
  final IconData icon;
  final String value;
  final String label;
  final VoidCallback onTap;
  final Color color;
  @override
  Widget build(BuildContext context) => Card(
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(12)),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, height: 1.1)),
                  Text(label, maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12.5, color: Colors.grey.shade700)),
                ]),
              ),
            ]),
          ),
        ),
      );
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 20, 4, 6),
        child: Row(children: [
          Container(width: 4, height: 20, decoration: BoxDecoration(color: brandAccent, borderRadius: BorderRadius.circular(2))),
          const SizedBox(width: 8),
          Text(text, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700, color: brandBlue)),
        ]),
      );
}

/// Downloads a private file with the token into a temporary folder and opens it. Nothing public, nothing kept long.
Future<void> openPrivateFile(BuildContext context, ApiClient api, String path, String filename) async {
  try {
    final data = await api.bytes(path);
    final dir = await getTemporaryDirectory();
    final safe = filename.replaceAll(RegExp(r'[^\w.\- ]', unicode: true), '_');
    final file = File('${dir.path}/$safe');
    await file.writeAsBytes(data, flush: true);
    await OpenFilex.open(file.path);
  } catch (e) {
    if (context.mounted) toast(context, problemText(context, e));
  }
}

/// Asks before something is deleted.
Future<bool> confirmDelete(BuildContext context) async {
  final s = S.of(context);
  final ok = await showDialog<bool>(
    context: context,
    builder: (_) => AlertDialog(
      content: Text(s.get('confirmDelete')),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.get('cancel'))),
        FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(110, 44)), onPressed: () => Navigator.pop(context, true), child: Text(s.get('delete'))),
      ],
    ),
  );
  return ok == true;
}

/// A small dialog with one text field. Returns the typed text, or null when cancelled.
Future<String?> askText(BuildContext context, String title, {String initial = '', int maxLength = 180, int maxLines = 1, String confirm = 'save'}) {
  final s = S.of(context);
  final controller = TextEditingController(text: initial);
  return showDialog<String>(
    context: context,
    builder: (_) => AlertDialog(
      title: Text(title),
      content: TextField(controller: controller, autofocus: true, maxLength: maxLength, maxLines: maxLines, minLines: 1),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(s.get('cancel'))),
        FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(110, 44)), onPressed: () => Navigator.pop(context, controller.text.trim()), child: Text(s.get(confirm))),
      ],
    ),
  );
}

/// Asks whether unsaved work may be thrown away.
Future<bool> confirmLeave(BuildContext context) async {
  final s = S.of(context);
  final ok = await showDialog<bool>(
    context: context,
    builder: (_) => AlertDialog(
      content: Text(s.get('discardChanges')),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.get('cancel'))),
        FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(110, 44)), onPressed: () => Navigator.pop(context, true), child: Text(s.get('leave'))),
      ],
    ),
  );
  return ok == true;
}

/// The attachments of one report, loaded from the server (the list and the files depend on who is looking).
class ReportFiles extends StatefulWidget {
  const ReportFiles({super.key, required this.listPath, required this.filePath});
  final String listPath;
  final String Function(FileInfo) filePath;
  @override
  State<ReportFiles> createState() => _ReportFilesState();
}

class _ReportFilesState extends State<ReportFiles> {
  List<FileInfo> _files = [];

  @override
  void initState() {
    super.initState();
    Future.microtask(_load); // the session is looked up after the first build, not inside initState
  }

  Future<void> _load() async {
    try {
      final data = await SessionScope.of(context).api.get(widget.listPath);
      if (mounted) setState(() => _files = parseList(data, FileInfo.fromJson));
    } catch (_) {
      // the report itself stays readable without its files
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_files.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(S.of(context).get('attachments'), style: const TextStyle(fontWeight: FontWeight.w700, color: brandBlue)),
        for (final f in _files) FileTile(file: f, path: widget.filePath(f)),
      ]),
    );
  }
}

class FileTile extends StatelessWidget {
  const FileTile({super.key, required this.file, required this.path});
  final FileInfo file;
  final String path;
  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Material(
        color: brandSoft,
        borderRadius: BorderRadius.circular(12),
        clipBehavior: Clip.antiAlias,
        child: ListTile(
        dense: true,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        leading: Icon(file.isImage ? Icons.image_outlined : Icons.attach_file, color: brandBlue),
        title: Text(file.filename, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w500)),
        subtitle: Text(formatSize(file.size)),
        trailing: const Icon(Icons.download_outlined, color: brandBlue),
        onTap: () => openPrivateFile(context, api, path, file.filename),
        ),
      ),
    );
  }
}
