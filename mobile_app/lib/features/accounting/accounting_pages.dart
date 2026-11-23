import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../localization/strings.dart';
import '../../services/api.dart';
import '../../shared/ui.dart';

// The accounting in the app: everything the website has (income with invoices, expenses with salaries, the month overview with
// the cash, the rate, month closings and the PDF documents), on the same server endpoints (/api/admin/money).
// Every amount stands in US dollars and Syrian pounds side by side; amounts come from the server as decimal text and are only
// formatted here, never added up with floating point. Nothing is deleted: an entry is cancelled with a reason, or reversed in a
// closed month. What a person may do comes from the server (`rights` of /meta) and is checked there again.

const _ink = Color(0xFF16253A);
const _muted = Color(0xFF5B6878);
const _faint = Color(0xFF9AA6B5);
const _line = Color(0xFFE3E9F0);
const _good = Color(0xFF1E7A45);
const _goodBg = Color(0xFFE4F4EA);
const _bad = Color(0xFFB3402F);
const _badBg = Color(0xFFFCE9E6);
const _warn = Color(0xFF8A5200);
const _warnBg = Color(0xFFFDF1DD);
const _neutral = Color(0xFF42536A);
const _neutralBg = Color(0xFFEEF2F6);

/// "1234567.5" -> "1,234,567.5". Only the text is changed; there is no arithmetic.
String moneyText(String? text) {
  if (text == null || text.isEmpty) return '—';
  final negative = text.startsWith('-');
  final parts = text.replaceFirst(RegExp(r'^[-+]'), '').split('.');
  final whole = parts[0].replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => ',');
  return '${negative ? '-' : ''}$whole${parts.length > 1 ? '.${parts[1]}' : ''}';
}

bool _negative(String? text) => text != null && text.startsWith('-') && !_zero(text);
bool _zero(String? text) => text == null || RegExp(r'^[-+]?[0.,]*$').hasMatch(text);

const _months = {
  'ar': ['كانون الثاني', 'شباط', 'آذار', 'نيسان', 'أيار', 'حزيران', 'تموز', 'آب', 'أيلول', 'تشرين الأول', 'تشرين الثاني', 'كانون الأول'],
  'de': ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
  'en': ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
};

String monthKey(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}';
String monthTitle(String code, String key) {
  final p = key.split('-');
  return '${(_months[code] ?? _months['en']!)[int.parse(p[1]) - 1]} ${p[0]}';
}

String shiftMonth(String key, int delta) {
  final p = key.split('-');
  return monthKey(DateTime(int.parse(p[0]), int.parse(p[1]) + delta, 1));
}

String dayText(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// What the server says about the person and the accounting: rights, today's rate, the categories.
class MoneyMeta {
  MoneyMeta(this.data);
  final Map<String, dynamic> data;
  Map<String, dynamic> get rights => (data['rights'] as Map).cast<String, dynamic>();
  bool get canCorrect => rights['correct'] == true;
  bool get canExport => rights['export'] == true;
  bool get canManage => rights['manage'] == true;
  Map<String, dynamic>? get rate => (data['rate'] as Map?)?.cast<String, dynamic>();
  String get today => data['today'] as String;
  String get thisMonth => today.substring(0, 7);
  List<Map<String, dynamic>> get incomeCategories => [for (final c in data['income_categories'] as List) (c as Map).cast<String, dynamic>()];
  List<Map<String, dynamic>> get expenseCategories => [for (final c in data['expense_categories'] as List) (c as Map).cast<String, dynamic>()];
}

Future<MoneyMeta> loadMeta(ApiClient api) async => MoneyMeta((await api.get('/api/admin/money/meta') as Map).cast<String, dynamic>());

Map<String, dynamic> _map(Object? v) => (v as Map).cast<String, dynamic>();
List<Map<String, dynamic>> _list(Object? v) => [for (final x in (v as List? ?? const [])) (x as Map).cast<String, dynamic>()];

// ================================================================================================================================
// building blocks
// ================================================================================================================================

/// Loads data, keeps showing the last result while it loads again (a thin bar on top instead of a blank page), and loads
/// again by itself when `signature` changes (another month, another filter).
class _Data<T> extends StatefulWidget {
  const _Data({super.key, required this.signature, required this.load, required this.builder});
  final String signature;
  final Future<T> Function() load;
  final Widget Function(BuildContext context, T data, Future<void> Function() reload) builder;
  @override
  State<_Data<T>> createState() => _DataState<T>();
}

class _DataState<T> extends State<_Data<T>> {
  T? _data;
  Object? _error;
  bool _busy = true;
  int _run = 0;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  @override
  void didUpdateWidget(covariant _Data<T> old) {
    super.didUpdateWidget(old);
    if (old.signature != widget.signature) _reload();
  }

  Future<void> _reload() async {
    final run = ++_run;
    setState(() => _busy = true);
    try {
      final v = await widget.load();
      if (!mounted || run != _run) return;
      setState(() {
        _data = v;
        _error = null;
        _busy = false;
      });
    } catch (e) {
      if (!mounted || run != _run) return;
      setState(() {
        _error = e;
        _busy = false;
      });
      if (_data != null) toast(context, problemText(context, e));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_data == null) return _busy ? const SkeletonList() : StateView.fromError(context, _error, onRetry: _reload);
    return Column(
      children: [
        SizedBox(height: 3, child: _busy ? const LinearProgressIndicator(minHeight: 3) : null),
        Expanded(
          child: RefreshIndicator(onRefresh: _reload, child: widget.builder(context, _data as T, _reload)),
        ),
      ],
    );
  }
}

/// One amount with its currency code: "USD 1,040.00". Zero is shown pale so the eye finds the real numbers.
class Money extends StatelessWidget {
  const Money(this.code, this.value, {super.key, this.size = 15, this.color, this.weight = FontWeight.w700});
  final String code;
  final String? value;
  final double size;
  final Color? color;
  final FontWeight weight;
  @override
  Widget build(BuildContext context) {
    final tone = color ?? (_zero(value) ? _faint : _ink);
    return Text.rich(
      TextSpan(
        children: [
          TextSpan(
            text: '$code ',
            style: TextStyle(fontSize: size * 0.7, fontWeight: FontWeight.w700, color: tone.withValues(alpha: 0.72), letterSpacing: 0.4),
          ),
          TextSpan(text: moneyText(value)),
        ],
      ),
      textDirection: TextDirection.ltr,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: TextStyle(fontSize: size, fontWeight: weight, color: tone, height: 1.25, fontFeatures: const [FontFeature.tabularFigures()]),
    );
  }
}

Color _signColor(String? v) => _zero(v) ? _faint : (_negative(v) ? _bad : _good);

/// The verdict in one glance: a filled pill "Profit" (green) / "Loss" (red) / "No profit, no loss" (grey) and the currency beside it.
class _ProfitWord extends StatelessWidget {
  const _ProfitWord({required this.value, required this.currency});
  final String? value;
  final String currency; // usd or syp
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final zero = _zero(value);
    final loss = _negative(value);
    final tone = zero ? _muted : (loss ? _bad : _good);
    final word = zero ? s.get('mnNoProfitLoss') : s.get(loss ? 'mnLoss' : 'mnProfit');
    return Wrap(
      spacing: 10,
      runSpacing: 6,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(color: tone, borderRadius: BorderRadius.circular(20)),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(zero ? Icons.remove_rounded : (loss ? Icons.arrow_downward_rounded : Icons.arrow_upward_rounded), size: 16, color: Colors.white),
              const SizedBox(width: 6),
              Text(word, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: Colors.white)),
            ],
          ),
        ),
        Text(s.get(currency == 'usd' ? 'mnInDollarsShort' : 'mnInPoundsShort'), style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: _muted)),
      ],
    );
  }
}

/// A white panel with a title line (icon, title, actions on the other side) and its content.
class _Panel extends StatelessWidget {
  const _Panel({required this.title, required this.child, this.icon, this.actions = const [], this.subtitle, this.padding = const EdgeInsets.fromLTRB(16, 0, 16, 16)});
  final String title;
  final String? subtitle;
  final IconData? icon;
  final List<Widget> actions;
  final Widget child;
  final EdgeInsets padding;
  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 12, 12),
            child: Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 12,
              runSpacing: 10,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (icon != null) ...[_IconBox(icon!, size: 34), const SizedBox(width: 10)],
                    Flexible(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            title,
                            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: _ink),
                          ),
                          if (subtitle != null) Text(subtitle!, style: const TextStyle(fontSize: 12.5, color: _muted)),
                        ],
                      ),
                    ),
                  ],
                ),
                if (actions.isNotEmpty) Wrap(spacing: 8, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: actions),
              ],
            ),
          ),
          Padding(padding: padding, child: child),
        ],
      ),
    );
  }
}

class _IconBox extends StatelessWidget {
  const _IconBox(this.icon, {this.tone = brandBlue, this.size = 38});
  final IconData icon;
  final Color tone;
  final double size;
  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(color: tone.withValues(alpha: 0.10), borderRadius: BorderRadius.circular(size * 0.3)),
    child: Icon(icon, size: size * 0.52, color: tone),
  );
}

/// Children in equal columns; every row is as high as its highest card. The number of columns follows the width.
class _Grid extends StatelessWidget {
  const _Grid({required this.children, this.minWidth = 220});
  final List<Widget> children;
  final double minWidth;
  @override
  Widget build(BuildContext context) {
    const gap = 12.0;
    return LayoutBuilder(
      builder: (context, box) {
        final n = math.max(1, math.min(children.length, ((box.maxWidth + gap) / (minWidth + gap)).floor()));
        return Column(
          children: [
            for (var i = 0; i < children.length; i += n)
              Padding(
                padding: const EdgeInsets.only(bottom: gap),
                child: IntrinsicHeight(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      for (var j = 0; j < n; j++) ...[if (j > 0) const SizedBox(width: gap), Expanded(child: i + j < children.length ? children[i + j] : const SizedBox.shrink())],
                    ],
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}

/// A key figure: an icon, a label, the amount in dollars and in pounds, a short line under it.
class _Kpi extends StatelessWidget {
  const _Kpi({required this.icon, required this.label, required this.usd, required this.syp, this.tone = brandBlue, this.badge, this.foot});
  final IconData icon;
  final String label;
  final String? usd;
  final String? syp;
  final Color tone;
  final Widget? badge;
  final String? foot;
  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _IconBox(icon, tone: tone, size: 34),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    label,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: _muted),
                  ),
                ),
                ?badge,
              ],
            ),
            const SizedBox(height: 14),
            if (usd != null) Money('USD', usd, size: 19, weight: FontWeight.w800),
            if (usd != null && syp != null) const SizedBox(height: 2),
            if (syp != null) Money('SYP', syp, size: 19, weight: FontWeight.w800),
            if (foot != null) ...[const Spacer(), const SizedBox(height: 10), Text(foot!, style: const TextStyle(fontSize: 12, color: _muted, height: 1.4))],
          ],
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag(this.text, {this.fg = _neutral, this.bg = _neutralBg, this.icon});
  final String text;
  final Color fg;
  final Color bg;
  final IconData? icon;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
    decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (icon != null) ...[Icon(icon, size: 14, color: fg), const SizedBox(width: 4)],
        Flexible(
          child: Text(
            text,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: fg),
          ),
        ),
      ],
    ),
  );
}

/// "Test" mark of a trial entry (it can be deleted for good with "delete test data" on the overview).
Widget _testTag(S s) => _Tag(s.get('mnTestTag'), fg: _warn, bg: _warnBg, icon: Icons.science_outlined);

Widget? _stateTag(S s, Map<String, dynamic> r) {
  final state = _stateTagOnly(s, r);
  if (r['is_test'] != true) return state;
  return Wrap(spacing: 6, runSpacing: 6, children: [_testTag(s), ?state]);
}

Widget? _stateTagOnly(S s, Map<String, dynamic> r) {
  if (r['voided'] == true) return _Tag('${s.get('mnCancelled')}: ${r['void_reason'] ?? ''}', icon: Icons.block);
  if (r['is_reversal'] == true) return _Tag(s.get('mnReversal'), fg: _warn, bg: _warnBg, icon: Icons.undo_rounded);
  if (r['reversed'] == true) return _Tag(s.get('mnReversed'), fg: _warn, bg: _warnBg, icon: Icons.undo_rounded);
  return null;
}

