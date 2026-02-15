import glob
import json
import logging
import os
import re
import sys
from typing import Dict, Optional, Tuple

from manga_translator.utils.path_manager import get_original_txt_path, get_translated_txt_path

logger = logging.getLogger(__name__)


def parse_template(template_string: str):
    """Parse free-form template into prefix/item/separator/suffix sections."""
    lines = template_string.splitlines(True)
    item_line_indices = [i for i, line in enumerate(lines) if "<original>" in line]
    if not item_line_indices:
        raise ValueError("Template must contain at least one '<original>' placeholder.")

    first_item_line_index = item_line_indices[0]
    first_item_line = lines[first_item_line_index]

    original_placeholder = "<original>"
    original_start_index = first_item_line.find(original_placeholder)

    translated_placeholder = "<translated>"
    translated_end_index = first_item_line.find(translated_placeholder)
    if translated_end_index != -1:
        translated_end_index += len(translated_placeholder)
        item_template = first_item_line[original_start_index:translated_end_index]
    else:
        item_template = first_item_line[original_start_index:]

    leading_spaces = first_item_line[:original_start_index]
    prefix = "".join(lines[:first_item_line_index]) + leading_spaces

    if len(item_line_indices) > 1:
        second_item_line_index = item_line_indices[1]
        second_item_line = lines[second_item_line_index]

        separator_from_first_line = first_item_line[translated_end_index:]
        separator_between_lines = "".join(lines[first_item_line_index + 1 : second_item_line_index])

        second_original_start_index = second_item_line.find("<original>")
        separator_to_second_line = second_item_line[:second_original_start_index] if second_original_start_index > 0 else ""

        separator = separator_from_first_line + separator_between_lines + separator_to_second_line

        last_item_line_index = item_line_indices[-1]
        last_item_line = lines[last_item_line_index]
        last_translated_end_index = last_item_line.find(translated_placeholder)
        if last_translated_end_index != -1:
            last_translated_end_index += len(translated_placeholder)
            suffix_from_last_line = last_item_line[last_translated_end_index:]
        else:
            suffix_from_last_line = last_item_line
        suffix = suffix_from_last_line + "".join(lines[last_item_line_index + 1 :])
    else:
        separator = ""
        suffix_from_first_line = first_item_line[translated_end_index:]
        suffix = suffix_from_first_line + "".join(lines[first_item_line_index + 1 :])

    return prefix, item_template, separator, suffix


def generate_original_text(detailed_json_path: str, template_path: str = None, output_path: str = None) -> str:
    try:
        with open(detailed_json_path, "r", encoding="utf-8") as f:
            source_data = json.load(f)
    except Exception as exc:
        return f"Error reading JSON file: {exc}"

    image_data = next(iter(source_data.values()), None)
    if not image_data or "regions" not in image_data:
        return "Error: Could not find 'regions' list in source JSON."
    regions = image_data.get("regions", [])

    items = []
    for region in regions:
        original_text = region.get("text", "").replace("[BR]", "")
        translated_text = region.get("translation", "").replace("[BR]", "")
        if original_text.strip():
            items.append(
                {
                    "original": original_text,
                    "translated": translated_text if translated_text else original_text,
                }
            )

    if output_path is None:
        json_dir = os.path.dirname(detailed_json_path)
        json_basename = os.path.basename(detailed_json_path)
        if json_dir.endswith(os.path.join("manga_translator_work", "json")):
            work_dir = os.path.dirname(json_dir)
            image_dir = os.path.dirname(work_dir)
            image_name = json_basename.replace("_translations.json", "")
            for ext in [".jpg", ".png", ".jpeg", ".webp", ".avif"]:
                image_path = os.path.join(image_dir, image_name + ext)
                if os.path.exists(image_path):
                    output_path = get_original_txt_path(image_path)
                    break
            if output_path is None:
                output_path = os.path.splitext(detailed_json_path)[0] + "_original.txt"
        else:
            output_path = os.path.splitext(detailed_json_path)[0] + "_original.txt"

    try:
        if not items:
            output_content = ""
        elif template_path and os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                template_string = f.read()
            prefix, item_template, separator, suffix = parse_template(template_string)
            formatted_items = []
            for item in items:
                formatted_item = item_template.replace("<original>", item["original"])
                formatted_item = formatted_item.replace("<translated>", item["translated"])
                formatted_items.append(formatted_item)
            output_content = prefix + separator.join(formatted_items) + suffix
        else:
            output_content = "\n".join([item["original"] for item in items])

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_content)
        logger.info("Original text exported to: %s", output_path)
    except Exception as exc:
        return f"Error writing to output file: {exc}"

    return output_path


