#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DeepL Game Translator v3.3.8 - ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ
==============================================================

КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ v3.3.8:
- ✅ УДАЛЁН дубликат функции apply_translations_to_file
- ✅ Поддержка одинарных ' ' и двойных " " кавычек
- ✅ Исправлена проблема с неработающим переводом

Автор: NeR1cH
Версия: 3.3.8 - Final Fixed Edition
"""

import sys
import subprocess
import os
import re
from functools import lru_cache
import time
import zipfile
import tarfile
import tempfile
import shutil
import json
from pathlib import Path
import uuid
import logging
import asyncio

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Проверка и установка зависимостей для асинхронности
try:
    import aiohttp
except ImportError:
    logger.info("Установка aiohttp для асинхронных запросов...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp", "--quiet"])
        import aiohttp
        logger.info("✅ aiohttp установлен!")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить aiohttp: {e}")
        aiohttp = None

try:
    from tqdm import tqdm
except ImportError:
    logger.info("Установка tqdm для прогресс-бара...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm", "--quiet"])
        from tqdm import tqdm
        logger.info("✅ tqdm установлен!")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить tqdm: {e}")
        tqdm = None

# Импортируем tkinter только если не в тестовом режиме
tk = None
ttk = None
filedialog = None
scrolledtext = None

if '--test-mode' not in sys.argv and os.environ.get('TEST_MODE') != '1':
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, scrolledtext
    except ImportError as e:
        logger.warning(f"Tkinter not available, GUI mode disabled: {e}")
        tk = None

# ===================================================================
# КОМПИЛИРОВАННЫЕ REGEX (ОПТИМИЗАЦИЯ ПРОИЗВОДИТЕЛЬНОСТИ)
# ===================================================================

# Паттерны для извлечения английского текста
RE_PERCENT_PLACEHOLDER = re.compile(r'%\w+%')
RE_ENGLISH_WORDS = re.compile(r'\b[A-Za-z]{2,}\b')
RE_STRUCTURAL_KEY = re.compile(r'^([A-ZА-ЯЁ][A-ZА-ЯЁ0-9_]*)\s*:')
RE_DOUBLE_QUOTES = re.compile(r'"([^"]+)"')
RE_SINGLE_QUOTES_COMPLEX = re.compile(r"'([^']+(?:'[^']+)*)'")
RE_SINGLE_QUOTES_SIMPLE = re.compile(r"'([^']+)'")
RE_PLACEHOLDER_BRACES = re.compile(r'\{[A-Z_]+\}')
RE_BRACKETS_BRACES = re.compile(r'[\[\]\{\}]')
RE_CYRILLIC = re.compile(r'[А-Яа-яЁё]')
RE_LATIN = re.compile(r'[A-Za-z]')
RE_PLACEHOLDER_ALL = re.compile(r'\{[^}]*\}')
RE_CURLY_PLACEHOLDERS = re.compile(r'\{[A-Z0-9_]+\}')
RE_SLAVIC_CHARS = re.compile(r'[А-Яа-яЁёЇїІіЄєЎў]')

# ===================================================================
# ПРОВЕРКА И УСТАНОВКА ЗАВИСИМОСТЕЙ
# ===================================================================

def check_dependencies():
    """Проверяет наличие requests"""
    try:
        import requests
        return True
    except ImportError:
        return False

if not check_dependencies():
    logger.info("Установка зависимостей...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "--quiet"])
        logger.info("✅ Зависимости установлены! Перезапусти программу.")
        input("Нажми Enter для выхода...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Не удалось установить requests: {e}")
        logger.error("Выполни вручную: pip install requests")
        input("Нажми Enter для выхода...")
        sys.exit(1)

import requests

# ===================================================================
# КОНФИГУРАЦИЯ
# ===================================================================

CONFIG_FILE = "translator_config.json"

def load_config():
    """Загружает конфигурацию"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки конфига: {e}")
            pass
    return {
        "deepl_api_key": "",
        "microsoft_api_key": "",
        "microsoft_region": "global",
        "default_translator": "deepl"
    }

def save_config(config):
    """Сохраняет конфигурацию"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.warning(f"⚠️ Ошибка сохранения конфига: {e}")
        return False

# ===================================================================
# КРИТИЧЕСКИ ВАЖНЫЕ ФУНКЦИИ
# ===================================================================

def extract_archive(archive_path, extract_to):
    """Распаковывает архив"""
    try:
        if not os.path.exists(archive_path):
            return False
        
        os.makedirs(extract_to, exist_ok=True)
        
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            return True
        
        elif archive_path.endswith(('.tar', '.tar.gz', '.tgz')):
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)
            return True
        
        return False
    except Exception as e:
        logger.warning(f"⚠️ Ошибка распаковки архива: {e}")
        return False

def is_safe_path(base_path, user_path):
    """Проверяет, что путь находится внутри базовой директории (защита от Path Traversal)"""
    base = os.path.abspath(base_path)
    target = os.path.abspath(user_path)
    return target.startswith(base + os.sep) or target == base

def search_folder(folder_path, extract_archives=False):
    """Ищет файлы и извлекает текст"""
    total_files = 0
    unique_texts = set()
    file_structure = {}
    
    # Проверка на Path Traversal
    if not is_safe_path(os.getcwd(), folder_path):
        logger.error(f"❌ Ошибка: путь '{folder_path}' выходит за пределы рабочей директории")
        return 0, set(), {}
    
    text_extensions = ('.txt', '.json', '.yml', '.yaml', '.xml')
    
    try:
        all_files_found = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, folder_path)
                
                if file.endswith(text_extensions):
                    all_files_found.append((file_path, rel_path))
        
        for file_path, rel_path in all_files_found:
            try:
                texts = extract_english_text_from_file(file_path)
                
                if texts:
                    total_files += 1
                    unique_texts.update(texts)
                    file_structure[rel_path] = texts
            except Exception as e:
                logger.warning(f"⚠️ Ошибка обработки {rel_path}: {e}")
        
        return total_files, unique_texts, file_structure
    
    except Exception as e:
        logger.error(f"❌ Критическая ошибка поиска: {e}")
        return 0, set(), {}

# ===================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===================================================================

@lru_cache(maxsize=1000)
def extract_english_parts(text):
    """Извлекает английский текст (с кэшированием)"""
    temp_text = RE_PERCENT_PLACEHOLDER.sub('', text)
    english_words = RE_ENGLISH_WORDS.findall(temp_text)
    
    if english_words:
        return text.strip()
    
    return None

@lru_cache(maxsize=100)
def _get_structural_keys(content_hash, content_sample):
    """Кэширует определение структурных ключей"""
    structural_keys = set()
    for line in content_sample.split('\n'):
        line_stripped = line.strip()
        match = RE_STRUCTURAL_KEY.match(line_stripped)
        if match:
            key = match.group(1)
            structural_keys.add(key)
            structural_keys.add(key.upper())
            structural_keys.add(key.lower())
    
    RESERVED_KEYS = {
        'RATING', 'BAD', 'OK', 'GOOD', 'ATTRACTION', 'SERVICE', 'INN', 'HOTEL',
        'WIKI', 'NAME', 'TEXT', 'CATEGORY', 'CATEGORIES', 'ATTRACTIONS'
    }
    structural_keys.update(RESERVED_KEYS)
    return structural_keys

def extract_english_text_from_file(file_path):
    """Извлекает английский текст из файла (v3.3.9 - ИСПРАВЛЕНА ПРОБЛЕМА С АПОСТРОФАМИ)"""
    results = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Определяем структурные ключи
        structural_keys = _get_structural_keys(hash(content), content[:5000])
        
        # ===== ИСПРАВЛЕННОЕ ИЗВЛЕЧЕНИЕ =====
        # Используем компилированные regex для производительности
        matches = []
        
        # Обработка по строкам
        for line in content.split('\n'):
            # 1. ДВОЙНЫЕ кавычки "..."
            double_quotes = RE_DOUBLE_QUOTES.findall(line)
            matches.extend(double_quotes)
            
            # 2. ОДИНАРНЫЕ кавычки '...', но только если нет двойных кавычек
            if '"' not in line:
                single_quotes = RE_SINGLE_QUOTES_COMPLEX.findall(line)
                
                if not single_quotes:
                    simple_single = RE_SINGLE_QUOTES_SIMPLE.findall(line)
                    matches.extend(simple_single)
                else:
                    matches.extend(single_quotes)
        
        # Фильтрация результатов
        for text in matches:
            text_stripped = text.strip()
            
            if not text_stripped:
                continue
            
            # Пропускаем структурные элементы
            text_without_placeholders = RE_PLACEHOLDER_BRACES.sub('', text_stripped)
            if RE_BRACKETS_BRACES.search(text_without_placeholders):
                continue
            
            # Пропускаем структурные ключи
            if text_stripped in structural_keys:
                continue
            
            # Пропускаем короткие ключи
            words = text_stripped.split()
            if len(words) == 1:
                word = words[0]
                if word.isupper() and word.isalpha() and len(word) <= 15:
                    continue
            
            # Пропускаем строки с преобладанием русского
            cyrillic_count = len(RE_CYRILLIC.findall(text_stripped))
            latin_count = len(RE_LATIN.findall(text_stripped))
            
            if cyrillic_count > latin_count and cyrillic_count > 10:
                continue
            
            # Проверяем наличие английских слов
            text_no_placeholders = RE_PLACEHOLDER_ALL.sub('', text_stripped)
            text_no_placeholders = RE_PERCENT_PLACEHOLDER.sub('', text_no_placeholders)
            english_words = RE_ENGLISH_WORDS.findall(text_no_placeholders)
            
            if len(english_words) == 0:
                continue
            
            results.append(text)
        
        return results
    
    except Exception as e:
        logger.error(f"ERROR: {e}")
        return []

@lru_cache(maxsize=1024)
def extract_placeholders(text):
    """Кэшированное извлечение плейсхолдеров"""
    return re.findall(r'\{[A-Z0-9_]+\}', text)

def translate_with_placeholder_protection(text, api_key, translator="deepl", region="global", retry=3):
    """Переводит с защитой плейсхолдеров"""
    placeholders = extract_placeholders(text)
    
    if not placeholders:
        if translator == "deepl":
            return translate_with_deepl(text, api_key, retry=retry)
        elif translator == "microsoft":
            return translate_with_microsoft(text, api_key, region, retry=retry)
        else:
            return None, "Неизвестный переводчик"
    
    temp_text = text
    placeholder_map = {}
    
    for i, placeholder in enumerate(placeholders):
        temp_marker = f"__PLACEHOLDER_{i}__"
        placeholder_map[temp_marker] = placeholder
        temp_text = temp_text.replace(placeholder, temp_marker, 1)
    
    if translator == "deepl":
        translated = translate_with_deepl(temp_text, api_key, retry=retry)
    elif translator == "microsoft":
        translated = translate_with_microsoft(temp_text, api_key, region, retry=retry)
    else:
        return None, "Неизвестный переводчик"
    
    if isinstance(translated, tuple):
        return translated
    
    for temp_marker, original_placeholder in placeholder_map.items():
        translated = translated.replace(temp_marker, original_placeholder)
    
    return translated.strip()

def apply_translations_to_file(original_file, translations, output_file):
    """Применяет переводы к файлу (v3.3.8 - ПОДДЕРЖКА ' ' и " ")"""
    try:
        with open(original_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"❌ Ошибка чтения {original_file}: {e}")
        return False, 0
    
    if not content.strip():
        os.makedirs(os.path.dirname(output_file), exist_ok=True) if os.path.dirname(output_file) else None
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, 0
    
    # Определяем структурные ключи
    structural_keys = set()
    for line in content.split('\n'):
        match = re.match(r'^([A-ZА-ЯЁ][A-ZА-ЯЁ0-9_]*)\s*:', line.strip())
        if match:
            key = match.group(1)
            structural_keys.update([key, key.upper(), key.lower()])
    
    RESERVED_KEYS = {'RATING', 'BAD', 'OK', 'GOOD', 'ATTRACTION', 'SERVICE', 'INN', 'HOTEL'}
    structural_keys.update(RESERVED_KEYS)
    
    # 🔴 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Заменяем в ОБОИХ типах кавычек!
    replaced_count = 0
    result_lines = []
    
    for line in content.split('\n'):
        result_line = line
        
        # Находим ОБА типа кавычек
        double_matches = list(re.finditer(r'"([^"]*)"', line))
        single_matches = list(re.finditer(r"'([^']*)'", line))
        
        # Сортируем по позиции (в обратном порядке)
        all_matches = sorted(
            [(m, '"') for m in double_matches] + [(m, "'") for m in single_matches],
            key=lambda x: x[0].start(),
            reverse=True
        )
        
        for match, quote_type in all_matches:
            original_text = match.group(1)
            text_stripped = original_text.strip()
            
            # Пропускаем структурные элементы
            if re.search(r'[\[\]\{\}]', text_stripped):
                continue
            
            # Пропускаем структурные ключи
            if text_stripped in structural_keys:
                continue
            
            # Пропускаем короткие ключи
            words = text_stripped.split()
            if len(words) == 1 and words[0].isupper() and words[0].isalpha() and len(words[0]) <= 15:
                continue
            
            if not text_stripped:
                continue
            
            # Ищем перевод
            translated_text = translations.get(original_text)
            if not translated_text:
                clean_text = original_text.replace('%r%', '').replace('%R%', '').strip()
                translated_text = translations.get(clean_text)
            
            # Применяем перевод
            if translated_text:
                start_pos = match.start(1)
                end_pos = match.end(1)
                result_line = result_line[:start_pos] + translated_text + result_line[end_pos:]
                replaced_count += 1
                logger.info(f"✅ [{quote_type}] Заменено: {original_text[:40]}... → {translated_text[:40]}...")
        
        result_lines.append(result_line)
    
    # Сохраняем
    os.makedirs(os.path.dirname(output_file), exist_ok=True) if os.path.dirname(output_file) else None
    with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(result_lines))
    
    return True, replaced_count



def load_translations_from_file(file_path):
    """Загружает переводы из файла"""
    translations = {}
    
    if not os.path.exists(file_path):
        return translations
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split('=', 1)
                if len(parts) == 2:
                    original = parts[0].strip().replace('\\=', '=')
                    translated = parts[1].strip().replace('\\=', '=')
                    if original and translated:
                        translations[original] = translated
    except Exception as e:
        logger.warning(f"⚠️ Ошибка загрузки {file_path}: {e}")
    
    return translations

def load_translations_from_folder(folder_path):
    """Загружает переводы из папки"""
    translations = {}
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.txt'):
                full_path = os.path.join(root, file)
                translations.update(load_translations_from_file(full_path))
    return translations

def save_translations_to_file(file_path, translations):
    """Сохраняет переводы в файл"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True) if os.path.dirname(file_path) else None
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Переводы игры (DeepL Game Translator)\n")
            f.write(f"# Всего фраз: {len(translations)}\n")
            f.write(f"# Формат: оригинал = перевод\n\n")
            
            for eng, rus in sorted(translations.items()):
                eng_escaped = eng.replace('=', '\\=')
                rus_escaped = rus.replace('=', '\\=')
                f.write(f"{eng_escaped} = {rus_escaped}\n")
        
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения: {e}")
        return False

