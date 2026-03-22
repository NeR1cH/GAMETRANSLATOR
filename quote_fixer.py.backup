#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Автоматическое исправление проблем с кавычками в Python-коде
=============================================================

Этот скрипт:
1. Находит строки с нечётным количеством кавычек
2. Автоматически исправляет типичные ошибки
3. Создаёт резервную копию оригинального файла
4. Генерирует отчёт об исправлениях

Автор: Claude
Версия: 1.0
"""

import re
import os
import shutil
from datetime import datetime

class QuoteFixer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.backup_path = None
        self.fixes = []
        self.lines = []
        
    def create_backup(self):
        """Создаёт резервную копию файла"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = f"{self.file_path}.backup_{timestamp}"
        shutil.copy2(self.file_path, self.backup_path)
        print(f"✅ Резервная копия: {self.backup_path}")
        
    def load_file(self):
        """Загружает файл"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.lines = f.readlines()
        print(f"📄 Загружено строк: {len(self.lines)}")
        
    def count_quotes(self, text):
        """Подсчитывает кавычки, игнорируя экранированные"""
        # Убираем экранированные символы
        clean = re.sub(r'\\["\']', '', text)
        
        # Убираем строковые литералы r"..." и r'...'
        clean = re.sub(r'r"[^"]*"', '', clean)
        clean = re.sub(r"r'[^']*'", '', clean)
        
        single = clean.count("'")
        double = clean.count('"')
        
        return single, double
    
    def fix_regex_patterns(self, line, line_num):
        """Исправляет паттерны регулярных выражений"""
        # Паттерн: pattern = r'"([^"]*)"'
        if 'pattern' in line and '= r' in line:
            # Исправляем на одинарные кавычки снаружи
            fixed = re.sub(
                r'pattern\s*=\s*r"([^"]*)"',
                r"pattern = r'\1'",
                line
            )
            if fixed != line:
                self.fixes.append({
                    'line': line_num,
                    'type': 'regex_pattern',
                    'before': line.strip(),
                    'after': fixed.strip()
                })
                return fixed
        return line
    
    def fix_findall_patterns(self, line, line_num):
        """Исправляет паттерны в re.findall"""
        # Паттерн: re.findall(r'"([^"]*)"', content)
        if 're.findall' in line or 're.match' in line or 're.search' in line:
            # Меняем внешние кавычки на одинарные
            fixed = re.sub(
                r'(re\.\w+)\(r"([^"]*)"',
                r"\1(r'\2'",
                line
            )
            if fixed != line:
                self.fixes.append({
                    'line': line_num,
                    'type': 'regex_findall',
                    'before': line.strip(),
                    'after': fixed.strip()
                })
                return fixed
        return line
    
    def fix_strip_quotes(self, line, line_num):
        """Исправляет strip с кавычками"""
        # line_stripped.strip('"\'')
        if '.strip(' in line and '"' in line and "'" in line:
            # Используем тройные кавычки или экранирование
            fixed = re.sub(
                r'\.strip\(["\'](["\'])["\']?\)',
                r'''.strip('"\\'')''',
                line
            )
            if fixed != line:
                self.fixes.append({
                    'line': line_num,
                    'type': 'strip_method',
                    'before': line.strip(),
                    'after': fixed.strip()
                })
                return fixed
        return line
    
    def fix_docstrings(self, line_num):
        """Проверяет и исправляет docstring"""
        line = self.lines[line_num]
        
        # Ищем открывающий """
        if '"""' in line and line.strip() == '"""':
            # Ищем закрывающий """
            found_closing = False
            for i in range(line_num + 1, min(line_num + 100, len(self.lines))):
                if '"""' in self.lines[i]:
                    found_closing = True
                    break
            
            if not found_closing:
                # Добавляем закрывающий """
                # Находим следующую пустую строку или конец функции
                insert_pos = line_num + 1
                for i in range(line_num + 1, min(line_num + 50, len(self.lines))):
                    if self.lines[i].strip() == '' or not self.lines[i].startswith('    '):
                        insert_pos = i
                        break
                
                self.lines.insert(insert_pos, '    """\n')
                self.fixes.append({
                    'line': line_num,
                    'type': 'docstring_close',
                    'before': 'Незакрытый docstring',
                    'after': f'Добавлен закрывающий """ на строке {insert_pos}'
                })
                return True
        
        return False
    
    def fix_fstring_multiline(self, line_num):
        """Исправляет многострочные f-строки"""
        line = self.lines[line_num]
        
        # Ищем открывающий f""" или """
        if ('f"""' in line or 'text = """' in line or 'stats = """' in line) and line.strip().endswith('"""'):
            # Ищем закрывающий """
            found_closing = False
            for i in range(line_num + 1, min(line_num + 200, len(self.lines))):
                test_line = self.lines[i].strip()
                if test_line == '"""' or test_line.endswith('"""'):
                    found_closing = True
                    break
            
            if not found_closing:
                # Ищем следующую строку с кодом (не пустую и не комментарий)
                insert_pos = line_num + 1
                for i in range(line_num + 1, min(line_num + 100, len(self.lines))):
                    test_line = self.lines[i].strip()
                    if test_line and not test_line.startswith('#') and '"""' not in test_line:
                        # Проверяем уровень отступа
                        indent = len(self.lines[i]) - len(self.lines[i].lstrip())
                        if indent <= len(line) - len(line.lstrip()):
                            insert_pos = i
                            break
                
                # Добавляем закрывающий """
                indent = ' ' * (len(line) - len(line.lstrip()))
                self.lines.insert(insert_pos, f'{indent}"""\n')
                self.fixes.append({
                    'line': line_num,
                    'type': 'multiline_fstring',
                    'before': 'Незакрытая многострочная строка',
                    'after': f'Добавлен закрывающий """ на строке {insert_pos}'
                })
                return True
        
        return False
    
    def analyze_and_fix(self):
        """Анализирует и исправляет проблемы"""
        print("\n🔍 Анализ и исправление...\n")
        
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            line_num = i + 1
            
            # Пропускаем комментарии и пустые строки
            if line.strip().startswith('#') or not line.strip():
                i += 1
                continue
            
            # Исправляем docstring
            if self.fix_docstrings(i):
                continue
            
            # Исправляем многострочные строки
            if self.fix_fstring_multiline(i):
                continue
            
            # Исправляем обычные строки
            original = line
            line = self.fix_regex_patterns(line, line_num)
            line = self.fix_findall_patterns(line, line_num)
            line = self.fix_strip_quotes(line, line_num)
            
            if line != original:
                self.lines[i] = line
            
            i += 1
        
        print(f"✅ Найдено и исправлено ошибок: {len(self.fixes)}")
    
    def save_fixed_file(self):
        """Сохраняет исправленный файл"""
        output_path = self.file_path.replace('.py', '_fixed.py')
        with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
            f.writelines(self.lines)
        print(f"💾 Исправленный файл: {output_path}")
        return output_path
    
    def generate_report(self):
        """Генерирует отчёт об исправлениях"""
        report_path = self.file_path.replace('.py', '_fix_report.txt')
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("ОТЧЁТ ОБ ИСПРАВЛЕНИИ КАВЫЧЕК\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Файл: {self.file_path}\n")
            f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Всего исправлений: {len(self.fixes)}\n\n")
            f.write("=" * 70 + "\n\n")
            
            if not self.fixes:
                f.write("✅ Проблем с кавычками не найдено!\n")
            else:
                for i, fix in enumerate(self.fixes, 1):
                    f.write(f"ИСПРАВЛЕНИЕ #{i}\n")
                    f.write(f"Строка: {fix['line']}\n")
                    f.write(f"Тип: {fix['type']}\n")
                    f.write(f"До:  {fix['before']}\n")
                    f.write(f"После: {fix['after']}\n")
                    f.write("-" * 70 + "\n\n")
        
        print(f"📋 Отчёт сохранён: {report_path}")
        return report_path
    
    def verify_syntax(self, file_path):
        """Проверяет синтаксис исправленного файла"""
        print("\n🧪 Проверка синтаксиса...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            compile(code, file_path, 'exec')
            print("✅ Синтаксис корректен!")
            return True
        except SyntaxError as e:
            print(f"❌ Ошибка синтаксиса на строке {e.lineno}:")
            print(f"   {e.msg}")
            print(f"   {e.text}")
            return False
    
    def run(self):
        """Запускает весь процесс исправления"""
        print("\n" + "=" * 70)
        print("🔧 АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ КАВЫЧЕК В PYTHON-КОДЕ")
        print("=" * 70 + "\n")
        
        # Шаг 1: Резервная копия
        self.create_backup()
        
        # Шаг 2: Загрузка файла
        self.load_file()
        
        # Шаг 3: Анализ и исправление
        self.analyze_and_fix()
        
        # Шаг 4: Сохранение
        fixed_path = self.save_fixed_file()
        
        # Шаг 5: Отчёт
        report_path = self.generate_report()
        
        # Шаг 6: Проверка синтаксиса
        self.verify_syntax(fixed_path)
        
        print("\n" + "=" * 70)
        print("✅ ПРОЦЕСС ЗАВЕРШЁН")
        print("=" * 70)
        print(f"\n📁 Файлы:")
        print(f"   Оригинал (резервная копия): {self.backup_path}")
        print(f"   Исправленный: {fixed_path}")
        print(f"   Отчёт: {report_path}")
        print("\n💡 Рекомендация: Проверьте исправленный файл перед использованием!")


def main():
    """Главная функция"""
    import sys
    
    if len(sys.argv) < 2:
        print("❌ Использование: python quote_fixer.py <путь_к_файлу.py>")
        print("\nПример:")
        print("   python quote_fixer.py my_script.py")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        sys.exit(1)
    
    if not file_path.endswith('.py'):
        print("⚠️ Внимание: Файл не имеет расширения .py")
        response = input("Продолжить? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    fixer = QuoteFixer(file_path)
    fixer.run()


if __name__ == "__main__":
    main()