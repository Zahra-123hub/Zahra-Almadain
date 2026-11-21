import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:zahra_app/design/shell.dart';
import 'package:zahra_app/features/accounting/accounting_pages.dart';
import 'package:zahra_app/features/auth/login_page.dart';
import 'package:zahra_app/features/auth/role_chooser_page.dart';
import 'package:zahra_app/features/management/management_pages.dart';
import 'package:zahra_app/features/parents/parent_pages.dart';
import 'package:zahra_app/features/teachers/teacher_pages.dart';
import 'package:zahra_app/main.dart';
import 'package:zahra_app/localization/strings.dart';
import 'package:zahra_app/models/models.dart';
import 'package:zahra_app/services/api.dart';
import 'package:zahra_app/services/session.dart';
import 'package:zahra_app/shared/ui.dart';

http.Response json(Object body, [int status = 200]) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json; charset=utf-8'});

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('texts', () {
    test('every text exists in Arabic, German and English', () {
      final source = File('lib/localization/strings.dart').readAsStringSync();
      final keys = RegExp(r"^\s+'(\w+)': \{'ar': ", multiLine: true).allMatches(source).map((m) => m.group(1)!).toList();
      expect(keys.length, greaterThan(50));
      for (final code in ['ar', 'de', 'en']) {
        final s = S(code);
        for (final key in keys) {
          expect(s.get(key), isNot(key), reason: '$key missing in $code');
        }
      }
    });

    test('notification texts get the subject', () {
      expect(S('de').fill('n_report_published', 'Amal'), contains('Amal'));
    });
  });

  group('models', () {
    test('a report is read from the API answer', () {
      final r = Report.fromJson({'id': '1', 'child_id': '2', 'title': 'T', 'body': 'B', 'activities': '', 'meals': null, 'status': 'published', 'created_at': '2026-03-01T08:00:00Z', 'published_at': null});
      expect((r.title, r.meals, r.status), ('T', '', 'published'));
      expect(r.day, isNotNull);
    });

    test('a post with files', () {
      final p = Post.fromJson({
        'id': '1', 'scope': 'child', 'child_name': 'Amal', 'title': 'x', 'body': '', 'author': 'a',
        'files': [{'id': 'f', 'filename': 'a.png', 'media_type': 'image/png', 'size': 10}]
      });
      expect(p.files.single.isImage, isTrue);
    });
  });

  group('roles', () {
    setUpAll(() {
      TestWidgetsFlutterBinding.ensureInitialized();
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(
        const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
        (call) async => call.method == 'read' ? 'abc' : null,
      );
    });

    /// A server that answers /auth/me with the given roles and the active role, and switch-role with a new token.
    (Session, List<String>) serverSession(List<String> roles, {String? active, int switchStatus = 200}) {
      final calls = <String>[];
      final session = Session(ApiClient(client: MockClient((r) async {
        if (r.url.path.endsWith('/auth/switch-role')) {
          final role = (jsonDecode(r.body) as Map<String, dynamic>)['role'] as String;
          calls.add(role);
          if (switchStatus != 200) return json({'detail': 'x'}, switchStatus);
          return json({'access_token': 'token-for-$role', 'active_role': role, 'roles': roles, 'needs_role_choice': false});
        }
        return json({'id': 'a1', 'username': 'x', 'roles': roles, 'active_role': active});
      })))
        ..api.token = null;
      return (session, calls);
    }

    test('with several areas nothing is opened until the person chooses; the choice is sent to the server and gives a new token', () async {
      final (session, calls) = serverSession(['parent', 'teacher', 'manager']);
      await session.start();
      expect(session.areas, [Area.management, Area.teacher, Area.parent]);
      expect((session.area, session.needsAreaChoice), (null, true));
      await session.chooseArea(Area.parent);
      expect(calls, ['parent']);
      expect((session.area, session.activeRole, session.api.token, session.needsAreaChoice), (Area.parent, 'parent', 'token-for-parent', false));
      // a later start takes over what the server says (the session already works as a parent)
      final (again, none) = serverSession(['parent', 'teacher', 'manager'], active: 'parent');
      await again.start();
      expect((again.area, again.needsAreaChoice), (Area.parent, false));
      expect(none, isEmpty); // nothing had to be sent: the server already knew
      expect(again.lastArea, 'parent');
    });

    test('a changed area is told to the server first: a refused role changes nothing', () async {
      final (session, calls) = serverSession(['parent', 'teacher'], active: 'parent', switchStatus: 403);
      await session.start();
      expect(session.area, Area.parent);
      await session.setArea(Area.teacher); // refused with 403
      expect(session.area, Area.parent);
      expect(calls, ['teacher']);
      await expectLater(session.chooseArea(Area.teacher), throwsA(isA<ApiException>()));
      expect(session.area, Area.parent);
    });

    test('an account with one app area and other roles on the website works in that area at once and tells the server', () async {
      final (session, calls) = serverSession(['parent', 'admin']); // the administration is on the website only
      await session.start();
      expect((session.area, session.needsAreaChoice), (Area.parent, false));
      expect(calls, ['parent']);
    });

    test('a server that does not know the call yet (404) does not block the choice', () async {
      final (session, calls) = serverSession(['parent', 'teacher'], switchStatus: 404);
      await session.start();
      await session.chooseArea(Area.teacher);
      expect(session.area, Area.teacher);
      expect(calls, ['teacher']);
    });

    testWidgets('the choice screen lists the areas, marks the last one and opens the chosen one', (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      SharedPreferences.setMockInitialValues({'area': 'teacher'});
      final (session, calls) = serverSession(['parent', 'teacher', 'manager']);
      await session.start();
      await tester.pumpWidget(MaterialApp(
        locale: const Locale('en'),
        supportedLocales: S.supported,
        localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
        builder: (context, child) => SessionScope(session: session, child: child!),
        home: const RoleChooserPage(),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Choose how you want to work'), findsOneWidget);
      expect(find.text('Management area'), findsOneWidget);
      expect(find.text('Teacher area'), findsOneWidget);
      expect(find.text('Parent area'), findsOneWidget);
      expect(find.text('Last used'), findsOneWidget); // the teacher area
      await tester.tap(find.text('Teacher area'));
      await tester.pumpAndSettle();
      expect(calls, ['teacher']);
      expect(session.area, Area.teacher);
    });

    test('an admin account has no area in the app; an accounting account has the accounting', () async {
      final admin = Session(ApiClient(client: MockClient((_) async => json({'id': 'a1', 'username': 'x', 'roles': ['admin']}))))..api.token = 'abc';
      await admin.start();
      expect(admin.areas, isEmpty);
      expect(admin.hasMobileArea, isFalse);
      final money = Session(ApiClient(client: MockClient((r) async => r.url.path.endsWith('/switch-role')
          ? json({'access_token': 't2', 'active_role': 'accountant'})
          : json({'id': 'a2', 'username': 'y', 'roles': ['admin', 'accountant']}))))..api.token = 'abc';
      await money.start();
      expect(money.areas, [Area.accounting]);
    });
  });

  group('shell', () {
    Widget host(Session session, Size size) => MaterialApp(
          locale: const Locale('en'),
          supportedLocales: S.supported,
          localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
          builder: (context, child) => SessionScope(session: session, child: child!),
          home: AdaptiveShell(
            roleLabel: 'Parent',
            items: [
              ShellItem(id: 'home', icon: Icons.home_outlined, activeIcon: Icons.home, label: 'Home', page: (go) => TextButton(onPressed: () => go('profile'), child: const Text('home page'))),
              ShellItem(id: 'reports', icon: Icons.description_outlined, activeIcon: Icons.description, label: 'Reports', page: (_) => const Text('reports page')),
            ],
            more: [
              ShellItem(id: 'notifications', icon: Icons.notifications_outlined, activeIcon: Icons.notifications, label: 'Notifications', page: (_) => const Text('notifications page')),
              ShellItem(id: 'profile', icon: Icons.person_outline, activeIcon: Icons.person, label: 'Profile', page: (_) => const Text('profile page')),
            ],
          ),
        );

    Session sessionWithBell() => Session(ApiClient(client: MockClient((_) async => json({'unread': 3, 'items': []}))));

    testWidgets('phone: bottom bar with More; More lists the rest and opens it on its own page with a back button', (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(host(sessionWithBell(), const Size(390, 844)));
      await tester.pumpAndSettle();
      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.text('home page'), findsOneWidget);
      expect(find.text('3'), findsOneWidget); // the unread number on the bell
      await tester.tap(find.text('More'));
      await tester.pumpAndSettle();
      expect(find.text('Profile'), findsOneWidget);
      await tester.tap(find.text('Profile'));
      await tester.pumpAndSettle();
      expect(find.text('profile page'), findsOneWidget);
      await tester.tap(find.byIcon(Icons.arrow_back_ios_new_rounded));
      await tester.pumpAndSettle();
      expect(find.text('profile page'), findsNothing);
      // the home page can send the user to a goal that lives under More
      await tester.tap(find.text('Home'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('home page'));
      await tester.pumpAndSettle();
      expect(find.text('profile page'), findsOneWidget);
    });

    testWidgets('wide window: sidebar lists every goal, no bottom bar, selecting switches the content in place', (tester) async {
      tester.view.physicalSize = const Size(1280, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(host(sessionWithBell(), const Size(1280, 800)));
      await tester.pumpAndSettle();
      expect(find.byType(NavigationBar), findsNothing);
      for (final label in ['Home', 'Reports', 'Notifications', 'Profile']) {
        expect(find.text(label), findsWidgets);
      }
      await tester.tap(find.text('Profile').last);
      await tester.pumpAndSettle();
      expect(find.text('profile page'), findsOneWidget);
      expect(find.text('Parent'), findsOneWidget);
    });
  });

  group('states', () {
    Widget host(Widget child, {Session? session}) => MaterialApp(
          locale: const Locale('en'),
          supportedLocales: S.supported,
          localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
          builder: (context, page) => SessionScope(session: session ?? Session(ApiClient(client: MockClient((_) async => json({})))), child: page!),
          home: Scaffold(body: child),
        );

    testWidgets('while loading a skeleton shows, then the content', (tester) async {
      final done = Completer<Cached<String>>();
      await tester.pumpWidget(host(Loader<String>(load: () => done.future, builder: (context, data, reload) => Text('got $data'))));
      await tester.pump();
      expect(find.byType(SkeletonList), findsOneWidget);
      done.complete(Cached('it'));
      await tester.pumpAndSettle();
      expect(find.byType(SkeletonList), findsNothing);
      expect(find.text('got it'), findsOneWidget);
    });

    testWidgets('offline, no permission and a server problem each look different, and retry loads again', (tester) async {
      var attempt = 0;
      Future<Cached<String>> load() async {
        attempt++;
        if (attempt == 1) throw ApiException(ApiProblem.offline);
        if (attempt == 2) throw ApiException(ApiProblem.forbidden);
        if (attempt == 3) throw ApiException(ApiProblem.server);
        return Cached('fine');
      }

      await tester.pumpWidget(host(Loader<String>(load: load, builder: (context, data, reload) => Text('got $data'))));
      await tester.pumpAndSettle();
      expect(find.text('You are offline'), findsOneWidget);
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(find.text('No access'), findsOneWidget);
      expect(find.text('Retry'), findsNothing); // nothing to retry without the right to see it
    });

    testWidgets('a server problem offers a retry that brings the content', (tester) async {
      var attempt = 0;
      await tester.pumpWidget(host(Loader<String>(
        load: () async {
          attempt++;
          if (attempt == 1) throw ApiException(ApiProblem.server);
          return Cached('fine');
        },
        builder: (context, data, reload) => Text('got $data'),
      )));
      await tester.pumpAndSettle();
      expect(find.text('Could not load'), findsOneWidget);
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(find.text('got fine'), findsOneWidget);
    });

    test('an upload reports its progress up to 100 percent and sends the whole file', () async {
      final dir = Directory.systemTemp.createTempSync('upload');
      addTearDown(() => dir.deleteSync(recursive: true));
      final file = File('${dir.path}/a.pdf')..writeAsBytesSync(List.filled(300000, 7));
      String? contentType;
      var received = 0;
      final api = ApiClient(client: MockClient((r) async {
        contentType = r.headers['content-type'];
        received = r.bodyBytes.length;
        return json({'ok': true});
      }))..token = 'abc';
      final seen = <double>[];
      await api.multipart('/api/x', {'title': 't'}, [UploadFile(file.path, 'a.pdf')], onProgress: seen.add);
      expect(seen, isNotEmpty);
      expect(seen.last, 1.0);
      expect(seen, orderedEquals([...seen]..sort())); // never goes backwards
      expect(contentType, startsWith('multipart/form-data; boundary='));
      expect(received, greaterThan(300000));
    });

    testWidgets('a post can be previewed the way the parents see it before it is sent', (tester) async {
      tester.view.physicalSize = const Size(800, 1400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final session = Session(ApiClient(client: MockClient((_) async => json([]))));
      await tester.pumpWidget(host(PostComposer(children: [Child('c1', 'Amal')]), session: session));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).first, 'Trip on Friday');
      await tester.enterText(find.byType(TextField).at(1), 'Bring a hat.');
      await tester.tap(find.text('Preview'));
      await tester.pumpAndSettle();
      final sheet = find.byType(BottomSheet);
      expect(find.descendant(of: sheet, matching: find.text('Trip on Friday')), findsOneWidget);
      expect(find.descendant(of: sheet, matching: find.text('Bring a hat.')), findsOneWidget);
      expect(find.descendant(of: sheet, matching: find.byType(PostCard)), findsOneWidget);
    });

    testWidgets('ticking files turns the add button into a bar for sharing, and Cancel clears the ticks', (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      Object body(String path) {
        if (path.endsWith('/content')) return [{'id': 'f1', 'category': 'document', 'filename': 'a.pdf', 'media_type': 'application/pdf', 'size': 10}];
        if (path.endsWith('/storage')) return {'used_bytes': 10, 'limit_bytes': 1000};
        return [];
      }
      final session = Session(ApiClient(client: MockClient((r) async => json(body(r.url.path)))));
      await tester.pumpWidget(host(const TeacherMaterials(), session: session));
      await tester.pumpAndSettle();
      expect(find.byType(FloatingActionButton), findsOneWidget);
      expect(find.byType(BottomActionBar), findsNothing);
      await tester.tap(find.byType(Checkbox));
      await tester.pumpAndSettle();
      expect(find.byType(FloatingActionButton), findsNothing);
      expect(find.descendant(of: find.byType(BottomActionBar), matching: find.textContaining('Share with parents (1)')), findsOneWidget);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(find.byType(BottomActionBar), findsNothing);
      expect(tester.widget<Checkbox>(find.byType(Checkbox)).value, isFalse);
    });

    test('every report status has its own colour: draft grey, submitted orange, published green, returned red', () {
      expect(statusColor('draft'), const Color(0xFF42536A));
      expect(statusColor('submitted'), const Color(0xFF8A5200));
      expect(statusColor('published'), const Color(0xFF1E7A45));
      expect(statusColor('rejected'), const Color(0xFFB3402F));
      expect({for (final st in ['draft', 'submitted', 'published', 'rejected']) statusColor(st)}.length, 4);
    });

    test('file types get their own icon and colour', () {
      expect(fileTintFor('pdf', false).$2, isNot(fileTintFor('mp4', false).$2));
      expect(fileIconFor('pdf', false), Icons.picture_as_pdf_outlined);
      expect(fileIconFor('png', true), Icons.image_outlined);
      expect(fileExt('Arbeitsblatt Alif.PDF'), 'pdf');
      expect(fileExt('README'), '');
    });

    testWidgets('each child of a teacher has a button that starts a report for that child', (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final session = Session(ApiClient(client: MockClient((_) async => json([{'id': 'c1', 'display_name': 'Amal'}, {'id': 'c2', 'display_name': 'Omar'}]))));
      await tester.pumpWidget(host(const TeacherChildren(), session: session));
      await tester.pumpAndSettle();
      expect(find.text('Amal'), findsOneWidget);
      expect(find.text('New report'), findsNWidgets(2));
      await tester.tap(find.text('New report').first);
      await tester.pumpAndSettle();
      expect(find.byType(ReportEditor), findsOneWidget);
    });
  });

  group('api client', () {
    test('a bad sign-in is reported as unauthorized without ending a session', () async {
      var ended = false;
      final api = ApiClient(client: MockClient((_) async => json({'detail': 'Incorrect username or password.'}, 401)));
      api.onSessionEnded = () => ended = true;
      await expectLater(api.post('/api/platform/auth/login', {}), throwsA(isA<ApiException>().having((e) => e.problem, 'problem', ApiProblem.unauthorized)));
      expect(ended, isFalse);
    });

    test('a 401 with a token ends the session', () async {
      var ended = false;
      final api = ApiClient(client: MockClient((_) async => json({'detail': 'x'}, 401)))..token = 'abc';
      api.onSessionEnded = () => ended = true;
      await expectLater(api.get('/api/platform/children'), throwsA(isA<ApiException>()));
      expect(ended, isTrue);
    });

    test('the token is sent as Bearer header', () async {
      String? header;
      final api = ApiClient(client: MockClient((r) async {
        header = r.headers['Authorization'];
        return json([]);
      }))..token = 'abc';
      await api.get('/api/platform/children');
      expect(header, 'Bearer abc');
    });

    test('server answers are mapped (403 pending, 429, 5xx)', () async {
      Future<ApiProblem> problem(int status, String detail) async {
        final api = ApiClient(client: MockClient((_) async => json({'detail': detail}, status)));
        try {
          await api.get('/x');
        } on ApiException catch (e) {
          return e.problem;
        }
        throw StateError('no error');
      }

      expect(await problem(403, 'Your account is awaiting administrator approval.'), ApiProblem.pending);
      expect(await problem(403, 'Your account has been disabled.'), ApiProblem.disabled);
      expect(await problem(403, 'You do not have permission'), ApiProblem.forbidden);
      expect(await problem(429, 'Too many'), ApiProblem.tooMany);
      expect(await problem(500, ''), ApiProblem.server);
    });

    test('offline: the last loaded copy of the same account is shown, another account gets nothing', () async {
      var online = true;
      final api = ApiClient(client: MockClient((_) async {
        if (!online) throw const SocketException('down');
        return json([{'id': '1'}]);
      }))..cacheOwner = 'acc1';
      expect((await api.getCached('/list')).fromCache, isFalse);
      online = false;
      final again = await api.getCached('/list');
      expect((again.fromCache, (again.data as List).length), (true, 1));
      api.cacheOwner = 'acc2';
      await expectLater(api.getCached('/list'), throwsA(isA<ApiException>().having((e) => e.problem, 'problem', ApiProblem.offline)));
      api.cacheOwner = 'acc1';
      await api.clearCache(); // sign-out
      await expectLater(api.getCached('/list'), throwsA(isA<ApiException>()));
    });
  });

  group('screens', () {
    Widget host(Session session, Locale locale) => MaterialApp(
          locale: locale,
          supportedLocales: S.supported,
          localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate, GlobalCupertinoLocalizations.delegate],
          home: SessionScope(session: session, child: const LoginPage()),
        );

    testWidgets('Arabic login is right-to-left and asks for both fields', (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final session = Session(ApiClient(client: MockClient((_) async => json({}))));
      await tester.pumpWidget(host(session, const Locale('ar')));
      expect(Directionality.of(tester.element(find.byType(LoginPage))), TextDirection.rtl);
      expect(find.text('تسجيل الدخول'), findsWidgets);
      await tester.tap(find.byType(FilledButton));
      await tester.pump();
      expect(find.text('هذا الحقل مطلوب'), findsNWidgets(2));
      expect(tester.takeException(), isNull);
    });

    testWidgets('a screen opened later (new report) still finds the session', (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final session = Session(ApiClient(client: MockClient((_) async => json({}))));
      await tester.pumpWidget(ZahraApp(session: session));
      await tester.pump();
      Navigator.of(tester.element(find.byType(Navigator).first)).push(MaterialPageRoute(builder: (_) => const ReportEditor(children: [])));
      await tester.pumpAndSettle();
      expect(find.byType(ReportEditor), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('the parents learning tab lists only learning material, the posts tab the rest', (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final posts = [
        {'id': '1', 'scope': 'general', 'kind': 'material', 'child_name': '', 'title': 'Letters sheet', 'body': 'x', 'author': 'T', 'files': []},
        {'id': '2', 'scope': 'general', 'kind': 'post', 'child_name': '', 'title': 'Trip on Friday', 'body': 'x', 'author': 'T', 'files': []},
      ];
      final session = Session(ApiClient(client: MockClient((r) async => r.url.path.contains('announcements') ? json([]) : json(posts))));
      Future<void> show(Widget page) async {
        await tester.pumpWidget(MaterialApp(
          locale: const Locale('en'),
          supportedLocales: S.supported,
          localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
          home: SessionScope(session: session, child: Scaffold(body: page)),
        ));
        await tester.pumpAndSettle();
      }

      await show(const ParentLearning());
      expect(find.text('Letters sheet'), findsOneWidget);
      expect(find.text('Trip on Friday'), findsNothing);
      await show(const ParentPosts());
      expect(find.text('Trip on Friday'), findsOneWidget);
      expect(find.text('Letters sheet'), findsNothing);
    });

    testWidgets('private files can be ticked and shared with parents', (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      Object body(String path) {
        if (path.endsWith('/content')) return [{'id': 'f1', 'category': 'document', 'name': 'a.pdf', 'media_type': 'application/pdf', 'size': 10}];
        if (path.endsWith('/storage')) return {'used_bytes': 10, 'limit_bytes': 1000};
        return [];
      }
      final session = Session(ApiClient(client: MockClient((r) async => json(body(r.url.path)))));
      await tester.pumpWidget(MaterialApp(
        locale: const Locale('de'),
        supportedLocales: S.supported,
        localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate, GlobalCupertinoLocalizations.delegate],
        home: SessionScope(session: session, child: const Scaffold(body: TeacherMaterials())),
      ));
      await tester.pumpAndSettle();
      expect(find.byType(Checkbox), findsOneWidget);
      await tester.tap(find.byType(Checkbox));
      await tester.pumpAndSettle();
      expect(find.textContaining('Für Eltern freigeben'), findsOneWidget);
    });

    testWidgets('the management edits learning material like a course', (tester) async {
      tester.view.physicalSize = const Size(800, 1400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final calls = <String>[];
      final sections = [
        {'id': 's1', 'scope': 'general', 'kind': 'material', 'hidden': false, 'child_name': '', 'title': 'Letters', 'body': '', 'author': 'M', 'files': [{'id': 'f1', 'filename': 'Alif.pdf', 'media_type': 'application/pdf', 'size': 10}]},
        {'id': 's2', 'scope': 'general', 'kind': 'material', 'hidden': true, 'child_name': '', 'title': 'Numbers', 'body': '', 'author': 'M', 'files': []},
      ];
      final session = Session(ApiClient(client: MockClient((r) async {
        if (r.method != 'GET') calls.add('${r.method} ${r.url.path}');
        return r.method == 'DELETE' ? http.Response('', 204) : json(sections);
      })));
      await tester.pumpWidget(MaterialApp(
        locale: const Locale('en'),
        supportedLocales: S.supported,
        localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
        home: SessionScope(session: session, child: const Scaffold(body: CourseEditor())),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Letters'), findsOneWidget);
      expect(find.text('Hidden from parents'), findsOneWidget);
      expect(find.text('Add files'), findsWidgets);
      // the hidden section is shown again from its menu
      await tester.tap(find.byIcon(Icons.more_vert).at(2));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Show to parents'));
      await tester.pumpAndSettle();
      expect(calls, ['PATCH /api/platform/manager/materials/s2']);
      // a file is removed from its menu after a confirmation
      await tester.tap(find.byIcon(Icons.more_vert).at(1));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete file'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
      await tester.pumpAndSettle();
      expect(calls.last, 'DELETE /api/platform/manager/materials/s1/files/f1');
    });

    testWidgets('the management returns a report with a reason and sees the child and the files', (tester) async {
      tester.view.physicalSize = const Size(800, 1400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final calls = <String>[];
      Object? sent;
      final report = {'id': 'r1', 'child_id': 'c1', 'child_name': 'Amal', 'title': 'Happy day', 'body': 'Played', 'activities': '', 'meals': '', 'status': 'submitted', 'review_note': ''};
      final session = Session(ApiClient(client: MockClient((r) async {
        if (r.method == 'PATCH') {
          calls.add('PATCH ${r.url.path}');
          sent = jsonDecode(r.body);
          return json({...report, 'status': 'rejected'});
        }
        if (r.url.path.endsWith('/attachments')) return json([{'id': 'f1', 'filename': 'photo.pdf', 'media_type': 'application/pdf', 'size': 20}]);
        return json([report]);
      })));
      await tester.pumpWidget(MaterialApp(
        locale: const Locale('en'),
        supportedLocales: S.supported,
        localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
        builder: (context, child) => SessionScope(session: session, child: child!),
        home: const Scaffold(body: ReviewReports()),
      ));
      await tester.pumpAndSettle();
      expect(find.textContaining('Amal'), findsOneWidget);
      await tester.tap(find.text('Happy day'));
      await tester.pumpAndSettle();
      expect(find.text('photo.pdf'), findsOneWidget);
      await tester.tap(find.text('Return to teacher'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'Please add the meals.');
      await tester.tap(find.widgetWithText(FilledButton, 'Return to teacher'));
      await tester.pumpAndSettle();
      expect(calls, ['PATCH /api/platform/review/reports/r1']);
      expect(sent, {'status': 'rejected', 'note': 'Please add the meals.'});
    });

    testWidgets('a parent sees the attachments of a published report', (tester) async {
      tester.view.physicalSize = const Size(800, 1400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final paths = <String>[];
      final session = Session(ApiClient(client: MockClient((r) async {
        paths.add(r.url.path);
        return json([{'id': 'f1', 'filename': 'trip.pdf', 'media_type': 'application/pdf', 'size': 20}]);
      })));
      await tester.pumpWidget(MaterialApp(
        locale: const Locale('en'),
        supportedLocales: S.supported,
        localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
        home: SessionScope(session: session, child: Scaffold(body: ReportCard(Report(id: 'r1', childId: 'c1', title: 'T', body: 'B', activities: '', meals: '', status: 'published'), files: 'parent'))),
      ));
      await tester.pumpAndSettle();
      expect(find.text('trip.pdf'), findsOneWidget);
      expect(paths, ['/api/platform/children/c1/reports/r1/attachments']);
    });

    testWidgets('a returned report shows the reason and leaving with unsaved text asks first', (tester) async {
      tester.view.physicalSize = const Size(800, 1400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final session = Session(ApiClient(client: MockClient((_) async => json([]))));
      final report = Report(id: 'r1', childId: 'c1', title: 'T', body: 'B', activities: '', meals: '', status: 'rejected', reviewNote: 'Please add the meals.');
      await tester.pumpWidget(MaterialApp(
        locale: const Locale('en'),
        supportedLocales: S.supported,
        localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
        builder: (context, child) => SessionScope(session: session, child: child!),
        home: Builder(builder: (context) => Scaffold(body: TextButton(onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ReportEditor(report: report, children: [Child('c1', 'Amal')]))), child: const Text('open')))),
      ));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      expect(find.text('Please add the meals.'), findsOneWidget);
      // nothing typed yet: leaving is free
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.byType(ReportEditor), findsNothing);
      // typed text: the app asks, "Cancel" stays, "Leave" goes
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).first, 'New title');
      await tester.pump();
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('You have unsaved changes. Leave anyway?'), findsOneWidget);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(find.byType(ReportEditor), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.tap(find.text('Leave'));
      await tester.pumpAndSettle();
      expect(find.byType(ReportEditor), findsNothing);
    });

    testWidgets('German login is left-to-right', (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final session = Session(ApiClient(client: MockClient((_) async => json({}))));
      await tester.pumpWidget(host(session, const Locale('de')));
      expect(Directionality.of(tester.element(find.byType(LoginPage))), TextDirection.ltr);
      expect(find.text('Benutzername'), findsOneWidget);
    });

    testWidgets('a wrong password shows the message from the app, not the server text', (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final session = Session(ApiClient(client: MockClient((_) async => json({'detail': 'Incorrect username or password.'}, 401))));
      await tester.pumpWidget(host(session, const Locale('de')));
      await tester.enterText(find.byType(TextFormField).first, 'x');
      await tester.enterText(find.byType(TextFormField).last, 'y');
      await tester.tap(find.byType(FilledButton));
      await tester.pumpAndSettle();
      expect(find.text('Benutzername oder Passwort falsch.'), findsOneWidget);
    });
  });

  group('accounting', () {
    test('an accountant has the accounting area in the app; several roles choose first', () async {
      final only = Session(ApiClient(client: MockClient((r) async => r.url.path.endsWith('/auth/me')
          ? json({'id': 'a1', 'username': 'acc', 'roles': ['accountant'], 'active_role': 'accountant'})
          : json({'access_token': 't', 'active_role': 'accountant', 'roles': ['accountant']}))));
      await only.login('acc', 'x');
      expect((only.hasMobileArea, only.area), (true, Area.accounting));
      expect(only.areas, [Area.accounting]);
      expect(Session.roleOf[Area.accounting], 'accountant');
      final both = Session(ApiClient(client: MockClient((r) async => r.url.path.endsWith('/auth/me')
          ? json({'id': 'a2', 'username': 'm', 'roles': ['manager', 'accountant'], 'active_role': null})
          : json({'access_token': 't'}))));
      await both.login('m', 'x');
      expect(both.areas, [Area.management, Area.accounting]);
      expect(both.needsAreaChoice, true);
    });

    test('amounts are only formatted, never computed; months turn over the year', () {
      expect(moneyText('1234567.5'), '1,234,567.5');
      expect(moneyText('-300000'), '-300,000');
      expect(moneyText(null), '—');
      expect((shiftMonth('2026-01', -1), shiftMonth('2026-12', 1)), ('2025-12', '2027-01'));
      expect(monthTitle('ar', '2026-11'), 'تشرين الثاني 2026');
      expect(monthTitle('de', '2026-03'), 'März 2026');
    });

    Map<String, dynamic> meta({bool export = false, bool correct = false, bool manage = false}) => {
          'role': manage ? 'manager' : 'accountant', 'name': 'acc', 'today': '2026-11-16',
          'rights': {'record': true, 'correct': correct, 'export': export, 'manage': manage},
          'rate': {'syp_per_usd': '12000', 'valid_from': '2026-11-16', 'by': 'auto', 'source': 'auto', 'stale': false},
          'income_categories': [{'id': 'c1', 'key': 'tuition', 'name': 'Fees', 'is_active': true}],
          'expense_categories': [{'key': 'food', 'ar': 'الطعام', 'en': 'Food'}, {'key': 'salaries', 'ar': 'الرواتب', 'en': 'Salaries'}],
        };

    Widget page(Widget child, http.Response Function(http.Request) answer) {
      final session = Session(ApiClient(client: MockClient((r) async => answer(r))))..api.token = 't';
      return MaterialApp(
        locale: const Locale('en'),
        supportedLocales: S.supported,
        localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
        builder: (context, c) => SessionScope(session: session, child: c!),
        home: Scaffold(body: child),
      );
    }

    void tall(WidgetTester tester) {
      tester.view.physicalSize = const Size(900, 2600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
    }

    final pair = {'usd': '0.00', 'syp': '0'};
    Map<String, dynamic> summary(String month, {bool closed = false}) => {
          'month': month, 'previous_month': shiftMonth(month, -1), 'closed': closed, 'closing': closed ? {'by': 'boss', 'at': null} : null,
          'income': {'usd': '40.00', 'syp': '500000'}, 'expense': {'usd': '0.00', 'syp': '360000'}, 'surplus': {'usd': '40.00', 'syp': '140000'},
          'salaries': {'usd': '0.00', 'syp': '300000'}, 'other_expenses': pair, 'income_count': 3, 'expense_count': 2,
          'income_by_category': [{'category_id': 'c1', 'key': 'tuition', 'name': 'Fees', 'usd': '40.00', 'syp': '0', 'count': 2}],
          'expense_by_category': [{'category': 'food', 'ar': 'الطعام', 'en': 'Food', 'usd': '0.00', 'syp': '60000', 'count': 1}],
          'previous': {'income': pair, 'expense': pair, 'surplus': pair},
          'change': {
            for (final k in ['income', 'expense', 'surplus'])
              k: {'usd': {'difference': '40.00', 'percent': null}, 'syp': {'difference': '-20000', 'percent': '-12.5'}},
          },
          'converted': {'income': pair, 'expense': pair, 'surplus': pair},
          'invoices': {'open': 0, 'partial': 1, 'open_amount': {'usd': '15.00', 'syp': '0'}},
          'balance': {'start': {'usd': '1000.00', 'syp': '5000000'}, 'end': {'usd': '1040.00', 'syp': '5140000'}, 'profit': {'usd': '40.00', 'syp': '140000'}, 'opening': {'USD': {'as_of': '2026-10-01'}}},
        };

    testWidgets('the month overview shows profit or loss, the change and the cash in dollars and pounds', (tester) async {
      tall(tester);
      await tester.pumpWidget(page(const MoneySummaryPage(), (r) {
        if (r.url.path.endsWith('/meta')) return json(meta());
        return json(summary(r.url.queryParameters['month']!));
      }));
      await tester.pumpAndSettle();
      expect(find.text(monthTitle('en', monthKey(DateTime.now()))), findsOneWidget);
      expect(find.text('Profit / loss'), findsWidgets);
      expect(find.text('Profit in dollars'), findsOneWidget); // said in words, not only by the sign
      expect(find.text('Profit in pounds'), findsOneWidget);
      expect(find.text('SYP 140,000'), findsWidgets);
      expect(find.text('USD 1,040.00'), findsOneWidget); // the cash at the end of the month
      expect(find.text('Fees'), findsOneWidget);
      expect(find.textContaining('-12.5%'), findsWidgets); // the change against the month before
      expect(find.text('Month report as PDF'), findsNothing); // no export right
      expect(find.text('Close the month'), findsNothing); // no management right
      expect(find.text('Enter the cash balance'), findsNothing);
    });

    testWidgets('the management closes a past month (after asking) and may correct the cash', (tester) async {
      tall(tester);
      final posted = <String, Object?>{};
      await tester.pumpWidget(page(const MoneySummaryPage(), (r) {
        if (r.url.path.endsWith('/meta')) return json(meta(export: true, manage: true));
        if (r.method == 'POST') {
          posted[r.url.path] = jsonDecode(r.body);
          return json({'closed': true}, 201);
        }
        return json(summary(r.url.queryParameters['month']!, closed: posted.isNotEmpty));
      }));
      await tester.pumpAndSettle();
      expect(find.text('Month report as PDF'), findsOneWidget);
      expect(find.text('Correct the balance'), findsOneWidget);
      expect(find.text('Close the month'), findsNothing); // the running month cannot be closed yet
      await tester.tap(find.byTooltip('Previous month'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Close the month'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Close the month'));
      await tester.pumpAndSettle();
      final before = shiftMonth(monthKey(DateTime.now()), -1).split('-');
      expect(posted['/api/admin/money/closings'], {'year': int.parse(before[0]), 'month': int.parse(before[1])});
      expect(find.text('Reopen the month'), findsOneWidget);
    });

    Map<String, dynamic> donation() => {
          'id': 'e1', 'booked_on': '2026-11-16', 'description': 'Donation', 'category_id': 'c1', 'category': 'Fees', 'child_id': '', 'child': '', 'payer_name': 'Club',
          'amount': '500000', 'currency': 'SYP', 'rate': '12000', 'usd': '41.67', 'syp': '500000', 'note': '', 'voided': false, 'is_reversal': false, 'reversed': false,
          'invoice_id': '', 'invoice_number': '', 'version': 3, 'month_closed': false, 'created_by': 'acc',
        };

    http.Response incomeServer(http.Request r, List<(String, String, Map<String, dynamic>)> calls, {bool correct = false}) {
      final path = r.url.path;
      if (path.endsWith('/meta')) return json(meta(correct: correct, manage: correct, export: correct));
      if (r.method != 'GET') {
        calls.add((r.method, path, jsonDecode(r.body) as Map<String, dynamic>));
        if (path.endsWith('/money/invoices')) return json({'id': 'i9', 'number': 'INV-2026-0002'}, 201);
        return json({'id': 'e2'}, 201);
      }
      if (path.endsWith('/invoices/i9')) {
        return json({
          'id': 'i9', 'number': 'INV-2026-0002', 'issued_on': '2026-11-16', 'child_id': '', 'child': '', 'payer_name': 'Club', 'description': '', 'currency': 'USD', 'rate': '12000',
          'items': [{'description': 'Trip', 'usd': '10.00', 'syp': '120000'}], 'total': {'usd': '10.00', 'syp': '120000'}, 'paid': pair, 'open': {'usd': '10.00', 'syp': '120000'},
          'status': 'open', 'voided': false, 'void_reason': null, 'payments': [],
        });
      }
      if (path.endsWith('/invoices')) {
        return json({'rows': [{'id': 'i1', 'number': 'INV-2026-0001', 'issued_on': '2026-11-02', 'child': 'Amal', 'payer_name': '', 'description': '', 'status': 'partial',
          'total': {'usd': '30.00', 'syp': '360000'}, 'open': {'usd': '15.00', 'syp': '180000'}}]});
      }
      if (path.contains('/history/')) return json([{'at': '2026-11-16T09:30:00', 'actor': 'acc', 'action': 'income.create', 'reason': ''}]);
      if (path.endsWith('/children')) return json([{'id': 'k1', 'name': 'Amal'}]);
      if (path.endsWith('/employees')) return json([{'id': 'p1', 'name': 'Rama Al-Dairi'}]);
      if (path.endsWith('/salaries')) {
        return json({'month': '2026-11', 'paid': 1, 'unpaid': 1, 'rows': [
          {'employee_id': 'p1', 'name': 'Rama Al-Dairi', 'job_title': 'Teacher of the small group', 'is_active': true, 'salary': '1100000', 'salary_currency': 'SYP',
           'paid': true, 'automatic': true, 'paid_amount': '1100000', 'paid_currency': 'SYP'},
          {'employee_id': 'p2', 'name': 'Someone With A Rather Long Name', 'job_title': 'Cook', 'is_active': true, 'salary': null, 'salary_currency': 'SYP', 'paid': false, 'automatic': false},
        ]});
      }
      if (path.endsWith('/expenses')) {
        return json({'rows': [{...donation(), 'category': 'salaries', 'category_ar': 'الرواتب', 'category_en': 'Salaries', 'recipient': 'Rama', 'employee_id': 'p1', 'employee': 'Rama Al-Dairi', 'salary_month': '2026-10'}],
          'totals': {'USD': '0', 'SYP': '500000', 'value': {'USD': '41.67', 'SYP': '500000'}}, 'count': 1});
      }
      return json({'rows': [donation()], 'totals': {'USD': '0', 'SYP': '500000', 'value': {'USD': '41.67', 'SYP': '500000'}}, 'count': 1});
    }

    testWidgets('income: the entries with both currencies, the open invoices, and a new entry through the form', (tester) async {
      tall(tester);
      final calls = <(String, String, Map<String, dynamic>)>[];
      await tester.pumpWidget(page(const MoneyEntriesPage(kind: 'income'), (r) => incomeServer(r, calls)));
      await tester.pumpAndSettle();
      expect(find.text('Donation'), findsOneWidget);
      expect(find.text('USD 41.67'), findsWidgets);
      expect(find.text('INV-2026-0001 · Amal'), findsOneWidget);
      expect(find.text('Income categories'), findsNothing); // only for the management
      await tester.tap(find.text('New income'));
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextField, 'Reason'), 'November fee');
      await tester.enterText(find.widgetWithText(TextField, 'Amount'), '25');
      await tester.pump();
      expect(find.text('≈ SYP 300,000'), findsOneWidget); // only a hint; the server calculates the real value
      await tester.tap(find.text('Record'));
      await tester.pumpAndSettle();
      final (method, path, body) = calls.single;
      expect((method, path), ('POST', '/api/admin/money/income'));
      expect((body['amount'], body['currency'], body['category_id']), ('25', 'USD', 'c1'));
      expect(body.containsKey('rate'), isFalse); // only the management sends a rate of its own
    });

    testWidgets('an entry opens with its history; with the right to correct it is changed with its version', (tester) async {
      tall(tester);
      final calls = <(String, String, Map<String, dynamic>)>[];
      await tester.pumpWidget(page(const MoneyEntriesPage(kind: 'income'), (r) => incomeServer(r, calls, correct: true)));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Donation'));
      await tester.pumpAndSettle();
      expect(find.text('History'), findsOneWidget);
      expect(find.textContaining('recorded'), findsOneWidget);
      expect(find.text('Cancel the entry'), findsOneWidget);
      await tester.tap(find.text('Edit'));
      await tester.pumpAndSettle();
      expect(find.text('Change the income'), findsOneWidget);
      await tester.enterText(find.widgetWithText(TextField, 'Reason'), 'Donation of the club');
      await tester.tap(find.text('Save change'));
      await tester.pumpAndSettle();
      final (method, path, body) = calls.single;
      expect((method, path), ('PATCH', '/api/admin/money/income/e1'));
      expect((body['description'], body['amount'], body['currency'], body['expected_version']), ('Donation of the club', '500000', 'SYP', 3));
    });

    testWidgets('a loss is called a loss and shown without the minus sign', (tester) async {
      tall(tester);
      await tester.pumpWidget(page(const MoneySummaryPage(), (r) {
        if (r.url.path.endsWith('/meta')) return json(meta());
        return json({...summary(r.url.queryParameters['month']!), 'surplus': {'usd': '-700.00', 'syp': '0'}});
      }));
      await tester.pumpAndSettle();
      expect(find.text('Loss in dollars'), findsOneWidget);
      expect(find.text('No profit, no loss in pounds'), findsOneWidget);
      expect(find.text('USD 700.00'), findsOneWidget);
    });

    testWidgets('an invoice is changed through the same form (with the right to correct)', (tester) async {
      tall(tester);
      final calls = <(String, String, Map<String, dynamic>)>[];
      await tester.pumpWidget(page(InvoicePage(id: 'i9', meta: MoneyMeta(meta(correct: true))), (r) => incomeServer(r, calls, correct: true)));
      await tester.pumpAndSettle();
      expect(find.text('History'), findsOneWidget);
      await tester.tap(find.text('Edit invoice'));
      await tester.pumpAndSettle();
      expect(find.text('Edit invoice INV-2026-0002'), findsOneWidget);
      await tester.enterText(find.widgetWithText(TextField, 'Amount (USD)'), '12');
      await tester.tap(find.text('Save change'));
      await tester.pumpAndSettle();
      final (method, path, body) = calls.single;
      expect((method, path, body['payer_name']), ('PATCH', '/api/admin/money/invoices/i9', 'Club'));
      expect(body['items'], [{'description': 'Trip', 'amount': '12'}]);
    });

    testWidgets('a new invoice with its items is created and then opened', (tester) async {
      tall(tester);
      final calls = <(String, String, Map<String, dynamic>)>[];
      await tester.pumpWidget(page(const MoneyEntriesPage(kind: 'income'), (r) => incomeServer(r, calls)));
      await tester.pumpAndSettle();
      await tester.tap(find.text('New invoice'));
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextField, 'or the payer'), 'Club');
      await tester.enterText(find.widgetWithText(TextField, 'Item 1'), 'Trip');
      await tester.enterText(find.widgetWithText(TextField, 'Amount (USD)'), '10');
      await tester.tap(find.text('Create invoice'));
      await tester.pumpAndSettle();
      final (method, path, body) = calls.single;
      expect((method, path), ('POST', '/api/admin/money/invoices'));
      expect((body['payer_name'], body['currency']), ('Club', 'USD'));
      expect(body['items'], [{'description': 'Trip', 'amount': '10'}]);
      expect(find.text('INV-2026-0002'), findsOneWidget); // the invoice page
      expect(find.text('Record a payment'), findsWidgets);
    });
    testWidgets('the pages fit a phone screen in Arabic without overflowing', (tester) async {
      tester.view.physicalSize = const Size(390, 3000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final calls = <(String, String, Map<String, dynamic>)>[];
      for (final child in [const MoneySummaryPage(), const MoneyEntriesPage(kind: 'income'), const MoneyEntriesPage(kind: 'expenses')]) {
        final session = Session(ApiClient(client: MockClient((r) async {
          if (r.url.path.endsWith('/summary')) return json(summary(r.url.queryParameters['month']!));
          return incomeServer(r, calls, correct: true);
        })))..api.token = 't';
        await tester.pumpWidget(MaterialApp(
          locale: const Locale('ar'),
          supportedLocales: S.supported,
          localizationsDelegates: const [GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate, GlobalCupertinoLocalizations.delegate],
          builder: (context, c) => SessionScope(session: session, child: c!),
          home: Scaffold(body: child),
        ));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      }
    });
  });
}
