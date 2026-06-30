#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Curtain Bot v4.0 COMPLETE — Telegram бот для шторной мастерской.
Полностью переписанная версия с исправлением всех ошибок.
"""

import asyncio
import csv
import io
import logging
import os
import re
import qrcode
import time
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from enum import Enum, auto
from functools import wraps
from typing import Optional, List, Dict, Set, Tuple, Any, Union
from math import radians, sin, cos, sqrt, atan2

from dotenv import load_dotenv

load_dotenv()

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardMarkup,
    Message, ReplyKeyboardMarkup, Location, InputMediaPhoto,
    FSInputFile, User, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import InlineKeyboardButton


# ============================================================================
# КОНФИГУРАЦИЯ С ПРОВЕРКАМИ
# ============================================================================

def get_required_env(key: str) -> str:
    """Получение обязательной переменной окружения."""
    value = os.getenv(key, "")
    if not value:
        raise ValueError(f"Не задана обязательная переменная окружения: {key}")
    return value


def get_env_int(key: str, default: int) -> int:
    """Получение целочисленной переменной окружения."""
    value = os.getenv(key, str(default))
    try:
        return int(value)
    except ValueError:
        return default


def get_env_float(key: str, default: float) -> float:
    """Получение переменной окружения с плавающей точкой."""
    value = os.getenv(key, str(default))
    try:
        return float(value)
    except ValueError:
        return default


def get_env_bool(key: str, default: bool = False) -> bool:
    """Получение булевой переменной окружения."""
    value = os.getenv(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    return default


def parse_env_list(env_name: str, defaults: Optional[List[str]] = None) -> List[str]:
    """Парсинг списка из переменной окружения."""
    val = os.getenv(env_name, "")
    if val:
        return [x.strip() for x in val.split(",") if x.strip()]
    return defaults or []


def parse_ids(env_name: str) -> List[int]:
    """Парсинг списка ID из переменной окружения."""
    ids_str = os.getenv(env_name, "")
    if not ids_str:
        return []
    result = []
    for x in ids_str.split(","):
        x = x.strip()
        if x and x.lstrip('-').isdigit():
            result.append(int(x))
    return result


def parse_names(env_name: str) -> Dict[int, str]:
    """Парсинг словаря ID:имя из переменной окружения."""
    names_str = os.getenv(env_name, "")
    if not names_str:
        return {}
    result = {}
    for item in names_str.split(","):
        item = item.strip()
        if ":" in item:
            try:
                tid_str, name = item.split(":", 1)
                tid = int(tid_str.strip())
                name = name.strip()
                if name:
                    result[tid] = name
            except ValueError:
                continue
    return result


# Обязательные переменные
BOT_TOKEN = get_required_env("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "curtain_bot_v4.db")
BACKUP_CHAT_ID = os.getenv("BACKUP_CHAT_ID", "")
NOTIFICATION_GROUP_ID = os.getenv("NOTIFICATION_GROUP_ID", "")

# Преобразование с проверкой
NOTIFICATION_GROUP_ID_INT: Optional[int] = None
if NOTIFICATION_GROUP_ID and NOTIFICATION_GROUP_ID.lstrip('-').isdigit():
    NOTIFICATION_GROUP_ID_INT = int(NOTIFICATION_GROUP_ID)

# Настройки отчётов
DAILY_REPORT_MORNING_HOUR = get_env_int("DAILY_REPORT_MORNING_HOUR", 9)
DAILY_REPORT_MORNING_MINUTE = get_env_int("DAILY_REPORT_MORNING_MINUTE", 15)
DAILY_REPORT_EVENING_HOUR = get_env_int("DAILY_REPORT_EVENING_HOUR", 22)
DAILY_REPORT_EVENING_MINUTE = get_env_int("DAILY_REPORT_EVENING_MINUTE", 0)

SHIFT_REMINDER_HOUR = get_env_int("SHIFT_REMINDER_HOUR", 6)
SHIFT_REMINDER_MINUTE = get_env_int("SHIFT_REMINDER_MINUTE", 15)
DEADLINE_CHECK_INTERVAL = get_env_int("DEADLINE_CHECK_INTERVAL", 60)
ORDERS_PER_PAGE = get_env_int("ORDERS_PER_PAGE", 5)
ALLOWED_RADIUS_METERS = get_env_int("ALLOWED_RADIUS_METERS", 100)

WORKSHOP1_LAT = get_env_float("WORKSHOP1_LAT", 41.2995)
WORKSHOP1_LON = get_env_float("WORKSHOP1_LON", 69.2401)
WORKSHOP1_NAME = os.getenv("WORKSHOP1_NAME", "Цех №1")
WORKSHOP2_LAT = get_env_float("WORKSHOP2_LAT", 41.5829)
WORKSHOP2_LON = get_env_float("WORKSHOP2_LON", 60.6095)
WORKSHOP2_NAME = os.getenv("WORKSHOP2_NAME", "Цех №2")

WORKSHOP_LOCATIONS = [
    (WORKSHOP1_LAT, WORKSHOP1_LON, WORKSHOP1_NAME),
    (WORKSHOP2_LAT, WORKSHOP2_LON, WORKSHOP2_NAME),
]

# Каталоги
CATALOG_PATH = os.getenv("CATALOG_PATH", "catalog")
CORNICE_PHOTOS_DIR = os.path.join(CATALOG_PATH, "cornices")
MATERIAL_PHOTOS_DIR = os.path.join(CATALOG_PATH, "materials")
MODEL_PHOTOS_DIR = os.path.join(CATALOG_PATH, "models")

for directory in [CORNICE_PHOTOS_DIR, MATERIAL_PHOTOS_DIR, MODEL_PHOTOS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Справочники
CURTAIN_MODELS = parse_env_list("CURTAIN_MODELS", [
    "Прямые", "Жингалак", "Римские", "Австрийские", "Французские",
    "Японские", "Плиссе", "Рулонные", "Шторы-кафе", "Нитяные",
    "Бамбуковые", "Двойные", "Ламбрекен", "Блэкаут", "Другое"
])

MATERIALS_LIST = parse_env_list("MATERIALS_LIST", [
    "Блэкаут", "Велюр", "Лён", "Шёлк", "Атлас", "Габардин",
    "Тюль", "Органза", "Жаккард", "Хлопок", "Другое"
])

MATERIAL_OPTIONS_LIST = parse_env_list("MATERIAL_OPTIONS", [
    "Бархатные", "Шёлк", "Матовый", "Глянцевый", "Перламутровый",
    "Текстурный", "Однотонный", "С рисунком", "С принтом"
])

COLORS_LIST = parse_env_list("COLORS_LIST", [
    "Белый", "Бежевый", "Коричневый", "Серый", "Чёрный",
    "Синий", "Зелёный", "Красный", "Золотой", "Серебряный", "Другой"
])

CORNICE_TYPES = parse_env_list("CORNICE_TYPES", [
    "Профильный алюминий", "Круглый металл", "Круглый дерево",
    "Потолочный пластик", "Потолочный алюминий", "Струнный",
    "Электро", "Багетный", "Магнитный", "Двойной", "Другой"
])

TULLE_TYPES = parse_env_list("TULLE_TYPES", [
    "Органза", "Сетка", "Вуаль", "Шёлковая", "Полиэстер", "Не нужна"
])

SACHAK_TYPES = parse_env_list("SACHAK_TYPES", [
    "Лента-шнур", "Магнитный", "На липучке", "Крючки", "Не нужен"
])

ACCESSORY_TYPES = parse_env_list("ACCESSORY_TYPES", [
    "Подхваты", "Кисти", "Заколки", "Магниты", "Шторный шнур", "Не нужны"
])

# Роли и права
CEO_IDS = parse_ids("CEO_IDS")
ADMIN_IDS = parse_ids("ADMIN_IDS")
SELLER_IDS = parse_ids("SELLER_IDS")
MASTER_IDS = parse_ids("MASTER_IDS")
SEWER_IDS = parse_ids("SEWER_IDS")
INSTALLER_IDS = parse_ids("INSTALLER_IDS")
SMM_IDS = parse_ids("SMM_IDS")

CEO_NAMES = parse_names("CEO_NAMES")
ADMIN_NAMES = parse_names("ADMIN_NAMES")
SELLER_NAMES = parse_names("SELLER_NAMES")
MASTER_NAMES = parse_names("MASTER_NAMES")
SEWER_NAMES = parse_names("SEWER_NAMES")
INSTALLER_NAMES = parse_names("INSTALLER_NAMES")
SMM_NAMES = parse_names("SMM_NAMES")

ALL_NAMES: Dict[int, str] = {}
for names_dict in [CEO_NAMES, ADMIN_NAMES, SELLER_NAMES, MASTER_NAMES,
                   SEWER_NAMES, INSTALLER_NAMES, SMM_NAMES]:
    ALL_NAMES.update(names_dict)

ALL_REGISTERED_IDS = CEO_IDS + ADMIN_IDS + SELLER_IDS + MASTER_IDS + SEWER_IDS + INSTALLER_IDS + SMM_IDS

# ============================================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class Role(str, Enum):
    CEO = "ceo"
    ADMIN = "admin"
    SELLER = "seller"
    MASTER = "master"
    SEWER = "sewer"
    INSTALLER = "installer"
    SMM = "smm"


class OrderStatus(str, Enum):
    NEW = "new"
    PENDING_ADMIN = "pending_admin"
    ASSIGNED_MASTER = "assigned_master"
    IN_PROGRESS = "in_progress"
    PENDING_ADMIN_AFTER_MASTER = "pending_admin_after_master"
    TO_SEWER = "to_sewer"
    SEWING = "sewing"
    PENDING_ADMIN_AFTER_SEWER = "pending_admin_after_sewer"
    READY_FOR_INSTALL = "ready_for_install"
    ASSIGNED_INSTALLER = "assigned_installer"
    INSTALLING = "installing"
    COMPLETED = "completed"


class Priority(str, Enum):
    NORMAL = "normal"
    URGENT = "urgent"
    CRITICAL = "critical"


class PhotoStage(str, Enum):
    MEASUREMENT = "measurement"
    FABRIC = "fabric"
    CUTTING = "cutting"
    SEWING_PROCESS = "sewing_process"
    READY = "ready"
    INSTALL_BEFORE = "install_before"
    INSTALL_AFTER = "install_after"
    GENERAL = "general"


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def get_role_by_id(telegram_id: int) -> Role:
    """Определение роли по ID пользователя."""
    if telegram_id in CEO_IDS:
        return Role.CEO
    if telegram_id in ADMIN_IDS:
        return Role.ADMIN
    if telegram_id in SELLER_IDS:
        return Role.SELLER
    if telegram_id in MASTER_IDS:
        return Role.MASTER
    if telegram_id in SEWER_IDS:
        return Role.SEWER
    if telegram_id in INSTALLER_IDS:
        return Role.INSTALLER
    if telegram_id in SMM_IDS:
        return Role.SMM
    return Role.SELLER


def is_registered(telegram_id: int) -> bool:
    """Проверка, зарегистрирован ли пользователь."""
    return telegram_id in ALL_REGISTERED_IDS


def format_phone(phone: str) -> str:
    """Форматирование номера телефона."""
    cleaned = re.sub(r'\D', '', phone)
    if len(cleaned) == 9 and not cleaned.startswith('998'):
        cleaned = '998' + cleaned
    if len(cleaned) == 12 and cleaned.startswith('998'):
        return f"+{cleaned[0:3]} {cleaned[3:5]} {cleaned[5:8]} {cleaned[8:10]} {cleaned[10:12]}"
    return phone


def validate_phone(phone: str) -> bool:
    """Валидация номера телефона."""
    cleaned = re.sub(r'\D', '', phone.strip())
    # Узбекские номера: 9 цифр без кода, 12 цифр с кодом 998
    return len(cleaned) == 9 or (len(cleaned) == 12 and cleaned.startswith('998'))


def validate_date(date_string: str) -> bool:
    """Валидация даты."""
    date_string = date_string.strip()
    for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            datetime.strptime(date_string, date_format)
            return True
        except ValueError:
            continue
    return False


def normalize_date(date_string: str) -> str:
    """Нормализация даты к формату YYYY-MM-DD."""
    date_string = date_string.strip()
    for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_string, date_format).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_string


def parse_dimensions(text: str) -> Optional[Tuple[float, float, float]]:
    """
    Парсинг размеров из текста.
    Поддерживает: 150x200, 150х200, 150×200, 150*200, 150 200 и т.д.
    Возвращает (ширина, высота, площадь_м2) или None.
    """
    if not text or not isinstance(text, str):
        return None

    original_text = text.strip().lower()

    # Удаляем единицы измерения
    units_pattern = r'\b(см|sm|cm|мм|mm|м|m|метр|metr|сантиметр|миллиметр)\b'
    clean_text = re.sub(units_pattern, '', original_text)
    clean_text = clean_text.replace(",", ".")

    # Заменяем все разделители на пробел
    separators = r'[хx×\*\-\—\–\|\s]+'
    normalized = re.sub(separators, ' ', clean_text)

    # Извлекаем числа
    numbers = re.findall(r"\d+(?:\.\d+)?", normalized)

    if len(numbers) >= 2:
        try:
            width = float(numbers[0])
            height = float(numbers[1])
            if 0 < width <= 2000 and 0 < height <= 2000:
                area_m2 = (width * height) / 10000.0
                return (width, height, area_m2)
        except ValueError:
            pass

    return None


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расчёт расстояния между двумя точками на сфере (в метрах)."""
    R = 6371000  # Радиус Земли в метрах
    lat1_rad, lat2_rad = radians(lat1), radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


async def find_nearest_workshop(latitude: float, longitude: float) -> Optional[Tuple[float, float, str, float]]:
    """Поиск ближайшего цеха."""
    nearest = None
    min_distance = float('inf')
    for lat, lon, name in WORKSHOP_LOCATIONS:
        distance = calculate_distance(latitude, longitude, lat, lon)
        if distance < min_distance:
            min_distance = distance
            nearest = (lat, lon, name, distance)
    return nearest


async def is_near_any_workshop(latitude: float, longitude: float) -> Tuple[bool, Optional[Tuple]]:
    """Проверка, находится ли пользователь рядом с любым цехом."""
    nearest = await find_nearest_workshop(latitude, longitude)
    if nearest is None:
        return False, None
    return nearest[3] <= ALLOWED_RADIUS_METERS, nearest


def status_display(status: str) -> str:
    """Отображение статуса для пользователя."""
    mapping = {
        OrderStatus.NEW.value: "🆕 Новый",
        OrderStatus.PENDING_ADMIN.value: "⏳ Ждёт админа",
        OrderStatus.ASSIGNED_MASTER.value: "🔧 Назначен мастер",
        OrderStatus.IN_PROGRESS.value: "🔧 В работе у мастера",
        OrderStatus.PENDING_ADMIN_AFTER_MASTER.value: "⏳ Мастер готов, ждёт админа",
        OrderStatus.TO_SEWER.value: "📤 Передан швее",
        OrderStatus.SEWING.value: "🧵 Отшивается",
        OrderStatus.PENDING_ADMIN_AFTER_SEWER.value: "⏳ Швея готова, ждёт админа",
        OrderStatus.READY_FOR_INSTALL.value: "✅ Готов к установке",
        OrderStatus.ASSIGNED_INSTALLER.value: "👷 Назначен установщик",
        OrderStatus.INSTALLING.value: "🚚 Устанавливается",
        OrderStatus.COMPLETED.value: "🏁 Выполнен",
    }
    return mapping.get(status, status)


def priority_display(priority: str) -> str:
    """Отображение приоритета для пользователя."""
    mapping = {
        Priority.NORMAL.value: "🟢 Обычный",
        Priority.URGENT.value: "🟡 Срочный",
        Priority.CRITICAL.value: "🔴 Критический",
    }
    return mapping.get(priority, priority)


def priority_emoji(priority: str) -> str:
    """Эмодзи для приоритета."""
    mapping = {
        Priority.CRITICAL.value: "🔴",
        Priority.URGENT.value: "🟡",
        Priority.NORMAL.value: "🟢",
    }
    return mapping.get(priority, "⚪")


def stage_display(stage: str) -> str:
    """Отображение этапа для пользователя."""
    mapping = {
        PhotoStage.MEASUREMENT.value: "📏 Замеры",
        PhotoStage.FABRIC.value: "🧵 Ткань",
        PhotoStage.CUTTING.value: "✂️ Раскрой",
        PhotoStage.SEWING_PROCESS.value: "🪡 Пошив",
        PhotoStage.READY.value: "✅ Готово",
        PhotoStage.INSTALL_BEFORE.value: "🏠 До установки",
        PhotoStage.INSTALL_AFTER.value: "🎉 После установки",
        PhotoStage.GENERAL.value: "📸 Общее",
    }
    return mapping.get(stage, stage)


def get_item_photo_path(item_name: str, category: str = "cornices") -> Optional[str]:
    """
    Получение пути к фото элемента каталога.
    Кэширует результаты для избежания повторного сканирования.
    """
    # Кэш для ускорения
    if not hasattr(get_item_photo_path, "cache"):
        get_item_photo_path.cache = {}

    cache_key = f"{category}:{item_name}"
    if cache_key in get_item_photo_path.cache:
        cached_path = get_item_photo_path.cache[cache_key]
        if cached_path and os.path.exists(cached_path):
            return cached_path
        else:
            del get_item_photo_path.cache[cache_key]

    directory_map = {
        "cornices": CORNICE_PHOTOS_DIR,
        "materials": MATERIAL_PHOTOS_DIR,
        "models": MODEL_PHOTOS_DIR,
    }
    search_directory = directory_map.get(category, CORNICE_PHOTOS_DIR)
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', item_name)

    # Ищем по расширениям
    for extension in ['.jpg', '.jpeg', '.png', '.webp']:
        full_path = os.path.join(search_directory, safe_name + extension)
        if os.path.exists(full_path):
            get_item_photo_path.cache[cache_key] = full_path
            return full_path

    # Ищем по имени без расширения
    try:
        for filename in os.listdir(search_directory):
            name_without_ext = os.path.splitext(filename)[0]
            if name_without_ext == safe_name:
                full_path = os.path.join(search_directory, filename)
                get_item_photo_path.cache[cache_key] = full_path
                return full_path
    except OSError:
        pass

    get_item_photo_path.cache[cache_key] = None
    return None


async def send_catalog_photo(
        chat_id: int,
        item_name: str,
        caption: str,
        category: str = "cornices",
        reply_markup: Optional[InlineKeyboardMarkup] = None
) -> bool:
    """Отправка фото из каталога."""
    photo_path = get_item_photo_path(item_name, category)
    if photo_path:
        try:
            photo = FSInputFile(photo_path)
            await bot.send_photo(chat_id, photo, caption=caption, reply_markup=reply_markup)
            return True
        except Exception as error:
            logger.warning(f"Ошибка отправки фото {photo_path}: {error}")
    return False


# ============================================================================
# БАЗА ДАННЫХ (ПОЛНОСТЬЮ ПЕРЕРАБОТАНА)
# ============================================================================

