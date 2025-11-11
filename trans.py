#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Game Text Scanner v2.0 - Улучшенная версия
===========================================

Сканирует игровые файлы, извлекает английский текст и создаёт переводы

Автор: NeR1cH (улучшено)
Версия: 2.0
"""

import os
import re
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import zipfile
import tempfile
import shutil
from pathlib import Path

# ===================================================================
# КЛАСС БРАУЗЕРА АРХИВОВ
# ===================================================================

class ArchiveSelector:
    def __init__(self, archive_path):
        self.archive_path = archive_path
        self.selected_items = []
        self.temp_dir = None
        
    def show_selector(self):
        """Показывает окно выбора файлов/папок из архива"""
        root = tk.Tk()
        root.title("📦 Выберите файлы/папки из архива")
        root.geometry("700x500")
        
        # Заголовок
        header = tk.Frame(root, bg="#3498db", height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text=f"📦 {os.path.basename(self.archive_path)}",
                font=("Segoe UI", 14, "bold"), bg="#3498db", fg="white").pack(pady=15)
        
        # Инструкция
        info_frame = tk.Frame(root, bg="#e8f4f8")
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(info_frame, 
                text="Выберите файлы или папки для обработки. Можно выбрать несколько (Ctrl+клик)",
                font=("Segoe UI", 9), bg="#e8f4f8", fg="#2c3e50").pack(pady=8, padx=10)
        
        # Создаём дерево файлов
        tree_frame = ttk.Frame(root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set, selectmode='extended')
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=tree.yview)
        
        # Настройка колонок
        tree['columns'] = ('type', 'size')
        tree.column('#0', width=400, minwidth=200)
        tree.column('type', width=100, minwidth=80)
        tree.column('size', width=100, minwidth=80)
        
        tree.heading('#0', text='Имя', anchor='w')
        tree.heading('type', text='Тип', anchor='w')
        tree.heading('size', text='Размер', anchor='w')
        
        # Загружаем структуру архива
        self._load_archive_structure(tree)
        
        def select_all():
            for item in tree.get_children():
                tree.selection_add(item)
        
        def deselect_all():
            tree.selection_remove(tree.get_children())
        
        def on_select():
            selected = tree.selection()
            if not selected:
                messagebox.showerror("Ошибка", "Не выбрано ни одного элемента!")
                return
            
            self.selected_items = [tree.item(item)['values'][0] for item in selected]
            root.destroy()
        
        # Кнопки выбора
        select_frame = tk.Frame(root, bg="white")
        select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(select_frame, text="✅ Выбрать всё", 
                  command=select_all, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text="❌ Снять всё",
                  command=deselect_all, width=15).pack(side=tk.LEFT, padx=5)
        
        # Кнопки действий
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="✅ Выбрать выделенные", command=on_select, width=25).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Отмена", command=root.destroy, width=25).pack(side=tk.LEFT, padx=5)
        
        root.mainloop()
        return self.selected_items
    
    def _load_archive_structure(self, tree):
        """Загружает структуру архива в дерево"""
        try:
            with zipfile.ZipFile(self.archive_path, 'r') as zf:
                # Фильтруем только нужные файлы
                valid_extensions = ('.txt', '.json', '.yml', '.xml')
                
                items = []
                for info in zf.infolist():
                    if info.is_dir():
                        # Проверяем, есть ли в этой папке нужные файлы
                        has_valid_files = any(
                            f.filename.startswith(info.filename) and 
                            f.filename.endswith(valid_extensions)
                            for f in zf.infolist()
                        )
                        if has_valid_files:
                            items.append({
                                'path': info.filename.rstrip('/'),
                                'type': '📁 Папка',
                                'size': '',
                                'is_dir': True
                            })
                    elif info.filename.endswith(valid_extensions):
                        items.append({
                            'path': info.filename,
                            'type': '📄 Файл',
                            'size': self._format_size(info.file_size),
                            'is_dir': False
                        })
                
                # Добавляем в дерево
                for item in sorted(items, key=lambda x: (not x['is_dir'], x['path'])):
                    tree.insert('', 'end', 
                               text=os.path.basename(item['path']) or item['path'],
                               values=[item['path'], item['type'], item['size']])
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть архив: {e}")
    
    def _add_to_tree(self, tree, parent, structure, file_info, current_path=''):
        """Рекурсивно добавляет элементы в дерево"""
        # Эта функция больше не используется
        pass
    
    def _format_size(self, size):
        """Форматирует размер файла"""
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"
    
    def extract_selected(self):
        """Извлекает выбранные файлы во временную папку"""
        self.temp_dir = tempfile.mkdtemp(prefix='game_extract_')
        
        try:
            with zipfile.ZipFile(self.archive_path, 'r') as zf:
                for item in self.selected_items:
                    # Извлекаем файл или всю папку
                    for file_name in zf.namelist():
                        if file_name.startswith(item):
                            zf.extract(file_name, self.temp_dir)
        except Exception as e:
            print(f"⚠️ Ошибка при извлечении: {e}")
            return None
        
        return self.temp_dir
    
    def cleanup(self):
        """Удаляет временную папку"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass

