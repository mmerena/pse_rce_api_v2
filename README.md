# RCE - Rynkowa cena energii elektrycznej (Home Assistant GREEN)

Tutaj znajdziesz dwa ciekawe skrypty w Python. Pierwszy pokazuje sposób pobierania danych ze źródeł zewnętrznych przez API (REST API), drugi jest przykładem logowania bieżących stanów lokalnych sensorów HA (HA loguje tylko zmiany stanów).
Oba skrypty zapisują dane do lokalnaej bazy danych, z której w dalszej kolejności można je wykorzystywać na potrzeby m.in. automatyzacji (Energy Management System).
W tym przykładzie wykorzystano dane o rynkowych cenach energii elektrycznej dostępne przez PSE RCE API v2 oraz dane z sensorów integracji Forecast.Solar. Tutaj są one źródłem dla wizualizacji w Grafana. Poniżej znajdują się wszystkie niezbędne integracje do zainstalowania w HA.

Ustawienia -> Dodatki -> Sklep z dodatkami -> File editor
 -> Zainstaluj
 -> Konfiguracja

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

secrets.yaml
```yaml
mariadb_user: homeassistant
mariadb_password: ****************
mariadb_url: mysql://homeassistant:****************@core-mariadb/homeassistant?charset=utf8mb4
```

configuration.yaml
```yaml
recorder:
  db_url: !secret mariadb_url
  purge_keep_days: 10
  auto_purge: true
```

Ustawienia -> Urządzenia oraz usługi -> Dodaj integrację -> Forecast.Solar

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
│   └── apps.yaml
│   └── rce_prices_fetcher.py
│   └── sensors_to_db.py
├── logs/
│   └── rce_prices_fetcher.log
│   └── sensors_to_db.log
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
    user: !secret mariadb_user
    password: !secret mariadb_password
    table: rce_prices

  logging:
    file: /config/logs/rce_prices_fetcher.log

  api:
    base_url: https://api.raporty.pse.pl/api/rce-pln
    start_date_if_new: "2024-06-14"

  schedule:
    hour:   14
    minute: 35

sensors_to_db:
  module: sensors_to_db
  class: SensorsToDB

  db:
    host: core-mariadb
    name: homeassistant
    user: !secret mariadb_user
    password: !secret mariadb_password
    tables:
      forecast_solar:
        - sensor.energy_production_tomorrow
        - sensor.energy_production_today
        - sensor.power_production_now
        - sensor.energy_next_hour
        - sensor.energy_current_hour

  logging:
    file: /config/logs/sensors_to_db.log
```

Ustawienia -> Dodatki -> Sklep z dodatkami -> phpMyAdmin
 -> Zainstaluj

```sql
DELIMITER $$

CREATE OR REPLACE FUNCTION tz_warsaw_to_utc(local_dt DATETIME)
RETURNS DATETIME
DETERMINISTIC
BEGIN
    DECLARE y INT;
    DECLARE dst_start DATETIME;
    DECLARE dst_end DATETIME;

    SET y = YEAR(local_dt);

    -- DST start: ostatnia niedziela marca, 02:00 lokalnie (CEST)
    SET dst_start = DATE_ADD(
        DATE_SUB(
            DATE_ADD(MAKEDATE(y,1), INTERVAL 3 MONTH) - INTERVAL 1 DAY,
            INTERVAL (DAYOFWEEK(DATE_ADD(MAKEDATE(y,1), INTERVAL 3 MONTH) - INTERVAL 1 DAY) - 1) DAY
        ),
        INTERVAL 2 HOUR
    );

    -- DST end: ostatnia niedziela października, 03:00 lokalnie (CET)
    SET dst_end = DATE_ADD(
        DATE_SUB(
            DATE_ADD(MAKEDATE(y,1), INTERVAL 10 MONTH) - INTERVAL 1 DAY,
            INTERVAL (DAYOFWEEK(DATE_ADD(MAKEDATE(y,1), INTERVAL 10 MONTH) - INTERVAL 1 DAY) - 1) DAY
        ),
        INTERVAL 3 HOUR
    );

    -- Jeśli data w okresie DST (CEST), odejmujemy 2 godziny
    IF local_dt >= dst_start AND local_dt < dst_end THEN
        RETURN local_dt - INTERVAL 2 HOUR;
    ELSE
        -- Pozostałe godziny: CET, odejmujemy 1 godzinę
        RETURN local_dt - INTERVAL 1 HOUR;
    END IF;
END$$

DELIMITER ;

-----------------------------------------------------------

DELIMITER $$

