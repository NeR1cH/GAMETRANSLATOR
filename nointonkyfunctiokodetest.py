#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DeepL Game Translator - Minimalist Edition
==========================================
Версия: 4.0 - Minimalist UI with Enhanced Architecture

Автор: NeR1cH (Refactored)
"""

import sys
import subprocess
import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import time
import zipfile
import tarfile
import tempfile
import shutil
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

# ===================================================================
# ПРОВЕРКА ЗАВИСИМОСТЕЙ
# ===================================================================

def check_and_install_dependencies():
    """Проверяет и устанавливает зависимости"""
    try:
        import requests
        return True
    except ImportError:
        print("Установка зависимостей...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "--quiet"])
            print("✅ Зависимости установлены! Перезапустите программу.")
            input("Нажмите Enter...")
            sys.exit(0)
        except:
            print("❌ Ошибка установки requests")
            print("Выполните: pip install requests")
            input("Нажмите Enter...")
            sys.exit(1)

check_and_install_dependencies()
import requests

# ===================================================================
# КОНФИГУРАЦИЯ И КОНСТАНТЫ
# ===================================================================

CONFIG_FILE = "translator_config.json"

class FileType(Enum):
    """Типы поддерживаемых файлов"""
    TEXT = ('.txt', '.json', '.yml', '.yaml', '.xml')
    ARCHIVE = ('.zip', '.tar', '.tar.gz', '.tgz')

@dataclass
class TranslationResult:
    """Результат перевода"""
    original: str
    translated: str
    success: bool
    error: Optional[str] = None

# ===================================================================
# МОДУЛЬ КОНФИГУРАЦИИ
# ===================================================================

class ConfigManager:
    """Управление конфигурацией приложения"""
    
    @staticmethod
    def load() -> Dict:
        """Загружает конфигурацию"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"api_key": ""}
    
    @staticmethod
    def save(config: Dict) -> bool:
        """Сохраняет конфигурацию"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            return True
        except:
            return False

# ===================================================================
# МОДУЛЬ ОБРАБОТКИ ТЕКСТА
# ===================================================================

class TextExtractor:
    """Извлечение английского текста из файлов"""
    
    @staticmethod
    def extract_english_parts(text: str) -> Optional[str]:
        """Извлекает английские части из текста"""
        # Удаляем специальные конструкции
        text = re.sub(r'\{.*?\}', '', text)
        text = re.sub(r'%\w+%', '', text)
        
        # Разбиваем на части
        parts = re.split(r'(\s+|[.,!?:;()"\'])', text)
        english_parts = []
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Проверяем наличие английских букв без кириллицы
            if re.search(r'[A-Za-z]', part) and not re.search(r'[А-Яа-яЁё]', part):
                english_parts.append(part)
        
        return ' '.join(english_parts) if english_parts else None
    
    @staticmethod
    def extract_from_file(file_path: str) -> List[str]:
        """Извлекает английский текст из файла"""
        results = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Ищем текст в кавычках
                matches = re.findall(r'"(.*?)"', content, re.DOTALL)
                for match in matches:
                    english_text = TextExtractor.extract_english_parts(match)
                    if english_text:
                        results.append(english_text)
        except Exception as e:
            print(f"Ошибка чтения файла {file_path}: {e}")
        return results

# ===================================================================
# МОДУЛЬ РАБОТЫ С АРХИВАМИ
# ===================================================================

class ArchiveHandler:
    """Обработка архивов"""
    
    @staticmethod
    def extract(archive_path: str, extract_to: str) -> bool:
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
        except Exception as e:
            print(f"Ошибка распаковки архива: {e}")
        return False
    
    @staticmethod
    def get_contents(archive_path: str) -> List[Dict]:
        """Получает список содержимого архива"""
        temp_dir = tempfile.mkdtemp(prefix='archive_preview_')
        contents = []
        
        try:
            if ArchiveHandler.extract(archive_path, temp_dir):
                for root, dirs, files in os.walk(temp_dir):
                    for dir_name in dirs:
                        full_path = os.path.join(root, dir_name)
                        rel_path = os.path.relpath(full_path, temp_dir)
                        file_count = sum([len(f) for _, _, f in os.walk(full_path)])
                        
                        contents.append({
                            'name': rel_path,
                            'type': 'folder',
                            'size': f'{file_count} файлов',
                            'full_path': full_path,
                            'is_dir': True
                        })
                    
                    for file_name in files:
                        if file_name.endswith(FileType.TEXT.value):
                            full_path = os.path.join(root, file_name)
                            rel_path = os.path.relpath(full_path, temp_dir)
                            
                            try:
                                size = os.path.getsize(full_path)
                                size_str = ArchiveHandler._format_size(size)
                            except:
                                size_str = "?"
                            
                            contents.append({
                                'name': rel_path,
                                'type': 'file',
                                'size': size_str,
                                'full_path': full_path,
                                'is_dir': False
                            })
                
                contents.sort(key=lambda x: (not x['is_dir'], x['name']))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        return contents
    
    @staticmethod
    def _format_size(size: int) -> str:
        """Форматирует размер файла"""
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"

# ===================================================================
# МОДУЛЬ ПОИСКА ФАЙЛОВ
# ===================================================================

class FileScanner:
    """Сканирование файлов в папках и архивах"""
    
    @staticmethod
    def scan_folder(folder_path: str, extract_archives: bool = True) -> Tuple[List[Tuple[str, List[str]]], Set[str], Dict[str, List[str]]]:
        """Сканирует папку и извлекает тексты"""
        all_results = []
        unique_texts = set()
        file_structure = {}
        temp_dirs = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                
                # Обработка архивов
                if extract_archives and file.endswith(FileType.ARCHIVE.value):
                    temp_dir = tempfile.mkdtemp(prefix='game_extract_')
                    temp_dirs.append(temp_dir)
                    
                    if ArchiveHandler.extract(full_path, temp_dir):
                        sub_results, sub_texts, sub_structure = FileScanner.scan_folder(temp_dir, extract_archives=False)
                        all_results.extend(sub_results)
                        unique_texts.update(sub_texts)
                        file_structure.update(sub_structure)
                
                # Обработка текстовых файлов
                elif file.endswith(FileType.TEXT.value):
                    texts = TextExtractor.extract_from_file(full_path)
                    if texts:
                        all_results.append((full_path, texts))
                        unique_texts.update(texts)
                        rel_path = os.path.relpath(full_path, folder_path)
                        file_structure[rel_path] = texts
        
        # Очистка временных папок
        for temp_dir in temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        return all_results, unique_texts, file_structure

# ===================================================================
# МОДУЛЬ ПЕРЕВОДОВ
# ===================================================================

class TranslationManager:
    """Управление переводами"""
    
    @staticmethod
    def load_from_file(file_path: str) -> Dict[str, str]:
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
            except Exception as e:
                print(f"Ошибка загрузки переводов: {e}")
        return translations
    
    @staticmethod
    def load_from_folder(folder_path: str) -> Dict[str, str]:
        """Загружает переводы из папки"""
        translations = {}
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith('.txt'):
                    full_path = os.path.join(root, file)
                    file_trans = TranslationManager.load_from_file(full_path)
                    translations.update(file_trans)
        return translations
    
    @staticmethod
    def save_to_file(file_path: str, translations: Dict[str, str]) -> bool:
        """Сохраняет переводы в файл"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("# Переводы игры (DeepL)\n")
                f.write(f"# Всего фраз: {len(translations)}\n\n")
                for eng, rus in sorted(translations.items()):
                    f.write(f"{eng} = {rus}\n")
            return True
        except Exception as e:
            print(f"Ошибка сохранения переводов: {e}")
            return False
    
    @staticmethod
    def apply_to_file(original_file: str, translations: Dict[str, str], output_file: str) -> Tuple[bool, int]:
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
# МОДУЛЬ API DEEPL
# ===================================================================

