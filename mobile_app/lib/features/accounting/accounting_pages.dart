import 'package:flutter/material.dart';

import '../../localization/strings.dart';
import '../../services/api.dart';
import '../../shared/ui.dart';

// The accounting in the app: the same three pages as on the website (income, expenses, month overview), on the same server
// endpoints (/api/admin/money). Every amount stands in US dollars and Syrian pounds side by side; amounts come from the
// server as decimal text and are only formatted here, never computed with floating point. Nothing is deleted: an entry is
// cancelled with a reason. What a person may do comes from the server (`rights` of /meta) and is checked there again.

const _good = Color(0xFF1E7A45);
const _bad = Color(0xFFB3402F);
const _muted = Color(0xFF5B6878);

/// "1234567.5" -> "1,234,567.5". Only the text is changed; there is no arithmetic.
String moneyText(String? text) {
  if (text == null || text.isEmpty) return '—';
  final negative = text.startsWith('-');
  final parts = text.replaceFirst(RegExp(r'^[-+]'), '').split('.');
  final whole = parts[0].replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => ',');
  return '${negative ? '-' : ''}$whole${parts.length > 1 ? '.${parts[1]}' : ''}';
}

bool _negative(String? text) => text != null && text.startsWith('-') && text.replaceAll(RegExp(r'[-0.,]'), '').isNotEmpty;

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
  List<Map<String, dynamic>> get incomeCategories => [for (final c in data['income_categories'] as List) (c as Map).cast<String, dynamic>()];
  List<Map<String, dynamic>> get expenseCategories => [for (final c in data['expense_categories'] as List) (c as Map).cast<String, dynamic>()];
}

Future<MoneyMeta> loadMeta(ApiClient api) async => MoneyMeta((await api.get('/api/admin/money/meta') as Map).cast<String, dynamic>());

// ---- small pieces --------------------------------------------------------------------------------------------------------------
/// One amount in both currencies.
class TwoAmounts extends StatelessWidget {
  const TwoAmounts(this.usd, this.syp, {super.key, this.size = 15, this.strong = false});
  final String? usd;
  final String? syp;
  final double size;
  final bool strong;
  @override
  Widget build(BuildContext context) {
    final style = TextStyle(fontSize: size, fontWeight: strong ? FontWeight.w800 : FontWeight.w600, fontFeatures: const [FontFeature.tabularFigures()]);
    return Directionality(
      textDirection: TextDirection.ltr,
      child: Wrap(spacing: 14, runSpacing: 2, children: [Text('USD ${moneyText(usd)}', style: style), Text('SYP ${moneyText(syp)}', style: style.copyWith(color: const Color(0xFF42536A)))]),
    );
  }
}

/// The exchange rate of today in one line.
class RateStrip extends StatelessWidget {
  const RateStrip(this.meta, {super.key});
  final MoneyMeta meta;
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final r = meta.rate;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        dense: true,
        leading: const Icon(Icons.currency_exchange, color: brandBlue),
        title: Text(r == null ? s.get('mnNoRate') : '${moneyText(r['syp_per_usd'] as String?)} ${s.get('mnPerDollar')}', style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: r == null ? null : Text('${s.get(r['source'] == 'auto' ? 'mnRateAuto' : 'mnRateManual')} · ${r['valid_from']}${r['stale'] == true ? ' · ${s.get('mnRateOld')}' : ''}'),
      ),
    );
  }
}

