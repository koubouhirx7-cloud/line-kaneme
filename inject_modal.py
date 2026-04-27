with open("admin.html", "r") as f:
    content = f.read()

modal_html = """
    <!-- Export Modal -->
    <div id="exportModal" class="fixed inset-0 bg-black/50 z-[60] hidden flex items-center justify-center backdrop-blur-sm transition-opacity opacity-0">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden transform scale-95 transition-all duration-300" id="exportModalContent">
            <div class="p-5 border-b flex justify-between items-center bg-gray-50">
                <h3 class="font-bold text-lg text-gray-800 flex items-center gap-2">
                    <svg class="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    PDFレポート出力
                </h3>
                <button onclick="closeExportModal()" class="text-gray-400 hover:text-gray-600 font-bold text-xl">×</button>
            </div>
            <div class="p-5 space-y-4">
                <div>
                    <label class="block text-xs font-bold text-gray-700 mb-1">出力タイプ</label>
                    <select id="exportType" onchange="updateExportOptions()" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none">
                        <option value="month">月間レポート (Monthly)</option>
                        <option value="week">週間レポート (Weekly)</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs font-bold text-gray-700 mb-1">対象期間</label>
                    <select id="exportPeriod" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none bg-gray-50">
                        <!-- Populated dynamically -->
                    </select>
                </div>
                <div class="text-[11px] text-gray-500 bg-blue-50 p-2.5 rounded border border-blue-100 leading-relaxed text-blue-800">
                    💡 「プレビュー作成」をクリックすると、別タブで印刷用の画面が開きます。そのままブラウザの印刷機能から<b>[PDFとして保存]</b>を行ってください。
                </div>
            </div>
            <div class="bg-gray-50 p-4 border-t flex gap-3">
                <button onclick="closeExportModal()" class="flex-1 bg-white border border-gray-300 text-gray-700 py-2.5 rounded-lg font-bold text-sm hover:bg-gray-50 shadow-sm transition">キャンセル</button>
                <button onclick="executeExport()" class="flex-1 bg-indigo-600 text-white py-2.5 rounded-lg font-bold text-sm hover:bg-indigo-700 shadow-md transition flex justify-center items-center gap-2">
                    プレビュー作成
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                </button>
            </div>
        </div>
    </div>
"""

modal_js = """
        function openExportModal() {
            document.getElementById('exportModal').classList.remove('hidden');
            setTimeout(() => {
                document.getElementById('exportModal').classList.remove('opacity-0');
                document.getElementById('exportModalContent').classList.replace('scale-95', 'scale-100');
            }, 10);
            updateExportOptions();
        }

        function closeExportModal() {
            document.getElementById('exportModal').classList.add('opacity-0');
            document.getElementById('exportModalContent').classList.replace('scale-100', 'scale-95');
            setTimeout(() => document.getElementById('exportModal').classList.add('hidden'), 300);
        }

        function updateExportOptions() {
            const type = document.getElementById('exportType').value;
            const sel = document.getElementById('exportPeriod');
            sel.innerHTML = '';
            
            const inquiries = window.allInquiries.filter(i => i.status === 'completed');
            const groups = new Set();
            
            inquiries.forEach(req => {
                const updated = new Date(req.updated_at || req.created_at);
                if (type === 'month') {
                    groups.add(`${updated.getFullYear()}-${String(updated.getMonth() + 1).padStart(2, '0')}`);
                } else if (type === 'week') {
                    // simple week start
                    const firstDayOfYear = new Date(updated.getFullYear(), 0, 1);
                    const pastDaysOfYear = (updated - firstDayOfYear) / 86400000;
                    const weekNum = Math.ceil((pastDaysOfYear + firstDayOfYear.getDay() + 1) / 7);
                    groups.add(`${updated.getFullYear()}-W${String(weekNum).padStart(2, '0')}`);
                }
            });
            
            if (groups.size === 0) {
                sel.innerHTML = '<option value="">完了済みデータなし</option>';
                return;
            }
            
            Array.from(groups).sort().reverse().forEach(g => {
                const opt = document.createElement('option');
                opt.value = g;
                if(type === 'month') {
                    const [y, m] = g.split('-');
                    opt.textContent = `${y}年${parseInt(m)}月度`;
                } else {
                    const [y, w] = g.split('-W');
                    opt.textContent = `${y}年 第${parseInt(w)}週`;
                }
                sel.appendChild(opt);
            });
        }
        
        function executeExport() {
            const type = document.getElementById('exportType').value;
            const val = document.getElementById('exportPeriod').value;
            if(!val) return;
            
            let start, end;
            if(type === 'month') {
                const [y, m] = val.split('-');
                start = `${y}-${m}-01T00:00:00Z`;
                const lastDay = new Date(y, m, 0).getDate();
                end = `${y}-${m}-${lastDay}T23:59:59Z`;
            } else if (type === 'week') {
                const [y, wStr] = val.split('-W');
                const w = parseInt(wStr);
                const simple = new Date(y, 0, 1 + (w - 1) * 7);
                const dow = simple.getDay();
                const ISOweekStart = simple;
                if (dow <= 4)
                    ISOweekStart.setDate(simple.getDate() - simple.getDay() + 1);
                else
                    ISOweekStart.setDate(simple.getDate() + 8 - simple.getDay());
                    
                const isoEnd = new Date(ISOweekStart);
                isoEnd.setDate(isoEnd.getDate() + 6);
                
                start = `${ISOweekStart.toISOString().split('T')[0]}T00:00:00Z`;
                end = `${isoEnd.toISOString().split('T')[0]}T23:59:59Z`;
            }
            
            window.open('/report.html?start=' + encodeURIComponent(start) + '&end=' + encodeURIComponent(end) + '&title=' + encodeURIComponent(val) + '&type=' + type, '_blank');
            closeExportModal();
        }
"""

if "id=\"exportModal\"" not in content:
    content = content.replace("<script>", modal_html + "\n<script>\n" + modal_js)
    with open("admin.html", "w") as f:
        f.write(content)
