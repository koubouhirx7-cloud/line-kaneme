import re

with open('seamless_workflow_preview.html', 'r', encoding='utf-8') as f:
    content = f.read()

modal_html = """
    <!-- 設定モーダル -->
    <div id="settingsModal" class="fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center z-50">
        <div class="bg-white rounded-lg p-6 w-96 max-w-full shadow-2xl transform transition-all">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-bold text-gray-800">⚙️ 管理設定</h3>
                <button onclick="closeSettings()" class="text-gray-400 hover:text-gray-600 focus:outline-none">
                    <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
            
            <div class="space-y-4">
                <div class="border-b pb-4">
                    <h4 class="font-medium text-blue-600 mb-2">🏢 新規会社・グループ追加</h4>
                    <input type="text" id="newPartnerName" placeholder="会社名 (例: サンプル運送)" class="w-full border rounded p-2 mb-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none">
                    <input type="text" id="newPartnerLineId" placeholder="LINEグループ名 / ID (Cxxxx...)" class="w-full border rounded p-2 mb-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none">
                    <button onclick="addNewPartner()" class="w-full bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded transition-colors text-sm">
                        ＋ 会社を追加する
                    </button>
                </div>
            </div>
        </div>
    </div>
"""

# Insert modal HTML just before script tag or at end of body
content = content.replace("</body>", modal_html + "\n</body>")

# Replace gear icon to call openSettings()
gear_btn_pattern = r'(<button class="text-white hover:text-indigo-200">)(\s*<svg)'
content = re.sub(gear_btn_pattern, r'<button onclick="openSettings()" class="text-white hover:text-indigo-200">\2', content)

# Add JS functions
js_code = """
        // Settings Modal
        function openSettings() {
            document.getElementById('settingsModal').classList.remove('hidden');
            document.getElementById('settingsModal').classList.add('flex');
        }

        function closeSettings() {
            document.getElementById('settingsModal').classList.add('hidden');
            document.getElementById('settingsModal').classList.remove('flex');
        }

        async function addNewPartner() {
            const name = document.getElementById('newPartnerName').value;
            const lineId = document.getElementById('newPartnerLineId').value;
            
            if (!name) {
                alert("会社名を入力してください");
                return;
            }

            try {
                const response = await fetch('http://127.0.0.1:8000/api/partners', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, line_group_id: lineId })
                });

                if (response.ok) {
                    alert(`${name} を追加しました！`);
                    closeSettings();
                    fetchPartners(); // Refresh list
                    document.getElementById('newPartnerName').value = '';
                    document.getElementById('newPartnerLineId').value = '';
                } else {
                    alert('追加に失敗しました。');
                }
            } catch (error) {
                console.error('Error adding partner:', error);
                alert('通信エラーが発生しました。バックエンドが起動しているか確認してください。');
            }
        }
"""

content = content.replace("async function fetchPartners()", js_code + "\n\n        async function fetchPartners()")

with open('seamless_workflow_preview.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched settings modal into seamless_workflow_preview.html")