/// ◀ month ▶ in the reading direction (the arrows turn with the language).
class MonthBar extends StatelessWidget {
  const MonthBar({super.key, required this.month, required this.onChanged});
  final String month;
  final ValueChanged<String> onChanged;
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return Row(children: [
      IconButton(tooltip: s.get('mnPrevMonth'), onPressed: () => onChanged(shiftMonth(month, -1)), icon: const Icon(Icons.arrow_back)),
      Expanded(child: Text(monthTitle(s.code, month), textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
      IconButton(tooltip: s.get('mnNextMonth'), onPressed: () => onChanged(shiftMonth(month, 1)), icon: const Icon(Icons.arrow_forward)),
    ]);
  }
}

/// A figure card: a label, the amount in dollars and in pounds, a short note.
class MoneyTile extends StatelessWidget {
  const MoneyTile({super.key, required this.label, required this.usd, required this.syp, this.note, this.colored = false});
  final String label;
  final String? usd;
  final String? syp;
  final String? note;
  final bool colored;
  @override
  Widget build(BuildContext context) {
    Color tone(String? v) => !colored ? const Color(0xFF16253A) : (_negative(v) ? _bad : _good);
    final style = const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, fontFeatures: [FontFeature.tabularFigures()]);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: const TextStyle(fontSize: 13, color: _muted)),
          const SizedBox(height: 6),
          Directionality(
            textDirection: TextDirection.ltr,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('USD ${moneyText(usd)}', style: style.copyWith(color: tone(usd))),
              Text('SYP ${moneyText(syp)}', style: style.copyWith(color: tone(syp))),
            ]),
          ),
          if (note != null) Padding(padding: const EdgeInsets.only(top: 4), child: Text(note!, style: const TextStyle(fontSize: 12, color: _muted))),
        ]),
      ),
    );
  }
}

Widget _stateTag(S s, Map<String, dynamic> r) {
  if (r['voided'] == true) return Pill('${s.get('mnCancelled')}: ${r['void_reason']}', foreground: const Color(0xFF42536A));
  if (r['is_reversal'] == true) return Pill(s.get('mnReversal'), foreground: const Color(0xFF8A5200), background: const Color(0xFFFDF1DD));
  if (r['reversed'] == true) return Pill(s.get('mnReversed'), foreground: const Color(0xFF8A5200), background: const Color(0xFFFDF1DD));
  return const SizedBox.shrink();
}

// ---- the month overview --------------------------------------------------------------------------------------------------------
class MoneySummaryPage extends StatefulWidget {
  const MoneySummaryPage({super.key});
  @override
  State<MoneySummaryPage> createState() => _MoneySummaryPageState();
}

