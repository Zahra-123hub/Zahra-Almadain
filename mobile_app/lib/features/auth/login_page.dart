import 'package:flutter/material.dart';

import '../../config/config.dart';
import '../../design/tokens.dart';
import '../../localization/strings.dart';
import '../../services/api.dart';
import '../../services/session.dart';
import '../../shared/ui.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _form = GlobalKey<FormState>();
  final _user = TextEditingController();
  final _pass = TextEditingController();
  bool _busy = false;
  bool _hide = true;
  String? _error;

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    final session = SessionScope.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await session.login(_user.text, _pass.text);
      if (!mounted) return;
      if (!session.hasMobileArea) {
        final message = S.of(context).get('websiteOnly');
        await session.logout();
        if (mounted) setState(() => _error = message);
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = problemText(context, e, login: true));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// The brand: logo plate, name and kindergarten name, on the blue ground.
  Widget _brand(S s, {required double logoHeight}) => Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(Rad.l), boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 20, offset: Offset(0, 8))]),
          child: Image.asset('assets/logo.png', height: logoHeight, fit: BoxFit.contain),
        ),
        const SizedBox(height: Gap.l + 4),
        Text(s.get('appName'), textAlign: TextAlign.center, style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w700, color: Colors.white, height: 1.2)),
        const SizedBox(height: 2),
        Text(s.get('appSubtitle'), textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, color: Color(0xFFC9DAEC), fontWeight: FontWeight.w500)),
      ]);

  Widget _languages(Session session, {required bool onDark}) => FittedBox(fit: BoxFit.scaleDown, child: _languagePill(session, onDark: onDark));

  Widget _languagePill(Session session, {required bool onDark}) => Container(
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(color: onDark ? Colors.white.withValues(alpha: 0.14) : const Color(0xFFE6EDF5), borderRadius: BorderRadius.circular(999)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          for (final code in const ['ar', 'de', 'en'])
            Semantics(
              button: true,
              selected: session.locale.languageCode == code,
              child: InkWell(
                borderRadius: BorderRadius.circular(999),
                onTap: () => session.setLocale(code),
                child: AnimatedContainer(
                  duration: Dur.fast,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: BoxDecoration(color: session.locale.languageCode == code ? Colors.white : Colors.transparent, borderRadius: BorderRadius.circular(999)),
                  child: Text(const {'ar': 'العربية', 'de': 'Deutsch', 'en': 'English'}[code]!,
                      style: TextStyle(fontSize: 14, fontWeight: session.locale.languageCode == code ? FontWeight.w700 : FontWeight.w500, color: session.locale.languageCode == code ? brandBlue : (onDark ? Colors.white : const Color(0xFF42536A)))),
                ),
              ),
            ),
        ]),
      );

  Widget _formCard(S s, Session session) => Card(
        elevation: 3,
        shadowColor: const Color(0x33000000),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Rad.l)),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(22, 26, 22, 22),
          child: Form(
            key: _form,
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text(s.get('welcomeBack'), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              Text(s.get('signInHint'), style: const TextStyle(color: Color(0xFF5B6878), height: 1.5)),
              const SizedBox(height: Gap.xl - 4),
              if (session.sessionEnded)
                Padding(padding: const EdgeInsets.only(bottom: Gap.m), child: Text(s.get('sessionEnded'), style: const TextStyle(color: Color(0xFFB26E0B), fontWeight: FontWeight.w600))),
              TextFormField(
                controller: _user,
                textInputAction: TextInputAction.next,
                autocorrect: false,
                autofillHints: const [AutofillHints.username],
                decoration: InputDecoration(labelText: s.get('username'), prefixIcon: const Icon(Icons.person_outline)),
                validator: (v) => (v == null || v.trim().isEmpty) ? s.get('required') : null,
              ),
              const SizedBox(height: Gap.l),
              TextFormField(
                controller: _pass,
                obscureText: _hide,
                autofillHints: const [AutofillHints.password],
                onFieldSubmitted: (_) => _submit(),
                decoration: InputDecoration(
                  labelText: s.get('password'),
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
                    tooltip: s.get(_hide ? 'showPassword' : 'hidePassword'),
                    icon: Icon(_hide ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                    onPressed: () => setState(() => _hide = !_hide),
                  ),
                ),
                validator: (v) => (v == null || v.isEmpty) ? s.get('required') : null,
              ),
              AnimatedSize(
                duration: Dur.normal,
                alignment: Alignment.topCenter,
                child: _error == null
                    ? const SizedBox(width: double.infinity)
                    : Container(
                        margin: const EdgeInsets.only(top: Gap.m + 2),
                        padding: const EdgeInsets.all(Gap.m),
                        decoration: BoxDecoration(color: const Color(0xFFFDECEC), borderRadius: BorderRadius.circular(Rad.s + 2)),
                        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          const Icon(Icons.error_outline, size: 19, color: Color(0xFFB3402F)),
                          const SizedBox(width: Gap.s),
                          Expanded(child: Text(_error!, style: const TextStyle(color: Color(0xFF8A2D1F), height: 1.4))),
                        ]),
                      ),
              ),
              const SizedBox(height: Gap.xl),
              FilledButton(
                onPressed: _busy ? null : _submit,
                child: _busy ? const SizedBox(height: 22, width: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white)) : Text(s.get('signIn')),
              ),
            ]),
          ),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final session = SessionScope.of(context);
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.wide;
    final version = Text('${s.get('version')} ${AppConfig.version}', style: const TextStyle(fontSize: 12, color: Color(0xFF6A7686)));

    if (wide) {
      // brand on the left, the form on the right
      return Scaffold(
        body: Row(children: [
          Expanded(
            flex: 5,
            child: Container(
              color: brandBlue,
              padding: const EdgeInsets.all(Gap.xxl),
              child: Column(children: [
                Align(alignment: AlignmentDirectional.topEnd, child: _languages(session, onDark: true)),
                Expanded(child: Center(child: _brand(s, logoHeight: 130))),
              ]),
            ),
          ),
          Expanded(
            flex: 6,
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(Gap.xxl),
                child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 440), child: Column(mainAxisSize: MainAxisSize.min, children: [_formCard(s, session), const SizedBox(height: Gap.l), version])),
              ),
            ),
          ),
        ]),
      );
    }

    return Scaffold(
      body: SingleChildScrollView(
        child: Column(children: [
          Container(
            width: double.infinity,
            padding: EdgeInsets.fromLTRB(Gap.xl, MediaQuery.paddingOf(context).top + Gap.xl + 4, Gap.xl, 64),
            decoration: const BoxDecoration(color: brandBlue, borderRadius: BorderRadius.vertical(bottom: Radius.circular(36))),
            child: _brand(s, logoHeight: 96),
          ),
          Transform.translate(
            offset: const Offset(0, -36),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: Gap.l + 4),
              child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 440), child: _formCard(s, session)),
            ),
          ),
          Transform.translate(offset: const Offset(0, -20), child: _languages(session, onDark: false)),
          const SizedBox(height: Gap.s),
          version,
          const SizedBox(height: Gap.xl),
        ]),
      ),
    );
  }
}