/// The status of an invoice in its colour.
Widget _invoiceTag(S s, String status) => switch (status) {
  'paid' => _Tag(s.get('mnStatusPaid'), fg: _good, bg: _goodBg),
  'partial' => _Tag(s.get('mnPartlyPaid'), fg: _warn, bg: _warnBg),
  'void' => _Tag(s.get('mnCancelled')),
  _ => _Tag(s.get('mnOpen'), fg: _bad, bg: _badBg),
};

Widget _invoiceTags(S s, Map<String, dynamic> v) => Wrap(spacing: 6, runSpacing: 6, children: [if (v['is_test'] == true) _testTag(s), _invoiceTag(s, v['status'] as String)]);

/// Buttons that keep their natural width (the theme makes filled buttons full width).
Widget _primary(String label, IconData icon, VoidCallback? onPressed) => FilledButton.icon(
  style: FilledButton.styleFrom(
    minimumSize: const Size(0, 44),
    padding: const EdgeInsets.symmetric(horizontal: 18),
    textStyle: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700),
  ),
  onPressed: onPressed,
  icon: Icon(icon, size: 20),
  label: Text(label),
);

Widget _secondary(String label, IconData icon, VoidCallback? onPressed, {Color? color}) => OutlinedButton.icon(
  style: OutlinedButton.styleFrom(
    minimumSize: const Size(0, 44),
    padding: const EdgeInsets.symmetric(horizontal: 14),
    foregroundColor: color ?? brandBlue,
    side: BorderSide(color: color ?? _line),
    backgroundColor: Colors.white,
  ),
  onPressed: onPressed,
  icon: Icon(icon, size: 19),
  label: Text(label),
);

/// The page frame: a list with even margins; the toolbar first.
Widget _page(List<Widget> children) => ListView(physics: const AlwaysScrollableScrollPhysics(), padding: const EdgeInsets.fromLTRB(14, 12, 14, 32), children: children);

/// A small muted note under a section.
Widget _hint(String text) => Padding(
  padding: const EdgeInsets.fromLTRB(4, 0, 4, 14),
  child: Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Padding(
        padding: EdgeInsets.only(top: 1),
        child: Icon(Icons.info_outline_rounded, size: 15, color: _faint),
      ),
      const SizedBox(width: 6),
      Expanded(
        child: Text(text, style: const TextStyle(fontSize: 12, color: _muted, height: 1.5)),
      ),
    ],
  ),
);

Widget _empty(String text, {IconData icon = Icons.inbox_outlined}) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 22),
  child: Column(
    children: [
      Icon(icon, size: 30, color: _faint),
      const SizedBox(height: 8),
      Text(
        text,
        textAlign: TextAlign.center,
        style: const TextStyle(color: _muted),
      ),
    ],
  ),
);

/// Label and value in one line of a details list.
Widget _fact(String label, Widget value) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 7),
  child: Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      SizedBox(
        width: 130,
        child: Text(label, style: const TextStyle(fontSize: 13, color: _muted)),
      ),
      Expanded(child: value),
    ],
  ),
);

Widget _factText(String label, String value) => _fact(label, Text(value.isEmpty ? '—' : value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)));

// ---- month choice -------------------------------------------------------------------------------------------------------------
Future<String?> pickMonth(BuildContext context, String current) {
  final s = S.of(context);
  var year = int.parse(current.substring(0, 4));
  return showDialog<String>(
    context: context,
    builder: (context) => StatefulBuilder(
      builder: (context, setState) => AlertDialog(
        title: Row(
          children: [
            IconButton(onPressed: () => setState(() => year--), icon: const Icon(Icons.chevron_left)),
            Expanded(
              child: Text(
                '$year',
                textAlign: TextAlign.center,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
            ),
            IconButton(onPressed: () => setState(() => year++), icon: const Icon(Icons.chevron_right)),
          ],
        ),
        content: SizedBox(
          width: 340,
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (var m = 1; m <= 12; m++)
                SizedBox(
                  width: 104,
                  child: ChoiceChip(
                    showCheckmark: false,
                    label: SizedBox(
                      width: double.infinity,
                      child: Text((_months[s.code] ?? _months['en']!)[m - 1], textAlign: TextAlign.center, style: const TextStyle(fontSize: 13)),
                    ),
                    selected: current == '$year-${m.toString().padLeft(2, '0')}',
                    onSelected: (_) => Navigator.pop(context, '$year-${m.toString().padLeft(2, '0')}'),
                  ),
                ),
            ],
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text(s.get('cancel')))],
      ),
    ),
  );
}

/// ‹ month › with the month name in the middle (tap it to choose any month). The arrows turn with the reading direction.
class MonthSwitcher extends StatelessWidget {
  const MonthSwitcher({super.key, required this.month, required this.onChanged});
  final String month;
  final ValueChanged<String> onChanged;
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return Container(
      height: 46,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _line),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconButton(visualDensity: VisualDensity.compact, tooltip: s.get('mnPrevMonth'), onPressed: () => onChanged(shiftMonth(month, -1)), icon: const Icon(Icons.chevron_left)),
          Flexible(
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () async {
                final v = await pickMonth(context, month);
                if (v != null) onChanged(v);
              },
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.calendar_month_outlined, size: 18, color: brandBlue),
                    const SizedBox(width: 8),
                    Flexible(
                      child: Text(
                        monthTitle(s.code, month),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: _ink),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          IconButton(visualDensity: VisualDensity.compact, tooltip: s.get('mnNextMonth'), onPressed: () => onChanged(shiftMonth(month, 1)), icon: const Icon(Icons.chevron_right)),
        ],
      ),
    );
  }
}

