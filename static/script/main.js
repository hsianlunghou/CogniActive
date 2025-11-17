// Theme initialization
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

// Theme toggle
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
    
    // style convert
    document.body.style.transition = 'background-color 0.5s ease, color 0.5s ease';
}

// Update theme icon
function updateThemeIcon(theme) {
    const themeIcon = document.querySelector('.theme-icon');
    themeIcon.textContent = theme === 'light' ? '🌙' : '☀️';
}

// Listenning theme
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
});

// Navbar for phone
function toggleMobileMenu() {
    const navMenu = document.getElementById('navMenu');
    const navToggle = document.getElementById('navToggle');
    
    navMenu.classList.toggle('active');
    navToggle.classList.toggle('active');
}

// Listenning option menu
document.addEventListener('DOMContentLoaded', () => {
    const navToggle = document.getElementById('navToggle');
    if (navToggle) {
        navToggle.addEventListener('click', toggleMobileMenu);
    }
    
    // Point to link, close to menu
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                toggleMobileMenu();
            }
        });
    });
});

// Update navbar
function updateActiveNavLink() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link');
    
    let currentSection = '';
    
    sections.forEach(section => {
        const sectionTop = section.offsetTop;
        const sectionHeight = section.clientHeight;
        
        if (window.pageYOffset >= sectionTop - 100) {
            currentSection = section.getAttribute('id');
        }
    });
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${currentSection}`) {
            link.classList.add('active');
        }
    });
}

// Listenning scroll
window.addEventListener('scroll', updateActiveNavLink);

document.addEventListener('DOMContentLoaded', () => {
    const navLinks = document.querySelectorAll('a[href^="#"]');
    
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            
            const targetId = link.getAttribute('href');
            if (targetId === '#') return;
            
            const targetSection = document.querySelector(targetId);
            if (targetSection) {
                const navbarHeight = document.querySelector('.navbar').offsetHeight;
                const targetPosition = targetSection.offsetTop - navbarHeight;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
});

// Training option
function navigateToTraining(url) {
    // Add animation
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.3s ease';
    
    // set delay to show animation
    setTimeout(() => {
        window.location.href = url;
    }, 300);
}

// Intersection 
function initScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    // Observe all cards
    const animatedElements = document.querySelectorAll('.training-item, .about-card, .info-item');
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

// Initialize scroll
document.addEventListener('DOMContentLoaded', initScrollAnimations);

function handleNavbarScroll() {
    const navbar = document.querySelector('.navbar');
    
    if (window.scrollY > 50) {
        navbar.style.boxShadow = '0 4px 20px var(--shadow-medium)';
        navbar.style.padding = '0.5rem 0';
    } else {
        navbar.style.boxShadow = '0 2px 15px var(--shadow-light)';
        navbar.style.padding = '0';
    }
}

window.addEventListener('scroll', handleNavbarScroll);

// Update window size
let resizeTimer;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
        const navMenu = document.getElementById('navMenu');
        const navToggle = document.getElementById('navToggle');
        
        if (window.innerWidth > 768) {
            navMenu.classList.remove('active');
            navToggle.classList.remove('active');
        }
    }, 250);
});

// Page loading
window.addEventListener('load', () => {
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.5s ease';
    
    requestAnimationFrame(() => {
        document.body.style.opacity = '1';
    });
});

// Point to card (audio)
function initCardHoverEffects() {
    const trainingItems = document.querySelectorAll('.training-item:not(.coming-soon)');
    
    trainingItems.forEach(item => {
        item.addEventListener('mouseenter', () => {
            // Wait to develop
        });
    });
}

document.addEventListener('DOMContentLoaded', initCardHoverEffects);

// Use keyboard to listen 
document.addEventListener('DOMContentLoaded', () => {
    const focusableElements = document.querySelectorAll(
        'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    
    focusableElements.forEach(element => {
        element.addEventListener('focus', () => {
            element.style.outline = '2px solid var(--accent-primary)';
            element.style.outlineOffset = '3px';
        });
        
        element.addEventListener('blur', () => {
            element.style.outline = 'none';
        });
    });
});

// Event processing
function throttle(func, delay) {
    let lastCall = 0;
    return function(...args) {
        const now = new Date().getTime();
        if (now - lastCall < delay) {
            return;
        }
        lastCall = now;
        return func(...args);
    };
}

const throttledScroll = throttle(() => {
    updateActiveNavLink();
    handleNavbarScroll();
}, 100);

window.addEventListener('scroll', throttledScroll);

// Check error
window.addEventListener('error', (event) => {
    console.error('頁面錯誤:', event.error);
});

// Check environment
const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

if (isDevelopment) {
    console.log('%c🏓 CogniActive 開發模式', 'color: #D4956C; font-size: 20px; font-weight: bold;');
    console.log('當前主題:', document.documentElement.getAttribute('data-theme'));
    console.log('視窗尺寸:', window.innerWidth, 'x', window.innerHeight);
}

// Output log
console.log('%c🏓 CogniActive 精準桌球認知教練系統', 'color: #D4956C; font-size: 16px; font-weight: bold;');
console.log('%c© 2025 CogniActive. All rights reserved.', 'color: #8B7355; font-size: 12px;');