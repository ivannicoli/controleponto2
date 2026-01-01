import os
import cv2
import numpy as np
import pytesseract
import re
from flask import Flask, render_template, request, jsonify
from PIL import Image

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configure regex for parsing lines
# Looking for something like: "1 Seg 08:17 11:32 ..."
# Adjust regex to be flexible with OCR noise
LINE_REGEX = re.compile(r'(\d{1,2})\s+([a-zA-Z\u00C0-\u00FF\.]{3,4})\s+(.*)')
TIME_REGEX = re.compile(r'(\d{1,2}:\d{2})')

def preprocess_image(path):
    img = cv2.imread(path)
    if img is None: return None
    
    # 1. Resize (2x is solid)
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    # 2. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 3. Adaptive Thresholding (The Fix for Shadows)
    # Using a LARGE block size (99) makes it behave like a global threshold locally.
    # High C (25) ensures we aggressively remove the background (blue/gray) even if darker.
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 99, 25
    )
    
    # 4. Remove Table Lines (Smart Grid Removal)
    # Invert: Text/Lines=White, BG=Black
    img_bin = 255 - thresh
    
    # Kernel definition
    # Make vertical kernel very tall (1/25th of height) to avoid mistaking the number '1' for a line
    kernel_len_ver = max(img.shape[0] // 25, 20) 
    kernel_len_hor = max(img.shape[1] // 35, 20)
    
    ver_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_len_ver))
    hor_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len_hor, 1))
    
    # Detect lines
    vertical_lines = cv2.erode(img_bin, ver_kernel, iterations=1)
    vertical_lines = cv2.dilate(vertical_lines, ver_kernel, iterations=1)
    
    horizontal_lines = cv2.erode(img_bin, hor_kernel, iterations=1)
    horizontal_lines = cv2.dilate(horizontal_lines, hor_kernel, iterations=1)
    
    # Combine lines
    grid_mask = cv2.add(vertical_lines, horizontal_lines)
    
    # Dilate grid mask slightly
    grid_mask = cv2.dilate(grid_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)), iterations=1)
    
    # Subtract grid from binary image
    img_no_grid = cv2.subtract(img_bin, grid_mask)
    
    # Invert back: Text=Black, BG=White
    result = 255 - img_no_grid
    
    # 5. Text Thickening & Noise removal
    # Erode (darken) the text slightly so thin numbers like '1' do not disappear or break
    kernel = np.ones((2,2), np.uint8)
    result = cv2.erode(result, kernel, iterations=1)
    
    # Gaussian blur to smooth pixelation
    result = cv2.GaussianBlur(result, (3, 3), 0)
    _, result = cv2.threshold(result, 128, 255, cv2.THRESH_BINARY)
    
    return result

def fix_common_ocr_errors(text):
    # Common replacements for digits
    replacements = {
        'O': '0', 'o': '0',
        'I': '1', 'l': '1', 'i': '1', 'L': '1', '!': '1', '|': '1',
        'B': '8', 'b': '6', # b sometimes is 6
        'S': '5', 's': '5',
        'Z': '2', 'z': '2',
        '.': ':', ',': ':', ';': ':'
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text

def extract_data(image_path):
    processed_img = preprocess_image(image_path)
    if processed_img is None: return []
    
    custom_config = r'--oem 3 --psm 6'
    
    try:
        text = pytesseract.image_to_string(processed_img, config=custom_config, lang='por+eng')
    except Exception as e:
        print(f"OCR Error: {e}")
        return []
        
    print("DEBUG OCR TYPE 1:\n", text)
        
    results = []
    lines = text.split('\n')
    
    current_day = None
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 1. Clean line broadly
        clean_line = re.sub(r'[^0-9a-zA-Z\s\.:,;!|]', '', line)
        parts = clean_line.split()
        if not parts: continue
        
        # 2. Check for Day Number
        day_num = None
        # Must be at the VERY START of the line to be a new day row
        first_token_clean = re.sub(r'[^0-9]', '', parts[0])
        if first_token_clean.isdigit():
            val = int(first_token_clean)
            if 1 <= val <= 31:
                day_num = val

        # 3. Extract Times using Regex
        fixed_line = fix_common_ocr_errors(line)
        times = re.findall(r'(\d{1,2}:\d{2})', fixed_line)
        
        # Fallback: orphaned number pairs
        if len(times) < 2:
             extra_candidates = re.findall(r'\b(\d{2})[\s:]?(\d{2})\b', fixed_line)
             for t in extra_candidates:
                 formatted = f"{t[0]}:{t[1]}"
                 if formatted not in times:
                     times.append(formatted)

        # LOGIC BRANCH: New Day vs Orphan Data
        if day_num is not None:
            # NEW DAY ROW
            current_day = {
                'day': day_num,
                'weekday': parts[1] if len(parts) > 1 and not parts[1][0].isdigit() else '',
                'times': times # temporary list
            }
            results.append(current_day)
        
        elif current_day is not None and len(times) > 0:
            # ORPHAN LINE (likely belongs to the day above)
            # Check if these times are not already in the day to avoid dupes
            for t in times:
                if t not in current_day['times']:
                    current_day['times'].append(t)
    
    # 4. Final Formatting
    final_output = []
    
    # Deduplicate days - keep the one with most times found
    deduped_results = {}
    for r in results:
        d = r['day']
        if d not in deduped_results:
            deduped_results[d] = r
        else:
            if len(r['times']) > len(deduped_results[d]['times']):
                deduped_results[d] = r
                
    # Sort times and flatten to m1..m4
    for d, r in deduped_results.items():
        # Filter valid times (00:00 to 23:59) just in case
        valid_times = []
        for t in r['times']:
            try:
                h, m = map(int, t.split(':'))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    valid_times.append(f"{h:02d}:{m:02d}")
            except: pass
            
        valid_times.sort()
        
        final_output.append({
            'day': r['day'],
            'weekday': r['weekday'],
            'm1': valid_times[0] if len(valid_times) > 0 else '',
            'm2': valid_times[1] if len(valid_times) > 1 else '',
            'm3': valid_times[2] if len(valid_times) > 2 else '',
            'm4': valid_times[3] if len(valid_times) > 3 else '',
        })
            
    return sorted(final_output, key=lambda x: x['day'])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        
        try:
            data = extract_data(filepath)
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
