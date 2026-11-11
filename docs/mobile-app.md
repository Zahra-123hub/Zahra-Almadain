# Mobile app "Zahra Portal" / «بوابة زهرة» (Android and iOS)

Name on the phone: `بوابة زهرة` (Arabic) / `Zahra Portal` (other languages), set in `android/app/src/main/res/values*/strings.xml` and `ios/Runner/Info.plist`. Launcher icon: the kindergarten logo (`assets/icon.png`, adaptive foreground `assets/icon_foreground.png`); recreate with `dart run flutter_launcher_icons`.

Flutter app in `mobile_app/`. It uses the existing FastAPI backend and the same accounts; there is no second database.

## What it does
- **Parents**: home, my children (reports per child, search by day), reports, posts and notices (files open through the signed-in API), notifications, profile (language, password, sign-out).
- **Teachers**: home with counters, children, reports (draft, to management, straight to parents; camera / gallery / file attachments), posts (general or private to one child), teaching material (storage meter), notifications, profile.
- Accounts with both roles switch the area in the profile. Management / admin / accounting accounts are told to use the website.
- Arabic (default, RTL), German, English. All texts are in `lib/localization/strings.dart`.

## Backend parts used
Sign-in `/api/platform/auth/login` (Bearer token), `/auth/me`, `/auth/logout`, `/auth/change-password`, `/auth/language`, `/children`, `/children/{id}/reports`, `/parent/posts` (+files), `/teacher/children|reports|posts|content|storage`, `/notifications`, `/announcements`.
New (migration `0025_device_tokens`): `GET /api/app/version?version=x` (public; `update_required`, `update_available`, store links), `POST /api/platform/devices`, `POST /api/platform/devices/remove` (push token of a phone, bound to the signed-in account).
Environment of the server (all optional): `APP_LATEST_VERSION`, `APP_MIN_VERSION`, `APP_ANDROID_URL`, `APP_IOS_URL`, `APP_RELEASED`. The page `/app/` shows a store button only when its link is set (https only).

## Security
- Token in Android Keystore / iOS Keychain (`flutter_secure_storage`), no password is stored. A 401 ends the session.
- Rights are checked by the server on every call; the app only hides what is not meant for the role.
- Lists are kept for bad connections per account; removed at sign-out. Report texts typed by a teacher are kept as local drafts until sent.
- Files are fetched with the token into a temporary folder; there are no public links.

## Not done yet (needs accounts / keys from the kindergarten)
- **Push messages**: needs a Firebase project (`google-services.json`, `GoogleService-Info.plist`), an APNs key and a service-account key on Render. The token table and endpoints are ready.
- **Release builds**: Android needs the Android SDK and a signing key; iOS needs a Mac, an Apple developer account and signing.

## Build
```
cd mobile_app
flutter pub get
flutter analyze && flutter test
flutter build apk --release --dart-define=API_BASE=https://zahra-123hub-almadain-api.onrender.com
```
