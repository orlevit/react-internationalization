##################################    
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple
import openai
from collections import defaultdict

class ComplexI18nProcessor:
    def __init__(self, openai_client, target_languages: List[str] = None, project_path: str = "."):
        """
        Initialize the processor
        
        Args:
            openai_api_key: OpenAI API key for LLM calls
            target_languages: List of target languages for translation (default: ['en', 'es', 'fr'])
            project_path: Path to the project root
        """
        self.client = openai_client
        self.target_languages = target_languages
        self.project_path = Path(project_path)
        self.change_dict = {}
        self.translations = {lang: {} for lang in self.target_languages}
    
    def process_complex_i18n(self, possible_translations: Dict, symbols_dict: Dict) -> Dict:
        """
        Main processing function that orchestrates the entire i18n workflow
        
        Args:
            possible_translations: Dictionary of possible translations
            symbols_dict: Dictionary of symbols/components/functions
            
        Returns:
            Dictionary of complex i18n changes
        """
        print("Starting complex i18n processing...")
        
        # Step 1: Order possible_translations by file and span
        ordered_translations = self._order_translations(possible_translations)
        
        # Step 2-3: Create context and check intersections
        possible_translations_context = self._create_context(ordered_translations, symbols_dict)
        
        # Step 4: Process with LLM
        self._process_with_llm(possible_translations_context)
        
        # Step 5-8: Update files
        self._update_files(ordered_translations)
        
        # Step 9: Create translation files
        self._create_translation_files()
        
        return self.change_dict
    
    def _order_translations(self, possible_translations: Dict) -> Dict:
        """Order translations by file and span"""
        print("Ordering translations by file and span...")
        
        # Convert to list of tuples for sorting
        items = []
        for key, value in possible_translations.items():
            items.append((key, value))
        
        # Sort by file, then by span start
        items.sort(key=lambda x: (x[1]['file'], x[1]['span'][0]))
        
        # Convert back to ordered dictionary
        ordered = {}
        for key, value in items:
            ordered[key] = value
            
        return ordered
    
    def _create_context(self, possible_translations: Dict, symbols_dict: Dict) -> Dict:
        """Create context by checking intersections with symbols"""
        print("Creating context from symbols...")
        
        possible_translations_context = {}
        
        for key, translation_data in possible_translations.items():
            text = translation_data['text']
            file_path = translation_data['file']
            
            # Initialize context
            context = {}
            
            # Check for component/function calls in text that appear in symbols
            for symbol_key, symbol_data in symbols_dict.items():
                
                if symbol_key in text:
                    context[symbol_key] = symbol_data
            
            # Check dependencies recursively
            context = self._add_dependencies_recursively(context, symbols_dict)
            
            # Add to context dictionary
            possible_translations_context[key] = {
                **translation_data,
                'context': context
            }
        
        return possible_translations_context
    
    def _add_dependencies_recursively(self, context: Dict, symbols_dict: Dict) -> Dict:
        """Add dependencies recursively to context"""
        visited = set()
        
        def add_deps(current_context):
            for ctx_key, ctx_data in list(current_context.items()):
                if ctx_key in visited:
                    continue
                visited.add(ctx_key)
                
                dependencies = ctx_data.get('dependencies', [])
                for dep in dependencies:
                    if dep in symbols_dict:
                        current_context[dep] = symbols_dict[dep]
                        # Recursive call for nested dependencies
                        add_deps({dep: symbols_dict[dep]})
        
        add_deps(context)
        return context
    

    def _get_surrounding_text(self, file_path: str, span: Tuple[int, int], lines_before: int = 5, lines_after: int = 5) -> str:
        """Get surrounding lines of code based on character span"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                full_text = f.read()
                lines = full_text.splitlines(keepends=True)  # Retain \n characters

            # Map each character to its line number
            char_to_line = []
            current_char = 0
            for i, line in enumerate(lines):
                line_length = len(line)
                char_to_line.extend([i] * line_length)
                current_char += line_length

            # Handle out-of-range spans
            span_start = min(span[0], len(char_to_line) - 1)
            span_end = min(span[1], len(char_to_line) - 1)

            line_start = char_to_line[span_start]
            line_end = char_to_line[span_end]

            context_start = max(0, line_start - lines_before)
            context_end = min(len(lines), line_end + lines_after + 1)

            return ''.join(lines[context_start:context_end])

        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return ""

    def _process_with_llm(self, possible_translations_context: Dict):
        """Process translations with LLM"""
        print("Processing with LLM...")
        
        for key, data in possible_translations_context.items():
            text = data['text']
            file_path = data['file']
            span = data['span']
            context = data['context']
            
            # Get surrounding text
            text_surrounding = self._get_surrounding_text(file_path, span)
            
            # Prepare context string
            context_str = self._format_context(context, span)
            
            # Create prompt
            prompt = (
            f"You are expert in React and JavaScript.\n"
            f"This is a possible string that needs i18n translation, to be in the format of t{...}:\n"
            f"the_text_key: {key}\n"
            f"the text:\n{text}\n"
            f"the text span in the file:\n{span}\n"
            f"Text surrounding lines:\n{text_surrounding}\n"
            f"the file name:\n{file_path}\n"
            f"May be helpful components/function/variables etc, the_context_key:\n{context_str}\n"
            f"Print a dictionary of the changes that are needed in the code, use the \"text_key\" or the \"context_key\".\n"
            f"If change is not needed, then write \"No\". Write \"No\" only if you 100\n"
            f"If change is needed then your output should be a Python dictionary in the following format, and nothing else:\n"
            f"multi_change_dict = {{'the_text_key'({key}) or one of the 'the_context_key' values that given beofre: "
            f"{{'text': 'original_text', 'code': 'updated_code', 'adjusted_span': [start, end], "
            f"'description': 'change_description', 'file': 'file_path'}}}}\n\n\n"
            f"Important Python dictionary format rules:\n"
            f"'adjusted_span' - is the the current span of the text after the change.\n"
            f"only response with \"No\" or Python dictionary (\"multi_change_dict\"). Nothing else! without explanation!\n"
            f"the_text_key/the_context_key keys in the dictionary- have the value that was given before, and need to be replaced with their values! Do not merely write \"the_text_key\"/\"the_context_key\"!\n"
            f"Python dictionary/\"No\" response:\n"
            )
            # Call LLM
            response = self._call_llm(prompt)
            
            # Process response
            self._process_llm_response(response, key)
    
    def _format_context(self, context: Dict, span: Tuple) -> str:
        """Format context for LLM prompt"""
        context_lines = []
        for ctx_key, ctx_data in context.items():
            context_lines.append(f"Key: {ctx_key}")
            context_lines.append(f"Description: {ctx_data.get('description', '')}")
            context_lines.append(f"Type: {ctx_data.get('type', '')}")
            context_lines.append(f"File: {ctx_data.get('file', '')}")
            context_lines.append(f"Code: {ctx_data.get('code', '')}")
            context_lines.append(f"Span: {ctx_data.get('code', '')}")
            context_lines.append("---")
        return '\n'.join(context_lines)
    
    def _call_llm(self, prompt: str) -> str:
        """Call OpenAI LLM"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert React and JavaScript developer specializing in i18n."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling LLM: {e}")
            return "No"
    
    def _process_llm_response(self, response: str, original_key: str):
        """Process LLM response and update change_dict"""
        if response.strip().lower() == "no":
            return
        
        try:
            # Try to extract dictionary from response
            # This is a simplified extraction - you might need more robust parsing
            if "multi_change_dict" in response:
                # Extract the dictionary part
                dict_start = response.find("{")
                dict_end = response.rfind("}") + 1
                dict_str = response[dict_start:dict_end]
                
                # Parse the dictionary (this is simplified - consider using ast.literal_eval)
                changes = eval(dict_str)  
                
                # Update change_dict
                for change_key, change_data in changes.items():
                    if change_key not in self.change_dict:
                        self.change_dict[change_key] = change_data
                    else:
                        # Update existing entry
                        self.change_dict[change_key].update(change_data)
        except Exception as e:
            print(f"Error processing LLM response for {original_key}: {e}")
    

    def _update_files(self, ordered_translations):
        """Update source files based on approved translations in self.change"""
        print("Updating files...")

        # Group valid changes by file
        files_to_update = defaultdict(list)
        for key, change_data in self.change_dict.items():
            if key in ordered_translations:
                file_path = change_data.get('file')
                span = ordered_translations[key].get('span')
                code = self.change_dict[key].get('code')
                if file_path and span and code is not None:
                    files_to_update[file_path].append((span, code))

        # Apply changes to each file
        for file_path, changes in files_to_update.items():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_text = f.read()

                # Sort spans by start index (ascending)
                changes.sort(key=lambda x: x[0][0])

                # Offset to track text length change after insertions
                updated_text = original_text
                offset = 0

                for span, new_code in changes:
                    start, end = span
                    start += offset
                    end += offset

                    # Replace span with new code
                    updated_text = updated_text[:start] + new_code + updated_text[end:]

                    # Update offset
                    offset += len(new_code) - (end - start)

                # Write back updated content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_text)

                print(f"✔ Updated {file_path}")


                # Process each file
                for file_path, changes in files_to_update.items():
                    self._update_single_file(file_path, changes)
                    
            except Exception as e:
                print(f"✖ Error updating {file_path}: {e}")

    
    def _update_single_file(self, file_path: str, changes: List[Tuple[str, Dict]]):
        """Update a single file with changes"""
        try:
            # Load file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Create prompt for LLM
            prompt = f"""
You are expert in React and Java Script.
only update the following file content in order that the user fronting i18n will be valid, assume all imports are correct and existing.
content:
{content}
If change is needed then write down the whole content with the change and nothing else, otherwise write "No" and nothing else.
Your answer:
"""
            
            # Call LLM
            response = self._call_llm(prompt)
            
            # Update file
            if response.strip().lower() != "no":
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(response)
                print(f"Updated file: {file_path}")
            else:
                print(f"No changes needed for file: {file_path}")
                
        except Exception as e:
            print(f"Error updating file {file_path}: {e}")
    
    def _create_translation_files(self):
        """Create translation JSON files"""
        print("Creating translation files...")
        
        locales_dir = self.project_path / 'public' / 'locales'
        
        # Collect all translation keys from change_dict
        translation_keys = {}
        for change_key, change_data in self.change_dict.items():
            # Extract translation keys from the code changes
            # This is a simplified approach - you might need more sophisticated key extraction
            if 'code' in change_data:
                # Look for translation keys in the code
                text = change_data['text']
                # Simple regex or string matching to find i18n keys
                # This should be enhanced based on your i18n library format
                translation_keys[change_key] = text
        
        for lang in self.target_languages:
            lang_dir = locales_dir / lang
            lang_dir.mkdir(parents=True, exist_ok=True)
            
            # Load existing translations if they exist
            translation_file = lang_dir / 'common.json'
            existing_translations = {}
            if translation_file.exists():
                try:
                    with open(translation_file, 'r', encoding='utf-8') as f:
                        existing_translations = json.load(f)
                except Exception as e:
                    print(f"Error loading existing translations for {lang}: {e}")
            
            # Generate translations for new keys
            for key in translation_keys:
                if key not in existing_translations:
                    # Use LLM to generate translation
                    translated_text = self._generate_translation(translation_keys[key], lang)
                    existing_translations[key] = translated_text
            
            # Save updated translations
            with open(translation_file, 'w', encoding='utf-8') as f:
                json.dump(existing_translations, f, ensure_ascii=False, indent=2)
            
            print(f"Created/updated translation file: {translation_file}")
    
    def _generate_translation(self, text: str, target_lang: str) -> str:
        """Generate translation for a given key and language"""
