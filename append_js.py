import os

filepath = 'static/js/app.js'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

index = content.rfind('});')
if index != -1:
    code = """
    window.handleRouteLineClick = function(route) {
        if (!optimizeResult || !optimizeResult.suggestions) return;
        const suggestion = optimizeResult.suggestions[window.currentAlgoIndex || 0];
        showRouteDetailsModal(route, suggestion.destination);
    };
"""
    new_content = content[:index] + code + content[index:]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Appended JS successfully")
else:
    print("Could not find });")