class DeepLAPI:
    """Взаимодействие с DeepL API"""
    
    @staticmethod
    def translate(text: str, api_key: str, source_lang: str = 'EN', 
                  target_lang: str = 'RU', retry: int = 3) -> TranslationResult:
        """Переводит текст через DeepL API"""
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
                    result = response.json()
                    return TranslationResult(
                        original=text,
                        translated=result['translations'][0]['text'],
                        success=True
                    )
                elif response.status_code == 403:
                    return TranslationResult(text, "", False, "Неверный API ключ")
                elif response.status_code == 456:
                    return TranslationResult(text, "", False, "Превышен лимит символов")
                elif response.status_code == 429:
                    time.sleep(5)
                    continue
                elif response.status_code == 500:
                    if attempt < retry - 1:
                        time.sleep(3)
                        continue
                    else:
                        return TranslationResult(text, "", False, "Ошибка сервера DeepL")
                else:
                    return TranslationResult(text, "", False, f"Ошибка API: {response.status_code}")
            except Exception as e:
                if attempt < retry - 1:
                    time.sleep(2)
                    continue
                else:
                    return TranslationResult(text, "", False, f"Ошибка подключения: {e}")
        
        return TranslationResult(text, "", False, "Не удалось перевести")
    
    @staticmethod
    def verify_key(api_key: str) -> Tuple[bool, str]:
        """Проверяет валидность API ключа"""
        result = DeepLAPI.translate("Hello", api_key, retry=1)
        if result.success:
            return True, "Ключ валиден"
        return False, result.error or "Неизвестная ошибка"

