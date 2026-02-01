Struktura plików (w /config/appdaemon/)
```text
appdaemon/
├── apps/
│   ├── __init__.py               (może być pusty)
│   ├── rce_fetcher.py
│   └── apps.yaml
└── appdaemon.yaml                 (już pewnie masz)
```

apps.yaml
```yaml
rce_prices_fetcher:
  module: rce_fetcher
  class: RcePricesFetcher

  # --- Konfiguracja bazy danych ---
  db_host: core-mariadb
  db_user: !secret db_user
  db_password: !secret db_password
  db_name: homeassistant
  table_name: rce_prices

  # --- Konfiguracja API ---
  api_base_url: https://api.raporty.pse.pl/api/rce-pln
  start_date_if_new: 2024-06-14

  # --- Inne ustawienia (opcjonalne, możesz dodać / zmienić) ---
  # fetch_back_days_on_full_sync: 10
  # retry_count: 3
  # request_timeout: 15
```
