#!/usr/bin/env python3
r"""
Convert Vietnamese .properties files from raw UTF-8 to Unicode escape sequences.
Java properties files default to ISO-8859-1 encoding, so non-ASCII characters
need to be escaped as \uXXXX.
"""

import os
import re

def convert_properties_file(file_path):
    """Convert a properties file from raw UTF-8 to Unicode escape sequences."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if already converted - look for \u escape sequences in the raw content
    # If the file contains raw Vietnamese chars like đ, ạ, ô, it's not converted
    has_raw_vietnamese = any(ord(c) > 127 for c in content if c not in '\r\n\t ')

    if not has_raw_vietnamese:
        print(f"  Already converted: {file_path}")
        return False

    lines = content.split('\n')
    new_lines = []

    for line in lines:
        # Skip comments and empty lines
        stripped = line.strip()
        if stripped.startswith('#') or not stripped:
            new_lines.append(line)
            continue

        # Split key=value (only on first =)
        eq_idx = line.find('=')
        if eq_idx > 0:
            key_part = line[:eq_idx+1]
            value = line[eq_idx+1:]

            # Convert non-ASCII characters to Unicode escapes
            escaped_value = ''
            for char in value:
                if ord(char) > 127:
                    escaped_value += '\\u{:04x}'.format(ord(char))
                else:
                    escaped_value += char

            new_lines.append(key_part + escaped_value)
        else:
            new_lines.append(line)

    new_content = '\n'.join(new_lines)

    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  Converted: {file_path}")
    return True

def main():
    base_dir = r"C:\Users\huyho\IdeaProjects\fLMS\src\main\java"
    converted_count = 0

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file == "LocalStrings_vi.properties":
                file_path = os.path.join(root, file)
                if convert_properties_file(file_path):
                    converted_count += 1

    print(f"\nTotal converted: {converted_count} files")

if __name__ == "__main__":
    main()