class _MoneySummaryPageState extends State<MoneySummaryPage> {
  String month = monthKey(DateTime.now());

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<(MoneyMeta, Map<String, dynamic>)>(
      key: ValueKey('summary-$month'),
      load: () async {
        final meta = await loadMeta(api);
        final d = (await api.get('/api/admin/money/summary', query: {'month': month}) as Map).cast<String, dynamic>();
        return Cached((meta, d));
      },
      builder: (context, data, reload) {
        final (meta, d) = data;
        Map<String, dynamic> m(String k) => (d[k] as Map).cast<String, dynamic>();
        final balance = m('balance');
        final start = (balance['start'] as Map).cast<String, dynamic>();
        final end = (balance['end'] as Map).cast<String, dynamic>();
        final known = start['usd'] != null || start['syp'] != null;
        final invoices = m('invoices');
        final unpaid = (invoices['open'] as int) + (invoices['partial'] as int);
        List<Widget> cats(String key, String Function(Map<String, dynamic>) name) => [
              for (final c in (d[key] as List).cast<Map>())
                ListTile(dense: true, title: Text(name(c.cast<String, dynamic>())), subtitle: TwoAmounts(c['usd'] as String?, c['syp'] as String?, size: 13), trailing: Text('${c['count']}')),
            ];
        return ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 24), children: [
          MonthBar(month: month, onChanged: (v) => setState(() => month = v)),
          Wrap(spacing: 8, children: [
            Pill(d['closed'] == true ? s.get('mnMonthClosed') : s.get('mnMonthOpen'), foreground: d['closed'] == true ? _good : const Color(0xFF42536A)),
          ]),
          const SizedBox(height: 8),
          RateStrip(meta),
          MoneyTile(label: s.get('mnProfitLoss'), usd: m('surplus')['usd'] as String?, syp: m('surplus')['syp'] as String?, colored: true,
              note: '${d['income_count']} ${s.get('mnIncomeEntries')} · ${d['expense_count']} ${s.get('mnExpenseEntries')}'),
          Row(children: [
            Expanded(child: MoneyTile(label: s.get('mnIncome'), usd: m('income')['usd'] as String?, syp: m('income')['syp'] as String?)),
            const SizedBox(width: 8),
            Expanded(child: MoneyTile(label: s.get('mnExpenses'), usd: m('expense')['usd'] as String?, syp: m('expense')['syp'] as String?)),
          ]),
          Row(children: [
            Expanded(child: MoneyTile(label: s.get('mnSalaries'), usd: m('salaries')['usd'] as String?, syp: m('salaries')['syp'] as String?)),
            const SizedBox(width: 8),
            Expanded(
              child: MoneyTile(label: s.get('mnUnpaidInvoices'), usd: (invoices['open_amount'] as Map)['usd'] as String?, syp: (invoices['open_amount'] as Map)['syp'] as String?, note: '$unpaid'),
            ),
          ]),
          SectionTitle(s.get('mnCash')),
          if (known)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Text(s.get('mnCashStart'), style: const TextStyle(color: _muted, fontSize: 13)),
                  TwoAmounts(start['usd'] as String?, start['syp'] as String?),
                  const Divider(height: 20),
                  Text(s.get('mnCashEnd'), style: const TextStyle(color: _muted, fontSize: 13)),
                  TwoAmounts(end['usd'] as String?, end['syp'] as String?, strong: true, size: 17),
                ]),
              ),
            )
          else
            Card(child: Padding(padding: const EdgeInsets.all(14), child: Text(s.get('mnNoCash'), style: const TextStyle(color: _muted)))),
          SectionTitle(s.get('mnIncomeByCategory')),
          Card(child: Column(children: cats('income_by_category', (c) => c['name'] as String).isEmpty ? [ListTile(title: Text(s.get('mnNoEntries')))] : cats('income_by_category', (c) => c['name'] as String))),
          SectionTitle(s.get('mnExpensesByCategory')),
          Card(child: Column(children: cats('expense_by_category', (c) => c[s.code == 'ar' ? 'ar' : 'en'] as String).isEmpty ? [ListTile(title: Text(s.get('mnNoEntries')))] : cats('expense_by_category', (c) => c[s.code == 'ar' ? 'ar' : 'en'] as String))),
          if (meta.canExport) ...[
            const SizedBox(height: 12),
            OutlinedButton.icon(
              icon: const Icon(Icons.picture_as_pdf_outlined),
              label: Text(s.get('mnReportPdf')),
              onPressed: () => openPrivateFile(context, api, '/api/admin/money/export/summary.pdf', 'report-$month.pdf', query: {'month': month}),
            ),
          ],
          const SizedBox(height: 8),
          Text(s.get('mnColumnsNote'), style: const TextStyle(fontSize: 12, color: _muted, height: 1.5)),
        ]);
      },
    );
  }
}

// ---- income and expenses -------------------------------------------------------------------------------------------------------
/// The list of one month with its totals. `kind` is "income" or "expenses" (the path on the server).
class MoneyEntriesPage extends StatefulWidget {
  const MoneyEntriesPage({super.key, required this.kind});
  final String kind;
  @override
  State<MoneyEntriesPage> createState() => _MoneyEntriesPageState();
}

class _MoneyEntriesPageState extends State<MoneyEntriesPage> {
  String month = monthKey(DateTime.now());
  bool get income => widget.kind == 'income';

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    return Loader<(MoneyMeta, Map<String, dynamic>, List<Map<String, dynamic>>, Map<String, dynamic>?)>(
      key: ValueKey('${widget.kind}-$month'),
      load: () async {
        final meta = await loadMeta(api);
        final list = (await api.get('/api/admin/money/${widget.kind}', query: {'month': month}) as Map).cast<String, dynamic>();
        final invoices = income
            ? [for (final r in ((await api.get('/api/admin/money/invoices', query: {'status': 'unpaid'}) as Map)['rows'] as List)) (r as Map).cast<String, dynamic>()]
            : <Map<String, dynamic>>[];
        final salaries = income ? null : (await api.get('/api/admin/money/salaries', query: {'month': month}) as Map).cast<String, dynamic>();
        return Cached((meta, list, invoices, salaries));
      },
      builder: (context, data, reload) {
        final (meta, d, invoices, salaries) = data;
        final totals = (d['totals'] as Map).cast<String, dynamic>();
        final value = (totals['value'] as Map).cast<String, dynamic>();
        final rows = [for (final r in d['rows'] as List) (r as Map).cast<String, dynamic>()];
        Future<void> openForm([Map<String, dynamic>? salaryFor]) async {
          final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => MoneyEntryForm(kind: widget.kind, meta: meta, month: month, salaryFor: salaryFor)));
          if (saved == true) await reload();
        }

