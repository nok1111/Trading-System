# Alvora Mobile

Flutter app for the Alvora Trading Platform.

## Getting Started

```bash
flutter pub get
flutter run
```

## Structure

```
lib/
├── main.dart              # Entry point + auth gate
├── api/
│   ├── api_client.dart    # HTTP client with JWT auth
│   ├── auth_api.dart      # Login/register/logout
│   └── broker_api.dart    # Balance, positions, prices
├── screens/
│   ├── login_screen.dart  # Login with username/password
│   ├── dashboard_screen.dart  # Balance + positions overview
│   ├── positions_screen.dart  # Full positions list
│   └── settings_screen.dart   # Logout, broker info
├── widgets/
│   └── position_card.dart # Position display card
├── models/
│   ├── position.dart      # Position model
│   └── user.dart          # User model
└── theme/
    └── app_theme.dart     # Dark theme config
```

## Features (Scaffold)

- Login screen (connects to `/api/auth/login`)
- Dashboard with balance and open positions
- Positions list screen
- Settings with logout
- Dark mode theme
- Bottom navigation (Dashboard, Positions, Settings)

## TODO (Future Iterations)

- Trading (buy/sell)
- Price charts (fl_chart)
- AI Agent
- Social trading
- Push notifications
