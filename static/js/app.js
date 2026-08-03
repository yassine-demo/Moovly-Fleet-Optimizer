
const fmt2 = v => +(parseFloat(v) || 0).toFixed(2);  // monétaire et CO₂
const fmt1 = v => +(parseFloat(v) || 0).toFixed(1);  // distances et durées

function animateCounter(el, target, decimals = 1, duration = 800) {
    if (!el) return;
    const start = 0;
    const startTime = performance.now();
    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        const current = start + (target - start) * eased;
        el.textContent = current.toFixed(decimals);
        if (progress < 1) requestAnimationFrame(update);
        else el.textContent = target.toFixed(decimals);
    }
    requestAnimationFrame(update);
}

document.addEventListener('DOMContentLoaded', () => {
    MoovlyMap.init();

    const $ = id => document.getElementById(id);
    const panels = document.querySelectorAll('.panel');
    const steps = document.querySelectorAll('.step');

    const appData = { employes: [], destinations: [] };
    let selectedEmpIds = new Set();
    let selectedDestId = null;
    let optimizeResult = null;
    let selectedRoutesIndexes = new Set();

    // Chart instances
    let co2ChartInst = null, costChartInst = null, fleetChartInst = null;
    let cmpVehInst = null, cmpDistInst = null, cmpCostInst = null, cmpCo2Inst = null;

    /* ══════════ THEME & MAIN NAV ══════════ */
    const themeToggle = $('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', newTheme);
            if (themeToggle.querySelector('i')) {
                themeToggle.querySelector('i').className = newTheme === 'dark' ? 'ph ph-moon' : 'ph ph-sun';
            }
            if (optimizeResult) {
                const sug = optimizeResult.suggestions[window.currentAlgoIndex || 0];
                renderRSEDashboard(sug.rse_metrics, sug);
            }
        });
    }

    function switchMainView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const view = $(viewId);
    if (view) view.classList.add('active');

    // Associer chaque viewId à son bouton nav
    let btnId;
    if (viewId === 'view-planning') {
        btnId = 'nav-btn-planning';
    } else if (viewId === 'view-dashboard') {
        btnId = 'nav-btn-dashboard';
    } else if (viewId === 'view-params' || viewId === 'view-settings') {
        btnId = 'nav-btn-params';
    } else {
        btnId = 'nav-btn-dashboard'; // fallback
    }

    const btn = $(btnId);
    if (btn) btn.classList.add('active');

    if (viewId === 'view-planning' && window.MoovlyMap) {
        setTimeout(() => MoovlyMap.getMap().invalidateSize(), 100);
    }
}

    if ($('nav-btn-planning')) $('nav-btn-planning').addEventListener('click', () => switchMainView('view-planning'));
    if ($('nav-btn-dashboard')) $('nav-btn-dashboard').addEventListener('click', () => {
        if (!optimizeResult) { showToast('Veuillez d\'abord lancer une optimisation.', 'warning'); return; }
        switchMainView('view-dashboard');
        const sug = optimizeResult.suggestions[window.currentAlgoIndex || 0];
        renderRSEDashboard(sug.rse_metrics, sug);
        buildComparatorPanel(); // Construire les boutons de capacité
    });

    // --- Settings Logic ---
    async function loadSettings() {
        try {
            const res = await fetch('/api/get_settings');
            const data = await res.json();
            if (data.status === 'success') {
                if (data.tarifs) {
                    if ($('tarif-prise-en-charge')) $('tarif-prise-en-charge').value = data.tarifs.prise_en_charge;
                    if ($('tarif-pas-distance')) $('tarif-pas-distance').value = data.tarifs.pas_distance;
                    if ($('tarif-pas-temps')) $('tarif-pas-temps').value = data.tarifs.pas_temps;
                    if ($('tarif-prix-pas')) $('tarif-prix-pas').value = data.tarifs.prix_pas;
                    if ($('tarif-coef-hp')) $('tarif-coef-hp').value = data.tarifs.coef_hp;
                    if ($('tarif-coef-weekend')) $('tarif-coef-weekend').value = data.tarifs.coef_weekend;
                    if ($('tarif-taux-arret')) $('tarif-taux-arret').value = data.tarifs.taux_arret;
                }
                if (data.env) {
                    if ($('setting-co2-factor')) $('setting-co2-factor').value = data.env.co2_factor;
                    if ($('setting-vitesse-moyenne')) $('setting-vitesse-moyenne').value = data.env.vitesse_moyenne;
                    if ($('setting-detour-factor')) $('setting-detour-factor').value = data.env.detour_factor;
                }
                if (data.optim) {
                    if ($('setting-ortools-timeout')) $('setting-ortools-timeout').value = data.optim.ortools_timeout;
                    if ($('setting-clustering')) $('setting-clustering').value = data.optim.clustering_method;
                }
            }
        } catch (e) {
            console.error('Failed to load settings', e);
        }
    }

    async function saveSettings(payload) {
        showLoading('Enregistrement des paramètres...');
        try {
            const res = await fetch('/api/save_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.status === 'success') {
                showToast('<i class="ph ph-check-circle"></i> ' + data.message, 'success');
            } else {
                showToast(data.message, 'error');
            }
        } catch (e) {
            showToast('Erreur de connexion', 'error');
        } finally {
            hideLoading();
        }
    }

    if ($('btn-save-tarifs')) {
        $('btn-save-tarifs').addEventListener('click', () => {
            saveSettings({
                tarifs: {
                    prise_en_charge: parseFloat($('tarif-prise-en-charge').value),
                    pas_distance: parseFloat($('tarif-pas-distance').value),
                    pas_temps: parseFloat($('tarif-pas-temps').value),
                    prix_pas: parseFloat($('tarif-prix-pas').value),
                    coef_hp: parseFloat($('tarif-coef-hp').value),
                    coef_weekend: parseFloat($('tarif-coef-weekend').value),
                    taux_arret: parseFloat($('tarif-taux-arret').value)
                }
            });
        });
    }

    if ($('btn-save-env')) {
        $('btn-save-env').addEventListener('click', () => {
            saveSettings({
                env: {
                    co2_factor: parseFloat($('setting-co2-factor').value),
                    vitesse_moyenne: parseFloat($('setting-vitesse-moyenne').value),
                    detour_factor: parseFloat($('setting-detour-factor').value)
                }
            });
        });
    }

    if ($('btn-save-optim')) {
        $('btn-save-optim').addEventListener('click', () => {
            saveSettings({
                optim: {
                    ortools_timeout: parseInt($('setting-ortools-timeout').value, 10),
                    clustering_method: $('setting-clustering').value
                }
            });
        });
    }

    if ($('btn-reset-tarifs')) {
        $('btn-reset-tarifs').addEventListener('click', () => {
            $('tarif-prise-en-charge').value = 0.900;
            $('tarif-pas-distance').value = 79;
            $('tarif-pas-temps').value = 18;
            $('tarif-prix-pas').value = 0.046;
            $('tarif-coef-hp').value = 1.20;
            $('tarif-coef-weekend').value = 1.15;
            $('tarif-taux-arret').value = 8;
        });
    }

    function applyCapacityMode(mode) {
        window.modeCapacite = mode === 'ia' ? 'ia' : 'fixe';
        const btnFixe = $('btn-mode-fixe');
        const btnIa = $('btn-mode-ia');
        const wrapFixe = $('wrapper-cap-fixe');
        const wrapIa = $('wrapper-cap-ia');

        if (!btnFixe || !btnIa || !wrapFixe || !wrapIa) return;

        if (window.modeCapacite === 'ia') {
            btnIa.style.background = 'rgba(139, 92, 246, 0.2)';
            btnIa.style.color = '#fff';
            btnIa.style.borderColor = 'rgba(139, 92, 246, 0.4)';
            btnFixe.style.background = 'transparent';
            btnFixe.style.color = 'var(--text-muted)';
            btnFixe.style.borderColor = 'transparent';
            wrapFixe.classList.add('hidden');
            wrapIa.classList.remove('hidden');
        } else {
            btnFixe.style.background = 'var(--surface)';
            btnFixe.style.color = 'var(--text-primary)';
            btnFixe.style.borderColor = 'var(--border)';
            btnIa.style.background = 'transparent';
            btnIa.style.color = 'var(--text-muted)';
            btnIa.style.borderColor = 'transparent';
            wrapFixe.classList.remove('hidden');
            wrapIa.classList.add('hidden');
        }
    }

    function initCapacityModeControls() {
        const btnFixe = $('btn-mode-fixe');
        const btnIa = $('btn-mode-ia');
        if (btnFixe) btnFixe.addEventListener('click', () => applyCapacityMode('fixe'));
        if (btnIa) btnIa.addEventListener('click', () => applyCapacityMode('ia'));
        applyCapacityMode(window.modeCapacite || 'fixe');
    }

    initCapacityModeControls();

    // Helper global pour récupérer la route d'un employé depuis son ID
    window.getEmployeeRoute = function (empId) {
        if (!optimizeResult || !optimizeResult.suggestions || optimizeResult.suggestions.length === 0) return null;
        const suggestion = optimizeResult.suggestions[window.currentAlgoIndex || 0];
        for (let r of suggestion.routes) {
            const emp = r.ordre.find(e => e._id === empId);
            if (emp) return { emp: emp, route: r };
        }
        return null;
    };

    // Legacy integration
    if ($('btn-goto-dashboard')) $('btn-goto-dashboard').addEventListener('click', () => {
        if (!optimizeResult) return;
        switchMainView('view-dashboard');
        const sug = optimizeResult.suggestions[window.currentAlgoIndex || 0];
        renderRSEDashboard(sug.rse_metrics, sug);
        buildComparatorPanel();
    });

    /* ══════════ SIDEBAR TOGGLE ══════════ */
    const sidebarToggler = $('sidebar-toggler');
    const subSidebar = $('sub-sidebar');
    if (sidebarToggler && subSidebar) {
        sidebarToggler.addEventListener('click', () => {
            subSidebar.classList.toggle('collapsed');
            const isCollapsed = subSidebar.classList.contains('collapsed');
            sidebarToggler.innerHTML = isCollapsed ? '<i class="ph ph-caret-right"></i>' : '<i class="ph ph-caret-left"></i>';
            setTimeout(() => { if (window.MoovlyMap) MoovlyMap.getMap().invalidateSize(); }, 300);
        });
    }

    /* ══════════ TOASTS ══════════ */
    function showToast(msg, type = 'info', duration = 3000) {
        const c = $('toast-container');
        const t = document.createElement('div');
        t.className = 'app-toast toast-' + type;
        let icon = 'ph-info';
        if (type === 'success') icon = 'ph-check-circle';
        if (type === 'error') icon = 'ph-x-circle';
        if (type === 'warning') icon = 'ph-warning';
        t.innerHTML = `<i class="ph ${icon} text-lg"></i> <span>${msg}</span>`;
        c.appendChild(t);
        setTimeout(() => { t.classList.add('toast-exit'); setTimeout(() => t.remove(), 400); }, duration);
    }

    if ($('route-modal-close')) $('route-modal-close').addEventListener('click', () => $('modal-route-details').classList.add('hidden'));
    if ($('route-modal-close-btn')) $('route-modal-close-btn').addEventListener('click', () => $('modal-route-details').classList.add('hidden'));

    /* ══════════ LOADING ══════════ */
    window.currentAbortController = null;
    
    function showLoading(text, canCancel = false) { 
        $('loading-text').textContent = text; 
        $('loading').classList.remove('hidden'); 
        if (canCancel && $('btn-cancel-loading')) {
            $('btn-cancel-loading').classList.remove('hidden');
        } else if ($('btn-cancel-loading')) {
            $('btn-cancel-loading').classList.add('hidden');
        }
    }
    
    function hideLoading() { 
        $('loading').classList.add('hidden'); 
        if ($('btn-cancel-loading')) $('btn-cancel-loading').classList.add('hidden');
    }

    if ($('btn-cancel-loading')) {
        $('btn-cancel-loading').addEventListener('click', () => {
            if (window.currentAbortController) {
                window.currentAbortController.abort();
                window.currentAbortController = null;
            }
            hideLoading();
            showToast('<i class="ph ph-warning-circle"></i> Action annulée par l\'utilisateur.', 'warning');
            
            // Re-show the batch save button if there are pending modifications
            if (window.pendingManualClusterIds && document.getElementById('btn-batch-save')) {
                document.getElementById('btn-batch-save').style.display = 'block';
            }
        });
    }

    /* ══════════ NAVIGATION ══════════ */
    // panels 0-indexed: 0=import 1=config 2=results 3=rse 4=comparator
    function goToPanel(n) {
        panels.forEach((p, i) => p.classList.toggle('active', i === n));
        // stepper only covers panels 0-2
        steps.forEach((s, i) => {
            s.classList.remove('active', 'done');
            if (i < n && n <= 2) s.classList.add('done');
            else if (i === n && n <= 2) s.classList.add('active');
        });
    }

    // Legacy alias used elsewhere
    function goToStep(n) { goToPanel(n - 1); if (n === 2) buildConfigPanel(); }

    /* ══════════ UPLOAD BADGES ══════════ */
    function markUploaded(type, count) {
        const b = $('badge-' + type);
        if (b) { b.textContent = count + ' pts'; b.classList.add('success'); }
        checkStep1Ready();
    }
    function checkStep1Ready() {
        $('btn-go-step2').disabled = !(appData.employes.length > 0 && appData.destinations.length > 0);
    }

    /* ══════════ RÉINITIALISATION DE LA PLATEFORME ══════════ */
    const btnReset = $('btn-reset-platform');
    if (btnReset) {
        btnReset.addEventListener('click', async () => {
            // 1. Demander confirmation
            if (!confirm('Voulez-vous vraiment tout effacer ? Les employés, la destination et les routes seront supprimés.')) {
                return;
            }

            // 2. Montrer le loader
            if (typeof showLoading === 'function') showLoading('Réinitialisation en cours...');

            try {
                // 3. Vider le backend
                await fetch('/api/clear_store', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                // 4. Recharger la page complètement (réinitialise la carte, la mémoire, etc.)
                window.location.reload();

            } catch (err) {
                console.error('Erreur reset:', err);
                if (typeof showToast === 'function') showToast('Erreur lors de la réinitialisation', 'error');
                if (typeof hideLoading === 'function') hideLoading();
            }
        });
    }


    /* ══════════ FILE UPLOAD ══════════ */
    document.querySelectorAll('.upload-input').forEach(inp => {
        inp.addEventListener('change', async function () {
            const type = this.dataset.type;
            const file = this.files[0];
            if (!file) return;
            showLoading('Envoi ' + type + '…');
            const fd = new FormData();
            fd.append('file', file);
            try {
                const res = await fetch('/api/upload_employes', { method: 'POST', body: fd });
                const json = await res.json();
                if (json.status !== 'success') throw new Error(json.message);
                appData[type] = json[type];

                // --- FIX: Empêcher la superposition (Jittering) des coordonnées identiques ---
                if (appData[type]) {
                    const seen = new Set();
                    const JITTER = 0.00015; // ~15 mètres
                    appData[type].forEach(item => {
                        if (item.lat != null && item.lng != null) {
                            let lat = parseFloat(item.lat);
                            let lng = parseFloat(item.lng);
                            let key = lat.toFixed(5) + ',' + lng.toFixed(5);
                            let count = 0;
                            while (seen.has(key)) {
                                count++;
                                const angle = count * Math.PI / 3;
                                const radius = JITTER * Math.ceil(count / 6);
                                lat += Math.cos(angle) * radius;
                                lng += Math.sin(angle) * radius;
                                key = lat.toFixed(5) + ',' + lng.toFixed(5);
                            }
                            seen.add(key);
                            item.lat = lat;
                            item.lng = lng;
                        }
                    });
                }
                // -----------------------------------------------------------------------------

                markUploaded(type, json.count);
                refreshMap();
                showToast(json.count + ' employés importés', 'success');

                // Afficher les erreurs de géocodage
                const failures = json.geocode_failures || [];
                updateGeocodeErrors(failures);
                if (failures.length > 0) {
                    showToast(failures.length + ' adresse(s) non trouvée(s), voir l\'icône ⚠️', 'warning', 5000);
                }
            } catch (err) { showToast('Erreur: ' + err.message, 'error'); }
            hideLoading();
        });
    });

    /* ══════════ GEOCODE ERRORS POPUP ══════════ */
    function updateGeocodeErrors(failures) {
        const container = $('geocode-errors-container');
        const badge     = $('geocode-error-badge');
        const list      = $('geocode-error-list');
        if (!container || !badge || !list) return;

        list.innerHTML = '';
        if (failures.length === 0) {
            container.classList.add('hidden');
            return;
        }
        container.classList.remove('hidden');
        badge.textContent = failures.length;
        failures.forEach(addr => {
            const li = document.createElement('li');
            li.innerHTML = `<i class="ph ph-map-pin-simple-slash"></i><span>${addr}</span>`;
            list.appendChild(li);
        });
    }

    const errBtn   = $('geocode-error-btn');
    const errPopup = $('geocode-error-popup');
    if (errBtn && errPopup) {
        errBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            errPopup.classList.toggle('hidden');
        });
        document.addEventListener('click', () => errPopup.classList.add('hidden'));
    }

    /* ══════════ DESTINATIONS (Manuel uniquement) ══════════ */

    /* ══════════ MANUAL PIN ══════════ */
    const pinToast = $('pin-toast');
    const pinName = $('pin-name');
    const modal = $('modal-manual');
    let pendingPin = null;

    document.querySelectorAll('.btn-pin-manual').forEach(btn => {
        btn.addEventListener('click', () => startManualAdd(btn.dataset.type));
    });

    function startManualAdd(type) {
        pinName.textContent = 'Cliquez sur la carte pour positionner – ' + type;
        pinToast.classList.remove('hidden');
        MoovlyMap.enablePinMode(function (latlng) {
            pinToast.classList.add('hidden');
            pendingPin = { type, latlng };
            $('modal-title').textContent = type === 'employes' ? 'Nouvel Employé' : 'Nouvelle Destination';
            $('modal-name').value = '';
            $('modal-cap-group').classList.add('hidden');
            modal.classList.remove('hidden');
        });
    }

    $('modal-close').addEventListener('click', () => modal.classList.add('hidden'));
    $('modal-save').addEventListener('click', () => {
        if (!pendingPin) return;
        const { type, latlng } = pendingPin;
        const nom = $('modal-name').value.trim() ||
            (type === 'employes' ? 'Employé Manuel ' + (appData.employes.length + 1) : 'Destination Manuelle');
        const newItem = { id: type[0].toUpperCase() + (appData[type].length + 1), nom, lat: latlng.lat, lng: latlng.lng };
        modal.classList.add('hidden');
        showLoading('Enregistrement…');
        fetch('/api/add_manual', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type, item: newItem })
        }).then(r => r.json()).then(json => {
            if (json.status === 'success') {
                newItem._id = json._id;
                // Si c'est une destination, on remplace l'existante pour n'en avoir qu'une seule
                if (type === 'destinations') {
                    appData[type] = [newItem];
                    const destInfo = $('destination-info');
                    if (destInfo) destInfo.textContent = `📍 ${newItem.nom}`;
                } else {
                    appData[type].push(newItem);
                }
                markUploaded(type, appData[type].length);
                MoovlyMap.addMarkers(appData);
                showToast('Point enregistré !', 'success');
            } else { showToast('Erreur: ' + json.message, 'error'); }
        }).catch(err => showToast('Erreur: ' + err.message, 'error'))
            .finally(() => hideLoading());
    });

    $('btn-cancel-pin').addEventListener('click', () => { MoovlyMap.cancelPinMode(); pinToast.classList.add('hidden'); });

    /* ══════════ RELOCALISATION ══════════ */
    window.startRelocalisation = async function (type, id, nom) {
        MoovlyMap.closePopup();
        pinName.textContent = nom + ' (' + type + ') – Relocalisation';
        pinToast.classList.remove('hidden');
        MoovlyMap.enablePinMode(async function (latlng) {
            pinToast.classList.add('hidden');
            const idx = appData[type].findIndex(i => i._id === id);
            if (idx > -1) { appData[type][idx].lat = latlng.lat; appData[type][idx].lng = latlng.lng; }
            MoovlyMap.clearRoutes(); MoovlyMap.addMarkers(appData);
            try {
                const resp = await fetch('/api/update_location', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type, id, lat: latlng.lat, lng: latlng.lng })
                });
                const json = await resp.json();
                if (json.status !== 'success') { showToast('Erreur serveur: ' + json.message, 'error'); return; }
            } catch (err) { showToast('Erreur réseau: ' + err.message, 'error'); return; }
            if (panels[2].classList.contains('active')) {
                goToStep(2);
                showToast("Position mise à jour. Relancez l'optimisation.", 'warning', 5000);
            } else { showToast('Position de ' + nom + ' mise à jour.', 'success'); }
        });
    };

        /* ══════════ SUPPRESSION EMPLOYÉ ══════════ */
    window.deleteEmployee = function (id, nom) {
        MoovlyMap.closePopup();
        appData.employes = appData.employes.filter(e => e._id !== id);
        selectedEmpIds.delete(id);
        MoovlyMap.clearRoutes();
        MoovlyMap.addMarkers(appData);
        markUploaded('employes', appData.employes.length);
        checkRunReady();
        // Re-build config panel if it's visible (step 2)
        if (panels[1] && panels[1].classList.contains('active')) {
            buildConfigPanel();
        }
        showToast('<i class="ph ph-trash"></i> ' + nom + ' supprimé. ', 'warning', 5000);
    };

    /* ══════════ TAXI INDIVIDUEL (Forçage manuel en Batch) ══════════ */
    window.forcerTaxiIndividuel = function (employeeId) {
        MoovlyMap.getMap().closePopup();
        
        if (!employeeId || !optimizeResult) {
            showToast('Erreur : Aucune optimisation active.', 'error');
            return;
        }

        const suggestion = optimizeResult.suggestions[window.currentAlgoIndex || 0];
        if (!suggestion) return;

        // 1. Initialiser les clusters en attente si ce n'est pas déjà fait
        if (!window.pendingManualClusterIds) {
            window.originalManualClusterIds = JSON.stringify(suggestion.routes.map(r => r.ordre.map(e => e._id)));
            window.pendingManualClusterIds = suggestion.routes.map(r => r.ordre.map(e => e._id));
        }

        // 2. Retirer l'employé de son cluster actuel
        let removed = false;
        for (let i = 0; i < window.pendingManualClusterIds.length; i++) {
            const cluster = window.pendingManualClusterIds[i];
            const idx = cluster.indexOf(employeeId);
            if (idx !== -1) {
                cluster.splice(idx, 1);
                removed = true;
                break;
            }
        }

        if (removed) {
            // 3. Ajouter l'employé dans son propre cluster (taxi individuel)
            window.pendingManualClusterIds.push([employeeId]);
            
            // 4. Appeler la fonction qui gère l'affichage du bouton !
            if (typeof checkAndShowBatchSaveButton === 'function') {
                checkAndShowBatchSaveButton();
            }
            
            showToast('🚖 Employé mis en taxi individuel. Cliquez sur "Enregistrer" pour appliquer.', 'info', 4000);
        } else {
            showToast('Erreur : Employé introuvable dans les trajets actuels.', 'error');
        }
    };

    $('btn-go-step2').addEventListener('click', () => goToStep(2));
    $('btn-back-step1').addEventListener('click', () => goToStep(1));
    $('btn-new').addEventListener('click', () => { MoovlyMap.clearRoutes(); goToStep(2); });

    $('btn-show-rse').addEventListener('click', () => {
        if (optimizeResult) {
            const sug = optimizeResult.suggestions[window.currentAlgoIndex || 0];
            renderRSEDashboard(sug.rse_metrics, sug);
        }
        goToPanel(3);
    });

    $('btn-back-rse').addEventListener('click', () => goToPanel(2));
    $('btn-show-comparator').addEventListener('click', () => { buildComparatorPanel(); goToPanel(4); });
    $('btn-back-comparator').addEventListener('click', () => goToPanel(2));

    function refreshMap() { MoovlyMap.clearAll(); MoovlyMap.addMarkers(appData); }

    /* ══════════ STEP 2: CONFIG ══════════ */
    function buildConfigPanel() {
        const empList = $('emp-list');
        empList.innerHTML = '';
        selectedEmpIds.clear();

        appData.employes.forEach(emp => {
            if (emp.lat == null) return;
            const div = document.createElement('div');
            div.className = 'emp-item';
            div.style.display = 'flex';
            div.style.alignItems = 'center';
            div.innerHTML = '<span class="emp-check"></span><span class="emp-name" style="flex-grow: 1;">' + emp.nom + '</span><button class="btn-delete-emp" title="Supprimer cet employé" style="background: none; border: none; cursor: pointer; color: #ef4444; padding: 4px;"><i class="ph ph-trash"></i></button>';
            div.addEventListener('click', (e) => {
                if (e.target.closest('.btn-delete-emp')) {
                    e.stopPropagation();
                    appData.employes = appData.employes.filter(item => item._id !== emp._id);
                    selectedEmpIds.delete(emp._id);
                    div.remove();
                    refreshMap();
                    markUploaded('employes', appData.employes.length);
                    checkRunReady();
                    return;
                }
                if (selectedEmpIds.has(emp._id)) { selectedEmpIds.delete(emp._id); div.classList.remove('selected'); }
                else { selectedEmpIds.add(emp._id); div.classList.add('selected'); }
                checkRunReady();
            });
            empList.appendChild(div);
        });

        const sel = $('dest-select');
        sel.innerHTML = '<option value="">— Choisir une destination —</option>';
        appData.destinations.forEach(d => {
            if (d.lat == null) return;
            const opt = document.createElement('option');
            opt.value = d._id; opt.textContent = d.nom;
            sel.appendChild(opt);
        });
        if (appData.destinations.length > 0) {
            sel.value = appData.destinations[0]._id;
            selectedDestId = appData.destinations[0]._id;
        }
        sel.addEventListener('change', function () { selectedDestId = this.value || null; checkRunReady(); });

        $('select-all-emp').addEventListener('click', () => {
            empList.querySelectorAll('.emp-item').forEach((div, i) => {
                const emp = appData.employes.filter(e => e.lat != null)[i];
                if (emp) { selectedEmpIds.add(emp._id); div.classList.add('selected'); }
            });
            checkRunReady();
        });
        $('deselect-all-emp').addEventListener('click', () => {
            selectedEmpIds.clear();
            empList.querySelectorAll('.emp-item').forEach(d => d.classList.remove('selected'));
            checkRunReady();
        });
        checkRunReady();
    }

    function checkRunReady() { $('btn-run').disabled = !(selectedEmpIds.size > 0 && selectedDestId); }



    function getPoidsNormalises() {
        return {
            distance: 0.3333,
            cout:     0.3333,
            co2:      0.3334
        };
    }

    /* ══════════ OPTIMIZE ══════════ */
    $('btn-run').addEventListener('click', async () => {
        $('loading-text').innerHTML = `<div style="display:flex; flex-direction:column; gap:8px; align-items:center; width:250px;">
            <div id="prog-msg" style="font-weight:600; font-size:14px; text-align:center;">Démarrage...</div>
            <div style="width:100%; height:12px; background:#1e293b; border-radius:6px; overflow:hidden; border:1px solid #334155;">
                <div id="prog-bar" style="width:0%; height:100%; background:#6366f1; transition:width 0.4s ease;"></div>
            </div>
            <div id="prog-pct" style="font-size:12px; color:#94a3b8;">0%</div>
        </div>`;
        $('loading').classList.remove('hidden');

        try {
            const response = await fetch('/api/optimize_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    selected_employes_ids: [...selectedEmpIds],
                    destination_id: selectedDestId,
                    capacite: window.modeCapacite === 'ia' ? 'ia' : (parseInt($('taxi-capacity').value) || 4),
                    poids: getPoidsNormalises()
                })
            });
            const reader = response.body.getReader();
            let buffer = '';

            function decodeChunk(chunk) {
                if (typeof TextDecoder !== 'undefined') {
                    const decoder = window.__moovlyDecoder || (window.__moovlyDecoder = new TextDecoder());
                    return decoder.decode(chunk, { stream: true });
                }
                if (chunk instanceof Uint8Array) {
                    return Array.from(chunk).map(b => String.fromCharCode(b)).join('');
                }
                return String(chunk || '');
            }

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decodeChunk(value);
                const lines = buffer.split('\n');
                buffer = lines.pop(); // last partial line
                for (let line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const json = JSON.parse(line.substring(6));
                            if (json.step !== 'done' && json.step !== 'error') {
                                const bar = $('prog-bar');
                                const msg = $('prog-msg');
                                const pct = $('prog-pct');
                                if(bar) bar.style.width = json.pct + '%';
                                if(msg) msg.textContent = json.msg;
                                if(pct) pct.textContent = json.pct + '%';
                            } else if (json.step === 'done') {
                                optimizeResult = json.result;
                                displayResults(json.result);
                                goToPanel(2);
                                hideLoading();
                            } else if (json.step === 'error') {
                                throw new Error(json.message);
                            }
                        } catch(e) {}
                    }
                }
            }
        } catch (err) { showToast('Erreur: ' + err.message, 'error'); hideLoading(); }
    });

    /* ══════════ DISPLAY RESULTS ══════════ */
    function displayResults(data) {
        optimizeResult = data;

        // Sauvegarder dans l'historique automatiquement
        const best = data.suggestions?.find(s => s.is_best) || data.suggestions?.[0];
        if (best) {
            fetch('/api/save_historique', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    nb_employes:    best.routes?.reduce((a, r) => a + r.ordre.length, 0) || 0,
                    nb_vehicules:   best.routes?.length || 0,
                    capacite:       window.modeCapacite === 'ia' ? 'ia' : (parseInt($('taxi-capacity')?.value) || 4),
                    distance_km:    best.distance_km || 0,
                    duree_min:      best.duree_min || 0,
                    tarif_tnd:      best.tarif?.final || 0,
                    co2_kg:         best.rse_metrics?.co2_scenario_moovly || 0,
                    co2_saved_kg:   best.rse_metrics?.co2_saved_kg || 0,
                    cost_saved_tnd: best.rse_metrics?.cost_saved_tnd || 0,
                    methode:        best.methode || '',
                    destination_nom: best.destination?.nom || ''
                })
            }).catch(() => {}); // Silencieux, non bloquant
        }

        const suggestions = data.suggestions || [];
        const listDiv = $('strategies-list');
        listDiv.innerHTML = '';
        if (suggestions.length === 0) {
            $('suggestions-list').innerHTML = '<div class="section-hint">Aucun trajet trouvé.</div>';
            return;
        }
        const bestIdx = suggestions.findIndex(s => s.is_best) >= 0 ? suggestions.findIndex(s => s.is_best) : 0;
        window.currentAlgoIndex = bestIdx;

        let html = '';
        suggestions.forEach((sug, idx) => {
            const active = (idx === bestIdx) ? 'active' : '';
            const trophy = sug.is_best ? '<span class="badge-best" style="font-size:10px; background:var(--bg-primary); padding:2px 6px; border-radius:4px; margin-left:6px; color:#fff;">🏆 Meilleur score</span>' : '';
            const nameClean = sug.methode.replace(' (Recommandé) 🏆', '').trim();
            html += `<div class="strategy-item ${active}" data-idx="${idx}">
                <div>
                    <div class="strategy-name">${nameClean} ${trophy}</div>
                    <div class="strategy-stats" style="color: #6366f1; font-weight: 600;">${fmt1(sug.distance_km)} km • ${fmt1(sug.duree_min)} min</div>
                    <div style="font-size:0.75rem; color:#94a3b8; margin-top:4px;">Clustering: ${sug.clustering_method || 'N/A'}</div>
                    <div style="font-size:0.75rem; color:#6366f1; margin-top:2px;">Score composite : ${sug.score_composite}</div>
                </div>
            </div>`;
        });
        listDiv.innerHTML = html;

        const cards = listDiv.querySelectorAll('.strategy-item');
        cards.forEach(card => {
            card.addEventListener('click', () => {
                cards.forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                window.currentAlgoIndex = parseInt(card.getAttribute('data-idx'));
                renderSuggestion(suggestions[window.currentAlgoIndex]);
            });
        });
        renderSuggestion(suggestions[window.currentAlgoIndex]);

        // Suggestion automatique de capacité optimale
        if (optimizeResult && optimizeResult.suggestions && optimizeResult.suggestions.length > 0) {
            const currentSuggestion = optimizeResult.suggestions[0];
            const allEmps = currentSuggestion.routes.flatMap(r => r.ordre);
            
            // Read what the user actually inputted in the configuration panel
            const activeCapacity = parseInt($('taxi-capacity').value) || 3;

            fetch('/api/compare_scenarios', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    selected_employes_ids: [...selectedEmpIds],
                    destination_id: selectedDestId,
                    capacites: [2, 3, 4],
                    current_capacity: activeCapacity, // Send the baseline capacity to the backend
                    employes_data: allEmps,
                    destination_data: currentSuggestion.destination,
                    poids: getPoidsNormalises()
                })
            })
            .then(res => res.json())
            .then(json => {
                if (json.status === 'success' && json.scenarios && json.scenarios.length > 0) {
                    // Find the scenario with the minimum cost
                    const best = json.scenarios.reduce((prev, curr) => 
                        curr.tarif_tnd < prev.tarif_tnd ? curr : prev
                    );

                    // Only display a recommendation if the best capacity found is DIFFERENT from the active capacity
                    if (best.capacite !== activeCapacity) {
                        showToast(
                            `💡 Capacité recommandée : ${best.capacite} places (économie de ${best.cost_saved_tnd.toFixed(2)} TND par rapport à votre choix de ${activeCapacity} places)`,
                            'info',
                            8000
                        );
                    } else {
                        console.log(`La capacité actuelle (${activeCapacity}) est déjà optimale.`);
                    }
                }
            })
            .catch(err => console.warn("Erreur suggestion capacité:", err));
        }
    }

    function renderSuggestion(suggestion) {
        const list = $('suggestions-list');
        list.innerHTML = '';
        selectedRoutesIndexes.clear();
        MoovlyMap.clearRoutes();

        list.innerHTML = `<div class="section-hint" style="color:#10b981; font-weight:600; margin-bottom:10px;">✅ ${suggestion.methode} terminée !</div>`;

        // Checkbox "tout afficher"
        const toggleAllDiv = document.createElement('div');
        toggleAllDiv.style.cssText = 'display:flex; align-items:center; gap:8px; padding:8px 10px; background:#1e293b; border-radius:7px; margin-bottom:8px; border:1px solid #334155;';
        toggleAllDiv.innerHTML = `
            <input type="checkbox" id="chk-show-all-routes" style="width:15px; height:15px; cursor:pointer; accent-color:#6366f1;">
            <label for="chk-show-all-routes" style="cursor:pointer; font-size:0.85rem; font-weight:600; color:#f1f5f9; margin:0;">
                🗺️ Afficher tous les trajets sur la carte
            </label>`;
        list.appendChild(toggleAllDiv);

        const spreadBtn = document.createElement('button');
        spreadBtn.className = 'btn btn-outline btn-sm';
        spreadBtn.style.cssText = 'width:100%; margin-bottom:10px; font-size:0.8rem;';
        spreadBtn.innerHTML = '<i class="ph ph-arrows-out-simple"></i> Séparer / Regrouper les trajets';
        spreadBtn.addEventListener('click', () => MoovlyMap.toggleSpread());
        list.appendChild(spreadBtn);

        const chkAll = toggleAllDiv.querySelector('#chk-show-all-routes');
        chkAll.addEventListener('change', () => {
            const allCards = list.querySelectorAll('.result-card');
            const allCheckboxes = list.querySelectorAll('.route-checkbox');
            // Prevent triggering individual change events in a loop
            let updatedRoutes = [];

            allCheckboxes.forEach((chk, i) => {
                chk.checked = chkAll.checked;
                if (chkAll.checked) {
                    selectedRoutesIndexes.add(i);
                    if (allCards[i]) allCards[i].classList.add('selected');
                    updatedRoutes.push(suggestion.routes[i]);
                } else {
                    selectedRoutesIndexes.delete(i);
                    if (allCards[i]) allCards[i].classList.remove('selected');
                }
            });

            if (chkAll.checked) {
                window.taxiAnimators = [];
                window.isSimulationRunning = false;
                MoovlyMap.drawMultiRoutes(updatedRoutes, suggestion.destination);
                const bs = $('btn-simulate-taxis');
                if (bs) { bs.style.display = 'inline-flex'; bs.innerHTML = '<i class="ph ph-play-circle"></i> Simuler Taxis'; bs.classList.replace('btn-primary','btn-outline'); }
            } else {
                MoovlyMap.clearRoutes();
            }
        });

        suggestion.routes.forEach((r, idx) => {
            r.originalIdx = idx;
            const card = document.createElement('div');
            card.className = 'result-card route-card';
            card.innerHTML = `
                <div class="result-header">
                    <span class="result-badge badge-nn">${r.vehicule_id}</span>
                    ${r.vehicule ? `<span class="result-badge" style="background:#f1f5f9; color:#334155; margin-left:8px;">${r.vehicule.icon} ${r.vehicule.label}</span>` : ''}
                </div>
                <div class="result-metrics">
                    <div class="metric"><span class="metric-label">Distance</span><span class="metric-value">${fmt1(r.distance_km)}</span><span class="metric-unit">km</span></div>
                    <div class="metric"><span class="metric-label">Durée</span><span class="metric-value">${fmt1(r.duree_min)}</span><span class="metric-unit">min</span></div>
                </div>
                <div style="margin-top:10px; display:flex; justify-content:space-between; align-items:center;">
                    <button class="btn-link btn-details" style="font-size:0.8rem; padding:0;">➕ Plus de détails</button>
                    <div style="font-size:0.8rem; display:flex; align-items:center; gap:4px;">
                        <input type="checkbox" class="route-checkbox" id="route-chk-${idx}">
                        <label for="route-chk-${idx}" style="cursor:pointer; margin:0; color:#94a3b8;">Afficher sur la carte</label>
                    </div>
                </div>`;
            list.appendChild(card);

            // ── Focus route on card click ──
            const routeIdx = r.originalIdx !== undefined ? r.originalIdx : idx;
            card.title = 'Cliquer pour isoler ce véhicule sur la carte';

            card.addEventListener('click', (e) => {
                // Ne pas interférer avec les clics sur boutons internes
                if (e.target.closest('button') || e.target.closest('input') || e.target.closest('label')) return;

                if (MoovlyMap && typeof MoovlyMap.focusRoute === 'function') {
                    MoovlyMap.focusRoute(routeIdx);
                    const unfocusBtn = $('btn-unfocus-routes');
                    if (unfocusBtn) unfocusBtn.style.display = 'inline-flex';

                    // Highlight visuel de la card sélectionnée dans la sidebar
                    document.querySelectorAll('.route-card').forEach(c => c.classList.remove('focused'));
                    card.classList.add('focused');
                }
            });

            const chk = card.querySelector('.route-checkbox');
            chk.addEventListener('change', (e) => {
                if (e.target.checked) { selectedRoutesIndexes.add(idx); card.classList.add('selected'); }
                else { selectedRoutesIndexes.delete(idx); card.classList.remove('selected'); }
                window.taxiAnimators = [];
                window.isSimulationRunning = false;
                MoovlyMap.drawMultiRoutes(
                    Array.from(selectedRoutesIndexes).map(i => suggestion.routes[i]),
                    suggestion.destination);
                const bs2 = $('btn-simulate-taxis');
                if (bs2 && selectedRoutesIndexes.size > 0) { bs2.style.display = 'inline-flex'; bs2.innerHTML = '<i class="ph ph-play-circle"></i> Simuler Taxis'; bs2.classList.replace('btn-primary','btn-outline'); }
                else if (bs2) { bs2.style.display = 'none'; }
                // Sync chkAll
                const total = list.querySelectorAll('.route-checkbox').length;
                if (chkAll) {
                    chkAll.checked = selectedRoutesIndexes.size === total;
                    chkAll.indeterminate = selectedRoutesIndexes.size > 0 && selectedRoutesIndexes.size < total;
                }
            });

            card.addEventListener('click', (e) => {
                if (e.target.classList.contains('btn-details') ||
                    e.target.tagName.toLowerCase() === 'input' ||
                    e.target.tagName.toLowerCase() === 'label') return;
                chk.checked = !chk.checked;
                chk.dispatchEvent(new Event('change'));
            });

            card.querySelector('.btn-details').addEventListener('click', (e) => {
                e.stopPropagation();
                showRouteDetailsModal(r, suggestion.destination);
            });
        });
    }

    function showRouteDetailsModal(route, destination) {
    const rIdx = route.originalIdx;

    // ── Déterminer l'ordre d'affichage ─────────────────────────────
    // Si l'utilisateur a déjà modifié cette route sans encore sauvegarder,
    // on affiche l'ordre en attente plutôt que l'ordre original
    let displayOrder = route.ordre;
    if (window.pendingManualClusterIds && rIdx !== undefined) {
        const pendingIds = window.pendingManualClusterIds[rIdx];
        if (pendingIds && pendingIds.length > 0) {
            const empById = new Map(route.ordre.map(emp => [String(emp._id), emp]));
            const resolved = pendingIds.map(id => empById.get(id)).filter(Boolean);
            if (resolved.length === route.ordre.length) {
                displayOrder = resolved;
            }
        }
    }

    // ── Vérifier si cette route a des modifications en attente ──────
    const hasPendingChanges = (() => {
        if (!window.pendingManualClusterIds || !window.originalManualClusterIds || rIdx === undefined) return false;
        try {
            const orig = JSON.parse(window.originalManualClusterIds)[rIdx];
            const curr = window.pendingManualClusterIds[rIdx];
            return JSON.stringify(orig) !== JSON.stringify(curr);
        } catch { return false; }
    })();

    // ── Titre ───────────────────────────────────────────────────────
    $('route-modal-title').innerHTML = `
        <span class="result-badge" style="font-size:14px; padding:4px 12px;">
            ${route.vehicule_id}
        </span>
        ${route.vehicule ? `<span class="result-badge" style="background:#f1f5f9; color:#334155; margin-left:8px; font-size:14px; padding:4px 12px;">${route.vehicule.icon} ${route.vehicule.label}</span>` : ''}
        <span style="font-size:14px; font-weight:600; color:var(--accent); margin-left:12px;">
            Tarif estimé : ${fmt2(route.tarif?.final || 0)} TND
        </span>
        ${hasPendingChanges
            ? `<span style="font-size:11px; color:#a5b4fc; margin-left:8px;">
                   <i class="ph ph-pencil-simple"></i> Modifié — non sauvegardé
               </span>`
            : ''}
    `;

    // ── Liste ordre de ramassage ────────────────────────────────────
    let html = `<div style="margin-bottom:20px;">
        <div style="font-size:13px; font-weight:700; color:var(--text-muted);
                    text-transform:uppercase; margin-bottom:12px;">
            <i class="ph ph-list-numbers"></i> Ordre de ramassage
        </div>
        <div class="route-details-list" id="route-dnd-list">`;

    displayOrder.forEach((emp, i) => {
        html += `<div class="route-details-item" draggable="true"
                      data-emp-id="${emp._id}" data-idx="${i}"
                      style="cursor:grab;">
            <div style="font-weight:600; font-size:13px; pointer-events:none;">
                <i class="ph ph-dots-six-vertical"
                   style="color:var(--text-muted); margin-right:6px;"></i>
                <span class="emp-order-num">${i + 1}</span>.
                <span class="emp-name-text">${emp.nom}</span>
            </div>
            <div style="font-size:11px; color:var(--text-muted);
                        margin-top:2px; pointer-events:none;">
                <i class="ph ph-map-pin"></i>
                ${emp.residence || 'Localisation non précisée'}
            </div>
        </div>`;
    });

    html += `<div class="route-details-item route-details-dest" style="cursor:not-allowed;">
        <div style="font-weight:600; font-size:13px; color:var(--red);">
            <i class="ph ph-flag-checkered"></i> Destination
        </div>
        <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
            <i class="ph ph-map-pin"></i> ${destination.nom}
        </div>
    </div>
    </div></div>`;

    // ── Segments détaillés ──────────────────────────────────────────
    html += `<div>
        <div style="font-size:13px; font-weight:700; color:var(--text-muted);
                    text-transform:uppercase; margin-bottom:12px;">
            <i class="ph ph-map-trifold"></i> Segments Détaillés
        </div>`;

    if (hasPendingChanges) {
        // Ordre modifié → les distances actuelles ne correspondent plus
        html += `<div style="padding:10px 14px; background:rgba(99,102,241,0.08);
                              border:1px solid rgba(99,102,241,0.3);
                              border-radius:8px; font-size:12px; color:#a5b4fc;
                              margin-bottom:10px;">
            <i class="ph ph-info"></i>
            L'ordre a été modifié. Les distances seront recalculées après l'enregistrement.
        </div>`;
    }

    html += `<div style="background:rgba(255,255,255,0.02); border:1px solid var(--border);
                          border-radius:8px; overflow:hidden;">
        <table class="route-table">
        <thead><tr><th>De</th><th>Vers</th><th>Dist.</th><th>Temps</th></tr></thead>
        <tbody>`;

    route.segments.forEach(seg => {
        html += `<tr>
            <td>${seg.from}</td>
            <td>${seg.to}</td>
            <td style="font-weight:600;">${fmt2(seg.distance_km)} km</td>
            <td style="font-weight:600;">${fmt1(seg.duree_min)} min</td>
        </tr>`;
    });

    html += `</tbody></table></div></div>`;

    $('route-modal-body').innerHTML = html;
    $('modal-route-details').classList.remove('hidden');

    // ── Drag and Drop ───────────────────────────────────────────────
    const list = document.getElementById('route-dnd-list');
    let draggedItem = null;

    const getOrderFromDom = () =>
        [...list.querySelectorAll('.route-details-item[draggable="true"]')]
            .map(el => el.getAttribute('data-emp-id'));

    list.querySelectorAll('.route-details-item[draggable="true"]').forEach(item => {
        item.addEventListener('dragstart', function () {
            draggedItem = this;
            setTimeout(() => this.style.opacity = '0.5', 0);
        });

        item.addEventListener('dragend', function () {
            setTimeout(() => this.style.opacity = '1', 0);
            draggedItem = null;
        });

        item.addEventListener('dragover', function (e) {
            e.preventDefault();
            this.style.borderTop = '2px solid var(--primary)';
        });

        item.addEventListener('dragleave', function () {
            this.style.borderTop = '';
        });

        item.addEventListener('drop', function (e) {
            e.preventDefault();
            this.style.borderTop = '';
            if (!draggedItem || this === draggedItem) return;

            const allItems = [...list.querySelectorAll('.route-details-item[draggable="true"]')];
            const draggedIdx = allItems.indexOf(draggedItem);
            const targetIdx  = allItems.indexOf(this);

            if (draggedIdx < targetIdx) {
                this.after(draggedItem);
            } else {
                this.before(draggedItem);
            }

            // Renuméroter visuellement
            list.querySelectorAll('.route-details-item[draggable="true"]')
                .forEach((el, newIdx) => {
                    const span = el.querySelector('.emp-order-num');
                    if (span) span.innerText = newIdx + 1;
                });

            if (rIdx === undefined) return;

            const suggestion = optimizeResult.suggestions[window.currentAlgoIndex || 0];

            // Initialiser le snapshot global la PREMIÈRE fois qu'un changement
            // est fait (toutes routes confondues), en convertissant en String
            // pour éviter le mismatch number/string entre JSON et DOM
            if (!window.pendingManualClusterIds) {
                window.pendingManualClusterIds = suggestion.routes.map(
                    r => r.ordre.map(emp => String(emp._id))
                );
                window.originalManualClusterIds = JSON.stringify(
                    window.pendingManualClusterIds
                );
                window.pendingSuggestionRef = suggestion;
            }

            // Mettre à jour l'ordre de cette route dans le snapshot global
            window.pendingManualClusterIds[rIdx] = getOrderFromDom();

            checkAndShowBatchSaveButton();
        });
    });

    // ── Génération PDF ──────────────────────────────────────────────
    const btnPdf = $('route-modal-pdf-btn');
    if (btnPdf) {
        btnPdf.onclick = () => {
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF();
            doc.setFontSize(18);
            doc.setTextColor(40, 40, 40);
            doc.text("Feuille de Route Moovly", 105, 20, null, null, "center");
            doc.setFontSize(12);
            doc.setTextColor(100, 100, 100);
            doc.text(`Véhicule : ${route.vehicule_id}`, 14, 35);
            doc.text(`Destination : ${destination.nom}`, 14, 43);
            doc.text(`Distance Totale : ${fmt2(route.distance_km)} km`, 14, 51);
            doc.text(`Durée Estimée : ${fmt1(route.duree_min)} min`, 14, 59);
            doc.text(`Tarif Estimé : ${fmt2(route.tarif?.final || 0)} TND`, 14, 67);
            doc.setFontSize(14);
            doc.setTextColor(0, 0, 0);
            doc.text("Ordre de Ramassage", 14, 75);
            let yPos = 85;
            displayOrder.forEach((emp, i) => {
                doc.setFontSize(11);
                doc.text(
                    `${i + 1}. ${emp.nom} - ${emp.residence || 'Localisation non précisée'}`,
                    14, yPos
                );
                yPos += 8;
            });
            yPos += 10;
            doc.setFontSize(14);
            doc.text("Segments Détaillés", 14, yPos);
            doc.autoTable({
                startY: yPos + 5,
                head: [['De', 'Vers', 'Distance', 'Temps']],
                body: route.segments.map(seg => [
                    seg.from, seg.to,
                    `${fmt2(seg.distance_km)} km`,
                    `${fmt1(seg.duree_min)} min`
                ]),
                theme: 'grid',
                headStyles: { fillColor: [41, 128, 185] },
                styles: { fontSize: 10 }
            });
            doc.save(`Feuille_De_Route_${route.vehicule_id.replace(/\s+/g, '_')}.pdf`);
        };
    }
}

    /* ══════════ HEATMAP ══════════ */
    $('heatmap-toggle').addEventListener('change', (e) => {
        if (!optimizeResult || !optimizeResult.suggestions.length) return;
        const sug = optimizeResult.suggestions[window.currentAlgoIndex || 0];
        const routes = selectedRoutesIndexes.size > 0
            ? Array.from(selectedRoutesIndexes).map(i => sug.routes[i]) : sug.routes;
        MoovlyMap.toggleHeatmap(e.target.checked, routes);
    });

    /* ══════════════════════════════════════════════════════
       RSE DASHBOARD
    ══════════════════════════════════════════════════════ */
    function renderRSEDashboard(metrics, suggestion) {
        if (!metrics) return;

        // KPIs
        $('rse-co2-val').textContent = fmt2(metrics.co2_saved_kg) + ' kg';
        $('rse-cost-val').textContent = fmt2(metrics.cost_saved_tnd) + ' TND';
        $('rse-dist-val').textContent = fmt1(metrics.distance_saved_km) + ' km';
        $('rse-fill-val').textContent = fmt1(metrics.fill_rate_percent) + ' %';

        // Projections annuelles (252 jours)
        $('rse-annual-co2').textContent = (metrics.co2_saved_kg * 252).toFixed(1);
        $('rse-annual-cost').textContent = (metrics.cost_saved_tnd * 252).toFixed(1);
        $('rse-annual-trees').textContent = (metrics.co2_saved_kg * 252 / 21).toFixed(1);
        $('rse-annual-km').textContent = (metrics.distance_saved_km * 252).toFixed(1);

        const isLight = document.documentElement.getAttribute('data-theme') === 'light';
        const textColor = isLight ? '#475569' : '#e2e8f0';
        const gridColor = isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)';

        Chart.defaults.color = textColor;
        Chart.defaults.font.family = 'Inter';

        // 1. CO2 Chart (Bar Chart)
        if (co2ChartInst) co2ChartInst.destroy();
        co2ChartInst = new Chart($('co2Chart').getContext('2d'), {
            type: 'bar',
            data: {
                labels: ['Individuel', 'Moovly'],
                datasets: [{
                    data: [metrics.co2_scenario_perso, metrics.co2_scenario_moovly],
                    backgroundColor: ['rgba(239,68,68,0.7)', 'rgba(16,185,129,0.7)'],
                    borderRadius: 8
                }]
            },
            options: { plugins: { legend: { display: false } }, scales: { y: { grid: { color: gridColor } }, x: { grid: { display: false } } } }
        });

        // 2. Cost Chart (Donut Chart)
        const coutMoovly = Math.max(0, metrics.cost_scenario_perso - metrics.cost_saved_tnd);
        if (costChartInst) costChartInst.destroy();
        costChartInst = new Chart($('costChart').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Coût Moovly', 'Économie'],
                datasets: [{
                    data: [coutMoovly, metrics.cost_saved_tnd],
                    backgroundColor: ['rgba(99,102,241,0.8)', 'rgba(16,185,129,0.8)'],
                    borderWidth: 0
                }]
            },
            options: { cutout: '70%', plugins: { legend: { position: 'bottom' } } }
        });

        // 3. Fleet Chart (Line Chart)
        if (fleetChartInst) fleetChartInst.destroy();
        const routes = suggestion ? suggestion.routes : [];
        fleetChartInst = new Chart($('fleetChart').getContext('2d'), {
            type: 'line',
            data: {
                labels: routes.map((r, i) => 'Taxi ' + (i + 1)),
                datasets: [{
                    label: 'Passagers par véhicule',
                    data: routes.map(r => r.ordre.length),
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99,102,241,0.2)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#8b5cf6',
                    pointRadius: 6
                }]
            },
            options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: gridColor }, ticks: { stepSize: 1 } }, x: { grid: { display: false } } } }
        });

        updateROI(metrics);
    }

    /* ══════════════════════════════════════════════════════
       COMPARATEUR DE SCÉNARIOS
    ══════════════════════════════════════════════════════ */
    const DEFAULT_CAPS = [2, 3, 4];
    let activeCaps = new Set([2, 3, 4]);

    function buildComparatorPanel() {
        const grp = $('cap-toggle-group');
        if (!grp) return;
        grp.innerHTML = '';
        DEFAULT_CAPS.forEach(cap => {
            const btn = document.createElement('button');
            btn.className = 'cap-toggle-btn' + (activeCaps.has(cap) ? ' active' : '');
            btn.textContent = cap + ' places';
            btn.dataset.cap = cap;
            btn.addEventListener('click', () => {
                if (activeCaps.has(cap)) { if (activeCaps.size > 1) { activeCaps.delete(cap); btn.classList.remove('active'); } }
                else { activeCaps.add(cap); btn.classList.add('active'); }
            });
            grp.appendChild(btn);
        });
    }

    $('btn-run-compare').addEventListener('click', async () => {
        if (!optimizeResult) { showToast('Lancez d\'abord une optimisation', 'warning'); return; }

        $('compare-empty').classList.add('hidden');
        $('compare-loading').classList.remove('hidden');
        $('compare-results').classList.add('hidden');

        try {
            // Fallback : envoyer les données directement si le store serveur est vide
            const currentSuggestion = optimizeResult.suggestions[window.currentAlgoIndex || 0];
            const allEmps = currentSuggestion.routes.flatMap(r => r.ordre);

            const res = await fetch('/api/compare_scenarios', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    selected_employes_ids: [...selectedEmpIds],
                    destination_id: selectedDestId,
                    capacites: [...activeCaps].sort((a, b) => a - b),
                    employes_data: allEmps,
                    destination_data: currentSuggestion.destination,
                    poids: getPoidsNormalises()
                })
            });

            // Lire le texte brut d'abord pour éviter un crash JSON si Flask retourne du HTML
            const text = await res.text();
            let json;
            try { json = JSON.parse(text); }
            catch (_) {
                const match = text.match(/<pre[^>]*>([^<]{0,300})/);
                throw new Error('Erreur Python: ' + (match ? match[1].trim() : text.substring(0, 150)));
            }

            if (json.status !== 'success') throw new Error(json.message);
            renderComparatorResults(json.scenarios, json.nb_employes);
        } catch (err) {
            showToast('Erreur: ' + err.message.split('\n')[0], 'error');
            console.error(err);
        } finally {
            $('compare-loading').classList.add('hidden');
        }
    });

    function renderComparatorResults(scenarios, nbEmp) {
        $('compare-results').classList.remove('hidden');

        const labels = scenarios.map(s => s.capacite + ' places');
        const COLORS = ['#6366f1', '#10b981', '#f97316', '#ec4899', '#14b8a6'];
        const barOpts = (unit) => ({
            responsive: true,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.y} ${unit}` } } },
            scales: {
                x: { ticks: { color: '#64748b', font: { size: 11 } }, grid: { color: 'rgba(255,255,255,.04)' } },
                y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,.06)' } }
            }
        });

        const mkBar = (canvasId, data, unit, colors) => {
            const inst = Chart.getChart(canvasId);
            if (inst) inst.destroy();
            return new Chart($(canvasId).getContext('2d'), {
                type: 'bar',
                data: { labels, datasets: [{ data, backgroundColor: colors || COLORS, borderRadius: 6, borderWidth: 0 }] },
                options: barOpts(unit)
            });
        };

        const bestCostIdx = scenarios.reduce((bi, s, i) => s.tarif_tnd < scenarios[bi].tarif_tnd ? i : bi, 0);

        // 1. Bubble chart for Vehicles
        const vehInst = Chart.getChart('compareVehChart');
        if (vehInst) vehInst.destroy();
        cmpVehInst = new Chart($('compareVehChart').getContext('2d'), {
            type: 'bubble',
            data: {
                datasets: [{
                    label: 'Véhicules nécessaires',
                    data: scenarios.map(s => ({ x: s.capacite, y: s.nb_vehicules, r: s.capacite * 4 })),
                    backgroundColor: 'rgba(99,102,241,0.6)',
                    borderColor: '#6366f1'
                }]
            },
            options: { plugins: { legend: { display: false } }, scales: { x: { title: { display: true, text: 'Capacité' } }, y: { title: { display: true, text: 'Véhicules' }, beginAtZero: true } } }
        });

        // 2. Bar chart for Distance
        cmpDistInst = mkBar('compareDistChart', scenarios.map(s => s.distance_km), 'km');

        // 3. Bar chart for Cost
        cmpCostInst = mkBar('compareCostChart', scenarios.map(s => s.tarif_tnd), 'TND',
            scenarios.map((s, i) => i === bestCostIdx ? 'rgba(16,185,129,.8)' : 'rgba(99,102,241,.6)'));

        // 4. Pie chart for CO2
        const co2Inst = Chart.getChart('compareCo2Chart');
        if (co2Inst) co2Inst.destroy();
        cmpCo2Inst = new Chart($('compareCo2Chart').getContext('2d'), {
            type: 'pie',
            data: {
                labels,
                datasets: [{
                    data: scenarios.map(s => s.co2_kg),
                    backgroundColor: COLORS,
                    borderWidth: 0
                }]
            },
            options: { plugins: { legend: { position: 'right' } } }
        });

        // Tableau
        const bestS = scenarios[bestCostIdx];
        let tableHtml = `<table class="compare-table">
            <thead><tr>
                <th>Capacité</th><th>Véhicules</th><th>Distance (km)</th>
                <th>Durée (min)</th><th>Coût (TND)</th><th>CO₂ (kg)</th>
                <th>Remplissage</th><th>Économie (TND)</th>
            </tr></thead><tbody>`;
        scenarios.forEach((s, i) => {
            const best = i === bestCostIdx;
            tableHtml += `<tr class="${best ? 'best-row' : ''}">
                <td>${best ? '⭐ ' : ''}${s.capacite} places</td>
                <td>${s.nb_vehicules}</td>
                <td>${fmt1(s.distance_km)}</td>
                <td>${fmt1(s.duree_min)}</td>
                <td><strong>${fmt2(s.tarif_tnd)} TND</strong></td>
                <td>${fmt2(s.co2_kg)}</td>
                <td>${fmt1(s.fill_rate_percent)} %</td>
                <td>${fmt2(s.cost_saved_tnd)} TND</td>
            </tr>`;
        });
        tableHtml += '</tbody></table>';
        $('compare-table').innerHTML = tableHtml;

        // Recommandation
        const savings = fmt2(scenarios[0].tarif_tnd - bestS.tarif_tnd);
        $('compare-recommendation').innerHTML = `
            <div class="recommendation-box">
                <strong>💡 Recommandation</strong><br>
                Avec <strong>${bestS.capacite} places par véhicule</strong>, vous utilisez
                <strong>${bestS.nb_vehicules} véhicule(s)</strong> pour ${nbEmp} employés.<br>
                Coût optimal : <strong>${bestS.tarif_tnd} TND</strong> :
                soit <strong>${savings >= 0 ? savings.toFixed(2) : 0} TND d'économie</strong> par rapport à la capacité minimale testée.<br>
                Taux de remplissage : <strong>${bestS.fill_rate_percent}%</strong> •
                CO₂ émis : <strong>${bestS.co2_kg} kg</strong> (économie de <strong>${bestS.co2_saved_kg} kg</strong>).
            </div>`;
    }

    /* ══════════ EXPORT EXCEL ══════════ */
    $('btn-export').addEventListener('click', async () => {
        if (!optimizeResult) { showToast('Aucun résultat à exporter', 'warning'); return; }
        showLoading('Génération du rapport Excel…');
        try {
            const selIdx = window.currentAlgoIndex || 0;
            const res = await fetch('/api/export_excel', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ result: optimizeResult.suggestions[selIdx] })
            });
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = 'moovly_rapport.xlsx'; a.click();
            showToast('Rapport Excel généré !', 'success');
        } catch (err) { showToast('Erreur export: ' + err.message, 'error'); }
        hideLoading();
    });

    /* ══════════════════════════════════════════════════════
       ÉDITION MANUELLE DES CLUSTERS
    ══════════════════════════════════════════════════════ */
        window.handleEmployeeClick = function (emp, currentRoute) {
        if (!optimizeResult || !optimizeResult.suggestions || optimizeResult.suggestions.length === 0) return;
        MoovlyMap.drawEditHeatmap(emp);
        const suggestion = optimizeResult.suggestions[window.currentAlgoIndex || 0];
        let optionsHTML = '<option value="">-- Choisir un véhicule --</option>';
        suggestion.routes.forEach((r, idx) => {
            if (r.vehicule_id !== currentRoute.vehicule_id)
                optionsHTML += `<option value="${idx}">${r.vehicule_id} (${r.ordre.length} passager${r.ordre.length > 1 ? 's' : ''})</option>`;
        });
        L.popup({ maxWidth: 280, closeButton: true, className: 'glass-popup' })
            .setLatLng([emp.lat, emp.lng])
            .setContent(`<div style="min-width:230px;">
                <h4 style="margin:0 0 10px 0; font-size:14px; color:var(--text-primary); border-bottom:1px solid var(--border); padding-bottom:6px;">🔄 Déplacer <em>${emp.nom}</em></h4>
                
                <button onclick="window.startRelocalisation('employes', '${emp._id}', '${emp.nom}')" class="btn btn-outline btn-sm w-100 mb-3" style="font-size:12px;">
                    <i class="ph ph-map-pin"></i> Changer de localisation (GPS)
                </button>
                
                <p style="font-size:11px; margin:0 0 8px 0; color:var(--text-muted);">
                    Transférer de <strong>${currentRoute.vehicule_id}</strong> vers :</p>
                <select id="transfer-select" class="form-select mb-2" style="padding:6px; font-size:12px;">${optionsHTML}</select>
                <button id="btn-confirm-transfer" class="btn btn-primary btn-sm w-100 mt-2" style="font-size:12px;">✅ Valider le transfert</button>
                
                <button onclick="window.forcerTaxiIndividuel('${emp._id}')" class="btn btn-sm w-100 mt-2" style="font-size:12px; background: rgba(99, 102, 241, 0.15); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4);">
                    Taxi individuel
                </button>
            </div>`)
            .openOn(MoovlyMap.getMap());
        setTimeout(() => {
            const btn = document.getElementById('btn-confirm-transfer');
            if (!btn) return;
            btn.addEventListener('click', () => {
                const targetIdxStr = document.getElementById('transfer-select').value;
                if (targetIdxStr === '') { showToast('Sélectionnez un véhicule', 'warning'); return; }
                MoovlyMap.getMap().closePopup();
                executeManualTransfer(emp, currentRoute, parseInt(targetIdxStr), suggestion);
            });
        }, 100);
        MoovlyMap.getMap().once('popupclose', () => MoovlyMap.clearEditHeatmap());
    };

    window.pendingManualClusterIds = null;
    window.originalManualClusterIds = null;
    window.pendingSuggestionRef = null;

    function executeManualTransfer(emp, currentRoute, targetRouteIdx, suggestion) {
        if (!window.pendingManualClusterIds) {
            window.pendingManualClusterIds = [];
            suggestion.routes.forEach(r => window.pendingManualClusterIds.push(r.ordre.map(e => e._id)));
            window.originalManualClusterIds = JSON.stringify(window.pendingManualClusterIds);
            window.pendingSuggestionRef = suggestion;
        }
        
        // Remove emp from its current cluster
        window.pendingManualClusterIds.forEach(cluster => {
            const idx = cluster.indexOf(emp._id);
            if (idx > -1) cluster.splice(idx, 1);
        });
        
        // Add emp to target cluster
        window.pendingManualClusterIds[targetRouteIdx].push(emp._id);
        
        checkAndShowBatchSaveButton();
        if (document.getElementById('btn-batch-save')) {
            showToast(`<i class="ph ph-arrows-left-right"></i> ${emp.nom} déplacé. Cliquez sur "Enregistrer les modifications" pour appliquer.`, 'info');
        }
    }

    function checkAndShowBatchSaveButton() {
    const currentStr  = JSON.stringify(window.pendingManualClusterIds);
    const originalStr = window.originalManualClusterIds;
    let btn = document.getElementById('btn-batch-save');

    // Aucun changement par rapport à l'état initial → supprimer le bouton
    if (currentStr === originalStr) {
        if (btn) btn.remove();
        // Réinitialiser complètement pour que la prochaine drag session
        // repart d'un état propre
        window.pendingManualClusterIds  = null;
        window.originalManualClusterIds = null;
        window.pendingSuggestionRef     = null;
        return;
    }

        // Des changements existent → créer le bouton si absent ou le réafficher s'il était caché
        if (!btn) {
            btn = document.createElement('button');
            btn.id = 'btn-batch-save';
            btn.className = 'btn btn-primary';
            btn.innerHTML = '<i class="ph ph-floppy-disk"></i> Enregistrer les modifications';
            btn.style.cssText = `
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 9999;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                font-size: 16px;
                padding: 12px 24px;
                border-radius: 30px;
                animation: popIn 0.3s ease-out;
                margin-bottom: 50px;
            `;
            document.body.appendChild(btn);

            if (!document.getElementById('batch-save-anim')) {
                const style = document.createElement('style');
                style.id = 'batch-save-anim';
                style.innerHTML = `
                    @keyframes popIn {
                        0%   { opacity: 0; transform: translate(-50%, 20px); }
                        100% { opacity: 1; transform: translate(-50%, 0);    }
                    }
                `;
                document.head.appendChild(style);
            }

            btn.addEventListener('click', async () => {
            if (!window.pendingManualClusterIds) return;

            btn.style.display = 'none';

            const manual_cluster_ids = window.pendingManualClusterIds.filter(
                c => c.length > 0
            );

            showLoading('Enregistrement et recalcul des routes…', true);
            window.currentAbortController = new AbortController();

            try {
                const res = await fetch('/api/optimize_manual', {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json' },
                    signal:  window.currentAbortController.signal,
                    body:    JSON.stringify({
                        manual_cluster_ids,
                        destination_id: selectedDestId,
                        capacite: parseInt(document.getElementById('taxi-capacity').value) || 3
                    })
                });
                const json = await res.json();
                if (json.status !== 'success') throw new Error(json.message);

                optimizeResult          = json;
                window.currentAlgoIndex = 0;
                displayResults(json);

                showToast(
                    '<i class="ph ph-check-circle"></i> Modifications enregistrées.',
                    'success'
                );

                // Réinitialiser complètement
                window.pendingManualClusterIds  = null;
                window.originalManualClusterIds = null;
                window.pendingSuggestionRef     = null;
                btn.remove();

            } catch (err) {
                if (err.name === 'AbortError') {
                    // Annulé par l'utilisateur via btn-cancel-loading
                    btn.style.display = 'block';
                } else {
                    showToast('Erreur transfert: ' + err.message, 'error');
                    btn.style.display = 'block';
                }
            } finally {
                hideLoading();
                window.currentAbortController = null;
            }
        });
        
    }
    else {
            btn.style.display = 'block'; // Forcer l'affichage si le bouton existait déjà
        }
}

    /* ══════════ CLIC POLYLINE ══════════ */
    window.handleRouteLineClick = function (route) {
        if (!optimizeResult || !optimizeResult.suggestions) return;
        const destination = optimizeResult.suggestions[window.currentAlgoIndex || 0].destination;
        showRouteDetailsModal(route, destination);
    };

    /* ══════════ ROI ANNUEL ══════════ */
    function updateROI(metrics) {
        if (!metrics) return;
        const section = $('roi-section');
        if (section) section.style.display = 'block';

        const freq  = parseInt($('roi-freq')?.value  ?? 5)  || 5;
        const weeks = parseInt($('roi-weeks')?.value ?? 47) || 1;
        const annuel  = freq * weeks;
        const mensuel = freq * weeks / 12;

        const costPerTrip = metrics.cost_saved_tnd || 0;
        const co2PerTrip  = metrics.co2_saved_kg   || 0;

        // Mise à jour directe (sans animation qui se chevauche)
        const setVal = (id, val, decimals) => {
            const el = $(id);
            if (!el) return;
            el.textContent = val.toFixed(decimals);
            el.classList.remove('roi-updated');
            void el.offsetWidth; // force reflow pour relancer l'animation CSS
            el.classList.add('roi-updated');
        };

        setVal('roi-val-trajet', costPerTrip,           2);
        setVal('roi-val-mois',   costPerTrip * mensuel, 1);
        setVal('roi-val-an',     costPerTrip * annuel,  0);

        $('roi-co2-trajet').textContent = fmt2(co2PerTrip)             + ' kg CO₂';
        $('roi-co2-mois').textContent   = fmt2(co2PerTrip * mensuel)   + ' kg CO₂';
        $('roi-co2-an').textContent     = fmt2(co2PerTrip * annuel)    + ' kg CO₂';

        // Phrase d'impact
        const annualCost = costPerTrip * annuel;
        const annualCo2  = co2PerTrip  * annuel;
        const phraseEl   = $('roi-phrase');
        const phraseText = $('roi-phrase-text');
        if (phraseEl && phraseText && annualCost > 0) {
            phraseEl.style.display = 'flex';
            phraseText.textContent =
                `En ${weeks} semaines à ${freq} trajet${freq>1?'s':''}/semaine, Moovly économise ` +
                `${annualCost.toFixed(0)} TND à votre entreprise et évite ` +
                `${annualCo2.toFixed(1)} kg de CO₂ : soit l'équivalent de ` +
                `${(annualCo2 / 21).toFixed(0)} arbres plantés.`;
        }
    }

    // Listeners ROI inputs
    ['roi-freq', 'roi-weeks'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', () => {
            if (optimizeResult) {
                const sug = optimizeResult.suggestions[window.currentAlgoIndex || 0];
                if (sug?.rse_metrics) updateROI(sug.rse_metrics);
            }
        });
    });

    /* ══════════ DASHBOARD TABS ══════════ */
    function initDashTabs() {
        document.querySelectorAll('.dash-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const target = tab.dataset.tab;
                document.querySelectorAll('.dash-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
                tab.classList.add('active');
                const el = $('tab-' + target);
                if (el) el.style.display = 'block';
                if (target === 'historique') loadHistorique();
            });
        });
    }

    /* ══════════ HISTORIQUE ══════════ */
    let histChartInst = null;

    async function loadHistorique() {
        try {
            const resp = await fetch('/api/get_historique');
            const json = await resp.json();
            const hist = (json.historique || []).slice().reverse(); // Plus récent en premier

            const listEl = $('hist-list');
            const emptyEl = $('hist-empty');
            const chartWrap = $('hist-chart-wrap');

            if (hist.length === 0) {
                listEl.innerHTML = '';
                emptyEl.style.display = 'block';
                chartWrap.style.display = 'none';
                return;
            }

            emptyEl.style.display = 'none';
            chartWrap.style.display = 'block';

            // ── Graphique d'évolution CO₂ sauvegardé ──
            if (histChartInst) histChartInst.destroy();
            const isLight = document.documentElement.getAttribute('data-theme') === 'light';
            const last10 = [...hist].reverse().slice(-10);
            histChartInst = new Chart($('histChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: last10.map(s => new Date(s.date).toLocaleDateString('fr-FR', { day:'2-digit', month:'short' })),
                    datasets: [
                        {
                            label: 'CO₂ sauvegardé (kg)',
                            data: last10.map(s => fmt2(s.co2_saved_kg)),
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16,185,129,0.15)',
                            fill: true, tension: 0.4, pointRadius: 4
                        },
                        {
                            label: 'Économie (TND)',
                            data: last10.map(s => fmt2(s.cost_saved_tnd)),
                            borderColor: '#6366f1',
                            backgroundColor: 'rgba(99,102,241,0.1)',
                            fill: true, tension: 0.4, pointRadius: 4
                        }
                    ]
                },
                options: {
                    plugins: { legend: { position: 'bottom', labels: { font: { family: 'Inter', size: 11 } } } },
                    scales: {
                        y: { beginAtZero: true, grid: { color: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)' } },
                        x: { grid: { display: false } }
                    }
                }
            });

            // ── Liste des cards ──
            listEl.innerHTML = hist.map(s => {
                const d = new Date(s.date);
                const dateStr = d.toLocaleDateString('fr-FR', { day:'2-digit', month:'short', year:'numeric' });
                const timeStr = d.toLocaleTimeString('fr-FR', { hour:'2-digit', minute:'2-digit' });
                return `
                <div class="hist-card">
                    <div class="hist-date">
                        <strong>${dateStr}</strong><br>${timeStr}
                    </div>
                    <div class="hist-kpis">
                        <span class="hist-kpi"><strong>${s.nb_employes}</strong> emp.</span>
                        <span class="hist-kpi"><strong>${s.nb_vehicules}</strong> véhic.</span>
                        <span class="hist-kpi"><strong>${fmt1(s.distance_km)}</strong> km</span>
                        <span class="hist-kpi"><strong>${fmt2(s.tarif_tnd)}</strong> TND</span>
                        <span class="hist-kpi" style="color:#10b981"><strong>-${fmt2(s.co2_saved_kg)}</strong> kg CO₂</span>
                        <span class="hist-kpi" style="color:#6366f1"><strong>+${fmt2(s.cost_saved_tnd)}</strong> TND économ.</span>
                    </div>
                    <span class="hist-badge">${s.capacite} places</span>
                </div>`;
            }).join('');

        } catch (e) {
            console.error('Erreur chargement historique:', e);
        }
    }

    // Vider l'historique
    const btnClearHist = $('btn-clear-historique');
    if (btnClearHist) btnClearHist.addEventListener('click', async () => {
        if (!confirm('Supprimer tout l\'historique ?')) return;
        await fetch('/api/save_historique', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ _clear: true })
        }).catch(() => {});
        $('hist-list').innerHTML = '';
        $('hist-empty').style.display = 'block';
        $('hist-chart-wrap').style.display = 'none';
        if (histChartInst) { histChartInst.destroy(); histChartInst = null; }
    });

    /* ══════════ VUE GLOBALE (unfocus) ══════════ */
    const btnUnfocus = $('btn-unfocus-routes');
    if (btnUnfocus) btnUnfocus.addEventListener('click', () => {
        MoovlyMap.unfocusAll();
        btnUnfocus.style.display = 'none';
        document.querySelectorAll('.route-card').forEach(c => c.classList.remove('focused'));
    });

    /* ══════════ SIMULATION TAXIS ══════════ */
    const btnSimulate = $('btn-simulate-taxis');
    if (btnSimulate) btnSimulate.addEventListener('click', () => {
        window.isSimulationRunning = !window.isSimulationRunning;
        if (window.isSimulationRunning) {
            btnSimulate.innerHTML = '<i class="ph ph-stop-circle"></i> Arrêter Simulation';
            btnSimulate.classList.replace('btn-outline', 'btn-primary');
            if (window.taxiAnimators) window.taxiAnimators.forEach(a => a.start());
        } else {
            btnSimulate.innerHTML = '<i class="ph ph-play-circle"></i> Simuler Taxis';
            btnSimulate.classList.replace('btn-primary', 'btn-outline');
            if (window.taxiAnimators) window.taxiAnimators.forEach(a => a.stop());
        }
    });

    // Init tabs
    initDashTabs();

