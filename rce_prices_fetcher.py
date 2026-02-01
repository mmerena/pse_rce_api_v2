import appdaemon.plugins.hass.hassapi as hass
import logging
import os
from datetime import date, timedelta, datetime, time

import requests
import pymysql
from pymysql.err import ProgrammingError


class RCEPricesFetcher(hass.Hass):

    def initialize(self):
        # --- konfiguracja ---
        self.db_cfg = self.args.get("db", {})
        self.api_cfg = self.args.get("api", {})
        self.table = self.db_cfg.get("table", "rce_prices")

        # --- logger UTF-8 ---
        default_logfile = "/config/appdaemon/logs/rce_fetch_utf8.log"
        self.logger = self._setup_utf8_logger(self.args.get("logging", {}).get("file", default_logfile))
        self.logger.info("=== RCEPricesFetcher uruchomiony ===")
        self.logger.info("=== Test UTF-8: ąćęłńóśźż ===")

        # --- harmonogram dzienny ---
        schedule_cfg = self.args.get("schedule", {})
        run_hour = schedule_cfg.get("hour", 14)
        run_minute = schedule_cfg.get("minute", 35)
        run_time = time(hour=run_hour, minute=run_minute)
        self.run_daily(self.run_job, run_time)
        self.logger.info(f"Harmonogram dzienny ustawiony: {run_hour:02d}:{run_minute:02d}")

        # --- manualny trigger ---
        self.register_service("appdaemon/fetch_rce", self.run_job)
        self.logger.info("Manualny trigger 'appdaemon/fetch_rce' zarejestrowany")

    # ---------------------------------------------------------------------

    def _setup_utf8_logger(self, logfile):
        logger = logging.getLogger("rce_prices_fetcher")
        logger.setLevel(logging.INFO)

        # Tworzymy katalog jeśli nie istnieje
        log_dir = os.path.dirname(logfile)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        if not logger.handlers:
            handler = logging.FileHandler(logfile, encoding="utf-8")
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    # ---------------------------------------------------------------------

    def _connect_db(self):
        return pymysql.connect(
            host=self.db_cfg.get("host", "core-mariadb"),
            user=self.db_cfg.get("user", "homeassistant"),
            password=self.db_cfg.get("password", ""),
            db=self.db_cfg.get("name", "homeassistant"),
            charset="utf8mb4",
            autocommit=False,
        )

    # ---------------------------------------------------------------------

    def _table_exists(self, cursor):
        try:
            cursor.execute(f"SHOW TABLES LIKE '{self.table}'")
            return cursor.fetchone() is not None
        except ProgrammingError:
            return False

    # ---------------------------------------------------------------------

    def _create_table(self, cursor):
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                dtime_utc DATETIME PRIMARY KEY,
                period_utc VARCHAR(20),
                dtime DATETIME,
                period VARCHAR(20),
                rce_pln FLOAT,
                business_date DATE,
                publication_ts_utc DATETIME,
                publication_ts DATETIME
            )
            """
        )
        self.logger.info(f"Utworzono tabelę {self.table}")

    # ---------------------------------------------------------------------

    def _fetch_rce(self, date_str):
        url = (
            f"{self.api_cfg.get('base_url', '')}"
            f"?%24filter=business_date%20eq%20%27{date_str}%27"
        )

        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            data = r.json().get("value", [])
            self.logger.info(f"Pobrano {len(data)} rekordów dla {date_str}")
            return data
        except Exception as e:
            self.logger.error(f"Błąd API dla {date_str}: {e}")
            return []

    # ---------------------------------------------------------------------

    def _insert_data(self, cursor, data):
        inserted = 0
        for item in data:
            try:
                cursor.execute(
                    f"""
                    INSERT IGNORE INTO {self.table}
                    (dtime_utc, period_utc, dtime, period, rce_pln,
                     business_date, publication_ts_utc, publication_ts)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        item.get("dtime_utc"),
                        item.get("period_utc"),
                        item.get("dtime"),
                        item.get("period"),
                        item.get("rce_pln"),
                        item.get("business_date"),
                        item.get("publication_ts_utc"),
                        item.get("publication_ts"),
                    ),
                )
                inserted += cursor.rowcount
            except Exception as e:
                self.logger.error(f"Błąd zapisu rekordu: {e} | {item}")

        self.connection.commit()
        self.logger.info(f"Zapisano {inserted} nowych rekordów")

    # ---------------------------------------------------------------------

    def _date_range(self, start, end):
        cur = start
        while cur <= end:
            yield cur.strftime("%Y-%m-%d")
            cur += timedelta(days=1)

    # ---------------------------------------------------------------------

    def run_job(self, kwargs=None):
        self.connection = None
        cursor = None

        try:
            self.connection = self._connect_db()
            cursor = self.connection.cursor()

            tomorrow = date.today() + timedelta(days=1)

            if not self._table_exists(cursor):
                self._create_table(cursor)
                self.connection.commit()
                start = datetime.strptime(
                    self.api_cfg.get("start_date_if_new", "2024-06-14"), "%Y-%m-%d"
                ).date()
                self.logger.info(f"Nowa tabela – pobieram od {start} do {tomorrow}")
            else:
                cursor.execute(f"SELECT MAX(business_date) FROM {self.table}")
                max_bd = cursor.fetchone()[0]
                if max_bd:
                    start = max_bd - timedelta(days=3)
                else:
                    start = datetime.strptime(
                        self.api_cfg.get("start_date_if_new", "2024-06-14"), "%Y-%m-%d"
                    ).date()

                self.logger.info(f"Tabela istnieje – pobieram od {start} do {tomorrow}")

            for i, d in enumerate(self._date_range(start, tomorrow), 1):
                self.logger.info(f"[{i}] Pobieranie {d}")
                data = self._fetch_rce(d)
                if data:
                    self._insert_data(cursor, data)
                else:
                    self.logger.info(f"Brak danych dla {d}")

            self.logger.info("=== Pobieranie zakończone sukcesem ===")

        except Exception as e:
            self.logger.error(f"Błąd krytyczny: {type(e).__name__}: {e}")
            if self.connection:
                self.connection.rollback()

        finally:
            if cursor:
                cursor.close()
            if self.connection:
                self.connection.close()
            self.logger.info("=== Aplikacja zakończyła działanie ===")