class Database:
    """Класс для работы с базой данных."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection_pool: List[aiosqlite.Connection] = []
        self._max_connections = 10

    @asynccontextmanager
    async def get_connection(self):
        """Получение соединения из пула."""
        connection = None
        try:
            connection = await aiosqlite.connect(self.db_path)
            connection.row_factory = aiosqlite.Row
            yield connection
        finally:
            if connection:
                await connection.close()

    async def init(self) -> None:
        """Инициализация базы данных."""
        async with self.get_connection() as db:
            await db.executescript("""
                -- Таблица пользователей
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'seller',
                    phone TEXT,
                    lang TEXT DEFAULT 'ru',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Таблица смен
                CREATE TABLE IF NOT EXISTS shift_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    ended_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    last_lat REAL,
                    last_lon REAL,
                    workshop_point TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                );

                -- Таблица заказов
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_number TEXT UNIQUE,
                    client_name TEXT NOT NULL,
                    client_phone TEXT NOT NULL,
                    client_tg_id INTEGER,
                    model TEXT NOT NULL,
                    materials TEXT NOT NULL,
                    material_options TEXT,
                    color TEXT,
                    characteristics TEXT,
                    dimensions TEXT,
                    area_m2 REAL,
                    cornice TEXT,
                    cornice_rotation TEXT,
                    tulle TEXT,
                    sachak TEXT,
                    accessory TEXT,
                    door_model TEXT,
                    door_material TEXT,
                    door_material_options TEXT,
                    door_color TEXT,
                    door_dimensions TEXT,
                    door_cornice TEXT,
                    door_cornice_rotation TEXT,
                    door_sachak TEXT,
                    door_accessory TEXT,
                    install_address TEXT,
                    install_lat REAL,
                    install_lon REAL,
                    client_comment TEXT,
                    deadline TEXT,
                    priority TEXT DEFAULT 'normal',
                    status TEXT DEFAULT 'new',
                    work_price REAL DEFAULT 0,
                    deposit REAL DEFAULT 0,
                    remaining_payment REAL DEFAULT 0,
                    seller_id INTEGER,
                    assigned_to_id INTEGER,
                    master_id INTEGER,
                    sewer_id INTEGER,
                    installer_id INTEGER,
                    location_lat REAL,
                    location_lon REAL,
                    location_text TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    is_active INTEGER DEFAULT 1
                );

                -- Таблица истории статусов
                CREATE TABLE IF NOT EXISTS status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    changed_by INTEGER NOT NULL,
                    changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    comment TEXT,
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                );

                -- Таблица комментариев
                CREATE TABLE IF NOT EXISTS order_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    is_voice INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                );

                -- Таблица фото
                CREATE TABLE IF NOT EXISTS order_photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    file_unique_id TEXT NOT NULL,
                    stage TEXT DEFAULT 'general',
                    uploaded_by INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Таблица закупок
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    material_name TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    comment TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Таблица аудита
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT,
                    entity_id INTEGER,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Таблица отзывов
                CREATE TABLE IF NOT EXISTS client_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    client_phone TEXT NOT NULL,
                    rating INTEGER,
                    comment TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Индексы для оптимизации
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_orders_deadline ON orders(deadline);
                CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(client_phone);
                CREATE INDEX IF NOT EXISTS idx_orders_seller ON orders(seller_id);
                CREATE INDEX IF NOT EXISTS idx_photos_stage ON order_photos(order_id, stage);
                CREATE INDEX IF NOT EXISTS idx_history_order ON status_history(order_id);
                CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
            """)
            await db.commit()
        logger.info("База данных инициализирована (версия 4.0)")

    # ----- Работа с пользователями -----

    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение пользователя по ID."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_user(
            self,
            telegram_id: int,
            full_name: str,
            username: Optional[str],
            role: str,
            language: str = "ru"
    ) -> None:
        """Создание или обновление пользователя."""
        async with self.get_connection() as db:
            # Проверяем существование
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            existing = await cursor.fetchone()

            if existing:
                # Обновляем существующего
                await db.execute(
                    """UPDATE users 
                       SET full_name = ?, 
                           username = COALESCE(NULLIF(?, ''), username), 
                           lang = ? 
                       WHERE telegram_id = ?""",
                    (full_name, username or "", language, telegram_id)
                )
            else:
                # Создаём нового
                await db.execute(
                    "INSERT INTO users (telegram_id, full_name, username, role, lang) VALUES (?, ?, ?, ?, ?)",
                    (telegram_id, full_name, username, role, language)
                )
            await db.commit()

    async def update_user_language(self, telegram_id: int, language: str) -> None:
        """Обновление языка пользователя."""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE users SET lang = ? WHERE telegram_id = ?",
                (language, telegram_id)
            )
            await db.commit()

    async def get_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Получение всех пользователей с указанной ролью."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE role = ? AND is_active = 1",
                (role,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_all_active_users(self) -> List[Dict[str, Any]]:
        """Получение всех активных пользователей."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE is_active = 1"
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def update_user_role(self, telegram_id: int, new_role: str) -> None:
        """Обновление роли пользователя."""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE users SET role = ? WHERE telegram_id = ?",
                (new_role, telegram_id)
            )
            await db.commit()

    # ----- Работа со сменами -----

    async def start_shift(
            self,
            user_id: int,
            latitude: Optional[float] = None,
            longitude: Optional[float] = None,
            workshop_point: Optional[str] = None
    ) -> None:
        """Начало смены."""
        async with self.get_connection() as db:
            now = datetime.now().isoformat()
            # Завершаем предыдущую активную смену
            await db.execute(
                "UPDATE shift_records SET ended_at = ?, is_active = 0 WHERE user_id = ? AND is_active = 1",
                (now, user_id)
            )
            # Начинаем новую
            await db.execute(
                """INSERT INTO shift_records 
                   (user_id, started_at, is_active, last_lat, last_lon, workshop_point) 
                   VALUES (?, ?, 1, ?, ?, ?)""",
                (user_id, now, latitude, longitude, workshop_point)
            )
            await db.commit()

    async def end_shift(self, user_id: int) -> None:
        """Завершение смены."""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE shift_records SET ended_at = ?, is_active = 0 WHERE user_id = ? AND is_active = 1",
                (datetime.now().isoformat(), user_id)
            )
            await db.commit()

    async def is_on_shift(self, user_id: int) -> bool:
        """Проверка, находится ли пользователь на смене."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT 1 FROM shift_records WHERE user_id = ? AND is_active = 1",
                (user_id,)
            )
            return await cursor.fetchone() is not None

    async def get_today_shifts(self) -> List[Dict[str, Any]]:
        """Получение всех смен за сегодня."""
        today = date.today().isoformat()
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT s.*, u.full_name, u.role 
                   FROM shift_records s 
                   JOIN users u ON s.user_id = u.telegram_id 
                   WHERE s.started_at LIKE ? AND s.is_active = 1""",
                (f"{today}%",)
            )
            return [dict(row) for row in await cursor.fetchall()]

    # ----- Работа с заказами -----

    async def create_order(self, order_number: str, seller_id: int, **kwargs) -> int:
        """Создание нового заказа."""
        async with self.get_connection() as db:
            fields = ["order_number", "seller_id"] + list(kwargs.keys())
            values = [order_number, seller_id] + list(kwargs.values())
            placeholders = ",".join("?" * len(values))
            query = f"INSERT INTO orders ({','.join(fields)}) VALUES ({placeholders})"

            cursor = await db.execute(query, values)
            order_id = cursor.lastrowid

            # Добавляем запись в историю
            await db.execute(
                "INSERT INTO status_history (order_id, status, changed_by, comment) VALUES (?, ?, ?, ?)",
                (order_id, OrderStatus.NEW.value, seller_id, "Заказ создан")
            )
            await db.commit()
            return order_id

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Получение заказа по ID."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM orders WHERE id = ?",
                (order_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_order_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Поиск заказа по номеру телефона."""
        clean_phone = re.sub(r'\D', '', phone)
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT * FROM orders 
                   WHERE REPLACE(REPLACE(REPLACE(client_phone, ' ', ''), '+', ''), '-', '') LIKE ? 
                   AND is_active = 1 
                   ORDER BY created_at DESC 
                   LIMIT 1""",
                (f"%{clean_phone}%",)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_order(self, order_id: int, **kwargs) -> None:
        """Обновление полей заказа."""
        if not kwargs:
            return
        async with self.get_connection() as db:
            kwargs["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{key} = ?" for key in kwargs)
            values = list(kwargs.values()) + [order_id]
            await db.execute(f"UPDATE orders SET {set_clause} WHERE id = ?", values)
            await db.commit()

    async def update_order_number(self, order_id: int, order_number: str) -> None:
        """Обновление номера заказа."""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE orders SET order_number = ? WHERE id = ?",
                (order_number, order_id)
            )
            await db.commit()

    async def delete_order(self, order_id: int) -> None:
        """Мягкое удаление заказа."""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE orders SET is_active = 0, updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), order_id)
            )
            await db.commit()

    async def update_order_status(
            self,
            order_id: int,
            status: str,
            changed_by: int,
            comment: str = "",
            **kwargs
    ) -> None:
        """Обновление статуса заказа."""
        async with self.get_connection() as db:
            # Обновляем поля
            update_data = {"status": status, "updated_at": datetime.now().isoformat()}
            update_data.update(kwargs)

            if status == OrderStatus.COMPLETED.value:
                update_data["completed_at"] = datetime.now().isoformat()

            set_clause = ", ".join(f"{key} = ?" for key in update_data)
            await db.execute(
                f"UPDATE orders SET {set_clause} WHERE id = ?",
                list(update_data.values()) + [order_id]
            )

            # Добавляем в историю
            await db.execute(
                "INSERT INTO status_history (order_id, status, changed_by, comment) VALUES (?, ?, ?, ?)",
                (order_id, status, changed_by, comment or f"Статус изменён на {status}")
            )
            await db.commit()

    async def get_status_history(self, order_id: int) -> List[Dict[str, Any]]:
        """Получение истории статусов заказа."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT h.*, u.full_name 
                   FROM status_history h 
                   JOIN users u ON h.changed_by = u.telegram_id 
                   WHERE h.order_id = ? 
                   ORDER BY h.changed_at DESC""",
                (order_id,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_orders_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Получение заказов по статусу."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM orders WHERE status = ? AND is_active = 1 ORDER BY created_at DESC",
                (status,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_orders_by_seller(self, seller_id: int, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Получение заказов продавца."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT * FROM orders 
                   WHERE seller_id = ? AND is_active = 1 
                   ORDER BY created_at DESC 
                   LIMIT ? OFFSET ?""",
                (seller_id, limit, offset)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def count_orders_by_seller(self, seller_id: int) -> int:
        """Подсчёт количества заказов продавца."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM orders WHERE seller_id = ? AND is_active = 1",
                (seller_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_orders_for_sewer(self, sewer_id: int) -> List[Dict[str, Any]]:
        """Получение заказов для швеи."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT * FROM orders 
                   WHERE sewer_id = ? 
                   AND status IN (?, ?) 
                   AND is_active = 1""",
                (sewer_id, OrderStatus.TO_SEWER.value, OrderStatus.SEWING.value)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_orders_for_installer(self, installer_id: int) -> List[Dict[str, Any]]:
        """Получение заказов для установщика."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT * FROM orders 
                   WHERE installer_id = ? 
                   AND status IN (?, ?) 
                   AND is_active = 1""",
                (installer_id, OrderStatus.ASSIGNED_INSTALLER.value, OrderStatus.INSTALLING.value)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_overdue_orders(self) -> List[Dict[str, Any]]:
        """Получение просроченных заказов."""
        today = date.today().isoformat()
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT * FROM orders 
                   WHERE deadline IS NOT NULL 
                   AND deadline < ? 
                   AND status NOT IN (?, ?) 
                   AND is_active = 1 
                   ORDER BY deadline ASC""",
                (today, OrderStatus.COMPLETED.value, "completed")
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def search_orders(
            self,
            query: str = "",
            status: str = "",
            assigned_to: int = 0,
            seller_id: int = 0,
            overdue_only: bool = False,
            priority: str = "",
            limit: int = 20,
            offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Расширенный поиск заказов."""
        conditions = ["is_active = 1"]
        params = []

        if query:
            conditions.append("(order_number LIKE ? OR client_name LIKE ? OR client_phone LIKE ?)")
            like_pattern = f"%{query}%"
            params.extend([like_pattern, like_pattern, like_pattern])

        if status:
            conditions.append("status = ?")
            params.append(status)

        if assigned_to:
            conditions.append("(seller_id = ? OR master_id = ? OR sewer_id = ? OR installer_id = ?)")
            params.extend([assigned_to] * 4)

        if seller_id:
            conditions.append("seller_id = ?")
            params.append(seller_id)

        if overdue_only:
            today = date.today().isoformat()
            conditions.append("deadline IS NOT NULL AND deadline < ? AND status != ?")
            params.extend([today, OrderStatus.COMPLETED.value])

        if priority:
            conditions.append("priority = ?")
            params.append(priority)

        where_clause = " AND ".join(conditions)
        query_sql = f"""
            SELECT * FROM orders 
            WHERE {where_clause} 
            ORDER BY 
                CASE priority 
                    WHEN 'critical' THEN 1 
                    WHEN 'urgent' THEN 2 
                    ELSE 3 
                END, 
                created_at DESC 
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        async with self.get_connection() as db:
            cursor = await db.execute(query_sql, params)
            return [dict(row) for row in await cursor.fetchall()]

    async def count_orders(
            self,
            query: str = "",
            status: str = "",
            assigned_to: int = 0,
            seller_id: int = 0,
            overdue_only: bool = False,
            priority: str = ""
    ) -> int:
        """Подсчёт количества заказов по фильтрам."""
        conditions = ["is_active = 1"]
        params = []

        if query:
            conditions.append("(order_number LIKE ? OR client_name LIKE ? OR client_phone LIKE ?)")
            like_pattern = f"%{query}%"
            params.extend([like_pattern, like_pattern, like_pattern])

        if status:
            conditions.append("status = ?")
            params.append(status)

        if assigned_to:
            conditions.append("(seller_id = ? OR master_id = ? OR sewer_id = ? OR installer_id = ?)")
            params.extend([assigned_to] * 4)

        if seller_id:
            conditions.append("seller_id = ?")
            params.append(seller_id)

        if overdue_only:
            today = date.today().isoformat()
            conditions.append("deadline IS NOT NULL AND deadline < ? AND status != ?")
            params.extend([today, OrderStatus.COMPLETED.value])

        if priority:
            conditions.append("priority = ?")
            params.append(priority)

        where_clause = " AND ".join(conditions)
        query_sql = f"SELECT COUNT(*) FROM orders WHERE {where_clause}"

        async with self.get_connection() as db:
            cursor = await db.execute(query_sql, params)
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_status_counts(self) -> Dict[str, int]:
        """Получение количества заказов по статусам."""
        async with self.get_connection() as db:
            counts = {status.value: 0 for status in OrderStatus}
            cursor = await db.execute(
                "SELECT status, COUNT(*) FROM orders WHERE is_active = 1 GROUP BY status"
            )
            async for row in cursor:
                if row[0] in counts:
                    counts[row[0]] = row[1]
            return counts

    # ----- Комментарии -----

    async def add_comment(self, order_id: int, user_id: int, text: str, is_voice: int = 0) -> None:
        """Добавление комментария к заказу."""
        async with self.get_connection() as db:
            await db.execute(
                "INSERT INTO order_comments (order_id, user_id, text, is_voice) VALUES (?, ?, ?, ?)",
                (order_id, user_id, text, is_voice)
            )
            await db.commit()

    async def get_comments(self, order_id: int) -> List[Dict[str, Any]]:
        """Получение комментариев к заказу."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT c.*, u.full_name, u.role 
                   FROM order_comments c 
                   JOIN users u ON c.user_id = u.telegram_id 
                   WHERE c.order_id = ? 
                   ORDER BY c.created_at DESC""",
                (order_id,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    # ----- Фото -----

    async def add_photo(
            self,
            order_id: int,
            file_id: str,
            file_unique_id: str,
            uploaded_by: Optional[int] = None,
            stage: str = "general"
    ) -> None:
        """Добавление фото к заказу."""
        async with self.get_connection() as db:
            await db.execute(
                """INSERT INTO order_photos 
                   (order_id, file_id, file_unique_id, stage, uploaded_by) 
                   VALUES (?, ?, ?, ?, ?)""",
                (order_id, file_id, file_unique_id, stage, uploaded_by)
            )
            await db.commit()

    async def get_photos(self, order_id: int, stage: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получение фото заказа."""
        async with self.get_connection() as db:
            if stage:
                cursor = await db.execute(
                    """SELECT * FROM order_photos 
                       WHERE order_id = ? AND stage = ? 
                       ORDER BY created_at DESC""",
                    (order_id, stage)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM order_photos WHERE order_id = ? ORDER BY created_at DESC",
                    (order_id,)
                )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_photos_by_stage(self, order_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """Получение фото, сгруппированных по этапам."""
        all_photos = await self.get_photos(order_id)
        result: Dict[str, List[Dict[str, Any]]] = {}
        for photo in all_photos:
            stage = photo.get("stage", "general")
            if stage not in result:
                result[stage] = []
            result[stage].append(photo)
        return result

    # ----- Закупки -----

    async def add_purchase(self, order_id: int, material_name: str, price: float, quantity: int = 1) -> None:
        """Добавление записи о закупке материала."""
        async with self.get_connection() as db:
            await db.execute(
                "INSERT INTO purchases (order_id, material_name, price, quantity) VALUES (?, ?, ?, ?)",
                (order_id, material_name, price, quantity)
            )
            await db.commit()

    async def get_purchases(self, order_id: int) -> List[Dict[str, Any]]:
        """Получение списка закупок по заказу."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM purchases WHERE order_id = ?",
                (order_id,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_purchases_sum(self, order_id: int) -> float:
        """Получение общей суммы закупок по заказу."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(price * quantity), 0) FROM purchases WHERE order_id = ?",
                (order_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0.0

    async def get_purchases_sum_today(self) -> float:
        """Получение суммы закупок за сегодня."""
        today = date.today().isoformat()
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(price * quantity), 0) FROM purchases WHERE created_at LIKE ?",
                (f"{today}%",)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0.0

    # ----- Отзывы -----

    async def add_review(self, order_id: int, client_phone: str, rating: int, comment: str = "") -> None:
        """Добавление отзыва клиента."""
        async with self.get_connection() as db:
            await db.execute(
                "INSERT INTO client_reviews (order_id, client_phone, rating, comment) VALUES (?, ?, ?, ?)",
                (order_id, client_phone, rating, comment)
            )
            await db.commit()

    async def get_reviews(self, order_id: int) -> List[Dict[str, Any]]:
        """Получение отзывов по заказу."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM client_reviews WHERE order_id = ?",
                (order_id,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    # ----- Аудит -----

    async def audit(self, user_id: int, action: str, entity_type: str = "", entity_id: int = 0, details: str = "") -> None:
        """Запись действия в аудит."""
        async with self.get_connection() as db:
            await db.execute(
                "INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                (user_id, action, entity_type, entity_id, details)
            )
            await db.commit()

    # ----- Статистика -----

    async def get_daily_stats(self) -> Dict[str, Any]:
        """Получение ежедневной статистики."""
        today = date.today().isoformat()
        async with self.get_connection() as db:
            # Создано сегодня
            cursor = await db.execute(
                "SELECT COUNT(*) FROM orders WHERE created_at LIKE ? AND is_active = 1",
                (f"{today}%",)
            )
            created_today = (await cursor.fetchone())[0]

            # Выполнено сегодня
            cursor = await db.execute(
                "SELECT COUNT(*) FROM orders WHERE completed_at LIKE ? AND is_active = 1",
                (f"{today}%",)
            )
            completed_today = (await cursor.fetchone())[0]

            # На смене
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM shift_records WHERE started_at LIKE ? AND is_active = 1",
                (f"{today}%",)
            )
            on_shift = (await cursor.fetchone())[0]

            # Просрочено
            cursor = await db.execute(
                """SELECT COUNT(*) FROM orders 
                   WHERE deadline IS NOT NULL 
                   AND deadline < ? 
                   AND status NOT IN (?, ?) 
                   AND is_active = 1""",
                (today, OrderStatus.COMPLETED.value, "completed")
            )
            overdue = (await cursor.fetchone())[0]

            # Сумма закупок
            purchases_sum = await self.get_purchases_sum_today()

            # Статусы
            status_counts = await self.get_status_counts()

        return {
            "created_today": created_today,
            "completed_today": completed_today,
            "on_shift": on_shift,
            "overdue": overdue,
            "purchases_sum": purchases_sum,
            "status_counts": status_counts,
        }

    # ----- Экспорт -----

    async def export_orders_csv(self) -> bytes:
        """Экспорт заказов в CSV."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM orders WHERE is_active = 1 ORDER BY created_at DESC"
            )
            orders = [dict(row) for row in await cursor.fetchall()]

        output = io.StringIO()
        if not orders:
            output.write("Нет данных\n")
            return output.getvalue().encode("utf-8-sig")

        fieldnames = [
            "id", "order_number", "client_name", "client_phone",
            "model", "materials", "material_options", "color", "characteristics",
            "dimensions", "area_m2", "cornice", "cornice_rotation", "tulle",
            "sachak", "accessory", "door_model", "door_material",
            "door_material_options", "door_color", "door_dimensions",
            "door_cornice", "door_cornice_rotation", "door_sachak", "door_accessory",
            "install_address", "client_comment", "deadline", "priority", "status",
            "work_price", "deposit", "remaining_payment", "created_at",
            "updated_at", "completed_at",
        ]

        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            extrasaction="ignore",
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        writer.writeheader()

        for order in orders:
            order["status"] = status_display(order["status"])
            order["priority"] = priority_display(order["priority"])
            writer.writerow(order)

        return output.getvalue().encode("utf-8-sig")


# ============================================================================
# ГЛОБАЛЬНЫЕ ОБЪЕКТЫ
# ============================================================================

db = Database(DB_PATH)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ============================================================================
# ФУНКЦИИ УВЕДОМЛЕНИЙ
# ============================================================================

async def notify_group(message_text: str, photo: Optional[BufferedInputFile] = None) -> None:
    """Отправка уведомления в группу."""
    if NOTIFICATION_GROUP_ID_INT is None:
        return
    try:
        if photo:
            await bot.send_photo(NOTIFICATION_GROUP_ID_INT, photo=photo, caption=message_text)
        else:
            await bot.send_message(NOTIFICATION_GROUP_ID_INT, message_text)
    except Exception as error:
        logger.warning(f"Ошибка отправки уведомления в группу: {error}")


async def notify_all_admins(message_text: str) -> None:
    """Отправка уведомления всем администраторам."""
    for admin_id in CEO_IDS + ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message_text)
        except Exception as error:
            logger.warning(f"Ошибка отправки уведомления администратору {admin_id}: {error}")


async def notify_role_users(role: str, message_text: str) -> None:
    """Отправка уведомления всем пользователям с указанной ролью."""
    users = await db.get_users_by_role(role)
    for user in users:
        try:
            await bot.send_message(user["telegram_id"], message_text)
        except Exception as error:
            logger.warning(f"Ошибка отправки уведомления {user['telegram_id']}: {error}")


async def get_user_data(telegram_id: int, full_name: str, username: Optional[str]) -> Dict[str, Any]:
    """
    Получение или создание данных пользователя.
    Возвращает словарь с данными пользователя.
    """
    user = await db.get_user(telegram_id)

    # Получаем правильное имя из конфигурации
    env_name = ALL_NAMES.get(telegram_id)

    if not user:
        # Новый пользователь
        role = get_role_by_id(telegram_id).value
        display_name = env_name if env_name else full_name
        await db.create_user(telegram_id, display_name, username, role)
        user = await db.get_user(telegram_id)
    else:
        # Существующий пользователь - проверяем имя
        current_name = user.get("full_name", "")

        if env_name:
            correct_name = env_name
        elif current_name.startswith("User ") and current_name[5:].isdigit():
            correct_name = full_name
        else:
            correct_name = current_name

        if current_name != correct_name:
            await db.create_user(telegram_id, correct_name, username, user.get("role", "seller"), user.get("lang", "ru"))
            user = await db.get_user(telegram_id)

    return user


async def format_order_details(order: Dict[str, Any], for_client: bool = False) -> str:
    """Форматирование деталей заказа для отображения."""
    # Получаем имена ответственных
    seller_name = "Не назначен"
    admin_name = "Не назначен"
    master_name = "Не назначен"
    sewer_name = "Не назначен"
    installer_name = "Не назначен"

    if order.get("seller_id"):
        seller = await db.get_user(order["seller_id"])
        if seller:
            seller_name = seller["full_name"]

    if order.get("assigned_to_id"):
        admin_user = await db.get_user(order["assigned_to_id"])
        if admin_user and admin_user["role"] == "admin":
            admin_name = admin_user["full_name"]

    if order.get("master_id"):
        master = await db.get_user(order["master_id"])
        if master:
            master_name = master["full_name"]

    if order.get("sewer_id"):
        sewer = await db.get_user(order["sewer_id"])
        if sewer:
            sewer_name = sewer["full_name"]

    if order.get("installer_id"):
        installer = await db.get_user(order["installer_id"])
        if installer:
            installer_name = installer["full_name"]

    # Расчёты по финансам
    purchases = await db.get_purchases(order["id"])
    materials_total = sum(purchase["price"] * purchase["quantity"] for purchase in purchases)
    work_price = order.get("work_price", 0) or 0
    deposit_amount = order.get("deposit", 0) or 0
    remaining = order.get("remaining_payment", 0) or 0
    grand_total = materials_total + work_price

    # Дедлайн
    deadline_line = ""
    overdue_warning = ""
    if order.get("deadline"):
        deadline_line = f"\n📅 Дедлайн: <b>{order['deadline']}</b>"
        try:
            deadline_date = datetime.strptime(order["deadline"], "%Y-%m-%d").date()
            if deadline_date < date.today() and order["status"] != OrderStatus.COMPLETED.value:
                overdue_warning = "\n⚠️ <b>Просрочен!</b>"
        except ValueError:
            pass

    priority_line = f"\n⭐ Приоритет: {priority_display(order.get('priority', Priority.NORMAL.value))}"
    dimensions_line = f"\n📐 Размеры: {order.get('dimensions', '—')} см" if order.get("dimensions") else ""
    color_line = f"\n🎨 Цвет: {order.get('color', '—')}" if order.get("color") else ""
    material_options_line = f"\n✨ Опции: {order.get('material_options', '—')}" if order.get("material_options") else ""
    cornice_rotation_line = f"\n↩️ Поворот багета: {order.get('cornice_rotation', '—')}" if order.get("cornice_rotation") else ""
    tulle_line = f"\n🪟 Тюль: {order.get('tulle', '—')}" if order.get("tulle") else ""
    sachak_line = f"\n🎀 Сачак: {order.get('sachak', '—')}" if order.get("sachak") else ""
    accessory_line = f"\n🎁 Аксессуар: {order.get('accessory', '—')}" if order.get("accessory") else ""
    address_line = f"\n📍 Адрес: {order.get('install_address', '—')}" if order.get("install_address") else ""
    deposit_line = f"\n💰 Залог: {deposit_amount:.2f} сум" if deposit_amount else ""
    remaining_line = f"\n💰 Остаток: {remaining:.2f} сум" if remaining else ""

    # Дверная штора
    door_lines = ""
    if order.get("door_model"):
        door_lines = (
            f"\n\n🚪 <b>Дверная штора:</b>\n"
            f"🪟 Модель: {order.get('door_model', '—')}\n"
            f"🧵 Материал: {order.get('door_material', '—')}\n"
            f"🎨 Цвет: {order.get('door_color', '—')}\n"
            f"📐 Размеры: {order.get('door_dimensions', '—')} см\n"
            f"🔲 Багет: {order.get('door_cornice', '—')}"
        )

    if for_client:
        return (
            f"📋 <b>Ваш заказ {order['order_number']}</b>\n\n"
            f"🪟 Модель: {order['model']}\n"
            f"🧵 Материалы: {order['materials']}{material_options_line}{color_line}\n"
            f"📐 Характеристики: {order.get('characteristics', '—')}"
            f"{dimensions_line}\n"
            f"{tulle_line}{sachak_line}{accessory_line}\n"
            f"🔲 Багет: {order.get('cornice') or '—'}{cornice_rotation_line}\n"
            f"{address_line}"
            f"📌 Статус: {status_display(order['status'])}"
            f"{deadline_line}{overdue_warning}{priority_line}\n"
            f"{deposit_line}{remaining_line}\n\n"
            f"💰 <b>Итого: {grand_total:.2f} сум</b>"
            f"{door_lines}"
        )

    return (
        f"📋 <b>{order['order_number']}</b>\n\n"
        f"👤 Клиент: {order['client_name']}\n"
        f"📞 Телефон: {order['client_phone']}\n"
        f"🪟 Модель: {order['model']}\n"
        f"🧵 Материалы: {order['materials']}{material_options_line}{color_line}\n"
        f"📐 Характеристики: {order.get('characteristics', '—')}"
        f"{dimensions_line}\n"
        f"{tulle_line}{sachak_line}{accessory_line}\n"
        f"🔲 Багет: {order.get('cornice') or '—'}{cornice_rotation_line}\n"
        f"{address_line}"
        f"💬 Комментарий: {order.get('client_comment') or '—'}"
        f"{deadline_line}{overdue_warning}{priority_line}\n\n"
        f"📌 Статус: {status_display(order['status'])}\n\n"
        f"<b>👥 Ответственные:</b>\n"
        f"🛒 Продавец: {seller_name}\n"
        f"⚙️ Админ: {admin_name}\n"
        f"🔧 Мастер: {master_name}\n"
        f"🧵 Швея: {sewer_name}\n"
        f"👷 Установщик: {installer_name}\n\n"
        f"💰 Материалы: {materials_total:.2f} сум\n"
        f"💰 Работа: {work_price:.2f} сум\n"
        f"💰 Залог: {deposit_amount:.2f} сум\n"
        f"💰 Остаток: {remaining:.2f} сум\n"
        f"💰 <b>Итого: {grand_total:.2f} сум</b>"
        f"{door_lines}"
    )


async def generate_qr(order_id: int) -> bytes:
    """Генерация QR-кода для заказа."""
    buffer = io.BytesIO()
    qr = qrcode.make(f"ORDER:{order_id}")
    qr.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================================
# КЛАВИАТУРЫ (ПОЛНОСТЬЮ ПЕРЕРАБОТАНЫ)
# ============================================================================

def get_main_keyboard(role: Role) -> ReplyKeyboardMarkup:
    """Получение главной клавиатуры в зависимости от роли."""
    builder = ReplyKeyboardBuilder()

    if role == Role.CEO:
        buttons = [
            "📊 Дашборд", "👥 Управление ролями", "👥 Сотрудники на смене",
            "📋 Все заказы", "🔍 Поиск заказов", "📤 Экспорт CSV",
            "📤 Экспорт Excel", "📅 Просроченные", "⏰ Начать смену",
            "🏁 Закончить смену", "❓ Помощь"
        ]
        for text in buttons:
            builder.button(text=text)
        builder.adjust(2, 2, 2, 2, 2, 1)

    elif role == Role.ADMIN:
        buttons = [
            "📊 Дашборд", "📋 Заказы на распределение",
            "📋 Заказы от мастеров", "📋 Заказы от швей",
            "👷 Назначить установщика", "📋 Все заказы", "🔍 Поиск заказов",
            "📤 Экспорт CSV", "📤 Экспорт Excel", "📅 Просроченные",
            "⏰ Начать смену", "🏁 Закончить смену", "❓ Помощь"
        ]
        for text in buttons:
            builder.button(text=text)
        builder.adjust(2, 2, 2, 2, 2, 2, 1)

    elif role == Role.SELLER:
        buttons = ["📝 Новый заказ", "📋 Мои заказы", "🔍 Поиск заказов",
                   "⏰ Начать смену", "🏁 Закончить смену", "❓ Помощь"]
        for text in buttons:
            builder.button(text=text)
        builder.adjust(2, 2, 2)

    elif role == Role.MASTER:
        buttons = ["📥 Новые заказы", "📋 Мои заказы",
                   "✅ Готово (передать админу)", "📸 Фото этапа",
                   "⏰ Начать смену", "🏁 Закончить смену", "❓ Помощь"]
        for text in buttons:
            builder.button(text=text)
        builder.adjust(2, 2, 3)

    elif role == Role.SEWER:
        buttons = ["📥 Заказы на пошив", "📋 Мои заказы", "➕ Добавить материал",
                   "✅ Готово (передать админу)", "📸 Фото этапа",
                   "⏰ Начать смену", "🏁 Закончить смену", "❓ Помощь"]
        for text in buttons:
            builder.button(text=text)
        builder.adjust(2, 2, 2, 2)

    elif role == Role.INSTALLER:
        buttons = ["📥 Заказы на установку", "🚚 Выезд на адрес", "📸 Загрузить фото",
                   "✅ Готово (завершить работу)", "📸 Фото этапа",
                   "⏰ Начать смену", "🏁 Закончить смену", "❓ Помощь"]
        for text in buttons:
            builder.button(text=text)
        builder.adjust(2, 2, 2, 2)

    elif role == Role.SMM:
        buttons = ["📊 Дашборд", "📋 Все заказы", "⏰ Начать смену",
                   "🏁 Закончить смену", "❓ Помощь"]
        for text in buttons:
            builder.button(text=text)
        builder.adjust(2, 2, 1)

    return builder.as_markup(resize_keyboard=True)


def get_back_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопками "Назад" и "Отмена"."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Назад")
    builder.button(text="❌ Отмена")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_confirm_back_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопками "Подтвердить", "Назад", "Отмена"."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="✅ Подтвердить")
    builder.button(text="🔙 Назад")
    builder.button(text="❌ Отмена")
    builder.adjust(3)
    return builder.as_markup(resize_keyboard=True)


def get_skip_back_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопками "Пропустить", "Назад", "Отмена"."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="⏭ Пропустить")
    builder.button(text="🔙 Назад")
    builder.button(text="❌ Отмена")
    builder.adjust(3)
    return builder.as_markup(resize_keyboard=True)


def get_photo_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для загрузки фото."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📸 Загрузить фото")
    builder.button(text="✅ Завершить и отправить")
    builder.button(text="🔙 Назад")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_location_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для отправки геолокации."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📍 Отправить геолокацию", request_location=True)
    builder.button(text="🔙 Назад")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_yes_no_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с ответами Да/Нет."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="✅ Да")
    builder.button(text="❌ Нет")
    builder.button(text="🔙 Назад")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_model_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора модели штор."""
    builder = ReplyKeyboardBuilder()
    for model in CURTAIN_MODELS:
        builder.button(text=f"🪟 {model}")
    builder.button(text="🔙 Назад")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_materials_keyboard(selected: Optional[Set[str]] = None) -> ReplyKeyboardMarkup:
    """Клавиатура выбора материалов с множественным выбором."""
    if selected is None:
        selected = set()
    builder = ReplyKeyboardBuilder()
    for material in MATERIALS_LIST:
        if material in selected:
            builder.button(text=f"✅ {material}")
        else:
            builder.button(text=f"⬜ {material}")
    builder.button(text="✅ Подтвердить выбор")
    builder.button(text="🔙 Назад")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_material_options_keyboard(selected: Optional[Set[str]] = None) -> ReplyKeyboardMarkup:
    """Клавиатура выбора опций материала."""
    if selected is None:
        selected = set()
    builder = ReplyKeyboardBuilder()
    for option in MATERIAL_OPTIONS_LIST:
        if option in selected:
            builder.button(text=f"✅ {option}")
        else:
            builder.button(text=f"⬜ {option}")
    builder.button(text="✅ Подтвердить выбор")
    builder.button(text="🔙 Назад")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_color_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора цвета."""
    builder = ReplyKeyboardBuilder()
    for color in COLORS_LIST:
        builder.button(text=f"🎨 {color}")
    builder.button(text="🔙 Назад")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_tulle_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора тюли."""
    builder = ReplyKeyboardBuilder()
    for tulle_type in TULLE_TYPES:
        if tulle_type != "Не нужна":
            builder.button(text=f"🪟 {tulle_type}")
    builder.button(text="🔙 Назад")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_sachak_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора сачака."""
    builder = ReplyKeyboardBuilder()
    for sachak_type in SACHAK_TYPES:
        if sachak_type != "Не нужен":
            builder.button(text=f"🎀 {sachak_type}")
    builder.button(text="🔙 Назад")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_accessory_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора аксессуаров."""
    builder = ReplyKeyboardBuilder()
    for accessory_type in ACCESSORY_TYPES:
        if accessory_type != "Не нужны":
            builder.button(text=f"🎁 {accessory_type}")
    builder.button(text="🔙 Назад")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_address_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для ввода адреса."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📍 Отправить геолокацию", request_location=True)
    builder.button(text="📝 Ввести текстом")
    builder.button(text="⏭ Пропустить")
    builder.button(text="🔙 Назад")
    builder.adjust(1, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_client_menu_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для клиентов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Проверить заказ", callback_data="client_check_order")
    builder.button(text="⭐ Оставить отзыв", callback_data="client_review")
    builder.adjust(1)
    return builder.as_markup()


def get_rating_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для оценки заказа."""
    builder = InlineKeyboardBuilder()
    for rating in range(1, 6):
        stars = "⭐" * rating
        builder.button(text=stars, callback_data=f"rate:{order_id}:{rating}")
    builder.button(text="🔙 Назад", callback_data="client_menu")
    builder.adjust(1)
    return builder.as_markup()