# ===================================================================
# ФУНКЦИИ ИЗВЛЕЧЕНИЯ ТЕКСТА (УЛУЧШЕННЫЕ)
# ===================================================================

def extract_english_parts(text):
    """
    УЛУЧШЕННАЯ версия: извлекает только английский текст,
    сохраняя маркеры %r% и другие служебные символы
    """
    # Убираем маркеры временно для анализа
    temp_text = re.sub(r'%\w+%', '', text)
    
    # Ищем английские слова (минимум 2 буквы)
    english_words = re.findall(r'\b[A-Za-z]{2,}\b', temp_text)
    
    if english_words:
        # Возвращаем оригинальный текст, если в нём есть английские слова
        return text.strip()
    
    return None

def extract_english_text_from_file(file_path):
    """
    УЛУЧШЕННАЯ версия извлечения английского текста
    Сохраняет оригинальный формат с %r% для правильного перевода
    """
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
            # Находим весь текст в кавычках
            pattern = r'"([^"]*)"'
            matches = re.findall(pattern, content)
            
            for text in matches:
                # Проверяем, есть ли английский текст
                if re.search(r'\b[A-Za-z]{2,}\b', text):
                    # Добавляем оригинальный текст (с %r% если они есть)
                    results.append(text)
    except Exception as e:
        print(f"⚠️ Ошибка при чтении {file_path}: {e}")
    
    return results

def search_folder(folder_path, base_path=None, extract_archives=False):
    """
    УЛУЧШЕННАЯ версия: Рекурсивно сканирует все вложенные папки
    и извлекает английский текст из всех файлов
    """
    all_results = []
    unique_texts = set()
    temp_dirs = []
    
    if base_path is None:
        base_path = folder_path
    
    archive_extensions = ('.zip', '.tar', '.tar.gz', '.tgz')
    valid_extensions = ('.txt', '.json', '.yml', '.xml')
    
    print(f"🔍 Сканирование: {folder_path}")
    
    # Рекурсивно обходим ВСЕ папки и подпапки
    for root, dirs, files in os.walk(folder_path):
        # Показываем текущую папку
        rel_folder = os.path.relpath(root, folder_path)
        if rel_folder != '.':
            print(f"   📁 {rel_folder}")
        
        for file in files:
            full_path = os.path.join(root, file)
            
            # Обработка архивов (если включено)
            if extract_archives and file.endswith(archive_extensions):
                print(f"      📦 Распаковка архива: {file}")
                temp_dir = tempfile.mkdtemp(prefix='archive_scan_')
                temp_dirs.append(temp_dir)
                
                try:
                    if file.endswith('.zip'):
                        with zipfile.ZipFile(full_path, 'r') as zf:
                            zf.extractall(temp_dir)
                        
                        # Рекурсивно сканируем содержимое
                        sub_results, sub_texts, _ = search_folder(temp_dir, base_path, extract_archives=False)
                        all_results.extend(sub_results)
                        unique_texts.update(sub_texts)
                        print(f"         ✅ Найдено текстов: {len(sub_texts)}")
                except Exception as e:
                    print(f"         ⚠️ Ошибка: {e}")
            
            # Обработка текстовых файлов
            elif file.endswith(valid_extensions):
                relative_path = os.path.relpath(full_path, base_path)
                texts = extract_english_text_from_file(full_path)
                
                if texts:
                    all_results.append((relative_path, full_path, texts))
                    unique_texts.update(texts)
                    print(f"      📄 {file}: {len(texts)} текстов")
    
    # Очистка временных папок
    for temp_dir in temp_dirs:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    return all_results, unique_texts, {}