/* ══════════ NAVIGATION PARAMS ══════════ */
if ($('nav-btn-params')) {
    $('nav-btn-params').addEventListener('click', () => {
        switchMainView('view-params');
        loadParams();
    });
}

/* ══════════ PARAMÈTRES ══════════ */
async function loadParams() {
    try {
        const res  = await fetch('/api/get_params');
        const json = await res.json();
        if (json.status !== 'success') return;
        const t = json.tarifs;
        const r = json.params_rse;
        const a = json.params_algo;
        if($('p-pc')) $('p-pc').value       = t.prise_en_charge;
        if($('p-p79')) $('p-p79').value      = t.prix_79m;
        if($('p-p18')) $('p-p18').value      = t.prix_18s;
        if($('p-chp')) $('p-chp').value      = t.coef_hp;
        if($('p-cwe')) $('p-cwe').value      = t.coef_weekend;
        if($('p-mode')) $('p-mode').value     = t.mode_actif;
        if($('p-co2')) $('p-co2').value      = r.co2_kg_per_km;
        if($('p-ind')) $('p-ind').value      = r.cout_individuel_per_km;
        if($('p-cdist')) $('p-cdist').value    = a.max_cluster_distance_km;
        if($('p-ortlimit')) $('p-ortlimit').value = a.ortools_time_limit_s;
        if($('p-lambda')) $('p-lambda').value   = a.direction_lambda;
        simulateTarif();
        syncVehicleGrid(r.fleet_composition);
    } catch(e) { console.warn('loadParams:', e); }
}

