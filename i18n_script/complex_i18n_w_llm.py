import json
import re
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import openai  # or your preferred LLM library

@dataclass
class I18nChange:
    """Represents a single i18n change needed"""
    file: str
    original_text: str
    suggested_key: str
    line_number: int
    column: int
    context: str
    confidence: float
    reason: str

class I18nAnalyzer:
    def __init__(self, openai_client):
        """
        Initialize the i18n analyzer
        
        Args:
            openai_api_key: OpenAI API key for LLM calls
        """
        self.possible_translations = {}
        self.symbols_dict = {}
        self.required_changes = {}
        self.file_changes_tracker = {}  # Track changes made to each file
        self.updated_file_contents = {}  # Store updated file contents
        self.openai_client = openai_client

    def set_data(self, possible_translations: Dict, symbols_dict: Dict):
        """Set the data for analysis and initialize file tracking"""
        self.possible_translations = possible_translations.copy()  # Make a copy to avoid modifying original
        self.symbols_dict = symbols_dict
        self._initialize_file_tracking()
    
    def _initialize_file_tracking(self):
        """Initialize file change tracking"""
        files_to_track = set()
        
        # Get all files from possible_translations
        for info in self.possible_translations.values():
            files_to_track.add(info.get('file', ''))
        
        # Get all files from symbols_dict
        for info in self.symbols_dict.values():
            files_to_track.add(info.get('file', ''))
        
        # Initialize tracking for each file
        for file_path in files_to_track:
            if file_path and file_path != '':
                self.file_changes_tracker[file_path] = {
                    'changes_made': [],
                    'line_offset': 0,  # Track how line numbers have shifted
                    'modified': False
                }
                
                # Load original file content
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.updated_file_contents[file_path] = f.readlines()
                except Exception as e:
                    print(f"Warning: Could not load {file_path}: {str(e)}")
                    self.updated_file_contents[file_path] = []
    
    def analyze_i18n_needs(self) -> Dict[str, Any]:
        """
        Main function that uses LLM to analyze code and identify i18n needs
        
        Returns:
            Dictionary containing analysis results and required changes
        """
        print("🔍 Starting i18n analysis...")
        
        try:
            # Step 1: Prepare context for LLM
            print("📋 Preparing analysis context...")
            context = self._prepare_analysis_context()
            
            # Step 2: Call LLM to analyze code
            print("🤖 Analyzing with LLM...")
            llm_analysis = self._call_llm_for_analysis(context)
            
            # Step 3: Process LLM response and create change dictionary
            print("⚙️  Processing LLM response...")
            changes_dict = self._process_llm_response(llm_analysis)
            
            # Step 4: Cross-reference with possible translations
            print("🔗 Cross-referencing with translations...")
            final_analysis = self._cross_reference_translations(changes_dict)
            
            print(f"✅ Analysis complete! Found {len(final_analysis['required_changes'])} changes in {len(final_analysis['files_needing_changes'])} files")
            
            return final_analysis
            
        except Exception as e:
            print(f"❌ Error during analysis: {str(e)}")
            # Return minimal fallback result
            return {
                "required_changes": {},
                "files_needing_changes": [],
                "sorted_changes_by_position": [],
                "file_changes_tracker": self.file_changes_tracker,
                "updated_possible_translations": self.possible_translations,
                "summary": {"error": str(e)},
                "metadata": {"analysis_failed": True}
            }
    
    def _prepare_analysis_context(self) -> Dict[str, Any]:
        """Prepare context data for LLM analysis"""
        context = {
            "symbols_summary": self._summarize_symbols(),
            "translations_summary": self._summarize_translations(),
            "files_with_strings": self._get_files_with_strings(),
            "component_structure": self._analyze_component_structure()
        }
        return context
    
    def _summarize_symbols(self) -> Dict[str, Any]:
        """Create a summary of symbols for LLM context"""
        summary = {
            "total_symbols": len(self.symbols_dict),
            "by_type": {},
            "files": set(),
            "components": [],
            "functions_with_returns": []
        }
        
        for name, info in self.symbols_dict.items():
            symbol_type = info.get('type', 'unknown')
            summary['by_type'][symbol_type] = summary['by_type'].get(symbol_type, 0) + 1
            summary['files'].add(info.get('file', ''))
            
            if symbol_type == 'react_component':
                summary['components'].append(name)
            elif symbol_type in ['function', 'arrow_function'] and 'string' in str(info.get('return_output', '')):
                summary['functions_with_returns'].append(name)
        
        summary['files'] = list(summary['files'])
        return summary
    
    def _summarize_translations(self) -> Dict[str, Any]:
        """Create a summary of possible translations"""
        summary = {
            "total_strings": len(self.possible_translations),
            "by_confidence": {"True": 0, "Maybe": 0},
            "by_file": {},
            "common_patterns": []
        }
        
        for key, info in self.possible_translations.items():
            confidence = info.get('process_ind', 'Maybe')
            summary['by_confidence'][confidence] = summary['by_confidence'].get(confidence, 0) + 1
            
            file_name = info.get('file', 'unknown')
            if file_name not in summary['by_file']:
                summary['by_file'][file_name] = []
            summary['by_file'][file_name].append({
                'key': key,
                'text': info.get('text', ''),
                'confidence': confidence,
                'occurrences': info.get('occurrences', 1)
            })
        
        return summary
    
    def _get_files_with_strings(self) -> List[str]:
        """Get list of files that contain translatable strings"""
        files = set()
        for info in self.possible_translations.values():
            files.add(info.get('file', ''))
        return list(files)
    
    def _analyze_component_structure(self) -> Dict[str, Any]:
        """Analyze React component structure for i18n context"""
        components = {}
        
        for name, info in self.symbols_dict.items():
            if info.get('type') == 'react_component':
                components[name] = {
                    'file': info.get('file', ''),
                    'dependencies': info.get('dependencies', []),
                    'has_strings': self._component_has_strings(info.get('file', '')),
                    'code_snippet': info.get('code', '')[:500]  # First 500 chars
                }
        
        return components
    
    def _component_has_strings(self, file_path: str) -> bool:
        """Check if a component file has translatable strings"""
        for info in self.possible_translations.values():
            if info.get('file') == file_path:
                return True
        return False
    
    def _call_llm_for_analysis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Call LLM to analyze the code for i18n needs"""
        
        system_prompt = """You are an expert React/JavaScript developer specializing in internationalization (i18n). 
        Your task is to analyze code and identify places that need to be changed for proper i18n implementation.
        
        Focus on:
        1. Hardcoded strings in UI components that should be translated
        2. String concatenation that should use i18n interpolation
        3. Conditional text rendering that needs i18n keys
        4. Error messages and user-facing text
        5. Alt text, titles, and accessibility strings
        
        Avoid flagging:
        - Console logs and debug messages
        - API endpoints and URLs
        - CSS class names and IDs
        - Variable names and function names
        - Technical constants and configuration values
        
        IMPORTANT: Respond ONLY with valid JSON. No additional text or explanations.
        """
        
        user_prompt = f"""
        Please analyze this React/JavaScript project for i18n needs:
        
        PROJECT SUMMARY:
        - Total symbols: {context['symbols_summary']['total_symbols']}
        - Components: {len(context['symbols_summary']['components'])}
        - Files with strings: {len(context['files_with_strings'])}
        - Total translatable strings found: {context['translations_summary']['total_strings']}
        
        COMPONENTS WITH STRINGS:
        {json.dumps(context['component_structure'], indent=2)[:1000]}...
        
        TRANSLATABLE STRINGS BY FILE:
        {json.dumps(context['translations_summary']['by_file'], indent=2)[:2000]}...
        
        Respond with ONLY this JSON format:
        {{
            "files_needing_changes": [
                {{
                    "file": "path/to/file.js",
                    "priority": "high",
                    "changes_needed": [
                        {{
                            "original_text": "Hello World",
                            "suggested_key": "common.hello_world",
                            "line_estimate": 25,
                            "reason": "User-facing text in component",
                            "confidence": 0.95,
                            "i18n_pattern": "t('common.hello_world')"
                        }}
                    ]
                }}
            ],
            "summary": {{
                "total_files": 5,
                "high_priority": 2,
                "estimated_strings": 45,
                "recommendations": ["Use react-i18next", "Create namespace structure"]
            }}
        }}
        """
        
        if self.openai_client:
            try:
                print("🤖 Calling LLM for analysis...")
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    max_tokens=3000,
                    timeout=30  # 30 second timeout
                )
                
                response_content = response.choices[0].message.content.strip()
                print(f"📝 LLM Response received ({len(response_content)} chars)")
                
                # Clean up response - remove any markdown formatting
                if response_content.startswith('```json'):
                    response_content = response_content[7:]
                if response_content.endswith('```'):
                    response_content = response_content[:-3]
                
                response_content = response_content.strip()
                
                # Try to parse JSON
                try:
                    parsed_response = json.loads(response_content)
                    print("✅ LLM response parsed successfully")
                    return parsed_response
                except json.JSONDecodeError as json_err:
                    print(f"❌ JSON parsing failed: {json_err}")
                    print(f"Raw response: {response_content[:500]}...")
                    return self._fallback_analysis(context)
            
            except Exception as e:
                print(f"❌ LLM API call failed: {str(e)}")
                return self._fallback_analysis(context)
        else:
            print("⚠️  No OpenAI API key provided, using fallback analysis")
            return self._fallback_analysis(context)
    
    def _fallback_analysis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback analysis when LLM is not available"""
        print("🔄 Using fallback analysis...")
        
        files_needing_changes = []
        
        try:
            for file_path, strings in context['translations_summary']['by_file'].items():
                if strings:  # File has translatable strings
                    changes_needed = []
                    
                    for string_info in strings:
                        # Only include strings with high confidence or explicit True marking
                        if string_info.get('confidence') == 'True' or len(string_info.get('text', '')) > 3:
                            changes_needed.append({
                                "original_text": string_info['text'],
                                "suggested_key": self._generate_i18n_key(string_info['text']),
                                "line_estimate": 0,  # Would need file parsing to get exact line
                                "reason": "Translatable string detected by pattern matching",
                                "confidence": 0.8 if string_info['confidence'] == 'True' else 0.6,
                                "i18n_pattern": f"{{t('{self._generate_i18n_key(string_info['text'])})}}"
                            })
                    
                    if changes_needed:  # Only add files that have changes
                        files_needing_changes.append({
                            "file": file_path,
                            "priority": "high" if len(changes_needed) > 3 else "medium",
                            "changes_needed": changes_needed
                        })
            
            return {
                "files_needing_changes": files_needing_changes,
                "summary": {
                    "total_files": len(files_needing_changes),
                    "high_priority": len([f for f in files_needing_changes if f['priority'] == 'high']),
                    "estimated_strings": sum(len(f['changes_needed']) for f in files_needing_changes),
                    "recommendations": [
                        "Install react-i18next or similar i18n library",
                        "Create translation files for each language",
                        "Set up i18n provider in your app root",
                        "Replace hardcoded strings with translation keys"
                    ],
                    "analysis_method": "fallback_pattern_matching"
                }
            }
            
        except Exception as e:
            print(f"❌ Fallback analysis also failed: {str(e)}")
            return {
                "files_needing_changes": [],
                "summary": {
                    "total_files": 0,
                    "high_priority": 0,
                    "estimated_strings": 0,
                    "error": f"Both LLM and fallback analysis failed: {str(e)}",
                    "analysis_method": "failed"
                }
            }
    
    def _generate_i18n_key(self, text: str) -> str:
        """Generate a reasonable i18n key from text"""
        # Simple key generation logic
        key = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
        key = re.sub(r'\s+', '_', key.strip())
        key = key[:50]  # Limit length
        return f"common.{key}" if key else "common.unknown"
    
    def _process_llm_response(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """Process the LLM response into our internal format"""
        processed = {
            "analysis_metadata": {
                "timestamp": json.dumps({}),  # Would add actual timestamp
                "llm_used": "gpt-4" if self.openai_client else "fallback",
                "total_files_analyzed": len(self.symbols_dict),
                "total_strings_found": len(self.possible_translations)
            },
            "files_requiring_changes": {},
            "change_summary": llm_response.get('summary', {})
        }
        
        for file_info in llm_response.get('files_needing_changes', []):
            file_path = file_info['file']
            processed['files_requiring_changes'][file_path] = {
                'priority': file_info.get('priority', 'medium'),
                'changes': []
            }
            
            for change in file_info.get('changes_needed', []):
                processed['files_requiring_changes'][file_path]['changes'].append({
                    'original_text': change['original_text'],
                    'suggested_key': change['suggested_key'],
                    'reason': change['reason'],
                    'confidence': change['confidence'],
                    'i18n_pattern': change['i18n_pattern'],
                    'line_estimate': change.get('line_estimate', 0)
                })
        
        return processed
    
    def _cross_reference_translations(self, changes_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-reference LLM suggestions with our possible translations"""
        
        # Create the required_changes dictionary in the format you specified
        self.required_changes = {}
        
        # Process changes in order by file and line position to handle overlapping changes
        all_changes = []
        for file_path, file_info in changes_dict['files_requiring_changes'].items():
            for change in file_info['changes']:
                matching_translation = self._find_matching_translation(change['original_text'])
                if matching_translation:
                    all_changes.append({
                        'file_path': file_path,
                        'change': change,
                        'matching_translation': matching_translation
                    })
        
        # Sort changes by file and estimated line position
        all_changes.sort(key=lambda x: (x['file_path'], x['change'].get('line_estimate', 0)))
        
        # Process each change, updating file contents and spans as we go
        for change_item in all_changes:
            file_path = change_item['file_path']
            change = change_item['change']
            matching_translation = change_item['matching_translation']
            
            key = matching_translation['key']
            translation_info = self.possible_translations[key]
            
            # Check if this file has been modified and update spans accordingly
            updated_translation_info = self._update_translation_span_if_needed(key, translation_info, file_path)
            
            # Get current and modified lines using updated file content
            current_lines, lines_after, span = self._get_line_changes_with_tracking(
                file_path, 
                change['original_text'], 
                change['i18n_pattern'],
                updated_translation_info.get('span', (0, 0))
            )
            
            # Update the file tracking and content
            self._track_file_change(file_path, span, current_lines, lines_after, change['original_text'], change['i18n_pattern'])
            
            # Update the possible_translations with new span if it changed
            if span != updated_translation_info.get('span', (0, 0)):
                self.possible_translations[key]['span'] = span
            
            self.required_changes[key] = {
                'text': change['original_text'],
                'file': file_path,
                'process_ind': updated_translation_info.get('process_ind', 'Maybe'),
                'span': span,
                'occurrences': updated_translation_info.get('occurrences', 1),
                'suggested_key': change['suggested_key'],
                'confidence': change['confidence'],
                'reason': change['reason'],
                'i18n_pattern': change['i18n_pattern'],
                'current_lines_to_change': current_lines,
                'lines_after_change': lines_after,
                'file_was_modified': self.file_changes_tracker[file_path]['modified']
            }
        
        # Create sorted list by file and position
        sorted_changes = self._create_sorted_changes_list()
        
        # Prepare final analysis result
        final_analysis = {
            "required_changes": self.required_changes,
            "files_needing_changes": list(changes_dict['files_requiring_changes'].keys()),
            "sorted_changes_by_position": sorted_changes,
            "file_changes_tracker": self.file_changes_tracker,
            "updated_possible_translations": self.possible_translations,  # Include updated translations
            "summary": changes_dict['change_summary'],
            "metadata": changes_dict['analysis_metadata']
        }
        
        return final_analysis
    
    def _find_matching_translation(self, text: str) -> Optional[Dict[str, Any]]:
        """Find a matching translation from possible_translations"""
        for key, info in self.possible_translations.items():
            if info.get('text', '').strip() == text.strip():
                return {'key': key, 'info': info}
        return None
    
    def _update_translation_span_if_needed(self, key: str, translation_info: Dict, file_path: str) -> Dict:
        """Update translation span if the file has been modified"""
        if not self.file_changes_tracker.get(file_path, {}).get('modified', False):
            return translation_info  # No changes made to this file yet
        
        original_span = translation_info.get('span', (0, 0))
        if original_span == (0, 0):
            return translation_info  # No valid span to update
        
        # Calculate new span based on previous changes
        line_offset = self.file_changes_tracker[file_path]['line_offset']
        new_span = (original_span[0] + line_offset, original_span[1] + line_offset)
        
        # Update the translation info
        updated_info = translation_info.copy()
        updated_info['span'] = new_span
        
        return updated_info
    
    def _track_file_change(self, file_path: str, span: Tuple[int, int], 
                          current_lines: List[str], new_lines: List[str], 
                          original_text: str, replacement: str):
        """Track changes made to a file and update line offsets"""
        
        if file_path not in self.file_changes_tracker:
            return
        
        tracker = self.file_changes_tracker[file_path]
        
        # Record this change
        change_record = {
            'span': span,
            'original_lines': current_lines,
            'new_lines': new_lines,
            'original_text': original_text,
            'replacement': replacement,
            'lines_changed': len(new_lines) - len(current_lines)
        }
        
        tracker['changes_made'].append(change_record)
        tracker['modified'] = True
        
        # Update line offset for subsequent changes
        lines_difference = len(new_lines) - len(current_lines)
        tracker['line_offset'] += lines_difference
        
        # Update the file content in memory
        if file_path in self.updated_file_contents:
            start_line = max(0, span[0] - 1)
            end_line = min(len(self.updated_file_contents[file_path]), span[1])
            
            # Replace the lines in the updated content
            before = self.updated_file_contents[file_path][:start_line]
            after = self.updated_file_contents[file_path][end_line:]
            new_content = [line + '\n' for line in new_lines]
            
            self.updated_file_contents[file_path] = before + new_content + after
    
    def _get_line_changes_with_tracking(self, file_path: str, original_text: str, i18n_pattern: str, 
                                      original_span: Tuple[int, int]) -> Tuple[List[str], List[str], Tuple[int, int]]:
        """
        Get line changes using the current (possibly modified) file content
        """
        try:
            # Use updated file content if available
            if file_path in self.updated_file_contents:
                file_lines = self.updated_file_contents[file_path]
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_lines = f.readlines()
            
            # Find the lines containing the original text
            current_lines = []
            lines_after = []
            start_line = max(0, original_span[0] - 1) if original_span[0] > 0 else 0
            end_line = min(len(file_lines), original_span[1]) if original_span[1] > 0 else len(file_lines)
            
            # If span is not available, search for the text in current file content
            if original_span == (0, 0):
                start_line, end_line = self._find_text_in_file_lines(file_lines, original_text)
            
            # Extract current lines and create modified versions
            for i in range(start_line, end_line):
                if i < len(file_lines):
                    current_line = file_lines[i]
                    current_lines.append(current_line.rstrip('\n'))
                    
                    # Replace the original text with i18n pattern
                    if original_text in current_line:
                        modified_line = current_line.replace(original_text, i18n_pattern)
                        lines_after.append(modified_line.rstrip('\n'))
                    else:
                        lines_after.append(current_line.rstrip('\n'))
            
            # Update span based on actual findings
            actual_span = (start_line + 1, end_line) if start_line < end_line else original_span
            
            return current_lines, lines_after, actual_span
            
        except Exception as e:
            print(f"Warning: Could not read file {file_path}: {str(e)}")
            return [f"Error reading file: {str(e)}"], [f"Error reading file: {str(e)}"], original_span
    
    def _find_text_in_file_lines(self, file_lines: List[str], text: str) -> Tuple[int, int]:
        """Find the line range where text appears in file lines"""
        for i, line in enumerate(file_lines):
            if text in line:
                return i, i + 1
        return 0, 1  # Default if not found
    
    def _create_sorted_changes_list(self) -> List[Dict[str, Any]]:
        """
        Create a sorted list of changes by file name and position in file
        
        Returns:
            List of changes sorted by file and line position
        """
        changes_list = []
        
        for key, change_info in self.required_changes.items():
            changes_list.append({
                'key': key,
                'file': change_info['file'],
                'span': change_info['span'],
                'line_start': change_info['span'][0],
                'text': change_info['text'],
                'suggested_key': change_info['suggested_key'],
                'i18n_pattern': change_info['i18n_pattern'],
                'confidence': change_info['confidence'],
                'process_ind': change_info['process_ind'],
                'current_lines_to_change': change_info['current_lines_to_change'],
                'lines_after_change': change_info['lines_after_change'],
                'reason': change_info['reason'],
                'occurrences': change_info['occurrences'],
                'file_was_modified': change_info.get('file_was_modified', False)
            })
        
        # Sort by file name first, then by line position
        changes_list.sort(key=lambda x: (x['file'], x['line_start']))
        
        return changes_list
    
    def get_updated_file_contents(self, file_path: str) -> List[str]:
        """Get the updated file contents after all changes"""
        return self.updated_file_contents.get(file_path, [])
    
    def save_updated_files(self, backup: bool = True):
        """Save all updated files to disk"""
        for file_path, content in self.updated_file_contents.items():
            if self.file_changes_tracker.get(file_path, {}).get('modified', False):
                try:
                    # Create backup if requested
                    if backup:
                        backup_path = f"{file_path}.backup"
                        with open(file_path, 'r', encoding='utf-8') as original:
                            with open(backup_path, 'w', encoding='utf-8') as backup_file:
                                backup_file.write(original.read())
                        print(f"✅ Backup created: {backup_path}")
                    
                    # Save updated content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(content)
                    print(f"✅ Updated file saved: {file_path}")
                    
                except Exception as e:
                    print(f"❌ Error saving {file_path}: {str(e)}")
    
    def get_file_change_summary(self) -> Dict[str, Any]:
        """Get a summary of all file changes made"""
        summary = {
            'files_modified': 0,
            'total_changes': 0,
            'files_details': {}
        }
        
        for file_path, tracker in self.file_changes_tracker.items():
            if tracker['modified']:
                summary['files_modified'] += 1
                summary['total_changes'] += len(tracker['changes_made'])
                summary['files_details'][file_path] = {
                    'changes_count': len(tracker['changes_made']),
                    'line_offset': tracker['line_offset'],
                    'changes': tracker['changes_made']
                }
        
        return summary
    
    def generate_i18n_report(self, analysis_result: Dict[str, Any]) -> str:
        """Generate a human-readable report of the i18n analysis"""
        
        report = ["# i18n Analysis Report\n"]
        
        # Summary
        summary = analysis_result.get('summary', {})
        report.append(f"## Summary")
        report.append(f"- **Total files needing changes:** {len(analysis_result['files_needing_changes'])}")
        report.append(f"- **High priority files:** {summary.get('high_priority', 0)}")
        report.append(f"- **Estimated strings to translate:** {summary.get('estimated_strings', 0)}")
        report.append(f"- **Total changes identified:** {len(analysis_result['required_changes'])}")
        report.append("")
        
        # Sorted changes by file and position
        report.append("## Changes by File and Position")
        sorted_changes = analysis_result.get('sorted_changes_by_position', [])
        
        current_file = None
        for change in sorted_changes:
            # New file section
            if change['file'] != current_file:
                current_file = change['file']
                report.append(f"### {current_file}")
                report.append("")
            
            # Change details
            report.append(f"**Line {change['line_start']} - Key: `{change['key']}`**")
            report.append(f"- **Original text:** `{change['text']}`")
            report.append(f"- **Suggested key:** `{change['suggested_key']}`")
            report.append(f"- **i18n pattern:** `{change['i18n_pattern']}`")
            report.append(f"- **Confidence:** {change['confidence']:.2f}")
            report.append(f"- **Occurrences:** {change['occurrences']}")
            
            # Show current and modified lines
            if change['current_lines_to_change']:
                report.append("- **Current code:**")
                for line in change['current_lines_to_change']:
                    report.append(f"  ```javascript\n  {line}\n  ```")
                
                report.append("- **After i18n:**")
                for line in change['lines_after_change']:
                    report.append(f"  ```javascript\n  {line}\n  ```")
            
            report.append("")
        
        # Files needing changes summary
        report.append("## Files Summary")
        for file_path in analysis_result['files_needing_changes']:
            file_changes = [change for change in sorted_changes if change['file'] == file_path]
            high_confidence = len([c for c in file_changes if c['confidence'] > 0.8])
            
            report.append(f"- **{file_path}:** {len(file_changes)} changes ({high_confidence} high confidence)")
        
        report.append("")
        
        # Recommendations
        recommendations = summary.get('recommendations', [])
        if recommendations:
            report.append("## Recommendations")
            for rec in recommendations:
                report.append(f"- {rec}")
        
        return "\n".join(report)
    
    def export_changes_summary(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Export a clean summary of all changes for easy processing"""
        
        summary = {
            "total_changes": len(analysis_result['required_changes']),
            "files_affected": len(analysis_result['files_needing_changes']),
            "changes_by_file": {},
            "high_confidence_changes": 0,
            "medium_confidence_changes": 0,
            "low_confidence_changes": 0
        }
        
        # Group changes by file
        for change in analysis_result.get('sorted_changes_by_position', []):
            file_path = change['file']
            if file_path not in summary['changes_by_file']:
                summary['changes_by_file'][file_path] = []
            
            summary['changes_by_file'][file_path].append({
                'line': change['line_start'],
                'key': change['key'],
                'original': change['text'],
                'replacement': change['i18n_pattern'],
                'confidence': change['confidence']
            })
            
            # Count by confidence level
            if change['confidence'] > 0.8:
                summary['high_confidence_changes'] += 1
            elif change['confidence'] > 0.6:
                summary['medium_confidence_changes'] += 1
            else:
                summary['low_confidence_changes'] += 1
        
        return summary

# Usage example
def analyze_project_i18n(possible_translations: Dict, symbols_dict: Dict, 
                        openai_client) -> Dict[str, Any]:
    """
    Main function to analyze project for i18n needs
    
    Args:
        possible_translations: Dictionary of possible translations
        symbols_dict: Dictionary of code symbols
        openai_api_key: Optional OpenAI API key for LLM analysis
        
    Returns:
        Analysis results with required changes
    """
    try:
        print("🚀 Initializing i18n analyzer...")
        analyzer = I18nAnalyzer(openai_client)
        analyzer.set_data(possible_translations, symbols_dict)
        
        # Run analysis with timeout protection
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Analysis timed out after 60 seconds")
        
        # Set up timeout (60 seconds)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(60)
        
        try:
            result = analyzer.analyze_i18n_needs()
            signal.alarm(0)  # Cancel timeout
            return result
        except TimeoutError:
            signal.alarm(0)  # Cancel timeout
            print("⏰ Analysis timed out, returning basic analysis...")
            return {
                "required_changes": {},
                "files_needing_changes": list(set(info.get('file', '') for info in possible_translations.values())),
                "sorted_changes_by_position": [],
                "file_changes_tracker": analyzer.file_changes_tracker,
                "updated_possible_translations": possible_translations,
                "summary": {"error": "Analysis timed out", "timeout": True},
                "metadata": {"analysis_failed": True, "reason": "timeout"}
            }
            
    except Exception as e:
        print(f"❌ Critical error in analyze_project_i18n: {str(e)}")
        return {
            "required_changes": {},
            "files_needing_changes": [],
            "sorted_changes_by_position": [],
            "file_changes_tracker": {},
            "updated_possible_translations": possible_translations,
            "summary": {"error": str(e)},
            "metadata": {"analysis_failed": True, "reason": "exception"}
        }

# Example usage
if __name__ == "__main__":
    # Example data (replace with your actual data)
    possible_translations = {
        "hello_world": {
            'text': 'Hello World',
            'file': 'src/components/App.js',
            'process_ind': 'True',
            'span': (10, 12),
            'occurrences': 2
        },
        "welcome_message": {
            'text': 'Welcome to our app!',
            'file': 'src/components/App.js',  # Same file to test tracking
            'process_ind': 'Maybe',
            'span': (15, 16),
            'occurrences': 1
        },
        "button_text": {
            'text': 'Click me',
            'file': 'src/components/Header.js',
            'process_ind': 'True',
            'span': (8, 9),
            'occurrences': 1
        }
    }
    
    symbols_dict = {
        "App": {
            "type": "react_component",
            "file": "src/components/App.js",
            "dependencies": ["useState", "useEffect"],
            "code": "const App = () => { return <div><h1>Hello World</h1><p>Welcome to our app!</p></div>; }"
        },
        "Header": {
            "type": "react_component", 
            "file": "src/components/Header.js",
            "dependencies": [],
            "code": "const Header = () => { return <button>Click me</button>; }"
        }
    }
    
    # Run analysis
    print("🚀 Starting i18n analysis with file change tracking...")
    # results = analyze_project_i18n(possible_translations, symbols_dict, openai_client)
    
    # Print file change tracking summary
    analyzer = I18nAnalyzer()
    analyzer.set_data(possible_translations, symbols_dict)
    
    print("\n=== FILE CHANGE TRACKING SUMMARY ===")
    change_summary = analyzer.get_file_change_summary()
    print(json.dumps(change_summary, indent=2))
    
    print("\n=== UPDATED POSSIBLE TRANSLATIONS ===")
    updated_translations = results.get('updated_possible_translations', {})
    for key, info in updated_translations.items():
        original = possible_translations.get(key, {})
        if info.get('span') != original.get('span'):
            print(f"Key '{key}': span updated from {original.get('span')} to {info.get('span')}")
    
    print("\n=== SORTED CHANGES BY FILE AND POSITION ===")
    for change in results['sorted_changes_by_position']:
        print(f"File: {change['file']}, Line: {change['line_start']}")
        print(f"  Original: {change['text']}")
        print(f"  Replace with: {change['i18n_pattern']}")
        print(f"  File was modified: {change['file_was_modified']}")
        print(f"  Current lines: {change['current_lines_to_change']}")
        print(f"  After change: {change['lines_after_change']}")
        print()
    
    # Generate detailed report
    report = analyzer.generate_i18n_report(results)
    print(report)
    
    # Export summary
    summary = analyzer.export_changes_summary(results)
    print("\n=== CHANGES SUMMARY ===")
    print(json.dumps(summary, indent=2))
    
    # Save results with file tracking
    with open('i18n_analysis_with_tracking.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    with open('i18n_changes_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
        
    # Optionally save updated files (commented out for safety)
    # analyzer.save_updated_files(backup=True)
    
    print("\n✅ Analysis complete with file change tracking!")