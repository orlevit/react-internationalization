import ast
import re
import os
from typing import Dict, List, Tuple, Any, Optional
import json

class ReactJSParser:
    def __init__(self):
        self.symbols = {}
        self.current_file = None
        self.file_content = None
        
    def parse_files(self, react_files: List[str]) -> Dict[str, Any]:
        """
        Parse a list of React/JS files and extract symbols
        
        Args:
            react_files: List of file paths to React/JS files
            
        Returns:
            Dictionary containing all extracted symbols
        """
        for file_path in react_files:
            if os.path.exists(file_path):
                self.parse_file(file_path)
            else:
                print(f"Warning: File {file_path} not found")
                
        return self.symbols
    
    def parse_file(self, file_path: str):
        """Parse a single React/JS file"""
        self.current_file = file_path
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.file_content = f.read()
            
            # Try to parse as JavaScript/React using regex patterns
            # Since Python's AST is for Python, we'll use regex-based parsing
            self._extract_functions()
            self._extract_classes()
            self._extract_constants()
            self._extract_variables()
            self._extract_arrow_functions()
            self._extract_react_components()
            
        except Exception as e:
            print(f"Error parsing {file_path}: {str(e)}")
    
    def _get_line_number(self, start_pos: int) -> int:
        """Get line number from character position"""
        return self.file_content[:start_pos].count('\n') + 1
    
    def _get_span(self, match) -> Tuple[int, int]:
        """Get span (start, end) from regex match"""
        start_line = self._get_line_number(match.start())
        end_line = self._get_line_number(match.end())
        return (start_line, end_line)
    
    def _extract_dependencies(self, code: str) -> List[str]:
        """Extract function calls and variable references from code"""
        dependencies = []
        
        # Function calls: functionName(...)
        func_calls = re.findall(r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(', code)
        dependencies.extend(func_calls)
        
        # Variable references (excluding keywords)
        js_keywords = {
            'const', 'let', 'var', 'function', 'class', 'if', 'else', 'for', 
            'while', 'do', 'switch', 'case', 'break', 'continue', 'return',
            'true', 'false', 'null', 'undefined', 'this', 'super', 'new',
            'typeof', 'instanceof', 'in', 'of', 'delete', 'void'
        }
        
        var_refs = re.findall(r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\b', code)
        dependencies.extend([var for var in var_refs if var not in js_keywords])
        
        # Remove duplicates and return
        return list(set(dependencies))
    
    def _extract_return_type(self, code: str) -> Optional[str]:
        """Try to infer return type from code"""
        # Look for return statements
        return_matches = re.findall(r'return\s+([^;]+)', code)
        if return_matches:
            return_val = return_matches[-1].strip()
            if return_val.startswith('"') or return_val.startswith("'"):
                return "string"
            elif return_val.startswith('['):
                return "array"
            elif return_val.startswith('{'):
                return "object"
            elif return_val in ['true', 'false']:
                return "boolean"
            elif return_val.isdigit():
                return "number"
        return "unknown"
    
    def _extract_functions(self):
        """Extract regular function declarations"""
        pattern = r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^)]*\)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.finditer(pattern, self.file_content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            func_name = match.group(1)
            full_code = match.group(0)
            
            self.symbols[func_name] = {
                "description": f"Function {func_name}",
                "type": "function",
                "span": self._get_span(match),
                "return_output": self._extract_return_type(full_code),
                "dependencies": self._extract_dependencies(full_code),
                "file": self.current_file,
                "code": full_code.strip()
            }
    
    def _extract_arrow_functions(self):
        """Extract arrow function declarations"""
        # const/let/var funcName = (...) => { ... }
        pattern = r'(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*\([^)]*\)\s*=>\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.finditer(pattern, self.file_content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            func_name = match.group(1)
            full_code = match.group(0)
            
            self.symbols[func_name] = {
                "description": f"Arrow function {func_name}",
                "type": "arrow_function",
                "span": self._get_span(match),
                "return_output": self._extract_return_type(full_code),
                "dependencies": self._extract_dependencies(full_code),
                "file": self.current_file,
                "code": full_code.strip()
            }
    
    def _extract_classes(self):
        """Extract class declarations"""
        pattern = r'class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:extends\s+[a-zA-Z_$][a-zA-Z0-9_$]*)?\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.finditer(pattern, self.file_content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            class_name = match.group(1)
            full_code = match.group(0)
            
            self.symbols[class_name] = {
                "description": f"Class {class_name}",
                "type": "class",
                "span": self._get_span(match),
                "return_output": "class_instance",
                "dependencies": self._extract_dependencies(full_code),
                "file": self.current_file,
                "code": full_code.strip()
            }
    
    def _extract_constants(self):
        """Extract constant declarations"""
        pattern = r'const\s+([A-Z_][A-Z0-9_]*)\s*=\s*([^;]+);?'
        matches = re.finditer(pattern, self.file_content)
        
        for match in matches:
            const_name = match.group(1)
            const_value = match.group(2).strip()
            
            self.symbols[const_name] = {
                "description": f"Constant {const_name}",
                "type": "constant",
                "span": self._get_span(match),
                "return_output": self._infer_type(const_value),
                "dependencies": self._extract_dependencies(const_value),
                "file": self.current_file,
                "code": match.group(0).strip()
            }
    
    def _extract_variables(self):
        """Extract variable declarations"""
        pattern = r'(?:let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*([^;]+);?'
        matches = re.finditer(pattern, self.file_content)
        
        for match in matches:
            var_name = match.group(1)
            var_value = match.group(2).strip()
            
            # Skip if it's already captured as a function
            if var_name not in self.symbols:
                self.symbols[var_name] = {
                    "description": f"Variable {var_name}",
                    "type": "variable",
                    "span": self._get_span(match),
                    "return_output": self._infer_type(var_value),
                    "dependencies": self._extract_dependencies(var_value),
                    "file": self.current_file,
                    "code": match.group(0).strip()
                }
    
    def _extract_react_components(self):
        """Extract React component declarations"""
        # React functional components
        pattern = r'(?:const|let|var)\s+([A-Z][a-zA-Z0-9_$]*)\s*=\s*\([^)]*\)\s*=>\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.finditer(pattern, self.file_content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            component_name = match.group(1)
            full_code = match.group(0)
            
            self.symbols[component_name] = {
                "description": f"React component {component_name}",
                "type": "react_component",
                "span": self._get_span(match),
                "return_output": "jsx_element",
                "dependencies": self._extract_dependencies(full_code),
                "file": self.current_file,
                "code": full_code.strip()
            }
    
    def _infer_type(self, value: str) -> str:
        """Infer the type of a value"""
        value = value.strip()
        if value.startswith('"') or value.startswith("'") or value.startswith('`'):
            return "string"
        elif value.startswith('['):
            return "array"
        elif value.startswith('{'):
            return "object"
        elif value in ['true', 'false']:
            return "boolean"
        elif value.replace('.', '').isdigit():
            return "number"
        else:
            return "unknown"

# Usage example
def parse_react_project(react_files: List[str]) -> Dict[str, Any]:
    """
    Main function to parse React project files
    
    Args:
        react_files: List of React/JS file paths
        
    Returns:
        Dictionary with extracted symbols
    """
    parser = ReactJSParser()
    return parser.parse_files(react_files)

# Example usage:
if __name__ == "__main__":
    # Example file list
    react_files = [
        "src/components/App.js",
        "src/utils/helpers.js",
        "src/components/Header.jsx",
        # Add your actual file paths here
    ]
    
    # Parse the files
    symbols_dict = parse_react_project(react_files)
    
    # Print results
    print(json.dumps(symbols_dict, indent=2))
    
    # Example of accessing specific symbol
    if "getAllRecords" in symbols_dict:
        print(f"\nFunction: {symbols_dict['getAllRecords']}")
    
    # Save to file
    with open('react_symbols.json', 'w', encoding='utf-8') as f:
        json.dump(symbols_dict, f, indent=2, ensure_ascii=False)
