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
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _form,
                child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  ClipOval(child: Image.asset('assets/logo.png', width: 96, height: 96, fit: BoxFit.cover)),
                  const SizedBox(height: 16),
                  Text(s.get('appName'), textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold, color: brandBlue)),
                  Text(s.get('appSubtitle'), textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade700)),
                  const SizedBox(height: 8),
                  Text(s.get('signInHint'), textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade700)),
                  const SizedBox(height: 24),
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
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _pass,
                    obscureText: _hide,
                    autofillHints: const [AutofillHints.password],
                    onFieldSubmitted: (_) => _submit(),
                    decoration: InputDecoration(
                      labelText: s.get('password'),
                      prefixIcon: const Icon(Icons.lock_outline),
                      suffixIcon: IconButton(icon: Icon(_hide ? Icons.visibility : Icons.visibility_off), onPressed: () => setState(() => _hide = !_hide)),
                    ),
                    validator: (v) => (v == null || v.isEmpty) ? s.get('required') : null,
                  ),
                  if (_error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.red))),
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: _busy ? null : _submit,
                    child: _busy ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : Text(s.get('signIn')),
                  ),
                  const SizedBox(height: 16),
                  Wrap(alignment: WrapAlignment.center, children: [
                    for (final code in const ['ar', 'de', 'en'])
                      TextButton(
                        onPressed: () => session.setLocale(code),
                        child: Text(const {'ar': 'العربية', 'de': 'Deutsch', 'en': 'English'}[code]!,
                            style: TextStyle(fontWeight: session.locale.languageCode == code ? FontWeight.bold : FontWeight.normal)),
                      ),
                  ]),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