        return Scaffold(
          backgroundColor: Colors.transparent,
          floatingActionButton: FloatingActionButton.extended(
            backgroundColor: brandAccent,
            icon: const Icon(Icons.add),
            label: Text(s.get(income ? 'mnNewIncome' : 'mnNewExpense')),
            onPressed: meta.rate == null ? null : () => openForm(),
          ),
          body: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 96), children: [
            MonthBar(month: month, onChanged: (v) => setState(() => month = v)),
            RateStrip(meta),
            MoneyTile(
              label: s.get(income ? 'mnIncome' : 'mnExpenses'),
              usd: value['USD'] as String?,
              syp: value['SYP'] as String?,
              note: '${s.get('mnReallyPaid')}: USD ${moneyText(totals['USD'] as String?)} · SYP ${moneyText(totals['SYP'] as String?)} · ${d['count']} ${s.get('mnEntries')}',
            ),
            if (rows.isEmpty) Padding(padding: const EdgeInsets.all(24), child: Text(s.get('mnNoEntries'), textAlign: TextAlign.center, style: const TextStyle(color: _muted))),
            for (final r in rows) _EntryCard(r: r, kind: widget.kind, meta: meta, onChanged: reload),
            if (income && invoices.isNotEmpty) ...[
              SectionTitle(s.get('mnInvoices')),
              for (final v in invoices)
                Card(
                  child: ListTile(
                    leading: const CircleAvatar(backgroundColor: brandSoft, child: Icon(Icons.receipt_long_outlined, color: brandBlue)),
                    title: Text('${v['number']} · ${v['child'] == '' ? v['payer_name'] : v['child']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                    subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(s.get('mnOpenAmount'), style: const TextStyle(fontSize: 12, color: _muted)),
                      TwoAmounts((v['open'] as Map)['usd'] as String?, (v['open'] as Map)['syp'] as String?, size: 13),
                    ]),
                    trailing: Pill(s.get(v['status'] == 'partial' ? 'mnPartlyPaid' : 'mnOpen'), foreground: const Color(0xFF8A5200), background: const Color(0xFFFDF1DD)),
                    onTap: () async {
                      final changed = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => InvoicePage(id: v['id'] as String, meta: meta)));
                      if (changed == true) await reload();
                    },
                  ),
                ),
            ],
            if (salaries != null) ...[
              SectionTitle('${s.get('mnSalariesOf')} ${monthTitle(s.code, month)}'),
              for (final p in [for (final x in salaries['rows'] as List) (x as Map).cast<String, dynamic>()])
                Card(
                  child: ListTile(
                    title: Text(p['name'] as String, style: const TextStyle(fontWeight: FontWeight.w700)),
                    subtitle: Text(p['salary'] == null ? (p['job_title'] as String? ?? '') : '${moneyText(p['salary'] as String?)} ${p['salary_currency']}'),
                    trailing: p['paid'] == true
                        ? Pill(s.get(p['automatic'] == true ? 'mnPaidAuto' : 'mnPaid'), foreground: _good, background: const Color(0xFFE4F4EA))
                        : (p['is_active'] == true && meta.rate != null
                            ? OutlinedButton(onPressed: () => openForm(p), child: Text(s.get('mnPaySalary')))
                            : Pill(s.get('mnNotPaid'), foreground: _bad, background: const Color(0xFFFCE9E6))),
                  ),
                ),
              Padding(padding: const EdgeInsets.all(6), child: Text(s.get('mnSalaryNote'), style: const TextStyle(fontSize: 12, color: _muted, height: 1.5))),
            ],
            if (meta.canExport)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.picture_as_pdf_outlined),
                  label: Text(s.get(income ? 'mnIncomePdf' : 'mnExpensesPdf')),
                  onPressed: () => openPrivateFile(context, api, '/api/admin/money/export/${widget.kind}.pdf', '${widget.kind}-$month.pdf', query: {'month': month}),
                ),
              ),
          ]),
        );
      },
    );
  }
}