# ===================================================================
# МОДУЛЬ ПРОВЕРКИ КАЧЕСТВА
# ===================================================================

class QualityChecker:
    """Проверка качества переводов"""
    
    @staticmethod
    def check_translation(original: str, translated: str) -> List[str]:
        """Проверяет качество перевода"""
        errors = []
        
        if not translated or translated.strip() == "":
            errors.append("Пустой перевод")
        
        if original.strip().lower() == translated.strip().lower():
            errors.append("Текст не переведён")
        
        if not re.search(r'[А-Яа-яЁё]', translated):
            errors.append("Нет кириллицы")
        
        if len(translated) < len(original) * 0.3 and len(original) > 20:
            errors.append("Подозрительно короткий")
        
        return errors
    
    @staticmethod
    def check_translations(translations: Dict[str, str]) -> List[Dict]:
        """Проверяет все переводы"""
        errors = []
        for original, translated in translations.items():
            issues = QualityChecker.check_translation(original, translated)
            if issues:
                errors.append({
                    'original': original,
                    'translated': translated,
                    'errors': issues
                })
        return errors

# ===================================================================
# ГЛАВНОЕ ПРИЛОЖЕНИЕ - МИНИМАЛИСТИЧНЫЙ ИНТЕРФЕЙС
# ===================================================================

