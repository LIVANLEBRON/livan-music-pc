document.addEventListener('DOMContentLoaded', () => {
    // --- State ---
    let currentPlaylist = [];
    let activePlaylistView = []; // La lista que se está reproduciendo actualmente
    let currentIndex = -1;
    let isShuffle = false;
    let repeatMode = 0; // 0: off, 1: all, 2: one
    let playlistsData = { "Favoritos": [], "Mis Playlists": {} };
    let shuffleHistory = [];

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
            
            if(target === 'library') loadLibrary();
            if(target === 'playlists') renderPlaylistsTab();
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

    async function loadLibrary() {
        try {
            const res = await fetch('/library');
            const data = await res.json();
            currentPlaylist = data.songs;
            
            document.getElementById('library-count').textContent = currentPlaylist.length;
            document.getElementById('card-songs').querySelector('h3').textContent = currentPlaylist.length;
            
            renderLibrary(document.getElementById('library-search').value);
        } catch (e) {
            console.error('Error loading library:', e);
        }
    }

    // --- Renderizado de Biblioteca ---
    function renderLibrary(filterText = '') {
        const list = document.getElementById('library-list');
        list.innerHTML = '';
        
        if(currentPlaylist.length === 0) {
            list.innerHTML = '<p class="loading-text">No tienes canciones en tu PC todavía. ¡Ve a la pestaña Buscar!</p>';
            return;
        }

        currentPlaylist.forEach((song, index) => {
            const searchText = `${song.title} ${song.artist}`.toLowerCase();
            if(filterText && !searchText.includes(filterText.toLowerCase())) return;
            const isFav = playlistsData["Favoritos"].some(s => s.filename === song.filename);

            const div = document.createElement('div');
            div.className = 'song-card';
            
            // Si hay portada
            let imgHtml = song.thumbnail_url 
                ? `<img src="${song.thumbnail_url}" class="song-card-img">`
                : `<span class="material-symbols-outlined" style="font-size: 40px; color: #475569;">music_note</span>`;
                
            div.innerHTML = `
                <div class="song-card-img-container" onclick="playFromLibrary(${index})">
                    ${imgHtml}
                    <button class="song-card-action">
                        <span class="material-symbols-outlined">play_arrow</span>
                    </button>
                </div>
                <div class="song-card-title">${song.title}</div>
                <div class="song-card-artist">${song.artist}</div>
                <button class="fav-btn control-btn" style="position: absolute; top: 15px; right: 15px; background: rgba(0,0,0,0.5); border-radius: 50%; padding: 5px; color: ${isFav ? '#EF4444' : '#fff'};" title="Favoritos">
                    <span class="material-symbols-outlined" style="font-size: 20px;">${isFav ? 'favorite' : 'favorite_border'}</span>
                </button>
                <button class="delete-btn control-btn" style="position: absolute; top: 15px; left: 15px; background: rgba(239,68,68,0.7); border-radius: 50%; padding: 5px; color: #fff; opacity: 0; transition: opacity 0.3s;" title="Eliminar Canción">
                    <span class="material-symbols-outlined" style="font-size: 20px;">delete</span>
                </button>
            `;
            if(activePlaylistView === currentPlaylist && index === currentIndex) div.classList.add('playing');
            
            // Mostrar botón de borrar solo al hacer hover
            div.onmouseenter = () => div.querySelector('.delete-btn').style.opacity = '1';
            div.onmouseleave = () => div.querySelector('.delete-btn').style.opacity = '0';
            
            // Lógica de botón Favorito
            div.querySelector('.fav-btn').onclick = async (e) => {
                e.stopPropagation();
                toggleFavorite(song);
                renderLibrary(document.getElementById('library-search').value);
            };
            
            // Lógica de botón Eliminar
            div.querySelector('.delete-btn').onclick = async (e) => {
                e.stopPropagation();
                if (confirm(`¿Estás seguro de que quieres borrar "${song.title}" de tu PC? Esta acción no se puede deshacer.`)) {
                    try {
                        const res = await fetch('/api/delete_song', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ filename: song.filename })
                        });
                        const data = await res.json();
                        if (data.status === 'ok') {
                            loadLibrary(); // recargar
                        } else {
                            alert("Error al borrar el archivo: " + data.error);
                        }
                    } catch (err) {
                        alert("Error de conexión al intentar borrar.");
                    }
                }
            };
            
            list.appendChild(div);
        });
    }

    window.playFromLibrary = function(index) {
        activePlaylistView = currentPlaylist;
        playSong(index);
        renderLibrary(document.getElementById('library-search').value);
    };

    // --- Favoritos Logic ---
    async function toggleFavorite(song) {
        const index = playlistsData["Favoritos"].findIndex(s => s.filename === song.filename);
        if (index > -1) {
            playlistsData["Favoritos"].splice(index, 1);
        } else {
            playlistsData["Favoritos"].push(song);
        }
        await savePlaylists();
        updatePlayerFavIcon();
    }

    function updatePlayerFavIcon() {
        if(currentIndex === -1 || !activePlaylistView[currentIndex]) return;
        const currentSong = activePlaylistView[currentIndex];
        const isFav = playlistsData["Favoritos"].some(s => s.filename === currentSong.filename);
        btnFav.style.color = isFav ? '#EF4444' : '#475569';
        btnFav.innerHTML = `<span class="material-symbols-outlined">${isFav ? 'favorite' : 'favorite_border'}</span>`;
    }

    btnFav.onclick = () => {
        if(currentIndex > -1 && activePlaylistView[currentIndex]) {
            toggleFavorite(activePlaylistView[currentIndex]);
            if(document.getElementById('tab-library').classList.contains('active')) {
                renderLibrary(document.getElementById('library-search').value);
            }
        }
    };

    // --- Reproducción y Controles ---
    function playSong(index) {
        if(activePlaylistView.length === 0) return;
        if(index < 0) index = activePlaylistView.length - 1;
        if(index >= activePlaylistView.length) index = 0;
        
        currentIndex = index;
        const song = activePlaylistView[currentIndex];
        
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
        
        audio.src = `/stream?file=${encodeURIComponent(song.filename)}`;
        audio.play();
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
        loadLibrary();
    };

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
            
            if (data.status === 'downloading') {
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
                historyItem.statusText = 'Completado';
                updateHistoryUI();
                btn.innerHTML = '<span class="material-symbols-outlined">check_circle</span>';
                btn.style.background = 'rgba(16, 185, 129, 0.2)';
                btn.style.color = '#10B981';
                loadLibrary();
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
    loadPlaylists().then(() => loadLibrary());
});
