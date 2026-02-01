Ustawienia -> Dodatki -> Sklep z dodatkami -> File editor
# -> Zainstaluj
# -> Konfiguracja

```yaml
dirsfirst: true
enforce_basepath: false
git: false
ignore_pattern:
  - __pycache__
  - .cloud
  - .storage
  - deps
ssh_keys: []
```

Ustawienia -> Dodatki -> Sklep z dodatkami -> MariaDB
 -> Zainstaluj
 -> Konfiguracja

```yaml
databases:
  - homeassistant
logins:
  - username: homeassistant
    password: ****************
  - username: grafana
    password: ****************
rights:
  - username: homeassistant
    database: homeassistant
  - username: grafana
    database: homeassistant
    privileges:
      - SELECT
```

Ustawienia -> Dodatki -> Sklep z dodatkami -> phpMyAdmin
 -> Zainstaluj

Ustawienia -> Dodatki -> Sklep z dodatkami -> AppDaemon
 -> Zainstaluj
 -> Konfiguracja

```yaml
system_packages: []
python_packages:
  - Requests
  - PyMySQL
init_commands: []
log_level: info
```

Struktura plików:
```text
/addon_configs/a0d7b954_appdaemon/
├── apps/
│   └── rce_prices_fetcher.py
├── apps.yaml
├── logs/
│   └── rce_prices_fetcher.log
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