#         prompt = f"""
# You are an expert React and JavaScript developer specializing in internationalization (i18n).

# You are given a JavaScript text snippet that may include function expressions, template strings, or JSX.
# Your task is to extract and translate it into **human-readable string(s)** meant for user display into {target_lang}.
# 2. Keep the surrounding JavaScript syntax **unchanged**.
# 3. Return only the modified text snippet with the translated content, and **nothing else**.

# Text to translate:
# {text}
# """
        prompt = f"""
        You are an expert React and JavaScript developer who specializes in i18n.

        You are given a JavaScript-like string that may contain dynamic expressions such as:
        - Immediately invoked functions like: "{{(() => 'Some message')()}}"
        - i18n expressions like: "{{t('Already translated')}}"
        - Or just raw user-facing strings.

        Your task is:
        - If the input is already an i18n expression like {{t('text')}}, return it unchanged.
        - If the input contains any other kind of user-facing text, or just simple text, **translate the text** to the target language: {target_lang}.

        Only return the final translated user fronting string (i.e., 'translated text') or the original {{t('...')}}. Do not include any explanation or extra output.

        Now process the following input:
        Input: {text}

        Respond with ONLY the translated resulting user-facing text or i18n code.
        """

   
        response = self._call_llm(prompt)
        return response.strip()


def main():
    """
    Main function to demonstrate usage
    """
    # Example usage
    processor = ComplexI18nProcessor(
        openai_client="your-openai-api-key",
        target_languages=['en', 'es', 'fr'],
        project_path="."
    )
    
    # Example input data
    possible_translations = {
        "greeting_text": {
            'text': "Hello World",
            'file': "src/components/Header.jsx",
            'process_ind': 'True',
            'span': (10, 12),
            'occurrences': 1
        }
    }
    
    symbols_dict = {
        "handleLanguageChange": {
            'description': 'Arrow function handleLanguageChange',
            'type': 'arrow_function',
            'span': [67, 70],
            'return_output': 'unknown',
            'dependencies': ['selectedLanguage'],
            'file': 'src/components/Header.jsx',
            'code': 'const handleLanguageChange = (lang) => { setSelectedLanguage(lang); }'
        }
    }
    
    # Process
    complex_i18n_changes = processor.process_complex_i18n(possible_translations, symbols_dict)
    
    return complex_i18n_changes


if __name__ == "__main__":
    # Install required packages first:
    # pip install openai
    
    result = main()
    print("Complex i18n processing completed!")
    print(f"Changes made: {len(result)}")