CREATE OR REPLACE FUNCTION tz_utc_to_warsaw(utc_dt DATETIME)
RETURNS DATETIME
DETERMINISTIC
BEGIN
    DECLARE y INT;
    DECLARE dst_start DATETIME;
    DECLARE dst_end DATETIME;

    SET y = YEAR(utc_dt);

    -- DST start: ostatnia niedziela marca 02:00 lokalnie → 01:00 UTC
    SET dst_start = DATE_ADD(
        DATE_SUB(
            DATE_ADD(MAKEDATE(y,1), INTERVAL 3 MONTH) - INTERVAL 1 DAY,
            INTERVAL (DAYOFWEEK(DATE_ADD(MAKEDATE(y,1), INTERVAL 3 MONTH) - INTERVAL 1 DAY) - 1) DAY
        ),
        INTERVAL 1 HOUR
    );

    -- DST end: ostatnia niedziela października 03:00 lokalnie → 02:00 UTC
    SET dst_end = DATE_ADD(
        DATE_SUB(
            DATE_ADD(MAKEDATE(y,1), INTERVAL 10 MONTH) - INTERVAL 1 DAY,
            INTERVAL (DAYOFWEEK(DATE_ADD(MAKEDATE(y,1), INTERVAL 10 MONTH) - INTERVAL 1 DAY) - 1) DAY
        ),
        INTERVAL 2 HOUR
    );

    -- Jeśli UTC w okresie DST, dodajemy 2 godziny
    IF utc_dt >= dst_start AND utc_dt < dst_end THEN
        RETURN utc_dt + INTERVAL 2 HOUR;
    ELSE
        -- Pozostałe godziny: CET, dodajemy 1 godzinę
        RETURN utc_dt + INTERVAL 1 HOUR;
    END IF;
END$$

DELIMITER ;

-- ---------------------------------------------------------
--
-- TAURON G13
--
-- Taryfa G13 – taryfa przedpołudniowa (średnia cena) w godzinach 7:00 – 13:00, taryfa popołudniowa (najwyższa cena)
-- latem w godzinach 19:00 – 22:00, zimą w godzinach 16:00 – 21:00, pozostałe godziny (najniższa cena)
-- latem 13:00 – 19:00 oraz 22:00 – 7:00, zimą 13:00 – 16:00 oraz 21:00 – 7:00, a także weekendy.
--

CREATE OR REPLACE VIEW tauron_G13 AS
SELECT * FROM (

WITH RECURSIVE dates AS (
    SELECT DATE_SUB(CURDATE(), INTERVAL 180 DAY) AS `date`
    UNION ALL
    SELECT DATE_ADD(`date`, INTERVAL 1 DAY)
    FROM dates
    WHERE `date` < DATE_ADD(CURDATE(), INTERVAL 1 DAY)
)

-- 7:00 i 13:00 (czasu polskiego)
SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL 7 HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL 7 HOUR) AS time,
    '07:00' AS `title`,
    'T3 -> T1' AS `text`
FROM dates
WHERE DAYOFWEEK(`date`) BETWEEN 2 AND 6

UNION ALL

SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL 13 HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL 13 HOUR) AS time,
    '13:00' AS `title`,
    'T1 -> T3' AS `text`
FROM dates
WHERE DAYOFWEEK(`date`) BETWEEN 2 AND 6

UNION ALL

-- 19:00 (lato) / 16:00 (zima)
SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL IF(MONTH(`date`) BETWEEN 4 AND 9, 19, 16) HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL IF(MONTH(`date`) BETWEEN 4 AND 9, 19, 16) HOUR) AS time,
    CONCAT(LPAD(IF(MONTH(`date`) BETWEEN 4 AND 9, 19, 16), 2, '0'), ':00') AS `title`,
    'T3 -> T2' AS `text`
FROM dates
WHERE DAYOFWEEK(`date`) BETWEEN 2 AND 6

UNION ALL

-- 22:00 (lato) / 21:00 (zima)
SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL IF(MONTH(`date`) BETWEEN 4 AND 9, 22, 21) HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL IF(MONTH(`date`) BETWEEN 4 AND 9, 22, 21) HOUR) AS time,
    CONCAT(LPAD(IF(MONTH(`date`) BETWEEN 4 AND 9, 22, 21), 2, '0'), ':00') AS `title`,
    'T2 -> T3' AS `text`
FROM dates
WHERE DAYOFWEEK(`date`) BETWEEN 2 AND 6

) g13
ORDER BY 1 DESC;

-- ---------------------------------------------------------
--
-- TAURON G12w
--
-- Taryfa G12w – tańsza energia elektryczna w ciągu dnia w godzinach 13:00 – 15:00 oraz 22:00 – 6:00
-- oraz w weekendy i w dniach ustawowo wolnych od pracy.
--

CREATE OR REPLACE VIEW tauron_G12w AS
SELECT * FROM (

WITH RECURSIVE dates AS (
    SELECT DATE_SUB(CURDATE(), INTERVAL 180 DAY) AS `date`
    UNION ALL
    SELECT DATE_ADD(`date`, INTERVAL 1 DAY)
    FROM dates
    WHERE `date` < DATE_ADD(CURDATE(), INTERVAL 1 DAY)
)

-- 6:00, 13:00, 15:00, 22:00 (czasu polskiego)
SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL 6 HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL 6 HOUR) AS time,
    '06:00' AS `title`,
    'T2 -> T1' AS `text`
FROM dates
WHERE DAYOFWEEK(`date`) BETWEEN 2 AND 6

