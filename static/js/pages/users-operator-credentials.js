(function () {
  document.querySelectorAll('.copy-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var target = document.getElementById(this.dataset.target);
      navigator.clipboard.writeText(target.textContent.trim()).then(function () {
        btn.innerHTML = '<i class="bi bi-check2" style="color:#238636"></i>';
        setTimeout(function () { btn.innerHTML = '<i class="bi bi-clipboard"></i>'; }, 2000);
      });
    }.bind(btn));
  });

  document.getElementById('copyAll').addEventListener('click', function () {
    var login    = document.getElementById('valLogin').textContent.trim();
    var password = document.getElementById('valPassword').textContent.trim();
    var text = 'Логин: ' + login + '\nПароль: ' + password;
    navigator.clipboard.writeText(text).then(function () {
      var btn = document.getElementById('copyAll');
      btn.innerHTML = '<i class="bi bi-check2-circle"></i> Скопировано!';
      btn.style.background = '#1a7f37';
      setTimeout(function () {
        btn.innerHTML = '<i class="bi bi-clipboard-check"></i> Скопировать всё';
        btn.style.background = '#238636';
      }, 3000);
    });
  });
}());