class _EntryCard extends StatelessWidget {
  const _EntryCard({required this.r, required this.kind, required this.meta, required this.onChanged});
  final Map<String, dynamic> r;
  final String kind;
  final MoneyMeta meta;
  final Future<void> Function() onChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final income = kind == 'income';
    final who = [
      if (income) ...[r['payer_name'], r['child']] else ...[r['recipient'], r['employee']],
    ].whereType<String>().where((x) => x.isNotEmpty).join(' · ');
    final category = income ? r['category'] as String : (s.code == 'ar' ? r['category_ar'] : r['category_en']) as String;
    final voided = r['voided'] == true;
    return Card(
      child: InkWell(
        onTap: () => showModalBottomSheet(context: context, isScrollControlled: true, builder: (_) => _EntrySheet(r: r, kind: kind, meta: meta, onChanged: onChanged)),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                child: Text(r['description'] as String,
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15, decoration: voided ? TextDecoration.lineThrough : null, color: voided ? _muted : null)),
              ),
              Text(r['booked_on'] as String, textDirection: TextDirection.ltr, style: const TextStyle(fontSize: 12, color: _muted)),
            ]),
            const SizedBox(height: 4),
            Text([category, if (who.isNotEmpty) who].join(' · '), style: const TextStyle(fontSize: 12.5, color: _muted)),
            const SizedBox(height: 8),
            TwoAmounts(r['usd'] as String?, r['syp'] as String?),
            const SizedBox(height: 4),
            Text('${s.get('mnReallyPaid')}: ${moneyText(r['amount'] as String?)} ${r['currency']} · ${s.get('mnAtRate')} ${moneyText(r['rate'] as String?)}',
                style: const TextStyle(fontSize: 12, color: _muted)),
            Padding(padding: const EdgeInsets.only(top: 4), child: _stateTag(s, r)),
          ]),
        ),
      ),
    );
  }
}

/// The details of one entry: the amounts, the history, and (with the right) cancelling it.
class _EntrySheet extends StatelessWidget {
  const _EntrySheet({required this.r, required this.kind, required this.meta, required this.onChanged});
  final Map<String, dynamic> r;
  final String kind;
  final MoneyMeta meta;
  final Future<void> Function() onChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    final mayCancel = meta.canCorrect && r['voided'] != true && r['is_reversal'] != true && r['reversed'] != true;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(r['description'] as String, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          TwoAmounts(r['usd'] as String?, r['syp'] as String?, strong: true, size: 17),
          const SizedBox(height: 4),
          Text('${s.get('mnReallyPaid')}: ${moneyText(r['amount'] as String?)} ${r['currency']} · ${s.get('mnAtRate')} ${moneyText(r['rate'] as String?)}', style: const TextStyle(color: _muted)),
          if ((r['note'] as String? ?? '').isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text(r['note'] as String)),
          const Divider(height: 24),
          Text(s.get('mnHistory'), style: const TextStyle(fontWeight: FontWeight.w700)),
          FutureBuilder<dynamic>(
            future: api.get('/api/admin/money/history/${r['id']}'),
            builder: (context, snap) {
              if (!snap.hasData) return const Padding(padding: EdgeInsets.all(8), child: LinearProgressIndicator());
              final lines = [for (final x in snap.data as List) (x as Map).cast<String, dynamic>()];
              return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                for (final x in lines)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      '${(x['at'] as String? ?? '').replaceFirst('T', ' ').padRight(16).substring(0, 16)} · ${s.get('mnAction_${(x['action'] as String).replaceAll('.', '_')}')} · ${x['actor'] == 'auto' ? s.get('mnSystem') : x['actor']}${(x['reason'] as String? ?? '').isEmpty ? '' : ' — ${x['reason']}'}',
                      style: const TextStyle(fontSize: 13),
                    ),
                  ),
              ]);
            },
          ),
          if (mayCancel) ...[
            const SizedBox(height: 16),
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(foregroundColor: _bad, side: const BorderSide(color: _bad), minimumSize: const Size.fromHeight(48)),
              icon: const Icon(Icons.block),
              label: Text(s.get(r['month_closed'] == true ? 'mnReverse' : 'mnCancelEntry')),
              onPressed: () async {
                final reason = await askText(context, s.get('mnCancelReason'), maxLength: 300, maxLines: 2, confirm: 'mnCancelEntry');
                if (reason == null || !context.mounted) return;
                try {
                  await api.post('/api/admin/money/$kind/${r['id']}/void', {'reason': reason.trim()});
                  if (!context.mounted) return;
                  Navigator.pop(context);
                  toast(context, s.get('mnCancelledDone'));
                  await onChanged();
                } on ApiException catch (e) {
                  if (context.mounted) toast(context, problemText(context, e));
                }
              },
            ),
          ],
        ]),
      ),
    );
  }
}

