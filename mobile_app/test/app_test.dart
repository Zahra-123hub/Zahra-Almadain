import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:zahra_app/features/auth/login_page.dart';
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

    test('a manager who is also a teacher and a parent may open three areas, and the last one is remembered', () async {
      Session make() => Session(ApiClient(client: MockClient((_) async => json({'id': 'a1', 'username': 'x', 'roles': ['parent', 'teacher', 'manager']}))))..api.token = null;
      final session = make();
      await session.start();
      expect(session.areas, [Area.management, Area.teacher, Area.parent]);
      expect(session.area, Area.management);
      await session.setArea(Area.parent);
      final again = make();
      await again.start();
      expect(again.area, Area.parent);
    });

    test('admin and accounting accounts have no area in the app', () async {
      final session = Session(ApiClient(client: MockClient((_) async => json({'id': 'a1', 'username': 'x', 'roles': ['admin', 'accountant']}))))..api.token = 'abc';
      await session.start();
      expect(session.areas, isEmpty);
      expect(session.hasMobileArea, isFalse);
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
}
