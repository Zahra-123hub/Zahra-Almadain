// Plain data classes for what the existing API returns.

String _s(dynamic v) => v == null ? '' : v.toString();

DateTime? _date(dynamic v) => v == null ? null : DateTime.tryParse(v.toString())?.toLocal();

class Child {
  Child(this.id, this.name);
  final String id;
  final String name;
  factory Child.fromJson(Map<String, dynamic> j) => Child(_s(j['id']), _s(j['display_name']));
}

class Report {
  Report({
    required this.id,
    required this.childId,
    required this.title,
    required this.body,
    required this.activities,
    required this.meals,
    required this.status,
    this.createdAt,
    this.publishedAt,
    this.reviewNote = '',
    this.childName = '',
  });
  final String id;
  final String childId;
  final String title;
  final String body;
  final String activities;
  final String meals;
  final String status; // draft, submitted, published, rejected, archived
  final String reviewNote; // why the management returned it
  final String childName; // only in the management's review list
  final DateTime? createdAt;
  final DateTime? publishedAt;

  DateTime? get day => publishedAt ?? createdAt;

  factory Report.fromJson(Map<String, dynamic> j) => Report(
        id: _s(j['id']),
        childId: _s(j['child_id']),
        title: _s(j['title']),
        body: _s(j['body']),
        activities: _s(j['activities']),
        meals: _s(j['meals']),
        status: _s(j['status']),
        createdAt: _date(j['created_at']),
        publishedAt: _date(j['published_at']),
        reviewNote: _s(j['review_note']),
        childName: _s(j['child_name']),
      );
}

/// Reads a JSON list of objects.
List<T> parseList<T>(dynamic data, T Function(Map<String, dynamic>) make) =>
    (data as List).map((e) => make(e as Map<String, dynamic>)).toList();

class FileInfo {
  FileInfo(this.id, this.filename, this.mediaType, this.size);
  final String id;
  final String filename;
  final String mediaType;
  final int size;
  bool get isImage => mediaType.startsWith('image/');
  factory FileInfo.fromJson(Map<String, dynamic> j) =>
      FileInfo(_s(j['id']), _s(j['filename']), _s(j['media_type']), (j['size'] as num?)?.toInt() ?? 0);
}

class Post {
  Post({required this.id, required this.scope, this.kind = 'post', this.hidden = false, required this.childName, required this.title, required this.body, required this.author, this.createdAt, this.files = const []});
  final String id;
  final String scope; // general | child
  final String kind; // post | material
  final bool hidden; // learning material the management has hidden from the parents
  final String childName;
  final String title;
  final String body;
  final String author;
  final DateTime? createdAt;
  final List<FileInfo> files;

  factory Post.fromJson(Map<String, dynamic> j) => Post(
        id: _s(j['id']),
        scope: _s(j['scope']),
        kind: _s(j['kind']).isEmpty ? 'post' : _s(j['kind']),
        hidden: j['hidden'] == true,
        childName: _s(j['child_name']),
        title: _s(j['title']),
        body: _s(j['body']),
        author: _s(j['author']),
        createdAt: _date(j['created_at']),
        files: ((j['files'] as List?) ?? const []).map((f) => FileInfo.fromJson(f as Map<String, dynamic>)).toList(),
      );
}

class Notice {
  Notice(this.id, this.title, this.body, this.createdAt);
  final String id;
  final String title;
  final String body;
  final DateTime? createdAt;
  factory Notice.fromJson(Map<String, dynamic> j) => Notice(_s(j['id']), _s(j['title']), _s(j['body']), _date(j['created_at']));
}

class AppNotification {
  AppNotification({required this.id, required this.kind, required this.subject, required this.read, this.createdAt});
  final String id;
  final String kind;
  final String subject;
  final bool read;
  final DateTime? createdAt;
  factory AppNotification.fromJson(Map<String, dynamic> j) => AppNotification(
        id: _s(j['id']),
        kind: _s(j['kind']),
        subject: _s(j['subject']),
        read: j['read'] == true,
        createdAt: _date(j['created_at']),
      );
}

class MaterialFile {
  MaterialFile(this.id, this.filename, this.mediaType, this.size, this.category, this.reportId);
  final String id;
  final String filename;
  final String mediaType;
  final int size;
  final String category;
  final String? reportId;
  factory MaterialFile.fromJson(Map<String, dynamic> j) => MaterialFile(
        _s(j['id']),
        _s(j['filename']),
        _s(j['media_type']),
        (j['size'] as num?)?.toInt() ?? 0,
        _s(j['category']),
        j['report_id']?.toString(),
      );
}