// ---- the form of a new income or expense ----------------------------------------------------------------------------------------
class MoneyEntryForm extends StatefulWidget {
  const MoneyEntryForm({super.key, required this.kind, required this.meta, required this.month, this.salaryFor});
  final String kind;
  final MoneyMeta meta;
  final String month;
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
  String? _category;
  String _currency = 'USD';
  String? _link; // a child (income) or a person of the staff (salary)
  List<Map<String, dynamic>> _people = [];
  bool _busy = false;
  bool get income => widget.kind == 'income';

  @override
  void initState() {
    super.initState();
    _day = DateTime.parse(widget.meta.today);
    _rate.text = (widget.meta.rate?['syp_per_usd'] as String?) ?? '';
    final cats = income ? widget.meta.incomeCategories.where((c) => c['is_active'] == true).toList() : widget.meta.expenseCategories;
    _category = cats.isEmpty ? null : (income ? cats.first['id'] : cats.first['key']) as String;
    final p = widget.salaryFor;
    if (p != null) {
      _category = 'salaries';
      _link = p['employee_id'] as String;
      _who.text = p['name'] as String;
      if (p['salary'] != null) _amount.text = p['salary'] as String;
      _currency = (p['salary_currency'] as String?) ?? 'SYP';
    } else if (!income) {
      _category = 'food';
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
      if (mounted) setState(() => _people = [for (final x in list) (x as Map).cast<String, dynamic>()]);
    } catch (_) {}
  }

