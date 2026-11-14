import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config/config.dart';

enum ApiProblem { offline, unauthorized, forbidden, notFound, tooMany, pending, disabled, bad, server }

class ApiException implements Exception {
  ApiException(this.problem, {this.status = 0, this.detail = ''});
  final ApiProblem problem;
  final int status;
  final String detail;
  @override
  String toString() => 'ApiException($problem, $status, $detail)';
}

class Cached<T> {
  Cached(this.data, {this.fromCache = false});
  final T data;
  final bool fromCache;
}

/// The only place that talks to the existing FastAPI backend. All rights are checked by the server;
/// the app never decides who may see what.
class ApiClient {
  ApiClient({http.Client? client}) : _http = client ?? http.Client();

  final http.Client _http;
  String? token;
  String cacheOwner = '';

  /// Called when the server says the session is over (HTTP 401 on a call that carried a token).
  void Function()? onSessionEnded;

  static const _timeout = Duration(seconds: 60); // the free server may need a while to wake up

  Uri _uri(String path, [Map<String, String>? query]) {
    final base = Uri.parse(AppConfig.apiBase);
    return base.replace(path: path, queryParameters: query);
  }

  Map<String, String> _headers({bool json = true}) => {
        if (token != null) 'Authorization': 'Bearer $token',
        if (json) 'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  Future<http.Response> _send(Future<http.Response> Function() call) async {
    try {
      return await call().timeout(_timeout);
    } on SocketException {
      throw ApiException(ApiProblem.offline);
    } on TimeoutException {
      throw ApiException(ApiProblem.offline);
    } on http.ClientException {
      throw ApiException(ApiProblem.offline);
    }
  }

  dynamic _decode(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.bodyBytes.isEmpty) return null;
      return jsonDecode(utf8.decode(response.bodyBytes));
    }
    String detail = '';
    try {
      final body = jsonDecode(utf8.decode(response.bodyBytes));
      if (body is Map && body['detail'] is String) detail = body['detail'] as String;
    } catch (_) {}
    final status = response.statusCode;
    if (status == 401) {
      if (token != null) onSessionEnded?.call();
      throw ApiException(ApiProblem.unauthorized, status: status, detail: detail);
    }
    if (status == 403) {
      final lower = detail.toLowerCase();
      if (lower.contains('awaiting')) throw ApiException(ApiProblem.pending, status: status, detail: detail);
      if (lower.contains('disabled')) throw ApiException(ApiProblem.disabled, status: status, detail: detail);
      throw ApiException(ApiProblem.forbidden, status: status, detail: detail);
    }
    if (status == 404) throw ApiException(ApiProblem.notFound, status: status, detail: detail);
    if (status == 429) throw ApiException(ApiProblem.tooMany, status: status, detail: detail);
    if (status >= 500) throw ApiException(ApiProblem.server, status: status, detail: detail);
    throw ApiException(ApiProblem.bad, status: status, detail: detail);
  }

  Future<dynamic> get(String path, {Map<String, String>? query}) async =>
      _decode(await _send(() => _http.get(_uri(path, query), headers: _headers())));

  Future<dynamic> post(String path, [Object? body]) async => _decode(await _send(
      () => _http.post(_uri(path), headers: _headers(), body: body == null ? null : jsonEncode(body))));

  Future<dynamic> patch(String path, Object body) async =>
      _decode(await _send(() => _http.patch(_uri(path), headers: _headers(), body: jsonEncode(body))));

  Future<dynamic> delete(String path) async =>
      _decode(await _send(() => _http.delete(_uri(path), headers: _headers())));

  /// multipart/form-data with files (reports' attachments, posts, teaching material).
  ///
  /// `onProgress` (0 to 1) reports how much of the request has been handed over for sending.
  Future<dynamic> multipart(String path, Map<String, String> fields, List<UploadFile> files, {String fileField = 'files', void Function(double)? onProgress}) async {
    return _decode(await _send(() async {
      final request = http.MultipartRequest('POST', _uri(path));
      request.headers.addAll(_headers(json: false));
      request.fields.addAll(fields);
      for (final f in files) {
        request.files.add(await http.MultipartFile.fromPath(fileField, f.path, filename: f.name));
      }
      if (onProgress == null) return http.Response.fromStream(await _http.send(request));
      final total = request.contentLength;
      final body = request.finalize(); // sets the multipart content type
      final streamed = http.StreamedRequest('POST', request.url)
        ..headers.addAll(request.headers)
        ..contentLength = total;
      var sent = 0;
      body.listen(
        (chunk) {
          sent += chunk.length;
          streamed.sink.add(chunk);
          onProgress(total == 0 ? 1.0 : (sent / total).clamp(0.0, 1.0));
        },
        onDone: streamed.sink.close,
        onError: (Object e, StackTrace st) {
          streamed.sink.addError(e, st);
          streamed.sink.close();
        },
      );
      return http.Response.fromStream(await _http.send(streamed));
    }));
  }

  /// Private files are fetched with the token; there are no public links.
  Future<List<int>> bytes(String path) async {
    final response = await _send(() => _http.get(_uri(path), headers: _headers(json: false)));
    if (response.statusCode >= 200 && response.statusCode < 300) return response.bodyBytes;
    _decode(response);
    throw ApiException(ApiProblem.server);
  }

  // ---- reading with a saved copy for bad connections --------------------------------------------------------------
  // Only lists the person may see anyway are kept (reports, posts, notices). The copy belongs to one account and is
  // removed at sign-out.
  String _cacheKey(String path) => 'cache:$cacheOwner:$path';

  Future<Cached<dynamic>> getCached(String path) async {
    final prefs = await SharedPreferences.getInstance();
    try {
      final data = await get(path);
      if (cacheOwner.isNotEmpty) await prefs.setString(_cacheKey(path), jsonEncode(data));
      return Cached(data);
    } on ApiException catch (e) {
      if (e.problem == ApiProblem.offline || e.problem == ApiProblem.server) {
        final saved = prefs.getString(_cacheKey(path));
        if (saved != null && cacheOwner.isNotEmpty) return Cached(jsonDecode(saved), fromCache: true);
      }
      rethrow;
    }
  }

  Future<void> clearCache() async {
    final prefs = await SharedPreferences.getInstance();
    for (final key in prefs.getKeys().where((k) => k.startsWith('cache:') || k.startsWith('draft:'))) {
      await prefs.remove(key);
    }
  }
}

class UploadFile {
  UploadFile(this.path, this.name);
  final String path;
  final String name;
}
