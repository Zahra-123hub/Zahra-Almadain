import 'package:flutter/material.dart';

import '../../config/config.dart';
import '../../localization/strings.dart';
import '../../models/models.dart';
import '../../services/api.dart';
import '../../design/shell.dart';
import '../../shared/ui.dart';

String notificationText(S s, AppNotification n) {
  final key = 'n_${n.kind}';
  final text = s.fill(key, n.subject);
  return text == key ? n.subject : text;
}

// ---- notifications ---------------------------------------------------------------------------------------------------
class NotificationsPage extends StatelessWidget {
  const NotificationsPage({super.key, this.onChanged});
  final VoidCallback? onChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<Map<String, dynamic>>(
      load: () async {
        final c = await api.getCached('/api/platform/notifications');
        return Cached(c.data as Map<String, dynamic>, fromCache: c.fromCache);
      },
      builder: (context, data, reload) {
        final items = ((data['items'] as List?) ?? []).map((e) => AppNotification.fromJson(e as Map<String, dynamic>)).toList();
        if (items.isEmpty) return EmptyNote(s.get('noNotifications'));
        return ListView(padding: const EdgeInsets.all(12), children: [
          if ((data['unread'] as num? ?? 0) > 0)
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: TextButton.icon(
                icon: const Icon(Icons.done_all),
                label: Text(s.get('readAll')),
                onPressed: () async {
                  try {
                    await api.post('/api/platform/notifications/read-all');
                    await reload();
                    onChanged?.call();
                  } catch (e) {
                    if (context.mounted) toast(context, problemText(context, e));
                  }
                },
              ),
            ),
          for (final n in items)
            Card(
              child: ListTile(
                leading: Icon(n.read ? Icons.notifications_none : Icons.notifications_active, color: n.read ? Colors.grey : brandAccent),
                title: Text(notificationText(s, n), style: TextStyle(fontWeight: n.read ? FontWeight.normal : FontWeight.bold)),
                subtitle: Text(formatDate(n.createdAt)),
                onTap: n.read
                    ? null
                    : () async {
                        try {
                          await api.post('/api/platform/notifications/${n.id}/read');
                          await reload();
                          onChanged?.call();
                        } catch (_) {}
                      },
              ),
            ),
        ]);
      },
    );
  }
}

// ---- notices of the management -----------------------------------------------------------------------------------------
class NoticeCards extends StatelessWidget {
  const NoticeCards(this.notices, {super.key});
  final List<Notice> notices;
  @override
  Widget build(BuildContext context) {
    return Column(children: [
      for (final n in notices)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const Icon(Icons.campaign_outlined, color: brandAccent),
                const SizedBox(width: 8),
                Expanded(child: Text(n.title, style: const TextStyle(fontWeight: FontWeight.bold))),
              ]),
              if (n.body.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text(n.body)),
              Padding(padding: const EdgeInsets.only(top: 6), child: Text(formatDate(n.createdAt), style: const TextStyle(fontSize: 12, color: Colors.grey))),
            ]),
          ),
        ),
    ]);
  }
}

// ---- profile and settings ------------------------------------------------------------------------------------------------
class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final session = SessionScope.of(context);
    return ListView(padding: const EdgeInsets.all(16), children: [
      Card(
        child: ListTile(
          leading: const CircleAvatar(backgroundColor: brandSoft, child: Icon(Icons.person, color: brandBlue)),
          title: Text(session.username ?? ''),
          subtitle: Text(session.roles.join(', ')),
        ),
      ),
      if (session.areas.length > 1) ...[
        SectionTitle(s.get('switchArea')),
        const AreaSwitcher(light: true),
      ],
      SectionTitle(s.get('language')),
      Card(
        child: RadioGroup<String>(
          groupValue: session.locale.languageCode,
          onChanged: (v) => session.setLocale(v!),
          child: Column(children: [
            for (final entry in const {'ar': 'العربية', 'de': 'Deutsch', 'en': 'English'}.entries)
              RadioListTile<String>(value: entry.key, title: Text(entry.value)),
          ]),
        ),
      ),
      Card(
        child: ListTile(
          leading: const Icon(Icons.lock_outline),
          title: Text(s.get('changePassword')),
          onTap: () => showDialog(context: context, builder: (_) => const _PasswordDialog()),
        ),
      ),
      Card(
        child: ListTile(
          leading: const Icon(Icons.logout, color: Colors.red),
          title: Text(s.get('signOut')),
          onTap: () => session.logout(),
        ),
      ),
      Padding(
        padding: const EdgeInsets.only(top: 12),
        child: Center(child: Text('${s.get('version')} ${AppConfig.version}', style: const TextStyle(color: Colors.grey, fontSize: 12))),
      ),
    ]);
  }
}

class _PasswordDialog extends StatefulWidget {
  const _PasswordDialog();
  @override
  State<_PasswordDialog> createState() => _PasswordDialogState();
}

class _PasswordDialogState extends State<_PasswordDialog> {
  final current = TextEditingController();
  final fresh = TextEditingController();
  String? error;
  bool busy = false;

  Future<void> _save() async {
    final session = SessionScope.of(context);
    final s = S.of(context);
    if (current.text.isEmpty || fresh.text.length < 8) {
      setState(() => error = s.get('required'));
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await session.api.post('/api/platform/auth/change-password', {'current_password': current.text, 'new_password': fresh.text});
      if (!mounted) return;
      Navigator.pop(context);
      toast(context, s.get('passwordChanged'));
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        busy = false;
        error = e.detail.isNotEmpty && e.problem == ApiProblem.bad ? e.detail : problemText(context, e, login: true);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return AlertDialog(
      title: Text(s.get('changePassword')),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: current, obscureText: true, decoration: InputDecoration(labelText: s.get('currentPassword'))),
        const SizedBox(height: 12),
        TextField(controller: fresh, obscureText: true, decoration: InputDecoration(labelText: s.get('newPassword'))),
        if (error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(error!, style: const TextStyle(color: Colors.red))),
      ]),
      actions: [
        TextButton(onPressed: busy ? null : () => Navigator.pop(context), child: Text(s.get('cancel'))),
        FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(90, 40)), onPressed: busy ? null : _save, child: Text(s.get('save'))),
      ],
    );
  }
}
