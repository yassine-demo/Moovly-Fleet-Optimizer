import os

HTML_CONTENT = """<!DOCTYPE html>
<html lang="fr" data-theme="dark">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Moovly — Optimisation de Flotte SaaS</title>
    <script src="https://unpkg.com/@phosphor-icons/web"></script>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.css" />
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="icon" type="image/x-icon" href="/static/favicon.ico?v=1">
</head>

<body>
    <div id="app-container">
        <!-- GLOBAL SIDEBAR -->
        <nav class="main-nav">
            <div class="nav-brand">
                <img src="/static/Logo.png" class="nav-logo-img" alt="Moovly">
            </div>
            <div class="nav-links">
                <button class="nav-item active" id="nav-btn-planning" title="Planning & Map">
                    <i class="ph ph-map-trifold"></i>
                </button>
                <button class="nav-item" id="nav-btn-dashboard" title="Dashboard RSE">
                    <i class="ph ph-chart-pie-slice"></i>
                </button>
            </div>
            <div class="nav-bottom">
                <button class="nav-item" id="theme-toggle" title="Thème">
                    <i class="ph ph-moon"></i>
                </button>
            </div>
        </nav>

        <!-- MAIN CONTENT -->
        <main id="main-content">
            
            <!-- ================= VIEW: PLANNING ================= -->
            <div id="view-planning" class="view active">
                <aside class="sub-sidebar">
                    <nav class="stepper-nav">
                        <div class="step active" id="step-1"><span class="step-num">1</span><span class="step-label">Importer</span></div>
                        <div class="step-line"></div>
                        <div class="step" id="step-2"><span class="step-num">2</span><span class="step-label">Configurer</span></div>
                        <div class="step-line"></div>
                        <div class="step" id="step-3"><span class="step-num">3</span><span class="step-label">Résultats</span></div>
                    </nav>

                    <div class="panel-container">
                        <!-- PANEL 1 -->
                        <div class="panel active" id="panel-1">
                            <div class="panel-section">
                                <div class="section-title"><i class="ph ph-users"></i> Employés</div>
                                <div class="upload-wrapper">
                                    <label class="upload-card" id="upload-employes">
                                        <span class="upload-icon"><i class="ph ph-file-xls"></i></span>
                                        <span class="upload-info">
                                            <span class="upload-label">Employés (.xlsx)</span>
                                        </span>
                                        <span class="upload-status"><span class="upload-badge" id="badge-employes">—</span></span>
                                        <input type="file" class="upload-input" accept=".xlsx,.xls" data-type="employes">
                                    </label>
                                    <button class="btn-pin-manual" data-type="employes"><i class="ph ph-map-pin-plus"></i> Placer manuellement</button>
                                </div>
                            </div>
                            <div class="panel-section">
                                <div class="section-title"><i class="ph ph-map-pin"></i> Destinations</div>
                                <button class="btn btn-outline btn-sm" id="btn-load-destinations"><i class="ph ph-download-simple"></i> Charger destinations</button>
                                <button class="btn-pin-manual mt-2" data-type="destinations" style="width:100%;"><i class="ph ph-map-pin-plus"></i> Placer manuellement</button>
                            </div>
                            <button class="btn btn-primary mt-auto" id="btn-go-step2" disabled>Continuer <i class="ph ph-arrow-right"></i></button>
                        </div>

                        <!-- PANEL 2 -->
                        <div class="panel" id="panel-2">
                            <div class="panel-section">
                                <div class="section-title">Employés à inclure</div>
                                <div class="select-actions">
                                    <button class="btn-link" id="select-all-emp">Tout</button>
                                    <button class="btn-link" id="deselect-all-emp">Aucun</button>
                                </div>
                                <div class="emp-list" id="emp-list"></div>
                            </div>
                            <div class="panel-section">
                                <div class="section-title">Destination</div>
                                <select class="form-select" id="dest-select"><option value="">— Choisir —</option></select>
                            </div>
                            <div class="panel-section">
                                <div class="section-title">Capacité Taxi</div>
                                <input type="number" class="form-select" id="taxi-capacity" value="3" min="1" max="10">
                            </div>
                            <div class="btn-row mt-auto">
                                <button class="btn btn-outline btn-sm" id="btn-back-step1"><i class="ph ph-arrow-left"></i> Retour</button>
                                <button class="btn btn-primary btn-sm" id="btn-run" disabled><i class="ph ph-rocket-launch"></i> Lancer</button>
                            </div>
                        </div>

                        <!-- PANEL 3 -->
                        <div class="panel" id="panel-3">
                            <div class="section-title"><i class="ph ph-path"></i> Optimisation</div>
                            <div id="strategies-list"></div>
                            <div id="suggestions-list" class="suggestions-scroller"></div>
                            
                            <div class="form-check mt-3 glass-card">
                                <input type="checkbox" id="heatmap-toggle">
                                <label for="heatmap-toggle"><i class="ph ph-map-trifold"></i> Afficher Heatmap</label>
                            </div>
                            
                            <div class="action-stack mt-auto">
                                <button class="btn btn-primary btn-sm" id="btn-goto-dashboard"><i class="ph ph-chart-pie-slice"></i> Ouvrir Dashboard RSE</button>
                                <button class="btn btn-outline btn-sm" id="btn-export"><i class="ph ph-file-xls"></i> Exporter Excel</button>
                                <button class="btn btn-outline btn-sm" id="btn-new"><i class="ph ph-arrow-left"></i> Nouvelle optimisation</button>
                                <!-- Boutons cachés pour compatibilité app.js -->
                                <button id="btn-show-rse" style="display:none;"></button>
                                <button id="btn-show-comparator" style="display:none;"></button>
                                <button id="btn-back-rse" style="display:none;"></button>
                                <button id="btn-back-comparator" style="display:none;"></button>
                            </div>
                        </div>
                    </div>
                </aside>

                <div class="map-wrapper">
                    <div id="map"></div>
                    <div class="map-legend glass-card">
                        <div class="legend-item"><span class="legend-dot bg-green"></span> Employés</div>
                        <div class="legend-item"><span class="legend-dot bg-red"></span> Destination</div>
                    </div>
                </div>
            </div>

            <!-- ================= VIEW: DASHBOARD ================= -->
            <div id="view-dashboard" class="view dashboard-layout">
                <header class="dash-header">
                    <div>
                        <h1>Dashboard RSE & Comparateur</h1>
                        <p class="text-muted">Impact écologique, opérationnel et financier</p>
                    </div>
                </header>

                <!-- KPIs -->
                <section class="kpi-row">
                    <div class="kpi-card glass-card">
                        <div class="kpi-icon text-green"><i class="ph ph-leaf"></i></div>
                        <div class="kpi-content">
                            <div class="kpi-value" id="rse-co2-val">—</div>
                            <div class="kpi-label">CO₂ Évité</div>
                        </div>
                    </div>
                    <div class="kpi-card glass-card">
                        <div class="kpi-icon text-blue"><i class="ph ph-coins"></i></div>
                        <div class="kpi-content">
                            <div class="kpi-value" id="rse-cost-val">—</div>
                            <div class="kpi-label">Économie</div>
                        </div>
                    </div>
                    <div class="kpi-card glass-card">
                        <div class="kpi-icon text-purple"><i class="ph ph-ruler"></i></div>
                        <div class="kpi-content">
                            <div class="kpi-value" id="rse-dist-val">—</div>
                            <div class="kpi-label">Km Économisés</div>
                        </div>
                    </div>
                    <div class="kpi-card glass-card">
                        <div class="kpi-icon text-amber"><i class="ph ph-package"></i></div>
                        <div class="kpi-content">
                            <div class="kpi-value" id="rse-fill-val">—</div>
                            <div class="kpi-label">Remplissage</div>
                        </div>
                    </div>
                </section>

                <!-- Projections Annuelles -->
                <section class="dash-section">
                    <h2 class="section-title"><i class="ph ph-calendar-blank"></i> Projections (252 Jours)</h2>
                    <div class="projection-grid">
                        <div class="proj-item glass-card"><div class="proj-val" id="rse-annual-co2">—</div><div class="proj-lbl">kg CO₂ / an</div></div>
                        <div class="proj-item glass-card"><div class="proj-val" id="rse-annual-cost">—</div><div class="proj-lbl">TND / an</div></div>
                        <div class="proj-item glass-card"><div class="proj-val" id="rse-annual-trees">—</div><div class="proj-lbl">arbres éq.</div></div>
                        <div class="proj-item glass-card"><div class="proj-val" id="rse-annual-km">—</div><div class="proj-lbl">km / an</div></div>
                    </div>
                </section>

                <!-- Charts Grid -->
                <section class="charts-grid">
                    <div class="chart-container glass-card">
                        <h3 class="chart-title">CO₂ : Moovly vs Individuel</h3>
                        <div class="chart-body"><canvas id="co2Chart"></canvas></div>
                    </div>
                    <div class="chart-container glass-card">
                        <h3 class="chart-title">Répartition du Coût</h3>
                        <div class="chart-body"><canvas id="costChart"></canvas></div>
                    </div>
                    <div class="chart-container glass-card span-2">
                        <h3 class="chart-title">Utilisation de la flotte</h3>
                        <div class="chart-body"><canvas id="fleetChart"></canvas></div>
                    </div>
                </section>

                <!-- Comparateur -->
                <section class="dash-section mt-4">
                    <h2 class="section-title"><i class="ph ph-scales"></i> Comparateur de Scénarios</h2>
                    <div class="glass-card p-4">
                        <div class="flex-row gap-3 align-center mb-3">
                            <span class="text-sm fw-600">Simuler :</span>
                            <div id="cap-toggle-group" class="flex-row gap-2"></div>
                            <button class="btn btn-primary btn-sm ml-auto" id="btn-run-compare"><i class="ph ph-play"></i> Lancer</button>
                        </div>
                        
                        <div id="compare-loading" class="hidden text-center p-4">
                            <i class="ph ph-spinner-gap spin text-xl"></i> Calcul...
                        </div>

                        <div id="compare-results" class="hidden">
                            <div class="charts-grid mt-3">
                                <div class="chart-container glass-card"><h3 class="chart-title">Coût (TND)</h3><canvas id="compareCostChart"></canvas></div>
                                <div class="chart-container glass-card"><h3 class="chart-title">CO₂ (kg)</h3><canvas id="compareCo2Chart"></canvas></div>
                                <div class="chart-container glass-card"><h3 class="chart-title">Véhicules</h3><canvas id="compareVehChart"></canvas></div>
                                <div class="chart-container glass-card"><h3 class="chart-title">Distance (km)</h3><canvas id="compareDistChart"></canvas></div>
                            </div>
                            <div class="mt-4 glass-card p-3" id="compare-table" style="overflow-x:auto;"></div>
                            <div class="mt-3 p-3 glass-card bg-indigo-soft border-indigo" id="compare-recommendation"></div>
                        </div>
                    </div>
                </section>
            </div>
        </main>

        <div class="loading-overlay hidden" id="loading">
            <div class="spinner"></div>
            <div class="loading-text" id="loading-text">Chargement…</div>
        </div>
        <div id="toast-container"></div>
        <div class="toast-message hidden" id="pin-toast">
            <span id="pin-name">Positionnement</span>
            <button id="btn-cancel-pin" class="btn btn-sm btn-outline">Annuler</button>
        </div>
    </div>

    <!-- Modals -->
    <div class="modal-overlay hidden" id="modal-manual">
        <div class="modal-content glass-card">
            <div class="modal-header">
                <h3 id="modal-title">Ajouter</h3>
                <button class="modal-close" id="modal-close">&times;</button>
            </div>
            <div class="modal-body">
                <input type="text" class="form-select mb-3" id="modal-name" placeholder="Nom">
                <div id="modal-cap-group" class="hidden"><input type="number" class="form-select" id="modal-capacite"></div>
                <button class="btn btn-primary w-100" id="modal-save">Enregistrer</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay hidden" id="modal-route-details">
        <div class="modal-content glass-card" style="max-width:600px;">
            <div class="modal-header">
                <h3 id="route-modal-title">Détails</h3>
                <button class="modal-close" id="route-modal-close">&times;</button>
            </div>
            <div class="modal-body" id="route-modal-body" style="max-height:60vh; overflow-y:auto;"></div>
            <div class="modal-footer"><button class="btn btn-outline btn-sm" id="route-modal-close-btn">Fermer</button></div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="/static/js/map.js"></script>
    <script src="/static/js/app.js"></script>
</body>
</html>
"""

