// Get Firebase service instances
const { db, auth, storage, currentUser, handleAuthError, formatTimestamp } = window.firebaseServices;

// DOM Elements
const loginBtn = document.getElementById('login-btn');
const registerBtn = document.getElementById('register-btn');
const logoutBtn = document.getElementById('logout-btn');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const loginModal = new bootstrap.Modal(document.getElementById('login-modal'));
const registerModal = new bootstrap.Modal(document.getElementById('register-modal'));
const howItWorksBtn = document.getElementById('how-it-works-btn');
const howItWorksModal = new bootstrap.Modal(document.getElementById('how-it-works-modal'));
const registerLink = document.getElementById('register-link');
const loginLink = document.getElementById('login-link');
const googleLoginBtn = document.getElementById('google-login-btn');
const quickSearchForm = document.getElementById('quick-search-form');
const forgotPasswordLink = document.getElementById('forgot-password-link');

// Show alert function
function showAlert(message, type = 'info', container = 'content', timeout = 5000) {
    // Create alert element
    const alertEl = document.createElement('div');
    alertEl.className = `alert alert-${type} alert-dismissible fade show`;
    alertEl.role = 'alert';
    alertEl.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    // Get container
    const containerEl = document.getElementById(container);
    
    // Insert alert at the beginning of the container
    if (containerEl) {
        containerEl.insertBefore(alertEl, containerEl.firstChild);
    
        // Auto dismiss
        if (timeout > 0) {
            setTimeout(() => {
                if (alertEl.parentNode) {
                    alertEl.parentNode.removeChild(alertEl);
                }
            }, timeout);
        }
    } else {
        console.error('Alert container not found:', container);
        alert(message);
    }
}

// Show loading spinner
function showSpinner() {
    const spinnerOverlay = document.createElement('div');
    spinnerOverlay.className = 'spinner-overlay';
    spinnerOverlay.id = 'spinner-overlay';
    spinnerOverlay.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;
    document.body.appendChild(spinnerOverlay);
}