def orders_inline_keyboard(
        orders: List[Dict[str, Any]],
        prefix: str,
        page: int = 0,
        total: int = 0
) -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для списка заказов с пагинацией."""
    builder = InlineKeyboardBuilder()

    today = date.today().isoformat()
    for order in orders[:ORDERS_PER_PAGE]:
        deadline_mark = ""
        if order.get("deadline"):
            if order["deadline"] < today and order["status"] != OrderStatus.COMPLETED.value:
                deadline_mark = " 🔴"
            elif order["deadline"] == today:
                deadline_mark = " 🟡"

        builder.button(
            text=f"{priority_emoji(order.get('priority', Priority.NORMAL.value))} {order['order_number']} — {order['client_name']}{deadline_mark}",
            callback_data=f"{prefix}:{order['id']}:{page}"
        )

    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"page:{prefix}:{page - 1}"))

    total_pages = max(1, (total + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE)
    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))

    if (page + 1) * ORDERS_PER_PAGE < total:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"page:{prefix}:{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.adjust(1)
    return builder.as_markup()


def workers_inline_keyboard(
        workers: List[Dict[str, Any]],
        order_id: int,
        prefix: str
) -> InlineKeyboardMarkup:
    """Инлайн-клавиатура выбора работника."""
    builder = InlineKeyboardBuilder()
    emoji_map = {
        Role.SEWER.value: "🧵",
        Role.INSTALLER.value: "👷",
        Role.MASTER.value: "🔧"
    }

    for worker in workers:
        emoji = emoji_map.get(worker["role"], "👤")
        callback_data = f"{prefix}:{order_id}:{worker['telegram_id']}"
        builder.button(
            text=f"{emoji} {worker['full_name']}",
            callback_data=callback_data
        )

    builder.button(text="🔙 Назад", callback_data=f"back_to_transfer_order:{order_id}")
    builder.adjust(1)
    return builder.as_markup()


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора языка."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang:ru")
    builder.adjust(1)
    return builder.as_markup()


def get_cornice_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура выбора багета."""
    builder = InlineKeyboardBuilder()
    for cornice in CORNICE_TYPES:
        builder.button(text=f"📸 {cornice}", callback_data=f"cornice_select:{cornice}")
        builder.button(text=f"   ℹ️ Фото", callback_data=f"cornice_photo:{cornice}")
    builder.button(text="📝 Свой вариант", callback_data="cornice_manual")
    builder.button(text="🔙 Назад", callback_data="back_to_accessory")
    builder.adjust(2)
    return builder.as_markup()


def get_door_cornice_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура выбора багета для ДВЕРНОЙ шторы."""
    builder = InlineKeyboardBuilder()
    for cornice in CORNICE_TYPES:
        builder.button(text=f"📸 {cornice}", callback_data=f"door_cornice_select:{cornice}")
        builder.button(text=f"   ℹ️ Фото", callback_data=f"door_cornice_photo:{cornice}")
    builder.button(text="📝 Свой вариант", callback_data="door_cornice_manual")
    builder.button(text="🔙 Назад", callback_data="back_to_door_accessory")
    builder.adjust(2)
    return builder.as_markup()


def get_deadline_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура выбора дедлайна."""
    builder = InlineKeyboardBuilder()
    today = date.today()
    for days in [2, 3, 5, 7, 10, 14]:
        deadline_date = today + timedelta(days=days)
        builder.button(
            text=f"📅 +{days} дн. ({deadline_date:%d.%m})",
            callback_data=f"deadline_days:{days}"
        )
    builder.button(text="📝 Ввести вручную", callback_data="deadline_manual")
    builder.button(text="🔙 Назад", callback_data="back_to_cornice_rotation")
    builder.adjust(2)
    return builder.as_markup()


def get_priority_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура выбора приоритета."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 Обычный", callback_data="priority:normal")
    builder.button(text="🟡 Срочный", callback_data="priority:urgent")
    builder.button(text="🔴 Критический", callback_data="priority:critical")
    builder.button(text="🔙 Назад", callback_data="back_to_deadline")
    builder.adjust(3, 1)
    return builder.as_markup()


def get_search_filter_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура фильтров поиска."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔎 Поиск", callback_data="search_prompt")
    builder.button(text="📌 Статус", callback_data="filter_status_menu")
    builder.button(text="📅 Просроченные", callback_data="show_overdue")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(2, 2)
    return builder.as_markup()


def get_statuses_inline_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора статуса для фильтрации."""
    builder = InlineKeyboardBuilder()
    for status in OrderStatus:
        builder.button(text=status_display(status.value), callback_data=f"filter_status:{status.value}")
    builder.button(text="🔄 Все", callback_data="filter_status:all")
    builder.button(text="🔙 Назад", callback_data="back_to_search")
    builder.adjust(2)
    return builder.as_markup()


def get_order_detail_keyboard(order_id: int, role: Role) -> InlineKeyboardMarkup:
    """Клавиатура деталей заказа."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Комментарии", callback_data=f"comments:{order_id}")
    builder.button(text="📜 История", callback_data=f"history:{order_id}")
    builder.button(text="📸 Фото по этапам", callback_data=f"photos_by_stage:{order_id}")
    builder.button(text="🔗 QR-код", callback_data=f"qr_code:{order_id}")
    builder.button(text="🗺 Маршрут", callback_data=f"navigate:{order_id}")

    if role in (Role.CEO, Role.ADMIN, Role.SELLER):
        builder.button(text="✏️ Редактировать", callback_data=f"edit_order:{order_id}")

    if role in (Role.CEO, Role.ADMIN):
        builder.button(text="🗑 Удалить заказ", callback_data=f"delete_order:{order_id}")

    builder.button(text="🔙 Назад", callback_data="back_to_list")
    builder.adjust(2, 2, 2, 1, 1, 1)
    return builder.as_markup()


def get_photo_stage_keyboard(order_id: int, current_stage: str = "general") -> InlineKeyboardMarkup:
    """Клавиатура выбора этапа для фото."""
    builder = InlineKeyboardBuilder()
    stages = [
        ("📏 Замеры", PhotoStage.MEASUREMENT.value),
        ("🧵 Ткань", PhotoStage.FABRIC.value),
        ("✂️ Раскрой", PhotoStage.CUTTING.value),
        ("🪡 Пошив", PhotoStage.SEWING_PROCESS.value),
        ("✅ Готово", PhotoStage.READY.value),
        ("🏠 До установки", PhotoStage.INSTALL_BEFORE.value),
        ("🎉 После установки", PhotoStage.INSTALL_AFTER.value)
    ]

    for text, stage in stages:
        mark = "✅ " if stage == current_stage else ""
        builder.button(text=f"{mark}{text}", callback_data=f"photo_stage:{order_id}:{stage}")

    builder.button(text="🔙 Назад", callback_data=f"view_order:{order_id}:0")
    builder.adjust(2)
    return builder.as_markup()


def get_edit_fields_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора поля для редактирования."""
    builder = InlineKeyboardBuilder()
    fields = [
        ("👤 Имя клиента", "client_name"),
        ("📞 Телефон", "client_phone"),
        ("🪟 Модель", "model"),
        ("🧵 Материалы", "materials"),
        ("✨ Опции материала", "material_options"),
        ("🎨 Цвет", "color"),
        ("📐 Характеристики", "characteristics"),
        ("🔲 Багет", "cornice"),
        ("🪟 Тюль", "tulle"),
        ("🎀 Сачак", "sachak"),
        ("🎁 Аксессуар", "accessory"),
        ("📍 Адрес", "install_address"),
        ("📅 Дедлайн", "deadline"),
        ("⭐ Приоритет", "priority"),
        ("💰 Стоимость работы", "work_price"),
        ("💰 Залог", "deposit"),
        ("💰 Остаток", "remaining_payment"),
        ("💬 Комментарий", "client_comment")
    ]

    for text, callback_data in fields:
        builder.button(text=text, callback_data=f"edit:{callback_data}:{order_id}")

    builder.button(text="🔙 Назад", callback_data=f"view_order:{order_id}:0")
    builder.adjust(2)
    return builder.as_markup()


def get_purchase_action_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий после добавления материала."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить ещё", callback_data=f"add_more:{order_id}")
    builder.button(text="✅ Завершить", callback_data=f"finish_purch:{order_id}")
    builder.button(text="🔙 Назад", callback_data=f"back_to_sewer_menu")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_users_inline_keyboard(users: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура выбора пользователя для управления ролями."""
    builder = InlineKeyboardBuilder()
    for user in users:
        username_display = f" (@{user['username']})" if user.get("username") else ""
        builder.button(
            text=f"👤 {user['full_name']}{username_display}",
            callback_data=f"set_role:{user['telegram_id']}"
        )
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_roles_inline_keyboard(target_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора роли для назначения."""
    builder = InlineKeyboardBuilder()
    roles_list = [
        ("⚙️ Администратор", "admin"),
        ("🛒 Продавец", "seller"),
        ("🔧 Мастер", "master"),
        ("🧵 Швея", "sewer"),
        ("👷 Установщик", "installer"),
        ("📱 SMM", "smm")
    ]
    for text, role in roles_list:
        builder.button(text=text, callback_data=f"confirm_role:{target_id}:{role}")
    builder.button(text="🔙 Назад", callback_data="back_to_users_list")
    builder.adjust(1)
    return builder.as_markup()


def get_delete_confirm_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Да, удалить", callback_data=f"confirm_delete:{order_id}")
    builder.button(text="🔙 Назад", callback_data=f"view_order:{order_id}:0")
    builder.adjust(1)
    return builder.as_markup()


# ============================================================================
# FSM СОСТОЯНИЯ
# ============================================================================

class OrderCreationFSM(StatesGroup):
    """Состояния создания заказа."""
    client_name = State()
    client_phone = State()
    install_address = State()
    waiting_address_text = State()
    model = State()
    materials = State()
    material_options = State()
    color = State()
    tulle = State()
    tulle_type = State()
    sachak = State()
    sachak_type = State()
    accessory = State()
    accessory_type = State()
    dimensions = State()
    cornice = State()
    cornice_rotation = State()
    door_needed = State()
    door_model = State()
    door_material = State()
    door_material_options = State()
    door_color = State()
    door_dimensions = State()
    door_sachak = State()
    door_sachak_type = State()
    door_accessory = State()
    door_accessory_type = State()
    door_cornice = State()
    door_cornice_rotation = State()
    deadline = State()
    priority = State()
    work_price = State()
    deposit_amount = State()
    deposit = State()
    remaining_payment = State()
    client_comment = State()
    confirm = State()


class PurchaseFSM(StatesGroup):
    """Состояния добавления закупки."""
    order_id = State()
    material_name = State()
    price = State()
    confirm = State()


class PhotoStageFSM(StatesGroup):
    """Состояния загрузки фото по этапам."""
    order_id = State()
    stage = State()
    photos = State()


class InstallerPhotoFSM(StatesGroup):
    """Состояния загрузки фото установщиком."""
    order_id = State()
    before_photos = State()
    after_photos = State()
    confirm = State()


class SearchFSM(StatesGroup):
    """Состояния поиска."""
    waiting_query = State()


class EditFSM(StatesGroup):
    """Состояния редактирования заказа."""
    order_id = State()
    field = State()
    value = State()


class ClientFSM(StatesGroup):
    """Состояния клиентского меню."""
    phone = State()
    order_check = State()
    review_rating = State()
    review_text = State()


class AdminCommentFSM(StatesGroup):
    """Состояния добавления комментария администратором."""
    order_id = State()
    next_action = State()
    target_id = State()
    comment = State()


class RejectFSM(StatesGroup):
    """Состояния отклонения заказа."""
    order_id = State()
    reason = State()


class TempState(StatesGroup):
    """Временное состояние для хранения order_id."""
    temp_order_id = State()


# ============================================================================
# ОБЩИЕ ОБРАБОТЧИКИ
# ============================================================================

@dp.message(Command("start"))
async def command_start(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start."""
    await state.clear()
    user_id = message.from_user.id

    if not is_registered(user_id):
        await message.answer(
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Это бот шторной мастерской.\n"
            "Вы можете проверить статус заказа или оставить отзыв.",
            reply_markup=get_client_menu_keyboard()
        )
        return

    user = await get_user_data(user_id, message.from_user.full_name, message.from_user.username)
    role = Role(user["role"])

    greetings = {
        Role.CEO: "👑 Добро пожаловать, CEO!",
        Role.ADMIN: "⚙️ Добро пожаловать, Администратор!",
        Role.SELLER: "🛒 Добро пожаловать, Продавец!",
        Role.MASTER: "🔧 Добро пожаловать, Мастер!",
        Role.SEWER: "🧵 Добро пожаловать, Швея!",
        Role.INSTALLER: "👷 Добро пожаловать, Установщик!",
        Role.SMM: "📱 Добро пожаловать, SMM!",
    }

    shift_message = ""
    if role not in (Role.CEO, Role.ADMIN, Role.SMM):
        on_shift = await db.is_on_shift(user_id)
        shift_message = "\n\n✅ Вы на смене" if on_shift else "\n\n⚠️ Нажмите «⏰ Начать смену»"

    if not user.get("lang"):
        await message.answer(
            f"{greetings.get(role, 'Привет!')}\n\nВыберите язык:",
            reply_markup=get_language_keyboard()
        )
        return

    await db.audit(user_id, "start")
    await message.answer(
        greetings.get(role, "Привет!") + shift_message,
        reply_markup=get_main_keyboard(role)
    )


@dp.message(F.text == "❌ Отмена")
async def button_cancel(message: Message, state: FSMContext) -> None:
    """Обработчик кнопки "Отмена"."""
    await state.clear()
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    role = Role(user["role"]) if user else Role.SELLER
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=get_main_keyboard(role)
    )


@dp.callback_query(F.data == "noop")
async def callback_noop(callback: CallbackQuery) -> None:
    """Пустой обработчик для неактивных кнопок."""
    await callback.answer()


@dp.callback_query(F.data.startswith("lang:"))
async def callback_set_language(callback: CallbackQuery, state: FSMContext) -> None:
    """Установка языка пользователя."""
    language = callback.data.split(":")[1]
    user_id = callback.from_user.id

    await db.update_user_language(user_id, language)
    await db.audit(user_id, "set_language", details=language)

    user = await db.get_user(user_id)
    role = Role(user["role"]) if user else Role.SELLER

    await callback.message.delete()
    await callback.message.answer(
        f"✅ Язык установлен: {language}",
        reply_markup=get_main_keyboard(role)
    )
    await callback.answer()


@dp.message(Command("help"))
@dp.message(F.text == "❓ Помощь")
async def command_help(message: Message) -> None:
    """Обработчик команды помощи."""
    help_text = (
        "📖 <b>Помощь по боту</b>\n\n"
        "📝 Новый заказ — создать заказ\n"
        "📋 Мои заказы — просмотр ваших заказов\n"
        "📸 Фото этапа — добавить фото к заказу\n"
        "✅ Готово (передать админу) — завершить этап работы\n"
        "➕ Добавить материал — добавить расход материала (швея)\n\n"
        "По вопросам обращайтесь к администратору."
    )
    await message.answer(help_text)


# ============================================================================
# СОЗДАНИЕ ЗАКАЗА (ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ)
# ============================================================================

@dp.message(F.text == "📝 Новый заказ")
async def start_order_creation(message: Message, state: FSMContext) -> None:
    """Начало создания нового заказа."""
    user_id = message.from_user.id

    if not is_registered(user_id):
        return

    user = await db.get_user(user_id)
    if not user:
        return
    if Role(user["role"]) not in (Role.SELLER, Role.CEO, Role.ADMIN):
        await message.answer("🚫 Нет доступа.")
        return

    if not await db.is_on_shift(user_id) and Role(user["role"]) not in (Role.CEO, Role.ADMIN):
        await message.answer("⚠️ Начните смену для создания заказа.")
        return

    await state.set_state(OrderCreationFSM.client_name)
    await message.answer(
        "📝 <b>Создание заказа</b>\n\n"
        "Шаг 1 из 22: <b>Имя клиента</b>\n"
        "Введите имя клиента:",
        reply_markup=get_back_cancel_keyboard()
    )


@dp.message(OrderCreationFSM.client_name)
async def order_step_client_name(message: Message, state: FSMContext) -> None:
    """Шаг 1: Имя клиента."""
    if message.text in ("❌ Отмена", "🔙 Назад"):
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if len(message.text.strip()) < 2:
        await message.answer("❌ Имя слишком короткое. Введите полное имя клиента:", reply_markup=get_back_cancel_keyboard())
        return

    await state.update_data(client_name=message.text.strip())
    await state.set_state(OrderCreationFSM.client_phone)
    await message.answer(
        "Шаг 2 из 22: <b>Телефон и Telegram</b>\n\n"
        "Введите номер телефона (например: <code>77 623 8118</code>)\n"
        "Бот автоматически добавит +998\n\n"
        "Если есть Telegram username: <code>77 623 8118 @username</code>",
        reply_markup=get_back_cancel_keyboard()
    )


@dp.message(OrderCreationFSM.client_phone)
async def order_step_client_phone(message: Message, state: FSMContext) -> None:
    """Шаг 2: Телефон клиента."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.client_name)
        await message.answer("Шаг 1 из 22: <b>Имя клиента</b>\nВведите имя:", reply_markup=get_back_cancel_keyboard())
        return

    text = message.text.strip()
    parts = text.split()
    phone = parts[0]
    username = " ".join(parts[1:]) if len(parts) > 1 else ""

    if not validate_phone(phone):
        await message.answer(
            "❌ Неверный формат телефона!\nПримеры: <code>77 623 8118</code> или <code>998776238118</code>",
            reply_markup=get_back_cancel_keyboard()
        )
        return

    formatted_phone = format_phone(phone)
    client_telegram_id = None

    if username:
        if not username.startswith("@"):
            try:
                client_telegram_id = int(username)
                username = ""
            except ValueError:
                pass

    await state.update_data(client_phone=formatted_phone, client_tg_id=client_telegram_id)
    await state.set_state(OrderCreationFSM.install_address)
    await message.answer(
        "Шаг 3 из 22: <b>Адрес установки</b>\n\n"
        "Отправьте геолокацию или введите адрес текстом:",
        reply_markup=get_address_keyboard()
    )


@dp.message(OrderCreationFSM.install_address)
async def order_step_install_address(message: Message, state: FSMContext) -> None:
    """Шаг 3: Адрес установки."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.client_phone)
        await message.answer("Шаг 2 из 22: <b>Телефон клиента</b>\nВведите номер:", reply_markup=get_back_cancel_keyboard())
        return

    if message.text == "⏭ Пропустить":
        await state.update_data(install_address=None, install_lat=None, install_lon=None)

    elif message.text == "📝 Ввести текстом":
        await state.set_state(OrderCreationFSM.waiting_address_text)
        await message.answer("📝 Введите адрес установки текстом:", reply_markup=get_back_cancel_keyboard())
        return

    elif message.location:
        latitude = message.location.latitude
        longitude = message.location.longitude
        await state.update_data(install_address=f"📍 {latitude}, {longitude}", install_lat=latitude, install_lon=longitude)
    else:
        await message.answer(
            "❌ Отправьте геолокацию, введите адрес текстом или нажмите «Пропустить»:",
            reply_markup=get_address_keyboard()
        )
        return

    await state.set_state(OrderCreationFSM.model)
    await message.answer("Шаг 4 из 22: <b>Выберите модель штор:</b>", reply_markup=get_model_keyboard())


@dp.message(OrderCreationFSM.waiting_address_text)
async def order_step_address_text(message: Message, state: FSMContext) -> None:
    """Обработка текстового адреса."""
    if message.text in ("❌ Отмена", "🔙 Назад"):
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    await state.update_data(install_address=message.text.strip(), install_lat=None, install_lon=None)
    await state.set_state(OrderCreationFSM.model)
    await message.answer("Шаг 4 из 22: <b>Выберите модель штор:</b>", reply_markup=get_model_keyboard())


# ============================================================================
# ПРОДОЛЖЕНИЕ СОЗДАНИЯ ЗАКАЗА
# ============================================================================