CSS_CONTENT = """/* ==========================================================================
   MOOVLY SAAS PREMIUM UI
   ========================================================================== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    /* DARK THEME (Default) */
    --bg-main: #0f172a;
    --bg-grad: radial-gradient(circle at top right, #1e1b4b, #0f172a 60%, #020617);
    --surface: rgba(30, 41, 59, 0.6);
    --surface-hover: rgba(51, 65, 85, 0.7);
    --border: rgba(255, 255, 255, 0.08);
    --text-primary: #f8fafc;
    --text-muted: #94a3b8;
    
    --brand-500: #6366f1;
    --brand-600: #4f46e5;
    --brand-glow: rgba(99, 102, 241, 0.4);
    
    --green: #10b981; --blue: #0ea5e9; --purple: #8b5cf6; --amber: #f59e0b; --red: #ef4444;
}

[data-theme="light"] {
    --bg-main: #f8fafc;
    --bg-grad: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
    --surface: rgba(255, 255, 255, 0.7);
    --surface-hover: rgba(255, 255, 255, 0.9);
    --border: rgba(0, 0, 0, 0.08);
    --text-primary: #0f172a;
    --text-muted: #64748b;
    --brand-glow: rgba(99, 102, 241, 0.2);
}

* { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
body { background: var(--bg-grad); color: var(--text-primary); height: 100vh; overflow: hidden; transition: 0.3s; }

/* UTILS */
.hidden { display: none !important; }
.text-muted { color: var(--text-muted); }
.text-green { color: var(--green); } .bg-green { background: var(--green); }
.text-blue { color: var(--blue); } .text-purple { color: var(--purple); }
.text-amber { color: var(--amber); } .bg-red { background: var(--red); }
.text-center { text-align: center; } .mt-2 { margin-top: 8px; } .mt-3 { margin-top: 16px; } .mt-4 { margin-top: 24px; }
.mb-3 { margin-bottom: 16px; } .w-100 { width: 100%; } .p-3 { padding: 16px; } .p-4 { padding: 24px; }
.flex-row { display: flex; } .gap-2 { gap: 8px; } .gap-3 { gap: 12px; } .align-center { align-items: center; } .ml-auto { margin-left: auto; }
.spin { animation: spin 1s linear infinite; } @keyframes spin { 100% { transform: rotate(360deg); } }
.bg-indigo-soft { background: rgba(99, 102, 241, 0.1); } .border-indigo { border: 1px solid rgba(99,102,241,0.3); }

/* GLASSMORPHISM */
.glass-card {
    background: var(--surface);
    backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border);
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    transition: 0.3s;
}

/* LAYOUT */
#app-container { display: flex; height: 100vh; }
#main-content { flex: 1; position: relative; overflow: hidden; }
.view { display: none; height: 100%; width: 100%; }
.view.active { display: flex; animation: fadeIn 0.4s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

/* GLOBAL SIDEBAR */
.main-nav {
    width: 70px; background: rgba(0,0,0,0.2); border-right: 1px solid var(--border);
    backdrop-filter: blur(20px); display: flex; flex-direction: column; align-items: center; padding: 20px 0; z-index: 2000;
}
.nav-brand img { width: 40px; border-radius: 10px; margin-bottom: 30px; }
.nav-links { display: flex; flex-direction: column; gap: 16px; flex: 1; }
.nav-item {
    width: 44px; height: 44px; border-radius: 12px; border: none; background: transparent; color: var(--text-muted);
    font-size: 22px; cursor: pointer; transition: 0.3s; display: flex; align-items: center; justify-content: center;
}
.nav-item:hover { background: var(--surface); color: var(--text-primary); }
.nav-item.active { background: var(--brand-500); color: #fff; box-shadow: 0 4px 15px var(--brand-glow); }
.nav-bottom { margin-top: auto; }

/* PLANNING VIEW */
.sub-sidebar { width: 380px; background: var(--surface); backdrop-filter: blur(20px); border-right: 1px solid var(--border); display: flex; flex-direction: column; z-index: 1000;}
.map-wrapper { flex: 1; position: relative; }
#map { width: 100%; height: 100%; }
.map-legend { position: absolute; bottom: 20px; right: 20px; z-index: 900; padding: 12px 16px; display: flex; gap: 12px; font-size: 12px;}
.legend-item { display: flex; align-items: center; gap: 6px; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; }

/* PANELS */
.stepper-nav { display: flex; align-items: center; padding: 20px; border-bottom: 1px solid var(--border); }
.step { display: flex; align-items: center; gap: 8px; opacity: 0.5; font-size: 12px; font-weight: 600;}
.step.active { opacity: 1; color: var(--brand-500); }
.step-num { width: 24px; height: 24px; border-radius: 50%; border: 2px solid currentColor; display: flex; align-items: center; justify-content: center;}
.step.active .step-num { background: var(--brand-500); color: #fff; border-color: var(--brand-500); }
.step-line { flex: 1; height: 2px; background: var(--border); margin: 0 10px; }
.panel-container { flex: 1; overflow-y: auto; position: relative; }
.panel { display: none; padding: 20px; flex-direction: column; height: 100%; }
.panel.active { display: flex; }
.section-title { font-size: 14px; font-weight: 700; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; color: var(--text-primary);}

/* UPLOAD & FORMS */
.upload-card { border: 2px dashed var(--border); padding: 16px; border-radius: 12px; display: flex; align-items: center; gap: 12px; cursor: pointer; transition: 0.3s; position: relative; }
.upload-card:hover { border-color: var(--brand-500); background: rgba(99,102,241,0.05); }
.upload-icon { font-size: 24px; color: var(--brand-500); }
.upload-label { font-size: 13px; font-weight: 600; display: block;}
.upload-input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.upload-badge { background: var(--green); color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700; }
.btn-pin-manual { background: none; border: none; color: var(--blue); font-size: 12px; font-weight: 600; cursor: pointer; padding: 8px 0; text-align: left; }

.form-select { width: 100%; padding: 10px 14px; background: var(--bg-main); border: 1px solid var(--border); border-radius: 8px; color: var(--text-primary); font-size: 13px; outline: none;}
.form-select:focus { border-color: var(--brand-500); }

/* BUTTONS */
.btn { padding: 10px 16px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 8px; border: none; transition: 0.3s;}
.btn-primary { background: linear-gradient(135deg, var(--brand-500), var(--brand-600)); color: #fff; box-shadow: 0 4px 15px var(--brand-glow); }
.btn-primary:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 20px var(--brand-glow); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-primary); }
.btn-outline:hover { background: var(--surface); }
.btn-sm { padding: 8px 12px; font-size: 12px; }
.btn-link { background: none; border: none; color: var(--brand-500); font-size: 12px; cursor: pointer; }

/* LISTS & RESULTS */
.emp-list { max-height: 200px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.emp-item { padding: 8px 12px; background: var(--surface); border-radius: 6px; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 10px; border: 1px solid transparent; }
.emp-item.selected { border-color: var(--brand-500); background: rgba(99,102,241,0.1); }
.emp-item::before { content: ''; width: 14px; height: 14px; border: 2px solid var(--border); border-radius: 4px; }
.emp-item.selected::before { background: var(--brand-500); border-color: var(--brand-500); }

.strategy-item { padding: 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; cursor: pointer; margin-bottom: 8px; transition: 0.3s; }
.strategy-item.active { border-color: var(--brand-500); background: rgba(99,102,241,0.1); }
.strategy-name { font-size: 13px; font-weight: 700; margin-bottom: 4px; }
.strategy-stats { font-size: 11px; color: var(--text-muted); }

.result-card { background: var(--surface); border: 1px solid var(--border); padding: 14px; border-radius: 10px; margin-bottom: 10px; transition: 0.3s; }
.result-card.selected { border-color: var(--brand-500); box-shadow: 0 0 15px var(--brand-glow); }
.result-badge { background: rgba(99,102,241,0.2); color: var(--brand-500); padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; }

.form-check { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; }
.action-stack { display: flex; flex-direction: column; gap: 8px; }
.cap-toggle-btn { background: var(--surface); border: 1px solid var(--border); color: var(--text-primary); padding: 6px 12px; border-radius: 20px; font-size: 12px; cursor: pointer; }
.cap-toggle-btn.active { background: var(--brand-500); color: #fff; border-color: var(--brand-500); }

/* DASHBOARD VIEW */
.dashboard-layout { overflow-y: auto; padding: 40px; display: flex; flex-direction: column; gap: 30px; }
.dash-header h1 { font-size: 28px; font-weight: 800; letter-spacing: -1px; margin-bottom: 4px; }
.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.kpi-card { padding: 24px; display: flex; align-items: center; gap: 20px; }
.kpi-icon { width: 56px; height: 56px; border-radius: 16px; background: rgba(255,255,255,0.05); display: flex; align-items: center; justify-content: center; font-size: 28px; }
.kpi-value { font-size: 24px; font-weight: 800; margin-bottom: 4px; }
.kpi-label { font-size: 13px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;}

.projection-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }
.proj-item { padding: 16px; text-align: center; }
.proj-val { font-size: 20px; font-weight: 700; color: var(--blue); margin-bottom: 4px; }
.proj-lbl { font-size: 12px; color: var(--text-muted); }

.charts-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.span-2 { grid-column: span 2; }
.chart-container { padding: 20px; }
.chart-title { font-size: 15px; font-weight: 700; margin-bottom: 20px; display: flex; align-items: center; gap: 8px;}
.chart-body { position: relative; height: 300px; width: 100%; }

/* MODALS & LOADERS */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); z-index: 3000; display: flex; align-items: center; justify-content: center; }
.modal-content { width: 400px; padding: 24px; }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.modal-close { background: none; border: none; font-size: 24px; color: var(--text-muted); cursor: pointer; }
.loading-overlay { position: absolute; inset: 0; background: rgba(15,23,42,0.8); backdrop-filter: blur(8px); z-index: 2500; display: flex; flex-direction: column; align-items: center; justify-content: center;}

/* TABLE */
.compare-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.compare-table th, .compare-table td { padding: 12px; text-align: left; border-bottom: 1px solid var(--border); }
.compare-table th { color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 11px;}
.best-row { background: rgba(16, 185, 129, 0.1); }
"""

with open('c:/Users/yassine/Desktop/test_modéles/Test 2/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(HTML_CONTENT)

with open('c:/Users/yassine/Desktop/test_modéles/Test 2/static/css/style.css', 'w', encoding='utf-8') as f:
    f.write(CSS_CONTENT)

print("HTML and CSS rewritten.")
