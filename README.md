# Volleyball Court Reservation Platform

A full-stack Firebase-powered volleyball court reservation application that allows players to discover, view, and book courts in real time.

## Features

- User authentication and role management
- Court discovery and search
- Real-time booking and reservation management
- Waitlist functionality
- Recurring reservations
- Court maintenance scheduling
- Responsive UI design

## Technology Stack

- **Frontend:** HTML, JavaScript
- **Backend:** Python Flask
- **Database:** Firestore (NoSQL)
- **Storage:** Firebase Storage
- **Authentication:** Firebase Authentication

## Getting Started

### Prerequisites

- Python 3.8+
- Node.js and npm
- Firebase account

### Installation

1. Clone the repository
2. Install backend dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Install frontend dependencies:
   ```
   cd static
   npm install
   ```
4. Set up Firebase credentials (firebase-key.json is required)
5. Run the application:
   ```
   python app.py
   ```

## Project Structure

- `/app.py` - Main Flask application
- `/static/` - Frontend assets (HTML, CSS, JavaScript)
- `/templates/` - Flask templates
- `/models/` - Data models
- `/controllers/` - Application controllers
- `/tests/` - Test suite
- `/config/` - Configuration files 