function simulateTarif() {
    const pc  = parseFloat($('p-pc')?.value)  || 0.9;
    const p79 = parseFloat($('p-p79')?.value) || 0.046;
    const p18 = parseFloat($('p-p18')?.value) || 0.046;
    const chp = parseFloat($('p-chp')?.value) || 1.2;
    const cwe = parseFloat($('p-cwe')?.value) || 1.15;
    const mode= $('p-mode')?.value || 'standard';
    const dist= parseFloat($('sim-dist')?.value) || 10;
    const dur = parseFloat($('sim-dur')?.value)  || 15;
    const dM = dist * 1000, dS = dur * 60, arr = dS * 0.08;
    const cD = (dM / 79) * p79;
    const cT = (arr / 18) * p18;
    const base = pc + cD + cT;
    let coef = 1.0;
    if (mode === 'hp')   coef = chp;
    if (mode === 'we')   coef = cwe;
    if (mode === 'hpwe') coef = chp * cwe;
    const total = base * coef;
    if ($('sim-result-total')) {
        $('sim-result-total').textContent = total.toFixed(3);
        $('sim-result-breakdown').textContent =
            `base ${pc.toFixed(3)} + km ${cD.toFixed(3)} + tps ${cT.toFixed(3)}` +
            (coef > 1 ? ` × ${coef.toFixed(2)}` : '');
    }
}

