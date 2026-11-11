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
const brandSoft = Color(0xFFEAF1F8);
const brandAccent = Color(0xFFE8A33D);

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: brandBlue, primary: brandBlue, secondary: brandAccent);
  return ThemeData(
    colorScheme: scheme,
    useMaterial3: true,
    scaffoldBackgroundColor: const Color(0xFFF6F8FB),
    appBarTheme: const AppBarTheme(backgroundColor: brandBlue, foregroundColor: Colors.white, centerTitle: true),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: Color(0xFFE2E8F0))),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
    ),
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
        Padding(padding: const EdgeInsets.all(32), child: Center(child: Text(text, style: TextStyle(color: Colors.grey.shade600), textAlign: TextAlign.center))),
      ]);
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) =>
      Padding(padding: const EdgeInsets.fromLTRB(4, 16, 4, 4), child: Text(text, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)));
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

class FileTile extends StatelessWidget {
  const FileTile({super.key, required this.file, required this.path});
  final FileInfo file;
  final String path;
  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Icon(file.isImage ? Icons.image_outlined : Icons.attach_file),
      title: Text(file.filename, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Text(formatSize(file.size)),
      trailing: const Icon(Icons.download_outlined),
      onTap: () => openPrivateFile(context, api, path, file.filename),
    );
  }
}
