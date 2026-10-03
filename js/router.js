// KisanAI Router
(function() {
  const routes = {};

  function register(path, renderFn) {
    routes[path] = renderFn;
  }

  function navigate(hash) {
    window.location.hash = hash;
  }

  function resolveRoute() {
    let hash = window.location.hash || '#/';
    let path = hash.replace(/^#/, '');
    if (path === '') path = '/';

    // Auth & Onboarding Route Guards
    const onboarded = localStorage.getItem('kisanOnboarded');
    const authenticated = localStorage.getItem('kisanAuth');
    const publicPaths = ['/splash', '/onboarding', '/language', '/login', '/signup', '/otp', '/permissions'];
    const isPublic = publicPaths.some(p => path.startsWith(p));

    if (!isPublic) {
      if (!onboarded) {
        window.location.hash = '#/splash';
        return;
      } else if (!authenticated) {
        window.location.hash = '#/login';
        return;
      }
    }
    
    // Default fallback to home
    const renderFn = routes[path] || routes['/'];
    const container = document.getElementById('app');
    
    if (container && renderFn) {
      // Add subtle transition effect
      container.style.opacity = 0;
      
      setTimeout(() => {
        container.innerHTML = '';
        renderFn(container);
        
        // Apply translations to static parts
        if (window.KisanI18n) {
          window.KisanI18n.applyTranslations();
        }
        
        // Update active class in navigation
        updateActiveNav(path);
        
        // Scroll to top
        window.scrollTo(0, 0);
        
        container.style.opacity = 1;
      }, 100);
    }
  }

  function updateActiveNav(currentPath) {
    const navLinks = document.querySelectorAll('.bottom-nav-item');
    navLinks.forEach(link => {
      const href = link.getAttribute('href');
      if (href) {
        const path = href.replace(/^#/, '');
        // Match exact or match parent (for nested paths if any)
        if (path === currentPath || (currentPath === '/' && path === '/') || (currentPath !== '/' && path !== '/' && currentPath.startsWith(path))) {
          link.classList.add('active');
        } else {
          link.classList.remove('active');
        }
      }
    });
  }

  // Listen to hash change and window load
  window.addEventListener('hashchange', resolveRoute);
  window.addEventListener('load', resolveRoute);
  
  // Re-resolve route on language change to redraw content with new strings
  window.addEventListener('kisanLanguageChanged', resolveRoute);

  window.KisanRouter = {
    register,
    navigate,
    resolveRoute
  };
})();