function syncVehicleGrid(fleet) {
    if (!fleet || !Array.isArray(fleet)) {
        // Fallback default
        $('vehicle-grid').querySelectorAll('.params-vehicle').forEach(v => {
            const input = v.querySelector('.v-input');
            if (input) input.value = (v.dataset.id === 'berline') ? 5 : 0;
        });
        return;
    }
    $('vehicle-grid').querySelectorAll('.params-vehicle').forEach(v => {
        const id = v.dataset.id;
        const match = fleet.find(f => f.id === id);
        const input = v.querySelector('.v-input');
        if (input) input.value = match ? match.count : 0;
    });
}

// Presets tarif
document.querySelectorAll('.params-preset').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.params-preset').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const preset = btn.dataset.preset;
        if ($('p-mode')) $('p-mode').value = preset;
        simulateTarif();
    });
});

// Empêche la propagation du clic sur l'input pour ne pas interférer
document.querySelectorAll('.params-vehicle .v-input').forEach(input => {
    input.addEventListener('input', () => {
        if (parseInt(input.value) < 0) input.value = 0;
    });
});

// Simulateur live
['p-pc','p-p79','p-p18','p-chp','p-cwe','p-mode', 'sim-dist', 'sim-dur'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', simulateTarif);
});

// Bouton Réinitialiser
$('btn-params-reset')?.addEventListener('click', async () => {
    await fetch('/api/update_params', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            tarifs:      { prise_en_charge:0.9, prix_79m:0.046, prix_18s:0.046, coef_hp:1.2, coef_weekend:1.15, mode_actif:'standard' },
            params_rse:  { co2_kg_per_km:0.12, cout_individuel_per_km:0.582 },
            params_algo: { max_cluster_distance_km:5.0, ortools_time_limit_s:3, direction_lambda:2.0 }
        })
    });
    await loadParams();
    showToast('Paramètres réinitialisés aux valeurs officielles.', 'info');
});

