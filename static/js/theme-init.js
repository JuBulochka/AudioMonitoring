(function(){
      try {
        var t = localStorage.getItem('pj-theme') || 'light';
        document.documentElement.setAttribute('data-theme', t);
        document.documentElement.setAttribute('data-bs-theme', t);
      } catch(e) {}
    }());