def generate_translated_text(detailed_json_path: str, template_path: str = None, output_path: str = None) -> str:
    try:
        with open(detailed_json_path, "r", encoding="utf-8") as f:
            source_data = json.load(f)
    except Exception as exc:
        return f"Error reading JSON file: {exc}"

    image_data = next(iter(source_data.values()), None)
    if not image_data or "regions" not in image_data:
        return "Error: Could not find 'regions' list in source JSON."
    regions = image_data.get("regions", [])

    items = []
    for region in regions:
        original_text = region.get("text", "").replace("[BR]", "")
        translated_text = region.get("translation", "").replace("[BR]", "")
        if original_text.strip():
            items.append({"original": original_text, "translated": translated_text})

    if output_path is None:
        json_dir = os.path.dirname(detailed_json_path)
        json_basename = os.path.basename(detailed_json_path)
        if json_dir.endswith(os.path.join("manga_translator_work", "json")):
            work_dir = os.path.dirname(json_dir)
            image_dir = os.path.dirname(work_dir)
            image_name = json_basename.replace("_translations.json", "")
            for ext in [".jpg", ".png", ".jpeg", ".webp", ".avif"]:
                image_path = os.path.join(image_dir, image_name + ext)
                if os.path.exists(image_path):
                    output_path = get_translated_txt_path(image_path)
                    break
            if output_path is None:
                output_path = os.path.splitext(detailed_json_path)[0] + "_translated.txt"
        else:
            output_path = os.path.splitext(detailed_json_path)[0] + "_translated.txt"

    try:
        if not items:
            output_content = ""
        elif template_path and os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                template_string = f.read()
            prefix, item_template, separator, suffix = parse_template(template_string)
            formatted_items = []
            for item in items:
                formatted_item = item_template.replace("<original>", item["original"])
                formatted_item = formatted_item.replace("<translated>", item["translated"])
                formatted_items.append(formatted_item)
            output_content = prefix + separator.join(formatted_items) + suffix
        else:
            output_content = "\n".join([item["translated"] for item in items])

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_content)
        logger.info("Translated text exported to: %s", output_path)
    except Exception as exc:
        return f"Error writing to output file: {exc}"

    return output_path


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource in dev/PyInstaller env."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_path, relative_path)


def get_default_template_path() -> str:
    return resource_path(os.path.join("examples", "translation_template.json"))


def ensure_default_template_exists() -> Optional[str]:
    template_path = get_default_template_path()
    if not os.path.exists(template_path):
        template_dir = os.path.dirname(template_path)
        os.makedirs(template_dir, exist_ok=True)
        default_template_content = """翻译模板文件

原文: <original>
译文: <translated>

"""
        try:
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(default_template_content)
            logger.info("Created default template at: %s", template_path)
        except Exception as exc:
            logger.error("Failed to create default template: %s", exc)
            return None
    return template_path


