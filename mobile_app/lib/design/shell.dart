import 'package:flutter/material.dart';

import '../localization/strings.dart';
import '../services/session.dart';
import '../shared/ui.dart';
import 'tokens.dart';

/// One place the user can go to: a bottom-bar tab, or (on a wide window) an entry of the sidebar.
class ShellItem {
  const ShellItem({required this.id, required this.icon, required this.activeIcon, required this.label, required this.page});
  final String id;
  final IconData icon;
  final IconData activeIcon;
  final String label;
  final Widget Function(void Function(String id) goTo) page;
}

/// Shows a newer-version hint when the server offers one.
class UpdateHint extends StatelessWidget {
  const UpdateHint({super.key});
  @override
  Widget build(BuildContext context) {
    final info = SessionScope.of(context).versionInfo;
    if (info?.updateAvailable != true) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      color: const Color(0xFFE6F2FF),
      padding: const EdgeInsets.all(8),
      child: Text(S.of(context).get('updateAvailable'), textAlign: TextAlign.center, style: const TextStyle(fontSize: 12)),
    );
  }
}

/// The blue top zone: rounded at the bottom, one title, the bell with the number of unread messages.
class AppHeader extends StatelessWidget {
  const AppHeader({super.key, required this.title, this.subtitle, this.onBack, this.onBell, this.trailing, this.besideSidebar = false});
  final String title;
  final String? subtitle;
  final VoidCallback? onBack;
  final VoidCallback? onBell;
  final Widget? trailing;

  /// In a wide window the sidebar sits right next to the header, so the corner on that side stays square.
  final bool besideSidebar;

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.paddingOf(context).top;
    return Container(
      width: double.infinity,
      padding: EdgeInsets.fromLTRB(Gap.l, top + Gap.m, Gap.m, Gap.l),
      decoration: BoxDecoration(
        color: brandBlue,
        borderRadius: besideSidebar ? const BorderRadiusDirectional.only(bottomEnd: Radius.circular(Rad.l)) : const BorderRadius.vertical(bottom: Radius.circular(Rad.l)),
      ),
      child: Row(children: [
        if (onBack != null)
          Padding(
            padding: const EdgeInsetsDirectional.only(end: Gap.s),
            child: IconButton(
              tooltip: S.of(context).get('back'),
              onPressed: onBack,
              icon: const Icon(Icons.arrow_back_ios_new_rounded, color: Colors.white, size: 20),
            ),
          ),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w700, height: 1.2)),
            if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 2), child: Text(subtitle!, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Color(0xFFC9DAEC), fontSize: 13))),
          ]),
        ),
        ?trailing,
        if (onBell != null) NotificationBell(onTap: onBell!),
      ]),
    );
  }
}

/// The bell with the number of unread notifications (read from the same list the notifications page shows).
class NotificationBell extends StatefulWidget {
  const NotificationBell({super.key, required this.onTap});
  final VoidCallback onTap;
  @override
  State<NotificationBell> createState() => NotificationBellState();
}

class NotificationBellState extends State<NotificationBell> {
  int _unread = 0;

  @override
  void initState() {
    super.initState();
    Future.microtask(reload);
  }

  Future<void> reload() async {
    try {
      final c = await SessionScope.of(context).api.getCached('/api/platform/notifications');
      final n = ((c.data as Map<String, dynamic>)['unread'] as num? ?? 0).toInt();
      if (mounted) setState(() => _unread = n);
    } catch (_) {
      // the bell stays quiet when the list cannot be loaded
    }
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: S.of(context).get('notifications'),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () async {
          widget.onTap();
          await Future<void>.delayed(const Duration(milliseconds: 600));
          if (mounted) await reload();
        },
        child: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(14)),
          child: Stack(alignment: Alignment.center, children: [
            const Icon(Icons.notifications_none_rounded, color: Colors.white, size: 24),
            if (_unread > 0)
              PositionedDirectional(
                top: 5,
                end: 5,
                child: Container(
                  constraints: const BoxConstraints(minWidth: 18),
                  height: 18,
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  decoration: BoxDecoration(color: brandAccent, borderRadius: BorderRadius.circular(9)),
                  alignment: Alignment.center,
                  child: Text(_unread > 99 ? '99+' : '$_unread', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: brandBlue)),
                ),
              ),
          ]),
        ),
      ),
    );
  }
}

