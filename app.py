import cv2
import time
import requests
from datetime import datetime, timedelta
import threading
import numpy as np
import pyttsx3
import speech_recognition as sr
from pymongo import MongoClient
import openai
from gridfs import GridFS
import os
from bson.binary import Binary
import io
import zlib



# 🔹 MongoDB Setup
# MONGO_URI = "mongodb+srv://Studybuddy:Paav1234@studydeskcluster.lmi3g.mongodb.net/?retryWrites=true&w=majority&appName=StudyDeskCluster"
MONGO_URI = "mongodb+srv://Studybuddy:.lmi3g.mongodb.net/?retryWrites=true&w=majority&appName=StudyDeskCluster"
client = MongoClient(MONGO_URI)
db = client["study_tracker"]
users_collection = db["users"]
sessions_collection = db["study_sessions"]

# Add after MongoDB setup
fs = GridFS(db)  # Initialize GridFS

# 🔹 API Endpoints
API_URL = "http://localhost:8000/tasks"
LOGIN_URL = "http://localhost:8000/login"
UPDATE_PROGRESS_URL = "http://localhost:8000/update_progress"

# 🔹 Initialize Text-to-Speech
engine = pyttsx3.init()
openai.api_key = "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"  # Replace with a valid OpenAI API Key

# 🔹 Load Face Recognizer
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

def compress_video(input_path):
    """Compress video file using OpenCV"""
    try:
        temp_output = f"compressed_{os.path.basename(input_path)}"
        cap = cv2.VideoCapture(input_path)
        
        # Lower resolution and fps for compression
        width = 320
        height = 240
        fps = 10
        
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            # Resize frame for compression
            resized = cv2.resize(frame, (width, height))
            out.write(resized)
            
        cap.release()
        out.release()
        
        return temp_output
    except Exception as e:
        print(f"[ERROR] Video compression failed: {str(e)}")
        return None
    
# ✅ Speak Function
def speak(text):
    """Convert text to speech with error handling."""
    print(f"[VOICE] {text}")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            engine.say(text)
            engine.runAndWait()
            return
        except RuntimeError as e:
            print(f"[WARNING] TTS Engine busy (attempt {attempt + 1}/{max_retries})")
            time.sleep(1)  # Wait before retry
            try:
                engine.endLoop()  # Try to end existing loop
            except:
                pass
            
            if attempt == max_retries - 1:
                print(f"[ERROR] Failed to speak after {max_retries} attempts: {str(e)}")
                return
            
def check_task_reminders():
    """Check and remind about scheduled tasks"""
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
            for task in current_tasks:
                print(f"[DEBUG] Task starting now: {task['task']}")
                speak(f"Your task '{task['task']}' is starting now!")
                # Update status to in-progress
                db["tasks"].update_one(
                    {"_id": task["_id"]},
                    {"$set": {"status": "in-progress"}}
                )

            print(f"[DEBUG] Current time: {current_time_str}, Checking for tasks at: {reminder_time}")

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

# ✅ Update Study Progress
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

# ✅ Face Recognition
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

# ✅ Listen to User
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

# ✅ OpenAI Chatbot
def openai_answer(query):
    """Get response from OpenAI ChatGPT."""
    if not query:
        return "I couldn't understand your question. Please try again."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": query}]
        )
        answer = response['choices'][0]['message']['content']
        print(f" ChatGPT Answer: {answer}")
        return answer
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return "Sorry, I couldn't fetch an answer right now."

# ✅ Track Distraction & Study Time
def track_distraction(session_duration, user_email, task_name):
    """Monitor distractions and record session."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open video capture")
        return None, None, "Failed"

    # Video recording setup with compression settings
    frame_width = 320  # Reduced width for smaller file size
    frame_height = 240  # Reduced height for smaller file size
    fps = 10  # Reduced FPS for smaller file size
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_video_path = f'session_{timestamp}.avi'
    
    out = cv2.VideoWriter(
        temp_video_path,
        cv2.VideoWriter_fourcc(*'XVID'),
        fps,
        (frame_width, frame_height)
    )
    
    print("[INFO] Starting video recording...")
    
    # Initialize tracking variables
    last_seen = time.time()
    distraction_time = 0
    study_start = time.time()
    eyes_closed_start = None
    reminder_sent = False
    session_end_time = study_start + session_duration

    try:
        while time.time() - study_start < session_duration:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Failed to capture frame")
                continue
            
            # Resize frame for compression
            resized_frame = cv2.resize(frame, (frame_width, frame_height))
            out.write(resized_frame)

            gray = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)

            # Check for session end warning
            time_remaining = session_end_time - time.time()
            if time_remaining <= 120 and not reminder_sent:
                current_study_time = (time.time() - study_start) // 60
                current_distraction = distraction_time // 60
                speak(f"Two minutes remaining. You've studied for {current_study_time:.0f} minutes.")
                reminder_sent = True

            if len(faces) > 0:
                last_seen = time.time()
                eyes_closed_start = None
                print("[INFO] User is focused.")
            else:
                if time.time() - last_seen > 30:
                    speak("You seem distracted! Focus on your studies.")
                    distraction_time += time.time() - last_seen
                    last_seen = time.time()

                if eyes_closed_start is None:
                    eyes_closed_start = time.time()
                elif time.time() - eyes_closed_start > 60:
                    speak("Wake up! Open your eyes.")
                elif time.time() - eyes_closed_start > 120:
                    speak("Session stopped due to inactivity.")
                    break

            print("[INFO] Checking for 'Hey Buddy'...")
            query = listen()
            if query and "hey buddy" in query:
                speak("Yes, how can I help you?")
                question = listen()
                if question:
                    if "distracted time" in question:
                        speak(f"You have been distracted for {distraction_time // 60} minutes.")
                    else:
                        answer = openai_answer(question)
                        speak(answer)

            time.sleep(1)  # Reduced sleep time

    except Exception as e:
        print(f"[ERROR] Session recording error: {str(e)}")
    finally:
        # Cleanup video recording
        cap.release()
        out.release()
        
        # Store video in MongoDB
        try:
            print("[INFO] Processing and storing session video...")
            with open(temp_video_path, 'rb') as video_file:
                file_id = fs.put(
                    video_file,
                    filename=f"session_{timestamp}.avi",
                    metadata={
                        "user_email": user_email,
                        "task_name": task_name,
                        "duration_minutes": session_duration // 60,
                        "timestamp": datetime.now(),
                        "study_time": (time.time() - study_start) // 60,
                        "distraction_time": distraction_time // 60
                    }
                )
            print(f"[INFO] Video stored successfully with ID: {file_id}")
            
            # Clean up temporary file
            os.remove(temp_video_path)
            print("[INFO] Temporary video file cleaned up")
            
        except Exception as e:
            print(f"[ERROR] Failed to store session video: {str(e)}")

    study_time = time.time() - study_start
    status = "Completed" if distraction_time < study_time * 0.3 else "Partially Completed"
    return study_time, distraction_time, status

# ✅ Login and Fetch User
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

# ✅ Main Execution
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
        speak(f"Session ended! You studied for {study_time // 60} minutes.")
        update_progress(user["email"], study_time, distraction_time, status)
        if status == "Completed":
            speak("Great job staying focused!")