import os
import sys
import json
import random
import socket
import threading
import webbrowser
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3

# Configure paths for PyInstaller
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    application_path = sys._MEIPASS
    user_data_dir = Path.home() / "naeilum"
else:
    # Running in normal Python environment
    application_path = os.path.dirname(os.path.abspath(__file__))
    user_data_dir = Path(application_path) / "naeilum"

# Create user data directory
user_data_dir.mkdir(exist_ok=True)
(user_data_dir / "logs").mkdir(exist_ok=True)

# Configure logging
log_file = user_data_dir / "logs" / f"naeilum_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
    static_folder=os.path.join(application_path, 'static'),
    template_folder=os.path.join(application_path, 'templates'))
app.config['SECRET_KEY'] = 'naeilum-2024-secret-key'

# Load data files
def load_json_data(filename):
    """Load JSON data from file"""
    try:
        file_path = os.path.join(application_path, 'data', filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {filename}: {e}")
        return {}

SYLLABLES_DATA = load_json_data('syllables.json')
FORTUNES_DATA = load_json_data('fortunes.json')
SURNAMES_DATA = load_json_data('surnames.json')

# Initialize database
def init_database():
    """Initialize SQLite database for storing selections"""
    db_path = user_data_dir / "naeilum.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            first_name TEXT,
            last_name TEXT,
            chosen_name_kr TEXT,
            chosen_name_hanja TEXT,
            tags TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# Name generation algorithm
def get_korean_surname(last_name):
    """Map English last name to Korean surname"""
    if not last_name:
        return random.choice(SURNAMES_DATA.get("DEFAULT", [{"korean": "이", "hanja": "李"}]))

    initial = last_name[0].upper()

    # Special case for Smith -> Song (for demo)
    if last_name.upper() == "SMITH":
        return {"korean": "송", "hanja": "宋"}

    surname_options = SURNAMES_DATA.get(initial, SURNAMES_DATA.get("DEFAULT"))

    # Weighted random selection
    weights = [s.get("weight", 1) for s in surname_options]
    total_weight = sum(weights)
    rand = random.uniform(0, total_weight)

    cumulative = 0
    for surname, weight in zip(surname_options, weights):
        cumulative += weight
        if rand <= cumulative:
            return surname

    return surname_options[0]

def generate_korean_names(first_name, last_name, options=None):
    """Generate Korean name candidates"""
    if options is None:
        options = {}

    tags = options.get('tags', ['밝음', '지혜'])
    gender = options.get('gender', 'neutral')

    # Get Korean surname
    surname = get_korean_surname(last_name)

    # Special handling for Wilson Smith
    if first_name.upper() == "WILSON" and last_name.upper() == "SMITH":
        # Ensure Song Wil-Seon is included
        candidates = [{
            "name_kr": "송월선",
            "name_en": "Song Wil-Seon",
            "hanja": [surname["hanja"], "蔚", "宣"],
            "family_name": {
                "korean": surname["korean"],
                "hanja": surname["hanja"],
                "meaning": "Pine tree - symbol of longevity and resilience"
            },
            "given_name": [
                {"syllable": "월", "hanja": "蔚", "meaning": "무성하고 아름다운"},
                {"syllable": "선", "hanja": "宣", "meaning": "베풀고 선포하는"}
            ],
            "summary": "무성한 아름다움을 널리 베푸는 사람"
        }]
    else:
        candidates = []

    # Generate additional candidates based on tags
    syllables_by_tag = {}
    for syllable in SYLLABLES_DATA:
        tag = syllable.get('tag')
        if tag not in syllables_by_tag:
            syllables_by_tag[tag] = []
        syllables_by_tag[tag].append(syllable)

    # Generate candidates
    for _ in range(3 - len(candidates)):
        selected_syllables = []

        # Select syllables based on tags
        for tag in random.sample(tags, min(2, len(tags))):
            if tag in syllables_by_tag:
                syllable_options = syllables_by_tag[tag]
                # Prefer common syllables
                common_syllables = [s for s in syllable_options if s.get('common', 0) == 1]
                if common_syllables:
                    selected = random.choice(common_syllables)
                else:
                    selected = random.choice(syllable_options)
                selected_syllables.append(selected)

        # Ensure we have 2 syllables
        while len(selected_syllables) < 2:
            tag = random.choice(list(syllables_by_tag.keys()))
            selected_syllables.append(random.choice(syllables_by_tag[tag]))

        # Create candidate
        given_name_kr = "".join([s['syllable'] for s in selected_syllables[:2]])
        given_name_hanja = [s['hanja'] for s in selected_syllables[:2]]

        candidate = {
            "name_kr": surname["korean"] + given_name_kr,
            "name_en": romanize_korean_name(surname["korean"], given_name_kr),
            "hanja": [surname["hanja"]] + given_name_hanja,
            "family_name": {
                "korean": surname["korean"],
                "hanja": surname["hanja"],
                "meaning": get_surname_meaning(surname["hanja"])
            },
            "given_name": [
                {
                    "syllable": s['syllable'],
                    "hanja": s['hanja'],
                    "meaning": s['meaning']
                } for s in selected_syllables[:2]
            ],
            "summary": generate_name_summary(selected_syllables[:2])
        }

        candidates.append(candidate)

    return candidates[:3]

def romanize_korean_name(surname, given_name):
    """Convert Korean name to romanized version"""
    romanization_map = {
        "송": "Song", "이": "Lee", "김": "Kim", "박": "Park",
        "최": "Choi", "정": "Jung", "한": "Han", "서": "Seo",
        "강": "Kang", "조": "Cho", "윤": "Yoon", "장": "Jang",
        "임": "Lim", "홍": "Hong", "신": "Shin", "원": "Won",
        "백": "Baek", "문": "Moon", "민": "Min", "양": "Yang",
        "유": "Yoo", "남": "Nam", "노": "Noh", "고": "Ko",
        "구": "Koo", "류": "Ryu", "라": "Ra", "안": "Ahn",
        "오": "Oh", "태": "Tae", "도": "Do", "천": "Cheon",
        "배": "Bae", "변": "Byun", "황": "Hwang", "전": "Jeon"
    }

    # Simple romanization for given names
    given_romanization = {
        "월": "Wil", "선": "Seon", "명": "Myung", "영": "Young",
        "지": "Ji", "현": "Hyun", "용": "Yong", "준": "Jun",
        "윤": "Yoon", "하": "Ha", "유": "Yu", "연": "Yeon",
        "우": "Woo", "은": "Eun", "민": "Min", "정": "Jung",
        "성": "Sung", "원": "Won", "석": "Seok", "서": "Seo",
        "휘": "Hwi", "혁": "Hyuk", "채": "Chae", "소": "So",
        "예": "Ye", "규": "Kyu", "도": "Do", "경": "Kyung",
        "강": "Kang", "건": "Gun", "호": "Ho", "림": "Rim",
        "해": "Hae", "솔": "Sol"
    }

    surname_roman = romanization_map.get(surname, surname)
    given_parts = []
    for char in given_name:
        given_parts.append(given_romanization.get(char, char))

    return f"{surname_roman} {'-'.join(given_parts)}"

def get_surname_meaning(hanja):
    """Get meaning for surname hanja"""
    meanings = {
        "宋": "Pine tree - symbol of longevity and resilience",
        "李": "Plum tree - symbol of beauty and perseverance",
        "金": "Gold - symbol of value and nobility",
        "朴": "Simple wood - symbol of honesty and humility",
        "崔": "High mountain - symbol of greatness",
        "鄭": "Upright - symbol of righteousness",
        "韓": "Great nation - symbol of leadership",
        "徐": "Slow and steady - symbol of patience",
        "姜": "Ginger - symbol of strength and vitality"
    }
    return meanings.get(hanja, "Noble family lineage")

def generate_name_summary(syllables):
    """Generate summary based on syllable meanings"""
    meanings = [s.get('meaning', '') for s in syllables]
    if len(meanings) == 2:
        return f"{meanings[0]}하고 {meanings[1]}한 사람"
    return "품격 있고 아름다운 이름"

def generate_fortune(tags, date=None):
    """Generate fortune messages"""
    if date is None:
        date = datetime.now().strftime("%Y/%m/%d")

    cosmic_cookies = [
        "A squirrel is burying a nut for its future self. What small, wonderful thing can you do today that 'Future You' will thank you for?",
        "The universe is conspiring to bring you exactly what you need. Stay open to unexpected meetings.",
        "Your energy today is like a gentle breeze - soft but capable of moving mountains of doubt.",
        "Today's plot twist: the thing you've been worrying about will resolve itself in the most unexpected way.",
        "The stars suggest you trust your first instinct today. Your intuition is particularly sharp."
    ]

    lucky_snacks = [
        "Anything with chocolate. Seriously.",
        "Something crunchy - it will spark creativity.",
        "A warm drink will bring clarity to your thoughts.",
        "Fresh fruit will energize your afternoon.",
        "Share a snack with someone - double the luck!"
    ]

    # Get tag-based fortune
    available_tags = [tag for tag in tags if tag in FORTUNES_DATA]
    if not available_tags:
        available_tags = list(FORTUNES_DATA.keys())

    tag = random.choice(available_tags)
    deeper_look = random.choice(FORTUNES_DATA[tag])

    return {
        "date": date,
        "cosmic_cookie": random.choice(cosmic_cookies),
        "lucky_snack": random.choice(lucky_snacks),
        "deeper_look": deeper_look
    }

# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/suggest-names', methods=['POST'])
def suggest_names():
    """API endpoint for name suggestions"""
    try:
        data = request.json
        first_name = data.get('firstName', '')
        last_name = data.get('lastName', '')
        options = data.get('options', {})

        candidates = generate_korean_names(first_name, last_name, options)

        return jsonify({
            "success": True,
            "candidates": candidates,
            "original": {
                "first_name": first_name,
                "last_name": last_name
            }
        })
    except Exception as e:
        logger.error(f"Error generating names: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/fortune', methods=['GET', 'POST'])
def get_fortune():
    """API endpoint for fortune generation"""
    try:
        if request.method == 'POST':
            data = request.json
            tags = data.get('tags', ['밝음'])
        else:
            tags = request.args.get('tags', '밝음').split(',')

        date = request.args.get('date') or datetime.now().strftime("%Y/%m/%d")
        fortune = generate_fortune(tags, date)

        return jsonify({
            "success": True,
            "fortune": fortune
        })
    except Exception as e:
        logger.error(f"Error generating fortune: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/log-selection', methods=['POST'])
def log_selection():
    """Log user selection to database"""
    try:
        if request.json.get('save', False):
            data = request.json
            db_path = user_data_dir / "naeilum.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO selections (session_id, first_name, last_name, chosen_name_kr, chosen_name_hanja, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data.get('sessionId'),
                data.get('firstName'),
                data.get('lastName'),
                data.get('chosenName'),
                json.dumps(data.get('chosenHanja', [])),
                json.dumps(data.get('tags', []))
            ))

            conn.commit()
            conn.close()

        return '', 204
    except Exception as e:
        logger.error(f"Error logging selection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

def find_free_port(start_port=3000, max_port=3005):
    """Find a free port to run the server"""
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except OSError:
                continue
    return start_port

def open_browser(port):
    """Open browser after server starts"""
    import time
    time.sleep(1.5)  # Wait for server to start
    webbrowser.open(f'http://localhost:{port}')

if __name__ == '__main__':
    init_database()
    port = find_free_port()
    logger.info(f"Starting Naeilum server on port {port}")

    # Open browser in a separate thread
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Run the Flask app
    app.run(host='127.0.0.1', port=port, debug=False)
