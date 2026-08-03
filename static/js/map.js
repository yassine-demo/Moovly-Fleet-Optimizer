/**
 * MoovlyMap — Map module for Test 2
 */
const MoovlyMap = (function () {
    let map, markersLayer, routesLayer, heatmapsLayer;
    let pinCallback = null;
    let showHeatmaps = false;

        // ── Spread (écartement des routes superposées) ──────
    let allDrawnPolylines = [];   // { polyline, baseLatlngs, routeIdx, color, vehiculeId }
    let spreadLabelsLayer  = null;
    let isSpreadMode       = false;
    let isAnimating        = false;
    const SPREAD_METERS    = 14;  // distance en mètres entre routes en mode spread

    let currentDrawId = 0;
    
    let drawnRoutes = []; // [{polyline, circles, markers, baseStops, color}]
    let focusedRouteIdx = null;

    const ICONS = {
        employes: L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
            iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34]
        }),
        destinations: L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
            iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34]
        })
    };

    const PALETTE = ['#6366f1', '#f97316', '#10b981', '#ec4899', '#8b5cf6', '#14b8a6', '#f43f5e', '#eab308'];


    // ─────────────────────────────────────────────────────────────────
//  PERPENDICULAR OFFSET
//  Décale un tableau de [lat,lng] perpendiculairement à la direction
//  de la route de `offsetMeters` mètres.
// ─────────────────────────────────────────────────────────────────
function applyPerpendicularOffset(latlngs, offsetMeters) {
    if (!latlngs || latlngs.length < 2 || Math.abs(offsetMeters) < 0.001) {
        return latlngs;
    }
    // Une translation rigide (diagonale) évite les problèmes de boucles (artefacts) sur les virages serrés.
    const mPerDegLat = 111111;
    // On approxime pour la latitude de Tunis (~36.8)
    const mPerDegLng = mPerDegLat * Math.cos(36.8 * Math.PI / 180);
    
    // Décalage rigide Nord-Est
    const offsetLat = offsetMeters / mPerDegLat;
    const offsetLng = offsetMeters / mPerDegLng;

    return latlngs.map((pt) => {
        const [lat, lng] = Array.isArray(pt) ? pt : [pt.lat, pt.lng];
        return [lat + offsetLat, lng + offsetLng];
    });
}


const SPREAD_GAP_METERS = 20;  // Distance propre et serrée (en mètres) par couche de route

