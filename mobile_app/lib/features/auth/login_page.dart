import 'package:flutter/material.dart';

import '../../localization/strings.dart';
import '../../services/api.dart';
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

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final session = SessionScope.of(context);
    return Scaffold(
      body: SingleChildScrollView(
        child: Column(children: [
          // blue header with the logo
          Container(
            width: double.infinity,
            padding: EdgeInsets.fromLTRB(24, MediaQuery.of(context).padding.top + 36, 24, 56),
            decoration: const BoxDecoration(
              gradient: LinearGradient(colors: [brandBlue, brandDeep], begin: Alignment.topRight, end: Alignment.bottomLeft),
              borderRadius: BorderRadius.only(bottomLeft: Radius.circular(36), bottomRight: Radius.circular(36)),
            ),
            child: Column(children: [
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(24), boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 20, offset: Offset(0, 8))]),
                child: Image.asset('assets/logo.png', height: 110, fit: BoxFit.contain),
              ),
              const SizedBox(height: 20),
              Text(s.get('appName'), textAlign: TextAlign.center, style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w700, color: Colors.white)),
              const SizedBox(height: 2),
              Text(s.get('appSubtitle'), textAlign: TextAlign.center, style: const TextStyle(fontSize: 16, color: Color(0xDDFFFFFF))),
            ]),
          ),
          // the form, pulled up over the header
          Transform.translate(
            offset: const Offset(0, -28),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Card(
                  elevation: 3,
                  shadowColor: const Color(0x33000000),
                  child: Padding(
                    padding: const EdgeInsets.all(22),
                    child: Form(
                      key: _form,
                      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                        Text(s.get('signInHint'), textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade700, height: 1.5)),
                        const SizedBox(height: 20),
                        if (session.sessionEnded)
                          Padding(padding: const EdgeInsets.only(bottom: 12), child: Text(s.get('sessionEnded'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.orange))),
                        TextFormField(
                          controller: _user,
                          textInputAction: TextInputAction.next,
                          autocorrect: false,
                          autofillHints: const [AutofillHints.username],
                          decoration: InputDecoration(labelText: s.get('username'), prefixIcon: const Icon(Icons.person_outline)),
                          validator: (v) => (v == null || v.trim().isEmpty) ? s.get('required') : null,
                        ),
                        const SizedBox(height: 14),
                        TextFormField(
                          controller: _pass,
                          obscureText: _hide,
                          autofillHints: const [AutofillHints.password],
                          onFieldSubmitted: (_) => _submit(),
                          decoration: InputDecoration(
                            labelText: s.get('password'),
                            prefixIcon: const Icon(Icons.lock_outline),
                            suffixIcon: IconButton(icon: Icon(_hide ? Icons.visibility_outlined : Icons.visibility_off_outlined), onPressed: () => setState(() => _hide = !_hide)),
                          ),
                          validator: (v) => (v == null || v.isEmpty) ? s.get('required') : null,
                        ),
                        if (_error != null)
                          Container(
                            margin: const EdgeInsets.only(top: 14),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(color: const Color(0xFFFDECEC), borderRadius: BorderRadius.circular(12)),
                            child: Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFFB3261E))),
                          ),
                        const SizedBox(height: 22),
                        FilledButton(
                          onPressed: _busy ? null : _submit,
                          child: _busy ? const SizedBox(height: 22, width: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white)) : Text(s.get('signIn')),
                        ),
                      ]),
                    ),
                  ),
                ),
              ),
            ),
          ),
          Wrap(alignment: WrapAlignment.center, children: [
            for (final code in const ['ar', 'de', 'en'])
              TextButton(
                onPressed: () => session.setLocale(code),
                child: Text(const {'ar': 'العربية', 'de': 'Deutsch', 'en': 'English'}[code]!,
                    style: TextStyle(fontWeight: session.locale.languageCode == code ? FontWeight.w700 : FontWeight.w500, color: session.locale.languageCode == code ? brandBlue : Colors.grey.shade600)),
              ),
          ]),
          const SizedBox(height: 16),
        ]),
      ),
    );
  }
}
