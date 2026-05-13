fetch('/api/v1/dashboard/summary/')
  .then(r => r.json())
  .then(data => {
    const hourly = data.hourly_chart || [];
    const labels = hourly.map(h => h.hour);
    const totals = hourly.map(h => h.total);
    const anomalies = hourly.map(h => h.anomaly);

    const cs = getComputedStyle(document.documentElement);
    const tickClr  = cs.getPropertyValue('--txt-muted').trim();
    const dimClr   = cs.getPropertyValue('--txt-dim').trim();
    const gridClr  = cs.getPropertyValue('--border-clr').trim();

    new Chart(document.getElementById('activityChart'), {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Всего пакетов', data: totals, backgroundColor: 'rgba(88,166,255,.3)', borderColor: '#58a6ff', borderWidth: 1 },
          { label: 'Аномалии', data: anomalies, backgroundColor: 'rgba(248,81,73,.4)', borderColor: '#f85149', borderWidth: 1 },
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: { legend: { labels: { color: tickClr, font: { size: 11 } } } },
        scales: {
          x: { ticks: { color: dimClr, maxTicksLimit: 8, font: { size: 10 } }, grid: { color: gridClr } },
          y: { ticks: { color: tickClr, font: { size: 10 } }, grid: { color: gridClr } }
        }
      }
    });
  })
  .catch(() => {});
