import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import "./App.css";

function App() {
    // Original state variables
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [username, setUsername] = useState("");
    const [token, setToken] = useState(localStorage.getItem("token") || null);
    const [tasks, setTasks] = useState([]);
    const [task, setTask] = useState("");
    const [taskSchedule, setTaskSchedule] = useState("");
    const [status, setStatus] = useState("pending");
    const [isRegistering, setIsRegistering] = useState(false);
    const [activeSection, setActiveSection] = useState("dashboard");
    const [user, setUser] = useState(null);
    const [sessions, setSessions] = useState([]);
    const [parentCode, setParentCode] = useState("");
    const [newSession, setNewSession] = useState({
        name: "",
        startTime: "",
        endTime: "",
        status: "pending"
    });

    const api = axios.create({
        baseURL: "http://localhost:8000",
    });

    const fetchTasks = useCallback(async () => {
        if (!token) return;
        try {
            const response = await api.get("/tasks", {
                headers: { Authorization: `Bearer ${token}` },
            });
            console.log("Fetched Tasks:", response.data);
            setTasks(response.data.tasks);
        } catch (error) {
            console.error("Failed to fetch tasks:", error.response?.data?.detail || error.message);
        }
    }, [token]);

    const fetchSessions = useCallback(async () => {
        if (!token) return;
        try {
            const response = await api.get("/sessions", {
                headers: { Authorization: `Bearer ${token}` }
            });
            setSessions(response.data.sessions);
        } catch (error) {
            console.error("Failed to fetch sessions:", error);
        }
    }, [token]);
      // Add this new fetchUserProfile function after your existing fetch functions
const fetchUserProfile = useCallback(async () => {
    if (!token) return;
    try {
        const response = await api.get("/user/profile", {
            headers: { Authorization: `Bearer ${token}` }
        });
        setUser({ name: response.data.username }); // Setting username as name
    } catch (error) {
        console.error("Failed to fetch user profile:", error);
    }
}, [token]);

   // Update the existing useEffect
useEffect(() => {
    if (token) {
        fetchUserProfile(); // Add this line
        fetchTasks();
        fetchSessions();
    }
}, [token, fetchTasks, fetchSessions, fetchUserProfile]);

    const registerUser = async () => {
        try {
            await api.post("/register", { username, email, password });
            alert("User registered successfully!");
            setIsRegistering(false);
        } catch (error) {
            alert("Error: " + (error.response?.data?.detail || "Unknown error"));
        }
    };

    // Modify the existing loginUser function
const loginUser = async () => {
    try {
        const response = await api.post("/login", { email, password });
        const userToken = response.data.access_token;
        setToken(userToken);
        localStorage.setItem("token", userToken);
        alert("Login successful!");
        await fetchUserProfile(); // Add this line to fetch user profile
        fetchTasks();
    } catch (error) {
        alert("Error: " + (error.response?.data?.detail || "Login failed"));
    }
};

    const logoutUser = () => {
        setToken(null);
        localStorage.removeItem("token");
        setTasks([]);
        setSessions([]);
        alert("Logged out successfully!");
    };

    const updateTaskStatus = async (taskId, newStatus) => {
        try {
            await api.put(`/update-task/${taskId}`, { status: newStatus }, {
                headers: { Authorization: `Bearer ${token}` },
            });
            alert("Task updated successfully!");
            fetchTasks();
        } catch (error) {
            console.error("Failed to update task:", error.response?.data?.detail || error.message);
            alert("Failed to update task.");
        }
    };
  
    const deleteTask = async (taskId) => {
        try {
            await api.delete(`/delete-task/${taskId}`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            alert("Task deleted successfully!");
            fetchTasks();
        } catch (error) {
            console.error("Failed to delete task:", error.response?.data?.detail || error.message);
            alert("Failed to delete task.");
        }
    };

    const addTask = async () => {
        try {
            await api.post("/add-task", { task_schedule: taskSchedule, task, status }, {
                headers: { Authorization: `Bearer ${token}` },
            });
            alert("Task added successfully!");
            fetchTasks();
            setTask("");
            setTaskSchedule("");
        } catch (error) {
            console.error("Task Error:", error.response?.data?.detail || error.message);
            alert("Failed to add task.");
        }
    };

    const handleCreateSession = async (e) => {
        e.preventDefault();
        try {
            await api.post("/sessions", newSession, {
                headers: { Authorization: `Bearer ${token}` }
            });
            fetchSessions();
            setNewSession({ name: "", startTime: "", endTime: "", status: "pending" });
            alert("Session created successfully!");
        } catch (error) {
            alert("Failed to create session");
        }
    };
    
    // Add this new function after your existing functions
const addSession = async () => {
    try {
        await api.post("/add-session", {
            name: newSession.name,
            startTime: newSession.startTime,
            endTime: newSession.endTime,
            status: "pending"
        }, {
            headers: { Authorization: `Bearer ${token}` },
        });
        alert("Session added successfully!");
        fetchTasks();
        setNewSession({
            name: "",
            startTime: "",
            endTime: "",
            status: "pending"
        });
    } catch (error) {
        console.error("Session Error:", error.response?.data?.detail || error.message);
        alert("Failed to add session.");
    }
};

    const handleParentAccess = async (e) => {
        e.preventDefault();
        try {
            const response = await api.post("/parent-access", { code: parentCode }, {
                headers: { Authorization: `Bearer ${token}` }
            });
            // Handle parent access response
            alert("Access granted successfully!");
        } catch (error) {
            alert("Invalid parent access code");
        }
    };

    

    if (!token) {
        return (
            <div className="container">
                <div className="logo-container">
                    <img src="logo.png" alt="Logo" />
                </div>
                <h1>Study Desk Assistant<img src="logo.png" alt="Logo" /></h1>
                <div className="login-box">
                    <h2>{isRegistering ? "Sign Up" : "Login"}</h2>
                    {isRegistering && (
                        <input 
                            type="text" 
                            placeholder="Username" 
                            value={username} 
                            onChange={(e) => setUsername(e.target.value)} 
                        />
                    )}
                    <input 
                        type="email" 
                        placeholder="Email" 
                        value={email} 
                        onChange={(e) => setEmail(e.target.value)} 
                    />
                    <input 
                        type="password" 
                        placeholder="Password" 
                        value={password} 
                        onChange={(e) => setPassword(e.target.value)} 
                    />
                    {isRegistering ? (
                        <button onClick={registerUser} className="btn">Register</button>
                    ) : (
                        <button onClick={loginUser} className="btn">Login</button>
                    )}
                    <p>
                        {isRegistering ? "Already have an account?" : "Don't have an account?"} {" "}
                        <button onClick={() => setIsRegistering(!isRegistering)} className="link-btn">
                            {isRegistering ? "Login" : "Register"}
                        </button>
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="dashboard">
            <nav className="sidebar">
                <div className="user-profile">
                    <img src="logo.png" alt="Profile" />
                    <h3>{user?.name || "Student"}</h3>
                </div>
                <button 
                    className={activeSection === "dashboard" ? "active" : ""} 
                    onClick={() => setActiveSection("dashboard")}
                >
                    Dashboard
                </button>
                <button 
                    className={activeSection === "tasks" ? "active" : ""} 
                    onClick={() => setActiveSection("tasks")}
                >
                    Study Sessions
                </button>
                <button 
                    className={activeSection === "history" ? "active" : ""} 
                    onClick={() => setActiveSection("history")}
                >
                    History
                </button>
                <button 
                    className={activeSection === "parent" ? "active" : ""} 
                    onClick={() => setActiveSection("parent")}
                >
                    Parent Access
                </button>
                <button onClick={logoutUser} className="btn logout">Logout</button>
            </nav>

            <main className="content">
                {activeSection === "dashboard" && (
                    <div className="dashboard-section">
                        <h2>Today's Study Sessions</h2>
                        <div className="sessions-grid">
                            {sessions.filter(session => 
                                new Date(session.startTime).toDateString() === new Date().toDateString()
                            ).map(session => (
                                <div key={session._id} className="session-card">
                                    <h3>{session.name}</h3>
                                    <p>Time: {new Date(session.startTime).toLocaleTimeString()} - 
                                       {new Date(session.endTime).toLocaleTimeString()}</p>
                                    <p>Status: {session.status}</p>
                                    <div className="session-stats">
                                        <div>Study Time: {session.studyTime}m</div>
                                        <div>Distraction: {session.distractionTime}m</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {activeSection === "tasks" && (
                    <div className="tasks-section">
                        <h2>Task Management</h2>
                        <div className="add-task-form">
                            <input type="text" placeholder="Task" value={task} onChange={(e) => setTask(e.target.value)} />
                            <input type="datetime-local" value={taskSchedule} onChange={(e) => setTaskSchedule(e.target.value)} />
                            <select value={status} onChange={(e) => setStatus(e.target.value)}>
                                <option value="pending">Pending</option>
                                <option value="incomplete">Incomplete</option>
                                <option value="completed">Completed</option>
                            </select>
                            <button onClick={addTask} className="btn">Add Task</button>
                        </div>
                        <div className="task-list">
                            <h3>Your Tasks</h3>
                            {tasks.length > 0 ? (
                                tasks.map((task) => (
                                    <div key={task._id} className="task-item">
                                        <div className="task-info">
                                            <h4>{task.task}</h4>
                                            <p>Status: {task.status}</p>
                                            <p>Schedule: {new Date(task.task_schedule).toLocaleString()}</p>
                                        </div>
                                        <div className="task-actions">
                                            <button onClick={() => updateTaskStatus(task._id, "completed")} className="btn">Complete</button>
                                            <button onClick={() => updateTaskStatus(task._id, "incomplete")} className="btn">Incomplete</button>
                                            <button onClick={() => deleteTask(task._id)} className="btn delete">Delete</button>
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <p>No tasks found.</p>
                            )}
                        </div>
                    </div>
                )}

                {activeSection === "sessions" && (
                    <div className="sessions-section">
                        <h2>Create New Study Session</h2>
                        <div className="add-session-form">
                            <input
                                type="text"
                                placeholder="Session Name"
                                value={newSession.name}
                                onChange={(e) => setNewSession({...newSession, name: e.target.value})}
                            />
                            <input
                                type="datetime-local"
                                value={newSession.startTime}
                                onChange={(e) => setNewSession({...newSession, startTime: e.target.value})}
                            />
                            <input
                                type="datetime-local"
                                value={newSession.endTime}
                                onChange={(e) => setNewSession({...newSession, endTime: e.target.value})}
                            />
                            <button onClick={addSession} className="btn">Add Session</button>
                        </div>
                        <div className="session-list">
                            <h3>Your Study Sessions</h3>
                            {tasks.filter(task => task.type === "session").length > 0 ? (
                                tasks.filter(task => task.type === "session").map((session) => (
                                    <div key={session._id} className="session-item">
                                        <div className="session-info">
                                            <h4>{session.task}</h4>
                                            <p>Status: {session.status}</p>
                                            <p>Start: {new Date(session.task_schedule).toLocaleString()}</p>
                                            <p>End: {new Date(session.end_time).toLocaleString()}</p>
                                        </div>
                                        <div className="session-actions">
                                            <button onClick={() => updateTaskStatus(session._id, "completed")} className="btn">Complete</button>
                                            <button onClick={() => updateTaskStatus(session._id, "incomplete")} className="btn">Incomplete</button>
                                            <button onClick={() => deleteTask(session._id)} className="btn delete">Delete</button>
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <p>No study sessions found.</p>
                            )}
                        </div>
                    </div>
                )}

                {activeSection === "history" && (
                    <div className="history-section">
                        <h2>Study History</h2>
                        <div className="history-grid">
                            {sessions.map(session => (
                                <div key={session._id} className="history-card">
                                    <h3>{session.name}</h3>
                                    <p>Date: {new Date(session.startTime).toLocaleDateString()}</p>
                                    <p>Duration: {
                                        Math.round((new Date(session.endTime) - new Date(session.startTime)) / 60000)
                                    } minutes</p>
                                    <div className="session-stats">
                                        <div>Study Time: {session.studyTime}m</div>
                                        <div>Distraction: {session.distractionTime}m</div>
                                    </div>
                                    <p className="status">{session.status}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {activeSection === "parent" && (
                    <div className="parent-section">
                        <h2>Parent Access</h2>
                        <form onSubmit={handleParentAccess} className="parent-form">
                            <input
                                type="text"
                                placeholder="Enter Parent Access Code"
                                value={parentCode}
                                onChange={(e) => setParentCode(e.target.value)}
                            />
                            <button type="submit">Access Records</button>
                        </form>
                        <div className="video-records">
                            {/* Video records will be displayed here after parent authentication */}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}

export default App;