@dp.message(OrderCreationFSM.model)
async def order_step_model(message: Message, state: FSMContext) -> None:
    """Шаг 4: Модель штор."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.install_address)
        await message.answer(
            "Шаг 3 из 22: <b>Адрес установки</b>\n\nОтправьте геолокацию или введите адрес:",
            reply_markup=get_address_keyboard()
        )
        return

    model = message.text.strip().replace("🪟 ", "")
    if model not in CURTAIN_MODELS:
        await message.answer("❌ Выберите модель из списка:", reply_markup=get_model_keyboard())
        return

    await state.update_data(model=model, selected_materials=set())
    await state.set_state(OrderCreationFSM.materials)
    await message.answer(
        f"✅ Модель: <b>{model}</b>\n\n"
        "Шаг 5 из 22: <b>Материалы</b>\n"
        "Выберите один или несколько материалов (нажмите для выбора):\n"
        "Когда закончите, нажмите «✅ Подтвердить выбор»",
        reply_markup=get_materials_keyboard(set())
    )


@dp.message(OrderCreationFSM.materials)
async def order_step_materials(message: Message, state: FSMContext) -> None:
    """Шаг 5: Выбор материалов."""
    data = await state.get_data()
    selected = set(data.get("selected_materials", []))

    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.model)
        await message.answer("Шаг 4 из 22: <b>Модель штор</b>\nВыберите модель:", reply_markup=get_model_keyboard())
        return

    text = message.text.strip()

    if text.startswith("✅ "):
        text = text[2:]
    elif text.startswith("⬜ "):
        text = text[2:]

    if text == "Подтвердить выбор":
        if not selected:
            await message.answer("❌ Выберите хотя бы один материал:", reply_markup=get_materials_keyboard(selected))
            return

        materials_str = ", ".join(sorted(selected))
        await state.update_data(materials=materials_str)

        if len(selected) == 1:
            await state.update_data(selected_material_options=set())
            await state.set_state(OrderCreationFSM.material_options)
            await message.answer(
                f"✅ Материалы: <b>{materials_str}</b>\n\n"
                "Шаг 6 из 22: <b>Опции материала</b>\n"
                "Выберите один или несколько:\n"
                "Когда закончите, нажмите «✅ Подтвердить выбор»",
                reply_markup=get_material_options_keyboard(set())
            )
        else:
            await state.update_data(material_options=None)
            await state.set_state(OrderCreationFSM.color)
            await message.answer(
                f"✅ Материалы: <b>{materials_str}</b> (несколько материалов — опции пропущены)\n\n"
                "Шаг 7 из 22: <b>Цвет материала</b>\n"
                "Выберите цвет:",
                reply_markup=get_color_keyboard()
            )
        return

    if text in MATERIALS_LIST:
        if text in selected:
            selected.discard(text)
            await message.answer(f"➖ Материал <b>{text}</b> убран.\nВыбрано: {', '.join(sorted(selected)) if selected else 'пока ничего'}")
        else:
            selected.add(text)
            await message.answer(f"➕ Материал <b>{text}</b> добавлен.\nВыбрано: {', '.join(sorted(selected))}")

        await state.update_data(selected_materials=selected)
        await message.answer(
            "Шаг 5 из 22: <b>Материалы</b>\nКогда закончите, нажмите «✅ Подтвердить выбор»:",
            reply_markup=get_materials_keyboard(selected)
        )
    else:
        await message.answer("❌ Выберите материал из списка или нажмите «Подтвердить выбор»:", reply_markup=get_materials_keyboard(selected))


@dp.message(OrderCreationFSM.material_options)
async def order_step_material_options(message: Message, state: FSMContext) -> None:
    """Шаг 6: Опции материала."""
    data = await state.get_data()
    selected = set(data.get("selected_material_options", []))

    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.materials)
        old_selected = set(data.get("selected_materials", []))
        await message.answer("Шаг 5 из 22: <b>Материалы</b>\nВыберите материалы:", reply_markup=get_materials_keyboard(old_selected))
        return

    text = message.text.strip()

    if text.startswith("✅ "):
        text = text[2:]
    elif text.startswith("⬜ "):
        text = text[2:]

    if text == "Подтвердить выбор":
        options_str = ", ".join(sorted(selected)) if selected else None
        await state.update_data(material_options=options_str)
        await state.set_state(OrderCreationFSM.color)
        await message.answer(
            f"✅ Опции: <b>{options_str or '—'}</b>\n\n"
            "Шаг 7 из 22: <b>Цвет материала</b>\n"
            "Выберите цвет:",
            reply_markup=get_color_keyboard()
        )
        return

    if text in MATERIAL_OPTIONS_LIST:
        if text in selected:
            selected.discard(text)
            await message.answer(f"➖ Опция <b>{text}</b> убрана.\nВыбрано: {', '.join(sorted(selected)) if selected else 'пока ничего'}")
        else:
            selected.add(text)
            await message.answer(f"➕ Опция <b>{text}</b> добавлена.\nВыбрано: {', '.join(sorted(selected))}")

        await state.update_data(selected_material_options=selected)
        await message.answer(
            "Шаг 6 из 22: <b>Опции материала</b>\nКогда закончите, нажмите «✅ Подтвердить выбор»:",
            reply_markup=get_material_options_keyboard(selected)
        )
    else:
        await message.answer("❌ Выберите опцию из списка или нажмите «Подтвердить выбор»:", reply_markup=get_material_options_keyboard(selected))


@dp.message(OrderCreationFSM.color)
async def order_step_color(message: Message, state: FSMContext) -> None:
    """Шаг 7: Выбор цвета."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        data = await state.get_data()
        materials = data.get("materials", "")
        material_list = [m.strip() for m in materials.split(",") if m.strip()]

        if len(material_list) == 1:
            await state.set_state(OrderCreationFSM.material_options)
            await message.answer("Шаг 6 из 22: <b>Опции материала</b>\nВыберите опции:", reply_markup=get_material_options_keyboard(set()))
        else:
            await state.set_state(OrderCreationFSM.materials)
            await message.answer("Шаг 5 из 22: <b>Материалы</b>\nВыберите материалы:", reply_markup=get_materials_keyboard(set(data.get("selected_materials", []))))
        return

    color = message.text.strip().replace("🎨 ", "")
    if color not in COLORS_LIST:
        await message.answer("❌ Выберите цвет из списка:", reply_markup=get_color_keyboard())
        return

    await state.update_data(color=color)
    await state.set_state(OrderCreationFSM.tulle)
    await message.answer(f"✅ Цвет: <b>{color}</b>\n\nШаг 8 из 22: <b>Нужна тюль?</b>", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.tulle)
async def order_step_tulle(message: Message, state: FSMContext) -> None:
    """Шаг 8: Нужна ли тюль."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.color)
        await message.answer("Шаг 7 из 22: <b>Цвет материала</b>\nВыберите цвет:", reply_markup=get_color_keyboard())
        return

    if message.text == "✅ Да":
        await state.set_state(OrderCreationFSM.tulle_type)
        await message.answer("Шаг 8a из 22: <b>Выберите тип тюли:</b>", reply_markup=get_tulle_keyboard())
    elif message.text == "❌ Нет":
        await state.update_data(tulle="Не нужна")
        await state.set_state(OrderCreationFSM.sachak)
        await message.answer("Шаг 9 из 22: <b>Нужен сачак?</b>", reply_markup=get_yes_no_keyboard())
    else:
        await message.answer("❌ Выберите «Да» или «Нет»:", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.tulle_type)
async def order_step_tulle_type(message: Message, state: FSMContext) -> None:
    """Шаг 8a: Выбор типа тюли."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.tulle)
        await message.answer("Шаг 8 из 22: <b>Нужна тюль?</b>", reply_markup=get_yes_no_keyboard())
        return

    tulle = message.text.strip().replace("🪟 ", "")
    if tulle not in TULLE_TYPES or tulle == "Не нужна":
        await message.answer("❌ Выберите тип тюли из списка:", reply_markup=get_tulle_keyboard())
        return

    await state.update_data(tulle=tulle)
    await state.set_state(OrderCreationFSM.sachak)
    await message.answer(f"✅ Тюль: <b>{tulle}</b>\n\nШаг 9 из 22: <b>Нужен сачак?</b>", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.sachak)
async def order_step_sachak(message: Message, state: FSMContext) -> None:
    """Шаг 9: Нужен ли сачак."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.tulle)
        data = await state.get_data()
        if data.get("tulle") == "Не нужна":
            await message.answer("Шаг 8 из 22: <b>Нужна тюль?</b>", reply_markup=get_yes_no_keyboard())
        else:
            await state.set_state(OrderCreationFSM.tulle_type)
            await message.answer("Шаг 8a из 22: <b>Выберите тип тюли:</b>", reply_markup=get_tulle_keyboard())
        return

    if message.text == "✅ Да":
        await state.set_state(OrderCreationFSM.sachak_type)
        await message.answer("Шаг 9a из 22: <b>Выберите тип сачака:</b>", reply_markup=get_sachak_keyboard())
    elif message.text == "❌ Нет":
        await state.update_data(sachak="Не нужен")
        await state.set_state(OrderCreationFSM.accessory)
        await message.answer("Шаг 10 из 22: <b>Нужен аксессуар?</b>", reply_markup=get_yes_no_keyboard())
    else:
        await message.answer("❌ Выберите «Да» или «Нет»:", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.sachak_type)
async def order_step_sachak_type(message: Message, state: FSMContext) -> None:
    """Шаг 9a: Выбор типа сачака."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.sachak)
        await message.answer("Шаг 9 из 22: <b>Нужен сачак?</b>", reply_markup=get_yes_no_keyboard())
        return

    sachak = message.text.strip().replace("🎀 ", "")
    if sachak not in SACHAK_TYPES or sachak == "Не нужен":
        await message.answer("❌ Выберите тип сачака из списка:", reply_markup=get_sachak_keyboard())
        return

    await state.update_data(sachak=sachak)
    await state.set_state(OrderCreationFSM.accessory)
    await message.answer(f"✅ Сачак: <b>{sachak}</b>\n\nШаг 10 из 22: <b>Нужен аксессуар?</b>", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.accessory)
async def order_step_accessory(message: Message, state: FSMContext) -> None:
    """Шаг 10: Нужен ли аксессуар."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.sachak)
        data = await state.get_data()
        if data.get("sachak") == "Не нужен":
            await message.answer("Шаг 9 из 22: <b>Нужен сачак?</b>", reply_markup=get_yes_no_keyboard())
        else:
            await state.set_state(OrderCreationFSM.sachak_type)
            await message.answer("Шаг 9a из 22: <b>Выберите тип сачака:</b>", reply_markup=get_sachak_keyboard())
        return

    if message.text == "✅ Да":
        await state.set_state(OrderCreationFSM.accessory_type)
        await message.answer("Шаг 10a из 22: <b>Выберите аксессуар:</b>", reply_markup=get_accessory_keyboard())
    elif message.text == "❌ Нет":
        await state.update_data(accessory="Не нужны")
        await state.set_state(OrderCreationFSM.dimensions)
        await message.answer(
            "Шаг 11 из 22: <b>Размеры штор</b>\n\n"
            "Введите: <b>Ширина х Высота</b> (см)\n"
            "Пример: <code>150х200</code> или <code>150x200</code> или <code>150×200</code>",
            reply_markup=get_back_cancel_keyboard()
        )
    else:
        await message.answer("❌ Выберите «Да» или «Нет»:", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.accessory_type)
async def order_step_accessory_type(message: Message, state: FSMContext) -> None:
    """Шаг 10a: Выбор аксессуара."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.accessory)
        await message.answer("Шаг 10 из 22: <b>Нужен аксессуар?</b>", reply_markup=get_yes_no_keyboard())
        return

    accessory = message.text.strip().replace("🎁 ", "")
    if accessory not in ACCESSORY_TYPES or accessory == "Не нужны":
        await message.answer("❌ Выберите аксессуар из списка:", reply_markup=get_accessory_keyboard())
        return

    await state.update_data(accessory=accessory)
    await state.set_state(OrderCreationFSM.dimensions)
    await message.answer(
        f"✅ Аксессуар: <b>{accessory}</b>\n\n"
        "Шаг 11 из 22: <b>Размеры штор</b>\n\n"
        "Введите: <b>Ширина х Высота</b> (см)\n"
        "Пример: <code>150х200</code> или <code>150x200</code> или <code>150×200</code>",
        reply_markup=get_back_cancel_keyboard()
    )


@dp.message(OrderCreationFSM.dimensions)
async def order_step_dimensions(message: Message, state: FSMContext) -> None:
    """Шаг 11: Размеры штор."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.accessory)
        data = await state.get_data()
        if data.get("accessory") == "Не нужны":
            await message.answer("Шаг 10 из 22: <b>Нужен аксессуар?</b>", reply_markup=get_yes_no_keyboard())
        else:
            await state.set_state(OrderCreationFSM.accessory_type)
            await message.answer("Шаг 10a из 22: <b>Выберите аксессуар:</b>", reply_markup=get_accessory_keyboard())
        return

    parsed = parse_dimensions(message.text.strip())
    if not parsed:
        await message.answer(
            "❌ Неверный формат!\nВведите: <b>Ширина х Высота</b> (см)\n"
            "Примеры: <code>150х200</code>, <code>150x200</code>, <code>150×200</code>, <code>150 200</code>",
            reply_markup=get_back_cancel_keyboard()
        )
        return

    width, height, area = parsed
    await state.update_data(dimensions=f"{width:.0f}x{height:.0f}", area_m2=round(area, 4))
    await state.set_state(OrderCreationFSM.cornice)
    await message.answer(
        f"📐 Размеры: {width:.0f} x {height:.0f} см\n\n"
        "Шаг 12 из 22: <b>Багет / Карниз</b>\n"
        "Выберите тип (нажмите ℹ️ Фото для просмотра):",
        reply_markup=get_cornice_inline_keyboard()
    )


# ============================================================================
# БАГЕТ - ИСПРАВЛЕННЫЕ ОБРАБОТЧИКИ
# ============================================================================

@dp.callback_query(F.data.startswith("cornice_select:"))
async def order_callback_cornice_select(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор багета из списка."""
    cornice = callback.data.split(":", 1)[1]
    await state.update_data(cornice=cornice)
    await state.set_state(OrderCreationFSM.cornice_rotation)

    # Удаляем старое сообщение с inline-клавиатурой
    await callback.message.delete()

    # Отправляем новое
    await callback.message.answer(
        f"✅ Багет: <b>{cornice}</b>\n\n"
        "Шаг 13 из 22: <b>Нужен поворот для багета?</b>\n\n"
        "Выберите опцию:",
        reply_markup=get_yes_no_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("cornice_photo:"))
async def order_callback_cornice_photo(callback: CallbackQuery) -> None:
    """Просмотр фото багета."""
    cornice = callback.data.split(":", 1)[1]
    await send_catalog_photo(callback.from_user.id, cornice, f"📸 <b>{cornice}</b>", category="cornices")
    await callback.answer("📸 Фото отправлено")


@dp.callback_query(F.data == "cornice_manual")
async def order_callback_cornice_manual(callback: CallbackQuery, state: FSMContext) -> None:
    """Ручной ввод багета."""
    await state.set_state(OrderCreationFSM.cornice)
    await callback.message.delete()
    await callback.message.answer("📝 Введите название багета вручную:", reply_markup=get_back_cancel_keyboard())
    await callback.answer()


@dp.message(OrderCreationFSM.cornice)
async def order_step_cornice_text(message: Message, state: FSMContext) -> None:
    """Ручной ввод багета."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.dimensions)
        await message.answer("Шаг 11 из 22: <b>Размеры штор</b>\nВведите размеры:", reply_markup=get_back_cancel_keyboard())
        return

    await state.update_data(cornice=message.text.strip())
    await state.set_state(OrderCreationFSM.cornice_rotation)
    await message.answer(
        f"✅ Багет: <b>{message.text.strip()}</b>\n\n"
        "Шаг 13 из 22: <b>Нужен поворот для багета?</b>",
        reply_markup=get_yes_no_keyboard()
    )


@dp.message(OrderCreationFSM.cornice_rotation)
async def order_step_cornice_rotation(message: Message, state: FSMContext) -> None:
    """Шаг 13: Поворот багета."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.cornice)
        await message.answer("Шаг 12 из 22: <b>Багет / Карниз</b>\nВыберите тип:", reply_markup=get_cornice_inline_keyboard())
        return

    if message.text == "✅ Да":
        await state.update_data(cornice_rotation="Да")
    elif message.text == "❌ Нет":
        await state.update_data(cornice_rotation="Нет")
    else:
        await message.answer("❌ Выберите «Да» или «Нет»:", reply_markup=get_yes_no_keyboard())
        return

    # ПЕРЕХОД К ДЕДЛАЙНУ
    await state.set_state(OrderCreationFSM.deadline)
    await message.answer(
        "Шаг 14 из 22: <b>Дедлайн</b>\n\n"
        "Выберите срок выполнения:",
        reply_markup=get_deadline_inline_keyboard()
    )


# ============================================================================
# ДЕДЛАЙН
# ============================================================================

@dp.callback_query(F.data.startswith("deadline_days:"))
async def order_callback_deadline_days(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор дедлайна в днях."""
    days = int(callback.data.split(":")[1])
    deadline_date = date.today() + timedelta(days=days)
    deadline_str = deadline_date.strftime("%Y-%m-%d")
    await state.update_data(deadline=deadline_str)
    await state.set_state(OrderCreationFSM.priority)

    # Редактируем сообщение с inline-клавиатурой приоритета
    await callback.message.edit_text(
        f"✅ Дедлайн: {deadline_date.strftime('%d.%m.%Y')}\n\n"
        "Шаг 15 из 22: <b>Приоритет заказа</b>\n"
        "Выберите приоритет:",
        reply_markup=get_priority_inline_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "deadline_manual")
async def order_callback_deadline_manual(callback: CallbackQuery, state: FSMContext) -> None:
    """Ручной ввод дедлайна."""
    await state.set_state(OrderCreationFSM.deadline)
    await callback.message.edit_text(
        "📅 Введите дату дедлайна в формате: <code>2025-12-31</code> или <code>31.12.2025</code>"
    )
    await callback.message.answer("Или выберите действие:", reply_markup=get_back_cancel_keyboard())
    await callback.answer()


@dp.message(OrderCreationFSM.deadline)
async def order_step_deadline(message: Message, state: FSMContext) -> None:
    """Обработка ручного ввода дедлайна."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.cornice_rotation)
        await message.answer("Шаг 13 из 22: <b>Нужен поворот для багета?</b>", reply_markup=get_yes_no_keyboard())
        return

    if not validate_date(message.text.strip()):
        await message.answer(
            "❌ Неверный формат даты!\nВведите в формате: <code>2025-12-31</code> или <code>31.12.2025</code>",
            reply_markup=get_back_cancel_keyboard()
        )
        return

    deadline_str = normalize_date(message.text.strip())
    await state.update_data(deadline=deadline_str)
    await state.set_state(OrderCreationFSM.priority)
    await message.answer(
        f"✅ Дедлайн: {deadline_str}\n\n"
        "Шаг 15 из 22: <b>Приоритет заказа</b>\n"
        "Выберите приоритет:",
        reply_markup=get_priority_inline_keyboard()
    )


# ============================================================================
# ПРИОРИТЕТ
# ============================================================================

@dp.callback_query(F.data.startswith("priority:"))
async def order_callback_priority(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор приоритета заказа."""
    priority = callback.data.split(":")[1]
    await state.update_data(priority=priority)
    await state.set_state(OrderCreationFSM.door_needed)

    # 1. СНАЧАЛА редактируем сообщение, убираем inline-клавиатуру
    await callback.message.edit_text(
        f"✅ Приоритет: {priority_display(priority)}\n\n"
        "Шаг 16 из 22: <b>Нужна штора на дверь?</b>"
    )

    # 2. ПОТОМ отправляем НОВОЕ сообщение с обычной клавиатурой
    await callback.message.answer(
        "Выберите опцию:",
        reply_markup=get_yes_no_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_deadline")
async def back_to_deadline(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору дедлайна."""
    await state.set_state(OrderCreationFSM.deadline)
    await callback.message.edit_text(
        "Шаг 14 из 22: <b>Дедлайн</b>\n\n"
        "Выберите срок выполнения:",
        reply_markup=get_deadline_inline_keyboard()
    )
    await callback.answer()


# ============================================================================
# ДВЕРНАЯ ШТОРА (ПОД-ЗАКАЗ) - ИСПРАВЛЕННАЯ ВЕРСИЯ
# ============================================================================

@dp.message(OrderCreationFSM.door_needed)
async def order_step_door_needed(message: Message, state: FSMContext) -> None:
    """Шаг 16: Нужна ли дверная штора."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.priority)
        await message.answer(
            "Шаг 15 из 22: <b>Приоритет заказа</b>\n\n"
            "Выберите приоритет:",
            reply_markup=get_priority_inline_keyboard()
        )
        return

    if message.text == "✅ Да":
        await state.set_state(OrderCreationFSM.door_model)
        await message.answer(
            "🚪 <b>Создание дверной шторы</b>\n\n"
            "Шаг 16a из 11: <b>Модель дверной шторы</b>\n"
            "Выберите модель:",
            reply_markup=get_model_keyboard()
        )
    elif message.text == "❌ Нет":
        await state.update_data(door_model=None)
        await state.set_state(OrderCreationFSM.work_price)
        await message.answer(
            "Шаг 17 из 22: <b>Стоимость работы</b>\n\n"
            "Введите итоговую сумму (сум):",
            reply_markup=get_back_cancel_keyboard()
        )
    else:
        await message.answer("❌ Выберите «Да» или «Нет»:", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.door_model)
async def order_step_door_model(message: Message, state: FSMContext) -> None:
    """Шаг 16a: Модель дверной шторы."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.door_needed)
        await message.answer("Шаг 16 из 22: <b>Нужна штора на дверь?</b>", reply_markup=get_yes_no_keyboard())
        return

    model = message.text.strip().replace("🪟 ", "")
    if model not in CURTAIN_MODELS:
        await message.answer("❌ Выберите модель из списка:", reply_markup=get_model_keyboard())
        return

    await state.update_data(door_model=model, door_selected_materials=set())
    await state.set_state(OrderCreationFSM.door_material)
    await message.answer(
        f"✅ Модель дверной шторы: <b>{model}</b>\n\n"
        "Шаг 16b из 11: <b>Материал дверной шторы</b>\n"
        "Выберите один или несколько:\n"
        "Когда закончите, нажмите «✅ Подтвердить выбор»",
        reply_markup=get_materials_keyboard(set())
    )


@dp.message(OrderCreationFSM.door_material)
async def order_step_door_material(message: Message, state: FSMContext) -> None:
    """Шаг 16b: Материал дверной шторы."""
    data = await state.get_data()
    selected = set(data.get("door_selected_materials", []))

    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.door_model)
        await message.answer("Шаг 16a из 11: <b>Модель дверной шторы</b>\nВыберите модель:", reply_markup=get_model_keyboard())
        return

    text = message.text.strip()

    if text.startswith("✅ "):
        text = text[2:]
    elif text.startswith("⬜ "):
        text = text[2:]

    if text == "Подтвердить выбор":
        if not selected:
            await message.answer("❌ Выберите хотя бы один материал:", reply_markup=get_materials_keyboard(selected))
            return

        materials_str = ", ".join(sorted(selected))
        await state.update_data(door_material=materials_str)

        if len(selected) == 1:
            await state.update_data(door_selected_material_options=set())
            await state.set_state(OrderCreationFSM.door_material_options)
            await message.answer(
                f"✅ Материал двери: <b>{materials_str}</b>\n\n"
                "Шаг 16c из 11: <b>Опции материала дверной шторы</b>\n"
                "Выберите один или несколько:\n"
                "Когда закончите, нажмите «✅ Подтвердить выбор»",
                reply_markup=get_material_options_keyboard(set())
            )
        else:
            await state.update_data(door_material_options=None)
            await state.set_state(OrderCreationFSM.door_color)
            await message.answer(
                f"✅ Материал двери: <b>{materials_str}</b> (несколько материалов — опции пропущены)\n\n"
                "Шаг 16d из 11: <b>Цвет дверной шторы</b>\n"
                "Выберите цвет:",
                reply_markup=get_color_keyboard()
            )
        return

    if text in MATERIALS_LIST:
        if text in selected:
            selected.discard(text)
            await message.answer(f"➖ Материал <b>{text}</b> убран.\nВыбрано: {', '.join(sorted(selected)) if selected else 'пока ничего'}")
        else:
            selected.add(text)
            await message.answer(f"➕ Материал <b>{text}</b> добавлен.\nВыбрано: {', '.join(sorted(selected))}")

        await state.update_data(door_selected_materials=selected)
        await message.answer(
            "Шаг 16b из 11: <b>Материал дверной шторы</b>\nКогда закончите, нажмите «✅ Подтвердить выбор»:",
            reply_markup=get_materials_keyboard(selected)
        )
    else:
        await message.answer("❌ Выберите материал из списка или нажмите «Подтвердить выбор»:", reply_markup=get_materials_keyboard(selected))


@dp.message(OrderCreationFSM.door_material_options)
async def order_step_door_material_options(message: Message, state: FSMContext) -> None:
    """Шаг 16c: Опции материала дверной шторы."""
    data = await state.get_data()
    selected = set(data.get("door_selected_material_options", []))

    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.door_material)
        old_selected = set(data.get("door_selected_materials", []))
        await message.answer("Шаг 16b из 11: <b>Материал дверной шторы</b>\nВыберите материал:", reply_markup=get_materials_keyboard(old_selected))
        return

    text = message.text.strip()

    if text.startswith("✅ "):
        text = text[2:]
    elif text.startswith("⬜ "):
        text = text[2:]

    if text == "Подтвердить выбор":
        options_str = ", ".join(sorted(selected)) if selected else None
        await state.update_data(door_material_options=options_str)
        await state.set_state(OrderCreationFSM.door_color)
        await message.answer(
            f"✅ Опции двери: <b>{options_str or '—'}</b>\n\n"
            "Шаг 16d из 11: <b>Цвет дверной шторы</b>\n"
            "Выберите цвет:",
            reply_markup=get_color_keyboard()
        )
        return

    if text in MATERIAL_OPTIONS_LIST:
        if text in selected:
            selected.discard(text)
            await message.answer(f"➖ Опция <b>{text}</b> убрана.\nВыбрано: {', '.join(sorted(selected)) if selected else 'пока ничего'}")
        else:
            selected.add(text)
            await message.answer(f"➕ Опция <b>{text}</b> добавлена.\nВыбрано: {', '.join(sorted(selected))}")

        await state.update_data(door_selected_material_options=selected)
        await message.answer(
            "Шаг 16c из 11: <b>Опции материала двери</b>\nКогда закончите, нажмите «✅ Подтвердить выбор»:",
            reply_markup=get_material_options_keyboard(selected)
        )
    else:
        await message.answer("❌ Выберите опцию из списка или нажмите «Подтвердить выбор»:", reply_markup=get_material_options_keyboard(selected))


