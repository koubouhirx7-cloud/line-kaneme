import re

html_path = 'seamless_workflow_preview.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace partnerList div (hardcoded ones)
pattern_partner_settings = r'<div id="partnerList" class="space-y-2">.*?</div>\n\n                            <!-- 追加フォーム -->'
replacement_partner_settings = '''<div id="partnerList" class="space-y-2">
                                    <div class="text-center py-4 text-gray-400 text-xs">協力会社を取得中...</div>
                                </div>

                            <!-- 追加フォーム -->'''
content = re.sub(pattern_partner_settings, replacement_partner_settings, content, flags=re.DOTALL)

# Find <script> index and replace script content
script_start = content.find('<script>')
script_end = content.find('</script>') + len('</script>')

new_script = """<script>
        const API_BASE = 'http://localhost:8000/api';
        
        // --- 状態管理・UI更新 ---
        let currentData = null; // Currently selected inquiry for dispatch
        let allPartners = [];
        let pollingInterval = null;

        document.addEventListener('DOMContentLoaded', () => {
            fetchPartners();
            fetchInquiries();
            // Start basic polling for inbox (every 10s)
            pollingInterval = setInterval(fetchInquiries, 10000);
        });

        // ==========================
        // Data Fetching
        // ==========================
        async function fetchPartners() {
            try {
                const res = await fetch(`${API_BASE}/partners`);
                allPartners = await res.json();
                renderSettingsPartners(allPartners);
                renderDispatchPartnerMenu(allPartners);
            } catch (err) {
                console.error("Failed to load partners", err);
            }
        }

        async function fetchInquiries() {
            try {
                const res = await fetch(`${API_BASE}/inquiries`);
                const inquiries = await res.json();
                renderInbox(inquiries);
            } catch (err) {
                console.error("Failed to load inquiries", err);
            }
        }

        // ==========================
        // UI Rendering Logic
        // ==========================
        function renderSettingsPartners(partners) {
            const list = document.getElementById('partnerList');
            if (partners.length === 0) {
                list.innerHTML = `<div class="text-center text-xs text-gray-400 py-2">協力会社が登録されていません</div>`;
                return;
            }
            let html = '';
            partners.forEach(p => {
                const line = p.line_group_id || '未設定';
                const emoji = p.icon_emoji || '🏢';
                html += `
                    <div class="bg-white p-2.5 rounded-lg border border-gray-100 shadow-sm flex justify-between items-center" id="p-item-${p.id}">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded bg-blue-50 text-blue-600 flex items-center justify-center text-sm">${emoji}</div>
                            <div>
                                <p class="font-bold text-xs">${p.name}</p>
                                <p class="text-[9px] text-gray-500">LINE: ${line}</p>
                            </div>
                        </div>
                        <button onclick="deletePartner(${p.id})" class="text-red-400 hover:text-red-600 hover:bg-red-50 p-1.5 rounded transition">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                        </button>
                    </div>
                `;
            });
            list.innerHTML = html;
        }

        function renderDispatchPartnerMenu(partners) {
            // Replace the hardcoded partner select menu in dispatch view
            const container = document.querySelector('#screen-dispatch .flex-1.p-3.overflow-y-auto');
            if (!container) return; // Prevent errors if DOM missing
            
            // Re-inject the list 
            const headerHTML = `<p class="text-[11px] text-gray-500 mb-2 font-bold">送出先の協力会社を選択</p>`;
            let pHTML = '';
            
            if(partners.length === 0) {
                pHTML = `<div class="text-center text-xs text-gray-400">協力会社を登録してください</div>`;
            } else {
                partners.forEach(p => {
                    const emoji = p.icon_emoji || '🏢';
                    const id = `partner-disp-${p.id}`;
                    
                    pHTML += `
                    <div class="bg-white border border-gray-200 rounded-lg overflow-hidden partner-card mb-3" id="card-${id}">
                        <button onclick="togglePartner('${id}')" class="w-full px-3 py-3 flex justify-between items-center bg-gray-50">
                            <div class="flex items-center gap-2">
                                <div class="w-8 h-8 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm">${emoji}</div>
                                <div class="text-left">
                                    <h4 class="font-bold text-sm">${p.name}</h4>
                                    <p class="text-[9px] text-gray-500">LINEへ連携</p>
                                </div>
                            </div>
                            <svg class="w-4 h-4 text-gray-400 transition-transform" id="arrow-${id}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                            </svg>
                        </button>
                        <div id="form-${id}" class="accordion-content bg-white px-3 border-t">
                            <p class="text-[10px] text-gray-500 mb-2 text-center bg-gray-50 p-1 rounded">※上の顧客データがLINEに送信されます</p>
                            <button onclick="sendToPartner(${p.id})" id="btn-send-partner-${p.id}" class="w-full bg-blue-600 text-white font-bold py-2 rounded shadow text-xs">
                                この会社へLINE送信
                            </button>
                        </div>
                    </div>
                    `;
                });
            }
            container.innerHTML = headerHTML + pHTML;
        }

        function renderInbox(inquiries) {
            const list = document.getElementById('inboxList');
            const unhandledCount = inquiries.filter(i => i.status === 'received').length;
            
            document.getElementById('emptyInbox')?.classList.toggle('hidden', inquiries.length > 0);
            document.getElementById('inbox-badge')?.classList.toggle('hidden', unhandledCount === 0);
            if(unhandledCount > 0) document.getElementById('inbox-badge').innerText = unhandledCount;
            
            let html = '';
            inquiries.forEach((req, idx) => {
                const isNew = idx === 0 && unhandledCount > 0 && req.status === 'received';
                const badge = req.status === 'completed' ? `<span class="bg-green-100 text-green-700 text-[10px] font-bold px-2 py-0.5 rounded mr-1">完了</span>` :
                              req.status === 'dispatched' ? `<span class="bg-yellow-100 text-yellow-700 text-[10px] font-bold px-2 py-0.5 rounded mr-1">手配中</span>` :
                              isNew ? `<span class="bg-red-100 text-red-700 text-[10px] font-bold px-2 py-0.5 rounded mr-1 animate-pulse">新着</span>` :
                              `<span class="bg-blue-100 text-blue-700 text-[10px] font-bold px-2 py-0.5 rounded mr-1">受付済</span>`;
                              
                const btnState = req.status === 'received' ? 
                    `<button onclick='goToDispatch(${JSON.stringify(req).replace(/'/g, "&apos;")})' class="w-full bg-indigo-600 text-white py-1.5 rounded text-xs font-bold hover:bg-indigo-700 transition shadow-sm mt-2">データを確認して協力会社の手配へ</button>` :
                    `<button disabled class="w-full bg-gray-300 text-gray-500 py-1.5 rounded text-xs font-bold transition shadow-sm mt-2 cursor-not-allowed">手配済み</button>`;

                html += `
                    <div class="bg-white ${req.status==='received' ? 'border-l-4 border-blue-500' : 'border border-gray-200'} rounded-lg shadow-sm p-3 mb-3 ${isNew ? 'new-request-anim' : ''}">
                        <div class="flex justify-between border-b pb-1 mb-2">
                            <span class="font-bold text-sm text-gray-800">${req.customer_name} 様</span>
                            <div>${badge}</div>
                        </div>
                        <p class="text-[10px] text-gray-500 truncate mb-1">引取: ${req.pickup_location}</p>
                        <p class="text-[10px] text-gray-500 truncate mb-2">納品: ${req.delivery_location}</p>
                        <p class="text-[11px] text-gray-600 truncate mb-2 bg-gray-50 p-1 rounded">内容: ${req.detail}</p>
                        ${btnState}
                    </div>
                `;
            });
            list.innerHTML = html || `<div class="text-center py-10 text-gray-400 text-sm" id="emptyInbox">顧客からのお問い合わせを待機中...</div>`;
        }

        function updateProgress(step) {
            for (let i = 1; i <= 4; i++) {
                const circle = document.getElementById(`circle-${i}`);
                const text = document.getElementById(`text-${i}`);
                const line = document.getElementById(`line-${i}`);

                if (i < step) {
                    circle.className = "w-8 h-8 rounded-full border-2 flex items-center justify-center font-bold text-sm step-done transition-colors duration-300";
                    circle.innerHTML = "✓";
                    text.className = "ml-2 text-sm font-bold text-emerald-600";
                    if (line) line.classList.replace('bg-gray-200', 'bg-emerald-500');
                } else if (i === step) {
                    circle.className = "w-8 h-8 rounded-full border-2 flex items-center justify-center font-bold text-sm step-active transition-colors duration-300";
                    circle.innerHTML = i;
                    text.className = "ml-2 text-sm font-bold text-blue-600";
                    if (line) line.classList.replace('bg-emerald-500', 'bg-gray-200');
                } else {
                    circle.className = "w-8 h-8 rounded-full border-2 flex items-center justify-center font-bold text-sm step-inactive transition-colors duration-300";
                    circle.innerHTML = i;
                    text.className = "ml-2 text-sm font-bold text-gray-400";
                    if (line) line.classList.replace('bg-emerald-500', 'bg-gray-200');
                }
            }

            if (step === 2) {
                document.getElementById('badge-step-2').classList.replace('opacity-50', 'text-yellow-300');
                document.getElementById('badge-step-3').classList.replace('text-yellow-300', 'opacity-50');
            } else if (step === 3) {
                document.getElementById('badge-step-2').classList.replace('text-yellow-300', 'opacity-50');
                document.getElementById('badge-step-3').classList.replace('opacity-50', 'text-yellow-300');
            } else if (step === 4) {
                const arrow = document.getElementById('arrow-to-partner');
                if (arrow) arrow.classList.replace('text-gray-300', 'text-blue-500');
                const pZone = document.getElementById('partner-zone');
                if (pZone) pZone.classList.remove('opacity-50', 'pointer-events-none');
                const b4 = document.getElementById('badge-step-4');
                if (b4) b4.classList.replace('bg-gray-400', 'bg-[#06C755]');
            }
        }

        function switchTab(tabName) {
            const tabs = ['inbox', 'dispatch'];
            tabs.forEach(t => {
                const btn = document.getElementById(`tab-${t}`);
                const screen = document.getElementById(`screen-${t}`);

                if (t === tabName) {
                    btn.classList.replace('text-gray-400', 'text-blue-600');
                    btn.classList.replace('border-transparent', 'border-blue-600');
                    btn.classList.add('bg-blue-50');
                    screen.classList.remove('screen-hidden');
                    setTimeout(() => screen.classList.remove('opacity-0'), 20);
                } else {
                    btn.classList.replace('text-blue-600', 'text-gray-400');
                    btn.classList.replace('border-blue-600', 'border-transparent');
                    btn.classList.remove('bg-blue-50');
                    screen.classList.add('opacity-0');
                    setTimeout(() => {
                        if (btn.classList.contains('text-gray-400')) screen.classList.add('screen-hidden');
                    }, 400); 
                }
            });
            if (tabName === 'inbox') document.getElementById('inbox-badge')?.classList.add('hidden');
        }

        // ==========================
        // LIFF Form
        // ==========================
        function openLiff() {
            document.getElementById('liffModal').classList.add('open');
        }
        function closeLiff() {
            document.getElementById('liffModal').classList.remove('open');
        }

        async function submitLiff(event) {
            event.preventDefault();
            const btn = document.getElementById('btn-submit-liff');
            btn.innerText = "送信中...";
            btn.disabled = true;

            const payload = {
                customer_name: document.getElementById('df-name').value,
                phone_number: document.getElementById('df-phone').value,
                pickup_location: document.getElementById('df-from').value,
                delivery_location: document.getElementById('df-to').value,
                detail: document.getElementById('df-detail').value
            };

            try {
                const res = await fetch(`${API_BASE}/inquiries`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!res.ok) throw new Error("LIFF submission failed");
                const inquiry = await res.json();

                closeLiff();
                btn.innerText = "問い合わせを送信";
                btn.disabled = false;

                const chat = document.getElementById('customerChat');
                chat.insertAdjacentHTML('beforeend', `
                    <div class="flex mb-4 mt-2">
                        <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold mr-2 text-xs shrink-0">要</div>
                        <div class="chat-bubble left bg-white rounded-xl rounded-tl-sm shadow-md p-3 text-xs">
                            お問い合わせありがとうございます。確認次第手配を進めます！<br>
                            <span class="text-gray-400 text-[10px]">受付番号: ${inquiry.id}</span>
                        </div>
                    </div>
                `);
                chat.scrollTop = chat.scrollHeight;

                updateProgress(2);
                await fetchInquiries();

            } catch (err) {
                console.error(err);
                alert("送信に失敗しました");
                btn.innerText = "問い合わせを送信";
                btn.disabled = false;
            }
        }

        // ==========================
        // Dispatch Flow
        // ==========================
        function goToDispatch(inquiry) {
            updateProgress(3);
            currentData = inquiry;

            document.getElementById('pass-name').innerText = inquiry.customer_name;
            document.getElementById('pass-phone').innerText = inquiry.phone_number;
            document.getElementById('pass-detail').innerText = `引取: ${inquiry.pickup_location}\\n納品: ${inquiry.delivery_location}\\n詳細: ${inquiry.detail}`;

            switchTab('dispatch');
            document.getElementById('dispatch-empty').classList.add('hidden');
            document.getElementById('dispatch-content').classList.remove('hidden');
            
            // Re-render partners menu to ensure reset state
            renderDispatchPartnerMenu(allPartners);
            
            document.getElementById('dashStatus').innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-gray-300" id="statusDot"></span>
                    <span>ステータス: <span class="font-bold" id="statusText">待機中</span></span>
                </div>
            `;
        }

        let currentActivePartnerId = null;
        function togglePartner(id) {
            if (currentActivePartnerId && currentActivePartnerId !== id) {
                const oldContent = document.getElementById(`form-${currentActivePartnerId}`);
                if (oldContent) {
                    oldContent.classList.remove('open');
                    document.getElementById(`arrow-${currentActivePartnerId}`).classList.remove('rotate-180');
                    document.getElementById(`card-${currentActivePartnerId}`).classList.remove('active');
                }
            }
            document.getElementById(`form-${id}`).classList.toggle('open');
            document.getElementById(`arrow-${id}`).classList.toggle('rotate-180');
            document.getElementById(`card-${id}`).classList.toggle('active');
            currentActivePartnerId = document.getElementById(`form-${id}`).classList.contains('open') ? id : null;
        }

        async function sendToPartner(partnerId) {
            if (!currentData) return;
            
            const btn = document.getElementById(`btn-send-partner-${partnerId}`);
            btn.innerHTML = '送信中...';
            btn.disabled = true;

            try {
                const res = await fetch(`${API_BASE}/inquiries/${currentData.id}/dispatch`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ partner_id: partnerId })
                });
                if (!res.ok) throw new Error("Dispatch failed");

                btn.innerHTML = '✔ 送信完了';
                btn.classList.replace('bg-blue-600', 'bg-gray-400');

                document.getElementById('statusText').innerText = "協力会社へ連絡依頼済み（完了報告待ち）";
                document.getElementById('statusText').classList.add('text-blue-600');
                document.getElementById('statusDot').classList.replace('bg-gray-300', 'bg-blue-500');
                document.getElementById('statusDot').classList.add('animate-pulse');

                updateProgress(4);
                fetchInquiries(); // Background update inbox

                document.getElementById('partnerEmpty').classList.add('hidden');
                
                // Show message on Partner side
                const chat = document.getElementById('partnerChat');
                const msgHTML = `
                    <div class="flex mb-4 mt-2 opacity-0 translate-y-4 transition-all duration-300" id="incoming-${currentData.id}">
                        <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold mr-2 text-xs shrink-0 shadow-md">要</div>
                        <div class="chat-bubble left bg-white rounded-xl rounded-tl-sm shadow-md p-3 text-sm w-full">
                            <div class="bg-blue-600 text-white px-2 py-1 text-[10px] font-bold mb-2 rounded flex-wrap gap-1">
                                📞 お客様への連絡依頼
                            </div>
                            <p class="text-[11px] font-bold mb-1">${currentData.customer_name}</p>
                            <p class="text-blue-600 text-[11px] font-bold mb-2">☎️ ${currentData.phone_number}</p>
                            <div class="text-[10px] text-gray-600 bg-gray-50 p-1.5 rounded mb-3 border border-gray-100">
                                引取: ${currentData.pickup_location}<br>
                                納品: ${currentData.delivery_location}<br>
                                ${currentData.detail}
                            </div>
                            <button onclick="reportDone(this, '${currentData.id}', 'partner-disp-${partnerId}')" class="w-full bg-[#06C755] hover:bg-green-600 text-white font-bold py-2 rounded shadow text-xs transition">
                                連絡完了として報告
                            </button>
                        </div>
                    </div>
                `;
                chat.insertAdjacentHTML('beforeend', msgHTML);
                chat.scrollTop = chat.scrollHeight;

                setTimeout(() => {
                    const el = document.getElementById(`incoming-${currentData.id}`);
                    if (el) el.classList.remove('opacity-0', 'translate-y-4');
                }, 50);

            } catch (err) {
                console.error(err);
                alert("手配依頼の送信に失敗しました");
                btn.innerHTML = 'この会社へLINE送信';
                btn.disabled = false;
            }
        }

        async function reportDone(btn, inquiryId, cardId) {
            btn.innerHTML = "報告中...";
            btn.disabled = true;

            try {
                const res = await fetch(`${API_BASE}/inquiries/${inquiryId}/complete`, { method: 'POST' });
                if (!res.ok) throw new Error("Complete failed");

                btn.innerHTML = "✔ 報告済み";
                btn.className = "w-full bg-gray-200 text-gray-500 font-bold py-2 rounded shadow-inner text-xs cursor-not-allowed";

                const chat = document.getElementById('partnerChat');
                chat.insertAdjacentHTML('beforeend', `
                    <div class="flex flex-row-reverse mb-3 mt-1 opacity-0 translate-y-4 transition-all duration-300" id="done-${Date.now()}">
                        <div class="chat-bubble right bg-[#06C755] text-white rounded-xl rounded-tr-sm p-2 shadow-sm text-xs max-w-[80%]">
                            お客様への連絡、完了しました！
                        </div>
                    </div>
                `);
                chat.scrollTop = chat.scrollHeight;

                setTimeout(() => {
                    chat.lastElementChild.classList.remove('opacity-0', 'translate-y-4');
                }, 50);

                // Update Dash
                document.getElementById('statusText').innerText = "✅ 連絡完了の報告を受け取りました";
                document.getElementById('statusText').classList.replace('text-blue-600', 'text-green-600');
                document.getElementById('statusDot').classList.replace('bg-blue-500', 'bg-green-500');
                document.getElementById('statusDot').classList.remove('animate-pulse');
                document.getElementById(`card-${cardId}`)?.classList.add('border-green-400', 'bg-green-50');

                for (let i = 1; i <= 4; i++) {
                    const circle = document.getElementById(`circle-${i}`);
                    const text = document.getElementById(`text-${i}`);
                    circle.className = "w-8 h-8 rounded-full border-2 flex items-center justify-center font-bold text-sm step-done transition-colors duration-300";
                    circle.innerHTML = "✓";
                    text.className = "ml-2 text-sm font-bold text-emerald-600";
                }
                
                fetchInquiries(); // Refetch to mark inbox item as completed if they go back

            } catch (err) {
                console.error(err);
                alert("完了報告に失敗しました");
                btn.innerHTML = '連絡完了として報告';
                btn.disabled = false;
            }
        }

        // ==========================
        // Settings / Custom Partner
        // ==========================
        function openSettings() {
            document.getElementById('settingsPanel').classList.remove('translate-y-full');
        }
        function closeSettings() {
            document.getElementById('settingsPanel').classList.add('translate-y-full');
            document.getElementById('addAlert').classList.add('hidden');
        }

        async function addPartner() {
            const nameInput = document.getElementById('newPartnerName');
            const lineInput = document.getElementById('newPartnerLine');
            const name = nameInput.value.trim();
            const line = lineInput.value.trim();
            const alertEl = document.getElementById('addAlert');

            if (!name) {
                alertEl.classList.remove('hidden');
                return;
            }
            alertEl.classList.add('hidden');
            
            const btn = event.target;
            btn.innerHTML = '追加中...';
            btn.disabled = true;

            try {
                const res = await fetch(`${API_BASE}/partners`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, line_group_id: line, icon_emoji: '🆕' })
                });
                if (!res.ok) throw new Error("Add partner failed");
                nameInput.value = '';
                lineInput.value = '';
                await fetchPartners();
            } catch (err) {
                console.error(err);
                alert("協力会社の追加に失敗しました。");
            } finally {
                btn.innerHTML = '＋ 追加する';
                btn.disabled = false;
            }
        }

        async function deletePartner(id) {
            if (confirm('この協力会社を削除しますか？')) {
                const el = document.getElementById(`p-item-${id}`);
                if (el) {
                    el.classList.add('opacity-0', 'scale-95', 'transition-all', 'duration-300');
                    setTimeout(() => el.remove(), 300);
                }
                try {
                    await fetch(`${API_BASE}/partners/${id}`, { method: 'DELETE' });
                    // Refresh data behind the scenes
                    const res = await fetch(`${API_BASE}/partners`);
                    allPartners = await res.json();
                    renderDispatchPartnerMenu(allPartners);
                } catch (err) {
                    console.error("Delete failed", err);
                }
            }
        }
    </script>"""

new_content = content[:script_start] + new_script + content[script_end:]
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Rewrote seamless_workflow_preview.html with live API integration.")
