import json
import yaml
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import shutil
from datetime import datetime

@dataclass
class Config:
    project_path: str
    openai_api_key: str
    symbols_dict_path: str
    target_languages: List[str] = None
    default_language: str = "en"

    def __post_init__(self):
        if self.target_languages is None:
            self.target_languages = ["en", "es"]

class I18nApplicator:
    def __init__(self, config: Union[Config, str, None] = None, config_path: Optional[str] = None):
        """
        Initialize the i18n applicator
        
        Args:
            config: Either a Config object or path to config.yaml, or None
            config_path: Explicit path to config.yaml (overrides config if both provided)
        """
        if config_path:
            self.config = self._load_config_from_file(config_path)
        elif isinstance(config, Config):
            self.config = self._config_dataclass_to_dict(config)
        elif isinstance(config, str):
            self.config = self._load_config_from_file(config)
        else:
            raise ValueError("Must provide either a Config object or config_path")
            
        self.translation_files = {}
        self.changes_applied = []
    
    def _config_dataclass_to_dict(self, config: Config) -> Dict[str, Any]:
        """Convert Config dataclass to dictionary format"""
        return {
            'project_path': config.project_path,
            'openai_api_key': config.openai_api_key,
            'symbols_dict_path': config.symbols_dict_path,
            'default_language': config.default_language,
            'target_languages': config.target_languages
        }
        
    def _load_config_from_file(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Expand environment variables
            if 'openai_api_key' in config and config['openai_api_key'].startswith('${'):
                env_var = config['openai_api_key'][2:-1]  # Remove ${ and }
                config['openai_api_key'] = os.environ.get(env_var, '')
            
            return config
            
        except Exception as e:
            raise Exception(f"Failed to load config from {config_path}: {str(e)}")
    
    def apply_i18n_changes(self, analysis_results: Dict[str, Any], 
                          backup: bool = True, dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply i18n changes based on analysis results
        
        Args:
            analysis_results: Results from analyze_project_i18n()
            backup: Whether to create backup files
            dry_run: If True, only show what would be changed without applying
            
        Returns:
            Summary of changes applied
        """
        print("🚀 Starting i18n translation application...")
        
        try:
            # Step 1: Load existing translation files
            print("📚 Loading existing translation files...")
            self._load_translation_files()
            
            # Step 2: Add new translations to language files
            print("🔤 Adding translations to language files...")
            self._add_translations_to_files(analysis_results, dry_run)
            
            # Step 3: Apply changes to source files
            print("📝 Applying changes to source files...")
            self._apply_source_file_changes(analysis_results, backup, dry_run)
            
            # Step 4: Save updated translation files
            print("💾 Saving translation files...")
            self._save_translation_files(dry_run)
            
            # Step 5: Add i18n imports if needed
            print("📦 Adding i18n imports...")
            self._add_i18n_imports(analysis_results, dry_run)
            
            summary = self._create_application_summary()
            
            if dry_run:
                print("🔍 DRY RUN COMPLETE - No files were actually modified")
            else:
                print("✅ i18n translation application complete!")
            
            return summary
            
        except Exception as e:
            print(f"❌ Error applying i18n changes: {str(e)}")
            raise
    
    def _load_translation_files(self):
        """Load existing translation files for all target languages"""
        project_path = Path(self.config['project_path'])
        locales_dir = project_path / 'public' / 'locales'
        
        for lang in self.config['target_languages']:
            lang_dir = locales_dir / lang
            common_file = lang_dir / 'common.json'
            
            if common_file.exists():
                try:
                    with open(common_file, 'r', encoding='utf-8') as f:
                        self.translation_files[lang] = json.load(f)
                    print(f"📖 Loaded existing translations for {lang}: {len(self.translation_files[lang])} keys")
                except Exception as e:
                    print(f"⚠️  Error loading {common_file}: {e}")
                    self.translation_files[lang] = {}
            else:
                print(f"📄 No existing translation file for {lang}, creating new one")
                self.translation_files[lang] = {}
    
    def _add_translations_to_files(self, analysis_results: Dict[str, Any], dry_run: bool):
        """Add new translations to language files"""
        required_changes = analysis_results.get('required_changes', {})
        default_lang = self.config['default_language']
        
        new_translations = {}
        
        for change_key, change_info in required_changes.items():
            suggested_key = change_info.get('suggested_key', change_key)
            original_text = change_info.get('text', '')
            
            # Parse the suggested key (e.g., "common.hello_world" -> "hello_world")
            if '.' in suggested_key:
                namespace, key = suggested_key.split('.', 1)
            else:
                namespace = 'common'
                key = suggested_key
            
            # For now, we'll only handle the 'common' namespace
            if namespace == 'common':
                # Add to default language with original text
                if default_lang not in new_translations:
                    new_translations[default_lang] = {}
                new_translations[default_lang][key] = original_text
                
                # Add placeholders for other languages
                for lang in self.config['target_languages']:
                    if lang != default_lang:
                        if lang not in new_translations:
                            new_translations[lang] = {}
                        # Use original text as placeholder for non-default languages
                        new_translations[lang][key] = f"TODO: Translate '{original_text}' to {lang}"
        
        # Merge with existing translations
        for lang, translations in new_translations.items():
            if lang not in self.translation_files:
                self.translation_files[lang] = {}
            
            for key, value in translations.items():
                if key not in self.translation_files[lang]:
                    self.translation_files[lang][key] = value
                    print(f"➕ Added translation for {lang}.{key}: '{value}'")
                else:
                    print(f"⏭️  Skipped existing translation for {lang}.{key}")
    
    def _apply_source_file_changes(self, analysis_results: Dict[str, Any], 
                                 backup: bool, dry_run: bool):
        """Apply changes to source files"""
        sorted_changes = analysis_results.get('sorted_changes_by_position', [])
        
        # Group changes by file
        changes_by_file = {}
        for change in sorted_changes:
            file_path = change['file']
            if file_path not in changes_by_file:
                changes_by_file[file_path] = []
            changes_by_file[file_path].append(change)
        
        # Process each file
        for file_path, file_changes in changes_by_file.items():
            self._apply_file_changes(file_path, file_changes, backup, dry_run)
    
    def _apply_file_changes(self, file_path: str, changes: List[Dict], 
                          backup: bool, dry_run: bool):
        """Apply changes to a single file"""
        try:
            # Create full path
            full_path = Path(self.config['project_path']) / file_path
            
            if not full_path.exists():
                print(f"⚠️  File not found: {full_path}")
                return
            
            # Read current file content
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Sort changes by line number (descending) to avoid offset issues
            changes.sort(key=lambda x: x['line_start'], reverse=True)
            
            # Apply each change
            for change in changes:
                original_text = change['text']
                replacement = self._generate_i18n_replacement(change)
                
                if original_text in content:
                    content = content.replace(original_text, replacement, 1)  # Replace only first occurrence
                    print(f"🔄 Replacing in {file_path}: '{original_text}' → '{replacement}'")
                    
                    self.changes_applied.append({
                        'file': file_path,
                        'original': original_text,
                        'replacement': replacement,
                        'line': change['line_start']
                    })
                else:
                    print(f"⚠️  Text not found in {file_path}: '{original_text}'")
            
            # Save changes if not dry run
            if not dry_run and content != original_content:
                # Create backup if requested
                if backup:
                    backup_path = f"{full_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(full_path, backup_path)
                    print(f"📋 Backup created: {backup_path}")
                
                # Write updated content
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Updated: {file_path}")
            elif dry_run:
                print(f"🔍 [DRY RUN] Would update: {file_path}")
                
        except Exception as e:
            print(f"❌ Error processing {file_path}: {str(e)}")
    
    def _generate_i18n_replacement(self, change: Dict) -> str:
        """Generate the i18n replacement text"""
        suggested_key = change.get('suggested_key', change.get('key', ''))
        
        # Parse the key to get the actual key part
        if '.' in suggested_key:
            namespace, key = suggested_key.split('.', 1)
        else:
            key = suggested_key
        
        # Check if the original text contains JSX or is in a JSX context
        original_text = change['text']
        current_lines = change.get('current_lines_to_change', [])
        
        # Determine if we're in JSX context
        is_jsx = any(
            '<' in line or '>' in line or 'return' in line 
            for line in current_lines
        )
        
        if is_jsx:
            return f"{{t('{key}')}}"
        else:
            return f"t('{key}')"
    
    def _save_translation_files(self, dry_run: bool):
        """Save updated translation files"""
        project_path = Path(self.config['project_path'])
        locales_dir = project_path / 'public' / 'locales'
        
        for lang, translations in self.translation_files.items():
            lang_dir = locales_dir / lang
            common_file = lang_dir / 'common.json'
            
            if not dry_run:
                # Create directories if they don't exist
                lang_dir.mkdir(parents=True, exist_ok=True)
                
                # Sort translations alphabetically
                sorted_translations = dict(sorted(translations.items()))
                
                # Save with pretty formatting
                with open(common_file, 'w', encoding='utf-8') as f:
                    json.dump(sorted_translations, f, indent=2, ensure_ascii=False)
                
                print(f"💾 Saved {len(translations)} translations to {common_file}")
            else:
                print(f"🔍 [DRY RUN] Would save {len(translations)} translations to {common_file}")
    
    def _add_i18n_imports(self, analysis_results: Dict[str, Any], dry_run: bool):
        """Add i18n imports to files that need them"""
        files_needing_changes = analysis_results.get('files_needing_changes', [])
        
        for file_path in files_needing_changes:
            self._add_i18n_import_to_file(file_path, dry_run)
    
    def _add_i18n_import_to_file(self, file_path: str, dry_run: bool):
        """Add i18n import to a specific file if not already present"""
        try:
            full_path = Path(self.config['project_path']) / file_path
            
            if not full_path.exists():
                return
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if useTranslation import already exists
            if 'useTranslation' in content or "import { t }" in content:
                print(f"⏭️  i18n import already exists in {file_path}")
                return
            
            # Add import at the top
            import_line = "import { useTranslation } from 'react-i18next';\n"
            
            # Find where to insert the import
            lines = content.split('\n')
            insert_index = 0
            
            # Find the last import statement
            for i, line in enumerate(lines):
                if line.strip().startswith('import '):
                    insert_index = i + 1
            
            # Insert the import
            lines.insert(insert_index, import_line.rstrip())
            
            # Add useTranslation hook if it's a React component
            if 'function ' in content or 'const ' in content and '=>' in content:
                # Find the component function
                for i, line in enumerate(lines):
                    if ('function ' in line and '(' in line) or ('const ' in line and '=>' in line):
                        # Add the hook after the function declaration
                        hook_line = "  const { t } = useTranslation();"
                        lines.insert(i + 1, hook_line)
                        break
            
            new_content = '\n'.join(lines)
            
            if not dry_run:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"📦 Added i18n import to {file_path}")
            else:
                print(f"🔍 [DRY RUN] Would add i18n import to {file_path}")
                
        except Exception as e:
            print(f"❌ Error adding import to {file_path}: {str(e)}")
    
    def _create_application_summary(self) -> Dict[str, Any]:
        """Create summary of applied changes"""
        return {
            'timestamp': datetime.now().isoformat(),
            'config_used': self.config,
            'languages_updated': list(self.translation_files.keys()),
            'translation_counts': {
                lang: len(translations) 
                for lang, translations in self.translation_files.items()
            },
            'source_files_modified': len(set(change['file'] for change in self.changes_applied)),
            'total_replacements': len(self.changes_applied),
            'changes_applied': self.changes_applied,
            'translation_files_paths': [
                f"{self.config['project_path']}/public/locales/{lang}/common.json"
                for lang in self.translation_files.keys()
            ]
        }

def apply_i18n_translations(analysis_results: Dict[str, Any], 
                          config: Union[Config, str, None] = None,
                          config_path: Optional[str] = None,
                          backup: bool = True, 
                          dry_run: bool = False) -> Dict[str, Any]:
    """
    Main function to apply i18n translations
    
    Args:
        analysis_results: Results from analyze_project_i18n()
        config: Either a Config dataclass object, path to config.yaml, or None
        config_path: Explicit path to config.yaml (overrides config if provided)
        backup: Whether to create backup files
        dry_run: If True, only show what would be changed
        
    Returns:
        Summary of changes applied
    """
    applicator = I18nApplicator(config, config_path)
    return applicator.apply_i18n_changes(analysis_results, backup, dry_run)

# Example usage
if __name__ == "__main__":
    # Example with Config dataclass
    from dataclasses import dataclass
    
    @dataclass
    class Config:
        project_path: str
        openai_api_key: str
        symbols_dict_path: str
        target_languages: List[str] = None
        default_language: str = "en"

        def __post_init__(self):
            if self.target_languages is None:
                self.target_languages = ["en", "es"]
    
    # Example config object
    config = Config(
        project_path="./react-app3",
        openai_api_key="your-api-key",
        symbols_dict_path="./i18n_script/symbols_dict.json",
        target_languages=["en", "es", "fr"],
        default_language="en"
    )
    
    # Example analysis results (replace with actual results)
    example_results = {
        "required_changes": {
            "hello_world": {
                'text': 'Hello World',
                'file': 'src/components/App.js',
                'suggested_key': 'common.hello_world',
                'current_lines_to_change': ['  return <div>Hello World</div>;'],
                'lines_after_change': ['  return <div>{t("hello_world")}</div>;']
            }
        },
        "sorted_changes_by_position": [
            {
                'key': 'hello_world',
                'file': 'src/components/App.js',
                'line_start': 10,
                'text': 'Hello World',
                'suggested_key': 'common.hello_world',
                'current_lines_to_change': ['  return <div>Hello World</div>;']
            }
        ],
        "files_needing_changes": ["src/components/App.js"]
    }
    
    # Method 1: Using Config dataclass object (your use case)
    print("=== USING CONFIG OBJECT ===")
    summary = apply_i18n_translations(
        example_results, 
        config, 
        config_path="./i18n_script/config.yaml", 
        backup=False, 
        dry_run=True
    )
    print(json.dumps(summary, indent=2))
    
    # Method 2: Using config file path only
    print("\n=== USING CONFIG FILE PATH ===")
    summary = apply_i18n_translations(
        example_results, 
        config_path="./i18n_script/config.yaml",
        backup=True, 
        dry_run=True
    )
    print(json.dumps(summary, indent=2))
    
    # Method 3: Config object takes precedence over file path
    print("\n=== CONFIG OBJECT + FILE PATH (object wins) ===")
    summary = apply_i18n_translations(
        example_results, 
        config,  # This will be used
        config_path="./i18n_script/config.yaml",  # This will be ignored
        backup=False, 
        dry_run=True
    )
    print(json.dumps(summary, indent=2))