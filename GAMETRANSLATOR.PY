#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DeepL Game Translator - Профессиональный переводчик игр (Full GUI Edition)
===========================================================================

УСТАНОВКА ЗАВИСИМОСТЕЙ:
-----------------------
pip install requests

ПОЛУЧЕНИЕ API КЛЮЧА:
--------------------
1. Зарегистрируйся на DeepL: https://www.deepl.com/pro-api
2. Выбери бесплатный план (500,000 символов/месяц)
3. Скопируй API ключ из личного кабинета
4. Вставь его в программе через настройки

Автор: NeR1cH (Enhanced by Claude)
Версия: 3.0 - Full GUI Edition
"""

import sys
import subprocess
import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import time
import zipfile
import tarfile
import tempfile
import shutil
import json
from pathlib import Path

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
    print("Установка зависимостей...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "--quiet"])
        print("✅ Зависимости установлены! Перезапусти программу.")
        input("Нажми Enter для выхода...")
        sys.exit(0)
    except:
        print("❌ Не удалось установить requests")
        print("Выполни вручную: pip install requests")
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
        except:
            pass
    return {"api_key": ""}

def save_config(config):
    """Сохраняет конфигурацию"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        return True
    except:
        return False

# ===================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===================================================================

def extract_english_parts(text):
    """Извлекает английские части из текста"""
    text = re.sub(r'\{.*?\}', '', text)
    text = re.sub(r'%\w+%', '', text)
    parts = re.split(r'(\s+|[.,!?:;()"\'])', text)
    english_parts = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if re.search(r'[A-Za-z]', part) and not re.search(r'[А-Яа-яЁё]', part):
            english_parts.append(part)
    if english_parts:
        return ' '.join(english_parts)
    return None

def extract_english_text_from_file(file_path):
    """Извлекает английский текст из файла"""
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            matches = re.findall(r'"(.*?)"', content, re.DOTALL)
            for match in matches:
                english_text = extract_english_parts(match)
                if english_text:
                    results.append(english_text)
    except:
        pass
    return results

def extract_archive(archive_path, extract_to):
    """Распаковывает архив"""
    try:
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            return True
        elif archive_path.endswith(('.tar', '.tar.gz', '.tgz')):
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)
            return True
    except:
        pass
    return False

def search_folder(folder_path, extract_archives=True):
    """Ищет файлы с текстом"""
    all_results = []
    unique_texts = set()
    file_structure = {}
    temp_dirs = []
    
    archive_extensions = ('.zip', '.tar', '.tar.gz', '.tgz')
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            full_path = os.path.join(root, file)
            
            if extract_archives and file.endswith(archive_extensions):
                temp_dir = tempfile.mkdtemp(prefix='game_extract_')
                temp_dirs.append(temp_dir)
                
                if extract_archive(full_path, temp_dir):
                    sub_results, sub_texts, sub_structure = search_folder(temp_dir, extract_archives=False)
                    all_results.extend(sub_results)
                    unique_texts.update(sub_texts)
                    file_structure.update(sub_structure)
            
            elif file.endswith(('.txt', '.json', '.yml', '.xml')):
                texts = extract_english_text_from_file(full_path)
                if texts:
                    all_results.append((full_path, texts))
                    unique_texts.update(texts)
                    rel_path = os.path.relpath(full_path, folder_path)
                    file_structure[rel_path] = texts
    
    for temp_dir in temp_dirs:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    return all_results, unique_texts, file_structure

def load_translations_from_file(file_path):
    """Загружает переводы из файла"""
    translations = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        parts = line.strip().split('=', 1)
                        if len(parts) == 2:
                            translations[parts[0].strip()] = parts[1].strip()
        except:
            pass
    return translations

def load_translations_from_folder(folder_path):
    """Загружает переводы из папки"""
    translations = {}
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.txt'):
                full_path = os.path.join(root, file)
                file_trans = load_translations_from_file(full_path)
                translations.update(file_trans)
    return translations

