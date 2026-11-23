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
/// Each kind of notification with its own icon and colour, so the important ones stand out at a glance.
({IconData icon, Color color}) _notificationLook(String kind) => switch (kind) {
      'report_published' => (icon: Icons.description_rounded, color: const Color(0xFF1E7A45)),
      'report_returned' => (icon: Icons.undo_rounded, color: const Color(0xFFB7791F)),
      'report_submitted' => (icon: Icons.fact_check_rounded, color: brandBlue),
      'report_direct' => (icon: Icons.mark_email_read_rounded, color: brandBlue),
      'post_new' => (icon: Icons.forum_rounded, color: const Color(0xFF7A4FB3)),
      'announcement' => (icon: Icons.campaign_rounded, color: const Color(0xFFC0392B)),
      'note_praise' => (icon: Icons.star_rounded, color: const Color(0xFF5FA34C)),
      'note_note' => (icon: Icons.edit_note_rounded, color: const Color(0xFF5C8FE0)),
      'bring_new' => (icon: Icons.backpack_rounded, color: const Color(0xFFE5952B)),
      'plan_changed' => (icon: Icons.calendar_view_week_rounded, color: const Color(0xFF5C8FE0)),
      'absence_reported' => (icon: Icons.sick_rounded, color: const Color(0xFFCF5443)),
      'message_new' => (icon: Icons.chat_rounded, color: const Color(0xFF368F81)),
      _ => (icon: Icons.notifications_rounded, color: const Color(0xFF5B6878)),
    };

/// "14:05" today, "yesterday 14:05", otherwise the date.
String _notificationTime(S s, DateTime? at) {
  if (at == null) return '';
  final l = at.toLocal();
  final now = DateTime.now();
  String two(int n) => n.toString().padLeft(2, '0');
  final clock = '${two(l.hour)}:${two(l.minute)}';
  final day = DateTime(l.year, l.month, l.day);
  final today = DateTime(now.year, now.month, now.day);
  if (day == today) return clock;
  if (day == today.subtract(const Duration(days: 1))) return '${s.get('yesterday')} $clock';
  return formatDate(l);
}

class NotificationsPage extends StatelessWidget {
  const NotificationsPage({super.key, this.onChanged, this.goTo});
  final VoidCallback? onChanged;

  /// Opens the page a notification points to (reports, review, home ...), when the area has it.
  final void Function(String id)? goTo;

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
        final unread = (data['unread'] as num? ?? items.where((n) => !n.read).length).toInt();
        final now = DateTime.now();
        final today = DateTime(now.year, now.month, now.day);
        String groupOf(AppNotification n) {
          final at = n.createdAt?.toLocal();
          if (at == null) return 'earlier';
          final day = DateTime(at.year, at.month, at.day);
          if (day == today) return 'today';
          if (day == today.subtract(const Duration(days: 1))) return 'yesterday';
          if (today.difference(day).inDays < 7) return 'thisWeek';
          return 'earlier';
        }

        Future<void> open(AppNotification n) async {
          if (!n.read) {
            try {
              await api.post('/api/platform/notifications/${n.id}/read');
              onChanged?.call();
            } catch (_) {}
          }
          if (!context.mounted) return;
          if (n.view.isNotEmpty && goTo != null) {
            final navigator = Navigator.of(context);
            if (navigator.canPop()) navigator.pop(); // opened over the area on a phone: back to the area first
            goTo!(n.view);
          } else {
            await reload();
          }
        }

        final groups = <String, List<AppNotification>>{};
        for (final n in items) {
          groups.putIfAbsent(groupOf(n), () => []).add(n);
        }
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 820),
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 24), children: [
              // the summary: how many are new, and one button to clear them
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: unread > 0 ? brandBlue : Colors.white,
                  borderRadius: BorderRadius.circular(18),
                  border: unread > 0 ? null : Border.all(color: const Color(0xFFE3E9F0)),
                ),
                child: Row(children: [
                  Container(
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(color: unread > 0 ? Colors.white.withValues(alpha: 0.15) : brandSoft, borderRadius: BorderRadius.circular(14)),
                    child: Icon(unread > 0 ? Icons.notifications_active_rounded : Icons.notifications_none_rounded, color: unread > 0 ? Colors.white : brandBlue),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      unread > 0 ? s.fill('unreadCount', '$unread') : s.get('allRead'),
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: unread > 0 ? Colors.white : const Color(0xFF1B2533)),
                    ),
                  ),
                  if (unread > 0)
                    TextButton.icon(
                      style: TextButton.styleFrom(foregroundColor: Colors.white),
                      icon: const Icon(Icons.done_all_rounded),
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
                ]),
              ),
              for (final key in const ['today', 'yesterday', 'thisWeek', 'earlier'])
                if (groups[key] != null) ...[
                  Padding(
                    padding: const EdgeInsets.fromLTRB(4, 20, 4, 8),
                    child: Text(s.get(key), style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800, color: Color(0xFF5B6878))),
                  ),
                  for (final n in groups[key]!) _NotificationTile(n: n, onTap: () => open(n), canOpen: n.view.isNotEmpty && goTo != null),
                ],
            ]),
          ),
        );
      },
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.n, required this.onTap, required this.canOpen});
  final AppNotification n;
  final VoidCallback onTap;
  final bool canOpen;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final look = _notificationLook(n.kind);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: n.read ? Colors.white : const Color(0xFFF1F6FC),
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: n.read ? const Color(0xFFE3E9F0) : brandBlue.withValues(alpha: 0.25)),
            ),
            child: Row(children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(color: look.color.withValues(alpha: n.read ? 0.08 : 0.14), borderRadius: BorderRadius.circular(14)),
                child: Icon(look.icon, color: n.read ? look.color.withValues(alpha: 0.6) : look.color, size: 23),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(
                    notificationText(s, n),
                    style: TextStyle(fontSize: 15, height: 1.35, fontWeight: n.read ? FontWeight.w500 : FontWeight.w800, color: n.read ? const Color(0xFF42536A) : const Color(0xFF1B2533)),
                  ),
                  const SizedBox(height: 3),
                  Text(_notificationTime(s, n.createdAt), textDirection: TextDirection.ltr, style: const TextStyle(fontSize: 12.5, color: Color(0xFF7A8797))),
                ]),
              ),
              if (!n.read)
                Container(width: 10, height: 10, margin: const EdgeInsetsDirectional.only(start: 8), decoration: const BoxDecoration(color: brandAccent, shape: BoxShape.circle)),
              if (canOpen) const Padding(padding: EdgeInsetsDirectional.only(start: 4), child: Icon(Icons.chevron_right_rounded, color: Color(0xFFB8C2CE))),
            ]),
          ),
        ),
      ),
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
