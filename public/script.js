document.addEventListener('DOMContentLoaded', () => {
    const markNativeShell = () => document.documentElement.classList.add('native-shell');
    if(window.pywebview) markNativeShell();
    window.addEventListener('pywebviewready', markNativeShell, { once: true });

    // --- State ---
    let currentPlaylist = [];
    let activePlaylistView = []; // La lista que se está reproduciendo actualmente
    let currentIndex = -1;
    let isShuffle = false;
    let repeatMode = 0; // 0: off, 1: all, 2: one
    let playlistsData = { "Favoritos": [], "Mis Playlists": {} };
    let shuffleHistory = [];
    let locationSettings = null;
    let libraryLoaded = false;
    let libraryRendered = false;
    let favoriteSongKeys = new Set();

    const songKey = song => `${song.source_id || ''}::${song.filename || ''}`;

    // --- Tab Navigation ---
    const tabs = document.querySelectorAll('.nav-links li');
    const sections = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));
            
            tab.classList.add('active');
            const target = tab.getAttribute('data-tab');
            document.getElementById(`tab-${target}`).classList.add('active');
            
            if(target === 'library') {
                if(libraryLoaded) {
                    if(!libraryRendered) renderLibrary(document.getElementById('library-search').value);
                } else {
                    loadLibrary();
                }
            }
            if(target === 'playlists') renderPlaylistsTab();
            if(target === 'settings') loadSettings();
        });
        tab.addEventListener('keydown', event => {
            if(event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                tab.click();
            }
        });
    });

    // --- Audio Player Elements ---
    const audio = document.getElementById('audio-player');
    const btnPlay = document.getElementById('btn-play');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const btnShuffle = document.getElementById('btn-shuffle');
    const btnRepeat = document.getElementById('btn-repeat');
    const btnFav = document.getElementById('btn-player-fav');
    
    const progressBar = document.getElementById('progress-bar');
    const volumeBar = document.getElementById('volume-bar');
    const timeCurrent = document.getElementById('time-current');
    const timeTotal = document.getElementById('time-total');
    
    function formatTime(seconds) {
        if(isNaN(seconds)) return "0:00";
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    }

    // --- API Calls ---
    async function loadPlaylists() {
        try {
            const res = await fetch('/api/playlists');
            playlistsData = await res.json();
            favoriteSongKeys = new Set(playlistsData["Favoritos"].map(songKey));
        } catch (e) {
            console.error('Error loading playlists:', e);
        }
    }

    async function savePlaylists() {
        try {
            await fetch('/api/playlists', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(playlistsData)
            });
        } catch (e) {
            console.error('Error saving playlists:', e);
        }
    }

    async function loadLibrary(force = false) {
        if(libraryLoaded && !force) return;
        try {
            const res = await fetch('/library');
            const data = await res.json();
            currentPlaylist = data.songs;
            libraryLoaded = true;
            libraryRendered = false;
            
            document.getElementById('library-count').textContent = currentPlaylist.length;
            document.getElementById('card-songs').querySelector('h3').textContent = currentPlaylist.length;

            if(document.getElementById('tab-library').classList.contains('active')) {
                renderLibrary(document.getElementById('library-search').value);
            }
        } catch (e) {
            console.error('Error loading library:', e);
        }
    }

    async function loadSettings() {
        const status = document.getElementById('settings-status');
        try {
            const res = await fetch('/api/settings');
            if(!res.ok) throw new Error('No se pudo cargar la configuración');
            locationSettings = await res.json();
            renderSettings();
            status.textContent = '';
            status.className = 'settings-status';
        } catch (error) {
            status.textContent = error.message;
            status.className = 'settings-status error';
        }
    }

    function renderSettings() {
        if(!locationSettings) return;
        document.getElementById('download-path').value = locationSettings.download_dir;
        document.getElementById('default-music-path').textContent = locationSettings.default_download_dir;
        document.getElementById('locations-count').textContent = locationSettings.library_dirs.length;

        const list = document.getElementById('library-dirs-list');
        list.innerHTML = '';
        locationSettings.library_dirs.forEach(directory => {
            const item = document.createElement('article');
            item.className = 'location-row';
            item.innerHTML = `
                <div class="location-row-icon"><span class="material-symbols-outlined">${directory.is_download ? 'download' : 'folder'}</span></div>
                <div class="location-row-copy"><strong>${escapeHtml(directory.name)}</strong><span>${escapeHtml(directory.path)}</span></div>
                ${directory.is_download
                    ? '<span class="location-type">Descargas</span>'
                    : '<button class="remove-location icon-button" type="button" title="Quitar esta carpeta" aria-label="Quitar esta carpeta"><span class="material-symbols-outlined">close</span></button>'}
            `;
            if(!directory.is_download) {
                item.querySelector('.remove-location').onclick = () => updateSettings('remove_library', directory.path, 'Carpeta retirada de la biblioteca.');
            }
            list.appendChild(item);
        });
    }

    function escapeHtml(value) {
        const element = document.createElement('span');
        element.textContent = value ?? '';
        return element.innerHTML;
    }

    async function updateSettings(action, path, successMessage) {
        const status = document.getElementById('settings-status');
        if(!path || !path.trim()) {
            status.textContent = 'Selecciona o escribe una ruta válida.';
            status.className = 'settings-status error';
            return;
        }
        status.textContent = 'Guardando…';
        status.className = 'settings-status';
        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, path: path.trim() })
            });
            const data = await res.json();
            if(!res.ok || data.error) throw new Error(data.error || 'No se pudo guardar la ubicación');
            locationSettings = data;
            renderSettings();
            document.getElementById('library-path').value = '';
            status.textContent = successMessage;
            status.className = 'settings-status success';
            await loadLibrary(true);
        } catch (error) {
            status.textContent = error.message;
            status.className = 'settings-status error';
        }
    }

    async function chooseFolder(inputId) {
        const input = document.getElementById(inputId);
        if(window.pywebview?.api?.select_folder) {
            const selected = await window.pywebview.api.select_folder();
            if(selected) input.value = selected;
            return;
        }
        const selected = prompt('Escribe o pega la ruta completa de la carpeta:', input.value);
        if(selected !== null) input.value = selected.trim();
    }

    // --- Renderizado de Biblioteca ---
    function renderLibrary(filterText = '') {
        const list = document.getElementById('library-list');
        const normalizedFilter = filterText.trim().toLowerCase();

        if(currentPlaylist.length === 0) {
            list.innerHTML = '<p class="loading-text">No tienes canciones en tu PC todavía. ¡Ve a la pestaña Buscar!</p>';
            libraryRendered = true;
            return;
        }

        const fragment = document.createDocumentFragment();
        currentPlaylist.forEach((song, index) => {
            const searchText = `${song.title} ${song.artist}`.toLowerCase();
            if(normalizedFilter && !searchText.includes(normalizedFilter)) return;
            const isFav = favoriteSongKeys.has(songKey(song));

            const div = document.createElement('div');
            div.className = 'song-card';
            div.dataset.songIndex = index;

            const imgHtml = song.thumbnail_url
                ? `<img src="${escapeHtml(song.thumbnail_url)}" class="song-card-img" loading="lazy" decoding="async" alt="">`
                : `<span class="material-symbols-outlined" style="font-size: 40px; color: #475569;">music_note</span>`;

            div.innerHTML = `
                <div class="song-card-img-container" data-action="play" role="button" tabindex="0" aria-label="Reproducir ${escapeHtml(song.title)}">
                    ${imgHtml}
                    <button class="song-card-action" type="button" tabindex="-1" aria-hidden="true">
                        <span class="material-symbols-outlined">play_arrow</span>
                    </button>
                </div>
                <div class="song-card-title">${escapeHtml(song.title)}</div>
                <div class="song-card-artist">${escapeHtml(song.artist)}</div>
                <button class="fav-btn control-btn" data-action="favorite" type="button" style="position: absolute; top: 15px; right: 15px; background: rgba(0,0,0,0.5); border-radius: 50%; padding: 5px; color: ${isFav ? '#EF4444' : '#fff'};" title="Favoritos" aria-label="Cambiar favorito">
                    <span class="material-symbols-outlined" style="font-size: 20px;">${isFav ? 'favorite' : 'favorite_border'}</span>
                </button>
                <button class="delete-btn control-btn" data-action="delete" type="button" style="position: absolute; top: 15px; left: 15px; background: rgba(239,68,68,0.7); border-radius: 50%; padding: 5px; color: #fff; opacity: 0; transition: opacity 0.3s;" title="Eliminar Canción" aria-label="Eliminar canción">
                    <span class="material-symbols-outlined" style="font-size: 20px;">delete</span>
                </button>
            `;
            if(activePlaylistView === currentPlaylist && index === currentIndex) div.classList.add('playing');

            fragment.appendChild(div);
        });
        list.replaceChildren(fragment);
        libraryRendered = true;
    }

    function updateLibraryPlayingState() {
        document.querySelector('#library-list .song-card.playing')?.classList.remove('playing');
        if(activePlaylistView !== currentPlaylist || currentIndex < 0) return;
        document.querySelector(`#library-list .song-card[data-song-index="${currentIndex}"]`)?.classList.add('playing');
    }

    window.playFromLibrary = function(index) {
        activePlaylistView = currentPlaylist;
        playSong(index);
    };

    const libraryList = document.getElementById('library-list');
    libraryList.addEventListener('keydown', event => {
        if((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-action="play"]')) {
            event.preventDefault();
            const card = event.target.closest('.song-card');
            if(card) window.playFromLibrary(Number(card.dataset.songIndex));
        }
    });
    libraryList.addEventListener('click', async event => {
        const card = event.target.closest('.song-card');
        if(!card) return;
        const index = Number(card.dataset.songIndex);
        const song = currentPlaylist[index];
        if(!song) return;

        const action = event.target.closest('[data-action]')?.dataset.action;
        if(action === 'play') {
            window.playFromLibrary(index);
            return;
        }
        if(action === 'favorite') {
            await toggleFavorite(song);
            const isFav = favoriteSongKeys.has(songKey(song));
            const button = card.querySelector('.fav-btn');
            button.style.color = isFav ? '#EF4444' : '#fff';
            button.querySelector('.material-symbols-outlined').textContent = isFav ? 'favorite' : 'favorite_border';
            return;
        }
        if(action === 'delete' && confirm(`¿Estás seguro de que quieres borrar "${song.title}" de tu PC? Esta acción no se puede deshacer.`)) {
            try {
                const res = await fetch('/api/delete_song', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: song.filename, source_id: song.source_id })
                });
                const data = await res.json();
                if(data.status === 'ok') {
                    await loadLibrary(true);
                } else {
                    alert("Error al borrar el archivo: " + data.error);
                }
            } catch (error) {
                alert("Error de conexión al intentar borrar.");
            }
        }
    });

    // --- Favoritos Logic ---
    async function toggleFavorite(song) {
        const key = songKey(song);
        const index = playlistsData["Favoritos"].findIndex(s => songKey(s) === key);
        if (index > -1) {
            playlistsData["Favoritos"].splice(index, 1);
            favoriteSongKeys.delete(key);
        } else {
            playlistsData["Favoritos"].push(song);
            favoriteSongKeys.add(key);
        }
        await savePlaylists();
        updatePlayerFavIcon();
    }

    function updatePlayerFavIcon() {
        if(currentIndex === -1 || !activePlaylistView[currentIndex]) return;
        const currentSong = activePlaylistView[currentIndex];
        const isFav = favoriteSongKeys.has(songKey(currentSong));
        btnFav.style.color = isFav ? '#EF4444' : '#475569';
        btnFav.innerHTML = `<span class="material-symbols-outlined">${isFav ? 'favorite' : 'favorite_border'}</span>`;
    }

    btnFav.onclick = () => {
        if(currentIndex > -1 && activePlaylistView[currentIndex]) {
            toggleFavorite(activePlaylistView[currentIndex]).then(() => {
                if(activePlaylistView === currentPlaylist) {
                    const card = document.querySelector(`#library-list .song-card[data-song-index="${currentIndex}"]`);
                    const button = card?.querySelector('.fav-btn');
                    if(button) {
                        const isFav = favoriteSongKeys.has(songKey(activePlaylistView[currentIndex]));
                        button.style.color = isFav ? '#EF4444' : '#fff';
                        button.querySelector('.material-symbols-outlined').textContent = isFav ? 'favorite' : 'favorite_border';
                    }
                }
            });
        }
    };

    // --- Reproducción y Controles ---
    function playSong(index) {
        if(activePlaylistView.length === 0) return;
        if(index < 0) index = activePlaylistView.length - 1;
        if(index >= activePlaylistView.length) index = 0;
        
        currentIndex = index;
        const song = activePlaylistView[currentIndex];
        updateLibraryPlayingState();
        
        document.getElementById('player-title').textContent = song.title;
        document.getElementById('player-artist').textContent = song.artist;
        updatePlayerFavIcon();
        
        const playerImg = document.getElementById('player-img');
        const playerIcon = document.getElementById('player-art-icon');
        if (song.thumbnail_url) {
            playerImg.src = song.thumbnail_url;
            playerImg.style.display = 'block';
            playerIcon.style.display = 'none';
        } else {
            playerImg.style.display = 'none';
            playerIcon.style.display = 'block';
        }
        
        audio.src = song.stream_url || `/stream?file=${encodeURIComponent(song.filename)}`;
        audio.play().catch(error => console.error('No se pudo iniciar la reproducción:', error));
        btnPlay.innerHTML = '<span class="material-symbols-outlined">pause</span>';
    }

    btnPlay.onclick = () => {
        if(audio.paused) {
            audio.play();
            btnPlay.innerHTML = '<span class="material-symbols-outlined">pause</span>';
        } else {
            audio.pause();
            btnPlay.innerHTML = '<span class="material-symbols-outlined">play_arrow</span>';
        }
    };

    function playNext() {
        if(activePlaylistView.length === 0) return;
        if(repeatMode === 2) {
            audio.currentTime = 0;
            audio.play();
            return;
        }
        
        if(isShuffle) {
            let nextIndex = Math.floor(Math.random() * activePlaylistView.length);
            if(nextIndex === currentIndex && activePlaylistView.length > 1) {
                nextIndex = (nextIndex + 1) % activePlaylistView.length;
            }
            playSong(nextIndex);
        } else {
            if(currentIndex >= activePlaylistView.length - 1 && repeatMode === 0) {
                // Stop if no repeat and at end
                audio.pause();
                btnPlay.innerHTML = '<span class="material-symbols-outlined">play_arrow</span>';
            } else {
                playSong(currentIndex + 1);
            }
        }
    }

    btnNext.onclick = playNext;
    btnPrev.onclick = () => playSong(currentIndex - 1);

    audio.addEventListener('timeupdate', () => {
        progressBar.value = (audio.currentTime / audio.duration) * 100 || 0;
        timeCurrent.textContent = formatTime(audio.currentTime);
    });

    audio.addEventListener('loadedmetadata', () => {
        timeTotal.textContent = formatTime(audio.duration);
    });

    audio.addEventListener('ended', playNext);

    progressBar.addEventListener('input', () => {
        audio.currentTime = (progressBar.value / 100) * audio.duration;
    });

    const btnSpeed = document.getElementById('btn-speed');
    const speeds = [1.0, 1.25, 1.5, 2.0];
    let currentSpeedIndex = 0;
    
    btnSpeed.onclick = () => {
        currentSpeedIndex = (currentSpeedIndex + 1) % speeds.length;
        const newSpeed = speeds[currentSpeedIndex];
        audio.playbackRate = newSpeed;
        btnSpeed.textContent = newSpeed + 'x';
        
        if (newSpeed !== 1.0) {
            btnSpeed.style.background = 'var(--primary)';
            btnSpeed.style.color = 'white';
        } else {
            btnSpeed.style.background = 'transparent';
            btnSpeed.style.color = 'var(--text-main)';
        }
    };

    volumeBar.addEventListener('input', () => {
        audio.volume = volumeBar.value / 100;
    });

    // Toggle Shuffle
    btnShuffle.onclick = () => {
        isShuffle = !isShuffle;
        btnShuffle.style.color = isShuffle ? '#3B82F6' : '#475569';
    };

    // Toggle Repeat
    btnRepeat.onclick = () => {
        repeatMode = (repeatMode + 1) % 3;
        if(repeatMode === 0) {
            btnRepeat.style.color = '#475569';
            btnRepeat.innerHTML = '<span class="material-symbols-outlined">repeat</span>';
        } else if(repeatMode === 1) {
            btnRepeat.style.color = '#3B82F6';
            btnRepeat.innerHTML = '<span class="material-symbols-outlined">repeat</span>';
        } else {
            btnRepeat.style.color = '#3B82F6';
            btnRepeat.innerHTML = '<span class="material-symbols-outlined">repeat_one</span>';
        }
    };

    // --- Playlists UI ---
    document.getElementById('btn-new-playlist').onclick = async () => {
        const name = prompt('Nombre de la nueva Playlist:');
        if(name && name.trim() !== '') {
            if(!playlistsData["Mis Playlists"][name]) {
                playlistsData["Mis Playlists"][name] = [];
                await savePlaylists();
                renderPlaylistsTab();
            } else {
                alert('Esa playlist ya existe.');
            }
        }
    };

    function renderPlaylistsTab() {
        const grid = document.getElementById('playlists-grid');
        grid.innerHTML = '';
        
        // Render Favoritos
        const favCard = document.createElement('div');
        favCard.className = 'card';
        favCard.style.cursor = 'pointer';
        favCard.style.background = 'linear-gradient(145deg, rgba(239, 68, 68, 0.2) 0%, rgba(15,23,42,0.4) 100%)';
        favCard.innerHTML = `
            <h3 style="color: #EF4444;"><span class="material-symbols-outlined" style="font-size: 32px;">favorite</span></h3>
            <p style="font-size: 18px; color: white;">Favoritos</p>
            <p style="font-size: 13px;">${playlistsData["Favoritos"].length} canciones</p>
        `;
        favCard.onclick = () => viewPlaylistContent('Favoritos', playlistsData["Favoritos"]);
        grid.appendChild(favCard);

        // Render custom playlists
        Object.keys(playlistsData["Mis Playlists"]).forEach(name => {
            const list = playlistsData["Mis Playlists"][name];
            const card = document.createElement('div');
            card.className = 'card';
            card.style.cursor = 'pointer';
            card.innerHTML = `
                <h3><span class="material-symbols-outlined" style="font-size: 32px;">queue_music</span></h3>
                <p style="font-size: 18px; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${name}</p>
                <p style="font-size: 13px;">${list.length} canciones</p>
            `;
            card.onclick = () => viewPlaylistContent(name, list);
            grid.appendChild(card);
        });
    }

    function viewPlaylistContent(name, list) {
        const title = document.getElementById('playlist-view-title');
        title.style.display = 'block';
        title.textContent = `Viendo: ${name}`;
        
        const container = document.getElementById('playlist-content-list');
        container.innerHTML = '';
        
        if(list.length === 0) {
            container.innerHTML = '<p class="loading-text">Esta lista está vacía.</p>';
            return;
        }

        list.forEach((song, index) => {
            const div = document.createElement('div');
            div.className = 'song-row';
            div.innerHTML = `
                <div class="song-icon">🎵</div>
                <div class="song-details" onclick="playFromPlaylist('${name}', ${index})">
                    <div class="song-title">${song.title}</div>
                    <div class="song-artist">${song.artist}</div>
                </div>
            `;
            container.appendChild(div);
        });
    }

    window.playFromPlaylist = function(name, index) {
        if (name === 'Favoritos') activePlaylistView = playlistsData["Favoritos"];
        else activePlaylistView = playlistsData["Mis Playlists"][name];
        playSong(index);
    };

    // --- Search & Download ---
    document.getElementById('library-search').addEventListener('input', (e) => {
        renderLibrary(e.target.value);
    });

    document.getElementById('btn-refresh').onclick = () => {
        const btn = document.getElementById('btn-refresh');
        btn.classList.add('spinning');
        btn.querySelector('.refresh-icon').addEventListener('animationend', () => {
            btn.classList.remove('spinning');
        }, { once: true });
        loadLibrary(true);
    };

    document.getElementById('btn-browse-download').onclick = () => chooseFolder('download-path');
    document.getElementById('btn-browse-library').onclick = () => chooseFolder('library-path');
    document.getElementById('btn-save-download').onclick = () => updateSettings(
        'set_download',
        document.getElementById('download-path').value,
        'Nueva carpeta de descargas guardada.'
    );
    document.getElementById('btn-add-library').onclick = () => updateSettings(
        'add_library',
        document.getElementById('library-path').value,
        'Carpeta añadida. La música ya está disponible.'
    );

    document.getElementById('btn-search').onclick = async () => {
        const query = document.getElementById('search-input').value;
        if(!query) return;
        
        const status = document.getElementById('search-status');
        const resultsDiv = document.getElementById('search-results');
        
        status.textContent = 'Buscando en YouTube...';
        status.style.color = '#0088FF';
        resultsDiv.innerHTML = '';

        try {
            const res = await fetch(`/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            
            if(data.error) throw new Error(data.error);
            
            status.textContent = `${data.results.length} resultados encontrados.`;
            status.style.color = '#00CC66';
            
            data.results.forEach(item => {
                const div = document.createElement('div');
                div.className = 'song-card';
                div.innerHTML = `
                    <div class="song-card-img-container">
                        <img src="${item.thumbnail}" class="song-card-img">
                        <button class="song-card-action download-btn" title="Descargar">
                            <span class="material-symbols-outlined">download</span>
                        </button>
                    </div>
                    <div class="song-card-title">${item.title}</div>
                    <div class="song-card-artist">${item.artist}</div>
                `;
                
                div.querySelector('.download-btn').onclick = (e) => {
                    e.stopPropagation();
                    downloadSong(item.videoId, item.title, item.thumbnail, div.querySelector('.download-btn'));
                };
                
                resultsDiv.appendChild(div);
            });
        } catch (e) {
            status.textContent = `Error: ${e.message}`;
            status.style.color = '#FF6666';
        }
    };

    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if(e.key === 'Enter') document.getElementById('btn-search').click();
    });

    // --- Historial ---
    const historyList = document.getElementById('history-list');
    let downloadHistory = [];

    function updateHistoryUI() {
        if(downloadHistory.length === 0) {
            historyList.innerHTML = '<p class="loading-text">Aún no has descargado nada en esta sesión.</p>';
            return;
        }
        
        historyList.innerHTML = '';
        downloadHistory.slice().reverse().forEach(item => {
            const div = document.createElement('div');
            div.className = 'song-row';
            div.style.flexDirection = 'column';
            div.style.alignItems = 'stretch';
            div.style.gap = '10px';
            
            let statusIcon = '⏳';
            let statusColor = '#3B82F6';
            if (item.status === 'done') { statusIcon = '✅'; statusColor = '#10B981'; }
            if (item.status === 'error') { statusIcon = '❌'; statusColor = '#EF4444'; }
            
            div.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <img src="${item.thumbnail}" width="40" height="40" style="border-radius:8px; object-fit:cover;">
                        <div>
                            <div class="song-title">${item.title}</div>
                            <div class="song-artist" style="color: ${statusColor}; font-weight: 600;">${statusIcon} ${item.statusText}</div>
                        </div>
                    </div>
                </div>
                ${item.status !== 'done' && item.status !== 'error' ? `
                <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden;">
                    <div style="width: ${item.progress}%; height: 100%; background: ${statusColor}; transition: width 0.3s;"></div>
                </div>
                ` : ''}
            `;
            historyList.appendChild(div);
        });
    }

    document.getElementById('btn-clear-history').onclick = () => {
        downloadHistory = [];
        updateHistoryUI();
    };

    function downloadSong(id, title, thumbnail, btn) {
        btn.innerHTML = '<span class="material-symbols-outlined" style="animation: spin 2s linear infinite;">sync</span>';
        btn.style.background = 'rgba(59, 130, 246, 0.2)';
        btn.style.color = '#3B82F6';
        btn.disabled = true;
        
        const historyItem = { id, title, thumbnail, status: 'starting', statusText: 'Iniciando...', progress: 0 };
        downloadHistory.push(historyItem);
        updateHistoryUI();
        
        const evtSource = new EventSource(`/pc/download?id=${id}`);
        
        evtSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.status === 'preparing') {
                historyItem.status = 'preparing';
                historyItem.statusText = data.text;
                historyItem.downloadDir = data.download_dir;
                updateHistoryUI();
            } else if (data.status === 'downloading') {
                const match = data.text.match(/\[download\]\s+([\d\.]+)\%/);
                if(match) {
                    historyItem.progress = parseFloat(match[1]);
                    historyItem.status = 'downloading';
                    historyItem.statusText = `Descargando... ${historyItem.progress}%`;
                    updateHistoryUI();
                }
            } else if (data.status === 'processing') {
                historyItem.status = 'processing';
                historyItem.statusText = 'Procesando audio...';
                historyItem.progress = 100;
                updateHistoryUI();
            } else if (data.status === 'done') {
                historyItem.status = 'done';
                historyItem.statusText = data.text || 'Descarga completada';
                historyItem.file = data.file;
                updateHistoryUI();
                btn.innerHTML = '<span class="material-symbols-outlined">check_circle</span>';
                btn.style.background = 'rgba(16, 185, 129, 0.2)';
                btn.style.color = '#10B981';
                loadLibrary(true);
                evtSource.close();
            } else if (data.status === 'error') {
                historyItem.status = 'error';
                historyItem.statusText = data.text || 'Error en descarga';
                updateHistoryUI();
                btn.innerHTML = '<span class="material-symbols-outlined">error</span>';
                btn.style.background = 'rgba(239, 68, 68, 0.2)';
                btn.style.color = '#EF4444';
                btn.disabled = false;
                evtSource.close();
            }
        };
        
        evtSource.onerror = function() {
            historyItem.status = 'error';
            historyItem.statusText = 'Error de conexión con el servidor';
            updateHistoryUI();
            btn.innerHTML = '<span class="material-symbols-outlined">error</span>';
            btn.style.background = 'rgba(239, 68, 68, 0.2)';
            btn.style.color = '#EF4444';
            btn.disabled = false;
            evtSource.close();
        };
    }

    // Inicializar app
    Promise.all([loadPlaylists(), loadSettings()]).then(() => loadLibrary());
});