@dp.message(OrderCreationFSM.door_color)
async def order_step_door_color(message: Message, state: FSMContext) -> None:
    """Шаг 16d: Цвет дверной шторы."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        data = await state.get_data()
        door_material = data.get("door_material", "")
        material_list = [m.strip() for m in door_material.split(",") if m.strip()]
        if len(material_list) == 1:
            await state.set_state(OrderCreationFSM.door_material_options)
            await message.answer("Шаг 16c из 11: <b>Опции материала двери</b>\nВыберите опции:", reply_markup=get_material_options_keyboard(set()))
        else:
            await state.set_state(OrderCreationFSM.door_material)
            await message.answer("Шаг 16b из 11: <b>Материал дверной шторы</b>\nВыберите материал:", reply_markup=get_materials_keyboard(set(data.get("door_selected_materials", []))))
        return

    color = message.text.strip().replace("🎨 ", "")
    if color not in COLORS_LIST:
        await message.answer("❌ Выберите цвет из списка:", reply_markup=get_color_keyboard())
        return

    await state.update_data(door_color=color)
    await state.set_state(OrderCreationFSM.door_dimensions)
    await message.answer(
        f"✅ Цвет двери: <b>{color}</b>\n\n"
        "Шаг 16e из 11: <b>Размеры дверной шторы</b>\n"
        "Введите: <b>Ширина х Высота</b> (см)\n"
        "Пример: <code>80х200</code>",
        reply_markup=get_back_cancel_keyboard()
    )


@dp.message(OrderCreationFSM.door_dimensions)
async def order_step_door_dimensions(message: Message, state: FSMContext) -> None:
    """Шаг 16e: Размеры дверной шторы."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.door_color)
        await message.answer("Шаг 16d из 11: <b>Цвет дверной шторы</b>\nВыберите цвет:", reply_markup=get_color_keyboard())
        return

    parsed = parse_dimensions(message.text.strip())
    if not parsed:
        await message.answer(
            "❌ Неверный формат!\nВведите: <b>Ширина х Высота</b> (см)\nПример: <code>80х200</code>",
            reply_markup=get_back_cancel_keyboard()
        )
        return

    width, height, _ = parsed
    await state.update_data(door_dimensions=f"{width:.0f}x{height:.0f}")
    await state.set_state(OrderCreationFSM.door_sachak)
    await message.answer(
        f"📐 Размеры двери: {width:.0f} x {height:.0f} см\n\n"
        "Шаг 16f из 11: <b>Нужен сачак для дверной шторы?</b>",
        reply_markup=get_yes_no_keyboard()
    )


@dp.message(OrderCreationFSM.door_sachak)
async def order_step_door_sachak(message: Message, state: FSMContext) -> None:
    """Шаг 16f: Нужен ли сачак для дверной шторы."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.door_dimensions)
        await message.answer("Шаг 16e из 11: <b>Размеры дверной шторы</b>\nВведите размеры:", reply_markup=get_back_cancel_keyboard())
        return

    if message.text == "✅ Да":
        await state.set_state(OrderCreationFSM.door_sachak_type)
        await message.answer("Шаг 16f из 11: <b>Выберите тип сачака:</b>", reply_markup=get_sachak_keyboard())
    elif message.text == "❌ Нет":
        await state.update_data(door_sachak="Не нужен")
        await state.set_state(OrderCreationFSM.door_accessory)
        await message.answer("Шаг 16g из 11: <b>Нужен аксессуар для дверной шторы?</b>", reply_markup=get_yes_no_keyboard())
    else:
        await message.answer("❌ Выберите «Да» или «Нет»:", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.door_sachak_type)
async def order_step_door_sachak_type(message: Message, state: FSMContext) -> None:
    """Шаг 16f: Тип сачака для дверной шторы."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.door_sachak)
        await message.answer("Шаг 16f из 11: <b>Нужен сачак?</b>", reply_markup=get_yes_no_keyboard())
        return

    sachak = message.text.strip().replace("🎀 ", "")
    if sachak not in SACHAK_TYPES or sachak == "Не нужен":
        await message.answer("❌ Выберите тип сачака из списка:", reply_markup=get_sachak_keyboard())
        return

    await state.update_data(door_sachak=sachak)
    await state.set_state(OrderCreationFSM.door_accessory)
    await message.answer(f"✅ Сачак двери: <b>{sachak}</b>\n\nШаг 16g из 11: <b>Нужен аксессуар?</b>", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.door_accessory)
async def order_step_door_accessory(message: Message, state: FSMContext) -> None:
    """Шаг 16g: Нужен ли аксессуар для дверной шторы."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        data = await state.get_data()
        if data.get("door_sachak") == "Не нужен":
            await state.set_state(OrderCreationFSM.door_sachak)
            await message.answer("Шаг 16f из 11: <b>Нужен сачак?</b>", reply_markup=get_yes_no_keyboard())
        else:
            await state.set_state(OrderCreationFSM.door_sachak_type)
            await message.answer("Шаг 16f из 11: <b>Тип сачака</b>", reply_markup=get_sachak_keyboard())
        return

    if message.text == "✅ Да":
        await state.set_state(OrderCreationFSM.door_accessory_type)
        await message.answer("Шаг 16g из 11: <b>Выберите аксессуар:</b>", reply_markup=get_accessory_keyboard())
    elif message.text == "❌ Нет":
        await state.update_data(door_accessory="Не нужны")
        await state.set_state(OrderCreationFSM.door_cornice)
        await message.answer(
            "Шаг 16h из 11: <b>Багет для дверной шторы</b>\n"
            "Выберите тип багета:",
            reply_markup=get_door_cornice_inline_keyboard()
        )
    else:
        await message.answer("❌ Выберите «Да» или «Нет»:", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.door_accessory_type)
async def order_step_door_accessory_type(message: Message, state: FSMContext) -> None:
    """Шаг 16g: Тип аксессуара для дверной шторы."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.door_accessory)
        await message.answer("Шаг 16g из 11: <b>Нужен аксессуар?</b>", reply_markup=get_yes_no_keyboard())
        return

    accessory = message.text.strip().replace("🎁 ", "")
    if accessory not in ACCESSORY_TYPES or accessory == "Не нужны":
        await message.answer("❌ Выберите аксессуар из списка:", reply_markup=get_accessory_keyboard())
        return

    await state.update_data(door_accessory=accessory)
    await state.set_state(OrderCreationFSM.door_cornice)
    await message.answer(
        f"✅ Аксессуар: <b>{accessory}</b>\n\n"
        "Шаг 16h из 11: <b>Багет для дверной шторы</b>\n"
        "Выберите тип багета:",
        reply_markup=get_door_cornice_inline_keyboard()
    )


# ============================================================================
# ДВЕРНАЯ ШТОРА - БАГЕТ (ИСПРАВЛЕННЫЕ ОБРАБОТЧИКИ)
# ============================================================================

