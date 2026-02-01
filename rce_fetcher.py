import hassapi as hass
import requests
import pymysql
from datetime import date, timedelta, datetime

class RcePricesFetcher(hass.Hass):
    def initialize(self):
        self.log("Inicjalizacja RCE Prices Fetcher")

        # Pobieramy wszystkie potrzebne wartości z konfiguracji (apps.yaml)
        self.db_host       = self.args.get("db_host", "core-mariadb")
        self.db_user       = self.args.get("db_user")
        self.db_password   = self.args.get("db_password")
        self.db_name       = self.args.get("db_name", "homeassistant")
        self.table_name    = self.args.get("table_name", "rce_prices")

        self.api_base_url  = self.args.get("api_base_url", "https://api.raporty.pse.pl/api/rce-pln")
        self.start_date_if_new = self.args.get("start_date_if_new", "2024-06-14")

        # Podstawowe sprawdzenie czy mamy hasło i użytkownika
        if not self.db_user or not self.db_password:
            self.log("Brak db_user lub db_password w konfiguracji → AppDaemon nie będzie działał", level="ERROR")
            return

        self.log(f"Konfiguracja załadowana → tabela: {self.table_name}, api: {self.api_base_url}")

        # Uruchamiamy codziennie o 18:00
        self.run_daily(self.fetch_and_store, "18:00:00")

        self.log("Harmonogram ustawiony – codzienne pobieranie o 18:00")


    def connect_to_db(self):
        try:
            conn = pymysql.connect(
                host=self.db_host,
                user=self.db_user,
                password=self.db_password,
                database=self.db_name,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
            return conn
        except Exception as e:
            self.log(f"Błąd połączenia z bazą: {e}", level="ERROR")
            return None


    def table_exists(self, cursor):
        try:
            cursor.execute(f"SHOW TABLES LIKE '{self.table_name}'")
            return cursor.fetchone() is not None
        except:
            return False


    def create_table(self, cursor):
        sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
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
        cursor.execute(sql)
        self.log(f"Tabela {self.table_name} utworzona lub już istnieje")


    def fetch_rce_data(self, date_str: str):
        url = f"{self.api_base_url}?$filter=business_date eq '{date_str}'"
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json().get("value", [])
            self.log(f"Pobrano {len(data)} rekordów dla {date_str}")
            return data
        except Exception as e:
            self.log(f"Błąd API dla {date_str}: {e}", level="ERROR")
            return []


    def insert_data(self, cursor, conn, data):
        inserted = 0
        for row in data:
            try:
                cursor.execute(
                    f"""
                    INSERT IGNORE INTO {self.table_name}
                    (dtime_utc, period_utc, dtime, period, rce_pln, business_date, publication_ts_utc, publication_ts)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row["dtime_utc"],
                        row["period_utc"],
                        row["dtime"],
                        row["period"],
                        row["rce_pln"],
                        row["business_date"],
                        row["publication_ts_utc"],
                        row["publication_ts"],
                    ),
                )
                inserted += cursor.rowcount
            except Exception as e:
                self.log(f"Błąd zapisu rekordu {row.get('dtime_utc','?')}: {e}", level="WARNING")
                continue

        if inserted > 0:
            conn.commit()
            self.log(f"Zapisano {inserted} nowych rekordów")
        else:
            self.log("Brak nowych rekordów do zapisania")


    def get_max_business_date(self, cursor):
        try:
            cursor.execute(f"SELECT MAX(business_date) FROM {self.table_name}")
            result = cursor.fetchone()
            return result["MAX(business_date)"] if result else None
        except:
            return None


    def fetch_and_store(self, kwargs):
        self.log("START – pobieranie cen RCE")

        conn = self.connect_to_db()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            if not self.table_exists(cursor):
                self.create_table(cursor)
                conn.commit()
                start_date_str = self.start_date_if_new
                self.log("Nowa tabela – pobieram od daty startowej")
            else:
                max_bd = self.get_max_business_date(cursor)
                if max_bd is None:
                    start_date_str = self.start_date_if_new
                    self.log("Tabela pusta – pobieram od daty startowej")
                else:
                    start_dt = datetime.strptime(str(max_bd), "%Y-%m-%d").date() - timedelta(days=3)
                    start_date_str = start_dt.strftime("%Y-%m-%d")
                    self.log(f"Pobieram od {start_date_str} (max w bazie = {max_bd})")

            tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

            current = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end = datetime.strptime(tomorrow_str, "%Y-%m-%d").date()
            dates = []
            while current <= end:
                dates.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)

            self.log(f"Planuję pobrać dane dla {len(dates)} dni")

            for i, dt_str in enumerate(dates, 1):
                self.log(f"[{i}/{len(dates)}] {dt_str}")
                data = self.fetch_rce_data(dt_str)
                if data:
                    self.insert_data(cursor, conn, data)

            self.log("Pobieranie i zapis zakończone")

        except Exception as e:
            self.log(f"Błąd krytyczny: {e}", level="ERROR")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
        finally:
            if "cursor" in locals() and cursor:
                cursor.close()
            if conn:
                conn.close()