/// A page opened from "More" or the bell: same blue top zone with a back button.
class SubPage extends StatelessWidget {
  const SubPage({super.key, required this.title, required this.child});
  final String title;
  final Widget child;
  @override
  Widget build(BuildContext context) => Scaffold(
        body: Column(children: [
          AppHeader(title: title, onBack: () => Navigator.maybePop(context)),
          Expanded(child: child),
        ]),
      );
}

/// The frame of every area: phones get a bottom bar (at most five goals, the rest under "More"),
/// wide windows get a sidebar with everything in one list.
class AdaptiveShell extends StatefulWidget {
  const AdaptiveShell({super.key, required this.roleLabel, required this.items, this.more = const []});
  final String roleLabel;
  final List<ShellItem> items;
  final List<ShellItem> more;

  @override
  State<AdaptiveShell> createState() => _AdaptiveShellState();
}

class _AdaptiveShellState extends State<AdaptiveShell> {
  late String _id = widget.items.first.id;
  static const _moreId = '_more';

  List<ShellItem> get _all => [...widget.items, ...widget.more];

  void _goTo(String id) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    final inMore = widget.more.any((m) => m.id == id);
    if (inMore && !wide) {
      _openSub(widget.more.firstWhere((m) => m.id == id));
    } else {
      setState(() => _id = id);
    }
  }

  void _openSub(ShellItem item) {
    Navigator.push(context, MaterialPageRoute<void>(builder: (_) => SubPage(title: item.label, child: item.page(_goTo))));
  }

  void _openBell() {
    final notifications = _all.where((i) => i.id == 'notifications');
    if (notifications.isEmpty) return;
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    if (wide) {
      setState(() => _id = 'notifications');
    } else {
      _openSub(notifications.first);
    }
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= Breakpoints.wide;
    final s = S.of(context);
    final current = _id == _moreId ? null : _all.firstWhere((i) => i.id == _id, orElse: () => widget.items.first);
    final title = current?.label ?? s.get('more');
    final Widget body = _id == _moreId
        ? _MorePage(items: widget.more, onOpen: _openSub)
        : current!.page(_goTo);
    final content = AnimatedSwitcher(
      duration: Dur.normal,
      child: KeyedSubtree(key: ValueKey(_id), child: body),
    );

    if (wide) {
      return Scaffold(
        body: Row(children: [
          _Sidebar(roleLabel: widget.roleLabel, items: _all, selected: _id, onSelect: (id) => setState(() => _id = id)),
          Expanded(
            child: Column(children: [
              AppHeader(title: title, onBell: _openBell, besideSidebar: true),
              const UpdateHint(),
              Expanded(child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: Breakpoints.content), child: content))),
            ]),
          ),
        ]),
      );
    }

    final bottomIndex = _id == _moreId || widget.more.any((m) => m.id == _id) ? widget.items.length : widget.items.indexWhere((i) => i.id == _id);
    return Scaffold(
      body: Column(children: [
        AppHeader(title: title, onBell: _openBell),
        const UpdateHint(),
        Expanded(child: content),
      ]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: bottomIndex < 0 ? 0 : bottomIndex,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        onDestinationSelected: (i) => setState(() => _id = i < widget.items.length ? widget.items[i].id : _moreId),
        destinations: [
          for (final item in widget.items) NavigationDestination(icon: Icon(item.icon), selectedIcon: Icon(item.activeIcon), label: item.label),
          if (widget.more.isNotEmpty) NavigationDestination(icon: const Icon(Icons.menu_rounded), selectedIcon: const Icon(Icons.menu_rounded), label: s.get('more')),
        ],
      ),
    );
  }
}

/// "More" on a phone: the goals that do not fit into the bottom bar, then the switch to another area.
class _MorePage extends StatelessWidget {
  const _MorePage({required this.items, required this.onOpen});
  final List<ShellItem> items;
  final void Function(ShellItem) onOpen;

