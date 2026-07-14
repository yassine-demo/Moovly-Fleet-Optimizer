import re

with open('c:/Users/yassine/Desktop/test_modéles/Test 2/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('</title>', '</title>\n    <script src="https://unpkg.com/@phosphor-icons/web"></script>')

replacements = {
    '👤': '<i class="ph ph-users"></i>',
    '📄': '<i class="ph ph-file-xls"></i>',
    '📌': '<i class="ph ph-map-pin-plus"></i>',
    '📍': '<i class="ph ph-map-pin"></i>',
    '📥': '<i class="ph ph-download-simple"></i>',
    '🚀': '<i class="ph ph-rocket-launch"></i>',
    '🛣️': '<i class="ph ph-path"></i>',
    '🗺️': '<i class="ph ph-map-trifold"></i>',
    '🌍': '<i class="ph ph-globe-hemisphere-west"></i>',
    '⚖️': '<i class="ph ph-scales"></i>',
    '📊': '<i class="ph ph-chart-bar"></i>',
    '🌿': '<i class="ph ph-leaf"></i>',
    '💰': '<i class="ph ph-coins"></i>',
    '📏': '<i class="ph ph-ruler"></i>',
    '📦': '<i class="ph ph-package"></i>',
    '📅': '<i class="ph ph-calendar-blank"></i>',
    '🌳': '<i class="ph ph-tree"></i>',
    '🚗': '<i class="ph ph-car"></i>',
    '📋': '<i class="ph ph-clipboard-text"></i>',
    '⏳': '<i class="ph ph-hourglass-high"></i>',
    '▶': '<i class="ph ph-play-circle"></i>',
    '←': '<i class="ph ph-arrow-left"></i>',
    '🌿': '<i class="ph ph-leaf"></i>'
}

for emoji, icon in replacements.items():
    content = content.replace(emoji, icon)

with open('c:/Users/yassine/Desktop/test_modéles/Test 2/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Emojis replaced in index.html')
