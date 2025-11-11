#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для поиска незакрытых строковых литералов
"""

import re

def find_unterminated_strings(filepath):
    """Находит строки с незакрытыми кавычками"""
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ Не удалось открыть файл: {e}")
        return
    
    print("🔍 ПОИСК НЕЗАКРЫТЫХ СТРОКОВЫХ ЛИТЕРАЛОВ\n")
    print("="*70)
    
    issues_found = False
    
    for line_num, line in enumerate(lines, 1):
        # Пропускаем комментарии
        if line.strip().startswith('#'):
            continue
        
        # Убираем строковые литералы в тройных кавычках (они могут быть многострочными)
        temp_line = re.sub(r'""".*?"""', '""', line, flags=re.DOTALL)
        temp_line = re.sub(r"'''.*?'''", "''", temp_line, flags=re.DOTALL)
        
        # Подсчитываем одинарные кавычки (не экранированные)
        single_quotes = len(re.findall(r"(?<!\\)'", temp_line))
        
        # Подсчитываем двойные кавычки (не экранированные)
        double_quotes = len(re.findall(r'(?<!\\)"', temp_line))
        
        # Проверяем четность
        if single_quotes % 2 != 0 or double_quotes % 2 != 0:
            issues_found = True
            print(f"\n❌ СТРОКА {line_num}:")
            print(f"   Одинарных кавычек: {single_quotes} {'(нечетное!)' if single_quotes % 2 != 0 else ''}")
            print(f"   Двойных кавычек: {double_quotes} {'(нечетное!)' if double_quotes % 2 != 0 else ''}")
            print(f"   Код: {line.rstrip()}")
            
            # Подсказка где именно проблема
            if single_quotes % 2 != 0:
                positions = [m.start() for m in re.finditer(r"(?<!\\)'", temp_line)]
                print(f"   Позиции ': {positions}")
            
            if double_quotes % 2 != 0:
                positions = [m.start() for m in re.finditer(r'(?<!\\)"', temp_line)]
                print(f"   Позиции \": {positions}")
    
    print("\n" + "="*70)
    
    if not issues_found:
        print("✅ Незакрытых строк не найдено!")
    else:
        print("⚠️  Найдены проблемные строки. Проверьте их вручную.")
    
    # ДОПОЛНИТЕЛЬНО: Проверяем строку 154 отдельно
    if len(lines) >= 154:
        print(f"\n🔍 СТРОКА 154 (из ошибки):")
        print(f"   {lines[153].rstrip()}")  # Индекс 153 = строка 154
        
        # Показываем контекст (5 строк до и после)
        print(f"\n📋 КОНТЕКСТ (строки 149-159):")
        for i in range(max(0, 148), min(len(lines), 159)):
            marker = ">>> " if i == 153 else "    "
            print(f"{marker}{i+1:3d}: {lines[i].rstrip()}")


# ========== БЫСТРАЯ ПРОВЕРКА КОНКРЕТНЫХ ПАТТЕРНОВ ==========

def check_common_issues():
    """Проверяет типичные проблемы в вашем коде"""
    
    print("\n\n🔧 ТИПИЧНЫЕ ПРОБЛЕМЫ В ВАШЕМ КОДЕ:\n")
    
    issues = {
        "Регулярные выражения": [
            r'r"^[A-ZА-ЯЁ0-9_]+\s*:\s*$"',  # ← Правильно
            r'r"^[A-ZА-ЯЁ0-9_]+\s*:\s*',     # ← Неправильно (нет $")
            r're.match(r"^[A-ZА-ЯЁ0-9_]+',   # ← Неправильно
        ],
        
        "Строки с кириллицей": [
            r'"Проверяем формат "КЛЮЧ:"',    # ← Неправильно (кавычка внутри)
            r'"Проверяем формат \"КЛЮЧ:\""', # ← Правильно (экранирование)
            r"'Проверяем формат \"КЛЮЧ:\"'", # ← Правильно (другие кавычки)
        ],
        
        "Паттерны для поиска": [
            r'pattern = r\'"([^"]*)"\'',     # ← Правильно
            r'pattern = r"([^"]*)"',         # ← Неправильно (конфликт кавычек)
        ]
    }
    
    for category, examples in issues.items():
        print(f"\n{category}:")
        for example in examples:
            status = "✅" if example.count('"') % 2 == 0 and example.count("'") % 2 == 0 else "❌"
            print(f"  {status} {example}")


# ========== АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ ==========

def suggest_fixes(line):
    """Предлагает варианты исправления"""
    
    fixes = []
    
    # Проверяем регулярные выражения
    if 're.match(' in line or 're.search(' in line:
        if line.count('"') % 2 != 0:
            # Пробуем найти незакрытую строку
            match = re.search(r're\.(match|search)\(r"([^"]*?)$', line)
            if match:
                fixes.append(f"Добавьте \" в конец: {line.rstrip()}\"")
    
    # Проверяем обычные строки
    if line.count('"') % 2 != 0 and 'r"' not in line:
        fixes.append("Экранируйте внутренние кавычки: \\\"")
        fixes.append("Или используйте одинарные кавычки: '...'")
    
    return fixes


# ========== ЗАПУСК ==========

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        find_unterminated_strings(filepath)
    else:
        print("Использование: python check_strings.py <C:\VSCODE PROJECTS\GAMETRANSLATE\GAMETRANSLATOR.PY>")
        print("\nИли проверьте типичные проблемы:")
        check_common_issues()