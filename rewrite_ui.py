import re

html_path = 'ui_preview.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace partnerList div
pattern_partner = r'<div id="partnerList" class="space-y-4">.*?</div>\n\n            </div>'
replacement_partner = '''<div id="partnerList" class="space-y-4">
                    <div class="text-center text-gray-500 text-sm py-4" id="loadingPartners">
                        <svg class="animate-spin h-5 w-5 mx-auto mb-2 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        協力会社を読み込み中...
                    </div>
                </div>

            </div>'''

content = re.sub(pattern_partner, replacement_partner, content, flags=re.DOTALL)

# Find <script> index and replace script content
script_start = content.find('<script>')
script_end = content.find('</script>') + len('</script>')

new_script = """<script>
        const API_BASE = 'http://localhost:8000/api';
        let currentOpenId = null;
        let reminderTimeout = null;
        let isResponded = false;

        document.addEventListener('DOMContentLoaded', fetchPartners);

        async function fetchPartners() {
            try {
                const res = await fetch(`${API_BASE}/partners`);
                const partners = await res.json();
                renderPartners(partners);
            } catch (err) {
                console.error(err);
                document.getElementById('partnerList').innerHTML = `<div class="text-red-500 text-sm text-center py-4">協力会社の読み込みに失敗しました。サーバーが起動しているか確認してください。</div>`;
            }
        }

        function renderPartners(partners) {
            const list = document.getElementById('partnerList');
            list.innerHTML = '';
            
            if (partners.length === 0) {
                list.innerHTML = `<div class="text-gray-500 text-sm text-center py-4">登録されている協力会社がありません。</div>`;
                return;
            }

            partners.forEach(p => {
                const id = `partner_${p.id}`;
                const name = p.name;
                const emoji = p.icon_emoji || '🏢';
                const roleText = '登録スタッフ未設定'; // Mock data since it's not in DB yet

                const cardHTML = `
                    <div class="bg-white border text-left border-gray-200 rounded-lg shadow-sm overflow-hidden partner-card transition-all" id="card-${id}">
                        <button onclick="toggleAccordion('${id}', '${name}', ${p.id})" class="w-full px-4 py-4 flex justify-between items-center hover:bg-gray-50 transition">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-bold text-lg shadow-inner">
                                    ${emoji}
                                </div>
                                <div class="text-left">
                                    <h4 class="font-bold text-gray-800 text-base">${name}</h4>
                                    <p class="text-[11px] text-gray-500">${roleText}</p>
                                </div>
                            </div>
                            <div id="alert-${id}" class="hidden flex items-center gap-1 text-red-500 text-xs font-bold bg-red-50 px-2 py-1 rounded">
                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                                連絡未確認
                            </div>
                            <svg class="w-5 h-5 text-gray-400 transform transition-transform" id="arrow-${id}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </button>
                        
                        <div id="form-${id}" class="accordion-content bg-blue-50/50 px-5 border-t border-gray-100">
                            <form onsubmit="sendToLine(event, '${id}', '${name}', ${p.id})" class="space-y-3 pb-2">
                                <div>
                                    <label class="block text-xs font-bold text-gray-700 mb-1">顧客名</label>
                                    <input type="text" id="customer-${id}" required class="w-full text-sm border-gray-300 rounded-md p-2 border focus:ring-blue-500 focus:border-blue-500" placeholder="例: 株式会社テスト様">
                                </div>
                                <div class="grid grid-cols-2 gap-3">
                                    <div>
                                        <label class="block text-xs font-bold text-gray-700 mb-1">電話番号</label>
                                        <input type="text" id="phone-${id}" required class="w-full text-sm border-gray-300 rounded-md p-2 border focus:ring-blue-500 focus:border-blue-500" placeholder="03-1234-5678">
                                    </div>
                                    <div>
                                        <label class="block text-xs font-bold text-gray-700 mb-1">集荷先</label>
                                        <input type="text" id="pickup-${id}" class="w-full text-sm border-gray-300 rounded-md p-2 border focus:ring-blue-500 focus:border-blue-500" placeholder="例: 品川区">
                                    </div>
                                </div>
                                <div>
                                    <label class="block text-xs font-bold text-gray-700 mb-1">依頼内容</label>
                                    <input type="text" id="detail-${id}" required class="w-full text-sm border-gray-300 rounded-md p-2 border focus:ring-blue-500 focus:border-blue-500" placeholder="集荷時間の調整連絡をお願いします。">
                                </div>
                                <div class="pt-2">
                                    <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-xl shadow-lg flex justify-center items-center gap-2 transition">
                                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                                        連絡依頼を送信
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                `;
                list.insertAdjacentHTML('beforeend', cardHTML);
            });
        }

        function toggleAccordion(id, name, dbId) {
            document.getElementById('lineHeaderTitle').innerText = `📱 [${name}] グループ`;
            document.getElementById('lineHeaderSub').innerText = "配車担当者 他複数名";

            const content = document.getElementById(`form-${id}`);
            const arrow = document.getElementById(`arrow-${id}`);
            const card = document.getElementById(`card-${id}`);

            if (currentOpenId && currentOpenId !== id) {
                const oldContent = document.getElementById(`form-${currentOpenId}`);
                if (oldContent) {
                    oldContent.classList.remove('open');
                    document.getElementById(`arrow-${currentOpenId}`).classList.remove('rotate-180');
                    document.getElementById(`card-${currentOpenId}`).classList.remove('active');
                }
            }

            content.classList.toggle('open');
            arrow.classList.toggle('rotate-180');
            card.classList.toggle('active');

            if (content.classList.contains('open')) {
                const focusEl = document.getElementById(`customer-${id}`);
                if (focusEl) focusEl.focus();
            }

            currentOpenId = content.classList.contains('open') ? id : null;
        }

        async function sendToLine(event, formId, partnerName, dbId) {
            event.preventDefault();
            isResponded = false;

            const customerName = document.getElementById(`customer-${formId}`).value;
            const phone = document.getElementById(`phone-${formId}`).value;
            const pickup = document.getElementById(`pickup-${formId}`).value;
            const detail = document.getElementById(`detail-${formId}`).value;

            const btn = event.target.querySelector('button[type="submit"]');
            const originalHTML = btn.innerHTML;
            btn.innerHTML = '<span class="animate-pulse">送信中...</span>';
            btn.disabled = true;

            try {
                // 1. Create Inquiry
                const inquiryRes = await fetch(`${API_BASE}/inquiries`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        customer_name: customerName,
                        phone_number: phone,
                        pickup_location: pickup,
                        detail: detail
                    })
                });
                
                if (!inquiryRes.ok) throw new Error("Inquiry creation failed");
                const inquiryData = await inquiryRes.json();
                
                // 2. Dispatch Inquiry to Partner
                const dispatchRes = await fetch(`${API_BASE}/inquiries/${inquiryData.id}/dispatch`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ partner_id: dbId })
                });

                if (!dispatchRes.ok) throw new Error("Dispatch failed");

                // UI Updates after success
                btn.innerHTML = originalHTML;
                btn.disabled = false;
                toggleAccordion(formId, partnerName, dbId);

                document.getElementById(`card-${formId}`).style.borderColor = "#4ade80";
                setTimeout(() => { document.getElementById(`card-${formId}`).style.borderColor = ""; }, 1000);

                appendChatMessage(customerName, phone, detail, inquiryData.id, formId);

                document.getElementById('dashboardFooter').innerHTML = `
                    <span class="text-gray-400 font-normal text-xs">ステータス: </span><span class="text-blue-600 font-bold">先方へ連絡依頼済み（完了確認待ち: ${inquiryData.id}）</span>
                `;

                if (reminderTimeout) clearTimeout(reminderTimeout);
                reminderTimeout = setTimeout(() => {
                    if (!isResponded) {
                        sendReminder(customerName, formId);
                    }
                }, 10000); // 10 seconds for demo

            } catch (err) {
                console.error(err);
                alert("送信に失敗しました");
                btn.innerHTML = originalHTML;
                btn.disabled = false;
            }
        }

        function appendChatMessage(customerName, phone, detail, inquiryId, formId) {
            const chatContainer = document.getElementById('chatContainer');
            const messageId = Date.now();
            const timeStr = `${new Date().getHours()}:${String(new Date().getMinutes()).padStart(2, '0')}`;

            const msgHTML = `
                <div class="flex mb-5 opacity-0 transition-all duration-500 translate-y-4" id="msg-${messageId}">
                    <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold mr-2 text-xs shadow-md shrink-0 border border-white/20">要受付</div>
                    <div class="chat-bubble left bg-white rounded-xl rounded-tl-sm overflow-hidden max-w-[90%] shadow-md border border-gray-100">
                        <div class="bg-blue-600 text-white px-3 py-2 text-xs font-bold flex justify-between items-center">
                            <span>📞 お客様への連絡依頼</span>
                        </div>
                        <div class="p-3">
                            <p class="text-[12px] text-gray-600 mb-2 leading-relaxed">次のお客様へお電話していただき、内容の調整をお願いします。</p>
                            
                            <div class="bg-gray-50 border border-gray-100 rounded p-2 mb-3 text-[13px] shadow-inner">
                                <p class="font-bold text-gray-800 mb-1 border-b pb-1">${customerName}</p>
                                <p class="text-blue-600 font-bold mb-2">☎️ ${phone}</p>
                                <div class="text-xs text-gray-700 font-medium">
                                    👉 <span class="text-gray-500 font-normal">依頼内容:</span><br>
                                    ${detail}
                                </div>
                            </div>
                            
                            <p class="text-[10px] text-gray-400 mb-2 text-center">※お客様への連絡が終わりましたら、下のボタンを押して報告してください。</p>

                            <div class="flex" id="buttons-${messageId}">
                                <button onclick="markAsContacted(${messageId}, '${formId}', '${inquiryId}')" class="w-full bg-[#06C755] text-white font-bold py-3.5 rounded-xl text-sm hover:bg-green-600 transition shadow-lg border border-green-600 flex justify-center items-center gap-2">
                                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                    連絡完了として報告
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="text-[9px] text-white/80 self-end ml-1 mb-1 whitespace-nowrap">${timeStr}</div>
                </div>
            `;

            chatContainer.insertAdjacentHTML('beforeend', msgHTML);

            setTimeout(() => {
                const newMsg = document.getElementById(`msg-${messageId}`);
                newMsg.classList.remove('opacity-0', 'translate-y-4');
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }, 50);
        }

        async function markAsContacted(msgId, formId, inquiryId) {
            isResponded = true;
            if (reminderTimeout) clearTimeout(reminderTimeout);

            const btnGroup = document.getElementById(`buttons-${msgId}`);
            if (btnGroup) {
                const btn = btnGroup.querySelector('button');
                btn.innerHTML = '<span class="animate-pulse">報告中...</span>';
                btn.disabled = true;
            }

            try {
                // Call complete API
                const completeRes = await fetch(`${API_BASE}/inquiries/${inquiryId}/complete`, {
                    method: 'POST'
                });
                if (!completeRes.ok) throw new Error("Complete API failed");

                if (btnGroup) {
                    const btn = btnGroup.querySelector('button');
                    btn.innerHTML = '✔ 報告済み';
                    btn.className = 'w-full bg-gray-200 text-gray-500 font-bold py-3.5 rounded-xl text-sm transition shadow-inner border border-gray-300 cursor-not-allowed';
                }

                const chatContainer = document.getElementById('chatContainer');
                const timeStr = `${new Date().getHours()}:${String(new Date().getMinutes()).padStart(2, '0')}`;

                const replyHTML = `
                    <div class="flex flex-row-reverse mb-3 mt-1 opacity-0 transition-opacity duration-300" id="reply-${Date.now()}">
                        <div class="w-8 h-8 rounded-full bg-orange-400 flex items-center justify-center text-white font-bold ml-2 text-xs shadow-md shrink-0">担当者</div>
                        <div class="chat-bubble right bg-[#06C755] text-white rounded-xl rounded-tr-sm p-3 max-w-[70%] shadow-sm text-sm">
                            お客様への連絡、完了しました！
                        </div>
                        <div class="text-[9px] text-white/80 self-end mr-1 mb-1 text-right">既読1<br>${timeStr}</div>
                    </div>
                `;
                chatContainer.insertAdjacentHTML('beforeend', replyHTML);

                setTimeout(() => {
                    chatContainer.lastElementChild.classList.remove('opacity-0');
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }, 50);

                // UI update PC dashboard
                const alertEl = document.getElementById(`alert-${formId}`);
                if (alertEl) alertEl.classList.add('hidden');
                
                const cardEl = document.getElementById(`card-${formId}`);
                if (cardEl) {
                    cardEl.classList.remove('border-red-300', 'bg-red-50');
                    cardEl.classList.add('border-green-300', 'bg-green-50');
                    setTimeout(() => {
                        cardEl.classList.remove('border-green-300', 'bg-green-50');
                    }, 2000);
                }

                document.getElementById('dashboardFooter').innerHTML = `
                    <span class="text-gray-400 font-normal text-xs">ステータス: </span><span class="text-green-600 font-bold">✅ 連絡完了の報告を受け取りました！</span>
                `;

            } catch (err) {
                console.error(err);
                alert("完了報告に失敗しました。");
                if (btnGroup) {
                    const btn = btnGroup.querySelector('button');
                    btn.innerHTML = '連絡完了として報告';
                    btn.disabled = false;
                }
            }
        }

        function sendReminder(customerName, formId) {
            const chatContainer = document.getElementById('chatContainer');
            const timeStr = `${new Date().getHours()}:${String(new Date().getMinutes()).padStart(2, '0')}`;

            const reminderHTML = `
                <div class="flex mb-4 opacity-0 transition-all duration-500 translate-y-2" id="reminder-${Date.now()}">
                    <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold mr-2 text-xs shadow-md shrink-0 border border-white/20">要受付</div>
                    <div class="chat-bubble left bg-yellow-50 rounded-xl rounded-tl-sm overflow-hidden max-w-[85%] shadow-md border-l-4 border-yellow-500">
                        <div class="p-3">
                            <p class="font-bold text-yellow-700 text-xs mb-1">⚠️ [自動確認] 顧客への連絡はお済みでしょうか？</p>
                            <p class="text-[11px] text-gray-600">
                                お疲れ様です。先ほどご依頼した <strong>${customerName}</strong> 様への連絡について、まだ報告の確認がとれておりません。<br><br>
                                お忙しいところ恐縮ですが、連絡が完了しましたら元メッセージの「連絡完了として報告」ボタンを押してください！
                            </p>
                        </div>
                    </div>
                    <div class="text-[9px] text-white/80 self-end ml-1 mb-1 whitespace-nowrap">${timeStr}</div>
                </div>
            `;
            chatContainer.insertAdjacentHTML('beforeend', reminderHTML);

            setTimeout(() => {
                chatContainer.lastElementChild.classList.remove('opacity-0', 'translate-y-2');
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }, 50);

            const alertEl = document.getElementById(`alert-${formId}`);
            if (alertEl) alertEl.classList.remove('hidden');

            const cardEl = document.getElementById(`card-${formId}`);
            if (cardEl) cardEl.classList.add('border-red-300', 'bg-red-50');
        }

        // ==========================
        // 協力会社追加モーダルの処理 (Post API)
        // ==========================
        function openAddPartnerModal() {
            document.getElementById('addPartnerModal').classList.remove('hidden');
            document.getElementById('newPartnerName').focus();
        }

        function closeAddPartnerModal() {
            document.getElementById('addPartnerModal').classList.add('hidden');
            document.getElementById('newPartnerName').value = '';
            document.getElementById('newPartnerArea').value = '';
            document.getElementById('newPartnerStaff').value = '';
        }

        async function submitNewPartner(event) {
            event.preventDefault();
            const name = document.getElementById('newPartnerName').value;
            const area = document.getElementById('newPartnerArea').value;
            const btn = event.target.querySelector('button[type="submit"]');
            btn.innerHTML = '追加中...';
            btn.disabled = true;

            try {
                const res = await fetch(`${API_BASE}/partners`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: `${name} (${area})`,
                        icon_emoji: '🆕'
                    })
                });
                
                if (!res.ok) throw new Error("Failed to add partner");
                
                // Refresh partner list
                await fetchPartners();
                closeAddPartnerModal();

            } catch (err) {
                console.error(err);
                alert("追加に失敗しました");
            } finally {
                btn.innerHTML = '追加する';
                btn.disabled = false;
            }
        }
    </script>"""

new_content = content[:script_start] + new_script + content[script_end:]
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Rewrote ui_preview.html with API integration.")
