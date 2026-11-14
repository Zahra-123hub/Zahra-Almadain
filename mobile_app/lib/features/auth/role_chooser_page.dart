import 'package:flutter/material.dart';

import '../../design/shell.dart';
import '../../design/tokens.dart';
import '../../localization/strings.dart';
import '../../services/api.dart';
import '../../services/session.dart';
import '../../shared/ui.dart';

/// After signing in with several roles: the person chooses the area to work in. Only that area's data is open afterwards.
class RoleChooserPage extends StatefulWidget {
  const RoleChooserPage({super.key});
  @override
  State<RoleChooserPage> createState() => _RoleChooserPageState();
}

class _RoleChooserPageState extends State<RoleChooserPage> {
  Area? _busy;

  Future<void> _choose(Area area) async {
    final session = SessionScope.of(context);
    setState(() => _busy = area);
    try {
      await session.chooseArea(area);
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final session = SessionScope.of(context);
    final hints = {Area.management: 'roleManagementHint', Area.teacher: 'roleTeacherHint', Area.parent: 'roleParentHint'};
    final icons = {Area.management: Icons.shield_outlined, Area.teacher: Icons.edit_note_rounded, Area.parent: Icons.family_restroom_rounded};
    return Scaffold(
      body: Column(children: [
        AppHeader(title: s.fill('welcome', session.username ?? ''), subtitle: s.get('chooseRole')),
        Expanded(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: ListView(padding: const EdgeInsets.all(Gap.l), children: [
                for (final area in session.areas)
                  Padding(
                    padding: const EdgeInsets.only(bottom: Gap.m),
                    child: Card(
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                        side: BorderSide(color: session.lastArea == area.name ? brandBlue : const Color(0xFFE3E9F0), width: session.lastArea == area.name ? 2 : 1),
                      ),
                      child: InkWell(
                        onTap: _busy != null ? null : () => _choose(area),
                        hoverColor: brandSoft,
                        child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Row(children: [
                            Container(
                              width: 44,
                              height: 44,
                              decoration: BoxDecoration(color: session.lastArea == area.name ? brandBlue : brandSoft, borderRadius: BorderRadius.circular(12)),
                              child: Icon(icons[area], color: session.lastArea == area.name ? Colors.white : brandBlue),
                            ),
                            const SizedBox(width: 14),
                            Expanded(
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text(areaLabel(s, area), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                                Text(s.get(hints[area]!), style: const TextStyle(fontSize: 12.5, color: Color(0xFF6A7686))),
                              ]),
                            ),
                            if (_busy == area)
                              const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4))
                            else if (session.lastArea == area.name)
                              Pill(s.get('lastUsed'), foreground: const Color(0xFF1E7A45), background: const Color(0xFFE4F4EA))
                            else
                              const Icon(Icons.chevron_right_rounded),
                          ]),
                        ),
                      ),
                    ),
                  ),
                Padding(padding: const EdgeInsets.all(6), child: Text(s.get('roleChoiceNote'), style: const TextStyle(fontSize: 12.5, color: Color(0xFF6A7686), height: 1.5))),
                const SizedBox(height: Gap.s),
                TextButton.icon(onPressed: _busy != null ? null : session.logout, icon: const Icon(Icons.logout), label: Text(s.get('signOut'))),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}