@dp.callback_query(F.data.startswith("door_cornice_select:"))
async def order_callback_door_cornice_select(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор багета для дверной шторы."""
    cornice = callback.data.split(":", 1)[1]
    await state.update_data(door_cornice=cornice)
    await state.set_state(OrderCreationFSM.door_cornice_rotation)

    # Удаляем старое сообщение с inline-клавиатурой
    await callback.message.delete()

    # Отправляем новое
    await callback.message.answer(
        f"✅ Багет двери: <b>{cornice}</b>\n\n"
        "Шаг 16i из 11: <b>Поворот для багета дверной шторы?</b>\n\n"
        "Выберите опцию:",
        reply_markup=get_yes_no_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("door_cornice_photo:"))
async def order_callback_door_cornice_photo(callback: CallbackQuery) -> None:
    """Просмотр фото багета для дверной шторы."""
    cornice = callback.data.split(":", 1)[1]
    await send_catalog_photo(
        callback.from_user.id,
        cornice,
        f"📸 <b>{cornice}</b>",
        category="cornices"
    )
    await callback.answer("📸 Фото отправлено")


@dp.callback_query(F.data == "door_cornice_manual")
async def order_callback_door_cornice_manual(callback: CallbackQuery, state: FSMContext) -> None:
    """Ручной ввод багета для дверной шторы."""
    await state.set_state(OrderCreationFSM.door_cornice)
    await callback.message.delete()
    await callback.message.answer("📝 Введите название багета вручную:", reply_markup=get_back_cancel_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "back_to_cornice_rotation")
async def back_to_cornice_rotation(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору поворота багета."""
    await state.set_state(OrderCreationFSM.cornice_rotation)
    await callback.message.delete()
    await callback.message.answer(
        "Шаг 13 из 22: <b>Нужен поворот для багета?</b>\n\n"
        "Выберите опцию:",
        reply_markup=get_yes_no_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_accessory")
async def back_to_accessory(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору аксессуара (основной заказ)."""
    await state.set_state(OrderCreationFSM.accessory)
    await callback.message.delete()
    await callback.message.answer(
        "Шаг 10 из 22: <b>Нужен аксессуар?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_door_accessory")
async def back_to_door_accessory(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору аксессуара дверной шторы."""
    await state.set_state(OrderCreationFSM.door_accessory)
    await callback.message.delete()
    await callback.message.answer(
        "Шаг 16g из 11: <b>Нужен аксессуар для дверной шторы?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await callback.answer()


@dp.message(OrderCreationFSM.door_cornice)
async def order_step_door_cornice_text(message: Message, state: FSMContext) -> None:
    """Ручной ввод багета для дверной шторы."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.door_accessory)
        await message.answer("Шаг 16g из 11: <b>Нужен аксессуар?</b>", reply_markup=get_yes_no_keyboard())
        return

    await state.update_data(door_cornice=message.text.strip())
    await state.set_state(OrderCreationFSM.door_cornice_rotation)
    await message.answer(
        f"✅ Багет двери: <b>{message.text.strip()}</b>\n\n"
        "Шаг 16i из 11: <b>Поворот для багета?</b>",
        reply_markup=get_yes_no_keyboard()
    )


@dp.message(OrderCreationFSM.door_cornice_rotation)
async def order_step_door_cornice_rotation(message: Message, state: FSMContext) -> None:
    """Шаг 16i: Поворот багета для дверной шторы."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.door_cornice)
        await message.answer("Шаг 16h из 11: <b>Багет</b>", reply_markup=get_door_cornice_inline_keyboard())
        return

    if message.text == "✅ Да":
        await state.update_data(door_cornice_rotation="Да")
    elif message.text == "❌ Нет":
        await state.update_data(door_cornice_rotation="Нет")
    else:
        await message.answer("❌ Выберите «Да» или «Нет»:", reply_markup=get_yes_no_keyboard())
        return

    # ВОЗВРАЩАЕМСЯ К ОСНОВНОМУ ЗАКАЗУ
    await state.set_state(OrderCreationFSM.work_price)
    await message.answer(
        "✅ Дверная штора настроена!\n\n"
        "Шаг 17 из 22: <b>Стоимость работы</b>\n\n"
        "Введите итоговую сумму (сум):",
        reply_markup=get_back_cancel_keyboard()
    )

# ============================================================================
# СТОИМОСТЬ РАБОТЫ, ЗАЛОГ, КОММЕНТАРИЙ, ПОДТВЕРЖДЕНИЕ
# ============================================================================

@dp.message(OrderCreationFSM.work_price)
async def order_step_work_price(message: Message, state: FSMContext) -> None:
    """Шаг 17: Стоимость работы."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        data = await state.get_data()
        if data.get("door_model"):
            await state.set_state(OrderCreationFSM.door_cornice_rotation)
            await message.answer("Шаг 16i из 11: <b>Поворот багета дверной шторы?</b>", reply_markup=get_yes_no_keyboard())
        else:
            await state.set_state(OrderCreationFSM.door_needed)
            await message.answer("Шаг 16 из 22: <b>Нужна штора на дверь?</b>", reply_markup=get_yes_no_keyboard())
        return

    try:
        price = float(message.text.strip().replace(",", "."))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число (например: 150000):", reply_markup=get_back_cancel_keyboard())
        return

    await state.update_data(work_price=price)
    await state.set_state(OrderCreationFSM.deposit)
    await message.answer("Шаг 18 из 22: <b>Залог получен?</b>", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.deposit)
async def order_step_deposit(message: Message, state: FSMContext) -> None:
    """Шаг 18: Получен ли залог."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.work_price)
        data = await state.get_data()
        current_price = data.get("work_price", 0)
        await message.answer(
            f"Шаг 17 из 22: <b>Стоимость работы</b>\nТекущая стоимость: {current_price:.2f} сум\n"
            "Введите новую сумму или оставьте без изменений:",
            reply_markup=get_back_cancel_keyboard()
        )
        return

    if message.text == "✅ Да":
        await state.set_state(OrderCreationFSM.deposit_amount)
        await message.answer("Шаг 18a из 22: <b>Введите сумму залога (сум):</b>", reply_markup=get_back_cancel_keyboard())
    elif message.text == "❌ Нет":
        data = await state.get_data()
        work_price = data.get("work_price", 0)
        await state.update_data(deposit=0, remaining_payment=work_price)
        await state.set_state(OrderCreationFSM.client_comment)
        await message.answer(
            f"💰 Залог: 0 сум\n💰 Остаток: {work_price:.2f} сум\n\n"
            "Шаг 20 из 22: 💬 <b>Комментарий</b> (опционально):\n"
            "Введите комментарий или нажмите «Пропустить»:",
            reply_markup=get_skip_back_cancel_keyboard()
        )
    else:
        await message.answer("❌ Выберите «Да» или «Нет»:", reply_markup=get_yes_no_keyboard())


@dp.message(OrderCreationFSM.deposit_amount)
async def order_step_deposit_amount(message: Message, state: FSMContext) -> None:
    """Шаг 18a: Сумма залога."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.deposit)
        await message.answer("Шаг 18 из 22: <b>Залог получен?</b>", reply_markup=get_yes_no_keyboard())
        return

    try:
        deposit_amount = float(message.text.strip().replace(",", "."))
        if deposit_amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число:", reply_markup=get_back_cancel_keyboard())
        return

    data = await state.get_data()
    work_price = data.get("work_price", 0)
    remaining = max(0, work_price - deposit_amount)

    await state.update_data(deposit=deposit_amount, remaining_payment=remaining)
    await state.set_state(OrderCreationFSM.remaining_payment)
    await message.answer(
        f"💰 Залог: {deposit_amount:.2f} сум\n💰 Авто-расчёт остатка: <b>{remaining:.2f} сум</b>\n\n"
        "Шаг 19 из 22: <b>Сколько осталось оплатить?</b>\n(можно отредактировать, если нужно)",
        reply_markup=get_back_cancel_keyboard()
    )


@dp.message(OrderCreationFSM.remaining_payment)
async def order_step_remaining_payment(message: Message, state: FSMContext) -> None:
    """Шаг 19: Остаток к оплате."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.deposit_amount)
        data = await state.get_data()
        current_deposit = data.get("deposit", 0)
        await message.answer(
            f"Шаг 18a из 22: <b>Сумма залога</b>\nТекущий залог: {current_deposit:.2f} сум\n"
            "Введите новую сумму или оставьте без изменений:",
            reply_markup=get_back_cancel_keyboard()
        )
        return

    try:
        remaining = float(message.text.strip().replace(",", "."))
        if remaining < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число:", reply_markup=get_back_cancel_keyboard())
        return

    await state.update_data(remaining_payment=remaining)
    await state.set_state(OrderCreationFSM.client_comment)
    await message.answer(
        "Шаг 20 из 22: 💬 <b>Комментарий</b> (опционально):\n"
        "Введите комментарий или нажмите «Пропустить»:",
        reply_markup=get_skip_back_cancel_keyboard()
    )


@dp.message(OrderCreationFSM.client_comment)
async def order_step_client_comment(message: Message, state: FSMContext) -> None:
    """Шаг 20: Комментарий клиента."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        data = await state.get_data()
        if data.get("deposit", 0) > 0:
            await state.set_state(OrderCreationFSM.remaining_payment)
            current_remaining = data.get("remaining_payment", 0)
            await message.answer(
                f"Шаг 19 из 22: <b>Остаток к оплате</b>\nТекущий остаток: {current_remaining:.2f} сум\n"
                "Введите новое значение или оставьте без изменений:",
                reply_markup=get_back_cancel_keyboard()
            )
        else:
            await state.set_state(OrderCreationFSM.deposit)
            await message.answer("Шаг 18 из 22: <b>Залог получен?</b>", reply_markup=get_yes_no_keyboard())
        return

    if message.text in ("⏭ Пропустить", "Пропустить"):
        comment = None
    else:
        comment = message.text.strip()

    await state.update_data(client_comment=comment)

    data = await state.get_data()

    summary_lines = [
        "📋 <b>Проверьте данные:</b>\n",
        f"👤 Клиент: {data['client_name']}",
        f"📞 Телефон: {data['client_phone']}",
        f"📍 Адрес: {data.get('install_address', '—')}",
        f"🪟 Модель: {data['model']}",
        f"🧵 Материалы: {data['materials']}",
        f"✨ Опции: {data.get('material_options') or '—'}",
        f"🎨 Цвет: {data.get('color', '—')}",
        f"📐 Размеры: {data.get('dimensions', '—')} см",
        f"🪟 Тюль: {data.get('tulle', '—')}",
        f"🎀 Сачак: {data.get('sachak', '—')}",
        f"🎁 Аксессуар: {data.get('accessory', '—')}",
        f"🔲 Багет: {data.get('cornice') or '—'}",
        f"↩️ Поворот: {data.get('cornice_rotation', '—')}",
        f"📅 Дедлайн: {data.get('deadline', '—')}",
        f"⭐ Приоритет: {priority_display(data.get('priority', 'normal'))}",
    ]

    if data.get("door_model"):
        summary_lines.extend([
            "\n🚪 <b>Дверная штора:</b>",
            f"🪟 Модель: {data['door_model']}",
            f"🧵 Материал: {data.get('door_material', '—')}",
            f"🎨 Цвет: {data.get('door_color', '—')}",
            f"📐 Размеры: {data.get('door_dimensions', '—')} см",
            f"🔲 Багет: {data.get('door_cornice', '—')}",
            f"↩️ Поворот: {data.get('door_cornice_rotation', '—')}",
        ])

    summary_lines.extend([
        f"\n💰 Работа: {data.get('work_price', 0):.2f} сум",
        f"💰 Залог: {data.get('deposit', 0):.2f} сум",
        f"💰 Остаток: {data.get('remaining_payment', 0):.2f} сум",
        f"💬 Комментарий: {data.get('client_comment') or '—'}",
        "\nШаг 21 из 22: <b>Всё верно?</b>"
    ])

    await state.set_state(OrderCreationFSM.confirm)
    await message.answer("\n".join(summary_lines), reply_markup=get_confirm_back_cancel_keyboard())


@dp.message(OrderCreationFSM.confirm)
async def order_step_confirm(message: Message, state: FSMContext) -> None:
    """Шаг 21-22: Подтверждение создания заказа."""
    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Создание заказа отменено.", reply_markup=get_main_keyboard(role))
        return

    if message.text == "🔙 Назад":
        await state.set_state(OrderCreationFSM.client_comment)
        await message.answer(
            "Шаг 20 из 22: 💬 <b>Комментарий</b> (опционально):\n"
            "Введите комментарий или нажмите «Пропустить»:",
            reply_markup=get_skip_back_cancel_keyboard()
        )
        return

    if message.text not in ("✅ Подтвердить", "Подтвердить"):
        await message.answer("Нажмите «✅ Подтвердить» для создания заказа или «🔙 Назад» для возврата.")
        return

    data = await state.get_data()
    user_id = message.from_user.id

    order_kwargs = {
        "client_name": data["client_name"],
        "client_phone": data["client_phone"],
        "client_tg_id": data.get("client_tg_id"),
        "model": data["model"],
        "materials": data["materials"],
        "material_options": data.get("material_options"),
        "color": data.get("color"),
        "dimensions": data.get("dimensions"),
        "area_m2": data.get("area_m2"),
        "cornice": data.get("cornice"),
        "cornice_rotation": data.get("cornice_rotation"),
        "tulle": data.get("tulle", "Не нужна"),
        "sachak": data.get("sachak", "Не нужен"),
        "accessory": data.get("accessory", "Не нужны"),
        "deadline": data.get("deadline"),
        "priority": data.get("priority", "normal"),
        "door_model": data.get("door_model"),
        "door_material": data.get("door_material"),
        "door_material_options": data.get("door_material_options"),
        "door_color": data.get("door_color"),
        "door_dimensions": data.get("door_dimensions"),
        "door_cornice": data.get("door_cornice"),
        "door_cornice_rotation": data.get("door_cornice_rotation"),
        "door_sachak": data.get("door_sachak", "Не нужен"),
        "door_accessory": data.get("door_accessory", "Не нужны"),
        "install_address": data.get("install_address"),
        "install_lat": data.get("install_lat"),
        "install_lon": data.get("install_lon"),
        "client_comment": data.get("client_comment"),
        "work_price": data.get("work_price", 0),
        "deposit": data.get("deposit", 0),
        "remaining_payment": data.get("remaining_payment", 0),
    }

    order_id = await db.create_order("TEMP", user_id, **order_kwargs)
    order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{order_id:04d}"
    await db.update_order_number(order_id, order_number)

    seller = await db.get_user(user_id)
    seller_name = seller["full_name"] if seller else str(user_id)

    order = await db.get_order(order_id)
    await db.audit(user_id, "create_order", "order", order_id, order_number)

    await state.clear()
    await message.answer(
        f"✅ <b>Заказ создан!</b>\n\n"
        f"📋 {order_number}\n"
        f"👤 {data['client_name']}\n\n"
        f"⏳ Ожидает назначения администратором.",
        reply_markup=get_main_keyboard(Role.SELLER)
    )

    await notify_admin_new_order(order, seller_name)


# ============================================================================
# УВЕДОМЛЕНИЯ ДЛЯ АДМИНОВ
# ============================================================================

async def notify_admin_new_order(order: Dict[str, Any], seller_name: str) -> None:
    """Уведомление администраторов о новом заказе."""
    message_text = (
        f"🆕 <b>НОВЫЙ ЗАКАЗ — ТРЕБУЕТ НАЗНАЧЕНИЯ МАСТЕРА</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"👤 Клиент: {order['client_name']}\n"
        f"📞 Телефон: {order['client_phone']}\n"
        f"🪟 Модель: {order['model']}\n"
        f"📐 Размеры: {order.get('dimensions', 'не указаны')} см\n"
        f"⭐ Приоритет: {priority_display(order.get('priority', Priority.NORMAL.value))}\n"
        f"💰 Работа: {order.get('work_price', 0):.2f} сум\n\n"
        f"🛒 Создал: {seller_name}\n\n"
        f"<b>Нажмите «Назначить мастера»</b>"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔧 Назначить мастера", callback_data=f"admin_assign:{order['id']}")
    keyboard.button(text="📋 Посмотреть заказ", callback_data=f"view_order:{order['id']}:0")
    keyboard.adjust(1)

    for admin_id in CEO_IDS + ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message_text, reply_markup=keyboard.as_markup())
        except Exception as error:
            logger.warning(f"Ошибка уведомления админа {admin_id}: {error}")

    await notify_group(message_text)


async def notify_master_new_order(order: Dict[str, Any], master_id: int, admin_name: str) -> None:
    """Уведомление мастера о новом заказе."""
    try:
        master = await db.get_user(master_id)
        if not master:
            return

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="✅ Принять в работу", callback_data=f"master_accept:{order['id']}")
        keyboard.button(text="❌ Отклонить заказ", callback_data=f"master_reject:{order['id']}")
        keyboard.button(text="📋 Посмотреть заказ", callback_data=f"view_order:{order['id']}:0")
        keyboard.adjust(1)

        await bot.send_message(
            master_id,
            f"📥 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
            f"📋 {order['order_number']}\n"
            f"👤 Клиент: {order['client_name']}\n"
            f"📞 Телефон: {order['client_phone']}\n"
            f"🪟 Модель: {order['model']}\n"
            f"📐 Размеры: {order.get('dimensions', 'не указаны')} см\n"
            f"📅 Дедлайн: {order.get('deadline', 'не указан')}\n"
            f"⭐ Приоритет: {priority_display(order.get('priority', Priority.NORMAL.value))}\n"
            f"💰 Работа: {order.get('work_price', 0):.2f} сум\n\n"
            f"⚙️ Назначил: {admin_name}\n\n"
            f"<b>Нажмите «✅ Принять в работу» или «❌ Отклонить заказ»</b>",
            reply_markup=keyboard.as_markup()
        )
    except Exception as error:
        logger.warning(f"Ошибка уведомления мастера {master_id}: {error}")


async def notify_admin_master_done(order: Dict[str, Any], master_name: str) -> None:
    """Уведомление администратора о завершении работы мастера."""
    message_text = (
        f"✅ <b>МАСТЕР ЗАВЕРШИЛ РАБОТУ</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"👤 Клиент: {order['client_name']}\n"
        f"🔧 Мастер: {master_name}\n\n"
        f"<b>Нажмите «Передать швее»</b>"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🧵 Передать швее", callback_data=f"admin_to_sewer:{order['id']}")
    keyboard.button(text="📋 Посмотреть заказ", callback_data=f"view_order:{order['id']}:0")
    keyboard.adjust(1)

    for admin_id in CEO_IDS + ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message_text, reply_markup=keyboard.as_markup())
        except Exception as error:
            logger.warning(f"Ошибка уведомления админа {admin_id}: {error}")


async def notify_admin_sewer_done(order: Dict[str, Any], sewer_name: str) -> None:
    """Уведомление администратора о завершении работы швеи."""
    message_text = (
        f"✅ <b>ШВЕЯ ЗАВЕРШИЛА ПОШИВ</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"👤 Клиент: {order['client_name']}\n"
        f"🧵 Швея: {sewer_name}\n\n"
        f"<b>Нажмите «Назначить установщика»</b>"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="👷 Назначить установщика", callback_data=f"admin_assign_installer:{order['id']}")
    keyboard.button(text="📋 Посмотреть заказ", callback_data=f"view_order:{order['id']}:0")
    keyboard.adjust(1)

    for admin_id in CEO_IDS + ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message_text, reply_markup=keyboard.as_markup())
        except Exception as error:
            logger.warning(f"Ошибка уведомления админа {admin_id}: {error}")


async def notify_transfer_to_sewer(order: Dict[str, Any], sewer_id: int, admin_id: int) -> None:
    """Уведомление швеи о передаче заказа."""
    sewer = await db.get_user(sewer_id)
    admin = await db.get_user(admin_id)

    if sewer:
        try:
            await bot.send_message(
                sewer_id,
                f"🧵 <b>ЗАКАЗ НА ПОШИВ!</b>\n\n"
                f"📋 {order['order_number']}\n"
                f"👤 {order['client_name']}\n"
                f"📐 {order.get('dimensions', '—')} см\n"
                f"⚙️ Передал: {admin['full_name'] if admin else admin_id}"
            )
        except Exception as error:
            logger.warning(f"Ошибка уведомления швеи {sewer_id}: {error}")


async def notify_material_added(order: Dict[str, Any], material_name: str, price: float, added_by_id: int) -> None:
    """Уведомление о добавлении материала."""
    added_by = await db.get_user(added_by_id)
    added_by_name = added_by["full_name"] if added_by else str(added_by_id)

    message_text = (
        f"➕ <b>МАТЕРИАЛ ДОБАВЛЕН</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"🧵 {material_name}\n"
        f"💰 {price:.2f} сум\n"
        f"👤 {added_by_name}"
    )
    await notify_all_admins(message_text)


async def notify_order_edited(order: Dict[str, Any], field: str, old_value: Any, new_value: Any, editor_id: int) -> None:
    """Уведомление о редактировании заказа."""
    editor = await db.get_user(editor_id)
    editor_name = editor["full_name"] if editor else str(editor_id)

    message_text = (
        f"✏️ <b>ЗАКАЗ ИЗМЕНЁН</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"📝 {field}\n"
        f"📌 {str(old_value)[:50]} → {str(new_value)[:50]}\n"
        f"👤 {editor_name}"
    )
    await notify_all_admins(message_text)
    await notify_group(message_text)


async def notify_order_deleted(order: Dict[str, Any], deleted_by_id: int) -> None:
    """Уведомление об удалении заказа."""
    deleted_by = await db.get_user(deleted_by_id)
    deleted_by_name = deleted_by["full_name"] if deleted_by else str(deleted_by_id)

    message_text = (
        f"🗑 <b>ЗАКАЗ УДАЛЁН!</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"👤 {order['client_name']}\n"
        f"👤 Удалил: {deleted_by_name}"
    )
    await notify_all_admins(message_text)
    await notify_group(message_text)


async def notify_shift_start(user_id: int, user_name: str, role: str, workshop_name: str = "") -> None:
    """Уведомление о начале смены."""
    workshop_info = f" 📍{workshop_name}" if workshop_name else ""
    message_text = (
        f"⏰ <b>НАЧАЛО СМЕНЫ</b>\n\n"
        f"👤 {user_name}\n"
        f"🎭 {role}\n"
        f"🕐 {datetime.now().strftime('%H:%M')}{workshop_info}"
    )
    await notify_all_admins(message_text)
    await notify_group(message_text)


async def notify_shift_end(user_id: int, user_name: str, role: str) -> None:
    """Уведомление о завершении смены."""
    message_text = (
        f"🏁 <b>ЗАВЕРШЕНИЕ СМЕНЫ</b>\n\n"
        f"👤 {user_name}\n"
        f"🎭 {role}\n"
        f"🕐 {datetime.now().strftime('%H:%M')}"
    )
    await notify_all_admins(message_text)
    await notify_group(message_text)


# ============================================================================
# АДМИН — НАЗНАЧЕНИЕ МАСТЕРА (ИСПРАВЛЕННАЯ ВЕРСИЯ)
# ============================================================================

@dp.message(F.text == "📋 Заказы на распределение")
async def admin_pending_orders(message: Message) -> None:
    """Просмотр заказов, ожидающих назначения мастера."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.ADMIN, Role.CEO):
        await message.answer("🚫 Нет доступа.")
        return

    orders = await db.get_orders_by_status(OrderStatus.NEW.value)
    if not orders:
        await message.answer("📭 Нет новых заказов на распределение.")
        return

    total = len(orders)
    await message.answer(
        f"📋 <b>Новые заказы ({total}):</b>\n\nВыберите для назначения мастера:",
        reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "admin_assign", 0, total)
    )


@dp.callback_query(F.data.startswith("admin_assign:"))
async def admin_select_master_fsm(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор мастера для назначения (через FSM)."""
    parts = callback.data.split(":")

    if len(parts) < 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    try:
        order_id = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    order = await db.get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    # Проверка статуса
    if order["status"] != OrderStatus.NEW.value:
        await callback.answer(f"❌ Заказ уже обработан", show_alert=True)
        return

    # Сохраняем order_id в состояние
    await state.update_data(temp_order_id=order_id)

    masters = await db.get_users_by_role(Role.MASTER.value)
    on_shift = [m for m in masters if await db.is_on_shift(m["telegram_id"])]
    if not on_shift:
        on_shift = masters

    if not on_shift:
        await callback.answer("❌ Нет доступных мастеров", show_alert=True)
        return

    # Создаём кнопки
    builder = InlineKeyboardBuilder()
    for master in on_shift:
        builder.button(
            text=f"🔧 {master['full_name']}",
            callback_data=f"select_master:{master['telegram_id']}"
        )
    builder.button(text="🔙 Назад", callback_data="back_to_pending_orders")
    builder.adjust(1)

    await callback.message.edit_text(
        f"🔧 <b>Выберите мастера для {order['order_number']}:</b>",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("select_master:"))
async def process_master_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора мастера - переводим в режим ввода комментария."""
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    try:
        master_id = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    # Получаем order_id из состояния
    data = await state.get_data()
    order_id = data.get("temp_order_id")

    if not order_id:
        await callback.answer("❌ Сессия истекла. Выберите заказ заново.", show_alert=True)
        return

    order = await db.get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    # Очищаем временные данные
    await state.update_data(temp_order_id=None)

    # Переходим к вводу комментария
    await state.set_state(AdminCommentFSM.comment)
    await state.update_data(order_id=order_id, next_action="assign_master", target_id=master_id)

    master = await db.get_user(master_id)
    master_name = master['full_name'] if master else str(master_id)

    # Удаляем старое сообщение и отправляем новое
    await callback.message.delete()
    await callback.message.answer(
        f"📝 <b>Комментарий к назначению мастера</b> (опционально):\n\n"
        f"📋 {order['order_number']}\n"
        f"🔧 Мастер: {master_name}\n\n"
        f"Введите комментарий или нажмите «⏭ Пропустить»:",
        reply_markup=get_skip_back_cancel_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_pending_orders")
async def back_to_pending_orders(callback: CallbackQuery) -> None:
    """Возврат к списку заказов, ожидающих назначения мастера."""
    orders = await db.get_orders_by_status(OrderStatus.NEW.value)
    if not orders:
        await callback.message.edit_text("📭 Нет новых заказов на распределение.")
        return

    total = len(orders)
    await callback.message.edit_text(
        f"📋 <b>Новые заказы ({total}):</b>\n\nВыберите для назначения мастера:",
        reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "admin_assign", 0, total)
    )
    await callback.answer()


# ============================================================================
# АДМИН — ПЕРЕДАЧА ШВЕЕ
# ============================================================================

@dp.message(F.text == "📋 Заказы от мастеров")
async def admin_orders_from_masters(message: Message) -> None:
    """Просмотр заказов, ожидающих передачи швее."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.ADMIN, Role.CEO):
        await message.answer("🚫 Нет доступа.")
        return

    orders = await db.get_orders_by_status(OrderStatus.PENDING_ADMIN_AFTER_MASTER.value)
    if not orders:
        await message.answer("📭 Нет заказов от мастеров.")
        return

    total = len(orders)
    await message.answer(
        f"📋 <b>Заказы от мастеров ({total}):</b>\n\nВыберите для передачи швее:",
        reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "admin_to_sewer", 0, total)
    )


@dp.callback_query(F.data.startswith("admin_to_sewer:"))
async def admin_select_sewer(callback: CallbackQuery) -> None:
    """Выбор швеи для передачи заказа."""
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    sewers = await db.get_users_by_role(Role.SEWER.value)
    on_shift = [sewer for sewer in sewers if await db.is_on_shift(sewer["telegram_id"])]
    if not on_shift:
        on_shift = sewers

    if not on_shift:
        await callback.answer("❌ Нет доступных швей", show_alert=True)
        return

    await callback.message.edit_text(
        f"🧵 <b>Выберите швею для {order['order_number']}:</b>",
        reply_markup=workers_inline_keyboard(on_shift, order_id, "admin_transfer_sewer")
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_transfer_sewer:"))
async def admin_transfer_sewer_with_comment(callback: CallbackQuery, state: FSMContext) -> None:
    """Передача заказа швее с комментарием."""
    parts = callback.data.split(":")
    order_id = int(parts[1])
    sewer_id = int(parts[2])

    order = await db.get_order(order_id)
    if not order:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    await state.set_state(AdminCommentFSM.comment)
    await state.update_data(order_id=order_id, next_action="transfer_sewer", target_id=sewer_id)

    await callback.message.delete()
    await callback.message.answer(
        f"📝 <b>Комментарий к передаче швее</b> (опционально):\n\n"
        f"📋 {order['order_number']}\n"
        f"🧵 Швея: {ALL_NAMES.get(sewer_id, str(sewer_id))}\n\n"
        f"Введите комментарий или нажмите «⏭ Пропустить»:",
        reply_markup=get_skip_back_cancel_keyboard()
    )
    await callback.answer()


# ============================================================================
# АДМИН — НАЗНАЧЕНИЕ УСТАНОВЩИКА
# ============================================================================

@dp.message(F.text == "📋 Заказы от швей")
async def admin_orders_from_sewers(message: Message) -> None:
    """Просмотр заказов, ожидающих назначения установщика."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.ADMIN, Role.CEO):
        await message.answer("🚫 Нет доступа.")
        return

    orders = await db.get_orders_by_status(OrderStatus.PENDING_ADMIN_AFTER_SEWER.value)
    if not orders:
        await message.answer("📭 Нет заказов от швей.")
        return

    total = len(orders)
    await message.answer(
        f"📋 <b>Заказы от швей ({total}):</b>\n\nВыберите для назначения установщика:",
        reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "admin_assign_inst", 0, total)
    )


@dp.callback_query(F.data.startswith("admin_assign_inst:"))
async def admin_select_installer(callback: CallbackQuery) -> None:
    """Выбор установщика для назначения."""
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    installers = await db.get_users_by_role(Role.INSTALLER.value)
    on_shift = [installer for installer in installers if await db.is_on_shift(installer["telegram_id"])]
    if not on_shift:
        on_shift = installers

    if not on_shift:
        await callback.answer("❌ Нет доступных установщиков", show_alert=True)
        return

    await callback.message.edit_text(
        f"👷 <b>Выберите установщика для {order['order_number']}:</b>",
        reply_markup=workers_inline_keyboard(on_shift, order_id, "admin_assign_installer")
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_assign_installer:"))
async def admin_assign_installer_with_comment(callback: CallbackQuery, state: FSMContext) -> None:
    """Назначение установщика с комментарием."""
    parts = callback.data.split(":")
    order_id = int(parts[1])
    installer_id = int(parts[2])

    order = await db.get_order(order_id)
    if not order:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    await state.set_state(AdminCommentFSM.comment)
    await state.update_data(order_id=order_id, next_action="assign_installer", target_id=installer_id)

    await callback.message.delete()
    await callback.message.answer(
        f"📝 <b>Комментарий к назначению установщика</b> (опционально):\n\n"
        f"📋 {order['order_number']}\n"
        f"👷 Установщик: {ALL_NAMES.get(installer_id, str(installer_id))}\n\n"
        f"Введите комментарий или нажмите «⏭ Пропустить»:",
        reply_markup=get_skip_back_cancel_keyboard()
    )
    await callback.answer()


# ============================================================================
# ОБРАБОТКА КОММЕНТАРИЯ АДМИНА (ИСПРАВЛЕННАЯ ВЕРСИЯ)
# ============================================================================

@dp.message(AdminCommentFSM.comment)
async def admin_comment_handler(message: Message, state: FSMContext) -> None:
    """Обработка комментария администратора при назначении."""
    data = await state.get_data()
    order_id = data["order_id"]
    next_action = data["next_action"]
    target_id = data["target_id"]
    comment = message.text.strip()

    if comment in ("⏭ Пропустить", "Пропустить"):
        comment = ""

    admin = await db.get_user(message.from_user.id)
    admin_name = admin["full_name"] if admin else "Админ"
    order = await db.get_order(order_id)

    if not order:
        await state.clear()
        await message.answer("❌ Заказ не найден")
        return

    if next_action == "assign_master":
        await db.update_order_status(
            order_id,
            OrderStatus.ASSIGNED_MASTER.value,
            message.from_user.id,
            master_id=target_id,
            assigned_to_id=target_id,
            comment=f"Админ {admin_name} назначил мастера. {comment}".strip()
        )
        await db.audit(message.from_user.id, "admin_assign_master", "order", order_id, f"master {target_id}")

        updated_order = await db.get_order(order_id)
        await notify_master_new_order(updated_order, target_id, admin_name)

        # Уведомляем всех админов о назначении
        await notify_all_admins(
            f"✅ <b>МАСТЕР НАЗНАЧЕН</b>\n\n"
            f"📋 {order['order_number']}\n"
            f"🔧 Мастер: {ALL_NAMES.get(target_id, str(target_id))}\n"
            f"👤 Админ: {admin_name}"
        )

        await message.answer(f"✅ <b>Мастер назначен!</b>\n\n📋 {order['order_number']}")

    elif next_action == "transfer_sewer":
        await db.update_order_status(
            order_id,
            OrderStatus.TO_SEWER.value,
            message.from_user.id,
            sewer_id=target_id,
            assigned_to_id=target_id,
            comment=f"Админ {admin_name} передал швее. {comment}".strip()
        )
        await db.audit(message.from_user.id, "admin_to_sewer", "order", order_id, str(target_id))

        updated_order = await db.get_order(order_id)
        await notify_transfer_to_sewer(updated_order, target_id, message.from_user.id)

        await message.answer(f"✅ <b>Передано швее!</b>\n\n📋 {order['order_number']}")

    elif next_action == "assign_installer":
        await db.update_order_status(
            order_id,
            OrderStatus.ASSIGNED_INSTALLER.value,
            message.from_user.id,
            installer_id=target_id,
            assigned_to_id=target_id,
            comment=f"Админ {admin_name} назначил установщика. {comment}".strip()
        )
        await db.audit(message.from_user.id, "admin_assign_installer", "order", order_id, str(target_id))

        installer = await db.get_user(target_id)
        if installer:
            try:
                await bot.send_message(
                    target_id,
                    f"👷 <b>НОВЫЙ ЗАКАЗ НА УСТАНОВКУ!</b>\n\n"
                    f"📋 {order['order_number']}\n"
                    f"👤 {order['client_name']}\n"
                    f"📞 {order['client_phone']}\n"
                    f"📍 Адрес: {order.get('install_address', '—')}"
                )
            except Exception as error:
                logger.warning(f"Ошибка уведомления установщика {target_id}: {error}")

        await message.answer(f"✅ <b>Установщик назначен!</b>\n\n📋 {order['order_number']}")

    # Очищаем состояние после успешного выполнения
    await state.clear()


# ============================================================================
# МАСТЕР (ОСТАЁТСЯ БЕЗ ИЗМЕНЕНИЙ)
# ============================================================================

@dp.message(F.text == "📥 Новые заказы")
async def master_new_orders(message: Message) -> None:
    """Просмотр новых заказов для мастера."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.MASTER, Role.CEO, Role.ADMIN):
        return

    if not await db.is_on_shift(user_id) and Role(user["role"]) not in (Role.CEO, Role.ADMIN):
        await message.answer("⚠️ Начните смену для просмотра заказов.")
        return

    orders = await db.search_orders(status=OrderStatus.ASSIGNED_MASTER.value, assigned_to=user_id)
    if not orders:
        await message.answer("📭 Нет назначенных заказов.")
        return

    total = len(orders)
    await message.answer(
        f"📥 <b>Заказы ({total}):</b>",
        reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "m_accept", 0, total)
    )


@dp.callback_query(F.data.startswith("m_accept:"))
async def master_accept_order(callback: CallbackQuery) -> None:
    """Принятие заказа мастером в работу."""
    user_id = callback.from_user.id
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    if order["status"] == OrderStatus.IN_PROGRESS.value and order.get("master_id") == user_id:
        order_text = await format_order_details(order)
        await callback.message.edit_text(order_text)
        await callback.answer("Это ваш заказ.")
        return

    if order["status"] != OrderStatus.ASSIGNED_MASTER.value:
        await callback.answer("❌ Заказ уже взят другим мастером!", show_alert=True)
        return

    user = await db.get_user(user_id)
    if not user:
        return
    if Role(user["role"]) not in (Role.MASTER, Role.CEO, Role.ADMIN):
        await callback.answer("❌ Только мастер может принять заказ", show_alert=True)
        return

    await db.update_order_status(
        order_id,
        OrderStatus.IN_PROGRESS.value,
        user_id,
        master_id=user_id,
        assigned_to_id=user_id,
        comment=f"Мастер {user['full_name']} принял заказ в работу"
    )
    await db.audit(user_id, "master_accept_order", "order", order_id, f"Мастер {user['full_name']} принял заказ")

    await callback.message.edit_text(
        f"✅ <b>Принят в работу!</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"👤 {order['client_name']}\n\n"
        f"{status_display(OrderStatus.IN_PROGRESS.value)}"
    )
    await callback.answer("Принят!")


@dp.callback_query(F.data.startswith("master_reject:"))
async def master_reject_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало процесса отклонения заказа мастером."""
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order or order["status"] != OrderStatus.ASSIGNED_MASTER.value:
        await callback.answer("❌ Недоступно", show_alert=True)
        return

    await state.set_state(RejectFSM.reason)
    await state.update_data(order_id=order_id, role="master")

    await callback.message.delete()
    await callback.message.answer(
        f"❌ <b>Отклонение заказа</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"📝 Укажите причину отклонения:",
        reply_markup=get_back_cancel_keyboard()
    )
    await callback.answer()


@dp.message(RejectFSM.reason)
async def reject_order_handler(message: Message, state: FSMContext) -> None:
    """Обработка причины отклонения заказа."""
    data = await state.get_data()
    order_id = data["order_id"]
    role = data["role"]
    reason = message.text.strip()

    if reason in ("🔙 Назад", "❌ Отмена"):
        await state.clear()
        await message.answer("❌ Отклонение отменено.")
        return

    order = await db.get_order(order_id)
    if not order:
        await state.clear()
        return

    user = await db.get_user(message.from_user.id)
    user_name = user["full_name"] if user else str(message.from_user.id)

    await db.update_order_status(
        order_id,
        OrderStatus.PENDING_ADMIN.value,
        message.from_user.id,
        master_id=None,
        assigned_to_id=None,
        comment=f"{user_name} отклонил заказ. Причина: {reason}"
    )
    await db.audit(message.from_user.id, f"{role}_reject_order", "order", order_id, reason)

    notify_message = (
        f"❌ <b>ЗАКАЗ ОТКЛОНЁН</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"👤 {user_name} ({role})\n"
        f"📝 Причина: {reason}\n\n"
        f"📌 Статус возвращён: {status_display(OrderStatus.PENDING_ADMIN.value)}"
    )
    await notify_all_admins(notify_message)

    await state.clear()
    await message.answer(
        f"✅ Заказ отклонён.\n\n"
        f"📋 {order['order_number']}\n"
        f"Администратор уведомлён.",
        reply_markup=get_main_keyboard(Role(user["role"]) if user else Role.SELLER)
    )



@dp.callback_query(F.data.startswith("s_accept:"))
async def sewer_accept(callback: CallbackQuery) -> None:
    """Принятие заказа в работу швеёй."""
    user_id = callback.from_user.id
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order or order["status"] != OrderStatus.TO_SEWER.value or order["sewer_id"] != user_id:
        await callback.answer("❌ Недоступно", show_alert=True)
        return

    await db.update_order_status(order_id, OrderStatus.SEWING.value, user_id, assigned_to_id=user_id)
    await db.audit(user_id, "start_sewing", "order", order_id)

    await callback.message.edit_text(
        f"✅ <b>В работе!</b>\n\n"
        f"📋 {order['order_number']}\n\n"
        f"{status_display(OrderStatus.SEWING.value)}"
    )
    await callback.answer("В работе!")


@dp.message(F.text == "✅ Готово (передать админу)")
async def sewer_ready_complete(message: Message) -> None:
    """Завершение пошива и передача админу."""
    user_id = message.from_user.id
    orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.SEWING.value)

    if not orders:
        await message.answer("📭 Нет заказов в работе.")
        return

    total = len(orders)
    await message.answer(
        f"✅ <b>Выберите заказ для завершения:</b>",
        reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "s_to_admin", 0, total)
    )


@dp.callback_query(F.data.startswith("s_to_admin:"))
async def sewer_transfer_to_admin(callback: CallbackQuery) -> None:
    """Передача заказа администратору после завершения пошива."""
    user_id = callback.from_user.id
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order or order["status"] != OrderStatus.SEWING.value:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    sewer = await db.get_user(user_id)
    await db.update_order_status(
        order_id,
        OrderStatus.PENDING_ADMIN_AFTER_SEWER.value,
        user_id,
        comment=f"Швея {sewer['full_name'] if sewer else user_id} завершила пошив, передала админу"
    )
    await db.audit(user_id, "sewer_to_admin", "order", order_id)

    await notify_admin_sewer_done(order, sewer["full_name"] if sewer else str(user_id))

    await callback.message.edit_text(
        f"✅ <b>Пошив завершён, передано админу!</b>\n\n"
        f"📋 {order['order_number']}\n\n"
        f"{status_display(OrderStatus.PENDING_ADMIN_AFTER_SEWER.value)}"
    )
    await callback.answer("Передано админу!")


# ============================================================================
# УСТАНОВЩИК (ОСТАЁТСЯ БЕЗ ИЗМЕНЕНИЙ)
# ============================================================================

@dp.message(F.text == "📥 Заказы на установку")
async def installer_orders(message: Message) -> None:
    """Просмотр заказов на установку для установщика."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.INSTALLER, Role.CEO, Role.ADMIN):
        return

    orders = await db.get_orders_for_installer(user_id)
    ready_orders = await db.get_orders_by_status(OrderStatus.ASSIGNED_INSTALLER.value)

    all_orders = orders + [order for order in ready_orders if order not in orders]
    if not all_orders:
        await message.answer("📭 Нет заказов.")
        return

    total = len(all_orders)
    await message.answer(
        f"👷 <b>Заказы ({total}):</b>",
        reply_markup=orders_inline_keyboard(all_orders[:ORDERS_PER_PAGE], "i_view", 0, total)
    )


@dp.message(F.text == "🚚 Выезд на адрес")
async def start_install(message: Message) -> None:
    """Начало выезда на установку."""
    user_id = message.from_user.id
    orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.ASSIGNED_INSTALLER.value)

    if not orders:
        orders = await db.get_orders_by_status(OrderStatus.ASSIGNED_INSTALLER.value)

    if not orders:
        await message.answer("📭 Нет заказов для выезда.")
        return

    total = len(orders)
    await message.answer(
        f"🚚 <b>Выберите заказ:</b>",
        reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "i_start", 0, total)
    )


@dp.callback_query(F.data.startswith("i_start:"))
async def confirm_start_install(callback: CallbackQuery) -> None:
    """Подтверждение выезда на установку."""
    user_id = callback.from_user.id
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order or order["status"] not in [OrderStatus.ASSIGNED_INSTALLER.value]:
        await callback.answer("❌ Недоступно", show_alert=True)
        return

    await db.update_order_status(order_id, OrderStatus.INSTALLING.value, user_id, installer_id=user_id, assigned_to_id=user_id)
    await db.audit(user_id, "start_installing", "order", order_id)

    address = order.get("install_address", "—")
    await callback.message.edit_text(
        f"🚚 <b>Выезд!</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"👤 {order['client_name']}\n"
        f"📞 {order['client_phone']}\n"
        f"📍 Адрес: {address}\n\n"
        f"{status_display(OrderStatus.INSTALLING.value)}"
    )
    await callback.answer("Выезд подтверждён!")


# ============================================================================
# ФОТО УСТАНОВЩИКА (InstallerPhotoFSM)
# ============================================================================

@dp.message(F.text == "📸 Загрузить фото")
async def start_installer_photos(message: Message, state: FSMContext) -> None:
    """Начало загрузки фото установщиком."""
    user_id = message.from_user.id
    orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.INSTALLING.value)

    if not orders:
        await message.answer("📭 Нет активных установок.")
        return

    if len(orders) == 1:
        await state.update_data(order_id=orders[0]["id"], before_photos=[])
        await state.set_state(InstallerPhotoFSM.before_photos)
        await message.answer(
            f"📸 <b>Фото ДО установки</b> для {orders[0]['order_number']}\n\n"
            f"Отправьте минимум 1, максимум 5 фото.\n"
            f"Затем нажмите «✅ Завершить и отправить».",
            reply_markup=get_photo_keyboard()
        )
    else:
        total = len(orders)
        await message.answer(
            f"📸 <b>Выберите заказ:</b>",
            reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "i_photo", 0, total)
        )


@dp.callback_query(F.data.startswith("i_photo:"))
async def select_installer_photo_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор заказа для загрузки фото установщиком."""
    order_id = int(callback.data.split(":")[1])
    await state.update_data(order_id=order_id, before_photos=[])
    await state.set_state(InstallerPhotoFSM.before_photos)
    await callback.message.edit_text(
        "📸 <b>Фото ДО установки</b>\n\n"
        "Отправьте минимум 1, максимум 5 фото. Затем нажмите «✅ Завершить и отправить».",
        reply_markup=get_photo_keyboard()
    )
    await callback.answer()


@dp.message(InstallerPhotoFSM.before_photos, F.photo)
async def process_before_photo(message: Message, state: FSMContext) -> None:
    """Обработка фото ДО установки."""
    data = await state.get_data()
    photos = data.get("before_photos", [])

    if len(photos) >= 5:
        await message.answer("❌ Лимит 5 фото для этапа «ДО»", reply_markup=get_photo_keyboard())
        return

    photo = message.photo[-1]
    photos.append({"file_id": photo.file_id, "file_unique_id": photo.file_unique_id})
    await state.update_data(before_photos=photos)
    await message.answer(f"📸 ДО: {len(photos)}/5. Отправьте ещё или нажмите ✅.", reply_markup=get_photo_keyboard())


@dp.message(InstallerPhotoFSM.before_photos, F.text == "✅ Завершить и отправить")
async def finish_before_photos(message: Message, state: FSMContext) -> None:
    """Завершение загрузки фото ДО и переход к фото ПОСЛЕ."""
    data = await state.get_data()
    photos = data.get("before_photos", [])

    if not photos:
        await message.answer("❌ Нужно минимум 1 фото «ДО».", reply_markup=get_photo_keyboard())
        return

    await state.set_state(InstallerPhotoFSM.after_photos)
    await state.update_data(after_photos=[])
    await message.answer(
        f"✅ Фото ДО сохранено: {len(photos)}\n\n"
        f"📸 <b>Теперь отправьте фото ПОСЛЕ установки</b> (минимум 1, максимум 5):",
        reply_markup=get_photo_keyboard()
    )


@dp.message(InstallerPhotoFSM.after_photos, F.photo)
async def process_after_photo(message: Message, state: FSMContext) -> None:
    """Обработка фото ПОСЛЕ установки."""
    data = await state.get_data()
    photos = data.get("after_photos", [])

    if len(photos) >= 5:
        await message.answer("❌ Лимит 5 фото для этапа «ПОСЛЕ»", reply_markup=get_photo_keyboard())
        return

    photo = message.photo[-1]
    photos.append({"file_id": photo.file_id, "file_unique_id": photo.file_unique_id})
    await state.update_data(after_photos=photos)
    await message.answer(f"📸 ПОСЛЕ: {len(photos)}/5. Отправьте ещё или нажмите ✅.", reply_markup=get_photo_keyboard())


@dp.message(InstallerPhotoFSM.after_photos, F.text == "✅ Завершить и отправить")
async def finish_after_photos(message: Message, state: FSMContext) -> None:
    """Завершение загрузки фото и завершение установки."""
    data = await state.get_data()
    before_photos = data.get("before_photos", [])
    after_photos = data.get("after_photos", [])
    order_id = data.get("order_id")

    if not after_photos:
        await message.answer("❌ Нужно минимум 1 фото «ПОСЛЕ».", reply_markup=get_photo_keyboard())
        return

    order = await db.get_order(order_id) if order_id else None
    if not order or order["status"] != OrderStatus.INSTALLING.value:
        await state.clear()
        return

    user_id = message.from_user.id

    # Сохраняем фото
    for photo in before_photos:
        await db.add_photo(order_id, photo["file_id"], photo["file_unique_id"], user_id,
                           PhotoStage.INSTALL_BEFORE.value)

    for photo in after_photos:
        await db.add_photo(order_id, photo["file_id"], photo["file_unique_id"], user_id, PhotoStage.INSTALL_AFTER.value)

    # Завершаем заказ
    await db.update_order_status(order_id, OrderStatus.COMPLETED.value, user_id)
    await db.audit(user_id, "complete_order", "order", order_id,
                   f"before:{len(before_photos)},after:{len(after_photos)}")

    # Уведомляем клиента
    if order.get("client_tg_id"):
        try:
            await bot.send_message(
                order["client_tg_id"],
                f"✅ <b>Ваш заказ выполнен!</b>\n\n"
                f"📋 {order['order_number']}\n"
                f"🪟 {order['model']}\n\n"
                f"Спасибо за доверие! Оставьте отзыв — нажмите /start"
            )
        except Exception as error:
            logger.warning(f"Ошибка уведомления клиента {order['client_tg_id']}: {error}")

    await state.clear()
    user = await db.get_user(user_id)
    await message.answer(
        f"✅ <b>Работа завершена!</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"📸 ДО: {len(before_photos)}\n"
        f"📸 ПОСЛЕ: {len(after_photos)}\n\n"
        f"{status_display(OrderStatus.COMPLETED.value)}",
        reply_markup=get_main_keyboard(Role(user["role"]))
    )


@dp.message(InstallerPhotoFSM.before_photos, F.text)
@dp.message(InstallerPhotoFSM.after_photos, F.text)
async def invalid_installer_photo(message: Message) -> None:
    """Обработка некорректного ввода при загрузке фото."""
    await message.answer("❌ Отправьте фото или нажмите ✅.", reply_markup=get_photo_keyboard())


# ============================================================================
# ФОТО ПО ЭТАПАМ (PhotoStageFSM)
# ============================================================================

@dp.message(F.text == "📸 Фото этапа")
async def start_photo_stage(message: Message, state: FSMContext) -> None:
    """Начало загрузки фото по этапам."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    role = Role(user["role"])

    if role == Role.MASTER:
        orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.IN_PROGRESS.value)
    elif role == Role.SEWER:
        orders = await db.get_orders_for_sewer(user_id)
    elif role == Role.INSTALLER:
        orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.INSTALLING.value)
    else:
        await message.answer("🚫 Нет доступа.")
        return

    if not orders:
        await message.answer("📭 Нет активных заказов.")
        return

    if len(orders) == 1:
        await state.update_data(order_id=orders[0]["id"], photos=[])
        await state.set_state(PhotoStageFSM.stage)
        await message.answer(
            f"📸 Загрузка фото для {orders[0]['order_number']}\n\nВыберите этап:",
            reply_markup=get_photo_stage_keyboard(orders[0]["id"])
        )
    else:
        total = len(orders)
        await message.answer(
            f"📸 <b>Выберите заказ:</b>",
            reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "photo_stage_select", 0, total)
        )


@dp.callback_query(F.data.startswith("photo_stage_select:"))
async def select_photo_stage_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор заказа для загрузки фото по этапам."""
    order_id = int(callback.data.split(":")[1])
    await state.update_data(order_id=order_id, photos=[])
    await state.set_state(PhotoStageFSM.stage)
    await callback.message.edit_text(
        "📸 Выберите этап для фото:",
        reply_markup=get_photo_stage_keyboard(order_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("photo_stage:"))
async def set_photo_stage(callback: CallbackQuery, state: FSMContext) -> None:
    """Установка этапа для загрузки фото."""
    parts = callback.data.split(":")
    order_id = int(parts[1])
    stage = parts[2]

    await state.update_data(stage=stage)
    await state.set_state(PhotoStageFSM.photos)
    await callback.message.edit_text(
        f"📸 Этап: <b>{stage_display(stage)}</b>\n\n"
        f"Отправляйте фото. Нажмите «✅ Завершить и отправить» когда закончите.\n"
        f"Максимум 10 фото.",
        reply_markup=get_photo_keyboard()
    )
    await callback.answer()


@dp.message(PhotoStageFSM.photos, F.photo)
async def process_stage_photo(message: Message, state: FSMContext) -> None:
    """Обработка фото для этапа."""
    data = await state.get_data()
    photos = data.get("photos", [])

    if len(photos) >= 10:
        await message.answer("❌ Лимит 10 фото", reply_markup=get_photo_keyboard())
        return

    photo = message.photo[-1]
    photos.append({"file_id": photo.file_id, "file_unique_id": photo.file_unique_id})
    await state.update_data(photos=photos)
    await message.answer(f"📸 Фото {len(photos)}/10. Отправьте ещё или нажмите «✅ Завершить и отправить».",
                         reply_markup=get_photo_keyboard())


@dp.message(PhotoStageFSM.photos, F.text == "✅ Завершить и отправить")
async def finish_stage_photos(message: Message, state: FSMContext) -> None:
    """Завершение загрузки фото по этапу."""
    data = await state.get_data()
    photos = data.get("photos", [])
    order_id = data.get("order_id")
    stage = data.get("stage", "general")
    user_id = message.from_user.id

    if not photos:
        await message.answer("❌ Нет фото. Отправьте минимум 1.", reply_markup=get_photo_keyboard())
        return

    for photo in photos:
        await db.add_photo(order_id, photo["file_id"], photo["file_unique_id"], user_id, stage)

    await db.audit(user_id, "add_photos", "order", order_id, f"stage:{stage},count:{len(photos)}")

    order = await db.get_order(order_id)
    if order:
        notification_text = (
            f"📸 <b>ФОТООТЧЁТ ПО ЭТАПУ</b>\n\n"
            f"📋 {order['order_number']}\n"
            f"📷 Этап: {stage_display(stage)}\n"
            f"📸 Количество: {len(photos)}\n"
            f"👤 Загрузил: {user_id}"
        )
        await notify_all_admins(notification_text)

    await state.clear()
    user = await db.get_user(user_id)
    await message.answer(
        f"✅ <b>Фото сохранены!</b>\n\n"
        f"📸 Этап: {stage_display(stage)}\n"
        f"📷 Количество: {len(photos)}",
        reply_markup=get_main_keyboard(Role(user["role"]))
    )


@dp.message(PhotoStageFSM.photos)
async def invalid_stage_photo(message: Message) -> None:
    """Обработка некорректного ввода при загрузке фото по этапам."""
    await message.answer("❌ Отправьте фото или нажмите ✅.", reply_markup=get_photo_keyboard())


# ============================================================================
# КЛИЕНТСКОЕ МЕНЮ (ИСПРАВЛЕННАЯ ВЕРСИЯ)
# ============================================================================

@dp.callback_query(F.data == "client_check_order")
async def client_check_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Проверка статуса заказа клиентом."""
    await state.set_state(ClientFSM.phone)
    await state.update_data(intent="check")  # ДОБАВЛЕНО: указываем, что это проверка
    await callback.message.edit_text(
        "🔍 <b>Проверка заказа</b>\n\n"
        "Введите номер телефона, указанный при оформлении заказа:\n"
        "Пример: <code>77 623 8118</code>",
        reply_markup=get_back_cancel_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "client_review")
async def client_review_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало процесса оставления отзыва."""
    await state.set_state(ClientFSM.phone)
    await state.update_data(intent="review")  # ДОБАВЛЕНО: указываем, что это отзыв
    await callback.message.edit_text(
        "⭐ <b>Оставить отзыв</b>\n\n"
        "Введите номер телефона, указанный при оформлении заказа:\n"
        "Пример: <code>77 623 8118</code>",
        reply_markup=get_back_cancel_keyboard()
    )
    await callback.answer()


# ЕДИНЫЙ ОБРАБОТЧИК ДЛЯ ВСЕХ СОСТОЯНИЙ ClientFSM.phone
@dp.message(ClientFSM.phone)
async def client_phone_handler(message: Message, state: FSMContext) -> None:
    """Обработка номера телефона для отзыва или проверки."""
    if message.text in ("🔙 Назад", "❌ Отмена"):
        await state.clear()
        await message.answer(
            "🔙 Возврат в главное меню.",
            reply_markup=get_client_menu_keyboard()
        )
        return

    phone = message.text.strip()

    if not validate_phone(phone):
        await message.answer(
            "❌ Неверный формат телефона!\n"
            "Пример: <code>77 623 8118</code> или <code>998776238118</code>",
            reply_markup=get_back_cancel_keyboard()
        )
        return

    order = await db.get_order_by_phone(phone)

    if not order:
        await message.answer(
            "❌ Заказ с таким номером телефона не найден.\n"
            "Проверьте правильность ввода или обратитесь в мастерскую.",
            reply_markup=get_client_menu_keyboard()
        )
        await state.clear()
        return

    # Определяем, откуда пришли - из проверки или из отзыва
    data = await state.get_data()
    intent = data.get("intent", "check")

    if intent == "review":
        # Для отзыва: сохраняем данные и переходим к оценке
        await state.update_data(order_id=order["id"], client_phone=phone)
        await state.set_state(ClientFSM.review_rating)
        await message.answer(
            f"⭐ <b>Отзыв на заказ {order['order_number']}</b>\n\n"
            f"Оцените качество работы (от 1 до 5 звёзд):",
            reply_markup=get_rating_keyboard(order["id"])
        )
    else:
        # Для проверки: просто показываем заказ
        order_text = await format_order_details(order, for_client=True)
        await state.clear()
        await message.answer(order_text, reply_markup=get_client_menu_keyboard())


@dp.callback_query(F.data.startswith("rate:"))
async def client_review_rating(callback: CallbackQuery, state: FSMContext) -> None:
    """Получение оценки от клиента."""
    parts = callback.data.split(":")
    order_id = int(parts[1])
    rating = int(parts[2])

    await state.update_data(order_id=order_id, rating=rating)
    await state.set_state(ClientFSM.review_text)

    await callback.message.edit_text(
        f"⭐ Вы поставили {rating} звезд{'у' if rating == 1 else 'ы' if rating in (2, 3, 4) else '' if rating == 5 else ''}!\n\n"
        f"📝 Напишите ваш отзыв (пожелания, замечания, благодарности):",
        reply_markup=get_skip_back_cancel_keyboard()
    )
    await callback.answer()


@dp.message(ClientFSM.review_text)
async def client_review_text(message: Message, state: FSMContext) -> None:
    """Получение текста отзыва."""
    if message.text in ("🔙 Назад", "❌ Отмена"):
        await state.clear()
        await message.answer(
            "🔙 Отзыв отменён.",
            reply_markup=get_client_menu_keyboard()
        )
        return

    if message.text in ("⏭ Пропустить", "Пропустить"):
        review_text = ""
    else:
        review_text = message.text.strip()

    data = await state.get_data()
    order_id = data["order_id"]
    rating = data["rating"]
    client_phone = data.get("client_phone", "")

    await db.add_review(order_id, client_phone, rating, review_text)
    await db.audit(message.from_user.id, "add_review", "order", order_id, f"rating:{rating}")

    # Уведомляем администраторов
    order = await db.get_order(order_id)
    if order:
        notification_text = (
            f"⭐ <b>НОВЫЙ ОТЗЫВ</b>\n\n"
            f"📋 {order['order_number']}\n"
            f"👤 {order['client_name']}\n"
            f"⭐ Оценка: {rating}/5\n"
            f"📝 Комментарий: {review_text or '—'}"
        )
        await notify_all_admins(notification_text)

    await state.clear()
    await message.answer(
        "✅ <b>Спасибо за отзыв!</b>\n\n"
        "Ваше мнение очень важно для нас.",
        reply_markup=get_client_menu_keyboard()
    )


@dp.callback_query(F.data == "client_menu")
async def client_menu_back(callback: CallbackQuery) -> None:
    """Возврат в клиентское меню."""
    await callback.message.edit_text(
        "👋 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        reply_markup=get_client_menu_keyboard()
    )
    await callback.answer()


# ============================================================================
# QR-КОД, КОММЕНТАРИИ, ИСТОРИЯ, РЕДАКТИРОВАНИЕ, УДАЛЕНИЕ
# ============================================================================

@dp.callback_query(F.data.startswith("qr_code:"))
async def show_qr_code(callback: CallbackQuery) -> None:
    """Показ QR-кода заказа."""
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    qr_bytes = await generate_qr(order_id)
    qr_file = BufferedInputFile(qr_bytes, filename=f"qr_order_{order_id}.png")

    await callback.message.answer_photo(
        qr_file,
        caption=f"🔗 <b>QR-код заказа</b>\n\n📋 {order['order_number']}\n👤 {order['client_name']}\n\nОтсканируйте для быстрого доступа к заказу."
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("navigate:"))
async def send_navigation(callback: CallbackQuery) -> None:
    """Отправка навигации к адресу установки."""
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    latitude = order.get("install_lat") or order.get("location_lat")
    longitude = order.get("install_lon") or order.get("location_lon")
    location_text = order.get("install_address") or order.get("location_text", "")

    if latitude and longitude:
        await callback.message.answer_location(latitude, longitude)

        maps_url = f"https://2gis.uz/directions?to={longitude},{latitude}"
        yandex_url = f"https://yandex.uz/maps/?rtext=~{latitude},{longitude}"

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🗺 2GIS", url=maps_url)
        keyboard.button(text="🗺 Яндекс.Карты", url=yandex_url)
        keyboard.adjust(2)

        await callback.message.answer(
            "🗺 <b>Выберите навигатор:</b>",
            reply_markup=keyboard.as_markup()
        )
    elif location_text:
        await callback.message.answer(f"📍 <b>Адрес:</b>\n{location_text}")
    else:
        await callback.answer("❌ Адрес не указан", show_alert=True)

    await callback.answer()


@dp.callback_query(F.data.startswith("photos_by_stage:"))
async def show_photos_by_stage(callback: CallbackQuery) -> None:
    """Показ фото заказа, сгруппированных по этапам."""
    order_id = int(callback.data.split(":")[1])
    photos_by_stage = await db.get_photos_by_stage(order_id)
    order = await db.get_order(order_id)

    if not photos_by_stage:
        await callback.answer("📭 Нет фото", show_alert=True)
        return

    for stage, photos in photos_by_stage.items():
        if photos:
            media_group = []
            for index, photo in enumerate(photos[:10]):
                caption = f"{stage_display(stage)} — {order['order_number']}" if index == 0 else None
                media_group.append(InputMediaPhoto(media=photo["file_id"], caption=caption))

            if media_group:
                try:
                    await callback.message.answer_media_group(media_group)
                except Exception as error:
                    logger.warning(f"Ошибка отправки медиагруппы: {error}")

    await callback.answer()


@dp.callback_query(F.data.startswith("comments:"))
async def show_comments(callback: CallbackQuery) -> None:
    """Показ комментариев к заказу."""
    order_id = int(callback.data.split(":")[1])
    comments = await db.get_comments(order_id)
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    if not comments:
        await callback.answer("Нет комментариев")
        return

    lines = [f"💬 <b>Комментарии к {order['order_number']}:</b>"]
    for comment in comments[:20]:
        lines.append(f"\n👤 {comment['full_name']} ({comment.get('role', '')}):\n📝 {comment['text'][:200]}")

    await callback.message.edit_text("\n".join(lines))
    await callback.answer()


@dp.callback_query(F.data.startswith("history:"))
async def show_history(callback: CallbackQuery) -> None:
    """Показ истории статусов заказа."""
    order_id = int(callback.data.split(":")[1])
    history = await db.get_status_history(order_id)
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    if not history:
        await callback.answer("Нет истории")
        return

    lines = [f"📜 <b>История {order['order_number']}:</b>"]
    for history_item in history[:20]:
        time_str = history_item["changed_at"][:19] if history_item.get("changed_at") else ""
        lines.append(f"\n🕐 {time_str}\n📌 {status_display(history_item['status'])}\n👤 {history_item['full_name']}")
        if history_item.get("comment"):
            lines.append(f"💬 {history_item['comment'][:100]}")

    await callback.message.edit_text("\n".join(lines))
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_order:"))
async def edit_order_menu(callback: CallbackQuery) -> None:
    """Меню редактирования заказа."""
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"✏️ <b>Редактирование {order['order_number']}:</b>",
        reply_markup=get_edit_fields_keyboard(order_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit:"))
async def edit_field_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало редактирования поля заказа."""
    parts = callback.data.split(":")
    field = parts[1]
    order_id = int(parts[2])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    await state.update_data(order_id=order_id, field=field)
    await state.set_state(EditFSM.value)

    current_value = order.get(field, "")
    await callback.message.edit_text(
        f"✏️ <b>{field}</b>\n"
        f"Текущее значение: <code>{current_value}</code>\n\n"
        f"Введите новое значение:"
    )
    await callback.answer()


@dp.message(EditFSM.value)
async def edit_field_save(message: Message, state: FSMContext) -> None:
    """Сохранение отредактированного поля."""
    data = await state.get_data()
    order_id = data["order_id"]
    field = data["field"]
    new_value = message.text.strip()

    order = await db.get_order(order_id)
    if not order:
        await state.clear()
        return

    old_value = order.get(field, "")
    await db.update_order(order_id, **{field: new_value})
    await db.audit(message.from_user.id, "edit_order", "order", order_id, f"{field}:{old_value}->{new_value}")
    await notify_order_edited(order, field, old_value, new_value, message.from_user.id)

    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer(
        f"✅ <b>Поле обновлено!</b>\n"
        f"📝 {field}\n"
        f"📌 {str(old_value)[:50]} → {str(new_value)[:50]}",
        reply_markup=get_main_keyboard(Role(user["role"]))
    )

    updated_order = await db.get_order(order_id)
    order_text = await format_order_details(updated_order)
    await message.answer(order_text)


@dp.callback_query(F.data.startswith("delete_order:"))
async def delete_order_confirm(callback: CallbackQuery) -> None:
    """Подтверждение удаления заказа."""
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"🗑 <b>Вы уверены?</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"👤 {order['client_name']}\n\n"
        f"Это действие нельзя отменить!",
        reply_markup=get_delete_confirm_keyboard(order_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_delete:"))
async def delete_order_execute(callback: CallbackQuery) -> None:
    """Выполнение удаления заказа."""
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    await db.delete_order(order_id)
    await db.audit(callback.from_user.id, "delete_order", "order", order_id, order["order_number"])
    await notify_order_deleted(order, callback.from_user.id)

    await callback.message.edit_text(f"🗑 <b>Заказ удалён!</b>\n📋 {order['order_number']}")
    await callback.answer("Удалён!")
# ============================================================================
# УПРАВЛЕНИЕ РОЛЯМИ И СМЕНЫ
# ============================================================================

@dp.message(F.text == "👥 Управление ролями")
async def manage_roles(message: Message) -> None:
    """Управление ролями пользователей (только CEO)."""
    user_id = message.from_user.id

    if not is_registered(user_id) or get_role_by_id(user_id) != Role.CEO:
        await message.answer("🚫 Только CEO имеет доступ к управлению ролями.")
        return

    users = await db.get_all_active_users()
    if not users:
        await message.answer("Нет зарегистрированных пользователей.")
        return

    await message.answer(
        "👥 <b>Выберите пользователя для изменения роли:</b>",
        reply_markup=get_users_inline_keyboard(users)
    )


@dp.callback_query(F.data.startswith("set_role:"))
async def set_role_for_user(callback: CallbackQuery) -> None:
    """Выбор новой роли для пользователя."""
    target_id = int(callback.data.split(":")[1])
    user = await db.get_user(target_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"👤 <b>{user['full_name']}</b>\n"
        f"🎭 Текущая роль: {user['role']}\n\n"
        f"Выберите новую роль:",
        reply_markup=get_roles_inline_keyboard(target_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_role:"))
async def confirm_role_change(callback: CallbackQuery) -> None:
    """Подтверждение изменения роли."""
    parts = callback.data.split(":")
    target_id = int(parts[1])
    new_role = parts[2]

    user = await db.get_user(target_id)
    if not user:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    old_role = user["role"]
    await db.update_user_role(target_id, new_role)
    await db.audit(callback.from_user.id, "change_role", "user", target_id, f"{old_role}->{new_role}")

    notification_text = (
        f"🔄 <b>РОЛЬ ИЗМЕНЕНА</b>\n\n"
        f"👤 {user['full_name']}\n"
        f"🎭 {old_role} → {new_role}\n"
        f"👑 Изменил: CEO"
    )
    await notify_all_admins(notification_text)

    await callback.message.edit_text(
        f"✅ <b>Роль изменена!</b>\n\n"
        f"👤 {user['full_name']}\n"
        f"🎭 {old_role} → {new_role}"
    )
    await callback.answer("✅ Изменено!")


@dp.callback_query(F.data == "back_to_users_list")
async def back_to_users_list(callback: CallbackQuery) -> None:
    """Возврат к списку пользователей."""
    users = await db.get_all_active_users()
    await callback.message.edit_text(
        "👥 <b>Выберите пользователя:</b>",
        reply_markup=get_users_inline_keyboard(users)
    )
    await callback.answer()


@dp.message(F.text == "👥 Сотрудники на смене")
async def today_shifts(message: Message) -> None:
    """Просмотр сотрудников на смене сегодня."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.CEO, Role.ADMIN):
        await message.answer("🚫 Нет доступа.")
        return

    shifts = await db.get_today_shifts()
    if not shifts:
        await message.answer("📭 Сегодня никто не на смене.")
        return

    lines = ["👥 <b>Сотрудники на смене:</b>"]
    for shift in shifts:
        workshop = shift.get("workshop_point", "—")
        start_time = shift["started_at"][11:16] if shift.get("started_at") else "—"
        lines.append(f"\n👤 {shift['full_name']} ({shift['role']})\n🕐 {start_time}\n📍 {workshop}")

    await message.answer("\n".join(lines))


@dp.message(F.text == "⏰ Начать смену")
async def start_shift_command(message: Message) -> None:
    """Начало смены."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        return

    role = Role(user["role"])
    if role in (Role.CEO, Role.ADMIN, Role.SMM):
        await message.answer("⚠️ Смены не требуются для этой роли.")
        return

    if await db.is_on_shift(user_id):
        await message.answer("✅ Вы уже на смене.")
        return

    await message.answer(
        "📍 Отправьте геолокацию для начала смены:",
        reply_markup=get_location_keyboard()
    )


@dp.message(F.text == "🏁 Закончить смену")
async def end_shift_command(message: Message) -> None:
    """Завершение смены."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        return

    role = Role(user["role"])
    if role in (Role.CEO, Role.ADMIN, Role.SMM):
        await message.answer("⚠️ Смены не требуются для этой роли.")
        return

    if not await db.is_on_shift(user_id):
        await message.answer("⚠️ Вы не на смене.")
        return

    await db.end_shift(user_id)
    await db.audit(user_id, "end_shift")
    await notify_shift_end(user_id, user["full_name"], role.value)
    await message.answer(
        "🏁 <b>Смена завершена!</b>",
        reply_markup=get_main_keyboard(role)
    )


@dp.message(F.location)
async def process_location(message: Message) -> None:
    """Обработка геолокации для начала смены."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        return

    role = Role(user["role"])
    if role in (Role.CEO, Role.ADMIN, Role.SMM):
        return

    latitude = message.location.latitude
    longitude = message.location.longitude

    is_near, nearest = await is_near_any_workshop(latitude, longitude)

    if not is_near:
        await message.answer(
            f"⚠️ Вы слишком далеко от цеха!\n"
            f"📍 Ближайший: {nearest[2]} ({nearest[3]:.0f} м)"
        )
        return

    await db.start_shift(user_id, latitude, longitude, nearest[2])
    await db.audit(user_id, "start_shift", details=f"{nearest[2]}")
    await notify_shift_start(user_id, user["full_name"], role.value, nearest[2])
    await message.answer(
        f"✅ <b>Смена начата!</b>\n📍 {nearest[2]}",
        reply_markup=get_main_keyboard(role)
    )


# ============================================================================
# ОСТАЛЬНЫЕ КОМАНДЫ
# ============================================================================

@dp.message(F.text == "📊 Дашборд")
async def dashboard(message: Message) -> None:
    """Показ дашборда со статистикой."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.CEO, Role.ADMIN, Role.SMM):
        await message.answer("🚫 Нет доступа.")
        return

    stats = await db.get_daily_stats()

    dashboard_text = (
        "📊 <b>ДАШБОРД НА СЕГОДНЯ</b>\n\n"
        f"📝 Создано: <b>{stats['created_today']}</b>\n"
        f"✅ Выполнено: <b>{stats['completed_today']}</b>\n"
        f"👥 На смене: <b>{stats['on_shift']}</b>\n"
        f"⏰ Просрочено: <b>{stats['overdue']}</b>\n"
        f"💰 Закупки: <b>{stats['purchases_sum']:.2f} сум</b>\n\n"
        "📊 <b>ПО СТАТУСАМ:</b>\n"
    )

    for status, count in stats["status_counts"].items():
        if count > 0:
            dashboard_text += f"  {status_display(status)}: {count}\n"

    await message.answer(dashboard_text)


@dp.message(F.text == "🔍 Поиск заказов")
async def search_start(message: Message) -> None:
    """Начало поиска заказов."""
    user_id = message.from_user.id

    if not is_registered(user_id):
        return

    await message.answer(
        "🔍 <b>Поиск заказов:</b>",
        reply_markup=get_search_filter_keyboard()
    )


@dp.callback_query(F.data == "search_prompt")
async def search_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос поискового запроса."""
    await state.set_state(SearchFSM.waiting_query)
    await callback.message.edit_text("🔍 Введите поисковый запрос (номер заказа, имя клиента, телефон):")
    await callback.answer()


@dp.callback_query(F.data == "back_to_search")
async def back_to_search(callback: CallbackQuery) -> None:
    """Возврат к поиску."""
    await callback.message.edit_text(
        "🔍 <b>Поиск заказов:</b>",
        reply_markup=get_search_filter_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery) -> None:
    """Возврат в главное меню."""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    role = Role(user["role"]) if user else Role.SELLER
    await callback.message.delete()
    await callback.message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard(role)
    )
    await callback.answer()


@dp.message(SearchFSM.waiting_query)
async def search_execute(message: Message, state: FSMContext) -> None:
    """Выполнение поиска."""
    query = message.text.strip()

    if message.text in ["🔙 Назад", "❌ Отмена"]:
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Поиск отменён.", reply_markup=get_main_keyboard(role))
        return

    orders = await db.search_orders(query=query, limit=ORDERS_PER_PAGE)
    total = await db.count_orders(query=query)

    await state.clear()

    if not orders:
        await message.answer("📭 Ничего не найдено.")
        return

    await message.answer(
        f"🔍 <b>Результаты поиска ({total}):</b>",
        reply_markup=orders_inline_keyboard(orders, "view_order", 0, total)
    )


@dp.callback_query(F.data == "filter_status_menu")
async def filter_status_menu(callback: CallbackQuery) -> None:
    """Меню фильтрации по статусу."""
    await callback.message.edit_text(
        "📌 <b>Фильтр по статусу:</b>",
        reply_markup=get_statuses_inline_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("filter_status:"))
async def filter_status_execute(callback: CallbackQuery) -> None:
    """Выполнение фильтрации по статусу."""
    status = callback.data.split(":")[1]

    if status == "all":
        orders = await db.search_orders(limit=ORDERS_PER_PAGE)
        total = await db.count_orders()
        label = "Все заказы"
    else:
        orders = await db.search_orders(status=status, limit=ORDERS_PER_PAGE)
        total = await db.count_orders(status=status)
        label = status_display(status)

    if not orders:
        await callback.message.edit_text(f"📭 {label}: 0")
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📌 <b>{label} ({total}):</b>",
        reply_markup=orders_inline_keyboard(orders, "view_order", 0, total)
    )
    await callback.answer()


@dp.callback_query(F.data == "show_overdue")
async def show_overdue(callback: CallbackQuery) -> None:
    """Показ просроченных заказов."""
    orders = await db.get_overdue_orders()
    total = len(orders)

    if not orders:
        await callback.message.edit_text("📅 <b>Просроченных заказов нет!</b> 🎉")
        await callback.answer()
        return

    await callback.message.edit_text(
        f"⏰ <b>Просроченные заказы ({total}):</b>",
        reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "view_order", 0, total)
    )
    await callback.answer()


@dp.message(F.text == "📅 Просроченные")
async def overdue_button(message: Message) -> None:
    """Кнопка просмотра просроченных заказов."""
    orders = await db.get_overdue_orders()
    total = len(orders)

    if not orders:
        await message.answer("📅 <b>Просроченных заказов нет!</b> 🎉")
        return

    await message.answer(
        f"⏰ <b>Просроченные заказы ({total}):</b>",
        reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "view_order", 0, total)
    )


@dp.message(F.text == "📋 Все заказы")
async def all_orders(message: Message) -> None:
    """Просмотр всех заказов."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.CEO, Role.ADMIN, Role.SMM):
        await message.answer("🚫 Нет доступа.")
        return

    orders = await db.search_orders(limit=ORDERS_PER_PAGE)
    total = await db.count_orders()

    if not orders:
        await message.answer("📭 Нет заказов.")
        return

    await message.answer(
        f"📋 <b>Все заказы ({total}):</b>",
        reply_markup=orders_inline_keyboard(orders, "view_order", 0, total)
    )


@dp.message(F.text == "📋 Мои заказы")
async def my_orders(message: Message) -> None:
    """Просмотр заказов текущего пользователя."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await message.answer("❌ Пользователь не найден.")
        return

    role = Role(user["role"])

    if role == Role.SELLER:
        orders = await db.get_orders_by_seller(user_id, limit=ORDERS_PER_PAGE)
        total = await db.count_orders_by_seller(user_id)
    elif role == Role.MASTER:
        orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.IN_PROGRESS.value, limit=ORDERS_PER_PAGE)
        total = await db.count_orders(assigned_to=user_id, status=OrderStatus.IN_PROGRESS.value)
    elif role == Role.SEWER:
        orders = await db.get_orders_for_sewer(user_id)
        total = len(orders)
        orders = orders[:ORDERS_PER_PAGE]
    elif role == Role.INSTALLER:
        orders = await db.get_orders_for_installer(user_id)
        total = len(orders)
        orders = orders[:ORDERS_PER_PAGE]
    else:
        orders = await db.search_orders(limit=ORDERS_PER_PAGE)
        total = await db.count_orders()

    if not orders:
        await message.answer("📭 У вас нет активных заказов.")
        return

    await message.answer(
        f"📋 <b>Ваши заказы ({total}):</b>",
        reply_markup=orders_inline_keyboard(orders, "view_order", 0, total)
    )


@dp.message(F.text == "📤 Экспорт CSV")
async def export_csv(message: Message) -> None:
    """Экспорт заказов в CSV."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.CEO, Role.ADMIN):
        await message.answer("🚫 Нет доступа.")
        return

    csv_data = await db.export_orders_csv()
    file = BufferedInputFile(csv_data, filename=f"orders_{date.today().isoformat()}.csv")
    await message.answer_document(file, caption="📤 Экспорт заказов CSV")


@dp.message(F.text == "📤 Экспорт Excel")
async def export_excel(message: Message) -> None:
    """Экспорт заказов в формате Excel (CSV с другим расширением)."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.CEO, Role.ADMIN):
        await message.answer("🚫 Нет доступа.")
        return

    csv_data = await db.export_orders_csv()
    file = BufferedInputFile(csv_data, filename=f"orders_{date.today().isoformat()}.xlsx")
    await message.answer_document(file, caption="📤 Экспорт заказов XLSX (CSV формат)")


# ============================================================================
# ДОБАВЛЕНИЕ МАТЕРИАЛА (ШВЕЯ)
# ============================================================================

@dp.message(F.text == "➕ Добавить материал")
async def start_material(message: Message, state: FSMContext) -> None:
    """Добавление материала к заказу (швея)."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.SEWER, Role.CEO, Role.ADMIN):
        return

    orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.SEWING.value)

    if not orders:
        await message.answer("📭 Нет заказов в работе.")
        return

    if len(orders) == 1:
        await state.update_data(order_id=orders[0]["id"])
        await state.set_state(PurchaseFSM.material_name)
        await message.answer(
            f"🧵 Материал к {orders[0]['order_number']}\n\nВведите название материала:",
            reply_markup=get_back_cancel_keyboard()
        )
    else:
        total = len(orders)
        await message.answer(
            f"🧵 <b>Выберите заказ:</b>",
            reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "add_mat", 0, total)
        )


@dp.callback_query(F.data.startswith("add_mat:"))
async def select_mat_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор заказа для добавления материала."""
    order_id = int(callback.data.split(":")[1])
    await state.update_data(order_id=order_id)
    await state.set_state(PurchaseFSM.material_name)
    await callback.message.edit_text("🧵 Введите название материала:")
    await callback.answer()


@dp.message(PurchaseFSM.material_name)
async def material_name_input(message: Message, state: FSMContext) -> None:
    """Ввод названия материала."""
    if message.text in ["🔙 Назад", "❌ Отмена"]:
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard(role))
        return

    await state.update_data(material_name=message.text.strip())
    await state.set_state(PurchaseFSM.price)
    await message.answer("💰 Введите цену материала (сум):", reply_markup=get_back_cancel_keyboard())


@dp.message(PurchaseFSM.price)
async def material_price_input(message: Message, state: FSMContext) -> None:
    """Ввод цены материала."""
    if message.text == "🔙 Назад":
        await state.set_state(PurchaseFSM.material_name)
        await message.answer("🧵 Введите название материала:", reply_markup=get_back_cancel_keyboard())
        return

    if message.text == "❌ Отмена":
        await state.clear()
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard(role))
        return

    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Введите положительное число:",
            reply_markup=get_back_cancel_keyboard()
        )
        return

    data = await state.get_data()
    await db.add_purchase(data["order_id"], data["material_name"], price)
    await db.audit(message.from_user.id, "add_purchase", "order", data["order_id"], f"{data['material_name']} {price}")

    order = await db.get_order(data["order_id"])
    await notify_material_added(order, data["material_name"], price, message.from_user.id)

    await state.set_state(PurchaseFSM.confirm)
    await message.answer(
        f"✅ Добавлено: {data['material_name']} — {price:.2f} сум\n\n"
        f"Добавить ещё материал?",
        reply_markup=get_purchase_action_keyboard(data["order_id"])
    )


@dp.callback_query(PurchaseFSM.confirm, F.data.startswith("add_more:"))
async def add_more_material(callback: CallbackQuery, state: FSMContext) -> None:
    """Добавление ещё одного материала."""
    await state.set_state(PurchaseFSM.material_name)
    await callback.message.edit_text("🧵 Введите название материала:")
    await callback.answer()


@dp.callback_query(PurchaseFSM.confirm, F.data.startswith("finish_purch:"))
async def finish_material(callback: CallbackQuery, state: FSMContext) -> None:
    """Завершение добавления материалов."""
    data = await state.get_data()
    purchases = await db.get_purchases(data["order_id"])
    total = sum(purchase["price"] * purchase["quantity"] for purchase in purchases)

    lines = ["📦 <b>Закупки по заказу:</b>"]
    for index, purchase in enumerate(purchases, 1):
        lines.append(f"{index}. {purchase['material_name']} — {purchase['price']:.2f} сум")
    lines.append(f"\n💰 <b>Итого: {total:.2f} сум</b>")

    await callback.message.edit_text("\n".join(lines))
    await callback.answer("Сохранено!")
    await state.clear()


@dp.callback_query(F.data == "back_to_sewer_menu")
async def back_to_sewer_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат в меню швеи."""
    await state.clear()
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    role = Role(user["role"]) if user else Role.SEWER
    await callback.message.edit_text("🧵 Меню швеи.")
    await callback.answer()


# ============================================================================
# ПРОСМОТР ЗАКАЗА И ПАГИНАЦИЯ
# ============================================================================

@dp.callback_query(F.data.startswith("view_order:"))
async def view_order_callback(callback: CallbackQuery) -> None:
    """Просмотр деталей заказа."""
    parts = callback.data.split(":")
    order_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    order = await db.get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    order_text = await format_order_details(order)

    # Проверяем, откуда пришли - из уведомления о новом заказе или из списка
    is_from_notification = order["status"] == OrderStatus.NEW.value

    if is_from_notification:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔧 Назначить мастера", callback_data=f"admin_assign:{order_id}")
        builder.button(text="📋 Посмотреть заказ", callback_data=f"view_order:{order_id}:{page}")
        builder.button(text="🔙 Назад к заказам", callback_data="back_to_pending_orders")
        builder.adjust(1)
        await callback.message.edit_text(order_text, reply_markup=builder.as_markup())
    else:
        user_id = callback.from_user.id
        user = await db.get_user(user_id)
        role = Role(user["role"]) if user else Role.SELLER
        await callback.message.edit_text(order_text, reply_markup=get_order_detail_keyboard(order_id, role))

    await callback.answer()


@dp.callback_query(F.data == "back_to_list")
async def back_to_list(callback: CallbackQuery) -> None:
    """Возврат к списку заказов."""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    role = Role(user["role"]) if user else Role.SELLER
    await callback.message.delete()
    await callback.message.answer("📋 Главное меню.", reply_markup=get_main_keyboard(role))
    await callback.answer()


@dp.callback_query(F.data.startswith("back_to_transfer_order:"))
async def back_to_transfer_order(callback: CallbackQuery) -> None:
    """Возврат к списку заказов для передачи."""
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    # Определяем тип действия по статусу заказа
    if order["status"] == OrderStatus.PENDING_ADMIN_AFTER_MASTER.value:
        # Возврат к выбору швеи
        sewers = await db.get_users_by_role(Role.SEWER.value)
        on_shift = [sewer for sewer in sewers if await db.is_on_shift(sewer["telegram_id"])]
        if not on_shift:
            on_shift = sewers
        await callback.message.edit_text(
            f"🧵 <b>Выберите швею для {order['order_number']}:</b>",
            reply_markup=workers_inline_keyboard(on_shift, order_id, "admin_transfer_sewer")
        )
    elif order["status"] == OrderStatus.PENDING_ADMIN_AFTER_SEWER.value:
        # Возврат к выбору установщика
        installers = await db.get_users_by_role(Role.INSTALLER.value)
        on_shift = [installer for installer in installers if await db.is_on_shift(installer["telegram_id"])]
        if not on_shift:
            on_shift = installers
        await callback.message.edit_text(
            f"👷 <b>Выберите установщика для {order['order_number']}:</b>",
            reply_markup=workers_inline_keyboard(on_shift, order_id, "admin_assign_installer")
        )
    else:
        # Возврат к списку заказов администратора
        await callback.message.edit_text("📋 Возврат в меню администратора.")
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_main_keyboard(Role.ADMIN)
        )

    await callback.answer()


# ============================================================================
# ПАГИНАЦИЯ
# ============================================================================

@dp.callback_query(F.data.startswith("page:"))
async def handle_pagination(callback: CallbackQuery) -> None:
    """Обработка пагинации списков заказов."""
    parts = callback.data.split(":")
    prefix = parts[1]
    page = int(parts[2])

    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    role = Role(user["role"]) if user else Role.SELLER

    offset = page * ORDERS_PER_PAGE
    orders = []
    total = 0

    if prefix == "view_order":
        if role == Role.SELLER:
            orders = await db.get_orders_by_seller(user_id, limit=ORDERS_PER_PAGE, offset=offset)
            total = await db.count_orders_by_seller(user_id)
        elif role == Role.MASTER:
            orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.IN_PROGRESS.value, limit=ORDERS_PER_PAGE, offset=offset)
            total = await db.count_orders(assigned_to=user_id, status=OrderStatus.IN_PROGRESS.value)
        else:
            orders = await db.search_orders(limit=ORDERS_PER_PAGE, offset=offset)
            total = await db.count_orders()

    elif prefix == "m_accept":
        orders = await db.search_orders(
            status=OrderStatus.ASSIGNED_MASTER.value,
            assigned_to=user_id,
            limit=ORDERS_PER_PAGE,
            offset=offset
        )
        total = await db.count_orders(status=OrderStatus.ASSIGNED_MASTER.value, assigned_to=user_id)

    elif prefix == "m_to_admin":
        all_orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.IN_PROGRESS.value)
        total = len(all_orders)
        orders = all_orders[offset:offset + ORDERS_PER_PAGE]

    elif prefix in ("s_accept", "s_to_admin"):
        all_orders = await db.get_orders_for_sewer(user_id)
        total = len(all_orders)
        orders = all_orders[offset:offset + ORDERS_PER_PAGE]

    elif prefix in ("i_view", "i_start", "i_photo"):
        orders_installing = await db.get_orders_for_installer(user_id)
        ready_orders = await db.get_orders_by_status(OrderStatus.ASSIGNED_INSTALLER.value)
        all_orders = orders_installing + [order for order in ready_orders if order not in orders_installing]
        total = len(all_orders)
        orders = all_orders[offset:offset + ORDERS_PER_PAGE]

    elif prefix == "admin_assign":
        all_orders = await db.get_orders_by_status(OrderStatus.NEW.value)
        total = len(all_orders)
        orders = all_orders[offset:offset + ORDERS_PER_PAGE]

    elif prefix == "admin_to_sewer":
        all_orders = await db.get_orders_by_status(OrderStatus.PENDING_ADMIN_AFTER_MASTER.value)
        total = len(all_orders)
        orders = all_orders[offset:offset + ORDERS_PER_PAGE]

    elif prefix == "admin_assign_inst":
        all_orders = await db.get_orders_by_status(OrderStatus.PENDING_ADMIN_AFTER_SEWER.value)
        total = len(all_orders)
        orders = all_orders[offset:offset + ORDERS_PER_PAGE]

    elif prefix == "photo_stage_select":
        if role == Role.MASTER:
            all_orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.IN_PROGRESS.value)
        elif role == Role.SEWER:
            all_orders = await db.get_orders_for_sewer(user_id)
        elif role == Role.INSTALLER:
            all_orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.INSTALLING.value)
        else:
            all_orders = []
        total = len(all_orders)
        orders = all_orders[offset:offset + ORDERS_PER_PAGE]

    elif prefix == "add_mat":
        all_orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.SEWING.value)
        total = len(all_orders)
        orders = all_orders[offset:offset + ORDERS_PER_PAGE]

    if not orders:
        await callback.answer("📭 Больше нет заказов", show_alert=True)
        return

    await callback.message.edit_reply_markup(
        reply_markup=orders_inline_keyboard(orders, prefix, page, total)
    )

    await callback.answer()