// ---- the exchange rate --------------------------------------------------------------------------------------------------------
/// Today's rate as a small chip; a tap shows the list of rates and (for the management) the correction.
class RateChip extends StatelessWidget {
  const RateChip(this.meta, {super.key, required this.onChanged});
  final MoneyMeta meta;
  final Future<void> Function() onChanged;
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final r = meta.rate;
    final stale = r == null || r['stale'] == true;
    return Material(
      color: stale ? _warnBg : Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: stale ? const Color(0xFFF1D9AE) : _line),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () async {
          final changed = await showModalBottomSheet<bool>(
            context: context,
            isScrollControlled: true,
            showDragHandle: true,
            builder: (_) => _RateSheet(meta: meta),
          );
          if (changed == true) await onChanged();
        },
        child: Container(
          constraints: const BoxConstraints(minHeight: 46),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.currency_exchange_rounded, size: 19, color: stale ? _warn : brandBlue),
              const SizedBox(width: 8),
              Flexible(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      r == null ? s.get('mnNoRate') : '${moneyText(r['syp_per_usd'] as String?)} ${s.get('mnPerDollar')}',
                      style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800, color: _ink),
                    ),
                    if (r != null)
                      Text(
                        '${s.get(r['source'] == 'auto' ? 'mnRateAuto' : 'mnRateManual')} · ${r['valid_from']}${r['stale'] == true ? ' · ${s.get('mnRateOld')}' : ''}',
                        maxLines: 2,
                        style: const TextStyle(fontSize: 11, color: _muted),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RateSheet extends StatefulWidget {
  const _RateSheet({required this.meta});
  final MoneyMeta meta;
  @override
  State<_RateSheet> createState() => _RateSheetState();
}

class _RateSheetState extends State<_RateSheet> {
  final _value = TextEditingController();
  late DateTime _from = DateTime.parse(widget.meta.today);
  bool _busy = false;
  late Future<dynamic> _rates;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _rates = SessionScope.of(context).api.get('/api/admin/money/rates');
  }

  Future<void> _save() async {
    final s = S.of(context);
    if (_value.text.trim().isEmpty) return;
    setState(() => _busy = true);
    try {
      await SessionScope.of(context).api.post('/api/admin/money/rates', {'valid_from': dayText(_from), 'syp_per_usd': _value.text.trim()});
      if (!mounted) return;
      toast(context, s.get('mnRateSaved'));
      Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(s.get('mnRateTitle'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
              const SizedBox(height: 4),
              Text(s.get('mnRateExplain'), style: const TextStyle(fontSize: 12.5, color: _muted, height: 1.5)),
              if (widget.meta.canManage) ...[
                const SizedBox(height: 16),
                Text(s.get('mnRateCorrect'), style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                _DayField(label: s.get('mnValidFrom'), day: _from, last: DateTime.parse(widget.meta.today), onChanged: (d) => setState(() => _from = d)),
                const SizedBox(height: 10),
                TextField(
                  controller: _value,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  textDirection: TextDirection.ltr,
                  decoration: InputDecoration(labelText: s.get('mnPoundsPerDollar')),
                ),
                const SizedBox(height: 10),
                _primary(s.get('mnSaveRate'), Icons.check_rounded, _busy ? null : _save),
              ],
              const SizedBox(height: 18),
              Text(s.get('mnRateList'), style: const TextStyle(fontWeight: FontWeight.w700)),
              FutureBuilder<dynamic>(
                future: _rates,
                builder: (context, snap) {
                  if (snap.hasError) return Padding(padding: const EdgeInsets.all(8), child: Text(problemText(context, snap.error!)));
                  if (!snap.hasData) return const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator());
                  final rows = _list((snap.data as Map)['rates']);
                  if (rows.isEmpty) return _empty(s.get('mnNoRate'));
                  return Column(
                    children: [
                      for (final r in rows.take(12))
                        ListTile(
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          leading: Icon(r['source'] == 'auto' ? Icons.cloud_download_outlined : Icons.edit_outlined, size: 19, color: _muted),
                          title: Text('${moneyText(r['syp_per_usd'] as String?)} ${s.get('mnPerDollar')}', style: const TextStyle(fontWeight: FontWeight.w700)),
                          subtitle: Text('${s.get('mnValidFrom')} ${r['valid_from']} · ${r['source'] == 'auto' ? s.get('mnRateAuto') : r['by']}'),
                        ),
                    ],
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A date as a field: tap it to choose another day.
class _DayField extends StatelessWidget {
  const _DayField({required this.label, required this.day, required this.onChanged, this.last});
  final String label;
  final DateTime day;
  final DateTime? last;
  final ValueChanged<DateTime> onChanged;
  @override
  Widget build(BuildContext context) => InkWell(
    borderRadius: BorderRadius.circular(14),
    onTap: () async {
      final picked = await showDatePicker(context: context, initialDate: day, firstDate: DateTime(2020), lastDate: last ?? DateTime(2100));
      if (picked != null) onChanged(picked);
    },
    child: InputDecorator(
      decoration: InputDecoration(labelText: label, suffixIcon: const Icon(Icons.event_outlined)),
      child: Text(dayText(day), textDirection: TextDirection.ltr, textAlign: TextAlign.start),
    ),
  );
}

/// The row on top of every page: month, rate, state; the actions on the other side.
Widget _toolbar({required List<Widget> start, List<Widget> end = const []}) => Padding(
  padding: const EdgeInsets.only(bottom: 14),
  child: Wrap(
    alignment: WrapAlignment.spaceBetween,
    crossAxisAlignment: WrapCrossAlignment.center,
    spacing: 12,
    runSpacing: 10,
    children: [
      Wrap(spacing: 10, runSpacing: 10, crossAxisAlignment: WrapCrossAlignment.center, children: start),
      if (end.isNotEmpty) Wrap(spacing: 8, runSpacing: 8, children: end),
    ],
  ),
);

Future<void> _pdf(BuildContext context, String path, String name, [Map<String, String>? query]) => openPrivateFile(context, SessionScope.of(context).api, path, name, query: query);
Future<void> _print(BuildContext context, String path, String name, [Map<String, String>? query]) => printPrivatePdf(context, SessionScope.of(context).api, path, name, query: query);

// ================================================================================================================================
// the month overview
// ================================================================================================================================
class MoneySummaryPage extends StatefulWidget {
  const MoneySummaryPage({super.key});
  @override
  State<MoneySummaryPage> createState() => _MoneySummaryPageState();
}

class _MoneySummaryPageState extends State<MoneySummaryPage> {
  String month = monthKey(DateTime.now());

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    return _Data<(MoneyMeta, Map<String, dynamic>)>(
      signature: month,
      load: () async {
        final meta = await loadMeta(api);
        final d = _map(await api.get('/api/admin/money/summary', query: {'month': month}));
        return (meta, d);
      },
      builder: (context, data, reload) => _summary(context, data.$1, data.$2, reload),
    );
  }

  Widget _summary(BuildContext context, MoneyMeta meta, Map<String, dynamic> d, Future<void> Function() reload) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    final closed = d['closed'] == true;
    final invoices = _map(d['invoices']);
    final unpaid = (invoices['open'] as int) + (invoices['partial'] as int);
    final change = _map(d['change']);

    Future<void> closeMonth() async {
      final ok = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: Text(s.get('mnCloseMonth')),
          content: Text(s.get('mnCloseMonthAsk')),
          actions: [
            TextButton(onPressed: () => Navigator.pop(c, false), child: Text(s.get('cancel'))),
            FilledButton(
              style: FilledButton.styleFrom(minimumSize: const Size(110, 44)),
              onPressed: () => Navigator.pop(c, true),
              child: Text(s.get('mnCloseMonth')),
            ),
          ],
        ),
      );
      if (ok != true || !context.mounted) return;
      final p = month.split('-');
      try {
        await api.post('/api/admin/money/closings', {'year': int.parse(p[0]), 'month': int.parse(p[1])});
        if (context.mounted) toast(context, s.get('mnMonthClosed'));
        await reload();
      } on ApiException catch (e) {
        if (context.mounted) toast(context, problemText(context, e));
      }
    }

    Future<void> reopenMonth() async {
      final reason = await askText(context, s.get('mnReopenReason'), maxLength: 300, maxLines: 2, confirm: 'mnReopen');
      if (reason == null || !context.mounted) return;
      final p = month.split('-');
      try {
        await api.post('/api/admin/money/closings/${int.parse(p[0])}/${int.parse(p[1])}/reopen', {'reason': reason});
        await reload();
      } on ApiException catch (e) {
        if (context.mounted) toast(context, problemText(context, e));
      }
    }

    Widget changeLine(String key, String code) {
      final raw = (change[key] as Map?)?[code] as Map?;
      if (raw == null) return const SizedBox.shrink();
      final c = raw.cast<String, dynamic>();
      final diff = c['difference'] as String?;
      final pct = c['percent'] as String?;
      if (_zero(diff)) return Text(s.get('mnSameAsBefore'), style: const TextStyle(fontSize: 12, color: _muted));
      final up = !_negative(diff);
      return Wrap(
        spacing: 4,
        runSpacing: 2,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Icon(up ? Icons.trending_up_rounded : Icons.trending_down_rounded, size: 16, color: up ? _good : _bad),
          Text(
            '${up ? '+' : ''}${moneyText(diff)}${pct == null ? '' : ' (${up ? '+' : ''}$pct%)'}',
            textDirection: TextDirection.ltr,
            style: TextStyle(fontSize: 12, color: up ? _good : _bad, fontWeight: FontWeight.w700, fontFeatures: const [FontFeature.tabularFigures()]),
          ),
          Text(s.get('mnVsPrevious'), style: const TextStyle(fontSize: 12, color: _muted)),
        ],
      );
    }

    // the comparison with the month before in words (better / worse / the same), not as a bare +/- number
    Widget compareWords(String code) {
      final raw = (change['surplus'] as Map?)?[code] as Map?;
      if (raw == null) return const SizedBox.shrink();
      final diff = raw['difference'] as String?;
      if (_zero(diff)) return Text(s.get('mnSameAsBefore'), style: const TextStyle(fontSize: 12.5, color: _muted));
      final better = !_negative(diff);
      final tone = better ? _good : _bad;
      return Text(
        '${s.get(better ? 'mnBetterThanBefore' : 'mnWorseThanBefore')} ${moneyText(diff?.replaceFirst('-', ''))}',
        style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: tone),
      );
    }

    final surplus = _map(d['surplus']);
    final hero = Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const _IconBox(Icons.account_balance_outlined, size: 36),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    s.get('mnProfitLoss'),
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: _ink),
                  ),
                ),
                _Tag('${d['income_count']} ${s.get('mnIncomeEntries')} · ${d['expense_count']} ${s.get('mnExpenseEntries')}'),
              ],
            ),
            const SizedBox(height: 16),
            _Grid(
              minWidth: 240,
              children: [
                for (final code in ['usd', 'syp'])
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: _zero(surplus[code] as String?) ? const Color(0xFFF7F9FC) : (_negative(surplus[code] as String?) ? const Color(0xFFFDF4F2) : const Color(0xFFF1F9F4)),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _ProfitWord(value: surplus[code] as String?, currency: code),
                        const SizedBox(height: 6),
                        Money(code.toUpperCase(), (surplus[code] as String?)?.replaceFirst('-', ''), size: 26, weight: FontWeight.w900, color: _signColor(surplus[code] as String?)),
                        // the same result worth the other currency (each entry at its own rate): dollars and pounds in one box
                        if ((d['surplus_value'] as Map?)?[code] != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text('${s.get('mnWorth')} ', style: const TextStyle(fontSize: 13, color: _muted)),
                              Money(code == 'usd' ? 'SYP' : 'USD', ((d['surplus_value'] as Map)[code] as String?)?.replaceFirst('-', ''), size: 17, weight: FontWeight.w800, color: _signColor(surplus[code] as String?)),
                            ],
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '${s.get('mnIncome')} ${moneyText(_map(d['income'])[code] as String?)}  −  ${s.get('mnExpenses')} ${moneyText(_map(d['expense'])[code] as String?)}',
                          style: const TextStyle(fontSize: 12.5, color: _muted),
                        ),
                        const SizedBox(height: 4),
                        compareWords(code),
                      ],
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );

    final open = _map(invoices['open_amount']);
    final kpis = _Grid(
      minWidth: 200,
      children: [
        _Kpi(icon: Icons.south_west_rounded, tone: _good, label: s.get('mnIncome'), usd: _map(d['income'])['usd'] as String?, syp: _map(d['income'])['syp'] as String?),
        _Kpi(icon: Icons.north_east_rounded, tone: _bad, label: s.get('mnExpenses'), usd: _map(d['expense'])['usd'] as String?, syp: _map(d['expense'])['syp'] as String?),
        _Kpi(icon: Icons.badge_outlined, tone: brandBlue, label: s.get('mnSalaries'), usd: _map(d['salaries'])['usd'] as String?, syp: _map(d['salaries'])['syp'] as String?),
        _Kpi(
          icon: Icons.receipt_long_outlined,
          tone: _warn,
          label: s.get('mnUnpaidInvoices'),
          usd: open['usd'] as String?,
          syp: open['syp'] as String?,
          badge: _Tag('$unpaid', fg: unpaid > 0 ? _warn : _neutral, bg: unpaid > 0 ? _warnBg : _neutralBg),
        ),
      ],
    );

    final prevMonth = d['previous_month'] as String;
    Widget categories(String title, IconData icon, List<Map<String, dynamic>> rows, String Function(Map<String, dynamic>) name) => _Panel(
      title: title,
      icon: icon,
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: rows.isEmpty
          ? _empty(s.get('mnNoEntries'))
          : Column(
              children: [
                for (final (i, c) in rows.indexed) ...[
                  if (i > 0) const Divider(height: 1),
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(name(c), style: const TextStyle(fontWeight: FontWeight.w700)),
                        ),
                        _Tag('${c['count']}'),
                        const SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Money('USD', c['usd'] as String?, size: 14),
                            Money('SYP', c['syp'] as String?, size: 13, weight: FontWeight.w600),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
    );

    final converted = _map(_map(d['converted'])['surplus']);
    return _page([
      _toolbar(
        start: [
          MonthSwitcher(month: month, onChanged: (v) => setState(() => month = v)),
          closed
              ? _Tag('${s.get('mnMonthClosed')}${d['closing'] == null ? '' : ' · ${_map(d['closing'])['by']}'}', fg: _good, bg: _goodBg, icon: Icons.lock_outline_rounded)
              : _Tag(s.get('mnMonthOpen'), icon: Icons.lock_open_rounded),
          RateChip(meta, onChanged: reload),
        ],
        end: [
          if (meta.canManage && closed) _secondary(s.get('mnReopen'), Icons.lock_open_rounded, reopenMonth),
          if (meta.canManage && !closed && month.compareTo(meta.thisMonth) < 0) _secondary(s.get('mnCloseMonth'), Icons.lock_outline_rounded, closeMonth),
          if (meta.canExport) _secondary(s.get('mnPrint'), Icons.print_outlined, () => _print(context, '/api/admin/money/export/summary.pdf', 'report-$month.pdf', {'month': month})),
          if (meta.canExport) _primary(s.get('mnReportPdf'), Icons.picture_as_pdf_outlined, () => _pdf(context, '/api/admin/money/export/summary.pdf', 'report-$month.pdf', {'month': month})),
        ],
      ),
      hero,
      kpis,
      _CashPanel(meta: meta, d: d, onChanged: reload),
      _TestPanel(meta: meta, onChanged: reload),
      _Panel(
        title: s.get('mnCompare'),
        subtitle: '${s.get('mnVsPrevious')}: ${monthTitle(s.code, prevMonth)}',
        icon: Icons.compare_arrows_rounded,
        child: Column(
          children: [
            for (final (key, label) in [('income', 'mnIncome'), ('expense', 'mnExpenses'), ('surplus', 'mnProfitLoss')])
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 120,
                      child: Text(s.get(label), style: const TextStyle(fontWeight: FontWeight.w700)),
                    ),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [changeLine(key, 'usd'), changeLine(key, 'syp')]),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
      LayoutBuilder(
        builder: (context, box) {
          final a = categories(s.get('mnIncomeByCategory'), Icons.south_west_rounded, _list(d['income_by_category']), (c) => c['name'] as String);
          final b = categories(s.get('mnExpensesByCategory'), Icons.north_east_rounded, _list(d['expense_by_category']), (c) => c[s.code == 'ar' ? 'ar' : 'en'] as String);
          if (box.maxWidth < 760) return Column(children: [a, b]);
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: a),
              const SizedBox(width: 12),
              Expanded(child: b),
            ],
          );
        },
      ),
      _hint('${s.get('mnColumnsNote')} ${s.get('mnConverted')}: USD ${moneyText(converted['usd'] as String?)} / SYP ${moneyText(converted['syp'] as String?)}'),
    ]);
  }
}

/// The money the kindergarten has: start of the month, + income, − expenses, = profit, end of the month. The management
/// enters the opening balance here.
/// Trial data: shows how many entries are marked as test and lets the management delete them for good. Hidden when there are none.
class _TestPanel extends StatefulWidget {
  const _TestPanel({required this.meta, required this.onChanged});
  final MoneyMeta meta;
  final Future<void> Function() onChanged;
  @override
  State<_TestPanel> createState() => _TestPanelState();
}

class _TestPanelState extends State<_TestPanel> {
  Map<String, dynamic>? _data;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    try {
      final d = _map(await SessionScope.of(context).api.get('/api/admin/money/test-data'));
      if (mounted) setState(() => _data = d);
    } catch (_) {}
  }

  Future<void> _purge() async {
    final s = S.of(context);
    final total = _data?['total'] ?? 0;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        content: Text('${s.get('mnTestConfirm')} ($total)'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.get('cancel'))),
          FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(110, 44)), onPressed: () => Navigator.pop(context, true), child: Text(s.get('delete'))),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    setState(() => _busy = true);
    try {
      await SessionScope.of(context).api.post('/api/admin/money/test-data/purge', {});
      if (!mounted) return;
      toast(context, s.get('mnTestDeleted'));
      await widget.onChanged();
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final d = _data;
    if (d == null || (d['total'] ?? 0) == 0) return const SizedBox.shrink();
    return _Panel(
      title: s.get('mnTestData'),
      icon: Icons.science_outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${s.get('mnIncome')}: ${d['income']} · ${s.get('mnExpenses')}: ${d['expenses']} · ${s.get('mnTestInvoices')}: ${d['invoices']}'),
          if (widget.meta.canManage)
            Padding(padding: const EdgeInsets.only(top: 12), child: _secondary(s.get('mnTestDelete'), Icons.delete_forever_outlined, _busy ? null : _purge, color: _bad)),
        ],
      ),
    );
  }
}

class _CashPanel extends StatelessWidget {
  const _CashPanel({required this.meta, required this.d, required this.onChanged});
  final MoneyMeta meta;
  final Map<String, dynamic> d;
  final Future<void> Function() onChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final b = _map(d['balance']);
    final start = _map(b['start']);
    final known = start['usd'] != null || start['syp'] != null;
    final opening = _map(b['opening']);
    final asOf = ((opening['USD'] ?? opening['SYP']) as Map?)?['as_of'] as String?;