def translate_texts_batch(texts, api_key, translator="deepl", source_lang='EN', target_lang='RU', region='global', retry=3, use_async=True):
    """Пакетный перевод текстов с прогресс-баром и асинхронной поддержкой"""
    if not texts:
        return []
    
    # DeepL поддерживает до 50 текстов в одном запросе
    batch_size = 50
    results = []
    total_batches = (len(texts) + batch_size - 1) // batch_size
    
    # Используем tqdm для прогресс-бара если доступен
    batch_iterator = range(0, len(texts), batch_size)
    if tqdm is not None and len(texts) > batch_size:
        batch_iterator = tqdm.tqdm(batch_iterator, total=total_batches, desc="📦 Пакетный перевод", unit="пакет")
    
    for i in batch_iterator:
        batch = texts[i:i + batch_size]
        
        if translator == "deepl":
            url = "https://api-free.deepl.com/v2/translate" if ':fx' in api_key else "https://api.deepl.com/v2/translate"
            params = {
                'auth_key': api_key,
                'source_lang': source_lang,
                'target_lang': target_lang
            }
            # DeepL принимает multiple text parameters
            for text in batch:
                params.setdefault('text', [])
                params['text'].append(text)
            
            try:
                response = requests.post(url, data=params, timeout=60)
                if response.status_code == 200:
                    translations = [t['text'] for t in response.json()['translations']]
                    results.extend(translations)
                else:
                    # Fallback to individual translation
                    for text in batch:
                        result = translate_with_deepl(text, api_key, source_lang, target_lang, retry)
                        results.append(result[0] if isinstance(result, tuple) else result)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка пакетного перевода DeepL: {e}, используем индивидуальный перевод")
                # Fallback to individual translation
                for text in batch:
                    result = translate_with_deepl(text, api_key, source_lang, target_lang, retry)
                    results.append(result[0] if isinstance(result, tuple) else result)
        
        elif translator == "microsoft":
            endpoint = "https://api.cognitive.microsofttranslator.com/translate"
            params = {'api-version': '3.0', 'from': source_lang, 'to': target_lang}
            headers = {
                'Ocp-Apim-Subscription-Key': api_key,
                'Ocp-Apim-Subscription-Region': region,
                'Content-type': 'application/json',
                'X-ClientTraceId': str(uuid.uuid4())
            }
            body = [{'text': text} for text in batch]
            
            try:
                response = requests.post(endpoint, params=params, headers=headers, json=body, timeout=60)
                if response.status_code == 200:
                    translations = [t['text'] for t in response.json()[0]['translations']]
                    results.extend(translations)
                else:
                    # Fallback to individual translation
                    for text in batch:
                        result = translate_with_microsoft(text, api_key, region, source_lang, target_lang, retry)
                        results.append(result[0] if isinstance(result, tuple) else result)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка пакетного перевода Microsoft: {e}, используем индивидуальный перевод")
                # Fallback to individual translation
                for text in batch:
                    result = translate_with_microsoft(text, api_key, region, source_lang, target_lang, retry)
                    results.append(result[0] if isinstance(result, tuple) else result)
    
    return results


async def translate_texts_batch_async(texts, api_key, translator="deepl", source_lang='EN', target_lang='RU', region='global', retry=3):
    """Асинхронный пакетный перевод текстов с прогресс-баром"""
    if not texts:
        return []
    
    if aiohttp is None:
        logger.warning("⚠️ aiohttp не установлен, используем синхронный перевод")
        return translate_texts_batch(texts, api_key, translator, source_lang, target_lang, region, retry)
    
    batch_size = 50
    results = []
    total_batches = (len(texts) + batch_size - 1) // batch_size
    
    async with aiohttp.ClientSession() as session:
        # Создаем задачи для всех батчей
        tasks = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            task = process_batch_async(session, batch, api_key, translator, source_lang, target_lang, region, retry)
            tasks.append(task)
        
        # Выполняем все задачи с прогресс-баром
        if tqdm is not None and len(tasks) > 1:
            batch_results = []
            for f in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="🚀 Асинхронный перевод", unit="пакет"):
                result = await f
                batch_results.append(result)
            # Собираем результаты в правильном порядке
            for batch_result in batch_results:
                results.extend(batch_result)
        else:
            batch_results = await asyncio.gather(*tasks)
            for batch_result in batch_results:
                results.extend(batch_result)
    
    return results