// ─────────────────────────────────────────────────────────────────
//  SPREAD ANIMATION
//  Anime l'écartement ou le rapprochement de toutes les routes.
// ─────────────────────────────────────────────────────────────────
function animateSpread(toSpread, duration = 580) {
    if (isAnimating) return;
    isAnimating = true;

    const n         = allDrawnPolylines.length;
    if (n < 2)      { isAnimating = false; return; }

    const fromVal   = isSpreadMode ? 1 : 0;
    const toVal     = toSpread     ? 1 : 0;
    const startTime = performance.now();

    // Supprimer les labels immédiatement quand on referme
    if (!toSpread) removeSpreadLabels();

    function tick(now) {
        const elapsed  = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease-out cubic : rapide au début, doux à la fin
        const eased = 1 - Math.pow(1 - progress, 3);
        const t     = fromVal + (toVal - fromVal) * eased;

        allDrawnPolylines.forEach((item, i) => {
            // Centrer les offsets autour de 0 :
            // 3 routes → facteurs [-1, 0, 1]
            // 4 routes → [-1.5, -0.5, 0.5, 1.5]
            const factor  = i - (n - 1) / 2;
            
            // Correction ici : Utilisation de SPREAD_GAP_METERS et suppression du multiplicateur sauvage (1 + n * 0.25)
            const offsetM = factor * SPREAD_GAP_METERS * t;
            
            // 1. Déplacer la ligne du trajet (polyline)
            const shifted = applyPerpendicularOffset(item.baseLatlngs, offsetM);
            item.polyline.setLatLngs(shifted);

            // 2. Déplacer les cercles et marqueurs numériques associés
            const elements = drawnRoutes[item.routeIdx];
            if (elements && elements.baseStops) {
                elements.baseStops.forEach((basePt, stopIdx) => {
                    const shiftedPt = applyPerpendicularOffset([basePt], offsetM)[0];
                    if (elements.circles[stopIdx]) {
                        elements.circles[stopIdx].setLatLng(shiftedPt);
                    }
                    if (elements.markers[stopIdx]) {
                        elements.markers[stopIdx].setLatLng(shiftedPt);
                    }
                });
            }
        });

        if (progress < 1) {
            requestAnimationFrame(tick);
        } else {
            isSpreadMode = toSpread;
            isAnimating  = false;
            if (toSpread) showSpreadLabels();
        }
    }

    requestAnimationFrame(tick);
}

    // ─────────────────────────────────────────────────────────────────
    //  LABELS FLOTTANTS EN MODE SPREAD
    //  Affiche le nom du taxi au milieu de chaque route écartée.
    // ─────────────────────────────────────────────────────────────────
    function showSpreadLabels() {
        removeSpreadLabels();

        // Injecter les keyframes CSS si pas encore fait
        if (!document.getElementById('spread-label-css')) {
            const s = document.createElement('style');
            s.id = 'spread-label-css';
            s.textContent = `
                @keyframes labelPop {
                    from { opacity:0; transform:scale(0.4) translateY(6px); }
                    to   { opacity:1; transform:scale(1)   translateY(0);   }
                }
                .spread-label-inner {
                    animation: labelPop 0.28s ease-out forwards;
                    white-space: nowrap;
                    font-family: Inter, sans-serif;
                    font-size: 11px;
                    font-weight: 700;
                    width: max-content;
                    padding: 4px 10px;
                    border-radius: 12px;
                    box-shadow: 0 2px 8px rgba(0,0,0,.4);
                    border: 1.5px solid rgba(255,255,255,.45);
                    color: #3f0000;
                    cursor: pointer;
                }
            `;
            document.head.appendChild(s);
        }

        spreadLabelsLayer = L.layerGroup().addTo(map);
        const n = allDrawnPolylines.length;

        allDrawnPolylines.forEach((item, i) => {
            if (!item.baseLatlngs || item.baseLatlngs.length < 2) return;

            const factor  = i - (n - 1) / 2;
            const offsetM = factor * SPREAD_METERS * (1 + n * 0.25);
            const shifted = applyPerpendicularOffset(item.baseLatlngs, offsetM);

            // Placer le label au tiers de la route (plus lisible que le milieu)
            const labelIdx = Math.floor(shifted.length * 0.35);
            const labelPt  = shifted[Math.max(0, labelIdx)];

            L.marker(labelPt, {
                icon: L.divIcon({
                    className: '',
                    html: `<div class="spread-label-inner"
                                style="background:${item.color};"
                                title="${item.vehiculeId}">
                            ${item.vehiculeId}
                        </div>`,
                    iconSize:   [1, 1],
                    iconAnchor: [0, 10]
                }),
                interactive: true,
                zIndexOffset: 1500
            }).on('click', () => {
                // Cliquer le label → focus sur cette route
                if (window.handleRouteLineClick) {
                    // Récupérer la route correspondante depuis optimizeResult
                    if (window.optimizeResult) {
                        const sug = window.optimizeResult.suggestions[
                            window.currentAlgoIndex || 0
                        ];
                        const route = sug?.routes?.[item.routeIdx];
                        if (route) window.handleRouteLineClick(route);
                    }
                }
            }).addTo(spreadLabelsLayer);
        });
    }

    function removeSpreadLabels() {
        if (spreadLabelsLayer) {
            map.removeLayer(spreadLabelsLayer);
            spreadLabelsLayer = null;
        }
    }

    // ─────────────────────────────────────────────────────────────────
    //  TOGGLE SPREAD  (appelable depuis app.js aussi)
    // ─────────────────────────────────────────────────────────────────
    function toggleSpread() {
        if (isAnimating || allDrawnPolylines.length < 2) return;
        animateSpread(!isSpreadMode);
    }

    function collapseSpread() {
        if (isSpreadMode && !isAnimating) animateSpread(false);
    }

    function init() {
        map = L.map('map', { zoomControl: false }).setView([36.8, 10.17], 12);
        L.control.zoom({ position: 'topright' }).addTo(map);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; CARTO'
        }).addTo(map);

        markersLayer = L.layerGroup().addTo(map);
        routesLayer = L.layerGroup().addTo(map);
        heatmapsLayer = L.layerGroup().addTo(map);

        if (typeof L.Control.Geocoder !== 'undefined') {
            L.Control.geocoder({
                defaultMarkGeocode: false,
                position: 'topright',
                placeholder: 'Rechercher une adresse…'
            }).on('markgeocode', function (e) {
                map.flyToBounds(e.geocode.bbox);
            }).addTo(map);
        }

        map.on('click', function (e) {
            if (pinCallback) {
                const cb = pinCallback;
                cancelPinMode();
                cb(e.latlng);
            }
        });

            // ── Détection zones encombrées → spread au clic
        map.on('click', function (e) {
            // Mode pin : ne pas interférer
            if (pinCallback) return;
            // Clic sur espace vide quand spread actif → fermer
            if (isSpreadMode && !isAnimating) {
                animateSpread(false);
            }
        });
    }

    function clearAll() { 
        currentDrawId++;
        markersLayer.clearLayers(); 
        routesLayer.clearLayers(); 
        heatmapsLayer.clearLayers();
        allDrawnPolylines = [];
        isSpreadMode = false;
        removeSpreadLabels();
        drawnRoutes = []; 
        focusedRouteIdx = null;
    }


    function clearRoutes() { 
        currentDrawId++; 
        routesLayer.clearLayers(); 
        heatmapsLayer.clearLayers(); 
        allDrawnPolylines = [];
        isSpreadMode = false;
        removeSpreadLabels();
        drawnRoutes = []; 
        focusedRouteIdx = null;
        if (window.taxiAnimators) {
            window.taxiAnimators.forEach(a => a.stop());
            window.taxiAnimators = [];
        }
        window.isSimulationRunning = false;
        const btnSimulate = document.getElementById('btn-simulate-taxis');
        if (btnSimulate) {
            btnSimulate.innerHTML = '<i class="ph ph-play-circle"></i> Simuler Taxis';
            btnSimulate.style.display = 'none';
        }
    }

    function addMarkers(appData) {
        markersLayer.clearLayers();
        const coords = [];

        ['employes', 'destinations'].forEach(type => {
            (appData[type] || []).forEach(item => {
                if (item.lat != null && item.lng != null) {
                    const icon = ICONS[type];
                    const marker = L.marker([item.lat, item.lng], { icon }).addTo(markersLayer);
                    
                    marker.on('click', (e) => {
                        L.DomEvent.stopPropagation(e);
                        
                        // Si l'optimisation est faite, on affiche le popup de transfert
                        if (type === 'employes' && window.getEmployeeRoute) {
                            const routeInfo = window.getEmployeeRoute(item._id);
                            if (routeInfo && routeInfo.route && window.handleEmployeeClick) {
                                window.handleEmployeeClick(routeInfo.emp, routeInfo.route);
                                return;
                            }
                        }
                        
                        // Sinon, popup basique
                        let popupHtml = '<div class="popup-title" style="margin-bottom:5px; font-weight:600; font-size:14px;">' + (item.nom || item.id) + '</div>';
                        if (item.residence) {
                            popupHtml += '<div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;"><i class="ph ph-map-pin"></i> ' + item.residence + '</div>';
                        }
                        else {
                            popupHtml += '<div style="margin-bottom:10px;"></div>';
                        }
                        popupHtml += `<button class="btn btn-outline btn-sm w-100"
                            style="font-size:12px;"
                            onclick="window.startRelocalisation('${type}','${item._id}','${(item.nom || item.id).replace(/'/g, "\\'")}')">
                            <i class="ph ph-map-pin"></i> Changer localisation (GPS)</button>`;

                        if (type === 'employes') {
                            popupHtml += `<div style="margin-top:6px;">
                                <button class="btn btn-sm w-100"
                                style="font-size:12px; background:#ef4444; color:#fff; border:none; cursor:pointer; border-radius:6px; padding:6px 10px; display:flex; align-items:center; justify-content:center; gap:6px;"
                                onclick="window.deleteEmployee('${item._id}','${(item.nom || item.id).replace(/'/g, "\\'")}')"
                                ><i class="ph ph-trash"></i> Supprimer cet employe</button></div>`;
                        }
                            
                        L.popup({ maxWidth: 260, closeButton: true, className: 'glass-popup' })
                            .setLatLng([item.lat, item.lng])
                            .setContent('<div style="padding:4px;">' + popupHtml + '</div>')
                            .openOn(map);
                    });
                    
                    coords.push([item.lat, item.lng]);
                }
            });
        });

        if (coords.length && !pinCallback) {
            map.fitBounds(coords, { padding: [60, 60], maxZoom: 14 });
        }
    }

    function enablePinMode(callback) {
        pinCallback = callback;
        map.getContainer().style.cursor = 'crosshair';
    }

    function cancelPinMode() {
        pinCallback = null;
        map.getContainer().style.cursor = '';
    }

    /* ══════════════════════════════════════════════════════
       DRAW MULTI ROUTES
       Dessine les polylines OSRM + les cercles numérotés des employés.
       Chaque cercle ET chaque polyline est cliquable.
    ══════════════════════════════════════════════════════ */
    async function drawMultiRoutes(routes, destination) {
        currentDrawId++;
        const drawId = currentDrawId;
        allDrawnPolylines = [];
        isSpreadMode = false;
        removeSpreadLabels();
        routesLayer.clearLayers();
        drawnRoutes = [];
        focusedRouteIdx = null;
        if (!routes || routes.length === 0) return;

        drawHeatmaps(routes);

        // On dessine chaque route en parallèle (async)
        const drawPromises = routes.map(async (route, idx) => {
            if (!route.waypoints || route.waypoints.length < 2) return;

            const color = PALETTE[(route.originalIdx !== undefined ? route.originalIdx : idx) % PALETTE.length];
            const waypoints = route.waypoints.map(wp => Array.isArray(wp) ? wp : [wp.lat, wp.lng]);

            // ── 1. Récupérer la géométrie OSRM ──
            let latlngs = waypoints;
            try {
                const resp = await fetch('/api/route_geometry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ waypoints })
                });
                const geo = await resp.json();
                if (geo.status === 'success' && geo.latlngs && geo.latlngs.length > 2) {
                    latlngs = geo.latlngs;
                }
            } catch (e) {
                console.warn('OSRM fallback pour route', route.vehicule_id, e);
            }

            if (currentDrawId !== drawId) return; // Abort if another draw started or cleared

            // 2. Dessiner la polyline de la route
            const polyline = L.polyline(latlngs, {
                color, weight: 6, opacity: 0.85,
                lineCap: 'round', lineJoin: 'round'
            }).addTo(routesLayer);
            
           allDrawnPolylines.push({
               polyline,
               baseLatlngs: [...latlngs],    
               routeIdx:   (route.originalIdx !== undefined ? route.originalIdx : idx),
               color,
               vehiculeId: route.vehicule_id || `Taxi ${idx + 1}`
            });

            // Ajout de baseStops pour sauvegarder les positions initiales des employés
            const routeElements = { polyline, circles: [], markers: [], baseStops: [] };

            // Clic sur la ligne :
            polyline.on('click', (e) => {
                L.DomEvent.stopPropagation(e);
                const totalVisible = allDrawnPolylines.length;

                if (totalVisible >= 2 && !isSpreadMode && !isAnimating) {
                    animateSpread(true);
                } else {
                    if (window.handleRouteLineClick) window.handleRouteLineClick(route);
                }
            });

            // Tooltip au survol de la polyline
            polyline.bindTooltip(() => {
                if (allDrawnPolylines.length >= 2 && !isSpreadMode) {
                    return `
                        <div style="text-align:center; line-height:1.5;">
                            <strong style="color:#a5b4fc;">
                                ${allDrawnPolylines.length} trajets superposés
                            </strong><br>
                            <em style="font-size:11px; color:#94a3b8;">
                                Cliquez pour les séparer
                            </em> 
                        </div>`;
                }
                return `
                    <strong>${route.vehicule_id}</strong><br>
                    ${fmt1 ? fmt1(route.distance_km) : route.distance_km} km —
                    ${fmt1 ? fmt1(route.duree_min) : route.duree_min} min —
                    ${route.tarif?.final || 0} TND<br>
                    <em style="font-size:11px; color:#94a3b8;">
                        Cliquez pour les détails
                    </em>`;
            }, { sticky: true, direction: 'top', offset: [0, -4] });

            // 3. Dessiner les cercles numérotés des employés
            route.ordre.forEach((emp, i) => {
                // Sauvegarder la coordonnée géographique d'origine
                routeElements.baseStops.push([emp.lat, emp.lng]);

                // Cercle de fond coloré
                const circle = L.circleMarker([emp.lat, emp.lng], {
                    radius: 14,
                    color: '#fff',
                    fillColor: color,
                    fillOpacity: 0.92,
                    weight: 2.5
                }).addTo(routesLayer);
                routeElements.circles.push(circle);

                // Numéro à l'intérieur
                const numberMarker = L.marker([emp.lat, emp.lng], {
                    icon: L.divIcon({
                        className: '',
                        html: `<div style="color:#fff; font-size:11px; font-weight:800; text-align:center; line-height:28px; pointer-events:none;">${i + 1}</div>`,
                        iconSize: [28, 28],
                        iconAnchor: [14, 14]
                    }),
                    zIndexOffset: 500
                }).addTo(routesLayer);
                routeElements.markers.push(numberMarker);

                // Tooltip au survol : nom de l'employé
                circle.bindTooltip(
                    `<strong>${emp.nom}</strong><br><em style="font-size:11px;color:#94a3b8;">Cliquez pour déplacer vers un autre véhicule</em>`,
                    { direction: 'top', offset: [0, -16] }
                );

                // Clic sur l'employé → popup de transfert
                const onEmpClick = (e) => {
                    L.DomEvent.stopPropagation(e);
                    if (window.handleEmployeeClick) window.handleEmployeeClick(emp, route);
                };
                circle.on('click', onEmpClick);
                numberMarker.on('click', onEmpClick);
            });

            if (destination) {
                L.marker([destination.lat, destination.lng], {
                    icon: L.divIcon({
                        className: '',
                        html: `<div style="background:#ef4444; color:#fff; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:14px; border:2px solid #fff; box-shadow:0 2px 6px rgba(0,0,0,.3);">🏁</div>`,
                        iconSize: [28, 28],
                        iconAnchor: [14, 14]
                    }),
                    zIndexOffset: 1000
                }).bindTooltip(destination.nom, { permanent: false, direction: 'top' })
                    .addTo(routesLayer);
            }

            // ── 5. Animation du Taxi 🚕 ──
            if (latlngs.length > 1) {
                const taxiIcon = L.divIcon({
                    className: '',
                    html: '<div style="font-size:20px; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5)); transform: scaleX(-1);">🚕</div>',
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                });
                const taxiMarker = L.marker(latlngs[0], {icon: taxiIcon, zIndexOffset: 2000, opacity: 0}).addTo(routesLayer);
                
                const detailedPath = [];
                for(let i = 0; i < latlngs.length - 1; i++) {
                    const p1 = latlngs[i];
                    const p2 = latlngs[i+1];
                    const steps = 30;
                    for(let j = 0; j < steps; j++) {
                        const lat = p1[0] + (p2[0] - p1[0]) * (j/steps);
                        const lng = p1[1] + (p2[1] - p1[1]) * (j/steps);
                        detailedPath.push([lat, lng]);
                    }
                }
                detailedPath.push(latlngs[latlngs.length - 1]);
                
                let stepIdx = 0;
                let isSimulating = false;
                const speed = 2;

                function animateTaxi() {
                    if (!isSimulating || !map.hasLayer(taxiMarker)) return;
                    if (stepIdx >= detailedPath.length) {
                        stepIdx = 0;
                    }
                    taxiMarker.setLatLng(detailedPath[stepIdx]);
                    stepIdx += speed;
                    requestAnimationFrame(animateTaxi);
                }

                if (!window.taxiAnimators) window.taxiAnimators = [];
                window.taxiAnimators.push({
                    start: () => {
                        taxiMarker.setOpacity(1);
                        isSimulating = true;
                        stepIdx = 0;
                        taxiMarker.setLatLng(detailedPath[0]);
                        animateTaxi();
                    },
                    stop: () => {
                        isSimulating = false;
                        taxiMarker.setOpacity(0);
                    }
                });
            }
            
            drawnRoutes[route.originalIdx !== undefined ? route.originalIdx : idx] = routeElements;
        });

        await Promise.all(drawPromises);
    }

    /* ══════════ HEATMAP D'ÉDITION (voisinage d'un employé) ══════════ */
    let editHeatmapLayer = null;

    function drawEditHeatmap(emp) {
        if (editHeatmapLayer) { map.removeLayer(editHeatmapLayer); }
        editHeatmapLayer = L.layerGroup().addTo(map);

        [600, 1200, 2000].forEach((r, i) => {
            L.circle([emp.lat, emp.lng], {
                color: '#eab308',
                fillColor: '#eab308',
                fillOpacity: 0.12 - (i * 0.03),
                radius: r,
                weight: i === 0 ? 2 : 1,
                dashArray: i === 0 ? null : '6 4',
                interactive: false
            }).addTo(editHeatmapLayer);
        });

        map.panTo([emp.lat, emp.lng], { animate: true, duration: 0.4 });
    }

    function clearEditHeatmap() {
        if (editHeatmapLayer) { map.removeLayer(editHeatmapLayer); editHeatmapLayer = null; }
    }

    /* ══════════ HEATMAP DE ZONES (toggle) ══════════ */
    function drawHeatmaps(routes) {
        heatmapsLayer.clearLayers();
        if (!showHeatmaps || !routes) return;

        routes.forEach((route, idx) => {
            const color = PALETTE[(route.originalIdx !== undefined ? route.originalIdx : idx) % PALETTE.length];
            if (route.ordre && route.ordre.length > 0) {
                route.ordre.forEach(emp => {
                    [400, 800, 1200, 1600, 2400].forEach((r, i) => {
                        const opacity = 0.35 - (i * 0.07);
                        if (opacity > 0) {
                            L.circle([emp.lat, emp.lng], {
                                color: 'transparent',
                                fillColor: color,
                                fillOpacity: opacity,
                                radius: r,
                                interactive: false
                            }).addTo(heatmapsLayer);
                        }
                    });
                });
            }
        });
    }

    function toggleHeatmap(show, routes) {
        showHeatmaps = show;
        drawHeatmaps(routes);
    }

    function closePopup() { map.closePopup(); }
    function getMap() { return map; }
    
    function focusRoute(routeIdx) {
        if (drawnRoutes.length === 0) return;
        focusedRouteIdx = routeIdx;

        drawnRoutes.forEach((r, i) => {
            if (!r) return;
            const isFocused = (i === routeIdx);
            r.polyline?.setStyle({
                opacity:  isFocused ? 0.92 : 0.10,
                weight:   isFocused ? 8    : 4
            });
            r.circles?.forEach(c  => c.setStyle({ fillOpacity: isFocused ? 0.95 : 0.08, opacity: isFocused ? 1 : 0.1 }));
            r.markers?.forEach(m  => {
                const el = m.getElement();
                if (el) el.style.opacity = isFocused ? '1' : '0.08';
            });
        });

        const focused = drawnRoutes[routeIdx];
        if (focused?.polyline) {
            map.fitBounds(focused.polyline.getBounds(), { padding: [60, 60], maxZoom: 15 });
        }
    }

    function unfocusAll() {
        focusedRouteIdx = null;
        drawnRoutes.forEach(r => {
            if (!r) return;
            r.polyline?.setStyle({ opacity: 0.85, weight: 6 });
            r.circles?.forEach(c  => c.setStyle({ fillOpacity: 0.92, opacity: 1 }));
            r.markers?.forEach(m  => {
                const el = m.getElement();
                if (el) el.style.opacity = '1';
            });
        });
        const allBounds = drawnRoutes
            .filter(r => r?.polyline)
            .map(r => r.polyline.getBounds());
        if (allBounds.length > 1) {
            const combined = allBounds.reduce((acc, b) => acc.extend(b), allBounds[0]);
            map.fitBounds(combined, { padding: [60, 60] });
        }
    }

    return {
        init, clearAll, clearRoutes, addMarkers,
        enablePinMode, cancelPinMode,
        drawMultiRoutes, toggleHeatmap,
        drawEditHeatmap, clearEditHeatmap,
        closePopup, getMap,
        focusRoute, unfocusAll,
        toggleSpread, collapseSpread
    };
})();