// Hide loading spinner
function hideSpinner() {
    const spinnerOverlay = document.getElementById('spinner-overlay');
    if (spinnerOverlay) {
        spinnerOverlay.remove();
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    console.log('Document ready in app.js');
    
    // Initialize needed elements
    const loginBtn = document.getElementById('login-btn');
    const registerBtn = document.getElementById('register-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const loginLink = document.getElementById('login-link');
    const registerLink = document.getElementById('register-link');
    const googleLoginBtn = document.getElementById('google-login-btn');
    const forgotPasswordLink = document.getElementById('forgot-password-link');
    const quickSearchForm = document.getElementById('quick-search-form');
    const howItWorksBtn = document.getElementById('how-it-works-btn');
    
    // Initialize modals directly using Bootstrap 5 syntax
    const loginModalElement = document.getElementById('login-modal');
    const registerModalElement = document.getElementById('register-modal');
    const howItWorksModalElement = document.getElementById('how-it-works-modal');
    
    // Create modal instances if elements exist
    let loginModal, registerModal, howItWorksModal;
    
    if (loginModalElement) {
        loginModal = new bootstrap.Modal(loginModalElement);
        console.log('Login modal initialized');
    } else {
        console.error('Login modal element not found in the DOM');
    }
    
    if (registerModalElement) {
        registerModal = new bootstrap.Modal(registerModalElement);
        console.log('Register modal initialized');
    } else {
        console.error('Register modal element not found in the DOM');
    }
    
    if (howItWorksModalElement) {
        howItWorksModal = new bootstrap.Modal(howItWorksModalElement);
        console.log('How it works modal initialized');
    }

    // Login button click
    if (loginBtn) {
        console.log('Login button found, adding event listener');
        loginBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Login button clicked');
            if (loginModal) {
                loginModal.show();
            } else {
                console.error('Login modal not initialized');
                alert('Login functionality is currently unavailable. Please try again later.');
            }
        });
    } else {
        console.error('Login button not found in the DOM');
    }

    // Register button click
    if (registerBtn) {
        console.log('Register button found, adding event listener');
        registerBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Register button clicked');
            if (registerModal) {
                registerModal.show();
            } else {
                console.error('Register modal not initialized');
                alert('Registration functionality is currently unavailable. Please try again later.');
            }
        });
    } else {
        console.error('Register button not found in the DOM');
    }

    // Logout button click
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Logout clicked');
            auth.signOut()
                .then(() => {
                    showAlert('You have been successfully logged out.', 'success');
                })
                .catch((error) => {
                    console.error('Error signing out:', error);
                    showAlert('Error signing out. Please try again.', 'danger');
                });
        });
    }

    // How it works button click
    if (howItWorksBtn) {
        howItWorksBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (howItWorksModal) {
                howItWorksModal.show();
            }
        });
    }

    // Switch between login and register modals
    if (registerLink) {
        registerLink.addEventListener('click', (e) => {
            e.preventDefault();
            if (loginModal) loginModal.hide();
            setTimeout(() => {
                if (registerModal) registerModal.show();
            }, 400);
        });
    }

    if (loginLink) {
        loginLink.addEventListener('click', (e) => {
            e.preventDefault();
            if (registerModal) registerModal.hide();
            setTimeout(() => {
                if (loginModal) loginModal.show();
            }, 400);
        });
    }

    // Login form submission
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            console.log('Login form submitted');
            
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            const rememberMe = document.getElementById('remember-me').checked;
            
            // Set persistence based on remember me checkbox
            const persistence = rememberMe 
                ? firebase.auth.Auth.Persistence.LOCAL 
                : firebase.auth.Auth.Persistence.SESSION;
            
            showSpinner();
            
            auth.setPersistence(persistence)
                .then(() => {
                    console.log('Attempting to sign in with:', email);
                    return auth.signInWithEmailAndPassword(email, password);
                })
                .then((userCredential) => {
                    console.log('Login successful');
                    if (loginModal) loginModal.hide();
                    showAlert('Login successful!', 'success');
                    loginForm.reset();
                    hideSpinner();
                })
                .catch((error) => {
                    console.error('Login error:', error);
                    hideSpinner();
                    handleAuthError(error);
                });
        });
    } else {
        console.error('Login form not found');
    }

    // Register form submission
    if (registerForm) {
        registerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            console.log('Register form submitted');
            
            const name = document.getElementById('register-name').value;
            const email = document.getElementById('register-email').value;
            const password = document.getElementById('register-password').value;
            const confirmPassword = document.getElementById('register-confirm-password').value;
            
            if (password !== confirmPassword) {
                showAlert('Passwords do not match.', 'danger');
                return;
            }
            
            showSpinner();
            
            console.log('Attempting to create user:', email);
            auth.createUserWithEmailAndPassword(email, password)
                .then((userCredential) => {
                    const user = userCredential.user;
                    console.log('User created, updating profile');
                    
                    // Update profile with name
                    return user.updateProfile({
                        displayName: name
                    }).then(() => {
                        console.log('Profile updated, saving user document');
                        // Create user document in Firestore
                        return db.collection('users').doc(user.uid).set({
                            name: name,
                            email: email,
                            role: 'user',
                            createdAt: firebase.firestore.FieldValue.serverTimestamp()
                        });
                    });
                })
                .then(() => {
                    console.log('Registration complete');
                    if (registerModal) registerModal.hide();
                    showAlert('Registration successful! Welcome to Volleyball Court Reservation.', 'success');
                    registerForm.reset();
                    hideSpinner();
                })
                .catch((error) => {
                    console.error('Registration error:', error);
                    hideSpinner();
                    handleAuthError(error);
                });
        });
    } else {
        console.error('Register form not found');
    }

    // Google login
    if (googleLoginBtn) {
        googleLoginBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Google login button clicked');
            
            const provider = new firebase.auth.GoogleAuthProvider();
            
            showSpinner();
            
            auth.signInWithPopup(provider)
                .then((result) => {
                    const user = result.user;
                    console.log('Google login successful, checking user document');
                    
                    // Check if user document exists
                    return db.collection('users').doc(user.uid).get()
                        .then((doc) => {
                            if (!doc.exists) {
                                console.log('Creating new user document');
                                // Create new user document if it doesn't exist
                                return db.collection('users').doc(user.uid).set({
                                    name: user.displayName,
                                    email: user.email,
                                    role: 'user',
                                    createdAt: firebase.firestore.FieldValue.serverTimestamp()
                                });
                            }
                            return Promise.resolve();
                        });
                })
                .then(() => {
                    if (loginModal) loginModal.hide();
                    showAlert('Login with Google successful!', 'success');
                    hideSpinner();
                })
                .catch((error) => {
                    console.error('Google login error:', error);
                    hideSpinner();
                    handleAuthError(error);
                });
        });
    }

    // Forgot password
    if (forgotPasswordLink) {
        forgotPasswordLink.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Forgot password link clicked');
            
            const email = document.getElementById('login-email').value;
            
            if (!email) {
                showAlert('Please enter your email address first.', 'warning');
                return;
            }
            
            showSpinner();
            
            auth.sendPasswordResetEmail(email)
                .then(() => {
                    hideSpinner();
                    showAlert(`Password reset email sent to ${email}. Please check your inbox.`, 'info');
                })
                .catch((error) => {
                    console.error('Password reset error:', error);
                    hideSpinner();
                    handleAuthError(error);
                });
        });
    }

    // Quick search form
    if (quickSearchForm) {
        quickSearchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            console.log('Quick search form submitted');
            
            const date = document.getElementById('search-date').value;
            const time = document.getElementById('search-time').value;
            const surface = document.getElementById('search-surface').value;
            const location = document.getElementById('search-location').value;
            
            // Build query string
            const queryParams = new URLSearchParams();
            if (date) queryParams.append('date', date);
            if (time) queryParams.append('time', time);
            if (surface) queryParams.append('surface', surface);
            if (location) queryParams.append('location', location);
            
            // Redirect to courts page with search parameters
            window.location.href = `/courts?${queryParams.toString()}`;
        });
    }
    
    // Set current date as default for search date
    const searchDateInput = document.getElementById('search-date');
    if (searchDateInput) {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        searchDateInput.value = `${year}-${month}-${day}`;
        searchDateInput.min = `${year}-${month}-${day}`;
    }
    
    // Initialize featured courts if on homepage
    if (window.location.pathname === '/') {
        loadFeaturedCourts();
    }
});

