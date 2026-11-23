import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'design/shell.dart';
import 'features/accounting/accounting_pages.dart';
import 'features/admin/admin_pages.dart';
import 'features/auth/login_page.dart';
import 'features/auth/role_chooser_page.dart';
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
        theme: buildTheme(session.locale.languageCode),
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
    if (session.needsAreaChoice) return const RoleChooserPage();
    switch (session.area) {
      case Area.admin:
        return const AdminShell();
      case Area.management:
        return const ManagementShell();
      case Area.accounting:
        return const AccountingShell();
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

class ParentShell extends StatelessWidget {
  const ParentShell({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return AdaptiveShell(
      roleLabel: s.get('parentArea'),
      items: [
        ShellItem(id: 'home', icon: Icons.home_outlined, activeIcon: Icons.home_rounded, label: s.get('home'), page: (go) => ParentHome(goTo: go)),
        ShellItem(id: 'children', icon: Icons.child_care_outlined, activeIcon: Icons.child_care, label: s.get('myChildren'), page: (_) => const ParentChildren()),
        ShellItem(id: 'reports', icon: Icons.description_outlined, activeIcon: Icons.description, label: s.get('reports'), page: (_) => const ParentReports()),
        ShellItem(id: 'learning', icon: Icons.menu_book_outlined, activeIcon: Icons.menu_book, label: s.get('learning'), page: (_) => const ParentLearning()),
      ],
      more: [
        ShellItem(id: 'posts', icon: Icons.campaign_outlined, activeIcon: Icons.campaign, label: s.get('postsAndNotices'), page: (_) => const ParentPosts()),
        ShellItem(id: 'notifications', icon: Icons.notifications_outlined, activeIcon: Icons.notifications, label: s.get('notifications'), page: (_) => const NotificationsPage()),
        ShellItem(id: 'profile', icon: Icons.person_outline, activeIcon: Icons.person, label: s.get('profile'), page: (_) => const ProfilePage()),
      ],
    );
  }
}

class TeacherShell extends StatelessWidget {
  const TeacherShell({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return AdaptiveShell(
      roleLabel: s.get('teacherArea'),
      items: [
        ShellItem(id: 'home', icon: Icons.home_outlined, activeIcon: Icons.home_rounded, label: s.get('home'), page: (go) => TeacherHome(goTo: go)),
        ShellItem(id: 'children', icon: Icons.child_care_outlined, activeIcon: Icons.child_care, label: s.get('myChildren'), page: (_) => const TeacherChildren()),
        ShellItem(id: 'reports', icon: Icons.description_outlined, activeIcon: Icons.description, label: s.get('reports'), page: (_) => const TeacherReports()),
        ShellItem(id: 'posts', icon: Icons.campaign_outlined, activeIcon: Icons.campaign, label: s.get('posts'), page: (_) => const TeacherPosts()),
      ],
      more: [
        ShellItem(id: 'files', icon: Icons.folder_outlined, activeIcon: Icons.folder, label: s.get('materials'), page: (_) => const TeacherMaterials()),
        ShellItem(id: 'notifications', icon: Icons.notifications_outlined, activeIcon: Icons.notifications, label: s.get('notifications'), page: (_) => const NotificationsPage()),
        ShellItem(id: 'profile', icon: Icons.person_outline, activeIcon: Icons.person, label: s.get('profile'), page: (_) => const ProfilePage()),
      ],
    );
  }
}

class ManagementShell extends StatelessWidget {
  const ManagementShell({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return AdaptiveShell(
      roleLabel: s.get('managementArea'),
      items: [
        ShellItem(id: 'home', icon: Icons.home_outlined, activeIcon: Icons.home_rounded, label: s.get('home'), page: (go) => ManagementHome(goTo: go)),
        ShellItem(id: 'review', icon: Icons.fact_check_outlined, activeIcon: Icons.fact_check, label: s.get('reviewReports'), page: (_) => const ReviewReports()),
        ShellItem(id: 'course', icon: Icons.school_outlined, activeIcon: Icons.school, label: s.get('manageLearning'), page: (_) => const CourseEditor()),
        ShellItem(id: 'money', icon: Icons.account_balance_wallet_outlined, activeIcon: Icons.account_balance_wallet, label: s.get('mnAccounting'), page: (_) => const MoneyHub()),
      ],
      more: [
        ShellItem(id: 'profile', icon: Icons.person_outline, activeIcon: Icons.person, label: s.get('profile'), page: (_) => const ProfilePage()),
      ],
    );
  }
}

/// The admin: the same work as the admin page of the website (control centre, accounts, children and reports, accounting,
/// website content, activity log, visitors, files, security).
class AdminShell extends StatelessWidget {
  const AdminShell({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    String t(String ar, String de, String en) => s.code == 'ar' ? ar : (s.code == 'de' ? de : en);
    return AdaptiveShell(
      roleLabel: s.get('adminArea'),
      items: [
        ShellItem(id: 'control', icon: Icons.dashboard_outlined, activeIcon: Icons.dashboard, label: t('لوحة المتابعة', 'Kontrollzentrale', 'Control centre'), page: (_) => const AdminControlPage()),
        ShellItem(id: 'accounts', icon: Icons.manage_accounts_outlined, activeIcon: Icons.manage_accounts, label: t('الحسابات', 'Konten', 'Accounts'), page: (_) => const AdminAccountsPage()),
        ShellItem(id: 'children', icon: Icons.child_care_outlined, activeIcon: Icons.child_care, label: t('الأطفال والتقارير', 'Kinder und Berichte', 'Children and reports'), page: (_) => const AdminChildrenPage()),
        ShellItem(id: 'money', icon: Icons.account_balance_wallet_outlined, activeIcon: Icons.account_balance_wallet, label: s.get('mnAccounting'), page: (_) => const MoneyHub()),
      ],
      more: [
        ShellItem(id: 'website', icon: Icons.language_outlined, activeIcon: Icons.language, label: t('الموقع', 'Webseite', 'Website'), page: (_) => const AdminWebsitePage()),
        ShellItem(id: 'log', icon: Icons.history_rounded, activeIcon: Icons.history_rounded, label: t('سجل النظام', 'Protokoll', 'Activity log'), page: (_) => const AdminLogPage()),
        ShellItem(id: 'visitors', icon: Icons.insights_outlined, activeIcon: Icons.insights, label: t('الزوّار', 'Besucher', 'Visitors'), page: (_) => const AdminVisitorsPage()),
        ShellItem(id: 'files', icon: Icons.folder_outlined, activeIcon: Icons.folder, label: t('الملفات', 'Dateien', 'Files'), page: (_) => const AdminFilesPage()),
        ShellItem(id: 'security', icon: Icons.security_outlined, activeIcon: Icons.security, label: t('الأمان', 'Sicherheit', 'Security'), page: (_) => const AdminSecurityPage()),
        ShellItem(id: 'profile', icon: Icons.person_outline, activeIcon: Icons.person, label: s.get('profile'), page: (_) => const ProfilePage()),
      ],
    );
  }
}

/// The accounting: the month overview first, then income and expenses (the same pages as on the website).
class AccountingShell extends StatelessWidget {
  const AccountingShell({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return AdaptiveShell(
      roleLabel: s.get('accountingArea'),
      items: [
        ShellItem(id: 'summary', icon: Icons.insights_outlined, activeIcon: Icons.insights, label: s.get('mnSummary'), page: (_) => const MoneySummaryPage()),
        ShellItem(id: 'income', icon: Icons.south_west_rounded, activeIcon: Icons.south_west_rounded, label: s.get('mnIncome'), page: (_) => const MoneyEntriesPage(kind: 'income')),
        ShellItem(id: 'expenses', icon: Icons.north_east_rounded, activeIcon: Icons.north_east_rounded, label: s.get('mnExpenses'), page: (_) => const MoneyEntriesPage(kind: 'expenses')),
      ],
      more: [
        ShellItem(id: 'profile', icon: Icons.person_outline, activeIcon: Icons.person, label: s.get('profile'), page: (_) => const ProfilePage()),
      ],
    );
  }
}