  Future<void> _pickDay() async {
    final picked = await showDatePicker(context: context, initialDate: _day, firstDate: DateTime(2020), lastDate: DateTime.parse(widget.meta.today));
    if (picked == null || !mounted) return;
    setState(() => _day = picked);
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
    if (_description.text.trim().length < 2 || _amount.text.trim().isEmpty || _category == null) {
      toast(context, s.get('mnFillIn'));
      return;
    }
    final salary = !income && _category == 'salaries';
    final body = <String, dynamic>{
      'booked_on': dayText(_day),
      'description': _description.text.trim(),
      'amount': _amount.text.trim(),
      'currency': _currency,
      'note': _note.text.trim(),
      if (widget.meta.canManage && _rate.text.trim().isNotEmpty) 'rate': _rate.text.trim(),
      if (income) ...{'category_id': _category, 'child_id': _link, 'payer_name': _who.text.trim()},
      if (!income) ...{'category': _category, 'recipient': _who.text.trim(), 'employee_id': salary ? _link : null, 'salary_month': salary ? widget.month : null},
    };
    setState(() => _busy = true);
    try {
      await api.post('/api/admin/money/${widget.kind}', body);
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
    final cats = income
        ? [for (final c in widget.meta.incomeCategories.where((c) => c['is_active'] == true)) DropdownMenuItem(value: c['id'] as String, child: Text(c['name'] as String))]
        : [for (final c in widget.meta.expenseCategories) DropdownMenuItem(value: c['key'] as String, child: Text((s.code == 'ar' ? c['ar'] : c['en']) as String))];
    final salary = !income && _category == 'salaries';
    return Scaffold(
      appBar: AppBar(title: Text(widget.salaryFor != null ? s.get('mnPaySalary') : s.get(income ? 'mnNewIncome' : 'mnNewExpense'))),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        if (_busy) const LinearProgressIndicator(),
        FormSection(
          title: s.get('mnWhat'),
          child: Column(children: [
            ListTile(contentPadding: EdgeInsets.zero, leading: const Icon(Icons.event), title: Text(s.get(income ? 'mnDate' : 'mnDatePaid')), trailing: Text(dayText(_day), textDirection: TextDirection.ltr), onTap: _pickDay),
            TextField(controller: _description, maxLength: 300, decoration: InputDecoration(labelText: s.get('mnReason'))),
            DropdownButtonFormField<String>(initialValue: _category, items: cats, decoration: InputDecoration(labelText: s.get('mnCategory')), onChanged: (v) => setState(() => _category = v)),
            const SizedBox(height: 12),
            if (income || salary)
              DropdownButtonFormField<String?>(
                initialValue: _people.any((p) => p['id'] == _link) ? _link : null,
                items: [
                  const DropdownMenuItem<String?>(value: null, child: Text('—')),
                  for (final p in _people) DropdownMenuItem<String?>(value: p['id'] as String, child: Text(p['name'] as String)),
                ],
                decoration: InputDecoration(labelText: s.get(income ? 'mnChildOptional' : 'mnStaffMember')),
                onChanged: (v) => setState(() => _link = v),
              ),
            if (salary) Padding(padding: const EdgeInsets.only(top: 8), child: Text('${s.get('mnSalaryFor')}: ${monthTitle(s.code, widget.month)}', style: const TextStyle(color: _muted))),
            TextField(controller: _who, maxLength: 120, decoration: InputDecoration(labelText: s.get(income ? 'mnPayerOptional' : 'mnRecipientOptional'))),
          ]),
        ),
        FormSection(
          title: s.get('mnAmountTitle'),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            TextField(controller: _amount, keyboardType: const TextInputType.numberWithOptions(decimal: true), textDirection: TextDirection.ltr, decoration: InputDecoration(labelText: s.get('mnAmount'))),
            const SizedBox(height: 12),
            SegmentedButton<String>(
              segments: const [ButtonSegment(value: 'USD', label: Text('USD')), ButtonSegment(value: 'SYP', label: Text('SYP'))],
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
            const SizedBox(height: 8),
            Text(_approx(), textDirection: TextDirection.ltr, style: const TextStyle(fontWeight: FontWeight.w700, color: brandBlue)),
          ]),
        ),
        FormSection(title: s.get('mnNote'), child: TextField(controller: _note, maxLength: 500, decoration: InputDecoration(labelText: s.get('mnNote')))),
        if (!income) Text(s.get('mnOnlyPaid'), style: const TextStyle(fontSize: 12, color: _muted)),
      ]),
      bottomNavigationBar: BottomActionBar(children: [
        Expanded(child: FilledButton(onPressed: _busy ? null : _save, child: Text(s.get('mnRecord')))),
      ]),
    );
  }
}