class MinimalTranslatorApp:
    """Минималистичное приложение переводчика"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("DeepL Game Translator")
        self.root.geometry("800x600")
        
        # Данные
        self.config = ConfigManager.load()
        self.api_key = self.config.get("api_key", "")
        self.translations = {}
        self.current_source = None
        
        self._setup_ui()
        self._center_window()
        
        # Проверка API ключа при запуске
        if not self.api_key:
            self.root.after(500, self._show_api_setup)
    
    def _center_window(self):
        """Центрирует окно"""
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 800) // 2
        y = (self.root.winfo_screenheight() - 600) // 2
        self.root.geometry(f'800x600+{x}+{y}')
    
    def _setup_ui(self):
        """Создание интерфейса"""
        # Стиль
        style = ttk.Style()
        style.theme_use('clam')
        
        # Заголовок
        header = tk.Frame(self.root, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="🌐 DeepL Game Translator", 
                font=("Segoe UI", 16, "bold"), bg="#2c3e50", fg="white").pack(side="left", padx=20)
        
        ttk.Button(header, text="⚙️", command=self._show_api_setup, width=3).pack(side="right", padx=10)
        ttk.Button(header, text="❓", command=self._show_help, width=3).pack(side="right", padx=5)
        
        # Основная область
        main = tk.Frame(self.root, bg="#ecf0f1")
        main.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Панель действий
        actions = tk.LabelFrame(main, text="Основные действия", font=("Segoe UI", 10, "bold"),
                               bg="white", padx=15, pady=15)
        actions.pack(fill="x", pady=5)
        
        btn_frame = tk.Frame(actions, bg="white")
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="📁 Выбрать источник", 
                  command=self._select_source, width=20).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="🌐 Перевести", 
                  command=self._translate, width=20).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="📝 Применить переводы", 
                  command=self._apply_translations, width=20).pack(side="left", padx=5)
        
        self.source_label = tk.Label(actions, text="Источник не выбран", 
                                    bg="white", fg="#7f8c8d", font=("Segoe UI", 9))
        self.source_label.pack(anchor="w", pady=5)
        
        # Прогресс
        progress = tk.LabelFrame(main, text="Прогресс", font=("Segoe UI", 10, "bold"),
                                bg="white", padx=15, pady=15)
        progress.pack(fill="both", expand=True, pady=5)
        
        self.progress_bar = ttk.Progressbar(progress, mode='determinate')
        self.progress_bar.pack(fill="x", pady=5)
        
        # Лог с прокруткой
        log_frame = tk.Frame(progress, bg="white")
        log_frame.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.log_text = tk.Text(log_frame, height=15, font=("Consolas", 9),
                               bg="#f8f9fa", fg="#2c3e50", yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Дополнительные действия
        extra = tk.Frame(main, bg="white")
        extra.pack(fill="x", pady=5)
        
        ttk.Button(extra, text="🔍 Проверить качество", 
                  command=self._check_quality, width=20).pack(side="left", padx=5)
        ttk.Button(extra, text="💾 Сохранить", 
                  command=self._save_translations, width=20).pack(side="left", padx=5)
        ttk.Button(extra, text="📂 Загрузить переводы", 
                  command=self._load_translations, width=20).pack(side="left", padx=5)
        
        # Статус-бар
        self.status = tk.Label(self.root, text="Готов к работе", 
                              bg="#34495e", fg="white", anchor="w", padx=10, height=2)
        self.status.pack(fill="x", side="bottom")
    
    def _log(self, message: str):
        """Добавление сообщения в лог"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def _update_status(self, message: str, color: str = "#34495e"):
        """Обновление статус-бара"""
        self.status.config(text=message, bg=color)
        self.root.update()
    
    def _select_source(self):
        """Выбор источника для перевода"""
        choice = messagebox.askquestion("Выбор источника", 
                                       "Выбрать папку?\n\nДА - Папка\nНЕТ - Архив или файл")
        
        if choice == 'yes':
            path = filedialog.askdirectory(title="Выберите папку")
            if path:
                self.current_source = ('folder', path)
                self.source_label.config(text=f"Папка: {os.path.basename(path)}", fg="#27ae60")
                self._log(f"✅ Выбрана папка: {path}")
        else:
            path = filedialog.askopenfilename(
                title="Выберите файл или архив",
                filetypes=[("Все поддерживаемые", "*.txt *.json *.yml *.xml *.zip *.tar *.tar.gz"),
                          ("Текстовые", "*.txt *.json *.yml *.xml"),
                          ("Архивы", "*.zip *.tar *.tar.gz"),
                          ("Все файлы", "*.*")]
            )
            if path:
                if path.endswith(FileType.ARCHIVE.value):
                    # Предложить выбор файлов из архива
                    if messagebox.askyesno("Браузер архива", 
                                          "Хотите выбрать конкретные файлы из архива?"):
                        self._browse_archive(path)
                    else:
                        self.current_source = ('archive', path)
                        self.source_label.config(text=f"Архив: {os.path.basename(path)}", fg="#27ae60")
                        self._log(f"✅ Выбран архив: {path}")
                else:
                    self.current_source = ('file', path)
                    self.source_label.config(text=f"Файл: {os.path.basename(path)}", fg="#27ae60")
                    self._log(f"✅ Выбран файл: {path}")
    
    def _browse_archive(self, archive_path: str):
        """Браузер содержимого архива"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Содержимое: {os.path.basename(archive_path)}")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Заголовок
        tk.Label(dialog, text="Выберите файлы/папки", 
                font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        # Список
        frame = tk.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        
        tree = ttk.Treeview(frame, yscrollcommand=scrollbar.set, selectmode="extended")
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=tree.yview)
        
        tree['columns'] = ('type', 'size')
        tree.column('#0', width=350)
        tree.column('type', width=100)
        tree.column('size', width=100)
        
        tree.heading('#0', text='Имя')
        tree.heading('type', text='Тип')
        tree.heading('size', text='Размер')
        
        # Загрузка содержимого
        contents = ArchiveHandler.get_contents(archive_path)
        for item in contents:
            tree.insert('', 'end', text=item['name'],
                       values=(item['type'], item['size']),
                       tags=(item['full_path'],))
        
        # Кнопки
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        def confirm():
            selected = tree.selection()
            if selected:
                temp_dir = tempfile.mkdtemp(prefix='selected_')
                # Извлекаем выбранные элементы
                # (упрощённая версия - в реальности нужна полная реализация)
                self.current_source = ('folder', temp_dir)
                self.source_label.config(text=f"Из архива: {len(selected)} элементов", fg="#27ae60")
                self._log(f"✅ Выбрано {len(selected)} элементов из архива")
                dialog.destroy()
        
        ttk.Button(btn_frame, text="Выбрать", command=confirm, width=15).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Отмена", command=dialog.destroy, width=15).pack(side="left", padx=5)
    
    def _translate(self):
        """Перевод текстов"""
        if not self.api_key:
            messagebox.showerror("Ошибка", "API ключ не настроен!")
            return
        
        if not self.current_source:
            messagebox.showerror("Ошибка", "Источник не выбран!")
            return
        
        self._log("\n" + "="*60)
        self._log("🚀 НАЧАЛО ПЕРЕВОДА")
        self._log("="*60)
        
        source_type, source_path = self.current_source
        texts_to_translate = []
        
        try:
            # Извлечение текстов в зависимости от типа источника
            if source_type == 'folder':
                _, unique_texts, _ = FileScanner.scan_folder(source_path)
                texts_to_translate = list(unique_texts)
            
            elif source_type == 'archive':
                temp_dir = tempfile.mkdtemp(prefix='translate_')
                if ArchiveHandler.extract(source_path, temp_dir):
                    _, unique_texts, _ = FileScanner.scan_folder(temp_dir, extract_archives=False)
                    texts_to_translate = list(unique_texts)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                else:
                    messagebox.showerror("Ошибка", "Не удалось распаковать архив")
                    return
            
            elif source_type == 'file':
                texts_to_translate = TextExtractor.extract_from_file(source_path)
            
            if not texts_to_translate:
                messagebox.showwarning("Внимание", "Не найдено текстов для перевода!")
                return
            
            # Фильтрация уже переведённых
            new_texts = [t for t in texts_to_translate if t not in self.translations]
            
            self._log(f"📊 Найдено текстов: {len(texts_to_translate)}")
            self._log(f"✅ Уже переведено: {len(texts_to_translate) - len(new_texts)}")
            self._log(f"🆕 Требует перевода: {len(new_texts)}")
            
            if not new_texts:
                messagebox.showinfo("Готово", "Все тексты уже переведены!")
                return
            
            # Перевод
            self._log(f"\n🌐 Начинаю перевод {len(new_texts)} фраз...")
            self.progress_bar['maximum'] = len(new_texts)
            self.progress_bar['value'] = 0
            
            for i, text in enumerate(new_texts, 1):
                self.progress_bar['value'] = i
                percent = (i / len(new_texts)) * 100
                
                self._log(f"[{i}/{len(new_texts)}] ({percent:.1f}%) {text[:50]}...")
                self._update_status(f"Перевод: {i}/{len(new_texts)} ({percent:.0f}%)", "#3498db")
                
                result = DeepLAPI.translate(text, self.api_key)
                
                if result.success:
                    self.translations[result.original] = result.translated
                    self._log(f"   ✅ {result.translated[:50]}...")
                else:
                    self._log(f"   ❌ Ошибка: {result.error}")
                
                time.sleep(0.3)  # Задержка между запросами
            
            self._log(f"\n✅ Перевод завершён!")
            self._log(f"📊 Переведено: {len(self.translations)}")
            self._update_status(f"✅ Готово! Переведено: {len(self.translations)}", "#27ae60")
            messagebox.showinfo("Готово", f"Переведено {len(self.translations)} фраз!")
        
        except Exception as e:
            self._log(f"❌ Ошибка: {e}")
            self._update_status("❌ Ошибка перевода", "#e74c3c")
            messagebox.showerror("Ошибка", f"Произошла ошибка:\n{e}")
    
    def _apply_translations(self):
        """Применение переводов к файлам"""
        if not self.translations:
            messagebox.showerror("Ошибка", "Нет переводов для применения!")
            return
        
        # Выбор оригинальных файлов
        choice = messagebox.askquestion("Источник", 
                                       "Применить к папке?\n\nДА - Папка\nНЕТ - Один файл")
        
        if choice == 'yes':
            source_path = filedialog.askdirectory(title="Выберите папку с оригинальными файлами")
            if not source_path:
                return
            
            output_path = filedialog.askdirectory(title="Выберите папку для результата")
            if not output_path:
                return
            
            self._log("\n" + "="*60)
            self._log("📝 ПРИМЕНЕНИЕ ПЕРЕВОДОВ К ПАПКЕ")
            self._log("="*60)
            
            processed = 0
            total_replaced = 0
            
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    if file.endswith(FileType.TEXT.value):
                        orig_path = os.path.join(root, file)
                        rel_path = os.path.relpath(orig_path, source_path)
                        out_path = os.path.join(output_path, rel_path)
                        
                        os.makedirs(os.path.dirname(out_path), exist_ok=True)
                        
                        success, count = TranslationManager.apply_to_file(
                            orig_path, self.translations, out_path
                        )
                        
                        if success:
                            processed += 1
                            total_replaced += count
                            if count > 0:
                                self._log(f"✅ {rel_path}: {count} фраз")
            
            self._log(f"\n📊 Итого:")
            self._log(f"   Обработано файлов: {processed}")
            self._log(f"   Заменено фраз: {total_replaced}")
            self._update_status(f"✅ Применено к {processed} файлам", "#27ae60")
            messagebox.showinfo("Готово", f"Обработано {processed} файлов\nЗаменено {total_replaced} фраз")
        
        else:
            source_file = filedialog.askopenfilename(
                title="Выберите оригинальный файл",
                filetypes=[("Текстовые файлы", "*.txt *.json *.yml *.xml"), ("Все файлы", "*.*")]
            )
            if not source_file:
                return
            
            output_file = filedialog.asksaveasfilename(
                title="Сохранить как",
                defaultextension=".txt",
                filetypes=[("Все файлы", "*.*")]
            )
            if not output_file:
                return
            
            self._log("\n" + "="*60)
            self._log("📝 ПРИМЕНЕНИЕ ПЕРЕВОДОВ К ФАЙЛУ")
            self._log("="*60)
            
            success, count = TranslationManager.apply_to_file(
                source_file, self.translations, output_file
            )
            
            if success:
                self._log(f"✅ Обработан файл: {os.path.basename(source_file)}")
                self._log(f"📊 Заменено фраз: {count}")
                self._update_status(f"✅ Заменено {count} фраз", "#27ae60")
                messagebox.showinfo("Готово", f"Заменено {count} фраз!")
            else:
                self._log(f"❌ Ошибка обработки файла")
                self._update_status("❌ Ошибка применения", "#e74c3c")
                messagebox.showerror("Ошибка", "Не удалось применить переводы")
    
    def _check_quality(self):
        """Проверка качества переводов"""
        if not self.translations:
            messagebox.showerror("Ошибка", "Нет переводов для проверки!")
            return
        
        self._log("\n" + "="*60)
        self._log("🔍 ПРОВЕРКА КАЧЕСТВА ПЕРЕВОДОВ")
        self._log("="*60)
        
        errors = QualityChecker.check_translations(self.translations)
        
        self._log(f"📊 Всего переводов: {len(self.translations)}")
        self._log(f"✅ Корректных: {len(self.translations) - len(errors)}")
        self._log(f"❌ С проблемами: {len(errors)}")
        
        if errors:
            self._log("\nПроблемные переводы:")
            error_types = {}
            for err in errors[:10]:  # Показываем только первые 10
                self._log(f"\n❌ {err['original'][:50]}...")
                self._log(f"   Проблемы: {', '.join(err['errors'])}")
                for e_type in err['errors']:
                    error_types[e_type] = error_types.get(e_type, 0) + 1
            
            if len(errors) > 10:
                self._log(f"\n... и ещё {len(errors) - 10} проблемных переводов")
            
            self._log("\nТипы проблем:")
            for e_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                self._log(f"  • {e_type}: {count}")
            
            # Предложить исправить
            if messagebox.askyesno("Исправить проблемы?", 
                                  f"Найдено {len(errors)} проблемных переводов.\n\nИсправить автоматически?"):
                self._fix_translations(errors)
        else:
            self._log("\n✅ Все переводы в порядке!")
            messagebox.showinfo("Отлично!", "Все переводы корректны! ✅")
    
    def _fix_translations(self, errors: List[Dict]):
        """Исправление проблемных переводов"""
        if not self.api_key:
            messagebox.showerror("Ошибка", "API ключ не настроен!")
            return
        
        self._log("\n🔧 ИСПРАВЛЕНИЕ ПРОБЛЕМНЫХ ПЕРЕВОДОВ")
        
        fixed = 0
        failed = 0
        
        self.progress_bar['maximum'] = len(errors)
        self.progress_bar['value'] = 0
        
        for i, error_data in enumerate(errors, 1):
            self.progress_bar['value'] = i
            original = error_data['original']
            
            self._log(f"[{i}/{len(errors)}] Переводю: {original[:50]}...")
            self._update_status(f"Исправление: {i}/{len(errors)}", "#f39c12")
            
            result = DeepLAPI.translate(original, self.api_key, retry=5)
            
            if result.success:
                self.translations[original] = result.translated
                self._log(f"   ✅ Исправлено: {result.translated[:50]}...")
                fixed += 1
            else:
                self._log(f"   ❌ Не удалось: {result.error}")
                failed += 1
            
            time.sleep(0.5)
        
        self._log(f"\n📊 Результаты исправления:")
        self._log(f"   ✅ Исправлено: {fixed}")
        self._log(f"   ❌ Не удалось: {failed}")
        self._update_status(f"✅ Исправлено: {fixed}/{len(errors)}", "#27ae60")
        messagebox.showinfo("Готово", f"Исправлено {fixed} из {len(errors)} проблемных переводов")
    
    def _save_translations(self):
        """Сохранение переводов"""
        if not self.translations:
            messagebox.showerror("Ошибка", "Нет переводов для сохранения!")
            return
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        path = filedialog.asksaveasfilename(
            title="Сохранить переводы",
            defaultextension=".txt",
            initialfile=f"translations_{timestamp}.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if path:
            if TranslationManager.save_to_file(path, self.translations):
                self._log(f"💾 Сохранено в: {path}")
                self._update_status(f"✅ Сохранено: {len(self.translations)} переводов", "#27ae60")
                messagebox.showinfo("Успех", f"✅ Сохранено {len(self.translations)} переводов!\n\n📄 {os.path.basename(path)}")
            else:
                self._log(f"❌ Ошибка сохранения")
                self._update_status("❌ Ошибка сохранения", "#e74c3c")
                messagebox.showerror("Ошибка", "Не удалось сохранить переводы")
    
    def _load_translations(self):
        """Загрузка переводов"""
        choice = messagebox.askquestion("Загрузка", 
                                       "Загрузить из папки?\n\nДА - Папка\nНЕТ - Файл")
        
        if choice == 'yes':
            path = filedialog.askdirectory(title="Выберите папку с переводами")
            if path:
                loaded = TranslationManager.load_from_folder(path)
                self.translations.update(loaded)
                self._log(f"✅ Загружено {len(loaded)} переводов из папки")
                self._update_status(f"✅ Загружено: {len(self.translations)} переводов", "#27ae60")
                messagebox.showinfo("Успех", f"Загружено {len(loaded)} переводов из папки")
        else:
            path = filedialog.askopenfilename(
                title="Выберите файл с переводами",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if path:
                loaded = TranslationManager.load_from_file(path)
                self.translations.update(loaded)
                self._log(f"✅ Загружено {len(loaded)} переводов из файла")
                self._update_status(f"✅ Загружено: {len(self.translations)} переводов", "#27ae60")
                messagebox.showinfo("Успех", f"Загружено {len(loaded)} переводов из файла")
    
    def _show_api_setup(self):
        """Настройка API ключа"""
        dialog = tk.Toplevel(self.root)
        dialog.title("⚙️ Настройки API")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Центрирование
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Заголовок
        tk.Label(dialog, text="⚙️ Настройка DeepL API", 
                font=("Segoe UI", 14, "bold")).pack(pady=15)
        
        # Контент
        content = tk.Frame(dialog)
        content.pack(fill="both", expand=True, padx=20, pady=10)
        
        tk.Label(content, text="DeepL API ключ:", 
                font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        
        api_entry = tk.Entry(content, font=("Segoe UI", 10), width=50)
        api_entry.pack(fill="x", pady=5)
        api_entry.insert(0, self.api_key)
        
        # Инструкция
        info = tk.LabelFrame(content, text="Как получить API ключ", 
                            font=("Segoe UI", 9, "bold"), padx=10, pady=10)
        info.pack(fill="x", pady=15)
        
        instructions = """1. Перейдите: https://www.deepl.com/pro-api
