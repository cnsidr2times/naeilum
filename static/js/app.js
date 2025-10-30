// Naeilum Frontend Application
(function() {
    'use strict';

    // Global state
    const state = {
        currentScreen: 'input',
        userData: {
            firstName: '',
            lastName: '',
            options: {
                gender: 'neutral',
                tags: ['밝음'],
                save: false
            }
        },
        candidates: [],
        selectedName: null,
        sessionId: generateSessionId(),
        currentTags: []
    };

    // Generate session ID
    function generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // Initialize app
    function init() {
        // Set up event listeners
        setupEventListeners();

        // Show initial screen
        showScreen('input');
    }

    // Setup event listeners
    function setupEventListeners() {
        // Name form submission
        const nameForm = document.getElementById('name-form');
        if (nameForm) {
            nameForm.addEventListener('submit', handleNameSubmit);
        }

        // Options toggle
        const toggleOptions = document.getElementById('toggle-options');
        if (toggleOptions) {
            toggleOptions.addEventListener('click', (e) => {
                e.preventDefault();
                const panel = document.getElementById('options-panel');
                panel.classList.toggle('hidden');
                toggleOptions.textContent = panel.classList.contains('hidden') ? 'Options' : 'Hide Options';
            });
        }

        // Name card selection
        document.addEventListener('click', (e) => {
            if (e.target.closest('.name-card')) {
                handleNameCardClick(e.target.closest('.name-card'));
            }
        });

        // Buttons
        const previewBtn = document.getElementById('preview-btn');
        if (previewBtn) {
            previewBtn.addEventListener('click', handlePreviewResults);
        }

        const selectBtn = document.getElementById('select-btn');
        if (selectBtn) {
            selectBtn.addEventListener('click', handleSelectName);
        }

        const fortuneBtn = document.getElementById('fortune-btn');
        if (fortuneBtn) {
            fortuneBtn.addEventListener('click', handleShowFortune);
        }

        const otherFortunesBtn = document.getElementById('other-fortunes-btn');
        if (otherFortunesBtn) {
            otherFortunesBtn.addEventListener('click', handleOtherFortunes);
        }

        const restartBtn = document.getElementById('restart-btn');
        if (restartBtn) {
            restartBtn.addEventListener('click', handleRestart);
        }
    }

    // Handle name form submission
    async function handleNameSubmit(e) {
        e.preventDefault();

        // Get form data
        const firstName = document.getElementById('first-name').value.trim();
        const lastName = document.getElementById('last-name').value.trim();

        // Get options
        const gender = document.querySelector('input[name="gender"]:checked').value;
        const tagCheckboxes = document.querySelectorAll('input[name="tags"]:checked');
        const tags = Array.from(tagCheckboxes).map(cb => cb.value);
        const save = document.getElementById('save-data').checked;

        // Update state
        state.userData.firstName = firstName;
        state.userData.lastName = lastName;
        state.userData.options = {
            gender: gender,
            tags: tags.length > 0 ? tags : ['밝음', '지혜'],
            save: save
        };
        state.currentTags = state.userData.options.tags;

        // Show loading
        showLoading(true);

        try {
            // Call API
            const response = await fetch('/api/suggest-names', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    firstName: firstName,
                    lastName: lastName,
                    options: state.userData.options
                })
            });

            const data = await response.json();

            if (data.success) {
                state.candidates = data.candidates;
                displayNameSelection();
                showScreen('selection');
            } else {
                alert('Failed to generate names. Please try again.');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred. Please try again.');
        } finally {
            showLoading(false);
        }
    }

    // Display name selection screen
    function displayNameSelection() {
        // Set original name
        document.getElementById('original-name').textContent = 
            `${state.userData.firstName} ${state.userData.lastName}`;

        // Simple Korean transliteration for display
        const koreanFirst = transliterateToKorean(state.userData.firstName);
        const koreanLast = transliterateToKorean(state.userData.lastName);
        document.getElementById('original-name-kr').textContent = `${koreanFirst} ${koreanLast}`;

        // Display candidates
        const optionsContainer = document.getElementById('name-options');
        optionsContainer.innerHTML = '';

        state.candidates.forEach((candidate, index) => {
            const card = document.createElement('div');
            card.className = 'name-card';
            card.dataset.index = index;
            card.innerHTML = `
                <div class="name-card-title">${candidate.name_en}</div>
                <div class="name-card-subtitle">${candidate.name_kr}</div>
            `;
            optionsContainer.appendChild(card);
        });
    }

    // Handle name card click
    function handleNameCardClick(card) {
        // Remove previous selection
        document.querySelectorAll('.name-card').forEach(c => c.classList.remove('selected'));

        // Add selection
        card.classList.add('selected');

        // Enable select button
        document.getElementById('select-btn').disabled = false;

        // Store selected name
        const index = parseInt(card.dataset.index);
        state.selectedName = state.candidates[index];
    }

    // Handle preview results
    function handlePreviewResults() {
        if (!state.selectedName && state.candidates.length > 0) {
            state.selectedName = state.candidates[0];
        }

        if (state.selectedName) {
            displayNameMeaning();
            showScreen('meaning');
        }
    }

    // Handle select name
    async function handleSelectName() {
        if (state.selectedName) {
            // Log selection if save is enabled
            if (state.userData.options.save) {
                try {
                    await fetch('/api/log-selection', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            sessionId: state.sessionId,
                            firstName: state.userData.firstName,
                            lastName: state.userData.lastName,
                            chosenName: state.selectedName.name_kr,
                            chosenHanja: state.selectedName.hanja,
                            tags: state.userData.options.tags,
                            save: true
                        })
                    });
                } catch (error) {
                    console.error('Error logging selection:', error);
                }
            }

            displayNameMeaning();
            showScreen('meaning');
        }
    }

    // Display name meaning
    function displayNameMeaning() {
        const name = state.selectedName;

        // Set name header
        document.getElementById('selected-name').textContent = name.name_en;
        document.getElementById('selected-name-hanja').textContent = 
            `${name.name_kr}(${name.hanja.join('')})`;

        // Family name
        document.getElementById('family-name').textContent = name.family_name.korean;
        document.getElementById('family-hanja').textContent = name.family_name.hanja;
        document.getElementById('family-meaning').textContent = name.family_name.meaning;

        // Given name
        const givenNameContainer = document.getElementById('given-syllables');
        givenNameContainer.innerHTML = '';

        name.given_name.forEach(syllable => {
            const item = document.createElement('div');
            item.className = 'syllable-item';
            item.innerHTML = `
                <span class="syllable-char">${syllable.syllable}</span>
                <span class="syllable-hanja">${syllable.hanja}</span>
                <span class="syllable-meaning">${syllable.meaning}</span>
            `;
            givenNameContainer.appendChild(item);
        });

        // Summary
        document.getElementById('name-summary').textContent = name.summary;
    }

    // Handle show fortune
    async function handleShowFortune() {
        showLoading(true);

        try {
            const response = await fetch('/api/fortune', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tags: state.currentTags
                })
            });

            const data = await response.json();

            if (data.success) {
                displayFortune(data.fortune);
                showScreen('fortune');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to generate fortune. Please try again.');
        } finally {
            showLoading(false);
        }
    }

    // Handle other fortunes
    async function handleOtherFortunes() {
        await handleShowFortune();
    }

    // Display fortune
    function displayFortune(fortune) {
        document.getElementById('fortune-date').textContent = fortune.date;
        document.getElementById('cosmic-cookie').textContent = fortune.cosmic_cookie;
        document.getElementById('lucky-snack').textContent = fortune.lucky_snack;
        document.getElementById('deeper-look').textContent = fortune.deeper_look;
    }

    // Handle restart
    function handleRestart() {
        // Reset form
        document.getElementById('name-form').reset();
        document.getElementById('options-panel').classList.add('hidden');
        document.getElementById('toggle-options').textContent = 'Options';

        // Reset state
        state.selectedName = null;
        state.candidates = [];

        // Show input screen
        showScreen('input');
    }

    // Show/hide screens
    function showScreen(screenName) {
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });

        const screen = document.getElementById(`screen-${screenName}`);
        if (screen) {
            screen.classList.add('active');
        }

        state.currentScreen = screenName;
    }

    // Show/hide loading
    function showLoading(show) {
        const loading = document.getElementById('loading');
        if (loading) {
            if (show) {
                loading.classList.remove('hidden');
            } else {
                loading.classList.add('hidden');
            }
        }
    }

    // Simple Korean transliteration
    function transliterateToKorean(text) {
        const map = {
            'A': '아', 'B': '비', 'C': '씨', 'D': '디', 'E': '이',
            'F': '에프', 'G': '지', 'H': '에이치', 'I': '아이', 'J': '제이',
            'K': '케이', 'L': '엘', 'M': '엠', 'N': '엔', 'O': '오',
            'P': '피', 'Q': '큐', 'R': '알', 'S': '에스', 'T': '티',
            'U': '유', 'V': '브이', 'W': '더블유', 'X': '엑스', 'Y': '와이', 'Z': '제트'
        };

        // Special handling for common names
        const specialNames = {
            'WILSON': '윌슨',
            'SMITH': '스미스',
            'JOHN': '존',
            'MARY': '메리',
            'JAMES': '제임스',
            'DAVID': '데이비드',
            'MICHAEL': '마이클'
        };

        const upper = text.toUpperCase();
        if (specialNames[upper]) {
            return specialNames[upper];
        }

        // Basic transliteration
        let result = '';
        for (let char of upper) {
            result += map[char] || char;
        }
        return result;
    }

    // Start app when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();