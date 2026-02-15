import os
import sys

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def patch_db_manager(base_path):
    logs = []
    try:
        file_path = os.path.join(base_path, "database", "db_manager.py")
        if not os.path.exists(file_path):
            return ["❌ db_manager.py not found."]

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Target block to replace (Old Filters)
        old_filters = """                filters = [
                    Material.name.like(search_pattern),
                    Material.code.like(search_pattern),
                    Client.name.like(search_pattern)
                ]"""
        
        new_filters = """                filters = [
                    Material.name.like(search_pattern),
                    Material.code.like(search_pattern),
                    Client.name.like(search_pattern),
                    Material.manufacturer.like(search_pattern),
                    Material.name_en.like(search_pattern),
                    Material.origin.like(search_pattern),
                    Material.hs_code.like(search_pattern),
                    Material.nmpa_reg_num.like(search_pattern)
                ]"""

        old_ing_filters = """                    filters.extend([
                        Ingredient.name_ko.like(search_pattern),
                        Ingredient.name_en.like(search_pattern)
                    ])"""
        
        new_ing_filters = """                    filters.extend([
                        Ingredient.name_ko.like(search_pattern),
                        Ingredient.name_en.like(search_pattern),
                        Ingredient.cas_no.like(search_pattern)
                    ])"""

        patched = False
        if old_filters in content:
            content = content.replace(old_filters, new_filters)
            logs.append("✅ db_manager.py: Material filters updated.")
            patched = True
        
        if old_ing_filters in content:
            content = content.replace(old_ing_filters, new_ing_filters)
            logs.append("✅ db_manager.py: Ingredient filters updated.")
            patched = True
            
        if patched:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            logs.append("ℹ️ db_manager.py: Already up to date.")

    except Exception as e:
        logs.append(f"❌ db_manager.py patch failed: {str(e)}")
    
    return logs

def patch_ui_components(base_path):
    logs = []
    try:
        file_path = os.path.join(base_path, "modules", "ui_components.py")
        # ui_components가 없을 수도 있으므로 체크
        if not os.path.exists(file_path):
            # 필수 파일이 아니거나 구조가 다를 수 있음
            return ["ℹ️ ui_components.py not found (Skipped)."]

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        target = "materials = db_manager.search_materials(search_term, load_ingredients=True)"
        replacement = "materials = db_manager.search_materials(search_term, load_ingredients=True, search_ingredients=True)"

        if target in content:
            content = content.replace(target, replacement)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logs.append("✅ ui_components.py: search_materials call updated.")
        else:
            logs.append("ℹ️ ui_components.py: Target string not found or already updated.")

    except Exception as e:
        logs.append(f"❌ ui_components.py patch failed: {str(e)}")
    
    return logs

def run_patches():
    """Run all patches and return a list of status messages."""
    base_path = get_base_path()
    all_logs = []
    
    try:
        all_logs.extend(patch_db_manager(base_path))
        all_logs.extend(patch_ui_components(base_path))
    except Exception as e:
        all_logs.append(f"❌ Critical Patch Error: {str(e)}")
        
    return all_logs

if __name__ == "__main__":
    # 직접 실행 시 테스트
    for log in run_patches():
        print(log)