UNION ALL

SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL 13 HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL 13 HOUR) AS time,
    '13:00' AS `title`,
    'T1 -> T2' AS `text`
FROM dates
WHERE DAYOFWEEK(`date`) BETWEEN 2 AND 6

UNION ALL

SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL 15 HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL 15 HOUR) AS time,
    '15:00' AS `title`,
    'T2 -> T1' AS `text`
FROM dates
WHERE DAYOFWEEK(`date`) BETWEEN 2 AND 6

UNION ALL

SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL 22 HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL 22 HOUR) AS time,
    '22:00' AS `title`,
    'T1 -> T2' AS `text`
FROM dates
WHERE DAYOFWEEK(`date`) BETWEEN 2 AND 6

) g12w
ORDER BY 1 DESC;

-- ---------------------------------------------------------
-- TAUROG G12
--
-- Taryfa G12 – tańsza energia elektryczna w ciągu dnia w godzinach 13:00 – 15:00 oraz 22:00 – 6:00.
--

CREATE OR REPLACE VIEW tauron_G12 AS
SELECT * FROM (

WITH RECURSIVE dates AS (
    SELECT DATE_SUB(CURDATE(), INTERVAL 180 DAY) AS `date`
    UNION ALL
    SELECT DATE_ADD(`date`, INTERVAL 1 DAY)
    FROM dates
    WHERE `date` < DATE_ADD(CURDATE(), INTERVAL 1 DAY)
)

-- 6:00, 13:00, 15:00, 22:00 (czasu polskiego)
SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL 6 HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL 6 HOUR) AS time,
    '06:00' AS `title`,
    'T2 -> T1' AS `text`
FROM dates

UNION ALL

SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL 13 HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL 13 HOUR) AS time,
    '13:00' AS `title`,
    'T1 -> T2' AS `text`
FROM dates

UNION ALL

SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL 15 HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL 15 HOUR) AS time,
    '15:00' AS `title`,
    'T2 -> T1' AS `text`
FROM dates

UNION ALL

SELECT 
    UNIX_TIMESTAMP(tz_warsaw_to_utc(`date` + INTERVAL 22 HOUR)) AS time_utc,
    UNIX_TIMESTAMP(`date` + INTERVAL 22 HOUR) AS time,
    '22:00' AS `title`,
    'T1 -> T2' AS `text`
FROM dates

) g12
ORDER BY 1 DESC;
```

Ustawienia -> Dodatki -> Sklep z dodatkami -> Grafana -> Zainstaluj

Data Sources -> Add data source:

```text
 MySQL [ Host URL: core-mariadb, Database name: homeassistant, Username: grafana, Password: **************** ]
```

Dashboards -> Add visualization: 

RCE:
```sql
SELECT
    DATE_SUB(`dtime_utc`, INTERVAL 15 MINUTE) AS time,
    `rce_pln` AS RCE
FROM `rce_prices`;
```
energy_production_tomorrow:
```sql
SELECT
    DATE_ADD(`dtime_utc`, INTERVAL 1 DAY) AS time,
    100 * CAST(`entity_value` AS DECIMAL(10,4)) AS energy_production_tomorrow
FROM `forecast_solar`
INNER JOIN `states_meta` ON `forecast_solar`.`metadata_id` = `states_meta`.`metadata_id` AND `states_meta`.`entity_id` = 'sensor.energy_production_tomorrow';
```
energy_production_today:
```sql
SELECT
    `dtime_utc` AS time,
    100 * CAST(`entity_value` AS DECIMAL(10,4)) AS energy_production_today
FROM `forecast_solar`
INNER JOIN `states_meta` ON `forecast_solar`.`metadata_id` = `states_meta`.`metadata_id` AND `states_meta`.`entity_id` = 'sensor.energy_production_today';
```
power_production_now:
```sql
SELECT 
    `dtime_utc` AS time,
    CAST(`entity_value` AS DECIMAL(10,4)) AS power_production_now
FROM `forecast_solar`
INNER JOIN `states_meta` ON `forecast_solar`.`metadata_id` = `states_meta`.`metadata_id` AND `states_meta`.`entity_id` = 'sensor.power_production_now';
```
energy_next_hour:
```sql
SELECT
    DATE_ADD(`dtime_utc`, INTERVAL 1 HOUR) AS time,
    1000 * CAST(`entity_value` AS DECIMAL(10,4)) AS energy_next_hour
FROM `forecast_solar`
INNER JOIN `states_meta` ON `forecast_solar`.`metadata_id` = `states_meta`.`metadata_id` AND `states_meta`.`entity_id` = 'sensor.energy_next_hour';
```
energy_current_hour:
```sql
SELECT
    `dtime_utc` AS time,
    1000 * CAST(`entity_value` AS DECIMAL(10,4)) AS energy_current_hour
FROM `forecast_solar`
INNER JOIN `states_meta` ON `forecast_solar`.`metadata_id` = `states_meta`.`metadata_id` AND `states_meta`.`entity_id` = 'sensor.energy_current_hour';
```
