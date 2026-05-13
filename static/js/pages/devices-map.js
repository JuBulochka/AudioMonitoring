ymaps.ready(function () {

  // ── Карта ────────────────────────────────────────────
  const myMap = new ymaps.Map('map', {
    center: [55.75, 37.61],
    zoom: 5,
    controls: ['zoomControl'],
  }, {
    suppressMapOpenBlock: true,
  });

  // ── Кластеризатор (встроенный Яндекс) ────────────────
  const clusterer = new ymaps.Clusterer({
    preset: 'islands#invertedBlueClusterIcons',
    clusterDisableClickZoom: false,
    groupByCoordinates: false,
  });
  myMap.geoObjects.add(clusterer);

  // ── SVG-иконка маркера ───────────────────────────────
  function makeCircleSvg(color, isOnline) {
    const opacity = isOnline ? 1 : 0.5;
    const svg =
      `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18">` +
      `<circle cx="9" cy="9" r="7" fill="${color}" fill-opacity="${opacity}" ` +
      `stroke="white" stroke-width="2"/>` +
      `</svg>`;
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }

  // ── Контент balloon (появляется прямо у маркера) ─────
  function makeBalloonContent(d) {
    const lastSeen    = d.last_seen_at
      ? new Date(d.last_seen_at).toLocaleString('ru-RU')
      : 'нет данных';
    const statusColor = d.color || '#6c757d';
    const onlineHtml  = d.is_online
      ? `<span style="color:#3fb950">● онлайн</span>`
      : `<span style="color:#6c757d">● оффлайн</span>`;
    return `
      <div style="min-width:210px;font-family:system-ui,sans-serif;line-height:1.45">
        <div style="font-weight:700;font-size:.9rem;margin-bottom:3px">${d.name}</div>
        <div style="font-family:monospace;font-size:.75rem;color:#8b949e">${d.serial_number}</div>
        <div style="margin:6px 0">
          <span style="background:${statusColor}22;color:${statusColor};
                       border:1px solid ${statusColor}55;padding:2px 8px;
                       border-radius:10px;font-size:.7rem">${d.status}</span>
          &nbsp;${onlineHtml}
        </div>
        <div style="font-size:.72rem;color:#8b949e">Скв. ${d.well_number} · ${d.region}</div>
        <div style="font-size:.72rem;color:#8b949e;margin-top:2px">
          Последний сигнал: ${lastSeen}
        </div>
        <div style="margin-top:.6rem">
          <a href="/devices/${d.id}/"
             style="font-size:.78rem;color:#0550ae;text-decoration:none">
            → Открыть карточку
          </a>
        </div>
      </div>`;
  }

  // ── Загрузка устройств ────────────────────────────────
  let moveTimer;

  window.loadDevices = function () {
    myMap.balloon.close();

    const bounds = myMap.getBounds();   // [[minLat,minLng],[maxLat,maxLng]]
    const params = new URLSearchParams();
    params.set('sw_lat', bounds[0][0].toFixed(6));
    params.set('sw_lng', bounds[0][1].toFixed(6));
    params.set('ne_lat', bounds[1][0].toFixed(6));
    params.set('ne_lng', bounds[1][1].toFixed(6));

    const region  = document.getElementById('f-region').value;
    const status  = document.getElementById('f-status').value;
    const anomaly = document.getElementById('f-anomaly').checked;
    const offline = document.getElementById('f-offline').checked;
    if (region)  params.set('region', region);
    if (status)  params.set('status', status);
    if (anomaly) params.set('anomaly_only', 'true');
    if (offline) params.set('online_only', 'false');

    fetch('/api/v1/map/devices/?' + params)
      .then(r => r.json())
      .then(data => {
        document.getElementById('device-count').textContent =
          `Устройств на карте: ${data.count}`;

        clusterer.removeAll();

        const placemarks = data.features
          .filter(d => d.lat != null && d.lng != null)
          .map(d => new ymaps.Placemark(
            [d.lat, d.lng],
            {
              balloonContent: makeBalloonContent(d),
            },
            {
              iconLayout:         'default#image',
              iconImageHref:      makeCircleSvg(d.color || '#6c757d', d.is_online),
              iconImageSize:      [18, 18],
              iconImageOffset:    [-9, -9],
              balloonCloseButton: true,
              hideIconOnBalloonOpen: false,
            }
          ));

        clusterer.add(placemarks);
      })
      .catch(e => console.error('Map load error:', e));
  };

  // Перезагрузка при движении карты
  myMap.events.add('boundschange', function () {
    clearTimeout(moveTimer);
    moveTimer = setTimeout(loadDevices, 300);
  });

  // Фильтры
  ['f-region', 'f-status'].forEach(id =>
    document.getElementById(id).addEventListener('change', loadDevices));
  ['f-anomaly', 'f-offline'].forEach(id =>
    document.getElementById(id).addEventListener('change', loadDevices));

  // Первая загрузка
  loadDevices();

});