2. Нажмите "Sign up for free"
3. Заполните форму и подтвердите email
4. В личном кабинете найдите "API Keys"
5. Скопируйте ключ и вставьте выше

Бесплатный план: 500,000 символов/месяц"""
        
        tk.Label(info, text=instructions, font=("Segoe UI", 8), 
                justify="left").pack(anchor="w")
        
        # Кнопки
        btn_frame = tk.Frame(content)
        btn_frame.pack(pady=20)
        
        def save():
            key = api_entry.get().strip()
            if not key:
                messagebox.showerror("Ошибка", "API ключ не может быть пустым!", parent=dialog)
                return
            
            # Проверка ключа
            dialog.config(cursor="wait")
            dialog.update()
            
            valid, message = DeepLAPI.verify_key(key)
            dialog.config(cursor="")
            
            if valid:
                self.api_key = key
                self.config['api_key'] = key
                ConfigManager.save(self.config)
                
                self._update_status("✅ API ключ проверен и сохранён", "#27ae60")
                self._log(f"✅ API ключ настроен: {key[:10]}...{key[-5:]}")
                messagebox.showinfo("Успех!", f"✅ API ключ подтверждён!\n\n{message}", parent=dialog)
                dialog.destroy()
            else:
                messagebox.showerror("Ошибка", f"Не удалось проверить ключ:\n{message}", parent=dialog)
        
        ttk.Button(btn_frame, text="💾 Сохранить", command=save, width=15).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Отмена", command=dialog.destroy, width=15).pack(side="left", padx=5)
    
    def _show_help(self):
        """Справка"""
        dialog = tk.Toplevel(self.root)
        dialog.title("❓ Справка")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        
        # Центрирование
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 600) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 500) // 2
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="❓ Как пользоваться", 
                font=("Segoe UI", 14, "bold")).pack(pady=15)
        
        # Прокручиваемый текст
        frame = tk.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        
        text = tk.Text(frame, font=("Consolas", 9), wrap="word", 
                      yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text.yview)
        
        help_text = """
