import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/config.dart';
import 'api.dart';

enum Area { parent, teacher, management }

/// Who is signed in, which area is open, which language is used.
class Session extends ChangeNotifier {
  Session(this.api) {
    api.onSessionEnded = _expired;
  }

  final ApiClient api;
  static const _storage = FlutterSecureStorage();
  static const _tokenKey = 'access_token';

  bool ready = false;
  String? username;
  String? accountId;
  List<String> roles = [];
  Locale locale = const Locale('ar');
  Area? area;
  bool sessionEnded = false;
  String? activeRole; // the role the server has this session working in (null: not chosen yet)
  String? lastArea; // the area used last time, offered first on the choice screen
  VersionInfo? versionInfo;

  bool get signedIn => api.token != null && username != null;
  bool get isParent => roles.contains('parent');
  bool get isTeacher => roles.contains('teacher');
  bool get isManager => roles.contains('manager');
  bool get hasMobileArea => isParent || isTeacher || isManager;

  /// The role name the server uses for each area of the app.
  static const roleOf = {Area.management: 'manager', Area.teacher: 'teacher', Area.parent: 'parent'};

  /// Signed in with several areas and none chosen yet: the choice screen comes first.
  bool get needsAreaChoice => signedIn && hasMobileArea && areas.length > 1 && area == null;

  /// The areas this account may open, in the order they are offered.
  List<Area> get areas => [if (isManager) Area.management, if (isTeacher) Area.teacher, if (isParent) Area.parent];

  Future<void> start() async {
    final prefs = await SharedPreferences.getInstance();
    final lang = prefs.getString('lang');
    if (lang != null) locale = Locale(lang);
    await _checkVersion();
    final saved = await _storage.read(key: _tokenKey);
    if (saved != null) {
      api.token = saved;
      try {
        await _loadMe();
      } on ApiException catch (e) {
        // offline at start: keep the token and let the screens show saved data; a dead token is dropped by the 401 hook
        if (e.problem != ApiProblem.offline && e.problem != ApiProblem.server) await _clear();
      }
    }
    ready = true;
    notifyListeners();
  }

  Future<void> _checkVersion() async {
    try {
      final data = await api.get('/api/app/version', query: {'version': AppConfig.version});
      versionInfo = VersionInfo.fromJson(data as Map<String, dynamic>);
    } catch (_) {}
  }

  Future<void> _loadMe() async {
    final me = await api.get('/api/platform/auth/me') as Map<String, dynamic>;
    username = me['username'] as String;
    accountId = me['id'] as String;
    roles = List<String>.from(me['roles'] as List);
    api.cacheOwner = accountId!;
    final preferred = me['preferred_language'] as String?;
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getString('lang') == null && preferred != null && LanguageCodes.has(preferred)) locale = Locale(preferred);
    activeRole = me['active_role'] as String?;
    lastArea = prefs.getString('area');
    final open = areas;
    if (open.isEmpty) {
      area = null;
    } else if (open.length == 1) {
      area = open.first;
      if (activeRole != roleOf[area]) await _bind(area!); // the server should know too (best effort)
    } else {
      // an area is taken over only when the SERVER says the session already works in it; otherwise the person chooses
      final fromServer = open.where((a) => roleOf[a] == activeRole);
      area = fromServer.isEmpty ? null : fromServer.first;
    }
  }

  /// Tells the server which role this session works in. It answers with a new token for it (the old one ends).
  /// A server that does not know the call yet (404) is not an error: the area is then only remembered here.
  Future<void> _bind(Area target) async {
    try {
      final result = await api.post('/api/platform/auth/switch-role', {'role': roleOf[target]}) as Map<String, dynamic>;
      api.token = result['access_token'] as String;
      await _storage.write(key: _tokenKey, value: api.token);
      activeRole = result['active_role'] as String?;
    } on ApiException catch (e) {
      if (e.problem != ApiProblem.notFound && e.problem != ApiProblem.offline && e.problem != ApiProblem.server) rethrow;
    }
  }

  Future<void> login(String user, String password) async {
    sessionEnded = false;
    final result = await api.post('/api/platform/auth/login', {'username': user.trim(), 'password': password});
    api.token = result['access_token'] as String;
    await _storage.write(key: _tokenKey, value: api.token);
    await _loadMe();
    notifyListeners();
  }

  Future<void> logout() async {
    try {
      await api.post('/api/platform/auth/logout');
    } catch (_) {}
    await _clear();
    notifyListeners();
  }

  void _expired() {
    if (!signedIn) return;
    sessionEnded = true;
    _clear().then((_) => notifyListeners());
  }

  Future<void> _clear() async {
    api.token = null;
    api.cacheOwner = '';
    username = null;
    accountId = null;
    roles = [];
    area = null;
    activeRole = null;
    await _storage.delete(key: _tokenKey);
    await api.clearCache();
  }

  Future<void> setLocale(String code) async {
    locale = Locale(code);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('lang', code);
    notifyListeners();
    if (signedIn) {
      try {
        await api.patch('/api/platform/auth/language', {'language': code});
      } catch (_) {}
    }
  }

  /// Chooses (or changes) the area. The server is told first; a refused role changes nothing.
  Future<void> chooseArea(Area value) async {
    await _bind(value);
    area = value;
    lastArea = value.name;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('area', value.name);
    notifyListeners();
  }

  Future<void> setArea(Area value) async {
    try {
      await chooseArea(value);
    } on ApiException {
      // refused (for example 403): the area stays as it was
    }
  }
}

class LanguageCodes {
  static bool has(String code) => const ['ar', 'de', 'en'].contains(code);
}

class VersionInfo {
  VersionInfo({required this.updateRequired, required this.updateAvailable, required this.latest, required this.androidUrl, required this.iosUrl});
  final bool updateRequired;
  final bool updateAvailable;
  final String latest;
  final String androidUrl;
  final String iosUrl;

  factory VersionInfo.fromJson(Map<String, dynamic> json) => VersionInfo(
        updateRequired: json['update_required'] == true,
        updateAvailable: json['update_available'] == true,
        latest: (json['latest'] ?? '') as String,
        androidUrl: (json['android_url'] ?? '') as String,
        iosUrl: (json['ios_url'] ?? '') as String,
      );
}
