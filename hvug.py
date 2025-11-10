#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Translation Merger v1.0 - Объединение переводов с исправлением синтаксиса
==========================================================================
Заменяет английский текст на русский, сохраняя правильный формат
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

# ===================================================================
# НАСТРОЙКИ
# ===================================================================

def get_input_path(prompt: str) -> str:
    """Получает путь от пользователя"""
    path = input(prompt).strip().strip('"').strip("'")
    return os.path.abspath(path)

print("="*60)
print("🔧 ПЕРЕВОД И ИСПРАВЛЕНИЕ ИГРОВЫХ ФАЙЛОВ")
print("="*60)

ORIGINAL_DIR = get_input_path("\n📂 Папка с оригиналами (английский): ")
TRANSLATION_DIR = get_input_path("🌐 Папка с переводами (русский): ")
OUTPUT_DIR = get_input_path("💾 Куда сохранить результат: ")

# Создаём выходную папку
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===================================================================
# ФУНКЦИИ ПАРСИНГА
# ===================================================================

def extract_translations(file_path: str) -> Dict[str, str]:
    """
    Извлекает переводы из файла
    Возвращает словарь: ключ -> значение
    """
    translations = {}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Ищем все пары ключ: значение
        # Поддерживает многострочные значения с %r%
        pattern = r'(\w+):\s*"([^"]*(?:%r%[^"]*)*)"'
        
        for match in re.finditer(pattern, content, re.DOTALL):
            key = match.group(1)
            value = match.group(2)
            translations[key] = value
        
        # Также ищем массивы
        array_pattern = r'(\w+):\s*\[(.*?)\]'
        for match in re.finditer(array_pattern, content, re.DOTALL):
            key = match.group(1)
            array_content = match.group(2)
            
            # Извлекаем элементы массива
            items = re.findall(r'"([^"]*)"', array_content)
            if items:
                translations[key] = items
        
    except Exception as e:
        print(f"⚠️ Ошибка чтения {file_path}: {e}")
    
    return translations


def merge_translations(original_path: str, translation_path: str, output_path: str) -> Tuple[bool, int]:
    """
    Объединяет оригинал с переводами
    Возвращает (успех, количество замен)
    """
    replacements = 0
    
    try:
        # Читаем оригинал
        with open(original_path, "r", encoding="utf-8") as f:
            original_content = f.read()
        
        # Читаем переводы
        translations = extract_translations(translation_path)
        
        if not translations:
            print(f"⚠️ Не найдено переводов в {os.path.basename(translation_path)}")
            return False, 0
        
        # Заменяем каждый ключ
        result = original_content
        
        for key, value in translations.items():
            if isinstance(value, list):
                # Это массив
                array_str = ',\n\t'.join([f'"{item}"' for item in value])
                pattern = rf'{key}:\s*\[.*?\]'
                replacement = f'{key}: [\n\t{array_str},\n]'
                
                if re.search(pattern, result, re.DOTALL):
                    result = re.sub(pattern, replacement, result, flags=re.DOTALL)
                    replacements += 1
            else:
                # Это строка
                # Ищем оригинальное значение и заменяем
                pattern = rf'{key}:\s*"[^"]*(?:%r%[^"]*)*"'
                
                if re.search(pattern, result, re.DOTALL):
                    # Сохраняем %r% если они есть в переводе
                    replacement = f'{key}: "{value}"'
                    result = re.sub(pattern, replacement, result, flags=re.DOTALL)
                    replacements += 1
        
        # Нормализуем формат
        result = normalize_format(result)
        
        # Создаём папку для результата
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Сохраняем
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(result)
        
        return True, replacements
    
    except Exception as e:
        print(f"❌ Ошибка обработки {os.path.basename(original_path)}: {e}")
        return False, 0


def normalize_format(content: str) -> str:
    """
    Нормализует форматирование файла
    """
    # Убираем лишние пробелы
    content = re.sub(r'[ \t]+\n', '\n', content)
    
    # Убираем множественные пустые строки
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Добавляем запятые после закрывающих скобок массивов (где нужно)
    content = re.sub(r'\n\](?!\,)(?=\n[A-Z])', '\n],', content)
    
    # Убираем пробелы перед запятыми
    content = re.sub(r'\s+,', ',', content)
    
    # Нормализуем отступы в массивах
    lines = content.split('\n')
    normalized = []
    in_array = False
    
    for line in lines:
        stripped = line.strip()
        
        if stripped.endswith('['):
            in_array = True
            normalized.append(line)
        elif stripped in [']', '],']:
            in_array = False
            normalized.append(stripped)
        elif in_array and stripped.startswith('"'):
            normalized.append(f'\t{stripped}')
        else:
            normalized.append(line)
    
    return '\n'.join(normalized)


# ===================================================================
# ОСНОВНАЯ ПРОГРАММА
# ===================================================================

def main():
    if not os.path.exists(ORIGINAL_DIR):
        print(f"❌ Папка не найдена: {ORIGINAL_DIR}")
        return
    
    if not os.path.exists(TRANSLATION_DIR):
        print(f"❌ Папка не найдена: {TRANSLATION_DIR}")
        return
    
    print(f"\n📂 Оригиналы: {ORIGINAL_DIR}")
    print(f"🌐 Переводы: {TRANSLATION_DIR}")
    print(f"💾 Результат: {OUTPUT_DIR}\n")
    
    total_files = 0
    processed_files = 0
    total_replacements = 0
    
    # Обрабатываем все файлы
    for root, _, files in os.walk(ORIGINAL_DIR):
        for name in files:
            if not name.lower().endswith(".txt"):
                continue
            
            original_path = os.path.join(root, name)
            rel_path = os.path.relpath(original_path, ORIGINAL_DIR)
            
            # Ищем соответствующий файл перевода
            translation_path = os.path.join(TRANSLATION_DIR, rel_path)
            
            if not os.path.exists(translation_path):
                print(f"⚠️ Перевод не найден: {rel_path}")
                continue
            
            output_path = os.path.join(OUTPUT_DIR, rel_path)
            
            total_files += 1
            
            success, replacements = merge_translations(original_path, translation_path, output_path)
            
            if success:
                processed_files += 1
                total_replacements += replacements
                
                if replacements > 0:
                    print(f"✅ {rel_path} ({replacements} замен)")
                else:
                    print(f"⚪ {rel_path} (без изменений)")
            else:
                print(f"❌ {rel_path}")
    
    # Итоги
    print("\n" + "="*60)
    print("📊 СТАТИСТИКА")
    print("="*60)
    print(f"Обработано файлов: {processed_files}/{total_files}")
    print(f"Всего замен: {total_replacements}")
    
    print(f"\n✅ Готово! Результат сохранён в:\n{OUTPUT_DIR}")
    print("\n💡 Теперь скопируйте исправленные файлы в папку игры:")
    print(f"   {OUTPUT_DIR} → [папка игры]/langs/ru/")
    
    input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("\nНажмите Enter для выхода...")