  @override
  Widget build(BuildContext context) {
    final session = SessionScope.of(context);
    final s = S.of(context);
    return ListView(padding: const EdgeInsets.all(Gap.l), children: [
      Card(
        child: Column(children: [
          for (final (i, item) in items.indexed) ...[
            if (i > 0) const Divider(height: 1, indent: 64),
            ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: Gap.l, vertical: 4),
              leading: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(color: brandSoft, borderRadius: BorderRadius.circular(12)),
                child: Icon(item.icon, color: brandBlue),
              ),
              title: Text(item.label, style: const TextStyle(fontWeight: FontWeight.w600)),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () => onOpen(item),
            ),
          ],
        ]),
      ),
      if (session.areas.length > 1) ...[
        const SizedBox(height: Gap.l),
        Padding(padding: const EdgeInsets.only(bottom: Gap.s, left: 4, right: 4), child: Text(s.get('switchArea'), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF5B6878)))),
        AreaSwitcher(light: true),
      ],
    ]);
  }
}

String areaLabel(S s, Area a) => s.get(a == Area.management ? 'managementArea' : (a == Area.teacher ? 'teacherArea' : 'parentArea'));

/// The tiles for changing between the areas of one account (management, teacher, parent).
class AreaSwitcher extends StatelessWidget {
  const AreaSwitcher({super.key, this.light = false});
  final bool light; // true: on a light background; false: inside the dark sidebar
  @override
  Widget build(BuildContext context) {
    final session = SessionScope.of(context);
    final s = S.of(context);
    return Column(children: [
      for (final a in session.areas)
        Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: a == session.area ? null : () => session.setArea(a),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: a == session.area ? (light ? Colors.white : Colors.white) : (light ? Colors.white : Colors.white.withValues(alpha: 0.08)),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: a == session.area ? brandBlue : (light ? const Color(0xFFE3E9F0) : Colors.transparent), width: a == session.area ? 2 : 1),
              ),
              child: Row(children: [
                Icon(a == Area.management ? Icons.shield_outlined : (a == Area.teacher ? Icons.edit_note_rounded : Icons.family_restroom_rounded), size: 20, color: a == session.area || light ? brandBlue : Colors.white70),
                const SizedBox(width: 10),
                Expanded(child: Text(areaLabel(s, a), style: TextStyle(fontWeight: a == session.area ? FontWeight.w700 : FontWeight.w500, color: a == session.area || light ? brandBlue : Colors.white))),
                if (a == session.area) const Icon(Icons.check_circle_rounded, size: 18, color: Color(0xFF1E7A45)),
              ]),
            ),
          ),
        ),
    ]);
  }
}

/// The sidebar of wide windows (Windows, tablets in landscape).
class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.roleLabel, required this.items, required this.selected, required this.onSelect});
  final String roleLabel;
  final List<ShellItem> items;
  final String selected;
  final void Function(String) onSelect;

  @override
  Widget build(BuildContext context) {
    final session = SessionScope.of(context);
    return Container(
      width: 264,
      color: brandBlue,
      padding: const EdgeInsets.fromLTRB(14, 22, 14, 18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(6, 0, 6, 22),
          child: Row(children: [
            const LogoPlate(height: 44),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(S.of(context).get('appName'), style: const TextStyle(color: Colors.white, fontSize: 19, fontWeight: FontWeight.w700)),
                Text(roleLabel, style: const TextStyle(color: Color(0xFFB7CBE0), fontSize: 12)),
              ]),
            ),
          ]),
        ),
        Expanded(
          child: ListView(children: [
            for (final item in items)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Material(
                  color: item.id == selected ? Colors.white : Colors.transparent,
                  borderRadius: BorderRadius.circular(12),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(12),
                    hoverColor: Colors.white.withValues(alpha: 0.10),
                    onTap: () => onSelect(item.id),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                      child: Row(children: [
                        Icon(item.id == selected ? item.activeIcon : item.icon, size: 22, color: item.id == selected ? brandBlue : const Color(0xFFE3EDF7)),
                        const SizedBox(width: 12),
                        Expanded(child: Text(item.label, style: TextStyle(fontSize: 15, fontWeight: item.id == selected ? FontWeight.w700 : FontWeight.w500, color: item.id == selected ? brandBlue : const Color(0xFFE3EDF7)))),
                      ]),
                    ),
                  ),
                ),
              ),
          ]),
        ),
        if (session.areas.length > 1) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.10), borderRadius: BorderRadius.circular(16)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Padding(padding: const EdgeInsets.fromLTRB(4, 0, 4, 8), child: Text(S.of(context).get('switchArea'), style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: Color(0xFFB7CBE0)))),
              const AreaSwitcher(),
            ]),
          ),
        ],
      ]),
    );
  }
}
