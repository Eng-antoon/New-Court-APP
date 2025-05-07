// Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyBs16oG9LOGusyoL5p0TlGpjZoNScPhwqE",
    authDomain: "ohda-john.firebaseapp.com",
    databaseURL: "https://ohda-john-default-rtdb.firebaseio.com",
    projectId: "ohda-john",
    storageBucket: "ohda-john.appspot.com",
    messagingSenderId: "45108192967",
    appId: "1:45108192967:web:397b84201e33945b7600e2",
    measurementId: "G-BS2CRVZS0F"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);

// Get Firestore instance
const db = firebase.firestore();

// Get Storage instance
const storage = firebase.storage();

// Get Auth instance
const auth = firebase.auth();

// Set persistence to local for better user experience
auth.setPersistence(firebase.auth.Auth.Persistence.LOCAL)
  .catch((error) => {
    console.error("Auth persistence error:", error);
  });

// Observable for authentication state changes
let currentUser = null;

// Listen for authentication state changes
auth.onAuthStateChanged((user) => {
  currentUser = user;
  
  // Update UI based on authentication state
  updateUIForAuthState(user);
  
  // Dispatch custom event when auth state changes
  const event = new CustomEvent('authStateChanged', { detail: { user } });
  document.dispatchEvent(event);
});

// Function to update UI based on auth state
function updateUIForAuthState(user) {
  const userSignedInElements = document.querySelectorAll('#user-signed-in');
  const userNotSignedInElements = document.querySelectorAll('#user-not-signed-in');
  const userNameElements = document.querySelectorAll('#user-name');
  const reservationsNavItems = document.querySelectorAll('#reservations-nav-item');
  const adminOnlyElements = document.querySelectorAll('.admin-only');

  if (user) {
    // User is signed in
    userSignedInElements.forEach(el => el.style.display = 'block');
    userNotSignedInElements.forEach(el => el.style.display = 'none');
    
    // Update user name display
    userNameElements.forEach(el => el.textContent = user.displayName || user.email);
    
    // Show reservations nav item
    reservationsNavItems.forEach(el => el.style.display = 'block');
    
    // Check if user is admin
    db.collection('users').doc(user.uid).get()
      .then((doc) => {
        if (doc.exists && doc.data().role === 'admin') {
          // Show admin-only elements
          adminOnlyElements.forEach(el => el.style.display = 'block');
        } else {
          // Hide admin-only elements
          adminOnlyElements.forEach(el => el.style.display = 'none');
        }
      })
      .catch((error) => {
        console.error("Error checking admin status:", error);
      });
  } else {
    // User is signed out
    userSignedInElements.forEach(el => el.style.display = 'none');
    userNotSignedInElements.forEach(el => el.style.display = 'block');
    
    // Hide reservations nav item
    reservationsNavItems.forEach(el => el.style.display = 'none');
    
    // Hide admin-only elements
    adminOnlyElements.forEach(el => el.style.display = 'none');
  }
}

// Function to handle login errors
function handleAuthError(error) {
  let errorMessage = "An unknown error occurred.";
  
  // Map Firebase auth errors to user-friendly messages
  switch (error.code) {
    case 'auth/invalid-email':
      errorMessage = "The email address is not valid.";
      break;
    case 'auth/user-disabled':
      errorMessage = "This account has been disabled.";
      break;
    case 'auth/user-not-found':
      errorMessage = "No account found with this email.";
      break;
    case 'auth/wrong-password':
      errorMessage = "Incorrect password.";
      break;
    case 'auth/email-already-in-use':
      errorMessage = "This email is already in use.";
      break;
    case 'auth/weak-password':
      errorMessage = "Password is too weak.";
      break;
    case 'auth/network-request-failed':
      errorMessage = "Network error. Please check your connection.";
      break;
    default:
      errorMessage = error.message;
  }
  
  // Show error message to user (implement showAlert function in app.js)
  if (typeof showAlert === 'function') {
    showAlert(errorMessage, 'danger');
  } else {
    console.error(errorMessage);
    alert(errorMessage);
  }
}

// Function to format Firestore timestamp to local date string
function formatTimestamp(timestamp) {
  if (!timestamp) return '';
  
  const date = timestamp.toDate();
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Export Firebase instances and helper functions
window.firebaseServices = {
  db,
  auth,
  storage,
  currentUser: () => currentUser,
  handleAuthError,
  formatTimestamp
}; 