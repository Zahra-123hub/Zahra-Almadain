import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'features/auth/login_page.dart';
import 'features/common/common_pages.dart';
import 'features/management/management_pages.dart';
import 'features/parents/parent_pages.dart';
import 'features/teachers/teacher_pages.dart';
import 'localization/strings.dart';
import 'services/api.dart';
import 'services/session.dart';
import 'shared/ui.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final session = Session(ApiClient());
  runApp(ZahraApp(session: session));
  await session.start();
}

class ZahraApp extends StatelessWidget {
  const ZahraApp({super.key, required this.session});
  final Session session;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: session,
      builder: (context, _) => MaterialApp(
        title: 'Zahrat Al-Madain',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        locale: session.locale, // Arabic is the default; RTL follows the language automatically
        supportedLocales: S.supported,
        localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate, GlobalCupertinoLocalizations.delegate],
        // above the navigator, so screens opened later (report editor, new post) find the session too
        builder: (context, child) => SessionScope(session: session, child: child ?? const SizedBox.shrink()),
        home: const _Root(),
      ),
    );
  }
}

class _Root extends StatelessWidget {
  const _Root();
  @override
  Widget build(BuildContext context) {
    final session = SessionScope.of(context);
    if (!session.ready) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (session.versionInfo?.updateRequired == true) return _UpdateRequired(session.versionInfo!);
    if (!session.signedIn || !session.hasMobileArea) return const LoginPage();
    switch (session.area) {
      case Area.management:
        return const ManagementShell();
      case Area.teacher:
        return const TeacherShell();
      default:
        return const ParentShell();
    }
  }
}

class _UpdateRequired extends StatelessWidget {
  const _UpdateRequired(this.info);
  final VersionInfo info;
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.system_update, size: 56, color: brandBlue),
            const SizedBox(height: 16),
            Text(s.get('updateRequired'), textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('${s.get('version')} ${info.latest}'),
          ]),
        ),
      ),
    );
  }
}

/// A banner for a newer (but not required) version.
class _UpdateHint extends StatelessWidget {
  const _UpdateHint();
  @override
  Widget build(BuildContext context) {
    final info = SessionScope.of(context).versionInfo;
    if (info?.updateAvailable != true) return const SizedBox.shrink();
    return Container(width: double.infinity, color: const Color(0xFFE6F2FF), padding: const EdgeInsets.all(8), child: Text(S.of(context).get('updateAvailable'), textAlign: TextAlign.center, style: const TextStyle(fontSize: 12)));
  }
}

class ParentShell extends StatefulWidget {
  const ParentShell({super.key});
  @override
  State<ParentShell> createState() => _ParentShellState();
}

class _ParentShellState extends State<ParentShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final pages = <(IconData, String, Widget)>[
      (Icons.home_outlined, s.get('home'), ParentHome(goTo: (i) => setState(() => _index = i))),
      (Icons.child_care, s.get('myChildren'), const ParentChildren()),
      (Icons.description_outlined, s.get('reports'), const ParentReports()),
      (Icons.campaign_outlined, s.get('postsAndNotices'), const ParentPosts()),
      (Icons.menu_book_outlined, s.get('learning'), const ParentLearning()),
      (Icons.notifications_outlined, s.get('notifications'), const NotificationsPage()),
      (Icons.person_outline, s.get('profile'), const ProfilePage()),
    ];
    return Scaffold(
      appBar: AppBar(title: BarTitle(pages[_index].$2)),
      body: Column(children: [const _UpdateHint(), Expanded(child: KeyedSubtree(key: ValueKey(_index), child: pages[_index].$3))]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [for (final p in pages) NavigationDestination(icon: Icon(p.$1), label: p.$2)],
      ),
    );
  }
}

class ManagementShell extends StatefulWidget {
  const ManagementShell({super.key});
  @override
  State<ManagementShell> createState() => _ManagementShellState();
}

class _ManagementShellState extends State<ManagementShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final pages = <(IconData, String, Widget)>[
      (Icons.home_outlined, s.get('home'), ManagementHome(goTo: (i) => setState(() => _index = i))),
      (Icons.fact_check_outlined, s.get('reviewReports'), const ReviewReports()),
      (Icons.school_outlined, s.get('manageLearning'), const CourseEditor()),
      (Icons.notifications_outlined, s.get('notifications'), const NotificationsPage()),
      (Icons.person_outline, s.get('profile'), const ProfilePage()),
    ];
    return Scaffold(
      appBar: AppBar(title: BarTitle(pages[_index].$2)),
      body: Column(children: [const _UpdateHint(), Expanded(child: KeyedSubtree(key: ValueKey(_index), child: pages[_index].$3))]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [for (final p in pages) NavigationDestination(icon: Icon(p.$1), label: p.$2)],
      ),
    );
  }
}

class TeacherShell extends StatefulWidget {
  const TeacherShell({super.key});
  @override
  State<TeacherShell> createState() => _TeacherShellState();
}

class _TeacherShellState extends State<TeacherShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final pages = <(IconData, String, Widget)>[
      (Icons.home_outlined, s.get('home'), TeacherHome(goTo: (i) => setState(() => _index = i))),
      (Icons.child_care, s.get('myChildren'), const TeacherChildren()),
      (Icons.description_outlined, s.get('reports'), const TeacherReports()),
      (Icons.campaign_outlined, s.get('posts'), const TeacherPosts()),
      (Icons.folder_outlined, s.get('materials'), const TeacherMaterials()),
      (Icons.notifications_outlined, s.get('notifications'), const NotificationsPage()),
      (Icons.person_outline, s.get('profile'), const ProfilePage()),
    ];
    return Scaffold(
      appBar: AppBar(title: BarTitle(pages[_index].$2)),
      body: Column(children: [const _UpdateHint(), Expanded(child: KeyedSubtree(key: ValueKey(_index), child: pages[_index].$3))]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [for (final p in pages) NavigationDestination(icon: Icon(p.$1), label: p.$2)],
      ),
    );
  }
}
