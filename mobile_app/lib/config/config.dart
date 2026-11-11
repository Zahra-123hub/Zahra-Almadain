/// Settings of the app. The server is the existing FastAPI backend; nothing else is contacted.
class AppConfig {
  /// Can be changed at build time: flutter build apk --dart-define=API_BASE=https://...
  static const String apiBase = String.fromEnvironment(
    'API_BASE',
    defaultValue: 'https://zahra-123hub-almadain-api.onrender.com',
  );
  static const String version = '1.0.1';
  static const String supportMail = 'info@zahratalmadain.com';
}
