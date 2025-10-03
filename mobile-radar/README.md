Mobile Radar – Auth MVP (Phone + OTP)

Overview
- Flutter app skeleton focusing on mobile auth via phone + OTP.
- Matches Django template palette (primary #417690, secondary #6c757d, danger #dc3545).
- Uses existing backend endpoints:
  - POST /api/auth/otp/request/ → { status, dev_otp }
  - POST /api/auth/otp/verify/ → { token, user }

Run Locally
1) Ensure backend runs on http://127.0.0.1:8000
2) Flutter setup (3.19+ recommended)
3) From mobile-radar/, run:
   - flutter pub get
   - Android emulator: flutter run -d emulator --dart-define=API_BASE_URL=http://94.158.51.9:9998/api/
   - iOS simulator: flutter run -d ios --dart-define=API_BASE_URL=http://94.158.51.9:9998/api/

Env
- API base URL is passed via --dart-define API_BASE_URL and defaults to http://10.0.2.2:8000/api/ for Android emulator.

Flow
1) Enter phone, tap “Send Code” → calls /auth/otp/request/
2) Enter OTP (dev code is 99999) → calls /auth/otp/verify/
3) Token saved (Authorization: Token <token>) for subsequent API calls.

Next
- Add session screen + logout.
- Hook home screen to radars endpoints.
- Add basic form validation and error surfaces.