# ============================================================================
# ШЕДУЛЕР (ФОНОВЫЕ ЗАДАЧИ)
# ============================================================================

async def scheduler() -> None:
    """Фоновый планировщик задач."""
    last_backup_date = None
    last_overdue_notification = {}

    while True:
        current_time = datetime.now()

        # Утренний отчёт (ежедневно в заданное время)
        if (current_time.hour == DAILY_REPORT_MORNING_HOUR and
                current_time.minute == DAILY_REPORT_MORNING_MINUTE):
            stats = await db.get_daily_stats()
            report_text = (
                "🌅 <b>УТРЕННИЙ ОТЧЁТ</b>\n\n"
                f"📊 Создано сегодня: {stats['created_today']}\n"
                f"✅ Выполнено: {stats['completed_today']}\n"
                f"👥 На смене: {stats['on_shift']}\n"
                f"⏰ Просрочено: {stats['overdue']}\n"
            )
            await notify_all_admins(report_text)

            # Напоминание о начале смены для тех, кто ещё не начал
            shifts_today = await db.get_today_shifts()
            on_shift_ids = {shift["user_id"] for shift in shifts_today}

            for user_id in SELLER_IDS + MASTER_IDS + SEWER_IDS + INSTALLER_IDS:
                if user_id not in on_shift_ids and user_id not in CEO_IDS and user_id not in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            user_id,
                            "⏰ <b>Напоминание!</b>\n\n"
                            "Не забудьте начать смену! Нажмите «⏰ Начать смену» в меню."
                        )
                    except Exception as error:
                        logger.warning(f"Ошибка напоминания пользователю {user_id}: {error}")

            await asyncio.sleep(60)

        # Вечерний отчёт (ежедневно в заданное время)
        elif (current_time.hour == DAILY_REPORT_EVENING_HOUR and
              current_time.minute == DAILY_REPORT_EVENING_MINUTE):
            stats = await db.get_daily_stats()
            report_text = (
                "🌙 <b>ВЕЧЕРНИЙ ОТЧЁТ</b>\n\n"
                f"📊 Создано сегодня: {stats['created_today']}\n"
                f"✅ Выполнено: {stats['completed_today']}\n"
                f"💰 Закупки: {stats['purchases_sum']:.2f} сум\n"
                f"⏰ Просрочено: {stats['overdue']}\n\n"
                "📊 <b>ПО СТАТУСАМ:</b>\n"
            )
            for status, count in stats["status_counts"].items():
                if count > 0:
                    report_text += f"  {status_display(status)}: {count}\n"
            await notify_all_admins(report_text)

            # Напоминание о завершении смены
            shifts_today = await db.get_today_shifts()
            for shift in shifts_today:
                if shift["role"] not in (Role.CEO.value, Role.ADMIN.value, Role.SMM.value):
                    try:
                        await bot.send_message(
                            shift["user_id"],
                            "🌙 <b>Не забудьте завершить смену!</b>\n"
                            "Нажмите «🏁 Закончить смену» в меню."
                        )
                    except Exception as error:
                        logger.warning(f"Ошибка напоминания о завершении смены: {error}")

            await asyncio.sleep(60)

        # Проверка просроченных заказов (каждые DEADLINE_CHECK_INTERVAL секунд)
        else:
            overdue_orders = await db.get_overdue_orders()
            for order in overdue_orders:
                order_id = order["id"]
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

                # Не отправляем чаще 1 раза в 6 часов
                if order_id in last_overdue_notification:
                    try:
                        last_time = datetime.strptime(last_overdue_notification[order_id], "%Y-%m-%d %H:%M")
                        if (datetime.now() - last_time).total_seconds() < 21600:  # 6 часов
                            continue
                    except ValueError:
                        pass

                recipients = set()
                for field in ("seller_id", "master_id", "sewer_id", "installer_id"):
                    if order.get(field):
                        recipients.add(order[field])
                recipients.update(CEO_IDS + ADMIN_IDS)

                notification_text = (
                    f"⏰ <b>ПРОСРОЧЕН!</b>\n\n"
                    f"📋 {order['order_number']}\n"
                    f"👤 {order['client_name']}\n"
                    f"📅 Дедлайн: {order['deadline']}"
                )

                for user_id in recipients:
                    try:
                        await bot.send_message(user_id, notification_text)
                    except Exception as error:
                        logger.warning(f"Ошибка уведомления о просрочке {user_id}: {error}")

                last_overdue_notification[order_id] = now_str

            # Автоматический бэкап (каждые 6 часов)
            if (current_time.hour % 6 == 0 and current_time.minute == 0 and
                    (last_backup_date is None or current_time.date() != last_backup_date)):
                if BACKUP_CHAT_ID:
                    try:
                        with open(DB_PATH, "rb") as backup_file:
                            backup_data = backup_file.read()

                        backup_filename = f"backup_{current_time.strftime('%Y%m%d_%H%M')}.db"
                        backup_file_obj = BufferedInputFile(backup_data, filename=backup_filename)

                        await bot.send_document(
                            BACKUP_CHAT_ID,
                            backup_file_obj,
                            caption=f"💾 Автоматический бэкап {current_time.strftime('%Y-%m-%d %H:%M')}"
                        )
                        last_backup_date = current_time.date()
                        logger.info("Автоматический бэкап отправлен")
                    except Exception as error:
                        logger.error(f"Ошибка создания бэкапа: {error}")

            await asyncio.sleep(DEADLINE_CHECK_INTERVAL)


# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ОБРАБОТЧИКИ ДЛЯ ОБРАБОТКИ НЕИЗВЕСТНЫХ СООБЩЕНИЙ
# ============================================================================

@dp.message(F.text == "👷 Назначить установщика")
async def admin_assign_installer_button(message: Message) -> None:
    """Кнопка назначения установщика (для администратора)."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.ADMIN, Role.CEO):
        await message.answer("🚫 Нет доступа.")
        return

    orders = await db.get_orders_by_status(OrderStatus.PENDING_ADMIN_AFTER_SEWER.value)
    if not orders:
        await message.answer("📭 Нет заказов от швей.")
        return

    total = len(orders)
    await message.answer(
        f"👷 <b>Выберите заказ для назначения установщика ({total}):</b>",
        reply_markup=orders_inline_keyboard(orders[:ORDERS_PER_PAGE], "admin_assign_inst", 0, total)
    )


@dp.message(F.text == "✅ Готово (завершить работу)")
async def installer_complete_button(message: Message) -> None:
    """Кнопка завершения работы для установщика."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    if Role(user["role"]) not in (Role.INSTALLER, Role.CEO, Role.ADMIN):
        await message.answer("🚫 Нет доступа.")
        return

    orders = await db.search_orders(assigned_to=user_id, status=OrderStatus.INSTALLING.value)
    if not orders:
        await message.answer("📭 Нет активных установок.")
        return

    # Отправляем напоминание о необходимости загрузить фото
    await message.answer(
        "📸 <b>Для завершения установки необходимо загрузить фото</b>\n\n"
        "Нажмите «📸 Загрузить фото» для загрузки фото ДО и ПОСЛЕ установки.\n\n"
        "Только после загрузки фото заказ будет отмечен как выполненный."
    )


# ============================================================================
# ОБРАБОТКА НЕИЗВЕСТНЫХ СООБЩЕНИЙ
# ============================================================================

@dp.message()
async def unknown_message(message: Message) -> None:
    """Обработка неизвестных сообщений."""
    user_id = message.from_user.id

    if not is_registered(user_id):
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Используйте /start для начала работы.",
            reply_markup=get_client_menu_keyboard()
        )
        return

    user = await db.get_user(user_id)
    role = Role(user["role"]) if user else Role.SELLER

    await message.answer(
        "❓ Неизвестная команда.\n\n"
        "Используйте кнопки меню для навигации.",
        reply_markup=get_main_keyboard(role)
    )


# ============================================================================
# ЗАПУСК БОТА
# ============================================================================

async def main() -> None:
    """Главная функция запуска бота."""
    try:
        logger.info("Инициализация базы данных...")
        await db.init()

        logger.info("Запуск планировщика задач...")
        asyncio.create_task(scheduler())

        logger.info("Запуск бота Curtain Bot v4.0...")
        await dp.start_polling(bot)
    except Exception as error:
        logger.critical(f"Критическая ошибка при запуске бота: {error}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as error:
        logger.critical(f"Необработанная ошибка: {error}")