async def process_batch_async(session, batch, api_key, translator, source_lang, target_lang, region, retry):
    """Обрабатывает один батч асинхронно"""
    if translator == "deepl":
        url = "https://api-free.deepl.com/v2/translate" if ':fx' in api_key else "https://api.deepl.com/v2/translate"
        params = {
            'auth_key': api_key,
            'source_lang': source_lang,
            'target_lang': target_lang
        }
        for text in batch:
            params.setdefault('text', [])
            params['text'].append(text)
        
        for attempt in range(retry):
            try:
                async with session.post(url, data=params, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [t['text'] for t in data['translations']]
                    else:
                        break
            except Exception:
                if attempt == retry - 1:
                    break
                await asyncio.sleep(1)
        
        # Fallback to individual translation
        results = []
        for text in batch:
            result = await translate_with_deepl_async(session, text, api_key, source_lang, target_lang, retry)
            results.append(result[0] if isinstance(result, tuple) else result)
        return results
    
    elif translator == "microsoft":
        endpoint = "https://api.cognitive.microsofttranslator.com/translate"
        params = {'api-version': '3.0', 'from': source_lang, 'to': target_lang}
        headers = {
            'Ocp-Apim-Subscription-Key': api_key,
            'Ocp-Apim-Subscription-Region': region,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
        body = [{'text': text} for text in batch]
        
        for attempt in range(retry):
            try:
                async with session.post(endpoint, params=params, headers=headers, json=body, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [t['text'] for t in data[0]['translations']]
                    else:
                        break
            except Exception:
                if attempt == retry - 1:
                    break
                await asyncio.sleep(1)
        
        # Fallback to individual translation
        results = []
        for text in batch:
            result = await translate_with_microsoft_async(session, text, api_key, region, source_lang, target_lang, retry)
            results.append(result[0] if isinstance(result, tuple) else result)
        return results
    
    return []


async def translate_with_deepl_async(session, text, api_key, source_lang='EN', target_lang='RU', retry=3):
    """Асинхронный перевод через DeepL"""
    url = "https://api-free.deepl.com/v2/translate" if ':fx' in api_key else "https://api.deepl.com/v2/translate"
    params = {
        'auth_key': api_key,
        'text': text,
        'source_lang': source_lang,
        'target_lang': target_lang
    }
    
    for attempt in range(retry):
        try:
            async with session.post(url, data=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['translations'][0]['text']
                elif response.status == 403:
                    return None, "Неверный API ключ"
                elif response.status == 456:
                    return None, "Превышен лимит"
                elif response.status == 429:
                    await asyncio.sleep(5)
                elif response.status == 500:
                    await asyncio.sleep(2)
                else:
                    await asyncio.sleep(1)
        except asyncio.TimeoutError:
            if attempt == retry - 1:
                return None, "Таймаут"
            await asyncio.sleep(1)
        except Exception as e:
            if attempt == retry - 1:
                return None, str(e)
            await asyncio.sleep(1)
    
    return None, "Все попытки исчерпаны"


async def translate_with_microsoft_async(session, text, api_key, region, source_lang='EN', target_lang='RU', retry=3):
    """Асинхронный перевод через Microsoft"""
    endpoint = "https://api.cognitive.microsofttranslator.com/translate"
    params = {'api-version': '3.0', 'from': source_lang, 'to': target_lang}
    headers = {
        'Ocp-Apim-Subscription-Key': api_key,
        'Ocp-Apim-Subscription-Region': region,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{'text': text}]
    
    for attempt in range(retry):
        try:
            async with session.post(endpoint, params=params, headers=headers, json=body, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data[0]['translations'][0]['text']
                elif response.status == 403:
                    return None, "Неверный API ключ"
                elif response.status == 429:
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(1)
        except asyncio.TimeoutError:
            if attempt == retry - 1:
                return None, "Таймаут"
            await asyncio.sleep(1)
        except Exception as e:
            if attempt == retry - 1:
                return None, str(e)
            await asyncio.sleep(1)
    
    return None, "Все попытки исчерпаны"

def translate_with_deepl(text, api_key, source_lang='EN', target_lang='RU', retry=3):
    """Переводит через DeepL"""
    url = "https://api-free.deepl.com/v2/translate" if ':fx' in api_key else "https://api.deepl.com/v2/translate"
    
    params = {
        'auth_key': api_key,
        'text': text,
        'source_lang': source_lang,
        'target_lang': target_lang
    }
    
    for attempt in range(retry):
        try:
            response = requests.post(url, data=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()['translations'][0]['text']
            elif response.status_code == 403:
                return None, "Неверный API ключ"
            elif response.status_code == 456:
                return None, "Превышен лимит"
            elif response.status_code == 429:
                time.sleep(5)
            elif response.status_code == 500:
                if attempt < retry - 1:
                    time.sleep(3)
                else:
                    return None, "Ошибка сервера DeepL"
            else:
                return None, f"Ошибка API: {response.status_code}"
        except Exception as e:
            if attempt < retry - 1:
                time.sleep(2)
            else:
                logger.warning(f"⚠️ Ошибка DeepL API: {e}")
                return None, "Ошибка подключения"
    
    return None, "Не удалось перевести"

def translate_with_microsoft(text, api_key, region='global', source_lang='en', target_lang='ru', retry=3):
    """Переводит через Microsoft"""
    endpoint = "https://api.cognitive.microsofttranslator.com/translate"
    
    params = {'api-version': '3.0', 'from': source_lang, 'to': target_lang}
    headers = {
        'Ocp-Apim-Subscription-Key': api_key,
        'Ocp-Apim-Subscription-Region': region,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{'text': text}]
    
    for attempt in range(retry):
        try:
            response = requests.post(endpoint, params=params, headers=headers, json=body, timeout=30)
            
            if response.status_code == 200:
                return response.json()[0]['translations'][0]['text']
            elif response.status_code in [401, 403]:
                return None, "Ошибка авторизации Microsoft"
            elif response.status_code == 429:
                time.sleep(5)
            elif response.status_code == 500:
                if attempt < retry - 1:
                    time.sleep(3)
                else:
                    return None, "Ошибка сервера Microsoft"
            else:
                return None, f"Ошибка API: {response.status_code}"
        except Exception as e:
            if attempt < retry - 1:
                time.sleep(2)
            else:
                logger.warning(f"⚠️ Ошибка Microsoft API: {e}")
                return None, "Ошибка подключения"
    
    return None, "Не удалось перевести"

# ===================================================================
# ГЛАВНОЕ ОКНО ПРИЛОЖЕНИЯ
# ===================================================================

class TranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🌐 DeepL Game Translator")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
    
        # Загружаем конфигурацию
        self.config = load_config()
        self.deepl_api_key = self.config.get("deepl_api_key", "")
        self.microsoft_api_key = self.config.get("microsoft_api_key", "")
        self.microsoft_region = self.config.get("microsoft_region", "global")
        self.current_translator = self.config.get("default_translator", "deepl")

        self.center_window()
        self.setup_style()
        self.create_ui()
        # Переменные для управления процессом перевода
        self.translation_paused = False
        self.translation_running = False
        self.current_translation_progress = {
            'translated': {},
            'current_index': 0,
            'total': 0,
            'texts': []
}
    
        # Проверяем наличие API ключей
        if not self.deepl_api_key and not self.microsoft_api_key:
            self.status_bar.config(text="⚠️ API ключи не настроены - откройте Настройки", 
                                bg="#e74c3c", fg="white")
            # Автоматически открываем настройки при первом запуске
            self.root.after(500, self.show_settings)
        else:
            configured = []
            if self.deepl_api_key:
                configured.append("DeepL")
            if self.microsoft_api_key:
                configured.append("Microsoft")
            self.status_bar.config(text=f"✅ Настроены переводчики: {', '.join(configured)}", 
                                bg="#27ae60", fg="white")
    
    def center_window(self):
        """Центрирует окно"""
        self.root.update_idletasks()
        width = 900
        height = 700
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def setup_style(self):
        """Настройка стилей"""
        style = ttk.Style()
        style.theme_use('clam')
        
        self.root.configure(bg="#f5f6fa")
        
        style.configure("Header.TFrame", background="#2c3e50")
        style.configure("Content.TFrame", background="white")
        
        style.configure("Title.TLabel", 
                       background="#2c3e50",
                       foreground="white",
                       font=("Segoe UI", 20, "bold"))
        
        style.configure("Subtitle.TLabel",
                       background="#2c3e50",
                       foreground="#ecf0f1",
                       font=("Segoe UI", 10))
        
        style.configure("Accent.TButton",
                       font=("Segoe UI", 10, "bold"),
                       padding=10)
    def log_message(self, tab, message):
        """Добавление сообщения в лог"""
        if tab == "translate":
            self.translate_log.insert(tk.END, message + "\n")
            self.translate_log.see(tk.END)
        elif tab == "apply":
            self.apply_log.insert(tk.END, message + "\n")
            self.apply_log.see(tk.END)
        elif tab == "verify":
            self.verify_log.insert(tk.END, message + "\n")
            self.verify_log.see(tk.END)
        elif tab == "convert":
            self.convert_log.insert(tk.END, message + "\n")
            self.convert_log.see(tk.END)
        
        self.root.update()
    
    def show_error(self, title, message):
        """Показать ошибку"""
        ErrorDialog(self.root, title, message)
    
    def show_info(self, title, message):
        """Показать информацию"""
        InfoDialog(self.root, title, message)
    
    def ask_yes_no(self, title, message):
        """Спросить да/нет"""
        return YesNoDialog(self.root, title, message).result

    def show_settings(self):
        """Показать настройки"""
        SettingsDialog(self.root, self)
    
    def show_help(self):
        """Показать помощь"""
        HelpDialog(self.root)
    
    def show_archive_browser(self, archive_path):
        """Показывает браузер содержимого архива"""
        try:
            browser = ArchiveBrowserDialog(self.root, self, archive_path)
        except Exception as e:
            self.show_error("Ошибка", f"Не удалось открыть браузер архива:\n{str(e)}")

    def create_ui(self):
        """Создание интерфейса"""
        # Заголовок
        header = ttk.Frame(self.root, style="Header.TFrame", height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        title = ttk.Label(header, text="🌐 DeepL Game Translator", style="Title.TLabel")
        title.pack(pady=(15, 5))
        
        subtitle = ttk.Label(header, text="Профессиональный перевод игр", style="Subtitle.TLabel")
        subtitle.pack()
        
        # Верхняя панель с кнопками
        toolbar = tk.Frame(self.root, bg="#ecf0f1", height=60)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        
        btn_frame = tk.Frame(toolbar, bg="#ecf0f1")
        btn_frame.pack(expand=True, pady=10)
        
        ttk.Button(btn_frame, text="⚙️ Настройки", command=self.show_settings, width=15).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="❓ Помощь", command=self.show_help, width=15).pack(side="left", padx=5)
        
        # Основная область с вкладками
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Вкладки
        self.create_translate_tab()
        self.create_apply_tab()
        self.create_verify_tab()
        self.create_convert_tab()
        
        # Статус-бар
        self.status_bar = tk.Label(self.root, text="Готов к работе", 
                                   bg="#34495e", fg="white", 
                                   anchor="w", padx=10, height=2)
        self.status_bar.pack(fill="x", side="bottom")
    
    def create_translate_tab(self):
        """Вкладка перевода"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🌐 Перевод")
        
        # Scrollable frame
        canvas = tk.Canvas(tab, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg="white")
        
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Тип перевода
        type_frame = tk.LabelFrame(content, text="Тип перевода", bg="white", 
                                   font=("Segoe UI", 10, "bold"), padx=20, pady=15)
        type_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        self.translate_type = tk.StringVar(value="game")
        tk.Radiobutton(type_frame, text="🎮 Файлы игры (извлечение английского текста)", 
                      variable=self.translate_type, value="game", bg="white",
                      font=("Segoe UI", 10)).pack(anchor="w", pady=5)
        tk.Radiobutton(type_frame, text="📄 Обычный текст (построчный перевод)", 
                      variable=self.translate_type, value="text", bg="white",
                      font=("Segoe UI", 10)).pack(anchor="w", pady=5)
        
        # Выбор переводчика (добавить ПОСЛЕ type_frame.pack)
        translator_frame = tk.LabelFrame(content, text="Выбор переводчика", bg="white", 
                                        font=("Segoe UI", 10, "bold"), padx=20, pady=15)
        translator_frame.pack(fill="x", padx=20, pady=10)

        self.translator_choice = tk.StringVar(value=self.current_translator)
        tk.Radiobutton(translator_frame, text="🌐 DeepL (500K символов/месяц бесплатно)", 
                    variable=self.translator_choice, value="deepl", bg="white",
                    font=("Segoe UI", 10)).pack(anchor="w", pady=5)
        tk.Radiobutton(translator_frame, text="🔷 Microsoft Translator (2M символов/месяц бесплатно)", 
                    variable=self.translator_choice, value="microsoft", bg="white",
                    font=("Segoe UI", 10)).pack(anchor="w", pady=5)
        
        # Источник
        source_frame = tk.LabelFrame(content, text="Источник файлов", bg="white",
                                    font=("Segoe UI", 10, "bold"), padx=20, pady=15)
        source_frame.pack(fill="x", padx=20, pady=10)
        
        btn_row1 = tk.Frame(source_frame, bg="white")
        btn_row1.pack(fill="x", pady=5)
        ttk.Button(btn_row1, text="📦 Выбрать архив", 
                  command=self.select_archive_translate, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row1, text="📁 Выбрать папку", 
                  command=self.select_folder_translate, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row1, text="📄 Выбрать файл",
                  command=self.select_file_translate, width=20).pack(side="left", padx=5)
        
        self.translate_source_label = tk.Label(source_frame, text="Не выбрано", 
                                              bg="white", fg="#7f8c8d", 
                                              font=("Segoe UI", 9))
        self.translate_source_label.pack(anchor="w", pady=5)
        
        # Существующие переводы (опционально)
        existing_frame = tk.LabelFrame(content, text="Загрузить существующие переводы (опционально)", 
                                      bg="white", font=("Segoe UI", 10, "bold"), 
                                      padx=20, pady=15)
        existing_frame.pack(fill="x", padx=20, pady=10)
        
        btn_row2 = tk.Frame(existing_frame, bg="white")
        btn_row2.pack(fill="x", pady=5)
        ttk.Button(btn_row2, text="📄 Файл переводов",
                  command=self.load_existing_file, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row2, text="📁 Папка переводов",
                  command=self.load_existing_folder, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row2, text="🗑️ Очистить",
                  command=self.clear_existing, width=20).pack(side="left", padx=5)
        
        self.existing_label = tk.Label(existing_frame, text="Не загружено",
                                      bg="white", fg="#7f8c8d",
                                      font=("Segoe UI", 9))
        self.existing_label.pack(anchor="w", pady=5)
        
        # Прогресс
        progress_frame = tk.LabelFrame(content, text="Прогресс", bg="white",
                                      font=("Segoe UI", 10, "bold"),
                                      padx=20, pady=15)
        progress_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.translate_progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.translate_progress.pack(fill="x", pady=5)
        
        self.translate_log = scrolledtext.ScrolledText(progress_frame, height=10,
                                                       font=("Consolas", 9),
                                                       bg="#f8f9fa", fg="#2c3e50")
        self.translate_log.pack(fill="both", expand=True, pady=5)
        
        # Кнопки действий
        action_frame = tk.Frame(content, bg="white")
        action_frame.pack(fill="x", padx=20, pady=20)

        ttk.Button(action_frame, text="▶️ Начать/Продолжить",
                command=self.start_translation,
                style="Accent.TButton", width=20).pack(side="left", padx=5)
        ttk.Button(action_frame, text="⏸️ Пауза",
                command=self.pause_translation, width=15).pack(side="left", padx=5)
        ttk.Button(action_frame, text="💾 Сохранить результат",
                command=self.save_translation_result, width=20).pack(side="left", padx=5)
        
        # Данные
        self.translate_source = None
        self.translate_source_type = None
        self.existing_translations = {}
        self.current_translations = {}
    
    def create_apply_tab(self):
        """Вкладка применения переводов"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📝 Применить")
        
        canvas = tk.Canvas(tab, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg="white")
        
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Переводы
        trans_frame = tk.LabelFrame(content, text="Шаг 1: Загрузить переводы", bg="white",
                                   font=("Segoe UI", 10, "bold"), padx=20, pady=15)
        trans_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        btn_row = tk.Frame(trans_frame, bg="white")
        btn_row.pack(fill="x", pady=5)
        ttk.Button(btn_row, text="📄 Файл переводов",
                  command=self.load_apply_translations_file, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row, text="📁 Папка переводов",
                  command=self.load_apply_translations_folder, width=20).pack(side="left", padx=5)
        
        self.apply_trans_label = tk.Label(trans_frame, text="Не загружено",
                                         bg="white", fg="#7f8c8d", font=("Segoe UI", 9))
        self.apply_trans_label.pack(anchor="w", pady=5)
        
        # Оригинальные файлы
        orig_frame = tk.LabelFrame(content, text="Шаг 2: Выбрать оригинальные файлы",
                                  bg="white", font=("Segoe UI", 10, "bold"),
                                  padx=20, pady=15)
        orig_frame.pack(fill="x", padx=20, pady=10)
        
        btn_row2 = tk.Frame(orig_frame, bg="white")
        btn_row2.pack(fill="x", pady=5)
        ttk.Button(btn_row2, text="📄 Один файл",
                  command=self.select_original_file, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row2, text="📁 Папка",
                  command=self.select_original_folder, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row2, text="📦 Архив",
                  command=self.select_original_archive, width=20).pack(side="left", padx=5)
        
        self.apply_orig_label = tk.Label(orig_frame, text="Не выбрано",
                                        bg="white", fg="#7f8c8d", font=("Segoe UI", 9))
        self.apply_orig_label.pack(anchor="w", pady=5)
        
        # Вывод
        output_frame = tk.LabelFrame(content, text="Шаг 3: Куда сохранить результат",
                                    bg="white", font=("Segoe UI", 10, "bold"),
                                    padx=20, pady=15)
        output_frame.pack(fill="x", padx=20, pady=10)
        
        btn_row3 = tk.Frame(output_frame, bg="white")
        btn_row3.pack(fill="x", pady=5)
        ttk.Button(btn_row3, text="📄 Сохранить как файл",
                  command=self.select_output_file, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row3, text="📁 Выбрать папку",
                  command=self.select_output_folder, width=20).pack(side="left", padx=5)
        
        self.apply_output_label = tk.Label(output_frame, text="Не выбрано",
                                          bg="white", fg="#7f8c8d", font=("Segoe UI", 9))
        self.apply_output_label.pack(anchor="w", pady=5)
        
        # Прогресс
        progress_frame = tk.LabelFrame(content, text="Прогресс применения", bg="white",
                                      font=("Segoe UI", 10, "bold"), padx=20, pady=15)
        progress_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.apply_progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.apply_progress.pack(fill="x", pady=5)
        
        self.apply_log = scrolledtext.ScrolledText(progress_frame, height=10,
                                                   font=("Consolas", 9),
                                                   bg="#f8f9fa", fg="#2c3e50")
        self.apply_log.pack(fill="both", expand=True, pady=5)
        
        # Кнопка
        action_frame = tk.Frame(content, bg="white")
        action_frame.pack(fill="x", padx=20, pady=20)
        
        ttk.Button(action_frame, text="▶️ Применить переводы",
                  command=self.apply_translations,
                  style="Accent.TButton", width=30).pack()
        
        # Данные
        self.apply_translations_dict = {}
        self.apply_original_path = None
        self.apply_original_type = None
        self.apply_output_path = None
    
    def create_verify_tab(self):
        """Вкладка проверки"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔍 Проверка")
        
        canvas = tk.Canvas(tab, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg="white")
        
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Загрузка
        load_frame = tk.LabelFrame(content, text="Загрузить переводы для проверки",
                                  bg="white", font=("Segoe UI", 10, "bold"),
                                  padx=20, pady=15)
        load_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        btn_row = tk.Frame(load_frame, bg="white")
        btn_row.pack(fill="x", pady=5)
        ttk.Button(btn_row, text="📄 Файл переводов",
                  command=self.load_verify_file, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row, text="📁 Папка переводов",
                  command=self.load_verify_folder, width=20).pack(side="left", padx=5)
        
        self.verify_source_label = tk.Label(load_frame, text="Не загружено",
                                           bg="white", fg="#7f8c8d", font=("Segoe UI", 9))
        self.verify_source_label.pack(anchor="w", pady=5)
        
        # Статистика
        stats_frame = tk.LabelFrame(content, text="Статистика проверки", bg="white",
                                   font=("Segoe UI", 10, "bold"), padx=20, pady=15)
        stats_frame.pack(fill="x", padx=20, pady=10)
        
        self.verify_stats_text = tk.Text(stats_frame, height=6, font=("Segoe UI", 10),
                                        bg="#f8f9fa", fg="#2c3e50", relief="flat")
        self.verify_stats_text.pack(fill="x", pady=5)
        
        # Лог
        log_frame = tk.LabelFrame(content, text="Детали проверки", bg="white",
                                 font=("Segoe UI", 10, "bold"), padx=20, pady=15)
        log_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.verify_log = scrolledtext.ScrolledText(log_frame, height=10,
                                                    font=("Consolas", 9),
                                                    bg="#f8f9fa", fg="#2c3e50")
        self.verify_log.pack(fill="both", expand=True, pady=5)
        
        # Кнопки
        action_frame = tk.Frame(content, bg="white")
        action_frame.pack(fill="x", padx=20, pady=20)
        
        ttk.Button(action_frame, text="🔍 Проверить качество",
                  command=self.verify_translations,
                  style="Accent.TButton", width=25).pack(side="left", padx=5)
        ttk.Button(action_frame, text="🔧 Исправить ошибки",
                  command=self.fix_translations, width=25).pack(side="left", padx=5)
        ttk.Button(action_frame, text="💾 Сохранить",
                  command=self.save_verified, width=25).pack(side="left", padx=5)
        
        # Данные
        self.verify_translations_dict = {}
        self.verify_errors = []
    
    def create_convert_tab(self):
        """Вкладка конвертации"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔄 Конвертация")
        
        canvas = tk.Canvas(tab, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg="white")
        
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Описание
        desc_frame = tk.Frame(content, bg="#e8f4f8", relief="solid", borderwidth=1)
        desc_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        desc_text = """
🔄 КОНВЕРТАЦИЯ ФОРМАТА ПЕРЕВОДОВ

Эта функция преобразует переводы из формата "оригинал = перевод" 
в формат игры с сохранением структуры файлов.

Идеально подходит для финальной подготовки перевода перед установкой в игру.
        """
        tk.Label(desc_frame, text=desc_text.strip(), font=("Segoe UI", 9),
                bg="#e8f4f8", fg="#2c3e50", justify="left").pack(padx=15, pady=10)
        
        # Загрузка переводов
        trans_frame = tk.LabelFrame(content, text="Шаг 1: Загрузить переводы", bg="white",
                                   font=("Segoe UI", 10, "bold"), padx=20, pady=15)
        trans_frame.pack(fill="x", padx=20, pady=10)
        
        btn_row = tk.Frame(trans_frame, bg="white")
        btn_row.pack(fill="x", pady=5)
        ttk.Button(btn_row, text="📄 Файл переводов",
                  command=self.load_convert_translations_file, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row, text="📁 Папка переводов",
                  command=self.load_convert_translations_folder, width=20).pack(side="left", padx=5)
        
        self.convert_trans_label = tk.Label(trans_frame, text="Не загружено",
                                           bg="white", fg="#7f8c8d", font=("Segoe UI", 9))
        self.convert_trans_label.pack(anchor="w", pady=5)
        
        # Оригинальная структура
        struct_frame = tk.LabelFrame(content, text="Шаг 2: Выбрать оригинальную структуру",
                                    bg="white", font=("Segoe UI", 10, "bold"),
                                    padx=20, pady=15)
        struct_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Label(struct_frame, text="Выберите оригинальные файлы игры для сохранения структуры:",
                font=("Segoe UI", 9), bg="white", fg="#7f8c8d").pack(anchor="w", pady=5)
        
        btn_row2 = tk.Frame(struct_frame, bg="white")
        btn_row2.pack(fill="x", pady=5)
        ttk.Button(btn_row2, text="📁 Папка с оригиналами",
                  command=self.select_convert_original_folder, width=20).pack(side="left", padx=5)
        ttk.Button(btn_row2, text="📦 Архив с оригиналами",
                  command=self.select_convert_original_archive, width=20).pack(side="left", padx=5)
        
        self.convert_struct_label = tk.Label(struct_frame, text="Не выбрано",
                                            bg="white", fg="#7f8c8d", font=("Segoe UI", 9))
        self.convert_struct_label.pack(anchor="w", pady=5)
        
        # Выходная папка
        output_frame = tk.LabelFrame(content, text="Шаг 3: Куда сохранить результат",
                                    bg="white", font=("Segoe UI", 10, "bold"),
                                    padx=20, pady=15)
        output_frame.pack(fill="x", padx=20, pady=10)
        
        btn_row3 = tk.Frame(output_frame, bg="white")
        btn_row3.pack(fill="x", pady=5)
        ttk.Button(btn_row3, text="📁 Выбрать папку для результата",
                  command=self.select_convert_output, width=30).pack(side="left", padx=5)
        
        self.convert_output_label = tk.Label(output_frame, text="Не выбрано",
                                            bg="white", fg="#7f8c8d", font=("Segoe UI", 9))
        self.convert_output_label.pack(anchor="w", pady=5)
        
        # Сохранение результатов
        save_frame = tk.LabelFrame(content, text="Сохранение", bg="white",
                                  font=("Segoe UI", 10, "bold"), padx=20, pady=15)
        save_frame.pack(fill="x", padx=20, pady=10)
        
        self.convert_on_translate = tk.BooleanVar(value=False)
        tk.Checkbutton(save_frame, text="✅ Автоматически конвертировать при переводе",
                      variable=self.convert_on_translate, bg="white",
                      font=("Segoe UI", 10)).pack(anchor="w", pady=5)
        
        tk.Label(save_frame, 
                text="Если включено, новые переводы будут сразу сохраняться в формате игры",
                font=("Segoe UI", 8, "italic"), bg="white", fg="#95a5a6").pack(anchor="w", padx=20)
        
        # Прогресс
        progress_frame = tk.LabelFrame(content, text="Прогресс конвертации", bg="white",
                                      font=("Segoe UI", 10, "bold"), padx=20, pady=15)
        progress_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.convert_progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.convert_progress.pack(fill="x", pady=5)
        
        self.convert_log = scrolledtext.ScrolledText(progress_frame, height=10,
                                                     font=("Consolas", 9),
                                                     bg="#f8f9fa", fg="#2c3e50")
        self.convert_log.pack(fill="both", expand=True, pady=5)
        
        # Кнопка
        action_frame = tk.Frame(content, bg="white")
        action_frame.pack(fill="x", padx=20, pady=20)
        
        ttk.Button(action_frame, text="🔄 Конвертировать и сохранить",
                  command=self.convert_translations,
                  style="Accent.TButton", width=35).pack()
        
        # Данные
        self.convert_translations_dict = {}
        self.convert_original_path = None
        self.convert_original_type = None
        self.convert_output_path = None
    
    # ===================================================================
    # МЕТОДЫ ДЛЯ ВКЛАДКИ ПЕРЕВОДА
    # ===================================================================
    
    def select_archive_translate(self):
        """Выбор архива для перевода"""
        path = filedialog.askopenfilename(
            title="Выберите архив",
            filetypes=[("Архивы", "*.zip *.tar *.tar.gz *.tgz"), ("Все файлы", "*.*")]
        )
        if not path:
            return

        # Спрашиваем, хочет ли пользователь выбрать конкретные файлы
        choice = self.ask_yes_no(
            "Выбор файлов",
            "Хотите выбрать конкретные файлы/папки внутри архива?\n\n"
            "ДА - Открыть содержимое архива для выбора\n"
            "НЕТ - Обработать весь архив целиком"
        )
        
        if choice is None:
            return
        
        if choice:
            # Показываем содержимое архива для выбора БЕЗ ЗАДЕРЖКИ
            try:
                self.show_archive_browser(path)
            except Exception as e:
                self.show_error("Ошибка", f"Не удалось открыть браузер архива:\n{e}")
        else:
            # Обрабатываем весь архив
            self.translate_source = path
            self.translate_source_type = "archive"
            self.translate_source_label.config(text=f"Архив: {os.path.basename(path)}", fg="#27ae60")
            self.log_message("translate", f"✅ Выбран архив: {os.path.basename(path)}")
    def select_folder_translate(self):
        """Выбор папки для перевода"""
        path = filedialog.askdirectory(title="Выберите папку")
        if path:
            self.translate_source = path
            self.translate_source_type = "folder"
            self.translate_source_label.config(text=f"Папка: {os.path.basename(path)}", fg="#27ae60")
            self.log_message("translate", f"✅ Выбрана папка: {os.path.basename(path)}")
    
    def select_file_translate(self):
        """Выбор файла для перевода"""
        path = filedialog.askopenfilename(
            title="Выберите файл",
            filetypes=[("Текстовые файлы", "*.txt"), ("JSON", "*.json"), ("Все файлы", "*.*")]
        )
        if path:
            self.translate_source = path
            self.translate_source_type = "file"
            self.translate_source_label.config(text=f"Файл: {os.path.basename(path)}", fg="#27ae60")
            self.log_message("translate", f"✅ Выбран файл: {os.path.basename(path)}")
    
    def load_existing_file(self):
        """Загрузка существующих переводов из файла"""
        path = filedialog.askopenfilename(
            title="Выберите файл с переводами",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            trans = load_translations_from_file(path)
            self.existing_translations.update(trans)
            self.existing_label.config(
                text=f"Загружено: {len(self.existing_translations)} фраз",
                fg="#27ae60"
            )
            self.log_message("translate", f"✅ Загружено {len(trans)} переводов из файла")
    
    def load_existing_folder(self):
        """Загрузка существующих переводов из папки"""
        path = filedialog.askdirectory(title="Выберите папку с переводами")
        if path:
            trans = load_translations_from_folder(path)
            self.existing_translations.update(trans)
            self.existing_label.config(
                text=f"Загружено: {len(self.existing_translations)} фраз",
                fg="#27ae60"
            )
            self.log_message("translate", f"✅ Загружено {len(trans)} переводов из папки")
    
    def clear_existing(self):
        """Очистка существующих переводов"""
        self.existing_translations = {}
        self.existing_label.config(text="Не загружено", fg="#7f8c8d")
        self.log_message("translate", "🗑️ Существующие переводы очищены")
    
    def start_translation(self):
        """Запуск процесса перевода с автосохранением и паузой"""
        translator = self.translator_choice.get()
        if translator == "deepl":
            if not self.deepl_api_key:
                self.show_error("Ошибка", "DeepL API ключ не настроен! Перейдите в Настройки.")
                return
            current_api_key = self.deepl_api_key
        elif translator == "microsoft":
            if not self.microsoft_api_key:
                self.show_error("Ошибка", "Microsoft API ключ не настроен! Перейдите в Настройки.")
                return
            current_api_key = self.microsoft_api_key
        else:
            self.show_error("Ошибка", "Выберите переводчик!")
            return
        
        if not self.translate_source:
            self.show_error("Ошибка", "Не выбран источник для перевода!")
            return
        
        # Проверяем, возобновляем ли мы перевод
        if self.translation_running and self.translation_paused:
            self.resume_translation()
            return
        
        self.translation_running = True
        self.translation_paused = False
        
        self.log_message("translate", "\n" + "="*50)
        self.log_message("translate", "🚀 НАЧАЛО ПЕРЕВОДА (v3.3 - с автосохранением)")
        self.log_message("translate", "="*50)
        
        # Извлечение текстов (без изменений)
        self.log_message("translate", "🔍 Поиск текстов для перевода...")
        
        texts_to_translate = []
        file_structure = {}
        
        try:
            if self.translate_source_type == "archive":
                temp_dir = tempfile.mkdtemp(prefix='translate_')
                if extract_archive(self.translate_source, temp_dir):
                    self.log_message("translate", "📦 Архив распакован")
                    _, unique_texts, file_structure = search_folder(temp_dir, extract_archives=False)
                    texts_to_translate = list(unique_texts)
                    shutil.rmtree(temp_dir)
                else:
                    self.show_error("Ошибка", "Не удалось распаковать архив")
                    return
            
            elif self.translate_source_type == "folder":
                _, unique_texts, file_structure = search_folder(self.translate_source)
                texts_to_translate = list(unique_texts)
            
            elif self.translate_source_type == "file":
                if self.translate_type.get() == "game":
                    texts = extract_english_text_from_file(self.translate_source)
                    texts_to_translate = texts
                    file_structure[os.path.basename(self.translate_source)] = texts
                else:
                    with open(self.translate_source, 'r', encoding='utf-8') as f:
                        texts_to_translate = [line.strip() for line in f if line.strip()]
                    file_structure[os.path.basename(self.translate_source)] = texts_to_translate
        
        except Exception as e:
            self.show_error("Ошибка", f"Не удалось обработать источник:\n{e}")
            return
        
        if not texts_to_translate:
            self.show_error("Внимание", "Не найдено текстов для перевода!")
            return
        
        # Фильтрация уже переведённых
        new_texts = [t for t in texts_to_translate if t not in self.existing_translations]
        
        self.log_message("translate", f"📊 Найдено текстов: {len(texts_to_translate)}")
        self.log_message("translate", f"✅ Уже переведено: {len(texts_to_translate) - len(new_texts)}")
        self.log_message("translate", f"🆕 Требует перевода: {len(new_texts)}")
        
        if not new_texts:
            self.show_info("Готово", "Все тексты уже переведены!")
            return
        
        # Инициализация прогресса
        self.current_translation_progress = {
            'translated': dict(self.existing_translations),
            'current_index': 0,
            'total': len(new_texts),
            'texts': new_texts
        }
        
        # Начинаем перевод
        self.perform_translation()

    def perform_translation(self):
        """Выполняет перевод с автосохранением каждые 10 строк"""
        progress = self.current_translation_progress
        new_texts = progress['texts']
        
        self.translate_progress['maximum'] = progress['total']
        
        import datetime
        autosave_folder = os.path.join(tempfile.gettempdir(), "deepl_autosave")
        os.makedirs(autosave_folder, exist_ok=True)
        
        self.log_message("translate", f"💾 Автосохранения в: {autosave_folder}\n")
        
        for i in range(progress['current_index'], progress['total']):
            # Проверка паузы
            if self.translation_paused:
                self.log_message("translate", "\n⏸️ ПЕРЕВОД ПРИОСТАНОВЛЕН")
                self.log_message("translate", f"📊 Переведено: {i}/{progress['total']}")
                self.log_message("translate", f"💾 Прогресс сохранён. Нажмите 'Начать перевод' для продолжения")
                progress['current_index'] = i
                return
            
            text = new_texts[i]
            self.translate_progress['value'] = i + 1
            percent = ((i + 1) / progress['total']) * 100
            
            self.log_message("translate", f"[{i+1}/{progress['total']}] ({percent:.1f}%) {text[:50]}...")
            self.root.update()
            
            # НОВЫЙ КОД: Используем защищённый перевод
            translator = self.translator_choice.get()
            result = translate_with_placeholder_protection(
                text, 
                self.deepl_api_key if translator == "deepl" else self.microsoft_api_key,
                translator=translator,
                region=self.microsoft_region,
                retry=3
            )
            
            if isinstance(result, tuple):
                self.log_message("translate", f"   ❌ Ошибка: {result[1]}")
            else:
                progress['translated'][text] = result
                self.log_message("translate", f"   ✅ {result[:50]}...")
            
            # АВТОСОХРАНЕНИЕ КАЖДЫЕ 10 СТРОК
            if (i + 1) % 10 == 0:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                autosave_file = os.path.join(autosave_folder, f"autosave_{timestamp}.txt")
                
                if save_translations_to_file(autosave_file, progress['translated']):
                    self.log_message("translate", f"   💾 Автосохранение: {i+1} фраз → {os.path.basename(autosave_file)}")
            
            time.sleep(0.3)
        
        # Перевод завершён
        self.current_translations = progress['translated']
        self.translation_running = False
        self.translation_paused = False
        
        # Финальное сохранение
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        final_save = os.path.join(autosave_folder, f"final_{timestamp}.txt")
        save_translations_to_file(final_save, self.current_translations)
        
        self.log_message("translate", f"\n✅ Перевод завершён!")
        self.log_message("translate", f"📊 Переведено: {len(self.current_translations)}")
        self.log_message("translate", f"💾 Финальный файл: {os.path.basename(final_save)}")
        self.log_message("translate", f"📁 Папка автосохранений: {autosave_folder}")
        
        self.show_info("Готово", 
                    f"Переведено {len(self.current_translations)} фраз!\n\n"
                    f"💾 Автосохранения в:\n{autosave_folder}\n\n"
                    f"📄 Финальный файл:\n{os.path.basename(final_save)}")
        
    def pause_translation(self):
        """Приостановить перевод"""
        if self.translation_running and not self.translation_paused:
            self.translation_paused = True
            self.status_bar.config(text="⏸️ Перевод приостановлен - нажмите 'Начать перевод' для продолжения", 
                                bg="#f39c12", fg="white")
            self.log_message("translate", "\n⏸️ Запрос на приостановку перевода...")

    def resume_translation(self):
        """Возобновить перевод"""
        if self.translation_running and self.translation_paused:
            self.translation_paused = False
            self.status_bar.config(text="▶️ Перевод возобновлён", bg="#27ae60", fg="white")
            self.log_message("translate", "\n▶️ ВОЗОБНОВЛЕНИЕ ПЕРЕВОДА")
            self.log_message("translate", f"📊 Продолжаем с позиции: {self.current_translation_progress['current_index']}")
            self.perform_translation()
    def save_translation_result(self):
            """Сохранение результатов перевода"""
            if not self.current_translations:
                    self.show_error("Ошибка", "Нет переводов для сохранения!")
                    return
                
                # Проверяем, нужна ли автоматическая конвертация
            if self.convert_on_translate.get():
                    self.log_message("translate", "\n🔄 Автоматическая конвертация включена")
                    
                    if not self.convert_original_path or not self.convert_output_path:
                        choice = self.ask_yes_no("Настройка конвертации",
                                                "Для автоматической конвертации нужно настроить:\n"
                                                "• Папку/архив с оригинальными файлами\n"
                                                "• Папку для результата\n\n"
                                                "Перейти на вкладку конвертации для настройки?")
                        if choice:
                            self.notebook.select(3)  # Переключаемся на вкладку конвертации
                        return
                    
                    # Сначала сохраняем переводы в файл
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    temp_trans_file = os.path.join(tempfile.gettempdir(), f"translations_{timestamp}.txt")
                    
                    if save_translations_to_file(temp_trans_file, self.current_translations):
                        self.log_message("translate", f"💾 Переводы сохранены во временный файл")
                        
                        # Выполняем конвертацию
                        self.log_message("translate", "🔄 Конвертирую переводы в формат игры...")
                        success = self.perform_conversion(self.current_translations)
                        
                        if success:
                            self.log_message("translate", "✅ Конвертация завершена!")
                            
                            # Предлагаем сохранить и обычный файл с переводами
                            choice = self.ask_yes_no("Сохранить исходные переводы?",
                                                    "Файлы в формате игры созданы!\n\n"
                                                    "Хотите также сохранить переводы\n"
                                                    "в формате 'оригинал = перевод' для архива?")
                            if choice:
                                path = filedialog.asksaveasfilename(
                                    title="Сохранить переводы",
                                    defaultextension=".txt",
                                    filetypes=[("Text files", "*.txt")],
                                    initialfile=f"translations_{timestamp}.txt"
                                )
                                if path:
                                    shutil.copy2(temp_trans_file, path)
                                    self.log_message("translate", f"💾 Копия сохранена в: {path}")
                            
                            # Удаляем временный файл
                            try:
                                os.remove(temp_trans_file)
                            except Exception as e:
                                logger.warning(f"⚠️ Не удалось удалить временный файл: {e}")
                            
                            self.show_info("Успех!", 
                                        f"✅ Переводы сконвертированы и сохранены!\n\n"
                                        f"📁 Результат в: {os.path.basename(self.convert_output_path)}\n"
                                        f"📊 Переведено фраз: {len(self.current_translations)}")
                        else:
                            # Если конвертация не удалась, сохраняем обычным способом
                            try:
                                os.remove(temp_trans_file)
                            except Exception as e:
                                logger.warning(f"⚠️ Не удалось удалить временный файл: {e}")
                    return
                
                # Обычное сохранение (без автоконвертации)
            choice = self.ask_yes_no("Способ сохранения", 
                                        "Как сохранить переводы?\n\n"
                                        "ДА - В один файл (формат: оригинал = перевод)\n"
                                        "НЕТ - Сразу в формат игры с сохранением структуры")
                
            if choice is None:
                    return
                
            if choice:
                    # Сохранение в один файл
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    path = filedialog.asksaveasfilename(
                        title="Сохранить переводы",
                        defaultextension=".txt",
                        filetypes=[("Text files", "*.txt")],
                        initialfile=f"translations_{timestamp}.txt"
                    )
                    if path:
                        if save_translations_to_file(path, self.current_translations):
                            self.show_info("Успех", 
                                        f"✅ Сохранено {len(self.current_translations)} переводов!\n\n"
                                        f"📄 Файл: {os.path.basename(path)}")
                            self.log_message("translate", f"💾 Сохранено в: {path}")
            else:
                    # Сохранение в формат игры
                    if not self.translate_source or self.translate_source_type not in ["archive", "folder"]:
                        self.show_error("Ошибка", 
                                    "Для сохранения в формат игры нужно:\n"
                                    "• Перевести из архива или папки\n"
                                    "• Или настроить автоконвертацию")
                        return
                    
                    output_folder = filedialog.askdirectory(title="Выберите папку для сохранения")
                    if not output_folder:
                        return
                    
                    self.log_message("translate", "\n🔄 Конвертация в формат игры...")
                    
                    try:
                        # Используем исходную папку как источник структуры
                        if self.translate_source_type == "archive":
                            temp_dir = tempfile.mkdtemp(prefix='convert_source_')
                            if extract_archive(self.translate_source, temp_dir):
                                source_folder = temp_dir
                            else:
                                self.show_error("Ошибка", "Не удалось распаковать архив для конвертации")
                                return
                        else:
                            source_folder = self.translate_source
                        
                        # Применяем переводы к оригинальным файлам
                        processed_files = 0
                        total_replaced = 0
                        
                        for root, dirs, files in os.walk(source_folder):
                            for file in files:
                                if file.endswith(('.txt', '.json', '.yml', '.xml')):
                                    orig_path = os.path.join(root, file)
                                    rel_path = os.path.relpath(orig_path, source_folder)
                                    out_path = os.path.join(output_folder, rel_path)
                                    
                                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                                    
                                    success, count = apply_translations_to_file(
                                        orig_path,
                                        self.current_translations,
                                        out_path
                                    )
                                    
                                    if success:
                                        processed_files += 1
                                        total_replaced += count
                                        if count > 0:
                                            self.log_message("translate", f"✅ {rel_path}: {count} фраз")
                        
                        # Очистка временной папки
                        if self.translate_source_type == "archive":
                            try:
                                shutil.rmtree(temp_dir)
                            except Exception as e:
                                logger.warning(f"⚠️ Ошибка очистки временной папки: {e}")
                        
                        self.log_message("translate", f"\n📊 Итого:")
                        self.log_message("translate", f"   Обработано файлов: {processed_files}")
                        self.log_message("translate", f"   Применено переводов: {total_replaced}")
                        self.log_message("translate", f"   Сохранено в: {output_folder}")
                        
                        self.show_info("Успех!", 
                                    f"✅ Переводы применены к файлам игры!\n\n"
                                    f"📁 Папка: {os.path.basename(output_folder)}\n"
                                    f"📄 Файлов: {processed_files}\n"
                                    f"📊 Фраз: {total_replaced}")
                    
                    except Exception as e:
                        self.show_error("Ошибка", f"Не удалось сконвертировать:\n{e}")
    
    # ===================================================================
    # МЕТОДЫ ДЛЯ ВКЛАДКИ КОНВЕРТАЦИИ
    # ===================================================================
    
    def load_convert_translations_file(self):
        """Загрузка переводов для конвертации из файла"""
        path = filedialog.askopenfilename(
            title="Выберите файл с переводами",
            filetypes=[("Text files", "*.txt")]
        )
        if path:
            self.convert_translations_dict = load_translations_from_file(path)
            self.convert_trans_label.config(
                text=f"Загружено: {len(self.convert_translations_dict)} фраз",
                fg="#27ae60"
            )
    
    def load_convert_translations_folder(self):
        """Загрузка переводов для конвертации из папки"""
        path = filedialog.askdirectory(title="Выберите папку с переводами")
        if path:
            self.convert_translations_dict = load_translations_from_folder(path)
            self.convert_trans_label.config(
                text=f"Загружено: {len(self.convert_translations_dict)} фраз",
                fg="#27ae60"
            )
            self.log_message("convert", f"✅ Загружено {len(self.convert_translations_dict)} переводов")
    
    def select_convert_original_folder(self):
        """Выбор папки с оригинальными файлами"""
        path = filedialog.askdirectory(title="Выберите папку с оригинальными файлами игры")
        if path:
            self.convert_original_path = path
            self.convert_original_type = "folder"
            self.convert_struct_label.config(
                text=f"Папка: {os.path.basename(path)}",
                fg="#27ae60"
            )
            self.log_message("convert", f"✅ Выбрана папка: {os.path.basename(path)}")
    
    def select_convert_original_archive(self):
        """Выбор архива с оригинальными файлами"""
        path = filedialog.askopenfilename(
            title="Выберите архив с оригинальными файлами",
            filetypes=[("Архивы", "*.zip *.tar *.tar.gz")]
        )
        if path:
            self.convert_original_path = path
            self.convert_original_type = "archive"
            self.convert_struct_label.config(
                text=f"Архив: {os.path.basename(path)}",
                fg="#27ae60"
            )
            self.log_message("convert", f"✅ Выбран архив: {os.path.basename(path)}")
    
    def select_convert_output(self):
        """Выбор выходной папки"""
        path = filedialog.askdirectory(title="Выберите папку для сохранения результата")
        if path:
            self.convert_output_path = path
            self.convert_output_label.config(
                text=f"Папка: {os.path.basename(path)}",
                fg="#27ae60"
            )
            self.log_message("convert", f"✅ Результат будет сохранён в: {os.path.basename(path)}")
    
    def convert_translations(self):
        """Конвертация переводов в формат игры"""
        if not self.convert_translations_dict:
            self.show_error("Ошибка", "Не загружены переводы для конвертации!")
            return
        
        success = self.perform_conversion(self.convert_translations_dict)
        
        if success:
            self.show_info("Успех", "Конвертация завершена!")
    
    def perform_conversion(self, translations):
        """ИСПРАВЛЕННАЯ версия конвертации с точным сохранением формата"""
        if not self.convert_original_path:
            self.show_error("Ошибка", "Не выбрана папка с оригинальными файлами!")
            return False
        
        if not self.convert_output_path:
            self.show_error("Ошибка", "Не выбрана папка для результата!")
            return False
        
        self.log_message("convert", "\n" + "="*50)
        self.log_message("convert", "🔄 КОНВЕРТАЦИЯ ПЕРЕВОДОВ (v3.3)")
        self.log_message("convert", "="*50)
        
        try:
            original_folder = None
            temp_dir = None
            
            # Подготовка оригинальных файлов
            if self.convert_original_type == "archive":
                self.log_message("convert", "📦 Распаковка архива...")
                temp_dir = tempfile.mkdtemp(prefix='convert_')
                if extract_archive(self.convert_original_path, temp_dir):
                    original_folder = temp_dir
                    self.log_message("convert", "✅ Архив распакован")
                else:
                    self.show_error("Ошибка", "Не удалось распаковать архив")
                    return False
            else:
                original_folder = self.convert_original_path
            
            self.log_message("convert", f"🔄 Обработка файлов из: {os.path.basename(original_folder)}")
            self.log_message("convert", f"📊 Доступно переводов: {len(translations)}\n")
            
            processed_files = 0
            total_replaced = 0
            errors = []
            
            # Подсчитываем файлы для прогресс-бара
            all_files = []
            for root, dirs, files in os.walk(original_folder):
                for file in files:
                    if file.endswith(('.txt', '.json', '.yml', '.xml')):
                        all_files.append((root, file))
            
            self.convert_progress['maximum'] = len(all_files)
            
            # Обрабатываем все файлы
            for idx, (root, file) in enumerate(all_files, 1):
                self.convert_progress['value'] = idx
                
                orig_path = os.path.join(root, file)
                rel_path = os.path.relpath(orig_path, original_folder)
                out_path = os.path.join(self.convert_output_path, rel_path)
                
                # Применяем переводы
                success, count = apply_translations_to_file(
                    orig_path,
                    translations,
                    out_path
                )
                
                if success:
                    processed_files += 1
                    total_replaced += count
                    
                    if count > 0:
                        self.log_message("convert", f"✅ {rel_path}: {count} фраз")
                    else:
                        self.log_message("convert", f"⚪ {rel_path}: без изменений")
                else:
                    errors.append(rel_path)
                    self.log_message("convert", f"❌ {rel_path}: ошибка обработки")
                
                self.root.update()
            
            # Очистка
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    pass
            
            self.log_message("convert", f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
            self.log_message("convert", f"   Обработано файлов: {processed_files}")
            self.log_message("convert", f"   Применено переводов: {total_replaced}")
            self.log_message("convert", f"   Ошибок: {len(errors)}")
            self.log_message("convert", f"   Сохранено в: {self.convert_output_path}")
            
            if errors:
                self.log_message("convert", f"\n⚠️ Файлы с ошибками ({len(errors)}):")
                for err_file in errors[:10]:
                    self.log_message("convert", f"   • {err_file}")
                if len(errors) > 10:
                    self.log_message("convert", f"   ... и ещё {len(errors) - 10}")
            
            return True
        
        except Exception as e:
            import traceback
            self.log_message("convert", f"❌ Критическая ошибка: {e}")
            self.log_message("convert", traceback.format_exc())
            self.show_error("Ошибка", f"Произошла ошибка при конвертации:\n{e}")
            return False
    
    # ===================================================================
    # МЕТОДЫ ДЛЯ ВКЛАДКИ ПРИМЕНЕНИЯ
    # ===================================================================
    
    def load_apply_translations_file(self):
        """Загрузка переводов для применения из файла"""
        path = filedialog.askopenfilename(
            title="Выберите файл с переводами",
            filetypes=[("Text files", "*.txt")]
        )
        if path:
            self.apply_translations_dict = load_translations_from_file(path)
            self.apply_trans_label.config(
                text=f"Загружено: {len(self.apply_translations_dict)} фраз",
                fg="#27ae60"
            )
            self.log_message("apply", f"✅ Загружено {len(self.apply_translations_dict)} переводов")
    
    def load_apply_translations_folder(self):
        """Загрузка переводов для применения из папки"""
        path = filedialog.askdirectory(title="Выберите папку с переводами")
        if path:
            self.apply_translations_dict = load_translations_from_folder(path)
            self.apply_trans_label.config(
                text=f"Загружено: {len(self.apply_translations_dict)} фраз",
                fg="#27ae60"
            )
            self.log_message("apply", f"✅ Загружено {len(self.apply_translations_dict)} переводов")
    
    def select_original_file(self):
        """Выбор оригинального файла"""
        path = filedialog.askopenfilename(
            title="Выберите оригинальный файл",
            filetypes=[("Все файлы", "*.*")]
        )
        if path:
            self.apply_original_path = path
            self.apply_original_type = "file"
            self.apply_orig_label.config(
                text=f"Файл: {os.path.basename(path)}",
                fg="#27ae60"
            )
            self.log_message("apply", f"✅ Выбран файл: {os.path.basename(path)}")
    
    def select_original_folder(self):
        """Выбор папки с оригинальными файлами"""
        path = filedialog.askdirectory(title="Выберите папку с оригинальными файлами")
        if path:
            self.apply_original_path = path
            self.apply_original_type = "folder"
            self.apply_orig_label.config(
                text=f"Папка: {os.path.basename(path)}",
                fg="#27ae60"
            )
            self.log_message("apply", f"✅ Выбрана папка: {os.path.basename(path)}")
    
    def select_original_archive(self):
        """Выбор архива с оригинальными файлами"""
        path = filedialog.askopenfilename(
            title="Выберите архив",
            filetypes=[("Архивы", "*.zip *.tar *.tar.gz")]
        )
        if path:
            self.apply_original_path = path
            self.apply_original_type = "archive"
            self.apply_orig_label.config(
                text=f"Архив: {os.path.basename(path)}",
                fg="#27ae60"
            )
            self.log_message("apply", f"✅ Выбран архив: {os.path.basename(path)}")
    
    def select_output_file(self):
        """Выбор файла для сохранения результата"""
        path = filedialog.asksaveasfilename(
            title="Сохранить как",
            defaultextension=".txt",
            filetypes=[("Все файлы", "*.*")]
        )
        if path:
            self.apply_output_path = path
            self.apply_output_label.config(
                text=f"Файл: {os.path.basename(path)}",
                fg="#27ae60"
            )
            self.log_message("apply", f"✅ Результат будет сохранён в: {os.path.basename(path)}")
    
    def select_output_folder(self):
        """Выбор папки для сохранения результата"""
        path = filedialog.askdirectory(title="Выберите папку для результата")
        if path:
            self.apply_output_path = path
            self.apply_output_label.config(
                text=f"Папка: {os.path.basename(path)}",
                fg="#27ae60"
            )
            self.log_message("apply", f"✅ Результат будет сохранён в: {os.path.basename(path)}")
    
    def apply_translations(self):
        """Применение переводов"""
        if not self.apply_translations_dict:
            self.show_error("Ошибка", "Не загружены переводы!")
            return
        
        if not self.apply_original_path:
            self.show_error("Ошибка", "Не выбраны оригинальные файлы!")
            return
        
        if not self.apply_output_path:
            self.show_error("Ошибка", "Не выбрано место для сохранения!")
            return
        
        self.log_message("apply", "\n" + "="*50)
        self.log_message("apply", "🚀 ПРИМЕНЕНИЕ ПЕРЕВОДОВ")
        self.log_message("apply", "="*50)
        
        try:
            if self.apply_original_type == "file":
                # Один файл
                success, count = apply_translations_to_file(
                    self.apply_original_path,
                    self.apply_translations_dict,
                    self.apply_output_path
                )
                if success:
                    self.log_message("apply", f"✅ Обработан файл")
                    self.log_message("apply", f"📊 Заменено фраз: {count}")
                    self.show_info("Успех", f"Заменено {count} фраз!")
                else:
                    self.show_error("Ошибка", "Не удалось применить переводы")
            
            elif self.apply_original_type == "folder":
                # Папка
                processed = 0
                total_replaced = 0
                
                for root, dirs, files in os.walk(self.apply_original_path):
                    for file in files:
                        if file.endswith(('.txt', '.json', '.yml', '.xml')):
                            orig_path = os.path.join(root, file)
                            rel_path = os.path.relpath(orig_path, self.apply_original_path)
                            out_path = os.path.join(self.apply_output_path, rel_path)
                            
                            os.makedirs(os.path.dirname(out_path), exist_ok=True)
                            
                            success, count = apply_translations_to_file(
                                orig_path,
                                self.apply_translations_dict,
                                out_path
                            )
                            
                            if success:
                                processed += 1
                                total_replaced += count
                                self.log_message("apply", f"✅ {rel_path}: {count} фраз")
                
                self.log_message("apply", f"\n📊 Итого:")
                self.log_message("apply", f"   Обработано файлов: {processed}")
                self.log_message("apply", f"   Заменено фраз: {total_replaced}")
                self.show_info("Успех", f"Обработано {processed} файлов\nЗаменено {total_replaced} фраз")
            
            elif self.apply_original_type == "archive":
                # Архив
                temp_dir = tempfile.mkdtemp(prefix='apply_')
                if extract_archive(self.apply_original_path, temp_dir):
                    self.log_message("apply", "📦 Архив распакован")
                    
                    processed = 0
                    total_replaced = 0
                    
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if file.endswith(('.txt', '.json', '.yml', '.xml')):
                                orig_path = os.path.join(root, file)
                                rel_path = os.path.relpath(orig_path, temp_dir)
                                out_path = os.path.join(self.apply_output_path, rel_path)
                                
                                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                                
                                success, count = apply_translations_to_file(
                                    orig_path,
                                    self.apply_translations_dict,
                                    out_path
                                )
                                
                                if success:
                                    processed += 1
                                    total_replaced += count
                                    self.log_message("apply", f"✅ {rel_path}: {count} фраз")
                    
                    shutil.rmtree(temp_dir)
                    
                    self.log_message("apply", f"\n📊 Итого:")
                    self.log_message("apply", f"   Обработано файлов: {processed}")
                    self.log_message("apply", f"   Заменено фраз: {total_replaced}")
                    self.show_info("Успех", f"Обработано {processed} файлов\nЗаменено {total_replaced} фраз")
                else:
                    self.show_error("Ошибка", "Не удалось распаковать архив")
        
        except Exception as e:
            self.show_error("Ошибка", f"Произошла ошибка:\n{e}")
    
    # ===================================================================
    # МЕТОДЫ ДЛЯ ВКЛАДКИ ПРОВЕРКИ
    # ===================================================================
    
    def load_verify_file(self):
        """Загрузка файла для проверки"""
        path = filedialog.askopenfilename(
            title="Выберите файл с переводами",
            filetypes=[("Text files", "*.txt")]
        )
        if path:
            self.verify_translations_dict = load_translations_from_file(path)
            self.verify_source_label.config(
                text=f"Файл: {os.path.basename(path)} ({len(self.verify_translations_dict)} фраз)",
                fg="#27ae60"
            )
            self.log_message("verify", f"✅ Загружено {len(self.verify_translations_dict)} переводов")
    
    def load_verify_folder(self):
        """Загрузка папки для проверки"""
        path = filedialog.askdirectory(title="Выберите папку с переводами")
        if path:
            self.verify_translations_dict = load_translations_from_folder(path)
            self.verify_source_label.config(
                text=f"Папка: {os.path.basename(path)} ({len(self.verify_translations_dict)} фраз)",
                fg="#27ae60"
            )
            self.log_message("verify", f"✅ Загружено {len(self.verify_translations_dict)} переводов")
    
    def verify_translations(self):
        """Проверка качества переводов"""
        if not self.verify_translations_dict:
            self.show_error("Ошибка", "Не загружены переводы для проверки!")
            return
        
        self.log_message("verify", "\n" + "="*50)
        self.log_message("verify", "🔍 ПРОВЕРКА КАЧЕСТВА ПЕРЕВОДОВ")
        self.log_message("verify", "="*50)
        
        self.verify_errors = []
        total = len(self.verify_translations_dict)
        
        self.log_message("verify", f"📊 Проверяю {total} переводов...\n")
        
        # Проверка на ошибки
        for original, translated in self.verify_translations_dict.items():
            errors = []
            
            if not translated or translated.strip() == "":
                errors.append("Пустой перевод")
            
            if original.strip().lower() == translated.strip().lower():
                errors.append("Текст не переведён")
            
            if not re.search(r'[А-Яа-яЁё]', translated):
                errors.append("Нет кириллицы")
            
            if len(translated) < len(original) * 0.3 and len(original) > 20:
                errors.append("Подозрительно короткий")
            
            if errors:
                self.verify_errors.append({
                    'original': original,
                    'translated': translated,
                    'errors': errors
                })
                self.log_message("verify", f"❌ {original[:50]}...")
                self.log_message("verify", f"   Проблемы: {', '.join(errors)}\n")
        
        # Статистика
        stats = f"""
Всего переводов: {total}
✅ Корректных: {total - len(self.verify_errors)}
❌ С проблемами: {len(self.verify_errors)}

Типы проблем:
"""
        
        error_types = {}
        for err in self.verify_errors:
            for e_type in err['errors']:
                error_types[e_type] = error_types.get(e_type, 0) + 1
        
        for e_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            stats += f"  • {e_type}: {count}\n"
        
        self.verify_stats_text.delete(1.0, tk.END)
        self.verify_stats_text.insert(1.0, stats)
        
        if not self.verify_errors:
            self.show_info("Отлично!", "Все переводы в порядке! ✅")
        else:
            self.show_info("Проверка завершена", 
                          f"Найдено {len(self.verify_errors)} проблемных переводов из {total}")
    
    def fix_translations(self):
        """Исправление проблемных переводов"""
        if not self.verify_errors:
            self.show_error("Ошибка", "Сначала проведите проверку!")
            return
        
        translator = self.translator_choice.get()
        if translator == "deepl" and not self.deepl_api_key:
            self.show_error("Ошибка", "DeepL API ключ не настроен!")
            return
        elif translator == "microsoft" and not self.microsoft_api_key:
            self.show_error("Ошибка", "Microsoft API ключ не настроен!")
            return
        
        self.log_message("verify", "\n🔧 ИСПРАВЛЕНИЕ ПРОБЛЕМНЫХ ПЕРЕВОДОВ\n")
        
        fixed = 0
        failed = 0
        
        for i, error_data in enumerate(self.verify_errors, 1):
            original = error_data['original']
            self.log_message("verify", f"[{i}/{len(self.verify_errors)}] Переводю: {original[:50]}...")
            
            translator = self.translator_choice.get()
            result = translate_with_placeholder_protection(
            original, 
            self.deepl_api_key if translator == "deepl" else self.microsoft_api_key,
            translator=translator,
            region=self.microsoft_region,
            retry=5
        )
            
            if isinstance(result, tuple):
                self.log_message("verify", f"   ❌ Не удалось: {result[1]}")
                failed += 1
            else:
                self.verify_translations_dict[original] = result
                self.log_message("verify", f"   ✅ Исправлено: {result[:50]}...")
                fixed += 1
            
            time.sleep(0.5)
            self.root.update()
        
        self.log_message("verify", f"\n📊 Результаты исправления:")
        self.log_message("verify", f"   ✅ Исправлено: {fixed}")
        self.log_message("verify", f"   ❌ Не удалось: {failed}")
        
        self.show_info("Готово", f"Исправлено {fixed} из {len(self.verify_errors)} проблемных переводов")
        
        # Повторная проверка
        self.verify_errors = []
        self.verify_translations()
    
    def save_verified(self):
        """Сохранение проверенных переводов"""
        if not self.verify_translations_dict:
            self.show_error("Ошибка", "Нет переводов для сохранения!")
            return
        
        path = filedialog.asksaveasfilename(
            title="Сохранить исправленные переводы",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")]
        )
        if path:
            if save_translations_to_file(path, self.verify_translations_dict):
                self.show_info("Успех", "Переводы сохранены!")
                self.log_message("verify", f"💾 Сохранено в: {path}")
    


# ===================================================================
# ДИАЛОГОВЫЕ ОКНА
# ===================================================================

class ArchiveBrowserDialog:
    def __init__(self, parent, app, archive_path):
        self.app = app
        self.archive_path = archive_path
        self.selected_items = []
        self.temp_dir = None
        
        # ИСПРАВЛЕНИЕ: Создаём диалог БЕЗ parent, чтобы избежать проблем
        self.dialog = tk.Toplevel()
        self.dialog.title(f"📦 Содержимое: {os.path.basename(archive_path)}")
        self.dialog.geometry("700x500")
        self.dialog.resizable(True, True)
        
        # Делаем окно модальным
        self.dialog.grab_set()
        self.dialog.focus_set()
        
        # Центрируем окно
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width - 700) // 2
        y = (screen_height - 500) // 2
        self.dialog.geometry(f"700x500+{x}+{y}")
        
        # Заголовок
        header = tk.Frame(self.dialog, bg="#3498db", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="📦 Выберите файлы/папки из архива",
                font=("Segoe UI", 14, "bold"), bg="#3498db", fg="white").pack(pady=15)
        
        # Инструкция
        info_frame = tk.Frame(self.dialog, bg="#e8f4f8")
        info_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(info_frame, 
                text="Выберите файлы или папки для перевода. Можно выбрать несколько элементов (Ctrl+клик).",
                font=("Segoe UI", 9), bg="#e8f4f8", fg="#2c3e50").pack(pady=8, padx=10)
        
        # Список файлов
        list_frame = tk.Frame(self.dialog, bg="white")
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(list_frame, yscrollcommand=scrollbar.set, selectmode="extended")
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.tree.yview)
        
        # Настройка колонок
        self.tree['columns'] = ('type', 'size')
        self.tree.column('#0', width=400, minwidth=200)
        self.tree.column('type', width=100, minwidth=80)
        self.tree.column('size', width=100, minwidth=80)
        
        self.tree.heading('#0', text='Имя', anchor='w')
        self.tree.heading('type', text='Тип', anchor='w')
        self.tree.heading('size', text='Размер', anchor='w')
        
        # Кнопки выбора
        select_frame = tk.Frame(self.dialog, bg="white")
        select_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(select_frame, text="✅ Выбрать всё", 
                  command=self.select_all, width=15).pack(side="left", padx=5)
        ttk.Button(select_frame, text="❌ Снять всё",
                  command=self.deselect_all, width=15).pack(side="left", padx=5)
        
        # Статус
        self.status_label = tk.Label(self.dialog, text="Загрузка...", 
                                     bg="#ecf0f1", fg="#2c3e50", 
                                     font=("Segoe UI", 9), anchor="w", padx=10)
        self.status_label.pack(fill="x")
        
        # Кнопки действий
        btn_frame = tk.Frame(self.dialog, bg="white")
        btn_frame.pack(fill="x", padx=10, pady=15)
        
        ttk.Button(btn_frame, text="✅ Выбрать выделенные",
                  command=self.confirm_selection, width=25).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="❌ Отмена",
                  command=self.cancel, width=25).pack(side="left", padx=5)
        
        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)
        
        # Загружаем содержимое ПОСЛЕ создания всего интерфейса
        self.dialog.after(100, self.load_archive_content)
    
    def load_archive_content(self):
        """Загружает и отображает содержимое архива"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix='archive_browse_')
            
            if not extract_archive(self.archive_path, self.temp_dir):
                ErrorDialog(self.dialog, "Ошибка", "Не удалось распаковать архив")
                self.cancel()
                return
            
            items = []
            for root, dirs, files in os.walk(self.temp_dir):
                for dir_name in dirs:
                    full_path = os.path.join(root, dir_name)
                    rel_path = os.path.relpath(full_path, self.temp_dir)
                    file_count = sum([len(f) for _, _, f in os.walk(full_path)])
                    
                    items.append({
                        'name': rel_path,
                        'type': '📁 Папка',
                        'size': f'{file_count} файлов',
                        'full_path': full_path,
                        'is_dir': True
                    })
                
                for file_name in files:
                    if file_name.endswith(('.txt', '.json', '.yml', '.xml')):
                        full_path = os.path.join(root, file_name)
                        rel_path = os.path.relpath(full_path, self.temp_dir)
                        
                        try:
                            size = os.path.getsize(full_path)
                            size_str = self.format_size(size)
                        except Exception as e:
                            size_str = "?"
                        
                        items.append({
                            'name': rel_path,
                            'type': '📄 Файл',
                            'size': size_str,
                            'full_path': full_path,
                            'is_dir': False
                        })
            
            items.sort(key=lambda x: (not x['is_dir'], x['name']))
            
            for item in items:
                self.tree.insert('', 'end', text=item['name'], 
                               values=(item['type'], item['size']),
                               tags=(item['full_path'],))
            
            self.status_label.config(
                text=f"Найдено: {len([i for i in items if not i['is_dir']])} файлов, "
                     f"{len([i for i in items if i['is_dir']])} папок",
                bg="#27ae60", fg="white"
            )
        
        except Exception as e:
            ErrorDialog(self.dialog, "Ошибка", f"Не удалось загрузить архив:\n{e}")
            self.cancel()
    
    def format_size(self, size):
        """Форматирует размер файла"""
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"
    
    def select_all(self):
        """Выбрать все элементы"""
        for item in self.tree.get_children():
            self.tree.selection_add(item)
    
    def deselect_all(self):
        """Снять выбор со всех элементов"""
        self.tree.selection_remove(self.tree.get_children())
    
    def confirm_selection(self):
        """Подтверждение выбора"""
        selected = self.tree.selection()
        
        if not selected:
            ErrorDialog(self.dialog, "Ошибка", "Не выбрано ни одного элемента!")
            return
        
        selected_paths = []
        for item in selected:
            tags = self.tree.item(item, 'tags')
            if tags:
                selected_paths.append(tags[0])
        
        if not selected_paths:
            ErrorDialog(self.dialog, "Ошибка", "Не удалось получить выбранные элементы!")
            return
        
        result_dir = tempfile.mkdtemp(prefix='selected_')
        
        for path in selected_paths:
            if os.path.isdir(path):
                rel_path = os.path.relpath(path, self.temp_dir)
                dest = os.path.join(result_dir, rel_path)
                shutil.copytree(path, dest)
            else:
                rel_path = os.path.relpath(path, self.temp_dir)
                dest = os.path.join(result_dir, rel_path)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(path, dest)
        
        self.app.translate_source = result_dir
        self.app.translate_source_type = "folder"
        self.app.translate_source_label.config(
            text=f"Из архива: {len(selected)} элементов",
            fg="#27ae60"
        )
        self.app.log_message("translate", 
                            f"✅ Выбрано {len(selected)} элементов из архива {os.path.basename(self.archive_path)}")
        
        self.cleanup()
        self.dialog.destroy()
    
    def cancel(self):
        """Отмена"""
        self.cleanup()
        self.dialog.destroy()
    
    def cleanup(self):
        """Очистка временных файлов"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                pass


class ErrorDialog:
    def __init__(self, parent, title, message):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x200")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 200) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        # Иконка и текст
        content = tk.Frame(self.dialog, bg="white")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        tk.Label(content, text="❌", font=("Segoe UI", 40), bg="white", fg="#e74c3c").pack(pady=(0, 10))
        tk.Label(content, text=message, font=("Segoe UI", 10), bg="white", 
                wraplength=350, justify="center").pack(pady=10)
        
        ttk.Button(content, text="OK", command=self.dialog.destroy, width=15).pack(pady=10)

class InfoDialog:
    def __init__(self, parent, title, message):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x200")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 200) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        content = tk.Frame(self.dialog, bg="white")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        tk.Label(content, text="✅", font=("Segoe UI", 40), bg="white", fg="#27ae60").pack(pady=(0, 10))
        tk.Label(content, text=message, font=("Segoe UI", 10), bg="white",
                wraplength=350, justify="center").pack(pady=10)
        
        ttk.Button(content, text="OK", command=self.dialog.destroy, width=15).pack(pady=10)

class YesNoDialog:
    def __init__(self, parent, title, message):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("600x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 220) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        content = tk.Frame(self.dialog, bg="white")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        tk.Label(content, text="❓", font=("Segoe UI", 40), bg="white", fg="#3498db").pack(pady=(0, 10))
        tk.Label(content, text=message, font=("Segoe UI", 10), bg="white",
                wraplength=400, justify="center").pack(pady=10)
        
        btn_frame = tk.Frame(content, bg="white")
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Да", command=self.yes, width=15).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Нет", command=self.no, width=15).pack(side="left", padx=5)
        
        self.dialog.wait_window()
    
    def yes(self):
        self.result = True
        self.dialog.destroy()
    
    def no(self):
        self.result = False
        self.dialog.destroy()

class SettingsDialog:
    def __init__(self, parent, app):
        self.app = app
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("⚙️ Настройки")
        self.dialog.geometry("900x750")  # Увеличили высоту
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 900) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 750) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        # Заголовок
        header = tk.Frame(self.dialog, bg="#3498db", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="⚙️ Настройки переводчиков", 
                font=("Segoe UI", 16, "bold"), bg="#3498db", fg="white").pack(pady=15)
        
        # Контент с прокруткой
        canvas = tk.Canvas(self.dialog, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg="white")
        
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=30, pady=20)
        scrollbar.pack(side="right", fill="y")
        
        # ========== DEEPL ==========
        deepl_frame = tk.LabelFrame(content, text="🌐 DeepL Translator", 
                                bg="white", font=("Segoe UI", 11, "bold"),
                                fg="#2c3e50", padx=15, pady=10)
        deepl_frame.pack(fill="x", pady=10)
        
        tk.Label(deepl_frame, text="API ключ:", font=("Segoe UI", 10),
                bg="white", fg="#2c3e50").pack(anchor="w", pady=(5, 2))
        
        self.deepl_entry = tk.Entry(deepl_frame, font=("Segoe UI", 10), width=60)
        self.deepl_entry.pack(fill="x", pady=5)
        self.deepl_entry.insert(0, self.app.deepl_api_key)
        
        deepl_info = tk.Frame(deepl_frame, bg="#e8f4f8", relief="solid", borderwidth=1)
        deepl_info.pack(fill="x", pady=5)
        
        tk.Label(deepl_info, text="""
    📌 Как получить DeepL API ключ:
    1. Перейдите на https://www.deepl.com/pro-api
    2. Нажмите "Sign up for free"
    3. Заполните форму и подтвердите email
    4. В личном кабинете скопируйте API ключ

    ✅ Бесплатно: 500,000 символов/месяц
        """, font=("Segoe UI", 9), bg="#e8f4f8", fg="#2c3e50", 
                justify="left").pack(padx=10, pady=8, anchor="w")
        
        # ========== MICROSOFT ==========
        microsoft_frame = tk.LabelFrame(content, text="🔷 Microsoft Translator", 
                                    bg="white", font=("Segoe UI", 11, "bold"),
                                    fg="#2c3e50", padx=15, pady=10)
        microsoft_frame.pack(fill="x", pady=10)
        
        tk.Label(microsoft_frame, text="API ключ:", font=("Segoe UI", 10),
                bg="white", fg="#2c3e50").pack(anchor="w", pady=(5, 2))
        
        self.microsoft_entry = tk.Entry(microsoft_frame, font=("Segoe UI", 10), width=60)
        self.microsoft_entry.pack(fill="x", pady=5)
        self.microsoft_entry.insert(0, self.app.microsoft_api_key)
        
        tk.Label(microsoft_frame, text="Регион:", font=("Segoe UI", 10),
                bg="white", fg="#2c3e50").pack(anchor="w", pady=(10, 2))
        
        region_frame = tk.Frame(microsoft_frame, bg="white")
        region_frame.pack(fill="x", pady=5)
        
        self.microsoft_region_entry = tk.Entry(region_frame, font=("Segoe UI", 10), width=20)
        self.microsoft_region_entry.pack(side="left", padx=(0, 10))
        self.microsoft_region_entry.insert(0, self.app.microsoft_region)
        
        tk.Label(region_frame, text="(например: eastus, westeurope или global)", 
                font=("Segoe UI", 8, "italic"), bg="white", fg="#7f8c8d").pack(side="left")
        
        microsoft_info = tk.Frame(microsoft_frame, bg="#e8f4f8", relief="solid", borderwidth=1)
        microsoft_info.pack(fill="x", pady=5)
        
        tk.Label(microsoft_info, text="""
    📌 Как получить Microsoft Translator API ключ:
    1. Перейдите на https://portal.azure.com
    2. Создайте аккаунт (нужна карта, но списаний не будет)
    3. Нажмите "Create a resource" → найдите "Translator"
    4. Выберите план F0 (бесплатный)
    5. После создания перейдите в "Keys and Endpoint"
    6. Скопируйте KEY 1 и REGION

    ✅ Бесплатно: 2,000,000 символов/месяц
    ⚠️ Регион обязателен! Смотрите в Azure Portal
        """, font=("Segoe UI", 9), bg="#e8f4f8", fg="#2c3e50", 
                justify="left").pack(padx=10, pady=8, anchor="w")
        
        # ========== ВЫБОР ПО УМОЛЧАНИЮ ==========
        default_frame = tk.LabelFrame(content, text="⚙️ Переводчик по умолчанию", 
                                    bg="white", font=("Segoe UI", 11, "bold"),
                                    fg="#2c3e50", padx=15, pady=10)
        default_frame.pack(fill="x", pady=10)
        
        self.default_translator = tk.StringVar(value=self.app.current_translator)
        tk.Radiobutton(default_frame, text="DeepL", variable=self.default_translator, 
                    value="deepl", bg="white", font=("Segoe UI", 10)).pack(anchor="w", pady=3)
        tk.Radiobutton(default_frame, text="Microsoft", variable=self.default_translator, 
                    value="microsoft", bg="white", font=("Segoe UI", 10)).pack(anchor="w", pady=3)
        
        # Кнопки
        btn_frame = tk.Frame(self.dialog, bg="white")
        btn_frame.pack(fill="x", padx=30, pady=15)
        
        ttk.Button(btn_frame, text="💾 Сохранить", 
                command=self.save, width=20,
                style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Отмена",
                command=self.dialog.destroy, width=20).pack(side="left", padx=5)
        
        # Контекстные меню для обоих полей
        self.setup_context_menu(self.deepl_entry)
        self.setup_context_menu(self.microsoft_entry)
    
    def setup_context_menu(self, entry):
        """Создаёт контекстное меню для поля ввода"""
        context_menu = tk.Menu(entry, tearoff=0)
        context_menu.add_command(label="Вырезать (Ctrl+X)", 
                                command=lambda: self.cut_text(entry))
        context_menu.add_command(label="Копировать (Ctrl+C)", 
                                command=lambda: self.copy_text(entry))
        context_menu.add_command(label="Вставить (Ctrl+V)", 
                                command=lambda: self.paste_text(entry))
        context_menu.add_separator()
        context_menu.add_command(label="Выделить всё (Ctrl+A)", 
                                command=lambda: self.select_all(entry))
        
        entry.bind("<Button-3>", lambda e: self.show_context_menu(e, context_menu))
        entry.bind('<Control-v>', lambda e: self.paste_text(entry))
        entry.bind('<Control-V>', lambda e: self.paste_text(entry))
    
    def show_context_menu(self, event, menu):
        """Показывает контекстное меню"""
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def paste_text(self, entry):
        """Вставка из буфера обмена"""
        try:
            text = self.dialog.clipboard_get()
            if entry.selection_present():
                entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
            entry.insert(tk.INSERT, text)
        except Exception as e:
            pass
        return "break"

    def copy_text(self, entry):
        """Копирование в буфер обмена"""
        try:
            if entry.selection_present():
                text = entry.selection_get()
                self.dialog.clipboard_clear()
                self.dialog.clipboard_append(text)
        except Exception as e:
            pass
        return "break"

    def cut_text(self, entry):
        """Вырезание в буфер обмена"""
        try:
            if entry.selection_present():
                text = entry.selection_get()
                self.dialog.clipboard_clear()
                self.dialog.clipboard_append(text)
                entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except Exception as e:
            pass
        return "break"

    def select_all(self, entry):
        """Выделение всего текста"""
        entry.select_range(0, tk.END)
        entry.icursor(tk.END)
        return "break"
    
    def save(self):
        """Сохранение настроек"""
        deepl_key = self.deepl_entry.get().strip()
        microsoft_key = self.microsoft_entry.get().strip()
        microsoft_region = self.microsoft_region_entry.get().strip()
        default = self.default_translator.get()
        
        if not deepl_key and not microsoft_key:
            ErrorDialog(self.dialog, "Ошибка", 
                    "Нужно настроить хотя бы один переводчик!")
            return
        
        # Показываем индикатор проверки
        self.dialog.config(cursor="wait")
        self.dialog.update()
        
        # Проверяем ключи
        deepl_ok = False
        microsoft_ok = False
        
        if deepl_key:
            test = translate_with_deepl("Hello", deepl_key, retry=1)
            if isinstance(test, tuple):
                self.dialog.config(cursor="")
                ErrorDialog(self.dialog, "Ошибка DeepL", 
                        f"DeepL ключ не работает:\n{test[1]}")
                return
            deepl_ok = True
        
        if microsoft_key:
            test = translate_with_microsoft("Hello", microsoft_key, microsoft_region, retry=1)
            if isinstance(test, tuple):
                self.dialog.config(cursor="")
                ErrorDialog(self.dialog, "Ошибка Microsoft", 
                        f"Microsoft ключ не работает:\n{test[1]}\n\nПроверьте ключ и регион!")
                return
            microsoft_ok = True
        
        self.dialog.config(cursor="")
        
        # Сохраняем
        self.app.deepl_api_key = deepl_key
        self.app.microsoft_api_key = microsoft_key
        self.app.microsoft_region = microsoft_region
        self.app.current_translator = default
        
        self.app.config = {
            "deepl_api_key": deepl_key,
            "microsoft_api_key": microsoft_key,
            "microsoft_region": microsoft_region,
            "default_translator": default
        }
        
        if save_config(self.app.config):
            status_text = "✅ Настроены переводчики: "
            if deepl_ok:
                status_text += "DeepL "
            if microsoft_ok:
                status_text += "Microsoft"
            
            self.app.status_bar.config(text=status_text, bg="#27ae60", fg="white")
            
            InfoDialog(self.dialog, "Успех!", 
                    f"✅ Настройки сохранены!\n\n"
                    f"DeepL: {'✅' if deepl_ok else '❌'}\n"
                    f"Microsoft: {'✅' if microsoft_ok else '❌'}\n\n"
                    f"По умолчанию: {default.upper()}")
            
            self.dialog.destroy()
        else:
            ErrorDialog(self.dialog, "Ошибка", 
                    "Не удалось сохранить настройки в файл")
class HelpDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("❓ Помощь")
        self.dialog.geometry("700x600")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        # Заголовок
        header = tk.Frame(self.dialog, bg="#3498db", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="❓ Справка по использованию",
                font=("Segoe UI", 16, "bold"), bg="#3498db", fg="white").pack(pady=15)
        
        # Контент с прокруткой
        canvas = tk.Canvas(self.dialog, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg="white")
        
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Справочная информация
        help_text = """
🌐 ВКЛАДКА "ПЕРЕВОД"

Предназначена для перевода текстов из игровых файлов или обычных текстовых документов.

Шаги:
1. Выберите тип перевода:
   • Файлы игры - извлечение английского текста из игровых файлов
   • Обычный текст - построчный перевод текстовых файлов

2. Выберите источник:
   • Архив - для .zip, .tar файлов (с возможностью выбора конкретных файлов!)
   • Папка - для поиска файлов в папке

3. (Опционально) Загрузите существующие переводы, чтобы не переводить повторно

4. Нажмите "Начать перевод"

5. После завершения сохраните результат

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 ВКЛАДКА "ПРИМЕНИТЬ"

Применяет готовые переводы к оригинальным файлам игры.

Шаги:
1. Загрузите переводы (из файла или папки)

2. Выберите источник:
   • Архив - для .zip, .tar файлов (с возможностью выбора конкретных файлов!)
   • Папка - для поиска файлов в папке

3. Укажите, куда сохранить результат:
   • Файл - если обрабатывается один файл
   • Папка - если обрабатывается много файлов

4. Нажмите "Применить переводы"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 ВКЛАДКА "ПРОВЕРКА"

Проверяет качество готовых переводов и автоматически исправляет ошибки.

Шаги:
1. Загрузите переводы для проверки (файл или папка)

2. Нажмите "Проверить качество"
   Программа найдет:
   • Пустые переводы
   • Непереведённый текст
   • Переводы без кириллицы
   • Подозрительно короткие переводы

3. Нажмите "Исправить ошибки" для автоматического перевода проблемных фраз

4. Сохраните исправленные переводы

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔄 ВКЛАДКА "КОНВЕРТАЦИЯ"

Преобразует переводы из формата "оригинал = перевод" в формат игры.

Шаги:
1. Загрузите переводы (файл или папка)

2. Выберите оригинальную структуру:
   • Папка с оригинальными файлами
   • Архив с оригинальными файлами

3. Выберите папку для сохранения результата

4. (Опционально) Включите автоматическую конвертацию при переводе

5. Нажмите "Конвертировать и сохранить"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚙️ НАСТРОЙКИ

Здесь вы настраиваете DeepL API ключ, необходимый для работы переводчика.

Как получить бесплатный API ключ:
1. Зарегистрируйтесь на https://www.deepl.com/pro-api
2. Выберите бесплатный план (500,000 символов/месяц)
3. Скопируйте API ключ из личного кабинета
4. Вставьте в настройках программы

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 СОВЕТЫ

• Всегда сохраняйте промежуточные результаты
• Используйте режим проверки перед финальным применением
• Для больших проектов разбивайте работу на этапы
• Следите за лимитом символов в DeepL (500,000/месяц для free)
• Храните резервные копии оригинальных файлов

📦 Браузер архивов - теперь вы можете:
   • Просматривать содержимое архива перед обработкой
   • Выбирать конкретные файлы и папки для перевода
   • Использовать Ctrl+клик для множественного выбора

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ

Файлы: .txt, .json, .yml, .xml
Архивы: .zip, .tar, .tar.gz, .tgz

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🆘 ПРОБЛЕМЫ?

• Ошибка API ключа - проверьте правильность ключа в настройках
• Превышен лимит - подождите до следующего месяца или купите план
• Не находит текст - убедитесь, что файлы содержат английский текст
• Не применяются переводы - проверьте формат файла переводов

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Автор: NeR1cH 
Версия: Версия: 3.2 - Archive Browser Edition and UI Improvements
GitHub: 1.1.0.0
        """
        
        tk.Label(content, text=help_text.strip(), font=("Consolas", 9),
                bg="white", fg="#2c3e50", justify="left", anchor="w").pack(padx=30, pady=20, fill="both")
        
        # Кнопка закрытия
        btn_frame = tk.Frame(self.dialog, bg="white")
        btn_frame.pack(fill="x", padx=20, pady=15)
        
        ttk.Button(btn_frame, text="Закрыть", command=self.dialog.destroy, width=20).pack()

# ===================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ===================================================================

def main():
    root = tk.Tk()
    app = TranslatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()