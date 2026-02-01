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

scripts.yaml
```yaml
fetch_rce_manual:
  alias: "Ręczne pobranie RCE"
  sequence:
    - service: appdaemon.call_service
      data:
        app_name: rce_prices_fetcher
        service_name: fetch_rce
```

secrets.yaml
```yaml
mariadb_user: homeassistant
mariadb_password: ****************
```

Lovelace — przycisk do manualnego pobrania
```yaml
type: button
tap_action:
  action: call-service
  service: fetch_rce_manual
name: Pobierz RCE teraz
icon: mdi:flash
show_state: false
```