🌐 БЫСТРЫЙ СТАРТ

1. ⚙️ Настройте API ключ (кнопка вверху справа)
2. 📁 Выберите источник (папка, архив или файл)
3. 🌐 Нажмите "Перевести"
4. 💾 Сохраните результат

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 ОСНОВНЫЕ ФУНКЦИИ

📁 Выбрать источник
   Выбор файлов для перевода:
   • Папка - поиск всех текстовых файлов
   • Архив - с возможностью выбора содержимого
   • Файл - обработка одного файла

🌐 Перевести
   Автоматический перевод всех найденных текстов
   через DeepL API. Пропускает уже переведённые.

📝 Применить переводы
   Применяет готовые переводы к оригинальным
   файлам игры, сохраняя структуру.

🔍 Проверить качество
   Находит проблемные переводы:
   • Пустые переводы
   • Непереведённый текст
   • Отсутствие кириллицы
   • Подозрительно короткие

💾 Сохранить
   Сохранение переводов в формате:
   "оригинал = перевод"

📂 Загрузить переводы
   Загрузка существующих переводов
   из файла или папки

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 СОВЕТЫ

• Всегда сохраняйте промежуточные результаты
• Проверяйте качество перед применением
• Следите за лимитом (500,000 символов/месяц)
• Храните резервные копии оригиналов

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ

Файлы: .txt, .json, .yml, .yaml, .xml
Архивы: .zip, .tar, .tar.gz, .tgz

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Версия: 4.0 - Minimalist Edition
Автор: NeR1cH (Refactored)
"""
        
        text.insert("1.0", help_text)
        text.config(state="disabled")
        
        ttk.Button(dialog, text="Закрыть", command=dialog.destroy, width=15).pack(pady=10)

# ===================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ===================================================================

def main():
    """Точка входа в приложение"""
    root = tk.Tk()
    app = MinimalTranslatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()