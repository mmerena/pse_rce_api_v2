import appdaemon.plugins.hass.hassapi as hass
import logging
import os
from datetime import datetime

import pymysql
from pymysql.err import OperationalError

class SensorsToDB(hass.Hass):

    def initialize(self):
        # --- konfiguracja ---
        self.db_cfg = self.args.get("db", {})
        self.groups = self.args.get("groups", {})

        # --- automatyczna nazwa logu wg nazwy pliku ---
        log_dir = "/config/logs"
        base_name = os.path.splitext(os.path.basename(__file__))[0]
        default_logfile = os.path.join(log_dir, f"{base_name}.log")
        self.logger = self._setup_utf8_logger(self.args.get("logging", {}).get("file", default_logfile))

        # --- sprawdzenie konfiguracji bazy i sensorow ---
        if not self.db_cfg or not self.groups:
            self.logger.error("Brak konfiguracji DB lub grup sensorów!")
            self.run_in(run_on_quarter, 600)
            return

        self.logger.info("=== Aplikacja SensorsToDB uruchomiona ===")

        def run_on_quarter(kwargs=None):
            now = datetime.now()

            # Jeśli nie jesteśmy dokładnie na kwadransie → czekamy do najbliższego
            if now.minute % 15 != 0 or now.second >= 5:
                minutes_to_next = 15 - (now.minute % 15)
                if minutes_to_next == 15:
                    minutes_to_next = 0
                seconds_to_wait = minutes_to_next * 60 - now.second
                if seconds_to_wait <= 0:
                    seconds_to_wait += 900

                self.logger.info(f"Oczekiwanie {seconds_to_wait}s na uruchomienie...")
                self.run_in(run_on_quarter, seconds_to_wait)
                return

            # Jesteśmy na kwadransie → wykonujemy zapis
            self.save_all_sensors(kwargs)

            # Planujemy następne sprawdzenie za 10 minut
            self.run_in(run_on_quarter, 600)

        # Uruchamiamy pętlę
        run_on_quarter()

    def _setup_utf8_logger(self, logfile):
        logger = logging.getLogger("sensors_to_db")
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

    def save_all_sensors(self, kwargs):
        now_local = datetime.now()
        now_utc = datetime.utcnow()

        # Zaokrąglamy do pełnego kwadransa (00,15,30,45)
        minute = (now_local.minute // 15) * 15
        dtime_local = now_local.replace(minute=minute, second=0, microsecond=0)
        dtime_utc   = now_utc.replace(minute=minute, second=0, microsecond=0)

        connection = None
        try:
            connection = pymysql.connect(
                host=self.db_cfg.get("host", "core-mariadb"),
                user=self.db_cfg.get("user", "homeassistant"),
                password=self.db_cfg.get("password", ""),
                db=self.db_cfg.get("name", "homeassistant"),
                charset="utf8mb4",
                autocommit=False,
            )
            cursor = connection.cursor()

            for table_name, entities in self.groups.items():
                self.ensure_table(cursor, table_name)

                for entity_id in entities:
                    state_obj = self.get_state(entity_id, attribute="all")

                    if state_obj is None:
                        self.logger.warning(f"Encja nie istnieje / niedostępna: {entity_id}")
                        continue

                    try:
                        value_str = state_obj.get("state", None)
                        if value_str in ("unavailable", "unknown", None):
                            continue

                        value = float(value_str)  # rzucamy wyjątek jeśli nie da się skonwertować
                    except (ValueError, TypeError):
                        self.logger.info(f"Nie udało się skonwertować na float: {entity_id} = {value_str}")
                        continue

                    metadata_id = self.get_metadata_id(cursor, entity_id)
                    if metadata_id is None:
                        self.logger.info(f"Brak metadata_id dla {entity_id} w states_meta!")
                        continue

                    sql = """
                    INSERT IGNORE INTO `{}` 
                    (dtime_utc, dtime, metadata_id, entity_value)
                    VALUES (%s, %s, %s, %s)
                    """.format(table_name)

                    cursor.execute(sql, (
                        dtime_utc,
                        dtime_local,
                        metadata_id,
                        value
                    ))

            connection.commit()
            self.logger.info(f"Zapisano dane o {dtime_local.strftime('%Y-%m-%d %H:%M')}")

        except OperationalError as e:
            self.logger.error(f"Błąd bazy danych: {e}")
        except Exception as e:
            self.logger.error(f"Nieoczekiwany błąd: {type(e).__name__}: {e}")
        finally:
            if connection:
                connection.close()


    def ensure_table(self, cursor, table_name):
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                dtime_utc DATETIME NOT NULL,
                dtime DATETIME NOT NULL,
                metadata_id BIGINT NOT NULL,
                entity_value FLOAT NOT NULL,
                PRIMARY KEY(dtime_utc, metadata_id),
                KEY ixd_dtime_utc (dtime_utc),
                KEY idx_dtime (dtime),
                KEY idx_metadata (metadata_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)


    def get_metadata_id(self, cursor, entity_id):
        cursor.execute("""
            SELECT metadata_id
            FROM states_meta
            WHERE entity_id = %s
            LIMIT 1
        """, (entity_id,))
        result = cursor.fetchone()
        return result[0] if result else None

