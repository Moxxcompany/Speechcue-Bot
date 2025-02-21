import ast
import json


def extract_dictionary(file_path, key):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    parsed_content = ast.parse(content)
    for node in parsed_content.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Str):
            if node.targets[0].id == key:
                return node.value.s
    print(f"Key '{key}' not found in {file_path}")
    return None


def extract_all_keys(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    parsed_content = ast.parse(content)
    keys = []
    for node in parsed_content.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Str):
            keys.append(node.targets[0].id)
    return keys


# File paths for your language files
english_file_path = "English.py"
french_file_path = "French.py"
chinese_file_path = "Chinese.py"
hindi_file_path = "Hindi.py"

english_keys = extract_all_keys(english_file_path)
french_keys = extract_all_keys(french_file_path)
chinese_keys = extract_all_keys(chinese_file_path)
hindi_keys = extract_all_keys(hindi_file_path)

merged_all_keys_dict = {}

all_keys = set(english_keys + french_keys + chinese_keys + hindi_keys)

for key in all_keys:
    merged_all_keys_dict[key] = {
        "English": extract_dictionary(english_file_path, key),
        "Chinese": extract_dictionary(chinese_file_path, key),
        "French": extract_dictionary(french_file_path, key),
        "Hindi": extract_dictionary(hindi_file_path, key),
    }

output_all_keys_file_path = "translations.py"

with open(output_all_keys_file_path, "w", encoding="utf-8") as output_file:
    output_file.write("# Merged dictionary of all translations\n")
    for key, translations in merged_all_keys_dict.items():
        output_file.write(
            f"{key} = {json.dumps(translations, indent=4, ensure_ascii=False)}\n"
        )

print(f"Merged dictionary saved to: {output_all_keys_file_path}")
