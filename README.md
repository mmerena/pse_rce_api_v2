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
  # możesz dodać własne parametry jeśli chcesz, np:
  # start_date_if_new: "2024-06-14"
  # db_host: core-mariadb
  # ... itd.
```