def load_existing_translations(file_path):
    """
    Загружает уже существующие переводы
    С поддержкой экранирования специальных символов
    """
    translations = {}
    
    if not file_path or not os.path.exists(file_path):
        return translations
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Пропускаем комментарии и пустые строки
                if not line or line.startswith('#'):
                    continue
                
                # Ищем первый неэкранированный знак =
                if '=' in line:
                    parts = line.split('=', 1)
                    
                    if len(parts) == 2:
                        original = parts[0].strip()
                        translated = parts[1].strip()
                        
                        # Убираем экранирование
                        original = original.replace('\\=', '=')
                        translated = translated.replace('\\=', '=')
                        
                        if original and translated:
                            translations[original] = translated
    except Exception as e:
        print(f"⚠️ Ошибка при загрузке переводов из {file_path}: {e}")
    
    return translations

def save_translations(file_path, translations):
    """
    Сохраняет переводы с экранированием специальных символов
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True) if os.path.dirname(file_path) else None
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Переводы игры (Game Text Scanner v2.0)\n")
            f.write(f"# Всего фраз: {len(translations)}\n")
            f.write(f"# Формат: оригинал = перевод\n\n")
            
            for eng, rus in sorted(translations.items()):
                # Экранируем символы = в тексте
                eng_escaped = eng.replace('=', '\\=')
                rus_escaped = rus.replace('=', '\\=')
                
                f.write(f"{eng_escaped} = {rus_escaped}\n")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def apply_translations_to_file(original_file, translations, output_file):
    """
    УЛУЧШЕННАЯ версия применения переводов с точным сохранением структуры
    
    Заменяет ТОЛЬКО текст внутри кавычек, сохраняя всё остальное
    """
    try:
        # Читаем оригинальный файл
        with open(original_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Ошибка чтения файла {original_file}: {e}")
        return False, 0
    
    if not content.strip():
        # Пустой файл - просто копируем
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True) if os.path.dirname(output_file) else None
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, 0
        except:
            return False, 0
    
    # Паттерн для поиска текста в кавычках
    pattern = r'"([^"]*)"'
    
    replaced_count = 0
    result = content
    
    # Находим все совпадения
    matches = list(re.finditer(pattern, content))
    
    # Обрабатываем с конца, чтобы не сбивать позиции
    for match in reversed(matches):
        original_text = match.group(1)  # Текст без кавычек
        
        # Пропускаем пустые строки
        if not original_text.strip():
            continue
        
        translated_text = None
        
        # 1. Пробуем точное совпадение
        if original_text in translations:
            translated_text = translations[original_text]
        
        # 2. Пробуем совпадение без маркеров %r%
        elif original_text.replace('%r%', '').replace('%R%', '').strip() in translations:
            clean_text = original_text.replace('%r%', '').replace('%R%', '').strip()
            translated_text = translations[clean_text]
        
        # 3. Извлекаем только английский текст и ищем перевод
        else:
            english_part = extract_english_parts(original_text)
            if english_part:
                clean_english = english_part.replace('%r%', '').replace('%R%', '').strip()
                
                if clean_english in translations:
                    translated_text = translations[clean_english]
                elif english_part in translations:
                    translated_text = translations[english_part]
        
        # Если нашли перевод - заменяем
        if translated_text:
            start_pos = match.start(1)  # Начало текста (после открывающей кавычки)
            end_pos = match.end(1)      # Конец текста (перед закрывающей кавычкой)
            
            # Заменяем только содержимое между кавычками
            result = result[:start_pos] + translated_text + result[end_pos:]
            replaced_count += 1
    
    # Сохраняем результат
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True) if os.path.dirname(output_file) else None
        
        with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(result)
        
        return True, replaced_count
    except Exception as e:
        print(f"❌ Ошибка записи файла {output_file}: {e}")
        return False, 0

def create_translation_structure(results, output_folder, translation_dict):
    """
    УЛУЧШЕННАЯ версия: Создаёт полную структуру папок с переведёнными файлами
    Сохраняет всю иерархию папок из оригинала
    """
    processed_files = 0
    total_replaced = 0
    errors = []
    
    print("\n" + "="*60)
    print("🔄 Создание структуры переведённых файлов...")
    print("="*60)
    
    for relative_path, original_path, texts in results:
        output_path = os.path.join(output_folder, relative_path)
        
        # Создаём все вложенные папки
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Применяем переводы
        success, count = apply_translations_to_file(
            original_path,
            translation_dict,
            output_path
        )
        
        if success:
            processed_files += 1
            total_replaced += count
            
            if count > 0:
                print(f"✅ {relative_path}: {count} фраз переведено")
            else:
                # Копируем файл как есть, если в нём нет переводимых фраз
                print(f"⚪ {relative_path}: скопирован без изменений")
        else:
            errors.append(relative_path)
            print(f"❌ {relative_path}: ошибка обработки")
    
    print("\n" + "="*60)
    print(f"📊 Статистика:")
    print(f"   ✅ Обработано файлов: {processed_files}")
    print(f"   🔄 Применено переводов: {total_replaced}")
    if errors:
        print(f"   ❌ Ошибок: {len(errors)}")
    print("="*60)
    
    return processed_files, total_replaced

# ===================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ===================================================================

def main():
    root = tk.Tk()
    root.withdraw()
    
    print("="*60)
    print("🌐 Game Text Scanner v2.0")
    print("="*60)
    
    # Выбор источника: папка или архив
    choice = messagebox.askyesno("Выбор источника", 
                                  "Выбрать архив?\n\nДа - архив\nНет - папку")
    
    source_path = None
    temp_dir = None
    archive_selector = None
    extract_archives = False
    
    if choice:  # Архив
        archive_path = filedialog.askopenfilename(
            title="Выберите архив",
            filetypes=[("Архивы", "*.zip *.tar *.tar.gz *.tgz"), ("Все файлы", "*.*")]
        )
        if not archive_path:
            print("❌ Архив не выбран. Выход.")
            return
        
        # Спрашиваем, хочет ли пользователь выбрать конкретные файлы
        use_browser = messagebox.askyesno(
            "Выбор файлов",
            "Хотите выбрать конкретные файлы/папки внутри архива?\n\n"
            "ДА - Открыть содержимое архива для выбора\n"
            "НЕТ - Обработать весь архив целиком"
        )
        
        if use_browser:
            # Показываем браузер архива
            archive_selector = ArchiveSelector(archive_path)
            selected_items = archive_selector.show_selector()
            
            if not selected_items:
                print("❌ Файлы не выбраны. Выход.")
                return
            
            source_path = archive_selector.extract_selected()
            if not source_path:
                print("❌ Ошибка извлечения. Выход.")
                return
            
            print(f"✅ Выбрано элементов: {len(selected_items)}")
        else:
            # Распаковываем весь архив
            temp_dir = tempfile.mkdtemp(prefix='full_archive_')
            try:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extractall(temp_dir)
                source_path = temp_dir
                print(f"✅ Архив распакован: {os.path.basename(archive_path)}")
            except Exception as e:
                print(f"❌ Ошибка распаковки архива: {e}")
                return
    else:  # Папка
        source_path = filedialog.askdirectory(title="Выберите папку с файлами игры")
        if not source_path:
            print("❌ Папка не выбрана. Выход.")
            return
        
        # Спрашиваем про вложенные архивы
        extract_archives = messagebox.askyesno(
            "Вложенные архивы",
            "Автоматически распаковывать вложенные архивы?\n\n"
            "ДА - Искать и обрабатывать архивы внутри папки\n"
            "НЕТ - Игнорировать архивы"
        )
        
        print(f"✅ Выбрана папка: {os.path.basename(source_path)}")
    
    # Загружаем существующие переводы
    print("\n" + "="*60)
    load_existing = messagebox.askyesno(
        "Существующие переводы",
        "Загрузить уже существующие переводы?\n\n"
        "Это позволит не переводить уже готовые фразы повторно."
    )
    
    existing_translations = {}
    if load_existing:
        translation_file = filedialog.askopenfilename(
            title="Выберите файл с переводами (формат: оригинал = перевод)"
        )
        if translation_file:
            existing_translations = load_existing_translations(translation_file)
            print(f"✅ Загружено существующих переводов: {len(existing_translations)}")
    
    # Сканируем файлы
    print("\n" + "="*60)
    print("🔍 Сканирование файлов...")
    print("="*60)
    
    results, unique_texts, _ = search_folder(source_path, extract_archives=extract_archives)
    
    print("\n" + "="*60)
    
    if not results:
        messagebox.showwarning("Внимание", 
                             "Не найдено файлов с английским текстом!\n\n"
                             "Поддерживаемые форматы: .txt, .json, .yml, .xml")
        print("❌ Файлы не найдены!")
        return
    
    # Фильтруем уже переведённые
    unique_texts_to_translate = unique_texts - set(existing_translations.keys())
    
    print(f"📊 Результаты сканирования:")
    print(f"   📄 Найдено файлов: {len(results)}")
    print(f"   📝 Уникальных текстов: {len(unique_texts)}")
    print(f"   ✅ Уже переведено: {len(unique_texts) - len(unique_texts_to_translate)}")
    print(f"   🆕 Требует перевода: {len(unique_texts_to_translate)}")
    print("="*60)
    
    # Сохраняем результаты
    print("\n" + "="*60)
    save_path = filedialog.asksaveasfilename(
        title="Куда сохранить результаты с путями",
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt")],
        initialfile="game_texts_with_paths.txt"
    )
    
    unique_path = filedialog.asksaveasfilename(
        title="Куда сохранить уникальные строки для перевода",
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt")],
        initialfile="unique_texts_to_translate.txt"
    )
    
    if save_path:
        print(f"\n💾 Сохранение результатов...")
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write("# Игровые тексты с путями к файлам\n")
            f.write(f"# Всего файлов: {len(results)}\n")
            f.write(f"# Уникальных текстов: {len(unique_texts_to_translate)}\n")
            f.write(f"# Дата: {Path(save_path).stat().st_mtime if os.path.exists(save_path) else 'новый'}\n\n")
            
            for relative_path, full_path, texts in results:
                filtered_texts = [t for t in texts if t in unique_texts_to_translate]
                if filtered_texts:
                    f.write(f"{'='*60}\n")
                    f.write(f"Файл: {relative_path}\n")
                    f.write(f"{'='*60}\n")
                    for i, text in enumerate(filtered_texts, 1):
                        f.write(f"{i}. {text}\n")
                    f.write("\n")
        print(f"✅ Результаты с путями сохранены: {os.path.basename(save_path)}")
    
    if unique_path:
        print(f"💾 Сохранение уникальных строк...")
        with open(unique_path, 'w', encoding='utf-8') as f:
            f.write("# Уникальные тексты для перевода\n")
            f.write(f"# Всего: {len(unique_texts_to_translate)}\n")
            f.write("# Формат: одна строка = один текст для перевода\n\n")
            
            for i, text in enumerate(sorted(unique_texts_to_translate), 1):
                f.write(f"{text}\n")
        print(f"✅ Уникальные строки сохранены: {os.path.basename(unique_path)}")
    
    print(f"\n📊 Найдено уникальных строк для перевода: {len(unique_texts_to_translate)}")
    
    # Опционально: создание переведённой структуры
    if messagebox.askyesno("Создать переводы?", 
                          "Хотите создать структуру папок с переведёнными файлами?\n\n"
                          "(Нужен файл с переводами в формате: оригинал = перевод)"):
        translation_file = filedialog.askopenfilename(
            title="Выберите файл с переводами (формат: оригинал = перевод)"
        )
        
        if translation_file:
            translation_dict = load_existing_translations(translation_file)
            
            if not translation_dict:
                messagebox.showerror("Ошибка", "Файл с переводами пуст или имеет неверный формат!")
            else:
                output_folder = filedialog.askdirectory(title="Выберите папку для сохранения переведённых файлов")
                if output_folder:
                    print("\n" + "="*60)
                    print("🔄 Применение переводов к файлам...")
                    print(f"📂 Исходная структура: {len(results)} файлов")
                    print(f"📝 Доступно переводов: {len(translation_dict)}")
                    print("="*60)
                    
                    processed, replaced = create_translation_structure(results, output_folder, translation_dict)
                    
                    messagebox.showinfo("Готово!", 
                                       f"✅ Переведённые файлы созданы!\n\n"
                                       f"📁 Папка: {os.path.basename(output_folder)}\n"
                                       f"📄 Обработано файлов: {processed}\n"
                                       f"🔄 Применено переводов: {replaced}\n\n"
                                       f"Структура папок полностью сохранена!")
    
    # Очистка временных файлов
    if archive_selector:
        archive_selector.cleanup()
    
    if temp_dir and os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    print("\n" + "="*60)
    print("✅ Работа завершена!")
    print("="*60)

if __name__ == "__main__":
    main()