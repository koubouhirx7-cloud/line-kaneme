import re

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

# We need the HTML <head> and <style>
head_match = re.search(r'<head>.*?</head>', content, re.DOTALL)
head_html = head_match.group(0) if head_match else ""

# We need the dashboard container (Step 2 & 3)
dash_match = re.search(r'<!-- =======================\s*\[STEP 2 & 3\].*?(<div\s+class="bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col relative w-\[400px\] h-\[650px\] border border-gray-200">.*?<!-- 矢印 -->)', content, re.DOTALL)

# Adjust the regex to capture the exact div. We can simply use string finding.
start_idx = content.find('<div\n                    class="bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col relative w-[400px] h-[650px] border border-gray-200">')

# Let's find the matching closing div for this container
if start_idx == -1:
    # Try another format
    start_idx = content.find('<div class="bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col relative w-[400px] h-[650px] border border-gray-200">')

if start_idx == -1:
    # Use generic search
    start_idx = content.find('<!-- グローバルヘッダー') - 150 # approximate

dashboard_html = ""
if start_idx != -1:
    div_count = 0
    for i in range(start_idx, len(content)):
        if content[i:i+4] == '<div':
            div_count += 1
        elif content[i:i+5] == '</div':
            div_count -= 1
            if div_count == 0:
                dashboard_html = content[start_idx:i+6]
                break

# We also need the script
script_match = re.search(r'<script>.*?</script>', content, re.DOTALL)
script_html = script_match.group(0) if script_match else ""

# Build admin.html
admin_html = f"""<!DOCTYPE html>
<html lang="ja">
{head_html}
<body class="bg-slate-50 min-h-screen flex items-center justify-center font-sans text-gray-800 p-0 md:p-4">
    <div class="w-full h-[100dvh] md:h-[700px] md:w-[450px] bg-white md:rounded-2xl shadow-2xl overflow-hidden flex flex-col relative border border-gray-200">
        {dashboard_html[dashboard_html.find('<!-- グローバルヘッダー'):] if '<!-- グローバルヘッダー' in dashboard_html else dashboard_html}
    </div>
    
{script_html}

<script>
    // Clean up unnecessary JS references to mock phones that no longer exist
    // Just override the error-prone functions or references if needed
    const _originalUpdatePartnerPhone = window.updatePartnerPhone;
    if(typeof updatePartnerPhone !== 'undefined') {{
        window.updatePartnerPhone = function() {{ }}; // disable partner mock update
    }}
    
    // Auto-fetch every 3 seconds
    setInterval(fetchInquiries, 3000);
</script>
</body>
</html>
"""

# Let's cleanly strip out the container's own classes if we grabbed them
# Actually, the div we created wraps it perfectly if we take inner contents.
admin_html = admin_html.replace('class="bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col relative w-[400px] h-[650px] border border-gray-200"', 'class="flex flex-col h-full w-full relative"')

with open("admin.html", "w", encoding="utf-8") as f:
    f.write(admin_html)

print("Generated admin.html successfully!")