// ---- one invoice and its payment ----------------------------------------------------------------------------------------------
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
        body: Loader<Map<String, dynamic>>(
          load: () async => Cached((await api.get('/api/admin/money/invoices/${widget.id}') as Map).cast<String, dynamic>()),
          builder: (context, v, reload) {
            Map<String, dynamic> m(String k) => (v[k] as Map).cast<String, dynamic>();
            final open = v['status'] == 'open' || v['status'] == 'partial';
            return ListView(padding: const EdgeInsets.all(12), children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    Text('${v['number']} · ${v['child'] == '' ? v['payer_name'] : v['child']}', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800)),
                    Text('${v['issued_on']} · ${s.get('mnAtRate')} ${moneyText(v['rate'] as String?)}', style: const TextStyle(color: _muted)),
                    const Divider(height: 20),
                    for (final i in (v['items'] as List).cast<Map>()) ...[Text(i['description'] as String), TwoAmounts(i['usd'] as String?, i['syp'] as String?, size: 13), const SizedBox(height: 6)],
                    const Divider(height: 20),
                    Text(s.get('mnTotal'), style: const TextStyle(color: _muted)),
                    TwoAmounts(m('total')['usd'] as String?, m('total')['syp'] as String?, strong: true),
                    const SizedBox(height: 6),
                    Text(s.get('mnPaid'), style: const TextStyle(color: _muted)),
                    TwoAmounts(m('paid')['usd'] as String?, m('paid')['syp'] as String?),
                    const SizedBox(height: 6),
                    Text(s.get('mnOpenAmount'), style: const TextStyle(color: _muted)),
                    TwoAmounts(m('open')['usd'] as String?, m('open')['syp'] as String?, strong: true),
                  ]),
                ),
              ),
              OutlinedButton.icon(
                icon: const Icon(Icons.picture_as_pdf_outlined),
                label: Text(s.get('mnInvoicePdf')),
                onPressed: () => openPrivateFile(context, api, '/api/admin/money/invoices/${widget.id}.pdf', '${v['number']}.pdf'),
              ),
              if (open && widget.meta.rate != null)
                _PaymentForm(
                  invoiceId: widget.id,
                  meta: widget.meta,
                  payer: v['payer_name'] as String? ?? '',
                  onSaved: () async {
                    _changed = true;
                    await reload();
                  },
                ),
            ]);
          },
        ),
      ),
    );
  }
}

class _PaymentForm extends StatefulWidget {
  const _PaymentForm({required this.invoiceId, required this.meta, required this.payer, required this.onSaved});
  final String invoiceId;
  final MoneyMeta meta;
  final String payer;
  final Future<void> Function() onSaved;
  @override
  State<_PaymentForm> createState() => _PaymentFormState();
}

class _PaymentFormState extends State<_PaymentForm> {
  final _amount = TextEditingController();
  String _currency = 'USD';
  bool _busy = false;

  Future<void> _pay() async {
    if (_amount.text.trim().isEmpty) return;
    final s = S.of(context);
    final api = SessionScope.of(context).api;
    setState(() => _busy = true);
    try {
      await api.post('/api/admin/money/invoices/${widget.invoiceId}/payments',
          {'booked_on': widget.meta.today, 'amount': _amount.text.trim(), 'currency': _currency, 'payer_name': widget.payer});
      if (!mounted) return;
      toast(context, s.get('mnSaved'));
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
    return FormSection(
      title: s.get('mnRecordPayment'),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text(s.get('mnPaymentNote'), style: const TextStyle(fontSize: 12, color: _muted)),
        const SizedBox(height: 8),
        TextField(controller: _amount, keyboardType: const TextInputType.numberWithOptions(decimal: true), textDirection: TextDirection.ltr, decoration: InputDecoration(labelText: s.get('mnAmount'))),
        const SizedBox(height: 10),
        SegmentedButton<String>(
          segments: const [ButtonSegment(value: 'USD', label: Text('USD')), ButtonSegment(value: 'SYP', label: Text('SYP'))],
          selected: {_currency},
          onSelectionChanged: (v) => setState(() => _currency = v.first),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: _busy ? null : _pay,
          child: Text(s.get('mnRecordPayment')),
        ),
      ]),
    );
  }
}

// ---- for the management: the three pages behind one entry of its menu --------------------------------------------------------
class MoneyHub extends StatelessWidget {
  const MoneyHub({super.key});
  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return DefaultTabController(
      length: 3,
      child: Column(children: [
        Material(
          color: Colors.transparent,
          child: TabBar(tabs: [Tab(text: s.get('mnIncome')), Tab(text: s.get('mnExpenses')), Tab(text: s.get('mnSummary'))]),
        ),
        const Expanded(child: TabBarView(children: [MoneyEntriesPage(kind: 'income'), MoneyEntriesPage(kind: 'expenses'), MoneySummaryPage()])),
      ]),
    );
  }
}