def save_translations_to_file(file_path, translations):
    """Сохраняет переводы в файл"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Переводы игры (DeepL)\n")
            f.write(f"# Всего фраз: {len(translations)}\n\n")
            for eng, rus in sorted(translations.items()):
                f.write(f"{eng} = {rus}\n")
        return True
    except:
        return False

def translate_with_deepl(text, api_key, source_lang='EN', target_lang='RU', retry=3):
    """Переводит текст через DeepL API"""
    if ':fx' in api_key:
        url = "https://api-free.deepl.com/v2/translate"
    else:
        url = "https://api.deepl.com/v2/translate"
    
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
                result = response.json()
                return result['translations'][0]['text']
            elif response.status_code == 403:
                return None, "Неверный API ключ"
            elif response.status_code == 456:
                return None, "Превышен лимит символов"
            elif response.status_code == 429:
                time.sleep(5)
                continue
            elif response.status_code == 500:
                if attempt < retry - 1:
                    time.sleep(3)
                    continue
                else:
                    return None, "Ошибка сервера DeepL"
            else:
                return None, f"Ошибка API: {response.status_code}"
        except:
            if attempt < retry - 1:
                time.sleep(2)
                continue
            else:
                return None, "Ошибка подключения"
    
    return None, "Не удалось перевести"

def apply_translations_to_file(original_file, translations, output_file):
    """Применяет переводы к файлу"""
    try:
        with open(original_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return False, 0
    
    pattern = r'"([^"]*)"'
    matches = list(re.finditer(pattern, content))
    
    if not matches:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, 0
        except:
            return False, 0
    
    translated_content = content
    offset = 0
    replaced_count = 0
    
    for match in matches:
        original_text = match.group(1)
        
        if not original_text.strip():
            continue
        
        translated_text = translations.get(original_text)
        
        if translated_text:
            old_match = f'"{original_text}"'
            new_match = f'"{translated_text}"'
            
            start_pos = match.start() + offset
            end_pos = match.end() + offset
            
            translated_content = (
                translated_content[:start_pos] + 
                new_match + 
                translated_content[end_pos:]
            )
            
            offset += len(new_match) - len(old_match)
            replaced_count += 1
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        return True, replaced_count
    except:
        return False, 0

# ===================================================================
# ГЛАВНОЕ ОКНО ПРИЛОЖЕНИЯ
# ===================================================================

class TranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🌐 DeepL Game Translator")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        self.config = load_config()
        self.api_key = self.config.get("api_key", "")
        
        self.center_window()
        self.setup_style()
        self.create_ui()
        
        if not self.api_key:
            self.show_settings()
        else:
            self.status_bar.config(text="✅ API ключ настроен", fg="#27ae60")
    
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
        
        ttk.Button(action_frame, text="▶️ Начать перевод",
                  command=self.start_translation,
                  style="Accent.TButton", width=25).pack(side="left", padx=5)
        ttk.Button(action_frame, text="💾 Сохранить результат",
                  command=self.save_translation_result, width=25).pack(side="left", padx=5)
        
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
        if path:
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
        """Запуск процесса перевода"""
        if not self.api_key:
            self.show_error("Ошибка", "API ключ не настроен! Перейдите в Настройки.")
            return
        
        if not self.translate_source:
            self.show_error("Ошибка", "Не выбран источник для перевода!")
            return
        
        self.log_message("translate", "\n" + "="*50)
        self.log_message("translate", "🚀 НАЧАЛО ПЕРЕВОДА")
        self.log_message("translate", "="*50)
        
        # Извлечение текстов
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
        
        # Перевод
        self.log_message("translate", f"\n🌐 Начинаю перевод {len(new_texts)} фраз...")
        self.translate_progress['maximum'] = len(new_texts)
        self.translate_progress['value'] = 0
        
        self.current_translations = dict(self.existing_translations)
        
        for i, text in enumerate(new_texts, 1):
            self.translate_progress['value'] = i
            percent = (i / len(new_texts)) * 100
            
            self.log_message("translate", f"[{i}/{len(new_texts)}] ({percent:.1f}%) {text[:50]}...")
            self.root.update()
            
            result = translate_with_deepl(text, self.api_key)
            
            if isinstance(result, tuple):
                self.log_message("translate", f"   ❌ Ошибка: {result[1]}")
            else:
                self.current_translations[text] = result
                self.log_message("translate", f"   ✅ {result[:50]}...")
            
            time.sleep(0.3)
        
        self.log_message("translate", f"\n✅ Перевод завершён!")
        self.log_message("translate", f"📊 Переведено: {len(self.current_translations)}")
        self.show_info("Готово", f"Переведено {len(self.current_translations)} фраз!")
    
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
                                        "• Папку с оригинальными файлами\n"
                                        "• Папку для результата\n\n"
                                        "Перейти на вкладку конвертации для настройки?")
                if choice:
                    self.notebook.select(3)  # Переключаемся на вкладку конвертации
                return
            
            # Выполняем конвертацию
            self.log_message("translate", "🔄 Конвертирую переводы в формат игры...")
            success = self.perform_conversion(self.current_translations)
            
            if success:
                self.log_message("translate", "✅ Конвертация завершена!")
                self.show_info("Успех", "Переводы сконвертированы и сохранены в формате игры!")
            return
        
        # Обычное сохранение
        choice = self.ask_yes_no("Способ сохранения", 
                                 "Как сохранить переводы?\n\n"
                                 "ДА - В один файл\n"
                                 "НЕТ - С сохранением структуры")
        
        if choice is None:
            return
        
        if choice:
            # Сохранение в один файл
            path = filedialog.asksaveasfilename(
                title="Сохранить переводы",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt")]
            )
            if path:
                if save_translations_to_file(path, self.current_translations):
                    self.show_info("Успех", f"Сохранено {len(self.current_translations)} переводов!")
                    self.log_message("translate", f"💾 Сохранено в: {path}")
        else:
            # Сохранение со структурой
            folder = filedialog.askdirectory(title="Выберите папку для сохранения")
            if folder:
                # TODO: Реализовать сохранение со структурой
                self.show_info("Информация", "Сохранение со структурой в разработке")
    
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
        """Выполняет конвертацию переводов"""
        if not self.convert_original_path:
            self.show_error("Ошибка", "Не выбрана папка с оригинальными файлами!")
            return False
        
        if not self.convert_output_path:
            self.show_error("Ошибка", "Не выбрана папка для результата!")
            return False
        
        self.log_message("convert", "\n" + "="*50)
        self.log_message("convert", "🔄 КОНВЕРТАЦИЯ ПЕРЕВОДОВ")
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
            
            # Конвертация
            self.log_message("convert", f"🔄 Обработка файлов из: {os.path.basename(original_folder)}")
            
            processed_files = 0
            total_replaced = 0
            
            for root, dirs, files in os.walk(original_folder):
                for file in files:
                    if file.endswith(('.txt', '.json', '.yml', '.xml')):
                        orig_path = os.path.join(root, file)
                        rel_path = os.path.relpath(orig_path, original_folder)
                        out_path = os.path.join(self.convert_output_path, rel_path)
                        
                        # Создаём папку если нужно
                        os.makedirs(os.path.dirname(out_path), exist_ok=True)
                        
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
            
            # Очистка
            if temp_dir:
                shutil.rmtree(temp_dir)
            
            self.log_message("convert", f"\n📊 Итого:")
            self.log_message("convert", f"   Обработано файлов: {processed_files}")
            self.log_message("convert", f"   Применено переводов: {total_replaced}")
            self.log_message("convert", f"   Сохранено в: {self.convert_output_path}")
            
            return True
        
        except Exception as e:
            self.log_message("convert", f"❌ Ошибка: {e}")
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
        
        if not self.api_key:
            self.show_error("Ошибка", "API ключ не настроен!")
            return
        
        self.log_message("verify", "\n🔧 ИСПРАВЛЕНИЕ ПРОБЛЕМНЫХ ПЕРЕВОДОВ\n")
        
        fixed = 0
        failed = 0
        
        for i, error_data in enumerate(self.verify_errors, 1):
            original = error_data['original']
            self.log_message("verify", f"[{i}/{len(self.verify_errors)}] Переводю: {original[:50]}...")
            
            result = translate_with_deepl(original, self.api_key, retry=5)
            
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
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ===================================================================
    
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

# ===================================================================
# ДИАЛОГОВЫЕ ОКНА
# ===================================================================

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

class YesNoDialog:
    def __init__(self, parent, title, message):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x220")
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
        self.dialog.geometry("600x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 600) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        # Заголовок
        header = tk.Frame(self.dialog, bg="#3498db", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="⚙️ Настройки DeepL API", 
                font=("Segoe UI", 16, "bold"), bg="#3498db", fg="white").pack(pady=15)
        
        # Контент
        content = tk.Frame(self.dialog, bg="white")
        content.pack(fill="both", expand=True, padx=30, pady=20)
        
        # API ключ
        tk.Label(content, text="DeepL API ключ:", font=("Segoe UI", 11, "bold"),
                bg="white", fg="#2c3e50").pack(anchor="w", pady=(10, 5))
        
        self.api_entry = tk.Entry(content, font=("Segoe UI", 10), width=50)
        self.api_entry.pack(fill="x", pady=5)
        self.api_entry.insert(0, self.app.api_key)
        
        # Включаем стандартные горячие клавиши для Windows
        self.api_entry.bind('<Control-v>', lambda e: self.paste_text())
        self.api_entry.bind('<Control-V>', lambda e: self.paste_text())
        self.api_entry.bind('<Control-a>', lambda e: self.select_all())
        self.api_entry.bind('<Control-A>', lambda e: self.select_all())
        self.api_entry.bind('<Control-c>', lambda e: self.copy_text())
        self.api_entry.bind('<Control-C>', lambda e: self.copy_text())
        self.api_entry.bind('<Control-x>', lambda e: self.cut_text())
        self.api_entry.bind('<Control-X>', lambda e: self.cut_text())
        
        # Добавляем контекстное меню (правая кнопка мыши)
        self.setup_context_menu()
        
        # Инструкция
        info_frame = tk.LabelFrame(content, text="Как получить API ключ", 
                                  bg="white", font=("Segoe UI", 10, "bold"),
                                  fg="#7f8c8d", padx=15, pady=10)
        info_frame.pack(fill="x", pady=20)
        
        instructions = """
