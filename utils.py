import json
import zipfile
import os
from io import BytesIO
from flask import current_app

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def calculate_score(questions, user_answers):
    score = 0
    for question in questions:
        user_ans = user_answers.get(str(question.id))
        if question.type == 'mrq':
            correct = question.correct.split(', ') if question.correct else []
            user_ans = user_ans if isinstance(user_ans, list) else []
            if sorted(correct) == sorted(user_ans):
                score += 1
        elif question.type == 'tf':
            if str(user_ans).lower() == str(question.correct).lower():
                score += 1
        elif question.type == 'match':
            if user_ans and question.correct:
                correct_mappings = json.loads(question.correct)
                correct_count = sum(1 for term_id, def_id in user_ans.items()
                                   if correct_mappings.get(term_id) == def_id)
                score += correct_count / len(correct_mappings) if correct_mappings else 0.0
        else:
            if user_ans == question.correct:
                score += 1
    return score

def allowed_import_file(filename):
    """Check if file is allowed for import (JSON or ZIP)"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'json', 'zip'}

def create_test_zip(test_data, images_data):
    """Create a ZIP archive containing test data and images
    
    Args:
        test_data: List of test dictionaries (JSON serializable)
        images_data: Dictionary mapping image filenames to file paths
    
    Returns:
        BytesIO object containing the ZIP archive
    """
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add test data as JSON
        test_json = json.dumps(test_data, indent=4, ensure_ascii=False)
        zip_file.writestr('test_data.json', test_json)
        
        # Add images
        upload_folder = current_app.config['UPLOAD_FOLDER']
        for image_filename, image_path in images_data.items():
            if image_filename and os.path.exists(image_path):
                # Add to images/ folder in ZIP
                zip_path = f'images/{image_filename}'
                zip_file.write(image_path, zip_path)
    
    zip_buffer.seek(0)
    return zip_buffer

def extract_test_zip(zip_file):
    """Extract test data and images from ZIP file
    
    Args:
        zip_file: File-like object containing ZIP archive
    
    Returns:
        tuple: (test_data_json, extracted_images_dict)
            test_data_json: Parsed JSON data
            extracted_images_dict: Dict mapping filenames to BytesIO objects
    """
    test_data = None
    extracted_images = {}
    
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        # Validate ZIP structure
        file_list = zip_ref.namelist()
        
        if 'test_data.json' not in file_list:
            raise ValueError("ZIP file must contain 'test_data.json'")
        
        # Extract test data
        with zip_ref.open('test_data.json') as json_file:
            test_data = json.load(json_file)
        
        # Extract images
        for filename in file_list:
            if filename.startswith('images/') and not filename.endswith('/'):
                image_filename = filename.replace('images/', '')
                
                # Validate image file extension
                if allowed_file(image_filename):
                    with zip_ref.open(filename) as img_file:
                        extracted_images[image_filename] = BytesIO(img_file.read())
    
    return test_data, extracted_images

def save_extracted_images(extracted_images):
    """Save extracted images to the uploads folder
    
    Args:
        extracted_images: Dict mapping filenames to BytesIO objects
    
    Returns:
        list: List of successfully saved image filenames
    """
    upload_folder = current_app.config['UPLOAD_FOLDER']
    saved_images = []
    
    # Ensure upload folder exists
    os.makedirs(upload_folder, exist_ok=True)
    
    for filename, image_data in extracted_images.items():
        try:
            file_path = os.path.join(upload_folder, filename)
            
            # Handle filename conflicts by adding a number
            original_filename = filename
            counter = 1
            while os.path.exists(file_path):
                name, ext = os.path.splitext(original_filename)
                filename = f"{name}_{counter}{ext}"
                file_path = os.path.join(upload_folder, filename)
                counter += 1
            
            # Save the image
            with open(file_path, 'wb') as f:
                f.write(image_data.getvalue())
            
            saved_images.append(filename)
            
        except Exception as e:
            print(f"Error saving image {filename}: {str(e)}")
            continue
    
    return saved_images