def get_template_path_from_config(custom_path: str = None) -> str:
    """Resolve template path with priority: argument > env > default."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    if custom_path:
        path_to_check = custom_path if os.path.isabs(custom_path) else os.path.join(base_path, custom_path)
        if os.path.exists(path_to_check):
            return path_to_check

    env_template = os.environ.get("MANGA_TEMPLATE_PATH")
    if env_template:
        path_to_check = env_template if os.path.isabs(env_template) else os.path.join(base_path, env_template)
        if os.path.exists(path_to_check):
            return path_to_check

    return get_default_template_path()


def _load_large_json_optimized(json_file_path: str):
    """Load JSON with ijson fallback for large payloads."""
    try:
        import ijson

        with open(json_file_path, "rb") as f:
            return dict(ijson.kvitems(f, ""))
    except ImportError:
        logger.warning("ijson unavailable, falling back to json.load")
        with open(json_file_path, "r", encoding="utf-8") as f:
            return json.load(f)


def safe_update_large_json_from_text(text_file_path: str, json_file_path: str, template_path: str) -> str:
    """Update translation JSON with text content parsed by template."""
    import gc
    import shutil
    import tempfile
    import time

    for file_path, name in [(text_file_path, "TXT"), (json_file_path, "JSON"), (template_path, "模板")]:
        if not os.path.exists(file_path):
            return f"错误：{name}文件不存在: {file_path}"

    json_size_mb = os.path.getsize(json_file_path) / (1024 * 1024)

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_string = f.read()
        with open(text_file_path, "r", encoding="utf-8") as f:
            text_content = f.read()
    except Exception as exc:
        return f"错误：读取输入文件失败: {exc}"

    try:
        prefix, item_template, separator, suffix = parse_template(template_string)
    except ValueError as exc:
        return f"错误：解析模板失败: {exc}"

    translations: Dict[str, str] = {}
    try:
        parsed_json = json.loads(text_content)
        if isinstance(parsed_json, dict):
            translations = parsed_json
        else:
            raise ValueError("Not a dict")
    except (json.JSONDecodeError, ValueError):
        if prefix and text_content.startswith(prefix):
            text_content = text_content[len(prefix) :]
        if suffix and text_content.endswith(suffix):
            text_content = text_content[: -len(suffix)]

        if separator:
            items = text_content.split(separator)
            if len(items) == 1 and "," in text_content:
                items = re.split(r'",\s*"', text_content)
        else:
            items = [text_content] if text_content.strip() else []

        parts = re.split(f'({re.escape("<original>")}|{re.escape("<translated>")})', item_template)
        parser_regex_str = ""
        group_order = []
        for part in parts:
            if part == "<original>":
                parser_regex_str += "(.+?)"
                group_order.append("original")
            elif part == "<translated>":
                parser_regex_str += "(.*)"
                group_order.append("translated")
            else:
                parser_regex_str += re.escape(part)

        parser_regex = re.compile(parser_regex_str + "$", re.DOTALL)

        for item in items:
            if not item.strip():
                continue
            match = parser_regex.search(item)
            if not match:
                continue
            try:
                result = {}
                for j, group_name in enumerate(group_order):
                    result[group_name] = match.group(j + 1)
                translations[result["original"]] = result["translated"]
            except (IndexError, KeyError):
                continue

    if not translations:
        return "错误：未能从TXT文件中解析出任何翻译内容"

    def normalize_text(text: str) -> str:
        import unicodedata

        text = "".join(ch for ch in text if unicodedata.category(ch)[0] not in ["C", "Z"] and ch != "\ufffd")
        return " ".join(text.split())

    normalized_to_original = {normalize_text(k): k for k in translations.keys()}

    backup_path = None
    temp_path = None
    try:
        gc.collect()
        if json_size_mb > 50:
            source_data = _load_large_json_optimized(json_file_path)
        else:
            with open(json_file_path, "r", encoding="utf-8") as f:
                source_data = json.load(f)

        updated_count = 0
        image_key = next(iter(source_data.keys()), None)
        if not image_key or "regions" not in source_data[image_key]:
            return "错误：JSON文件格式不正确，找不到regions数据"

        for region in source_data[image_key]["regions"]:
            original_text = region.get("text", "")
            if original_text in translations:
                new_translation = translations[original_text]
            else:
                normalized = normalize_text(original_text)
                matched_original = normalized_to_original.get(normalized)
                if not matched_original:
                    continue
                new_translation = translations[matched_original]

            old_translation = region.get("translation", "")
            if old_translation != new_translation:
                region["translation"] = new_translation
                updated_count += 1

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=os.path.dirname(json_file_path),
            suffix=".tmp",
        ) as temp_file:
            temp_path = temp_file.name

            class OptimizedJSONEncoder(json.JSONEncoder):
                def default(self, obj):
                    if hasattr(obj, "tolist"):
                        return obj.tolist()
                    if hasattr(obj, "__int__"):
                        return int(obj)
                    if hasattr(obj, "__float__"):
                        return float(obj)
                    return super().default(obj)

            json.dump(source_data, temp_file, ensure_ascii=False, indent=4, cls=OptimizedJSONEncoder)

        if os.name == "nt" and os.path.exists(json_file_path):
            os.remove(json_file_path)
        shutil.move(temp_path, json_file_path)
        temp_path = None

        with open(json_file_path, "r", encoding="utf-8") as f:
            json.load(f)

        backup_pattern = f"{json_file_path}.backup_*"
        backup_files = sorted(glob.glob(backup_pattern), reverse=True)
        for old_backup in backup_files[3:]:
            try:
                os.remove(old_backup)
            except Exception:
                pass

        elapsed = time.time()
        _ = elapsed
        return f"成功更新 {updated_count} 条翻译"

    except Exception as exc:
        error_msg = f"错误：更新过程中出现异常: {exc}"
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        if backup_path and os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, json_file_path)
                error_msg += " (已恢复备份文件)"
            except Exception:
                error_msg += " (备份恢复失败，请手动恢复)"
        logger.error(error_msg)
        return error_msg
    finally:
        gc.collect()
