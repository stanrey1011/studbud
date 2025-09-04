#!/usr/bin/env python3

import json

def fix_match_questions(json_file_path):
    """Fix match type questions to have proper terms, definitions, and correct_mappings format"""
    
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    test_data = data[0]  # Assuming single test in array
    
    for question in test_data['questions']:
        if question['type'] == 'match':
            print(f"Fixing match question {question['id']}: {question['text'][:50]}...")
            
            # For drag-and-drop questions, the options are the items to drag
            # and correct contains the mappings
            
            if question['id'] == 16:  # DMVPN commands
                # Extract individual commands from options
                commands = question['options']
                # Create terms (left side - blanks) and definitions (right side - commands)
                terms = [
                    {"id": "1", "text": "Interface configuration"},
                    {"id": "2", "text": "NHRP authentication"},
                    {"id": "3", "text": "Multicast mapping"},
                    {"id": "4", "text": "NHRP network ID"},
                    {"id": "5", "text": "NHRP redirect"},
                    {"id": "6", "text": "NHRP shortcut"},
                    {"id": "7", "text": "Tunnel mode"},
                    {"id": "8", "text": "Tunnel source"}
                ]
                definitions = []
                for i, cmd in enumerate(commands):
                    definitions.append({"id": str(i+1), "text": cmd})
                
                # Create correct mappings (term ID -> definition ID)
                correct_mappings = {str(i+1): str(i+1) for i in range(len(commands))}
                
            elif question['id'] in [60, 202]:  # GETVPN components
                # Extract components and descriptions from the correct field
                correct_text = question['correct']
                pairs = correct_text.split(', ')
                
                terms = []
                definitions = []
                correct_mappings = {}
                
                for i, pair in enumerate(pairs):
                    if ': ' in pair:
                        term_text, def_text = pair.split(': ', 1)
                        terms.append({"id": str(i+1), "text": term_text})
                        definitions.append({"id": str(i+1), "text": def_text})
                        correct_mappings[str(i+1)] = str(i+1)
                
            elif question['id'] == 83:  # FlexVPN configuration
                # Similar to question 16 - configuration commands
                commands = question['options']
                terms = [
                    {"id": "1", "text": "Keyring definition"},
                    {"id": "2", "text": "Peer definition"},
                    {"id": "3", "text": "Peer address"},
                    {"id": "4", "text": "Local PSK"},
                    {"id": "5", "text": "Remote PSK"},
                    {"id": "6", "text": "IKEv2 profile"},
                    {"id": "7", "text": "Identity matching"},
                    {"id": "8", "text": "Remote authentication"},
                    {"id": "9", "text": "Local authentication"},
                    {"id": "10", "text": "Keyring association"}
                ]
                definitions = []
                for i, cmd in enumerate(commands):
                    definitions.append({"id": str(i+1), "text": cmd})
                
                correct_mappings = {str(i+1): str(i+1) for i in range(len(commands))}
            
            # Update the question with proper match format
            question['terms'] = terms
            question['definitions'] = definitions
            question['correct_mappings'] = correct_mappings
            
            # Remove the old fields
            del question['options']
            del question['correct']
    
    # Save the fixed JSON
    output_file = json_file_path.replace('.json', '_fixed.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Fixed JSON saved to: {output_file}")
    return output_file

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python fix_match_questions.py <json_file>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    fix_match_questions(json_file)