// Function to fetch and display featured courts on homepage
function loadFeaturedCourts() {
    const featuredCourtsList = document.getElementById('featured-courts-list');
    if (!featuredCourtsList) return;
    
    console.log('Loading featured courts');
    showSpinner();
    
    // Use a timeout to ensure Firebase is initialized
    setTimeout(() => {
        db.collection('courts')
            .limit(3)
            .get()
            .then((querySnapshot) => {
                hideSpinner();
                if (querySnapshot.empty) {
                    console.log('No courts found');
                    featuredCourtsList.innerHTML = '<p class="text-center">No courts available.</p>';
                    return;
                }
                
                let html = '';
                
                querySnapshot.forEach((doc) => {
                    const court = doc.data();
                    const courtId = doc.id;
                    console.log('Found court:', court.name);
                    
                    // Default image if none available
                    const courtImage = court.images && court.images.length > 0 
                        ? court.images[0] 
                        : '/static/img/court-placeholder.jpg';
                    
                    // Handle missing description
                    const description = court.description 
                        ? court.description.substring(0, 100) + '...' 
                        : 'No description available';
                    
                    html += `
                        <div class="col-md-4 mb-4">
                            <div class="card court-card h-100">
                                <img src="${courtImage}" class="card-img-top" alt="${court.name}" onerror="this.src='/static/img/court-placeholder.jpg'">
                                <div class="card-body">
                                    <h5 class="card-title">${court.name}</h5>
                                    <p class="card-text">${description}</p>
                                    <div class="d-flex justify-content-between align-items-center">
                                        <span class="badge court-type-${court.surface_type ? court.surface_type.toLowerCase() : 'default'}">${court.surface_type || 'Unknown'}</span>
                                        <a href="/courts/${courtId}" class="btn btn-sm btn-outline-primary">View Details</a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                featuredCourtsList.innerHTML = html;
            })
            .catch((error) => {
                hideSpinner();
                console.error("Error fetching courts:", error);
                featuredCourtsList.innerHTML = '<p class="text-center text-danger">Error loading courts. Please try again later.</p>';
            });
    }, 1000); // Give Firebase a second to initialize
} 