Struktura plików:
```text
/addon_configs/a0d7b954_appdaemon/
├── apps/
│   └── rce_prices_fetcher.py
├── apps.yaml
├── logs/
│   └── rce_fetch_utf8.log
```

apps.yaml
```yaml
---
rce_prices_fetcher:
  module: rce_prices_fetcher
  class: RCEPricesFetcher

  db:
    host: core-mariadb
    name: homeassistant
    table: rce_prices
    user: !secret mariadb_user
    password: !secret mariadb_password

  api:
    base_url: https://api.raporty.pse.pl/api/rce-pln
    start_date_if_new: "2024-06-14"

  logging:
    file: /config/logs/rce_prices_fetcher.log

  schedule:
    hour: 14
    minute: 35
```

secrets.yaml
```yaml
mariadb_user: homeassistant
mariadb_password: ****************
```