// Bouton Appliquer
$('btn-params-apply')?.addEventListener('click', async () => {
    try {
        const body = {
            tarifs: {
                prise_en_charge: parseFloat($('p-pc').value),
                prix_79m:        parseFloat($('p-p79').value),
                prix_18s:        parseFloat($('p-p18').value),
                coef_hp:         parseFloat($('p-chp').value),
                coef_weekend:    parseFloat($('p-cwe').value),
                mode_actif:      $('p-mode').value,
            },
            params_rse: {
                co2_kg_per_km:         parseFloat($('p-co2').value || 0.12),
                cout_individuel_per_km: parseFloat($('p-ind').value),
                fleet_composition:     Array.from(document.querySelectorAll('.params-vehicle')).map(v => ({
                    id: v.dataset.id,
                    label: v.dataset.label,
                    icon: v.dataset.icon,
                    co2: parseFloat(v.dataset.co2),
                    count: parseInt(v.querySelector('.v-input').value) || 0
                }))
            },
            params_algo: {
                max_cluster_distance_km: parseFloat($('p-cdist').value),
                ortools_time_limit_s:    parseInt($('p-ortlimit').value),
                direction_lambda:        parseFloat($('p-lambda').value),
            }
        };
        const res  = await fetch('/api/update_params', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const json = await res.json();
        if (json.status !== 'success') throw new Error(json.message);
        showToast('Paramètres appliqués. Relancez une optimisation pour voir l\'effet.', 'success');
        if ($('params-hint')) {
            $('params-hint').textContent = 'Appliqués le ' + new Date().toLocaleTimeString('fr-FR');
            $('params-hint').style.color = 'var(--text-success, #10b981)';
        }
    } catch(err) {
        showToast('Erreur: ' + err.message, 'error');
    }
});
});