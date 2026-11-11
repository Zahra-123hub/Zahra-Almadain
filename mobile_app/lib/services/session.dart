import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/config.dart';
import 'api.dart';

enum Area { parent, teacher }

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
  VersionInfo? versionInfo;

  bool get signedIn => api.token != null && username != null;
  bool get isParent => roles.contains('parent');
  bool get isTeacher => roles.contains('teacher');
  bool get hasMobileArea => isParent || isTeacher;

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
    area ??= isTeacher && !isParent ? Area.teacher : (isParent ? Area.parent : null);
    if (isTeacher && isParent) {
      final last = prefs.getString('area');
      area = last == 'teacher' ? Area.teacher : Area.parent;
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

  Future<void> setArea(Area value) async {
    area = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('area', value == Area.teacher ? 'teacher' : 'parent');
    notifyListeners();
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