    Widget line(String label, Map<String, dynamic> pair, {bool total = false, bool signed = false}) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: total ? BoxDecoration(color: brandSoft, borderRadius: BorderRadius.circular(12)) : null,
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: TextStyle(fontWeight: total ? FontWeight.w800 : FontWeight.w600, color: total ? brandBlue : _ink),
            ),
          ),
          SizedBox(
            width: 130,
            child: Align(
              alignment: AlignmentDirectional.centerEnd,
              child: Money('USD', pair['usd'] as String?, size: total ? 15.5 : 14.5, color: signed ? _signColor(pair['usd'] as String?) : null),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 150,
            child: Align(
              alignment: AlignmentDirectional.centerEnd,
              child: Money('SYP', pair['syp'] as String?, size: total ? 15.5 : 14.5, color: signed ? _signColor(pair['syp'] as String?) : null),
            ),
          ),
        ],
      ),
    );

    final narrow = MediaQuery.sizeOf(context).width < 560;
    Widget body;
    if (!known) {
      body = _empty(s.get(meta.canManage ? 'mnNoCashManage' : 'mnNoCash'), icon: Icons.savings_outlined);
    } else if (narrow) {
      Widget pair(String label, Map<String, dynamic> p, {bool strong = false, bool signed = false}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 7),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                label,
                style: TextStyle(fontWeight: strong ? FontWeight.w800 : FontWeight.w600, color: strong ? brandBlue : _ink),
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Money('USD', p['usd'] as String?, size: 14, color: signed ? _signColor(p['usd'] as String?) : null),
                Money('SYP', p['syp'] as String?, size: 14, color: signed ? _signColor(p['syp'] as String?) : null),
              ],
            ),
          ],
        ),
      );
      body = Column(
        children: [
          pair(s.get('mnCashStart'), start),
          const Divider(height: 1),
          pair('+ ${s.get('mnIncome')}', _map(d['income'])),
          pair('− ${s.get('mnExpenses')}', _map(d['expense'])),
          pair('= ${s.get('mnProfitLoss')}', _map(b['profit']), signed: true),
          const Divider(height: 1),
          pair(s.get('mnCashEnd'), _map(b['end']), strong: true),
        ],
      );
    } else {
      body = Column(
        children: [
          line(s.get('mnCashStart'), start),
          line('+ ${s.get('mnIncome')}', _map(d['income'])),
          line('− ${s.get('mnExpenses')}', _map(d['expense'])),
          line('= ${s.get('mnProfitLoss')}', _map(b['profit']), signed: true),
          const SizedBox(height: 4),
          line(s.get('mnCashEnd'), _map(b['end']), total: true),
        ],
      );
    }
    return _Panel(
      title: s.get('mnCash'),
      subtitle: known && asOf != null ? '${s.get('mnOpeningFrom')} $asOf' : null,
      icon: Icons.savings_outlined,
      actions: [
        if (meta.canManage)
          _secondary(s.get(known ? 'mnCorrectCash' : 'mnEnterCash'), Icons.edit_outlined, () async {
            final saved = await showModalBottomSheet<bool>(
              context: context,
              isScrollControlled: true,
              showDragHandle: true,
              builder: (_) => _OpeningSheet(meta: meta),
            );
            if (saved == true) await onChanged();
          }),
      ],
      child: body,
    );
  }
}

class _OpeningSheet extends StatefulWidget {
  const _OpeningSheet({required this.meta});
  final MoneyMeta meta;
  @override
  State<_OpeningSheet> createState() => _OpeningSheetState();
}

class _OpeningSheetState extends State<_OpeningSheet> {
  final _usd = TextEditingController();
  final _syp = TextEditingController();
  final _note = TextEditingController();
  late DateTime _day = DateTime.parse(widget.meta.today);
  bool _busy = false;

  Future<void> _save() async {
    final s = S.of(context);
    setState(() => _busy = true);
    try {
      await SessionScope.of(context).api.post('/api/admin/money/opening', {
        'as_of': dayText(_day),
        'usd': _usd.text.trim().isEmpty ? '0' : _usd.text.trim(),
        'syp': _syp.text.trim().isEmpty ? '0' : _syp.text.trim(),
        'note': _note.text.trim(),
      });
      if (!mounted) return;
      toast(context, s.get('mnCashSaved'));
      Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(s.get('mnEnterCash'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
              const SizedBox(height: 4),
              Text(s.get('mnCashExplain'), style: const TextStyle(fontSize: 12.5, color: _muted, height: 1.5)),
              const SizedBox(height: 16),
              _DayField(label: s.get('mnAtStartOf'), day: _day, last: DateTime.parse(widget.meta.today), onChanged: (d) => setState(() => _day = d)),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _usd,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      textDirection: TextDirection.ltr,
                      decoration: const InputDecoration(labelText: 'USD'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: TextField(
                      controller: _syp,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      textDirection: TextDirection.ltr,
                      decoration: const InputDecoration(labelText: 'SYP'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _note,
                maxLength: 300,
                decoration: InputDecoration(labelText: s.get('mnNote')),
              ),
              _primary(s.get('mnSaveCash'), Icons.check_rounded, _busy ? null : _save),
            ],
          ),
        ),
      ),
    );
  }
}

// ================================================================================================================================
// income and expenses
// ================================================================================================================================
/// One month (or a span of days) of income or expenses with filters, totals and the list; under it the invoices (income) or
/// the salaries (expenses). `kind` is "income" or "expenses" (the path on the server).
class MoneyEntriesPage extends StatefulWidget {
  const MoneyEntriesPage({super.key, required this.kind});
  final String kind;
  @override
  State<MoneyEntriesPage> createState() => _MoneyEntriesPageState();
}

class _MoneyEntriesPageState extends State<MoneyEntriesPage> {
  String month = monthKey(DateTime.now());
  String? category;
  DateTime? from;
  DateTime? to;
  String invoiceStatus = 'unpaid';
  final _search = TextEditingController();
  String q = '';
  bool get income => widget.kind == 'income';

  Map<String, String> get _query => {
    if (from != null || to != null) ...{if (from != null) 'date_from': dayText(from!), if (to != null) 'date_to': dayText(to!)} else 'month': month,
    (income ? 'category_id' : 'category'): ?category,
    if (q.isNotEmpty) 'q': q,
  };

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.of(context).api;
    final query = _query;
    return _Data<(MoneyMeta, Map<String, dynamic>, List<Map<String, dynamic>>, Map<String, dynamic>?)>(
      key: ValueKey(widget.kind),
      signature: '${widget.kind}|$query|$invoiceStatus',
      load: () async {
        final meta = await loadMeta(api);
        final list = _map(await api.get('/api/admin/money/${widget.kind}', query: query));
        final invoices = income ? _list(_map(await api.get('/api/admin/money/invoices', query: {'status': invoiceStatus}))['rows']) : <Map<String, dynamic>>[];
        final salaries = income ? null : _map(await api.get('/api/admin/money/salaries', query: {'month': month}));
        return (meta, list, invoices, salaries);
      },
      builder: (context, data, reload) => _body(context, data.$1, data.$2, data.$3, data.$4, reload),
    );
  }

  Widget _body(BuildContext context, MoneyMeta meta, Map<String, dynamic> d, List<Map<String, dynamic>> invoices, Map<String, dynamic>? salaries, Future<void> Function() reload) {
    final s = S.of(context);
    final totals = _map(d['totals']);
    final value = _map(totals['value']);
    final rows = _list(d['rows']);
    final span = from != null || to != null;

    Future<void> openForm({Map<String, dynamic>? row, Map<String, dynamic>? salaryFor}) async {
      final saved = await Navigator.push<bool>(
        context,
        MaterialPageRoute(
          builder: (_) => MoneyEntryForm(kind: widget.kind, meta: meta, month: month, row: row, salaryFor: salaryFor),
        ),
      );
      if (saved == true) await reload();
    }

    final cats = income
        ? [for (final c in meta.incomeCategories) (c['id'] as String, c['name'] as String)]
        : [for (final c in meta.expenseCategories) (c['key'] as String, (s.code == 'ar' ? c['ar'] : c['en']) as String)];

    final filters = Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Wrap(
          spacing: 10,
          runSpacing: 10,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            SizedBox(
              width: 260,
              child: TextField(
                controller: _search,
                textInputAction: TextInputAction.search,
                onSubmitted: (v) => setState(() => q = v.trim()),
                decoration: InputDecoration(
                  isDense: true,
                  hintText: s.get('mnSearch'),
                  prefixIcon: const Icon(Icons.search_rounded, size: 20),
                  suffixIcon: q.isEmpty
                      ? null
                      : IconButton(
                          icon: const Icon(Icons.close_rounded, size: 18),
                          onPressed: () => setState(() {
                            _search.clear();
                            q = '';
                          }),
                        ),
                ),
              ),
            ),
            SizedBox(
              width: 220,
              child: DropdownButtonFormField<String?>(
                initialValue: cats.any((c) => c.$1 == category) ? category : null,
                isExpanded: true,
                decoration: InputDecoration(isDense: true, labelText: s.get('mnCategory')),
                items: [
                  DropdownMenuItem<String?>(value: null, child: Text(s.get('mnAllCategories'))),
                  for (final c in cats)
                    DropdownMenuItem<String?>(
                      value: c.$1,
                      child: Text(c.$2, overflow: TextOverflow.ellipsis),
                    ),
                ],
                onChanged: (v) => setState(() => category = v),
              ),
            ),
            FilterChip(
              avatar: const Icon(Icons.date_range_outlined, size: 18),
              label: Text(span ? '${from == null ? '…' : dayText(from!)} → ${to == null ? '…' : dayText(to!)}' : s.get('mnCustomDates')),
              selected: span,
              onSelected: (_) async {
                if (span) {
                  setState(() => from = to = null);
                  return;
                }
                final r = await showDateRangePicker(context: context, firstDate: DateTime(2020), lastDate: DateTime.parse(meta.today));
                if (r != null) {
                  setState(() {
                    from = r.start;
                    to = r.end;
                  });
                }
              },
            ),
          ],
        ),
      ),
    );

    final list = _Panel(
      title: s.get(income ? 'mnIncome' : 'mnExpenses'),
      subtitle: span ? s.get('mnCustomDates') : monthTitle(s.code, month),
      icon: income ? Icons.south_west_rounded : Icons.north_east_rounded,
      padding: const EdgeInsets.fromLTRB(0, 0, 0, 6),
      child: rows.isEmpty
          ? _empty(s.get(q.isNotEmpty || category != null ? 'mnNothingFound' : 'mnNoEntries'))
          : Column(
              children: [
                for (final (i, r) in rows.indexed) ...[
                  if (i > 0) const Divider(height: 1, indent: 16, endIndent: 16),
                  _EntryRow(
                    r: r,
                    kind: widget.kind,
                    onTap: () => _openEntry(context, r, meta, reload, (row) => openForm(row: row)),
                  ),
                ],
              ],
            ),
    );

    return _page([
      _toolbar(
        start: [
          MonthSwitcher(
            month: month,
            onChanged: (v) => setState(() {
              month = v;
              from = to = null;
            }),
          ),
          RateChip(meta, onChanged: reload),
        ],
        end: [
          if (meta.canExport) _secondary(s.get('mnPrint'), Icons.print_outlined, () => _print(context, '/api/admin/money/export/${widget.kind}.pdf', '${widget.kind}-$month.pdf', {'month': month})),
          if (meta.canExport) _secondary('PDF', Icons.picture_as_pdf_outlined, () => _pdf(context, '/api/admin/money/export/${widget.kind}.pdf', '${widget.kind}-$month.pdf', {'month': month})),
          _primary(s.get(income ? 'mnNewIncome' : 'mnNewExpense'), Icons.add_rounded, meta.rate == null ? null : () => openForm()),
        ],
      ),
      _Grid(
        minWidth: 200,
        children: [
          _Kpi(
            icon: Icons.attach_money_rounded,
            tone: income ? _good : _bad,
            label: s.get('mnTotalDollars'),
            usd: value['USD'] as String?,
            syp: null,
            foot: '${s.get('mnReallyPaidUsd')}: ${moneyText(totals['USD'] as String?)}',
          ),
          _Kpi(
            icon: Icons.payments_outlined,
            tone: income ? _good : _bad,
            label: s.get('mnTotalPounds'),
            usd: null,
            syp: value['SYP'] as String?,
            foot: '${s.get('mnReallyPaidSyp')}: ${moneyText(totals['SYP'] as String?)}',
          ),
          _CountCard(count: d['count'] as int, label: s.get(income ? 'mnIncomeCount' : 'mnExpenseCount')),
        ],
      ),
      filters,
      list,
      if (income) _InvoicesPanel(meta: meta, rows: invoices, status: invoiceStatus, onStatus: (v) => setState(() => invoiceStatus = v), onChanged: reload),
      if (income && meta.canManage) _CategoriesPanel(meta: meta, onChanged: reload),
      if (salaries != null)
        _SalariesPanel(
          meta: meta,
          d: salaries,
          onPay: (p) => openForm(salaryFor: p),
        ),
      if (!income) _hint(s.get('mnOnlyPaid')),
    ]);
  }
}

