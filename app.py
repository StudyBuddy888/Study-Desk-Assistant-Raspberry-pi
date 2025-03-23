import cv2
import time
import requests
from datetime import datetime, timedelta
import threading
import numpy as np
import pyttsx3
import speech_recognition as sr
from pymongo import MongoClient
import google.generativeai as genai

# MongoDB Setup
# MONGO_URI = "mongodb+srv://Studybuddy:Paav1234@studydeskcluster.lmi3g.mongodb.net/?retryWrites=true&w=majority&appName=StudyDeskCluster"
MONGO_URI = "mongodb+srv://Studybuddy:@studydeskcluster.lmi3g.mongodb.net/?retryWrites=true&w=majority&appName=StudyDeskCluster"
client = MongoClient(MONGO_URI)
db = client["study_tracker"]
users_collection = db["users"]
sessions_collection = db["study_sessions"]

# API Endpoints
API_URL = "http://localhost:8000/tasks"
LOGIN_URL = "http://localhost:8000/login"
UPDATE_PROGRESS_URL = "http://localhost:8000/update_progress"

# Update TTS initialization
def init_tts():
    """Initialize Text-to-Speech engine"""
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 1.0)
        voices = engine.getProperty('voices')
        engine.setProperty('voice', voices[0].id)
        return engine
    except Exception as e:
        print(f"[ERROR] Failed to initialize TTS: {str(e)}")
        return None

# Modified speak function with better run loop handling
def speak(text):
    """Convert text to speech with proper cleanup."""
    global engine
    print(f"[VOICE] {text}")
    
    try:
        # Create new engine instance for each speak call
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 1.0)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
        return True
    except Exception as e:
        print(f"[ERROR] TTS error: {str(e)}")
        try:
            engine.stop()
        except:
            pass
        time.sleep(0.1)
        return False

# Global TTS engine
engine = init_tts()

#GEMINI_API_KEY = "AIzaSyAAbC20bXG1giPijXyoIT_qlwmwINZ3ZgI"  # Replace with your Google AI Studio API key
genai.configure(api_key=GEMINI_API_KEY)

