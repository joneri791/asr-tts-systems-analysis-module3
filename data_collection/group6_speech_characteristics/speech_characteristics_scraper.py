# speech_characteristics_scraper.py
import re
import sqlite3
from pathlib import Path

# --- Ключевые фразы и маппинг ---
SPEAKER_DEPENDENCY_MAP = {
    "speaker-independent": ("независимая", "Система работает без адаптации к конкретному диктору", False),
    "speaker adaptation": ("адаптивная", "Система адаптируется к голосу диктора", True),
}

SPEECH_TYPE_MAP = {
    "continuous speech": ("непрерывная", "Речь в естественном потоке", "Ошибки сегментации"),
    "isolated words": ("дискретная", "Речь ограничена отдельными словами", "Ограниченная естественность"),
    "spontaneous speech": ("спонтанная", "Свободная неподготовленная речь", "Высокая вариативность, ошибки"),
}


# --- Вспомогательные функции ---
def extract_characteristics(text: str):
    """Ищет в тексте ключевые фразы и возвращает найденные характеристики."""
    found_speakers = []
    found_speech = []

    for phrase, (typ, desc, learn) in SPEAKER_DEPENDENCY_MAP.items():
        if re.search(rf"\b{phrase}\b", text, flags=re.IGNORECASE):
            found_speakers.append((typ, desc, learn))

    for phrase, (typ, desc, issues) in SPEECH_TYPE_MAP.items():
        if re.search(rf"\b{phrase}\b", text, flags=re.IGNORECASE):
            found_speech.append((typ, desc, issues))

    return found_speakers, found_speech


def init_db(db_path="systems.db"):
    """Создаёт SQLite-базу с нужными таблицами, если её нет."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Таблицы систем
    cur.execute("""
    CREATE TABLE IF NOT EXISTS systems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        название TEXT,
        описание TEXT
    )""")

    # Speaker dependency
    cur.execute("""
    CREATE TABLE IF NOT EXISTS speaker_dependency_types (
        speaker_dep_id INTEGER PRIMARY KEY AUTOINCREMENT,
        speaker_dep_type TEXT,
        description TEXT,
        learning_require BOOLEAN
    )""")

    # Speech types
    cur.execute("""
    CREATE TABLE IF NOT EXISTS speech_types (
        speech_id INTEGER PRIMARY KEY AUTOINCREMENT,
        speech_type TEXT,
        description TEXT,
        issues TEXT
    )""")

    # Связки
    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_speakers (
        system_id INTEGER,
        speaker_dep_id INTEGER,
        FOREIGN KEY(system_id) REFERENCES systems(id),
        FOREIGN KEY(speaker_dep_id) REFERENCES speaker_dependency_types(speaker_dep_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_speech (
        system_id INTEGER,
        speech_id INTEGER,
        FOREIGN KEY(system_id) REFERENCES systems(id),
        FOREIGN KEY(speech_id) REFERENCES speech_types(speech_id)
    )""")

    conn.commit()
    return conn


def insert_characteristics(conn, system_id, speakers, speeches):
    """Сохраняет найденные характеристики в БД и связывает их с системой."""
    cur = conn.cursor()

    for typ, desc, learn in speakers:
        cur.execute("INSERT INTO speaker_dependency_types (speaker_dep_type, description, learning_require) VALUES (?, ?, ?)",
                    (typ, desc, learn))
        dep_id = cur.lastrowid
        cur.execute("INSERT INTO system_speakers (system_id, speaker_dep_id) VALUES (?, ?)", (system_id, dep_id))

    for typ, desc, issues in speeches:
        cur.execute("INSERT INTO speech_types (speech_type, description, issues) VALUES (?, ?, ?)",
                    (typ, desc, issues))
        speech_id = cur.lastrowid
        cur.execute("INSERT INTO system_speech (system_id, speech_id) VALUES (?, ?)", (system_id, speech_id))

    conn.commit()


# --- Основная логика ---
def process_models(descriptions_file: str, db_path="systems.db"):
    """Читает файл с описаниями моделей и анализирует их."""
    conn = init_db(db_path)
    cur = conn.cursor()

    for line in Path(descriptions_file).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue

        # допустим, формат: "SystemName | описание..."
        parts = line.split("|", maxsplit=1)
        if len(parts) != 2:
            continue

        system_name, description = parts[0].strip(), parts[1].strip()

        # Вставляем систему
        cur.execute("INSERT INTO systems (название, описание) VALUES (?, ?)", (system_name, description))
        system_id = cur.lastrowid

        # Ищем характеристики
        speakers, speeches = extract_characteristics(description)

        # Сохраняем
        insert_characteristics(conn, system_id, speakers, speeches)

    conn.close()


if __name__ == "__main__":
    # Пример: descriptions.txt должен содержать строки формата
    # Whisper | An end-to-end ASR model trained on multilingual speech. Supports speaker-independent continuous speech.
    process_models("descriptions.txt")