1. Перейдите на сайт: https://www.deepl.com/pro-api
2. Нажмите "Sign up for free"
3. Заполните форму регистрации
4. Подтвердите email
5. В личном кабинете найдите раздел "API Keys"
6. Скопируйте ключ и вставьте выше

Бесплатный план: 500,000 символов/месяц
        """
        
        tk.Label(info_frame, text=instructions.strip(), font=("Segoe UI", 9),
                bg="white", fg="#636e72", justify="left").pack(anchor="w")
        
        # Кнопки
        btn_frame = tk.Frame(content, bg="white")
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="💾 Сохранить", 
                  command=self.save, width=20,
                  style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Отмена",
                  command=self.dialog.destroy, width=20).pack(side="left", padx=5)
    
    def setup_context_menu(self):
        """Создаёт контекстное меню для поля ввода"""
        self.context_menu = tk.Menu(self.api_entry, tearoff=0)
        self.context_menu.add_command(label="Вырезать (Ctrl+X)", command=self.cut_text)
        self.context_menu.add_command(label="Копировать (Ctrl+C)", command=self.copy_text)
        self.context_menu.add_command(label="Вставить (Ctrl+V)", command=self.paste_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Выделить всё (Ctrl+A)", command=self.select_all)
        
        self.api_entry.bind("<Button-3>", self.show_context_menu)
    
    def show_context_menu(self, event):
        """Показывает контекстное меню"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
    
    def paste_text(self):
        """Вставка из буфера обмена"""
        try:
            text = self.dialog.clipboard_get()
            if self.api_entry.selection_present():
                self.api_entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
            self.api_entry.insert(tk.INSERT, text)
        except:
            pass
        return "break"
    
    def copy_text(self):
        """Копирование в буфер обмена"""
        try:
            if self.api_entry.selection_present():
                text = self.api_entry.selection_get()
                self.dialog.clipboard_clear()
                self.dialog.clipboard_append(text)
        except:
            pass
        return "break"
    
    def cut_text(self):
        """Вырезание в буфер обмена"""
        try:
            if self.api_entry.selection_present():
                text = self.api_entry.selection_get()
                self.dialog.clipboard_clear()
                self.dialog.clipboard_append(text)
                self.api_entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except:
            pass
        return "break"
    
    def select_all(self):
        """Выделение всего текста"""
        self.api_entry.select_range(0, tk.END)
        self.api_entry.icursor(tk.END)
        return "break"
    
    def save(self):
        """Сохранение настроек"""
        api_key = self.api_entry.get().strip()
        
        if not api_key:
            ErrorDialog(self.dialog, "Ошибка", "API ключ не может быть пустым!")
            return
        
        # Обновляем ключ в приложении
        self.app.api_key = api_key
        self.app.config['api_key'] = api_key
        
        # Сохраняем конфигурацию
        if save_config(self.app.config):
            # Обновляем статус-бар
            self.app.status_bar.config(text="✅ API ключ настроен и готов к работе", fg="#27ae60")
            InfoDialog(self.dialog, "Успех", "Настройки сохранены!\n\nAPI ключ готов к использованию.")
            self.dialog.destroy()
        else:
            ErrorDialog(self.dialog, "Ошибка", "Не удалось сохранить настройки")
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
   • Архив - для .zip, .tar файлов
   • Папка - для поиска файлов в папке
   • Файл - для перевода одного файла

3. (Опционально) Загрузите существующие переводы, чтобы не переводить повторно

4. Нажмите "Начать перевод"

5. После завершения сохраните результат

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 ВКЛАДКА "ПРИМЕНИТЬ"

Применяет готовые переводы к оригинальным файлам игры.

Шаги:
1. Загрузите переводы (из файла или папки)

2. Выберите оригинальные файлы:
   • Один файл - для применения к одному файлу
   • Папка - для обработки всех файлов в папке
   • Архив - для распаковки и обработки архива

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

Автор: NeR1cH (Enhanced by Claude)
Версия: 3.0 - Full GUI Edition
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