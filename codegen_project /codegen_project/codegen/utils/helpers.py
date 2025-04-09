import json

def extract_json_array(response_text):
    """
    Extracts a JSON array from the AI response text.
    """
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return None  # Return None if parsing fails

def process_file_content(file_list):
    """
    Ensures all file contents are strings and strips whitespace.
    """
    processed = []
    for file in file_list:
        if isinstance(file, dict) and 'filename' in file and 'content' in file:
            processed.append({
                'filename': file['filename'].strip(),
                'content': str(file['content']).strip()
            })
    return processed