# Initialize the model once globally
model = genai.GenerativeModel('gemini-2.0-flash')
session_active = False
# Load Face Recognizer
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    
def check_task_reminders():
    """Check and remind about scheduled tasks"""
    global session_active
    print("[INFO] Task reminder system activated")
    while True:
        try:
            current_time = datetime.now()
            # Get tasks scheduled 2 minutes from now
            reminder_time = (current_time + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M")
            current_time_str = current_time.strftime("%Y-%m-%dT%H:%M")
            
            # Find tasks that need 2-minute advance reminder
            advance_reminder_tasks = db["tasks"].find({
                "status": "pending",
                "task_schedule": reminder_time
            })
            
            # Find tasks due now
            current_tasks = db["tasks"].find({
                "status": "upcoming",  # Changed from pending to upcoming
                "task_schedule": current_time_str
            })
            
            # Process 2-minute advance reminders
            for task in advance_reminder_tasks:
                print(f"[DEBUG] Sending 2-minute advance reminder for: {task['task']}")
                speak(f"Reminder! Your task '{task['task']}' is starting in 2 minutes.")
                # Update status to upcoming
                db["tasks"].update_one(
                    {"_id": task["_id"]},
                    {"$set": {"status": "upcoming"}}
                )
            
            # Process current time tasks

        except Exception as e:
            print(f"[ERROR] Task reminder check failed: {str(e)}")
        
        time.sleep(15)

def wait_for_scheduled_task(token):
    """Wait for the next scheduled task"""
    while True:
        current_time = datetime.now()
        current_time_str = current_time.strftime("%Y-%m-%dT%H:%M")
        
        # Find next pending task
        next_task = db["tasks"].find_one({
            "status": "pending",
            "task_schedule": {"$gte": current_time_str}
        }, sort=[("task_schedule", 1)])
        
        if next_task:
            task_time = datetime.strptime(next_task["task_schedule"], "%Y-%m-%dT%H:%M")
            if current_time_str == next_task["task_schedule"]:
                # Calculate session duration from task schedule and end time
                end_time = datetime.strptime(next_task["end_time"], "%Y-%m-%dT%H:%M")
                session_duration = int((end_time - task_time).total_seconds())
                return session_duration, next_task
            else:
                time_diff = (task_time - current_time).total_seconds()
                if time_diff > 0:
                    print(f"[INFO] Waiting for scheduled task at {task_time.strftime('%H:%M')}...")
                    time.sleep(15)  # Check every 15 seconds
        else:
            print("[INFO] No scheduled tasks found")
            time.sleep(60)

# Update Study Progress
def update_progress(email, study_time, distraction_time, status):
    """Store study session details in MongoDB Atlas."""
    try:
        session_data = {
            "user_email": email,
            "study_time_minutes": study_time // 60,  # Convert to minutes
            "distraction_time_minutes": distraction_time // 60,  # Convert to minutes
            "total_session_duration": (study_time + distraction_time) // 60,
            "focus_percentage": ((study_time - distraction_time) / study_time) * 100 if study_time > 0 else 0,
            "status": status,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        result = sessions_collection.insert_one(session_data)
        print(f"[MongoDB] Session data stored successfully. Document ID: {result.inserted_id}")
        print(f"[Stats] Study time: {study_time//60}m, Distraction time: {distraction_time//60}m")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to store session data: {str(e)}")
        return False

# Face Recognition
def recognize_face():
    """Recognize user before starting session."""
    cap = cv2.VideoCapture(0)
    user_recognized = False
    speak("Please look at the camera for recognition.")

    while not user_recognized:
        ret, frame = cap.read()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

        if len(faces) > 0:
            user_recognized = True
            speak("Face recognized. Welcome back!")
            print("Face detected!")
        else:
            print("No face detected. Please adjust your position.")

    cap.release()
    return True

# Listen to User
def listen(timeout=10):
    """Capture and recognize voice input."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        print("Listening...")
        try:
            audio = recognizer.listen(source, timeout=timeout)
            query = recognizer.recognize_google(audio).lower()
            print(f"Heard: {query}")
            return query
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            return None
        except sr.WaitTimeoutError:
            return None
    return None



def gemini_answer(query):
    """Get response from Google Gemini."""
    if not query:
        return "I couldn't understand your question. Please try again."

    try:
        # Keep model initialization simple
        response = model.generate_content(f"Answer this question briefly: {query}")
        
        if hasattr(response, 'text'):
            answer = response.text.strip()[:200]  # Shorter responses
            return answer
        return "Sorry, I couldn't generate a proper response."
            
    except Exception as e:
        print(f"[ERROR] Gemini API Error: {e}")
        return "Sorry, I couldn't fetch an answer right now."

# Track Distraction & Study Time
def track_distraction(session_duration, user_email, task_name):
    """Monitor distractions during study session."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open video capture")
        return None, None, "Failed"

    last_seen = time.time()
    distraction_time = 0
    study_start = time.time()
    eyes_closed_start = None
    last_voice_prompt = 0
    VOICE_PROMPT_DELAY = 60  # Minimum seconds between voice prompts

    try:
        while time.time() - study_start < session_duration:
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)

            current_time = time.time()
            if len(faces) > 0:
                last_seen = current_time
                eyes_closed_start = None
                print("[INFO] User is focused.")
            else:
                if current_time - last_seen > 30 and current_time - last_voice_prompt > VOICE_PROMPT_DELAY:
                    if speak("You seem distracted! Focus on your studies."):
                        distraction_time += current_time - last_seen
                        last_seen = current_time
                        last_voice_prompt = current_time

            # Voice command handling with improved timing
            if current_time - last_voice_prompt > 5:
                query = listen()
                if query and "hey buddy" in query:
                    if speak("Yes, how can I help you?"):
                        question = listen()
                        if question:
                            if "distracted time" in question:
                                speak(f"You have been distracted for {distraction_time // 60} minutes.")
                            else:
                                answer = gemini_answer(question)
                                speak(answer)
                            last_voice_prompt = current_time + 2  # Add delay after response

            time.sleep(0.1)

    except Exception as e:
        print(f"[ERROR] Session error: {str(e)}")
        return None, None, "Failed"
    finally:
        cap.release()

    study_time = time.time() - study_start
    effective_study_time = study_time - distraction_time
    focus_percentage = (effective_study_time / study_time) * 100 if study_time > 0 else 0
    status = "Completed" if focus_percentage >= 75 else "Partially Completed"
    
    return study_time, distraction_time, status

# Login and Fetch User
def login_and_get_token():
    """Authenticate the most recently registered user."""
    latest_user = users_collection.find_one({}, sort=[("_id", -1)])

    if not latest_user:
        speak("No users found. Please register first.")
        return None, None

    email = latest_user["email"]
    speak(f"Logging in as {latest_user['username']}.")
    speak("Please say your password.")
    
    while True:
        password = listen(timeout=10)
        if not password:
            speak("I couldn't hear your password. Please try again.")
            continue

        login_data = {"email": email, "password": password}
        response = requests.post(LOGIN_URL, json=login_data)

        if response.status_code == 200:
            speak("Login successful.")
            return response.json()["access_token"], latest_user
        else:
            speak("Login failed. Please try again.")

#  Main Execution
if __name__ == "__main__":
    print(" Assistant is starting...")


    token, user = login_and_get_token()
    if not token:
        print(" Failed to log in. Exiting...")
        exit()
    
    print("[INFO] Starting task reminder system...")
    reminder_thread = threading.Thread(target=check_task_reminders, daemon=True)
    reminder_thread.start()

    # Wait for scheduled task instead of asking for duration
    session_duration, current_task = wait_for_scheduled_task(token)
    
    speak(f"Starting scheduled task '{current_task['task']}'. Session will last for {session_duration // 60} minutes.")
    time.sleep(2)

    if recognize_face():
        study_time, distraction_time, status = track_distraction(
            session_duration,
            user["email"],
            current_task["task"]
        )
        speak(f"Session ended! You studied for {study_time // 60} minutes and were distracted for {distraction_time // 60} minutes.")
        update_progress(user["email"], study_time, distraction_time, status)
        if status == "Completed":
            speak("Great job staying focused!")