/// The number of entries as a key figure.
class _CountCard extends StatelessWidget {
  const _CountCard({required this.count, required this.label});
  final int count;
  final String label;
  @override
  Widget build(BuildContext context) => Card(
    margin: EdgeInsets.zero,
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const _IconBox(Icons.format_list_numbered_rounded, size: 34),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: _muted),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            '$count',
            style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: _ink),
          ),
        ],
      ),
    ),
  );
}

/// One income or expense in the list: the day, what and who, both amounts on the other side.
class _EntryRow extends StatelessWidget {
  const _EntryRow({required this.r, required this.kind, required this.onTap});
  final Map<String, dynamic> r;
  final String kind;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final income = kind == 'income';
    final voided = r['voided'] == true;
    final who = [
      if (income) ...[r['payer_name'], r['child']] else ...[r['recipient'], if (r['employee'] != r['recipient']) r['employee']],
    ].whereType<String>().where((x) => x.isNotEmpty).join(' · ');
    final category = income ? r['category'] as String : (s.code == 'ar' ? r['category_ar'] : r['category_en']) as String;
    final day = (r['booked_on'] as String).split('-');
    final state = _stateTag(s, r);
    final tone = voided ? _faint : null;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 46,
              padding: const EdgeInsets.symmetric(vertical: 6),
              decoration: BoxDecoration(color: voided ? _neutralBg : (income ? _goodBg : _badBg), borderRadius: BorderRadius.circular(12)),
              child: Column(
                children: [
                  Text(
                    day[2],
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: voided ? _faint : (income ? _good : _bad), height: 1.1),
                  ),
                  Text(
                    '${day[1]}/${day[0].substring(2)}',
                    textDirection: TextDirection.ltr,
                    style: const TextStyle(fontSize: 10.5, color: _muted),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    r['description'] as String,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5, color: tone ?? _ink, decoration: voided ? TextDecoration.lineThrough : null),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    [category, if (who.isNotEmpty) who].join(' · '),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 12.5, color: _muted),
                  ),
                  if (state != null) Padding(padding: const EdgeInsets.only(top: 6), child: state),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Money('USD', r['usd'] as String?, size: 15, weight: FontWeight.w800, color: tone ?? (_negative(r['usd'] as String?) ? _bad : null)),
                Money('SYP', r['syp'] as String?, size: 13, weight: FontWeight.w600, color: tone ?? _muted),
                const SizedBox(height: 2),
                Text('${s.get('mnPaidIn')} ${r['currency']}', style: const TextStyle(fontSize: 11, color: _faint)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

Future<void> _openEntry(BuildContext context, Map<String, dynamic> r, MoneyMeta meta, Future<void> Function() reload, Future<void> Function(Map<String, dynamic>) edit) async {
  final kind = r.containsKey('category_ar') ? 'expenses' : 'income';
  final result = await showModalBottomSheet<String>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    constraints: const BoxConstraints(maxWidth: 640),
    builder: (_) => _EntrySheet(r: r, kind: kind, meta: meta),
  );
  if (result == 'edit') {
    await edit(r);
  } else if (result == 'changed') {
    await reload();
  }
}

/// The details of one entry: amounts, facts, history; editing and cancelling for those who may correct.
class _EntrySheet extends StatelessWidget {
  const _EntrySheet({required this.r, required this.kind, required this.meta});
  final Map<String, dynamic> r;
  final String kind;
  final MoneyMeta meta;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    final income = kind == 'income';
    final live = r['voided'] != true && r['is_reversal'] != true && r['reversed'] != true;
    final mayCorrect = meta.canCorrect && live;
    final closed = r['month_closed'] == true;
    final state = _stateTag(s, r);
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 16 + MediaQuery.viewInsetsOf(context).bottom),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(r['description'] as String, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
              if (state != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Align(alignment: AlignmentDirectional.centerStart, child: state),
                ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(child: _amountBox('USD', r['usd'] as String?)),
                  const SizedBox(width: 10),
                  Expanded(child: _amountBox('SYP', r['syp'] as String?)),
                ],
              ),
              const SizedBox(height: 10),
              _factText(s.get(income ? 'mnDate' : 'mnDatePaid'), r['booked_on'] as String),
              _factText(s.get('mnCategory'), income ? r['category'] as String : (s.code == 'ar' ? r['category_ar'] : r['category_en']) as String),
              if (income) ...[
                _factText(s.get('mnChild'), r['child'] as String? ?? ''),
                _factText(s.get('mnPayer'), r['payer_name'] as String? ?? ''),
                if ((r['invoice_number'] as String? ?? '').isNotEmpty) _factText(s.get('mnInvoice'), r['invoice_number'] as String),
              ] else ...[
                _factText(s.get('mnRecipient'), r['recipient'] as String? ?? ''),
                if ((r['employee'] as String? ?? '').isNotEmpty) _factText(s.get('mnStaffMember'), r['employee'] as String),
                if ((r['salary_month'] as String? ?? '').isNotEmpty) _factText(s.get('mnSalaryFor'), monthTitle(s.code, r['salary_month'] as String)),
              ],
              _fact(
                s.get('mnReallyPaid'),
                Text(
                  '${moneyText(r['amount'] as String?)} ${r['currency']}',
                  textDirection: TextDirection.ltr,
                  textAlign: TextAlign.start,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              _factText(s.get('mnRateShort'), '${moneyText(r['rate'] as String?)} ${s.get('mnPerDollar')}'),
              if ((r['note'] as String? ?? '').isNotEmpty) _factText(s.get('mnNote'), r['note'] as String),
              _factText(s.get('mnRecordedBy'), r['created_by'] == 'auto' ? s.get('mnSystem') : (r['created_by'] as String? ?? '')),
              const Divider(height: 26),
              Text(s.get('mnHistory'), style: const TextStyle(fontWeight: FontWeight.w800)),
              const SizedBox(height: 6),
              FutureBuilder<dynamic>(
                future: api.get('/api/admin/money/history/${r['id']}'),
                builder: (context, snap) {
                  if (snap.hasError) return Text(problemText(context, snap.error!));
                  if (!snap.hasData) return const Padding(padding: EdgeInsets.all(8), child: LinearProgressIndicator());
                  final lines = _list(snap.data);
                  if (lines.isEmpty) return Text(s.get('mnNoHistory'), style: const TextStyle(color: _muted));
                  return Column(
                    children: [
                      for (final x in lines)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 5),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Padding(
                                padding: EdgeInsets.only(top: 5),
                                child: Icon(Icons.circle, size: 8, color: brandBlue),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '${s.get('mnAction_${(x['action'] as String).replaceAll('.', '_')}')} · ${x['actor'] == 'auto' ? s.get('mnSystem') : x['actor']}',
                                      style: const TextStyle(fontWeight: FontWeight.w600),
                                    ),
                                    Text(
                                      (x['at'] as String? ?? '').replaceFirst('T', ' ').padRight(16).substring(0, 16),
                                      textDirection: TextDirection.ltr,
                                      style: const TextStyle(fontSize: 12, color: _muted),
                                    ),
                                    if ((x['reason'] as String? ?? '').isNotEmpty) Text(x['reason'] as String, style: const TextStyle(fontSize: 12.5)),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  );
                },
              ),
              if (meta.canManage && r['is_reversal'] != true) ...[
                const SizedBox(height: 18),
                _secondary(s.get(r['is_test'] == true ? 'mnUnmarkTest' : 'mnMarkTest'), Icons.science_outlined, () async {
                  try {
                    await api.post('/api/admin/money/$kind/${r['id']}/test', {'test': r['is_test'] != true});
                    if (!context.mounted) return;
                    toast(context, s.get(r['is_test'] == true ? 'mnTestUnmarked' : 'mnTestMarked'));
                    Navigator.pop(context, 'changed');
                  } on ApiException catch (e) {
                    if (context.mounted) toast(context, problemText(context, e));
                  }
                }),
              ],
              if (mayCorrect) ...[
                const SizedBox(height: 18),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    if (!closed) _primary(s.get('mnEdit'), Icons.edit_outlined, () => Navigator.pop(context, 'edit')),
                    _secondary(s.get(closed ? 'mnReverse' : 'mnCancelEntry'), Icons.block, color: _bad, () async {
                      final reason = await askText(context, s.get(closed ? 'mnReverseReason' : 'mnCancelReason'), maxLength: 300, maxLines: 2, confirm: closed ? 'mnReverse' : 'mnCancelEntry');
                      if (reason == null || !context.mounted) return;
                      try {
                        await api.post('/api/admin/money/$kind/${r['id']}/void', {'reason': reason.trim()});
                        if (!context.mounted) return;
                        toast(context, s.get('mnCancelledDone'));
                        Navigator.pop(context, 'changed');
                      } on ApiException catch (e) {
                        if (context.mounted) toast(context, problemText(context, e));
                      }
                    }),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _amountBox(String code, String? value) => Container(
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: const Color(0xFFF7F9FC),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: _line),
    ),
    child: Money(code, value, size: 18, weight: FontWeight.w800, color: _negative(value) ? _bad : null),
  );
}

// ---- invoices -------------------------------------------------------------------------------------------------------------------
class _InvoicesPanel extends StatelessWidget {
  const _InvoicesPanel({required this.meta, required this.rows, required this.status, required this.onStatus, required this.onChanged});
  final MoneyMeta meta;
  final List<Map<String, dynamic>> rows;
  final String status;
  final ValueChanged<String> onStatus;
  final Future<void> Function() onChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    Future<void> open(String id) async {
      final changed = await Navigator.push<bool>(
        context,
        MaterialPageRoute(
          builder: (_) => InvoicePage(id: id, meta: meta),
        ),
      );
      if (changed == true) await onChanged();
    }

