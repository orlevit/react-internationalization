#!/usr/bin/env python3
"""
i18n Agent for React App
Automatically adds internationalization to a React application
"""

import os
import re
import json
import hashlib
from pathlib import Path, PosixPath
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
from openai import OpenAI
from dotenv import load_dotenv
from collections import OrderedDict
from config import Config, load_config
from ast_creation import parse_react_project
from complex_i18n import ComplexI18nProcessor

class I18nAgent:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key)
        self.translations = defaultdict(dict)
        self.translation_keys = {}
        self.translation_keys_maybe = {}
        self.translation_keys_all = {}
        self.processed_files = []
        self.all_files = []
        self.react_files = []
        self.symbols_dict = {}
    
    def extract_translatable_strings(self):
        # Step 1: Scan project structure
        print("\n📁 Scanning project structure...")
        self.all_files  = self.scan_js_files() # TODO change

        # react_files = [i for i in self.all_files  if i.suffix in  ['.jsx','tsx']]
        react_files = [PosixPath('react-app3/pages/public/login.jsx')]

        print(f"Found {react_files} React files")
        print(f"Found {len(react_files)} React files")
        
        # Step 2: Extract translatable strings
        print("\n🔍 Extracting translatable strings...")
        for file_path in react_files:
            self.extract_strings_from_file(file_path)
        print(f"Extracted {len(self.translation_keys)} unique strings")
        
        self.translation_keys_all = self.translation_keys.copy()
        self.translation_keys_maybe = {key: data for key, data in self.translation_keys.items() if data['process_ind'] == 'Maybe'}
        self.translation_keys = {key: data for key, data in self.translation_keys.items() if data['process_ind'] == 'True'}
        return react_files
    
    def update_simple_translations(self, react_files):
        # Step 3: Generate translations using LLM
        print("\n🌍 Generating translations...")     
        self.generate_translations()
        
        # Step 4: Create translation files
        print("\n📝 Creating translation files...")
        self.create_translation_files()
        
        # Step 5: Setup i18n infrastructure
        print("\n🏗️ Setting up i18n infrastructure...")
        self.setup_i18n_config()
        
        # Step 6: Refactor React components
        print("\n🔧 Refactoring React components...")
        for file_path in react_files:
            self.refactor_component(file_path)
        
        # Step 7: Update package.json
        print("\n📦 Updating package.json...")
        self.update_package_json()
        

    def create_parse_react_project(self):
        # Save to file
        #if not os.path.exists(self.config.symbols_dict_path):
        symbols_dict = parse_react_project(self.all_files [:]) ########## TODO: change to all

        with open(self.config.symbols_dict_path, 'w', encoding='utf-8') as f:
            json.dump(symbols_dict, f, indent=2, ensure_ascii=False)
        # else:
        #     with open(self.config.symbols_dict_path, 'r', encoding='utf-8') as f: # todo: CNAGE
        #         symbols_dict = json.load(f)

        return symbols_dict 

    def run(self):
        """Main execution flow"""
        print("🚀 Starting i18n automation process...")
        # get all files
        react_files = self.extract_translatable_strings()

        # update only simple cases  where there is only a string 
        self.update_simple_translations(react_files)

        # handle complex cases where there are variables/function calles inside the text
        # create a mapping between functions/classes/objects and their references
        self.symbols_dict = self.create_parse_react_project()

        
        processor = ComplexI18nProcessor(
            openai_client=self.client,
            target_languages=self.config.target_languages,
            project_path=self.config.project_path)

        processor.process_complex_i18n(self.translation_keys_maybe, self.symbols_dict)

        print("\n✅ i18n automation complete!")
        
    def scan_js_files(self) -> List[Path]:
        """Scan for React component files"""
        react_files = []
        extensions = ['.jsx', '.js', '.tsx', '.ts']
        nextjs_special_files = ['_app.jsx', '_app.js', '_document.jsx', '_document.js', '_error.jsx', '_error.js']

        exclude_dirs = {'node_modules', '.next', 'build', 'dist'}
        
        for root, dirs, files in os.walk(self.config.project_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if any(file.endswith(ext) for ext in extensions) and not any(file.endswith(special_file) for special_file in nextjs_special_files):
                    file_path = Path(root) / file
                    # Check if it's likely a React component
                    # if self.is_react_component(file_path):
                    react_files.append(file_path)
                        
        return react_files
    
    def is_react_component(self, file_path: Path) -> bool:
        """Check if file contains React component"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return 'react' in content.lower() or 'jsx' in content
        except:
            return False
    
    def extract_strings_from_file(self, file_path: Path):
        """Extract hardcoded strings from a React file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Patterns to find hardcoded strings
        patterns = [
            # r'<(?:button|a|span|p|h[1-6]|div)[^>]*>\s*([^<>]+?)\s*</(?:button|a|span|p|h[1-6]|div)>',

            # JSX any element with direct innerText (fallback for generic cases)
            r'>([^<\n][^<]+?)</',

            # String literals in props like title="Save", label="Name"
            r'(?:title|label|placeholder|alt|value|message|description|error|success|warning|info)\s*=\s*["\']([^"\']+?)["\']',

            # Error messages, notifications (console, alert, notify, etc.)
            r'(?:alert|notify|console\.(?:log|error|warn))\s*\(\s*["\']([^"\']+?)["\']\s*\)',
        ]

            
        for pattern in patterns:
            matches = [match for match in re.finditer(pattern, content, re.IGNORECASE)]
            for match in matches:
                # Clean up the match
                group_id = len(match.groups())
                text = match.group(group_id).strip()
                match_span = match.span(group_id)

                # Skip if it's likely code or a variable
                process_ind = self.should_translate(text)
                if process_ind:
                    # Generate a unique key
                    key = self.generate_translation_key(text, str(file_path))
                    self.translation_keys[key] = {
                        'text': text,
                        'file': str(file_path),
                        'process_ind' : 'Maybe' if process_ind == 'Maybe' else 'True',
                        'span' : match_span,
                        'occurrences': self.translation_keys.get(key, {}).get('occurrences', 0) + 1
                    }
    
    def should_translate(self, text: str) -> bool:
        """Determine if a string should be translated"""
        # Skip empty or very short strings
        if not text or len(text) < 2:
            return False
            
        # Skip if it looks like code
        if '=>' in text:
            # If it *only* looks like an arrow function, skip
            if re.fullmatch(r'\s*\(?[\w\s,]*\)?\s*=>.*', text):
                return 'False'


        # Skip if it's just numbers or special characters
        if re.fullmatch(r'[\d\s\.,:;!?\-]+', text):
            return False
        

        # JSX expression: t("some text") — already internationalized
        # but might be used for checking duplicates or migration
        if re.fullmatch(r't\(\s*["\']([^"\']+)["\']\s*\)', text):
                return False   
        
        code_like_patterns = [
            r'^\{.*\}$',          # {...}
            r'^\$\{.*\}$',        # ${...}
            r'^\(.*\)$',          # (...)
            r'^`.*`$',          # `...`
            r'^(const|let|var|function)\b' # starts with JS declarations
        ]
        for pattern in code_like_patterns:
            if re.match(pattern, text):
                return 'Maybe'
             
        
        code_indicators = ['{', '}', '(', ')', '=>', 'function', 'const', 'let', 'var', '$', '`']
        if any(indicator in text for indicator in code_indicators):
            return 'Maybe'
        
        return True
    
    def generate_translation_key(self, text: str, context: str = '') -> str:
        """Generate a unique translation key"""
        # Create a base key from the text
        base_key = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        base_key = '_'.join(base_key.lower().split()[:5])
        
        # Add context if needed to ensure uniqueness
        if not base_key:
            base_key = 'text'
            
        # Make it unique with a short hash if needed
        full_text = f"{text}_{context}"
        text_hash = hashlib.md5(full_text.encode()).hexdigest()[:6]
        
        return f"{base_key}_{text_hash}"
    
    def generate_translations(self):
        """Use LLM to generate translations"""
        for lang in self.config.target_languages:
            if lang == self.config.default_language:
                # For default language, use original text
                for key, data in self.translation_keys.items():
                    self.translations[lang][key] = data['text']
            else:
                # Use LLM for other languages
                self.generate_language_translations(lang)
    
    def generate_language_translations(self, target_lang: str):
        """Generate translations for a specific language using LLM"""
        # Batch process translations for efficiency
        batch_size = 20
        keys = list(self.translation_keys.keys())[:batch_size] #TODO: batch_size
        
        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i:i + batch_size]
            texts_to_translate = {
                key: self.translation_keys[key]['text'] 
                for key in batch_keys
            }
            
            prompt = f"""
            Translate the following UI texts from English to {target_lang}.
            Maintain the tone and context appropriate for a web application.
            Return a JSON object with the same keys.
            
            Texts to translate:
            {json.dumps(texts_to_translate, indent=2)}
            """
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a professional translator specializing in UI/UX translations."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0
                )
                
                translated_texts = json.loads(response.choices[0].message.content)
                self.translations[target_lang].update(translated_texts)
                
            except Exception as e:
                print(f"Error translating batch for {target_lang}: {e}")
                # Fallback: use original text
                for key in batch_keys:
                    self.translations[target_lang][key] = self.translation_keys[key]['text']
    
    def create_translation_files(self):
        """Create translation JSON files"""
        locales_dir = Path(self.config.project_path) / 'public' / 'locales'
        
        for lang in self.config.target_languages:
            lang_dir = locales_dir / lang
            lang_dir.mkdir(parents=True, exist_ok=True)
            
            # Create translation file
            translation_file = lang_dir / 'common.json'
            with open(translation_file, 'w', encoding='utf-8') as f:
                json.dump(self.translations[lang], f, ensure_ascii=False, indent=2)
            
            print(f"Created translation file: {translation_file}")

    def setup_i18n_config(self):
        """Setup i18n configuration files"""
        # Dynamically generate resources from config
        resources_entries = '\n'.join([
            f"  {lang}: {{\n    translation: require('../public/locales/{lang}/common.json')\n  }},"
            for lang in self.config.target_languages
        ])
        
        i18n_config = f'''import i18n from 'i18next';
    import {{ initReactI18next }} from 'react-i18next';

    const resources = {{
    {resources_entries}
    }};

    i18n
    .use(initReactI18next)
    .init({{
        resources,
        fallbackLng: '{self.config.default_language}',
        debug: false,
        interpolation: {{
        escapeValue: false
        }}
    }});

    export default i18n;
    '''

        config_path = Path(self.config.project_path) / 'lib' / 'i18n.js'
        with open(config_path, 'w') as f:
            f.write(i18n_config)

        # Dynamically generate next-i18next.config.js
        locales_list = ', '.join([f"'{lang}'" for lang in self.config.target_languages])
        next_i18n_config = f'''module.exports = {{
    i18n: {{
        defaultLocale: '{self.config.default_language}',
        locales: [{locales_list}],
    }},
    }};
    '''

        next_config_path = Path(self.config.project_path) / 'next-i18next.config.js'
        with open(next_config_path, 'w') as f:
            f.write(next_i18n_config)

            
            next_config_path = Path(self.config.project_path) / 'next-i18next.config.js'
            with open(next_config_path, 'w') as f:
                f.write(next_i18n_config)
    
    
    def update_spans_after_insertion(self, file_path, all_translation_dict, insertion_pos, inserted_text_length):
        """
        Update span locations in all_translation_dict for entries that come after the insertion point
        
        Args:
            file_path: Path object of the current file
            all_translation_dict: Dictionary containing translation entries
            insertion_pos: Position where text was inserted
            inserted_text_length: Length of the inserted text
        """
        relative_file_path = str(file_path.relative_to(self.config.project_path))
        
        for key in all_translation_dict:
            entry = all_translation_dict[key]
            
            # Check if this entry belongs to the current file
            if entry.get("file") == relative_file_path:
                current_span = entry.get("span")
                
                if current_span and isinstance(current_span, tuple) and len(current_span) == 2:
                    start_pos, end_pos = current_span
                    
                    # Only update spans that start after the insertion point
                    if start_pos >= insertion_pos:
                        new_start = start_pos + inserted_text_length
                        new_end = end_pos + inserted_text_length
                        all_translation_dict[key]["span"] = (new_start, new_end)

    def process_file_with_span_updates(self, file_path, content, all_translation_dict):
        """
        Process file content and update spans in all_translation_dict accordingly
        """
        original_length = len(content)
        modified = False
        
        if 'useTranslation' not in content:
            import_statement = "import { useTranslation } from 'react-i18next';\n"
            insertion_pos = 0  # Import statement is added at the beginning
            inserted_length = len(import_statement)
            
            content = import_statement + content[:]
            modified = True
            
            # Update spans for this insertion
            self.update_spans_after_insertion(file_path, all_translation_dict, insertion_pos, inserted_length)
            
            # Process hooks addition
            content, modified_hook = self.add_translation_hooks_with_span_updates(content, file_path, all_translation_dict, inserted_length)
            modified = bool(modified or modified_hook)
        else:
            # If import already exists, just add hooks
            content, modified_hook = self.add_translation_hooks_with_span_updates(content, file_path, all_translation_dict, 0)
            modified = bool(modified_hook)
        
        return content, modified

    def add_translation_hooks_with_span_updates(self, content, file_path, all_translation_dict, previous_insertions_length=0):
        """
        Add translation hooks and update spans accordingly
        """
        modified = False
        total_inserted_length = previous_insertions_length
        
        # Pattern to match React components (functions that likely return JSX)
        # This looks for functions that contain JSX return statements
        component_patterns = [
            # Function components with explicit return containing JSX
            r'(?:export\s+(?:default\s+)?)?function\s+([A-Z][a-zA-Z0-9]*)\s*\([^)]*\)\s*\{(?=(?:[^{}]|{[^}]*})*return\s*(?:\(|\<))',
            # Arrow function components (const Component = () => { ... return JSX })
            r'(?:export\s+(?:default\s+)?)?const\s+([A-Z][a-zA-Z0-9]*)\s*=\s*(?:\([^)]*\)|[^=]+)\s*=>\s*\{(?=(?:[^{}]|{[^}]*})*return\s*(?:\(|\<))',
            # Arrow function components with implicit return (const Component = () => <JSX>)
            r'(?:export\s+(?:default\s+)?)?const\s+([A-Z][a-zA-Z0-9]*)\s*=\s*(?:\([^)]*\)|[^=]+)\s*=>\s*(?:\(?\s*<)',
        ]
        
        # Keep track of all insertions to update spans correctly
        insertions = []
        
        for pattern in component_patterns:
            matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))
            
            # Process matches in reverse order to avoid position shifts during insertion
            for match in reversed(matches):
                component_name = match.group(1)
                
                # Skip if it's clearly not a React component (common HOC patterns)
                if component_name.lower() in ['withauth', 'withrole', 'withpermission', 'hoc']:
                    continue
                    
                # Check if this function already has useTranslation hook
                component_start = match.start()
                
                # Find the opening brace of the function body
                if '=>' in match.group(0):
                    # Arrow function
                    arrow_pos = content.find('=>', component_start)
                    if arrow_pos != -1:
                        # Look for opening brace after arrow
                        brace_pos = content.find('{', arrow_pos)
                        if brace_pos != -1:
                            insert_pos = brace_pos + 1
                        else:
                            # Implicit return arrow function, skip
                            continue
                    else:
                        continue
                else:
                    # Regular function
                    brace_pos = content.find('{', match.end() - 1)
                    if brace_pos != -1:
                        insert_pos = brace_pos + 1
                    else:
                        continue
                
                # Find the end of this component to check for existing useTranslation
                component_end = self.find_function_end(content, insert_pos - 1)
                component_body = content[insert_pos:component_end]
                
                # Skip if useTranslation already exists in this component
                if 'useTranslation' in component_body:
                    continue
                    
                # Check if this looks like a React component by looking for JSX patterns
                jsx_patterns = [
                    r'return\s*\(',  # return (
                    r'return\s*<',   # return <
                    r'<[A-Z][a-zA-Z0-9]*',  # JSX component tags
                    r'<[a-z]+',      # HTML tags
                    r'className=',   # React className prop
                    r'onClick=',     # React event handlers
                ]
                
                has_jsx = any(re.search(jsx_pattern, component_body) for jsx_pattern in jsx_patterns)
                
                if has_jsx:
                    # Add the useTranslation hook
                    hook_line = '\n  const { t } = useTranslation();\n'
                    hook_length = len(hook_line)
                    
                    # Store insertion info for later span updates
                    insertions.append({
                        'position': insert_pos,
                        'length': hook_length
                    })
                    
                    content = content[:insert_pos] + hook_line + content[insert_pos:]
                    modified = True
        
        # Update spans for all insertions made in this function
        # Process insertions in forward order since we stored them in reverse processing order
        insertions.reverse()
        
        cumulative_offset = total_inserted_length
        for insertion in insertions:
            actual_insertion_pos = insertion['position'] + cumulative_offset
            self.update_spans_after_insertion(file_path, all_translation_dict, actual_insertion_pos, insertion['length'])
            cumulative_offset += insertion['length']
        
        return content, modified

    def add_translation_hooks(self, content):
        """
        Original method for backward compatibility - use the new method with span updates when possible
        """
        modified = False
        
        # Pattern to match React components (functions that likely return JSX)
        # This looks for functions that contain JSX return statements
        component_patterns = [
            # Function components with explicit return containing JSX
            r'(?:export\s+(?:default\s+)?)?function\s+([A-Z][a-zA-Z0-9]*)\s*\([^)]*\)\s*\{(?=(?:[^{}]|{[^}]*})*return\s*(?:\(|\<))',
            # Arrow function components (const Component = () => { ... return JSX })
            r'(?:export\s+(?:default\s+)?)?const\s+([A-Z][a-zA-Z0-9]*)\s*=\s*(?:\([^)]*\)|[^=]+)\s*=>\s*\{(?=(?:[^{}]|{[^}]*})*return\s*(?:\(|\<))',
            # Arrow function components with implicit return (const Component = () => <JSX>)
            r'(?:export\s+(?:default\s+)?)?const\s+([A-Z][a-zA-Z0-9]*)\s*=\s*(?:\([^)]*\)|[^=]+)\s*=>\s*(?:\(?\s*<)',
        ]
        
        for pattern in component_patterns:
            matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))
            
            # Process matches in reverse order to avoid position shifts
            for match in reversed(matches):
                component_name = match.group(1)
                
                # Skip if it's clearly not a React component (common HOC patterns)
                if component_name.lower() in ['withauth', 'withrole', 'withpermission', 'hoc']:
                    continue
                    
                # Check if this function already has useTranslation hook
                component_start = match.start()
                
                # Find the opening brace of the function body
                if '=>' in match.group(0):
                    # Arrow function
                    arrow_pos = content.find('=>', component_start)
                    if arrow_pos != -1:
                        # Look for opening brace after arrow
                        brace_pos = content.find('{', arrow_pos)
                        if brace_pos != -1:
                            insert_pos = brace_pos + 1
                        else:
                            # Implicit return arrow function, skip
                            continue
                    else:
                        continue
                else:
                    # Regular function
                    brace_pos = content.find('{', match.end() - 1)
                    if brace_pos != -1:
                        insert_pos = brace_pos + 1
                    else:
                        continue
                
                # Find the end of this component to check for existing useTranslation
                component_end = self.find_function_end(content, insert_pos - 1)
                component_body = content[insert_pos:component_end]
                
                # Skip if useTranslation already exists in this component
                if 'useTranslation' in component_body:
                    continue
                    
                # Check if this looks like a React component by looking for JSX patterns
                jsx_patterns = [
                    r'return\s*\(',  # return (
                    r'return\s*<',   # return <
                    r'<[A-Z][a-zA-Z0-9]*',  # JSX component tags
                    r'<[a-z]+',      # HTML tags
                    r'className=',   # React className prop
                    r'onClick=',     # React event handlers
                ]
                
                has_jsx = any(re.search(jsx_pattern, component_body) for jsx_pattern in jsx_patterns)
                
                if has_jsx:
                    # Add the useTranslation hook
                    hook_line = '\n  const { t } = useTranslation();\n'
                    content = content[:insert_pos] + hook_line + content[insert_pos:]
                    modified = True
        
        return content, modified
    #############################################################
    def find_function_end(self, content, start_pos):
        """Find the end position of a function body starting from the opening brace."""
        brace_count = 1
        pos = start_pos + 1
        
        while pos < len(content) and brace_count > 0:
            char = content[pos]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            pos += 1
        
        return pos

    
    def refactor_component(self, file_path: Path):
        def _convert_dict_to_ordered_list(d, file_path):
            file_translation_keys = {}
            not_cur_files_dict = {}
            for  key, data in d.items():
                if data['file'] == str(file_path):
                    file_translation_keys[key] = data
                else:
                    not_cur_files_dict[key] = data
                # specific_file_dict = {key: data  for key, data in self.translation_keys.items() if data['file'] == file_name}
            sorted_translation_list= sorted(file_translation_keys.items(), key=lambda x:  x[1]['span'][0])
                            
            return sorted_translation_list, not_cur_files_dict
        
        """Refactor a React component to use i18n"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        
        # sorted_translation_list, _ = _convert_dict_to_ordered_list(self.translation_keys, file_path)
        sorted_translation_list_all, not_cur_files_dict = _convert_dict_to_ordered_list(self.translation_keys_all, file_path)
                     
        # Replace hardcoded strings with t() calls
        for i,(key, data) in enumerate(sorted_translation_list_all):
            if data['process_ind'] == 'True':
                replaced_text = f"{{t('{key}')}}"
                len_diff = len(replaced_text) - (data['span'][1] - data['span'][0])
                content = content[:data['span'][0]] + f"{{t('{key}')}}" + content[data['span'][1]:]

                for j in range(i + 1,len(sorted_translation_list_all)):
                    sorted_translation_list_all[j][1]['span'] = (
                        sorted_translation_list_all[j][1]['span'][0] + len_diff,
                        sorted_translation_list_all[j][1]['span'][1] + len_diff
                    )
            
                modified = True

        all_translation_dict = not_cur_files_dict.copy()
        for i, (key, data) in enumerate(sorted_translation_list_all):
            all_translation_dict[key] = data
  
        if 'useTranslation' not in content:
            content, modified = self.process_file_with_span_updates(file_path, content, all_translation_dict)
        self.translation_keys_all = all_translation_dict
        self.translation_keys_maybe = {key: data for key, data in self.translation_keys_all.items() if data['process_ind'] == 'Maybe'}

        # Write back if modified
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.processed_files.append(file_path)
            print(f"✓ Refactored: {file_path.relative_to(self.config.project_path)}")
        
    def update_package_json(self):
        """Update package.json with i18n dependencies"""
        package_json_path = Path(self.config.project_path) / 'package.json'
        
        with open(package_json_path, 'r') as f:
            package_data = json.load(f)
        
        # Add i18n dependencies
        dependencies = package_data.get('dependencies', {})
        dependencies.update({
            'i18next': '^21.9.0',
            'react-i18next': '^11.18.0',
            'i18next-browser-languagedetector': '^6.1.0',
            'next-i18next': '^12.0.0'
        })
        
        package_data['dependencies'] = dependencies
        
        # Write back
        with open(package_json_path, 'w') as f:
            json.dump(package_data, f, indent=2)
        
        print("✓ Updated package.json with i18n dependencies")


def main():
    """Main entry point"""
    
    config = load_config("i18n_script/config.yaml")
    agent = I18nAgent(config)
    agent.run()


if __name__ == '__main__':
    main()