    return _Panel(
      title: s.get('mnInvoicesTitle'),
      subtitle: s.get('mnInvoiceIsClaim'),
      icon: Icons.receipt_long_outlined,
      padding: const EdgeInsets.fromLTRB(0, 0, 0, 6),
      actions: [
        _secondary(
          s.get('mnNewInvoice'),
          Icons.add_rounded,
          meta.rate == null
              ? null
              : () async {
                  final id = await Navigator.push<String>(context, MaterialPageRoute(builder: (_) => InvoiceForm(meta: meta)));
                  if (id != null) {
                    await onChanged();
                    await open(id);
                  }
                },
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (key, label) in [('unpaid', 'mnUnpaid'), ('', 'mnAllInvoices'), ('paid', 'mnStatusPaid'), ('void', 'mnCancelled')])
                  ChoiceChip(label: Text(s.get(label)), selected: status == key, onSelected: (_) => onStatus(key)),
              ],
            ),
          ),
          if (rows.isEmpty) _empty(s.get('mnNoInvoices'), icon: Icons.receipt_long_outlined),
          for (final (i, v) in rows.indexed) ...[
            if (i > 0) const Divider(height: 1, indent: 16, endIndent: 16),
            InkWell(
              onTap: () => open(v['id'] as String),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                child: Row(
                  children: [
                    const _IconBox(Icons.description_outlined, size: 40),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${v['number']} · ${(v['child'] as String? ?? '').isEmpty ? v['payer_name'] : v['child']}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5)),
                          const SizedBox(height: 3),
                          Text(
                            [v['issued_on'], v['description']].whereType<String>().where((x) => x.isNotEmpty).join(' · '),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 12.5, color: _muted),
                          ),
                          const SizedBox(height: 6),
                          _invoiceTags(s, v),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(s.get(v['status'] == 'paid' || v['status'] == 'void' ? 'mnTotal' : 'mnOpenAmount'), style: const TextStyle(fontSize: 11, color: _faint)),
                        Money('USD', _map(v[v['status'] == 'paid' || v['status'] == 'void' ? 'total' : 'open'])['usd'] as String?, size: 14.5, weight: FontWeight.w800),
                        Money('SYP', _map(v[v['status'] == 'paid' || v['status'] == 'void' ? 'total' : 'open'])['syp'] as String?, size: 12.5, weight: FontWeight.w600, color: _muted),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// A new invoice to a parent: the child or a payer, the currency, the items. An invoice is a claim, not income.
class InvoiceForm extends StatefulWidget {
  const InvoiceForm({super.key, required this.meta, this.invoice});
  final MoneyMeta meta;
  final Map<String, dynamic>? invoice; // an invoice to change
  @override
  State<InvoiceForm> createState() => _InvoiceFormState();
}

class _InvoiceFormState extends State<InvoiceForm> {
  late DateTime _day = DateTime.parse(widget.meta.today);
  final _payer = TextEditingController();
  final _description = TextEditingController();
  final _items = <(TextEditingController, TextEditingController)>[(TextEditingController(), TextEditingController())];
  String _currency = 'USD';
  String? _child;
  List<Map<String, dynamic>> _children = [];
  bool _busy = false;
  bool _test = false;

  @override
  void initState() {
    super.initState();
    final v = widget.invoice;
    if (v != null) {
      _day = DateTime.parse(v['issued_on'] as String);
      _payer.text = v['payer_name'] as String? ?? '';
      _description.text = v['description'] as String? ?? '';
      _currency = v['currency'] as String;
      _child = (v['child_id'] as String? ?? '').isEmpty ? null : v['child_id'] as String;
      _items
        ..clear()
        ..addAll([for (final i in _list(v['items'])) (TextEditingController(text: i['description'] as String), TextEditingController(text: (_currency == 'USD' ? i['usd'] : i['syp']) as String))]);
      if (_items.isEmpty) _items.add((TextEditingController(), TextEditingController()));
    }
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        final list = await SessionScope.of(context).api.get('/api/admin/people/children') as List;
        if (mounted) setState(() => _children = _list(list));
      } catch (_) {}
    });
  }

  Future<void> _save() async {
    final s = S.of(context);
    final items = [
      for (final (d, a) in _items)
        if (a.text.trim().isNotEmpty) {'description': d.text.trim().isEmpty ? s.get('mnItem') : d.text.trim(), 'amount': a.text.trim()},
    ];
    if (items.isEmpty || (_child == null && _payer.text.trim().isEmpty)) {
      toast(context, s.get('mnInvoiceFill'));
      return;
    }
    setState(() => _busy = true);
    try {
      final api = SessionScope.of(context).api;
      final body = {'issued_on': dayText(_day), 'child_id': _child, 'payer_name': _payer.text.trim(), 'description': _description.text.trim(), 'currency': _currency, 'items': items, if (widget.invoice == null) 'test': _test};
      final old = widget.invoice;
      final v = (old == null ? await api.post('/api/admin/money/invoices', body) : await api.patch('/api/admin/money/invoices/${old['id']}', body)) as Map;
      if (!mounted) return;
      toast(context, old == null ? '${s.get('mnInvoiceMade')} ${v['number']}' : s.get('mnInvoiceSaved'));
      Navigator.pop(context, v['id'] as String);
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(widget.invoice == null ? s.get('mnNewInvoice') : '${s.get('mnEditInvoice')} ${widget.invoice!['number']}')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (_busy) const LinearProgressIndicator(),
              FormSection(
                title: s.get('mnInvoiceTo'),
                child: Column(
                  children: [
                    _DayField(label: s.get('mnDate'), day: _day, last: DateTime.parse(widget.meta.today), onChanged: (d) => setState(() => _day = d)),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String?>(
                      initialValue: _child,
                      isExpanded: true,
                      items: [
                        const DropdownMenuItem<String?>(value: null, child: Text('—')),
                        for (final c in _children) DropdownMenuItem<String?>(value: c['id'] as String, child: Text(c['name'] as String)),
                      ],
                      decoration: InputDecoration(labelText: s.get('mnChild')),
                      onChanged: (v) => setState(() => _child = v),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _payer,
                      maxLength: 120,
                      decoration: InputDecoration(labelText: s.get('mnOrPayer')),
                    ),
                    TextField(
                      controller: _description,
                      maxLength: 300,
                      decoration: InputDecoration(labelText: s.get('mnDescriptionOptional')),
                    ),
                    SegmentedButton<String>(
                      segments: [
                        ButtonSegment(value: 'USD', label: Text(s.get('mnDollar'))),
                        ButtonSegment(value: 'SYP', label: Text(s.get('mnPound'))),
                      ],
                      selected: {_currency},
                      onSelectionChanged: (v) => setState(() => _currency = v.first),
                    ),
                    if (widget.invoice == null) CheckboxListTile(contentPadding: EdgeInsets.zero, controlAffinity: ListTileControlAffinity.leading, value: _test, onChanged: (v) => setState(() => _test = v ?? false), title: Text(s.get('mnTestEntry'))),
                  ],
                ),
              ),
              FormSection(
                title: s.get('mnItems'),
                trailing: TextButton.icon(
                  onPressed: _items.length >= 20 ? null : () => setState(() => _items.add((TextEditingController(), TextEditingController()))),
                  icon: const Icon(Icons.add_rounded),
                  label: Text(s.get('mnAddItem')),
                ),
                child: Column(
                  children: [
                    for (final (i, (d, a)) in _items.indexed)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Row(
                          children: [
                            Expanded(
                              flex: 3,
                              child: TextField(
                                controller: d,
                                maxLength: 200,
                                decoration: InputDecoration(labelText: '${s.get('mnItem')} ${i + 1}', counterText: ''),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              flex: 2,
                              child: TextField(
                                controller: a,
                                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                textDirection: TextDirection.ltr,
                                decoration: InputDecoration(labelText: '${s.get('mnAmount')} ($_currency)'),
                              ),
                            ),
                            IconButton(tooltip: s.get('mnRemoveItem'), onPressed: _items.length == 1 ? null : () => setState(() => _items.removeAt(i)), icon: const Icon(Icons.close_rounded)),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
              _hint(s.get('mnInvoiceIsClaimLong')),
            ],
          ),
        ),
      ),
      bottomNavigationBar: BottomActionBar(
        children: [
          Expanded(
            child: FilledButton(onPressed: _busy ? null : _save, child: Text(s.get(widget.invoice == null ? 'mnCreateInvoice' : 'mnSaveChange'))),
          ),
        ],
      ),
    );
  }
}

/// One invoice: items, total, paid, open, the payments; record a payment, the signed PDF, cancelling.
class InvoicePage extends StatefulWidget {
  const InvoicePage({super.key, required this.id, required this.meta});
  final String id;
  final MoneyMeta meta;
  @override
  State<InvoicePage> createState() => _InvoicePageState();
}

class _InvoicePageState extends State<InvoicePage> {
  bool _changed = false;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.pop(context, _changed);
      },
      child: Scaffold(
        appBar: AppBar(title: Text(s.get('mnInvoice'))),
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: _Data<Map<String, dynamic>>(
              signature: widget.id,
              load: () async => _map(await api.get('/api/admin/money/invoices/${widget.id}')),
              builder: (context, v, reload) {
                final open = v['status'] == 'open' || v['status'] == 'partial';
                final cur = v['currency'] as String;
                Widget sumLine(String label, Map<String, dynamic> pair, {bool strong = false, Color? color}) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(label, style: TextStyle(fontWeight: strong ? FontWeight.w800 : FontWeight.w600)),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Money('USD', pair['usd'] as String?, size: strong ? 16 : 14.5, color: color),
                          Money('SYP', pair['syp'] as String?, size: 13, weight: FontWeight.w600, color: color ?? _muted),
                        ],
                      ),
                    ],
                  ),
                );
                final payments = _list(v['payments']);
                return _page([
                  Card(
                    margin: const EdgeInsets.only(bottom: 14),
                    child: Padding(
                      padding: const EdgeInsets.all(18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Row(
                            children: [
                              const _IconBox(Icons.receipt_long_outlined, size: 44),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '${v['number']}',
                                      textDirection: TextDirection.ltr,
                                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
                                    ),
                                    Text((v['child'] as String? ?? '').isEmpty ? v['payer_name'] as String : v['child'] as String, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                                  ],
                                ),
                              ),
                              _invoiceTags(s, v),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              _Tag('${s.get('mnDate')}: ${v['issued_on']}', icon: Icons.event_outlined),
                              _Tag('${s.get('mnInvoiceCurrency')}: $cur', icon: Icons.payments_outlined),
                              _Tag('${s.get('mnRateShort')}: ${moneyText(v['rate'] as String?)}', icon: Icons.currency_exchange_rounded),
                            ],
                          ),
                          if ((v['description'] as String? ?? '').isNotEmpty) Padding(padding: const EdgeInsets.only(top: 10), child: Text(v['description'] as String)),
                          if (v['voided'] == true)
                            Padding(
                              padding: const EdgeInsets.only(top: 10),
                              child: _Tag('${s.get('mnCancelled')}: ${v['void_reason'] ?? ''}', icon: Icons.block),
                            ),
                          const Divider(height: 28),
                          for (final i in _list(v['items']))
                            Padding(
                              padding: const EdgeInsets.symmetric(vertical: 5),
                              child: Row(
                                children: [
                                  Expanded(child: Text(i['description'] as String)),
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.end,
                                    children: [
                                      Money('USD', i['usd'] as String?, size: 14),
                                      Money('SYP', i['syp'] as String?, size: 12.5, weight: FontWeight.w600, color: _muted),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          const Divider(height: 22),
                          sumLine(s.get('mnTotal'), _map(v['total']), strong: true),
                          sumLine(s.get('mnPaid'), _map(v['paid']), color: _good),
                          sumLine(s.get('mnOpenAmount'), _map(v['open']), strong: true, color: open ? _bad : null),
                          const SizedBox(height: 12),
                          Wrap(
                            spacing: 10,
                            runSpacing: 10,
                            children: [
                              if (widget.meta.canCorrect && v['voided'] != true)
                                _primary(s.get('mnEditInvoice'), Icons.edit_outlined, () async {
                                  final id = await Navigator.push<String>(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) => InvoiceForm(meta: widget.meta, invoice: v),
                                    ),
                                  );
                                  if (id != null) {
                                    _changed = true;
                                    await reload();
                                  }
                                }),
                              _secondary(s.get('mnPrint'), Icons.print_outlined, () => _print(context, '/api/admin/money/invoices/${widget.id}.pdf', '${v['number']}.pdf')),
                              if (widget.meta.canManage)
                                _secondary(s.get(v['is_test'] == true ? 'mnUnmarkTest' : 'mnMarkTest'), Icons.science_outlined, () async {
                                  try {
                                    await api.post('/api/admin/money/invoices/${widget.id}/test', {'test': v['is_test'] != true});
                                    _changed = true;
                                    await reload();
                                  } on ApiException catch (e) {
                                    if (context.mounted) toast(context, problemText(context, e));
                                  }
                                }),
                              _secondary(s.get('mnInvoicePdf'), Icons.picture_as_pdf_outlined, () => _pdf(context, '/api/admin/money/invoices/${widget.id}.pdf', '${v['number']}.pdf')),
                              if (widget.meta.canCorrect && v['status'] == 'open' && v['voided'] != true)
                                _secondary(s.get('mnCancelInvoice'), Icons.block, color: _bad, () async {
                                  final reason = await askText(context, s.get('mnCancelReason'), maxLength: 300, maxLines: 2, confirm: 'mnCancelInvoice');
                                  if (reason == null || !context.mounted) return;
                                  try {
                                    await api.post('/api/admin/money/invoices/${widget.id}/void', {'reason': reason});
                                    _changed = true;
                                    await reload();
                                  } on ApiException catch (e) {
                                    if (context.mounted) toast(context, problemText(context, e));
                                  }
                                }),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                  _Panel(
                    title: s.get('mnPayments'),
                    icon: Icons.payments_outlined,
                    child: payments.isEmpty
                        ? _empty(s.get('mnNoPayments'))
                        : Column(
                            children: [
                              for (final (i, p) in payments.indexed) ...[
                                if (i > 0) const Divider(height: 1),
                                Padding(
                                  padding: const EdgeInsets.symmetric(vertical: 10),
                                  child: Row(
                                    children: [
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              '${moneyText(p['amount'] as String?)} ${p['currency']}',
                                              textDirection: TextDirection.ltr,
                                              style: TextStyle(fontWeight: FontWeight.w800, decoration: p['voided'] == true ? TextDecoration.lineThrough : null),
                                            ),
                                            Text(
                                              '${p['booked_on']} · ${s.get('mnRateShort')} ${moneyText(p['rate'] as String?)}${(p['payer_name'] as String? ?? '').isEmpty ? '' : ' · ${p['payer_name']}'}',
                                              style: const TextStyle(fontSize: 12.5, color: _muted),
                                            ),
                                            if (p['voided'] == true) Padding(padding: const EdgeInsets.only(top: 4), child: _Tag('${s.get('mnCancelled')}: ${p['void_reason'] ?? ''}')),
                                            if (widget.meta.canCorrect && p['voided'] != true && p['is_reversal'] != true)
                                              Padding(
                                                padding: const EdgeInsets.only(top: 6),
                                                child: _secondary(s.get('mnCancelPayment'), Icons.block, color: _bad, () async {
                                                  final reason = await askText(context, s.get('mnCancelReason'), maxLength: 300, maxLines: 2, confirm: 'mnCancelPayment');
                                                  if (reason == null || !context.mounted) return;
                                                  try {
                                                    await api.post('/api/admin/money/income/${p['id']}/void', {'reason': reason});
                                                    _changed = true;
                                                    if (context.mounted) toast(context, s.get('mnCancelledDone'));
                                                    await reload();
                                                  } on ApiException catch (e) {
                                                    if (context.mounted) toast(context, problemText(context, e));
                                                  }
                                                }),
                                              ),
                                          ],
                                        ),
                                      ),
                                      Column(
                                        crossAxisAlignment: CrossAxisAlignment.end,
                                        children: [
                                          Text(s.get('mnCredited'), style: const TextStyle(fontSize: 11, color: _faint)),
                                          Text(
                                            '${moneyText(p['credited'] as String?)} $cur',
                                            textDirection: TextDirection.ltr,
                                            style: const TextStyle(fontWeight: FontWeight.w700),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ],
                          ),
                  ),
                  _Panel(
                    title: s.get('mnHistory'),
                    icon: Icons.history_rounded,
                    child: _History(id: widget.id),
                  ),
                  if (open && v['voided'] != true && widget.meta.rate != null)
                    _PaymentForm(
                      invoiceId: widget.id,
                      meta: widget.meta,
                      payer: v['payer_name'] as String? ?? '',
                      currency: cur,
                      onSaved: () async {
                        _changed = true;
                        await reload();
                      },
                    ),
                ]);
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _PaymentForm extends StatefulWidget {
  const _PaymentForm({required this.invoiceId, required this.meta, required this.payer, required this.currency, required this.onSaved});
  final String invoiceId;
  final MoneyMeta meta;
  final String payer;
  final String currency;
  final Future<void> Function() onSaved;
  @override
  State<_PaymentForm> createState() => _PaymentFormState();
}

class _PaymentFormState extends State<_PaymentForm> {
  final _amount = TextEditingController();
  late final _payer = TextEditingController(text: widget.payer);
  late final _rate = TextEditingController(text: (widget.meta.rate?['syp_per_usd'] as String?) ?? '');
  late String _currency = widget.currency;
  late DateTime _day = DateTime.parse(widget.meta.today);
  bool _busy = false;

  Future<void> _pickDay(DateTime d) async {
    setState(() => _day = d);
    try {
      final r = await SessionScope.of(context).api.get('/api/admin/money/rates', query: {'day': dayText(d)}) as Map;
      if (mounted && r['for_day'] != null) setState(() => _rate.text = r['for_day'] as String);
    } catch (_) {}
  }

  Future<void> _pay() async {
    if (_amount.text.trim().isEmpty) return;
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    setState(() => _busy = true);
    try {
      await api.post('/api/admin/money/invoices/${widget.invoiceId}/payments', {
        'booked_on': dayText(_day),
        'amount': _amount.text.trim(),
        'currency': _currency,
        'payer_name': _payer.text.trim(),
        if (widget.meta.canManage && _rate.text.trim().isNotEmpty) 'rate': _rate.text.trim(),
      });
      if (!mounted) return;
      toast(context, s.get('mnPaymentSaved'));
      _amount.clear();
      await widget.onSaved();
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return _Panel(
      title: s.get('mnRecordPayment'),
      subtitle: s.get('mnPaymentNote'),
      icon: Icons.add_card_outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Grid(
            minWidth: 220,
            children: [
              _DayField(label: s.get('mnDate'), day: _day, last: DateTime.parse(widget.meta.today), onChanged: _pickDay),
              TextField(
                controller: _payer,
                maxLength: 120,
                decoration: InputDecoration(labelText: s.get('mnPayer'), counterText: ''),
              ),
            ],
          ),
          _Grid(
            minWidth: 220,
            children: [
              TextField(
                controller: _amount,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                textDirection: TextDirection.ltr,
                decoration: InputDecoration(labelText: s.get('mnAmount')),
              ),
              TextField(
                controller: _rate,
                readOnly: !widget.meta.canManage,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                textDirection: TextDirection.ltr,
                decoration: InputDecoration(labelText: s.get('mnRateShort'), helperText: widget.meta.canManage ? null : s.get('mnRateFixed')),
              ),
            ],
          ),
          SegmentedButton<String>(
            segments: [
              ButtonSegment(value: 'USD', label: Text(s.get('mnDollar'))),
              ButtonSegment(value: 'SYP', label: Text(s.get('mnPound'))),
            ],
            selected: {_currency},
            onSelectionChanged: (v) => setState(() => _currency = v.first),
          ),
          const SizedBox(height: 14),
          Align(alignment: AlignmentDirectional.centerStart, child: _primary(s.get('mnRecordPayment'), Icons.check_rounded, _busy ? null : _pay)),
        ],
      ),
    );
  }
}

/// The history of an entry or an invoice: who did what, when, and why.
class _History extends StatelessWidget {
  const _History({required this.id});
  final String id;
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return FutureBuilder<dynamic>(
      future: SessionScope.of(context).api.get('/api/admin/money/history/$id'),
      builder: (context, snap) {
        if (snap.hasError) return Text(problemText(context, snap.error!));
        if (!snap.hasData) return const Padding(padding: EdgeInsets.all(8), child: LinearProgressIndicator());
        final lines = _list(snap.data);
        if (lines.isEmpty) return Text(s.get('mnNoHistory'), style: const TextStyle(color: _muted));
        return Column(
          children: [
            for (final x in lines)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 5),
                      child: Icon(Icons.circle, size: 8, color: brandBlue),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${s.get('mnAction_${(x['action'] as String).replaceAll('.', '_')}')} · ${x['actor'] == 'auto' ? s.get('mnSystem') : x['actor']}',
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          Text(
                            (x['at'] as String? ?? '').replaceFirst('T', ' ').padRight(16).substring(0, 16),
                            textDirection: TextDirection.ltr,
                            style: const TextStyle(fontSize: 12, color: _muted),
                          ),
                          if ((x['reason'] as String? ?? '').isNotEmpty) Text(x['reason'] as String, style: const TextStyle(fontSize: 12.5)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }
}

// ---- income categories (management) ----------------------------------------------------------------------------------------------
class _CategoriesPanel extends StatefulWidget {
  const _CategoriesPanel({required this.meta, required this.onChanged});
  final MoneyMeta meta;
  final Future<void> Function() onChanged;
  @override
  State<_CategoriesPanel> createState() => _CategoriesPanelState();
}

class _CategoriesPanelState extends State<_CategoriesPanel> {
  final _name = TextEditingController();
  bool _busy = false;

  Future<void> _call(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
      await widget.onChanged();
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          leading: const _IconBox(Icons.category_outlined, size: 34),
          title: Text(s.get('mnCategoriesTitle'), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          subtitle: Text(s.get('mnCategoriesHint'), style: const TextStyle(fontSize: 12.5, color: _muted)),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          children: [
            for (final c in widget.meta.incomeCategories)
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                secondary: IconButton(
                  tooltip: s.get('mnRename'),
                  icon: const Icon(Icons.edit_outlined, size: 20),
                  onPressed: _busy
                      ? null
                      : () async {
                          final name = await askText(context, s.get('mnRename'), initial: c['name'] as String, maxLength: 80);
                          if (name == null || name.trim().length < 2) return;
                          await _call(() => api.patch('/api/admin/money/categories/${c['id']}', {'name': name.trim()}));
                        },
                ),
                title: Text(c['name'] as String, style: const TextStyle(fontWeight: FontWeight.w600)),
                subtitle: c['key'] == 'tuition' ? Text(s.get('mnBuiltIn'), style: const TextStyle(fontSize: 12)) : null,
                value: c['is_active'] == true,
                onChanged: c['key'] == 'tuition' || _busy ? null : (v) => _call(() => api.patch('/api/admin/money/categories/${c['id']}', {'is_active': v})),
              ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _name,
                    maxLength: 80,
                    decoration: InputDecoration(labelText: s.get('mnNewCategory'), counterText: ''),
                  ),
                ),
                const SizedBox(width: 10),
                _secondary(
                  s.get('mnAdd'),
                  Icons.add_rounded,
                  _busy
                      ? null
                      : () {
                          if (_name.text.trim().length < 2) return;
                          _call(() async {
                            await api.post('/api/admin/money/categories', {'name': _name.text.trim()});
                            _name.clear();
                          });
                        },
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ---- salaries ---------------------------------------------------------------------------------------------------------------------
class _SalariesPanel extends StatefulWidget {
  const _SalariesPanel({required this.meta, required this.d, required this.onPay});
  final MoneyMeta meta;
  final Map<String, dynamic> d;
  final Future<void> Function(Map<String, dynamic>) onPay;
  @override
  State<_SalariesPanel> createState() => _SalariesPanelState();
}

class _SalariesPanelState extends State<_SalariesPanel> {
  String _scope = 'all';

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final d = widget.d;
    final rows = _list(d['rows']);
    final narrow = MediaQuery.sizeOf(context).width < 600;
    Widget status(Map<String, dynamic> p) {
      if (p['paid'] == true) {
        return _Tag(
          '${s.get(p['automatic'] == true ? 'mnPaidAuto' : 'mnPaidDone')} · ${moneyText(p['paid_amount'] as String?)} ${p['paid_currency']}',
          fg: _good,
          bg: _goodBg,
          icon: Icons.check_rounded,
        );
      }
      if (p['is_active'] == true && widget.meta.rate != null) return _secondary(s.get('mnPaySalary'), Icons.payments_outlined, () => widget.onPay(p));
      return _Tag(s.get('mnNotPaid'), fg: _bad, bg: _badBg);
    }

    return _Panel(
      title: '${s.get('mnSalariesOf')} ${monthTitle(s.code, d['month'] as String)}',
      icon: Icons.badge_outlined,
      padding: const EdgeInsets.fromLTRB(0, 0, 0, 6),
      actions: [
        _Tag('${d['paid']} ${s.get('mnPaidCount')}', fg: _good, bg: _goodBg),
        _Tag('${d['unpaid']} ${s.get('mnUnpaidCount')}', fg: (d['unpaid'] as int) > 0 ? _bad : _neutral, bg: (d['unpaid'] as int) > 0 ? _badBg : _neutralBg),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (rows.isEmpty) _empty(s.get('mnNoStaff'), icon: Icons.people_outline),
          for (final (i, p) in rows.indexed) ...[
            if (i > 0) const Divider(height: 1, indent: 16, endIndent: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  AvatarInitials(p['name'] as String, size: 40),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${p['name']}${p['is_active'] == true ? '' : ' (${s.get('mnLeft')})'}', style: const TextStyle(fontWeight: FontWeight.w700)),
                        Text(
                          [
                            if ((p['job_title'] as String? ?? '').isNotEmpty) p['job_title'] as String,
                            p['salary'] == null ? s.get('mnNoSalarySaved') : '${s.get('mnUsualSalary')} ${moneyText(p['salary'] as String?)} ${p['salary_currency']}',
                          ].join(' · '),
                          style: const TextStyle(fontSize: 12.5, color: _muted),
                        ),
                        if (narrow) Padding(padding: const EdgeInsets.only(top: 8), child: status(p)),
                      ],
                    ),
                  ),
                  if (!narrow) ...[const SizedBox(width: 10), status(p)],
                ],
              ),
            ),
          ],
          Padding(padding: const EdgeInsets.fromLTRB(16, 8, 16, 0), child: _hint(s.get('mnSalaryNote'))),
          if (widget.meta.canManage)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
              child: Wrap(
                spacing: 10,
                runSpacing: 10,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(s.get('mnStaffList'), style: const TextStyle(fontWeight: FontWeight.w700)),
                  SegmentedButton<String>(
                    segments: [
                      ButtonSegment(value: 'all', label: Text(s.get('mnAllStaff'))),
                      ButtonSegment(value: 'active', label: Text(s.get('mnActiveStaff'))),
                    ],
                    selected: {_scope},
                    onSelectionChanged: (v) => setState(() => _scope = v.first),
                  ),
                  _secondary('PDF', Icons.picture_as_pdf_outlined, () => _pdf(context, '/api/admin/people/employees/export.pdf', 'staff-$_scope.pdf', {'scope': _scope})),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

// ================================================================================================================================
// the form of an income or expense (new, change, salary)
// ================================================================================================================================
class MoneyEntryForm extends StatefulWidget {
  const MoneyEntryForm({super.key, required this.kind, required this.meta, required this.month, this.row, this.salaryFor});
  final String kind;
  final MoneyMeta meta;
  final String month;
  final Map<String, dynamic>? row; // an entry to change
  final Map<String, dynamic>? salaryFor; // a row of /salaries: pays the salary of this person
  @override
  State<MoneyEntryForm> createState() => _MoneyEntryFormState();
}

class _MoneyEntryFormState extends State<MoneyEntryForm> {
  final _description = TextEditingController();
  final _who = TextEditingController();
  final _amount = TextEditingController();
  final _rate = TextEditingController();
  final _note = TextEditingController();
  late DateTime _day;
  late String _salaryMonth = widget.month;
  String? _category;
  String _currency = 'USD';
  String? _link; // a child (income) or a person of the staff (salary)
  bool _test = false; // a trial entry: "delete test data" removes it again
  List<Map<String, dynamic>> _people = [];
  bool _busy = false;
  bool get income => widget.kind == 'income';

  @override
  void initState() {
    super.initState();
    final row = widget.row;
    final meta = widget.meta;
    _day = DateTime.parse(row?['booked_on'] as String? ?? meta.today);
    _rate.text = (row?['rate'] as String?) ?? (meta.rate?['syp_per_usd'] as String?) ?? '';
    if (row != null) {
      _description.text = row['description'] as String;
      _amount.text = (row['amount'] as String).replaceFirst('-', '');
      _currency = row['currency'] as String;
      _note.text = row['note'] as String? ?? '';
      if (income) {
        _category = row['category_id'] as String;
        _link = (row['child_id'] as String? ?? '').isEmpty ? null : row['child_id'] as String;
        _who.text = row['payer_name'] as String? ?? '';
      } else {
        _category = row['category'] as String;
        _link = (row['employee_id'] as String? ?? '').isEmpty ? null : row['employee_id'] as String;
        _who.text = row['recipient'] as String? ?? '';
        if ((row['salary_month'] as String? ?? '').isNotEmpty) _salaryMonth = row['salary_month'] as String;
      }
    } else {
      final cats = income ? meta.incomeCategories.where((c) => c['is_active'] == true).toList() : meta.expenseCategories;
      _category = cats.isEmpty ? null : (income ? cats.first['id'] : cats.first['key']) as String;
      final p = widget.salaryFor;
      if (p != null) {
        _category = 'salaries';
        _link = p['employee_id'] as String;
        _who.text = p['name'] as String;
        if (p['salary'] != null) _amount.text = p['salary'] as String;
        _currency = (p['salary_currency'] as String?) ?? 'SYP';
      } else if (!income && meta.expenseCategories.any((c) => c['key'] == 'food')) {
        _category = 'food';
      }
    }
    for (final c in [_amount, _rate]) {
      c.addListener(() => setState(() {}));
    }
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadPeople());
  }

  Future<void> _loadPeople() async {
    final api = SessionScope.of(context).api;
    final p = widget.salaryFor;
    if (p != null && _description.text.isEmpty) _description.text = '${S.of(context).get('mnSalaryWord')} ${p['name']}';
    try {
      final list = await api.get(income ? '/api/admin/people/children' : '/api/admin/people/employees') as List;
      if (mounted) setState(() => _people = _list(list));
    } catch (_) {}
  }

  Future<void> _dayChanged(DateTime picked) async {
    setState(() => _day = picked);
    if (widget.row != null) return; // a change keeps the rate it was made with
    try {
      final r = await SessionScope.of(context).api.get('/api/admin/money/rates', query: {'day': dayText(picked)}) as Map;
      if (mounted && r['for_day'] != null) setState(() => _rate.text = r['for_day'] as String);
    } catch (_) {}
  }

  /// The value in the other currency, only as a hint (the server calculates the real one with Decimal).
  String _approx() {
    final n = double.tryParse(_amount.text.trim());
    final r = double.tryParse(_rate.text.trim());
    if (n == null || r == null || r == 0) return '';
    return _currency == 'USD' ? '≈ SYP ${moneyText((n * r).round().toString())}' : '≈ USD ${moneyText((n / r).toStringAsFixed(2))}';
  }

  Future<void> _save() async {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    final salary = !income && _category == 'salaries';
    if (_description.text.trim().length < 2 || _amount.text.trim().isEmpty || _category == null || (salary && _link == null)) {
      toast(context, s.get(salary && _link == null ? 'mnPickStaff' : 'mnFillIn'));
      return;
    }
    final row = widget.row;
    final body = <String, dynamic>{
      'booked_on': dayText(_day),
      'description': _description.text.trim(),
      'amount': _amount.text.trim(),
      'currency': _currency,
      'note': _note.text.trim(),
      if (widget.meta.canManage && _rate.text.trim().isNotEmpty) 'rate': _rate.text.trim(),
      if (income) ...{'category_id': _category, 'child_id': _link, 'payer_name': _who.text.trim()},
      if (!income) ...{'category': _category, 'recipient': _who.text.trim(), 'employee_id': salary ? _link : null, 'salary_month': salary ? _salaryMonth : null},
      if (row != null) 'expected_version': row['version'],
      if (row == null) 'test': _test,
    };
    setState(() => _busy = true);
    try {
      if (row == null) {
        await api.post('/api/admin/money/${widget.kind}', body);
      } else {
        await api.patch('/api/admin/money/${widget.kind}/${row['id']}', body);
      }
      if (!mounted) return;
      toast(context, s.get('mnSaved'));
      Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) toast(context, problemText(context, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final row = widget.row;
    final cats = income
        ? [
            for (final c in widget.meta.incomeCategories.where((c) => c['is_active'] == true || c['id'] == row?['category_id']))
              DropdownMenuItem(value: c['id'] as String, child: Text(c['name'] as String)),
          ]
        : [for (final c in widget.meta.expenseCategories) DropdownMenuItem(value: c['key'] as String, child: Text((s.code == 'ar' ? c['ar'] : c['en']) as String))];
    final salary = !income && _category == 'salaries';
    final title = row != null
        ? s.get(income ? 'mnEditIncome' : 'mnEditExpense')
        : widget.salaryFor != null
        ? '${s.get('mnPaySalary')} · ${widget.salaryFor!['name']}'
        : s.get(income ? 'mnNewIncome' : 'mnNewExpense');
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (_busy) const LinearProgressIndicator(),
              FormSection(
                title: s.get('mnWhat'),
                child: Column(
                  children: [
                    _DayField(label: s.get(income ? 'mnDate' : 'mnDatePaid'), day: _day, last: DateTime.parse(widget.meta.today), onChanged: _dayChanged),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _description,
                      maxLength: 300,
                      decoration: InputDecoration(labelText: s.get('mnReason'), hintText: s.get(income ? 'mnReasonHintIncome' : 'mnReasonHintExpense')),
                    ),
                    DropdownButtonFormField<String>(
                      initialValue: _category,
                      isExpanded: true,
                      items: cats,
                      decoration: InputDecoration(labelText: s.get('mnCategory')),
                      onChanged: (v) => setState(() => _category = v),
                    ),
                    const SizedBox(height: 12),
                    if (income || salary) ...[
                      DropdownButtonFormField<String?>(
                        key: ValueKey('people-${_people.length}-$salary'),
                        initialValue: _people.any((p) => p['id'] == _link) ? _link : null,
                        isExpanded: true,
                        items: [
                          const DropdownMenuItem<String?>(value: null, child: Text('—')),
                          for (final p in _people) DropdownMenuItem<String?>(value: p['id'] as String, child: Text(p['name'] as String)),
                        ],
                        decoration: InputDecoration(labelText: s.get(income ? 'mnChildOptional' : 'mnStaffMember')),
                        onChanged: (v) => setState(() => _link = v),
                      ),
                      const SizedBox(height: 12),
                    ],
                    if (salary) ...[
                      InkWell(
                        borderRadius: BorderRadius.circular(14),
                        onTap: () async {
                          final v = await pickMonth(context, _salaryMonth);
                          if (v != null) setState(() => _salaryMonth = v);
                        },
                        child: InputDecorator(
                          decoration: InputDecoration(labelText: s.get('mnSalaryFor'), suffixIcon: const Icon(Icons.calendar_month_outlined)),
                          child: Text(monthTitle(s.code, _salaryMonth)),
                        ),
                      ),
                      const SizedBox(height: 12),
                    ],
                    TextField(
                      controller: _who,
                      maxLength: 120,
                      decoration: InputDecoration(labelText: s.get(income ? 'mnPayerOptional' : 'mnRecipientOptional')),
                    ),
                  ],
                ),
              ),
              FormSection(
                title: s.get('mnAmountTitle'),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextField(
                      controller: _amount,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      textDirection: TextDirection.ltr,
                      decoration: InputDecoration(labelText: s.get('mnAmount')),
                    ),
                    const SizedBox(height: 12),
                    SegmentedButton<String>(
                      segments: [
                        ButtonSegment(value: 'USD', label: Text(s.get('mnDollar'))),
                        ButtonSegment(value: 'SYP', label: Text(s.get('mnPound'))),
                      ],
                      selected: {_currency},
                      onSelectionChanged: (v) => setState(() => _currency = v.first),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _rate,
                      readOnly: !widget.meta.canManage,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      textDirection: TextDirection.ltr,
                      decoration: InputDecoration(labelText: s.get('mnRate'), helperText: widget.meta.canManage ? null : s.get('mnRateFixed')),
                    ),
                    if (_approx().isNotEmpty)
                      Container(
                        margin: const EdgeInsets.only(top: 12),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                        decoration: BoxDecoration(color: brandSoft, borderRadius: BorderRadius.circular(12)),
                        child: Text(
                          _approx(),
                          textDirection: TextDirection.ltr,
                          style: const TextStyle(fontWeight: FontWeight.w800, color: brandBlue),
                        ),
                      ),
                  ],
                ),
              ),
              FormSection(
                title: s.get('mnNote'),
                child: TextField(
                  controller: _note,
                  maxLength: 500,
                  decoration: InputDecoration(labelText: s.get('mnNote')),
                ),
              ),
              if (!income) _hint(s.get('mnOnlyPaid')),
              if (row == null) CheckboxListTile(contentPadding: EdgeInsets.zero, controlAffinity: ListTileControlAffinity.leading, value: _test, onChanged: (v) => setState(() => _test = v ?? false), title: Text(s.get('mnTestEntry'))),
            ],
          ),
        ),
      ),
      bottomNavigationBar: BottomActionBar(
        children: [
          Expanded(
            child: FilledButton(onPressed: _busy || widget.meta.rate == null ? null : _save, child: Text(s.get(row == null ? 'mnRecord' : 'mnSaveChange'))),
          ),
        ],
      ),
    );
  }
}

// ================================================================================================================================
// for the management: the three pages behind one entry of its menu
// ================================================================================================================================
class MoneyHub extends StatelessWidget {
  const MoneyHub({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return DefaultTabController(
      length: 3,
      child: Column(
        children: [
          Container(
            margin: const EdgeInsets.fromLTRB(14, 12, 14, 0),
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: _line),
            ),
            child: TabBar(
              dividerColor: Colors.transparent,
              indicatorSize: TabBarIndicatorSize.tab,
              indicator: BoxDecoration(color: brandBlue, borderRadius: BorderRadius.circular(10)),
              labelColor: Colors.white,
              unselectedLabelColor: _muted,
              labelStyle: const TextStyle(fontWeight: FontWeight.w800),
              tabs: [
                Tab(height: 40, text: s.get('mnSummary')),
                Tab(height: 40, text: s.get('mnIncome')),
                Tab(height: 40, text: s.get('mnExpenses')),
              ],
            ),
          ),
          const Expanded(
            child: TabBarView(
              children: [
                MoneySummaryPage(),
                MoneyEntriesPage(kind: 'income'),
                MoneyEntriesPage(kind: 'expenses'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
