// 当前登录的维修工信息
let currentEngineer = null;
const LOGIN_STORAGE_KEY = 'mdispatch_engineer_login';

// 从localStorage恢复登录状态
function restoreLoginState() {
    const saved = localStorage.getItem(LOGIN_STORAGE_KEY);
    if (saved) {
        try {
            currentEngineer = JSON.parse(saved);
            return true;
        } catch (e) {
            localStorage.removeItem(LOGIN_STORAGE_KEY);
        }
    }
    return false;
}

// 保存登录状态到localStorage
function saveLoginState() {
    if (currentEngineer) {
        localStorage.setItem(LOGIN_STORAGE_KEY, JSON.stringify(currentEngineer));
    }
}

// 登录函数
async function handleLogin() {
    const phone = document.getElementById('loginPhone').value.trim();
    const password = document.getElementById('loginPassword').value.trim();
    
    if (!phone || !password) {
        document.getElementById('loginError').textContent = '请输入账号和密码';
        document.getElementById('loginError').classList.add('show');
        return;
    }
    
    try {
        const res = await fetch('/api/engineer/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, password })
        });
        
        const data = await res.json();
        
        if (data.status === 'success') {
            currentEngineer = data.data;
            saveLoginState();
            document.getElementById('loginError').classList.remove('show');
            // 隐藏登录页，显示主应用
            document.getElementById('loginPage').style.display = 'none';
            document.getElementById('mainApp').style.display = 'block';
            // 初始化页面
            initPageUi();
            loadProfile();
            loadOrders();
            startUpload();
        } else {
            document.getElementById('loginError').textContent = data.message || '登录失败，请检查账号密码';
            document.getElementById('loginError').classList.add('show');
        }
    } catch (error) {
        document.getElementById('loginError').textContent = '网络错误，请稍后重试';
        document.getElementById('loginError').classList.add('show');
    }
}

// 退出登录函数
function handleLogout() {
    if (confirm('确定要退出登录吗？')) {
        currentEngineer = null;
        localStorage.removeItem(LOGIN_STORAGE_KEY);
        document.getElementById('mainApp').style.display = 'none';
        document.getElementById('loginPage').style.display = 'flex';
        document.getElementById('loginPhone').value = '';
        document.getElementById('loginPassword').value = '';
        document.getElementById('loginError').classList.remove('show');
    }
}

// 页面加载时检查是否有保存的登录状态
document.addEventListener('DOMContentLoaded', function() {
    // 检查是否有保存的登录状态
    if (restoreLoginState() && currentEngineer) {
        // 恢复登录状态，显示主应用
        document.getElementById('loginPage').style.display = 'none';
        document.getElementById('mainApp').style.display = 'block';
        initPageUi();
        loadProfile();
        loadOrders();
        startUpload();
    } else {
        // 显示登录页面
        document.getElementById('loginPage').style.display = 'flex';
        document.getElementById('mainApp').style.display = 'none';
    }
});

function initPageUi() {
    document.getElementById("hdrTitle").textContent = "维修工工作台";
    document.getElementById("hdrSub").textContent = "工单处理 · 我的信息";
    document.getElementById("navMine").textContent = "我的";
    document.getElementById("navOrders").textContent = "工单";
    document.getElementById("statsTitle").textContent = "工单状态概览";
    document.getElementById("detailTitle").textContent = "工单信息";

    if (false) document.getElementById("registerCard_removed").innerHTML = `
        <div class="card-title">
            基础信息
            <button type="button" class="btn btn-sm btn-outline" id="btnEditProfile" onclick="startProfileEdit()">修改</button>
        </div>
        <div id="profileView"><div class="empty" style="padding:16px 0">加载中…</div></div>
        <div id="profileEdit" class="hidden">
            <label class="form-label">维修工ID</label>
            <input id="engineerId" placeholder="维修工ID" value="ENG_REAL_001">
            <label class="form-label">姓名</label>
            <input id="name" placeholder="姓名" value="张师傅">
            <label class="form-label">联系电话</label>
            <input id="phone" placeholder="联系电话" value="13812345678">
            <label class="form-label">登录密码</label>
            <input id="password" type="password" placeholder="登录密码" value="123456">
            <label class="form-label">技能品牌</label>
            <input id="skillBrand" placeholder="技能品牌" value="奥的斯">
            <label class="form-label">技能型号</label>
            <input id="skillModel" placeholder="技能型号" value="GEN2">
            <label class="form-label">工作状态</label>
            <select id="workStatus">
                <option value="空闲">空闲</option>
                <option value="忙碌">忙碌</option>
                <option value="休假">休假</option>
            </select>
            <div class="form-actions">
                <button type="button" class="btn btn-outline" onclick="cancelProfileEdit()">取消</button>
                <button type="button" class="btn btn-primary" onclick="registerEngineer()">保存</button>
            </div>
        </div>
    `;

    document.getElementById("gpsCard").innerHTML = `
        <div class="card-title">实时定位</div>
        <p style="font-size:13px;color:var(--muted);margin-bottom:8px;">派单依赖 GPS，请保持空闲并上传定位</p>
        <button class="btn btn-success" onclick="startUpload()">开始上传定位</button>
        <p id="gpsStatus" style="font-size:13px;margin-top:10px;color:var(--muted)">未上传</p>
    `;

    const filters = ["全部", "待处理", "已接单", "已完成"];
    document.getElementById("filterBar").innerHTML = filters.map((f, i) =>
        `<button class="chip${i === 0 ? " active" : ""}" data-filter="${f}">${f}</button>`
    ).join("");
}

const STORAGE_KEY = "mdispatch_engineer_id";
let allTasks = [];
let currentFilter = "全部";
let uploadTimer = null;
let selectedTask = null;
let cachedEngineerProfile = null;
let profileEditing = false;

function showToast(msg) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2200);
}

function getEngineerId() {
    // 使用当前登录的维修工ID
    if (currentEngineer) {
        return currentEngineer.engineer_id || currentEngineer["维修工ID"] || "";
    }
    const el = document.getElementById("engineerId");
    if (el) {
        return el.value.trim() || "";
    }
    return "";
}

function switchTab(tab) {
    document.getElementById("pageMine").classList.toggle("active", tab === "mine");
    document.getElementById("pageOrders").classList.toggle("active", tab === "orders");
    document.querySelectorAll(".nav-item").forEach(n => {
        n.classList.toggle("active", n.dataset.tab === tab);
    });
    if (tab === "orders") loadOrders();
    if (tab === "mine") {
        setProfileEditMode(false);
        loadProfile();
    }
}

function taskStatusClass(status) {
    if (status === "已完成") return "task-done";
    if (status === "已接单") return "task-accepted";
    return "task-pending";
}

function mapFilterStatus(taskStatus) {
    if (taskStatus === "待处理" || taskStatus === "已派单" || taskStatus === "未派单") return "待处理";
    if (taskStatus === "已接单" || taskStatus === "处理中") return "已接单";
    if (taskStatus === "已完成") return "已完成";
    return taskStatus;
}

function renderInfoRows(rows) {
    return rows.map(([label, value]) =>
        `<div class="info-row"><span class="label">${label}</span><span class="value">${value || "—"}</span></div>`
    ).join("");
}

function renderProgressBar(status, task = {}) {
    const steps = [
        { icon: "1", label: "用户报修" },
        { icon: "2", label: "系统派单" },
        { icon: "3", label: "维修工接单" },
        { icon: "4", label: "开始处理" },
        { icon: "5", label: "维修完成" },
    ];
    
    let currentStep = 0;
    let fillWidth = "0%";
    
    if (status === "已取消") {
        return '<div class="progress-bar"><div class="progress-title">维修进度</div><div style="text-align:center;color:#6b7280;font-size:13px;padding:8px;">工单已取消</div></div>';
    }
    
    if (status === "待处理") {
        currentStep = 1;
        fillWidth = "0%";
    } else if (status === "已派单") {
        currentStep = 2;
        fillWidth = "20%";
    } else if (status === "已接单") {
        currentStep = 3;
        fillWidth = "40%";
    } else if (status === "处理中") {
        currentStep = 4;
        fillWidth = "60%";
    } else if (status === "已完成") {
        currentStep = 5;
        fillWidth = "100%";
    }
    
    let html = '<div class="progress-bar"><div class="progress-title">维修进度</div><div class="progress-steps">';
    
    steps.forEach((step, index) => {
        const stepNum = index + 1;
        let className = "";
        if (stepNum < currentStep) {
            className = "completed";
        } else if (stepNum === currentStep) {
            className = "active";
        }
        html += `<div class="progress-step ${className}"><div class="icon">${step.icon}</div><div class="label">${step.label}</div></div>`;
    });
    
    html += `<div class="progress-fill" style="width:${fillWidth}"></div></div>`;
    
    if (status === "已接单" && task) {
        const distance = task["距离"] || "—";
        const eta = task["预计到达时间"] || "—";
        html += `<div style="margin-top:12px;padding:10px 12px;background:#f8fafc;border-radius:8px;">
            <div style="display:flex;justify-content:space-between;font-size:12px;">
                <span style="color:#64748b;">距离</span>
                <span style="font-weight:600;color:#1e40af;">${distance}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:12px;margin-top:6px;">
                <span style="color:#64748b;">预计到达</span>
                <span style="font-weight:600;color:#1e40af;">${eta}</span>
            </div>
        </div>`;
    }
    
    html += '</div>';
    return html;
}

function renderEngineerView(mgmt) {
    document.getElementById("profileView").innerHTML = renderInfoRows([
        ["维修工ID", mgmt["维修工ID"]],
        ["维修工姓名", mgmt["维修工姓名"]],
        ["联系电话", mgmt["联系电话"]],
        ["工作状态", mgmt["工作状态"]],
        ["技能品牌", mgmt["技能品牌"]],
        ["技能型号", mgmt["技能型号"]],
        ["地理位置", mgmt["地理位置"]],
        ["更新时间", mgmt["更新时间"]],
    ]);
}

function fillEngineerForm(mgmt) {
    if (!mgmt) return;
    document.getElementById("engineerId").value = mgmt["维修工ID"] || getEngineerId();
    document.getElementById("name").value = mgmt["维修工姓名"] || "";
    document.getElementById("phone").value = mgmt["联系电话"] || "";
    document.getElementById("skillBrand").value = mgmt["技能品牌"] || "";
    document.getElementById("skillModel").value = mgmt["技能型号"] || "";
    if (mgmt["工作状态"]) {
        document.getElementById("workStatus").value = mgmt["工作状态"];
    }
}

function setProfileEditMode(editing) {
    profileEditing = editing;
    const card = document.getElementById("profileCard");
    if (card) card.classList.toggle("is-editing", editing);
}

function startProfileEdit() {
    if (cachedEngineerProfile) {
        fillEngineerForm(cachedEngineerProfile);
    } else {
        document.getElementById("engineerId").value = getEngineerId();
    }
    setProfileEditMode(true);
}

function cancelProfileEdit() {
    if (cachedEngineerProfile) {
        fillEngineerForm(cachedEngineerProfile);
        renderEngineerView(cachedEngineerProfile);
    }
    setProfileEditMode(false);
}

async function registerEngineer() {
    const engineer_id = getEngineerId();
    const res = await fetch("/api/engineer/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            engineer_id,
            name: document.getElementById("name").value.trim(),
            phone: document.getElementById("phone").value.trim(),
            password: document.getElementById("password").value,
            skill_brand: document.getElementById("skillBrand").value.trim(),
            skill_model: document.getElementById("skillModel").value.trim(),
            status: document.getElementById("workStatus").value,
        }),
    });
    const json = await res.json();
    if (json.status !== "success") {
        showToast(json.message || "保存失败");
        return;
    }
    showToast("信息已保存");
    setProfileEditMode(false);
    loadProfile();
}

async function loadProfile() {
    const engineerId = getEngineerId();
    const res = await fetch(`/api/app/engineer/profile/${encodeURIComponent(engineerId)}`);
    const json = await res.json();

    if (json.status !== "success") {
        cachedEngineerProfile = null;
        document.getElementById("profileView").innerHTML =
            '<div class="empty" style="padding:16px 0">尚未登记基础信息，请点击「修改」填写</div>';
        const idEl = document.getElementById("engineerId");
        if (idEl) idEl.value = getEngineerId();
        if (!profileEditing) setProfileEditMode(false);
        document.getElementById("orderStats").innerHTML = `
        <div class="stat-item wait"><div class="num">0</div><div class="lbl">待处理</div></div>
        <div class="stat-item"><div class="num">0</div><div class="lbl">已接单</div></div>
        <div class="stat-item done"><div class="num">0</div><div class="lbl">已完成</div></div>`;
        return;
    }

    const mgmt = json.data["维修人员管理表"];
    const stats = json.data["工单统计"] || {};
    cachedEngineerProfile = mgmt;

    fillEngineerForm(mgmt);
    renderEngineerView(mgmt);
    if (!profileEditing) setProfileEditMode(false);

    document.getElementById("orderStats").innerHTML = `
        <div class="stat-item wait"><div class="num">${stats["待处理"] || 0}</div><div class="lbl">待处理</div></div>
        <div class="stat-item"><div class="num">${stats["已接单"] || 0}</div><div class="lbl">已接单</div></div>
        <div class="stat-item done"><div class="num">${stats["已完成"] || 0}</div><div class="lbl">已完成</div></div>
    `;
}

function startUpload() {
    document.getElementById("gpsStatus").textContent = "正在请求定位权限...";
    if (uploadTimer) clearInterval(uploadTimer);
    uploadLocation();
    uploadTimer = setInterval(uploadLocation, 5000);
}

let trackWebSocket = null;
let currentTrackOrderId = null;

function connectTrackWebSocket() {
    // 获取当前正在处理的工单
    const currentOrder = allTasks.find(t => t["任务状态"] === "已接单" || t["任务状态"] === "处理中");
    if (!currentOrder) {
        return;
    }
    
    currentTrackOrderId = currentOrder["工单 ID"];
    const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    const url = `${protocol}${window.location.host}/ws/track/${currentTrackOrderId}`;
    
    if (trackWebSocket) {
        trackWebSocket.close();
    }
    
    trackWebSocket = new WebSocket(url);
    
    trackWebSocket.onopen = function() {
        console.log("WebSocket 已连接，工单 ID:", currentTrackOrderId);
    };
    
    trackWebSocket.onclose = function() {
        trackWebSocket = null;
    };
    
    trackWebSocket.onerror = function(err) {
        console.error("WebSocket 错误:", err);
    };
}

function uploadLocation() {
    if (!navigator.geolocation) {
        document.getElementById("gpsStatus").textContent = "浏览器不支持定位";
        return;
    }
    navigator.geolocation.getCurrentPosition(async (pos) => {
        const res = await fetch("/api/engineer/location/update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                engineer_id: getEngineerId(),
                latitude: pos.coords.latitude,
                longitude: pos.coords.longitude,
                status: document.getElementById("workStatus").value,
            }),
        });
        const json = await res.json();
        if (json.status === "success") {
            document.getElementById("gpsStatus").textContent =
                `已上传：${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)}`;
            loadProfile();
            
            // 通过WebSocket推送位置给正在追踪的用户
            sendLocationToTrackers(pos.coords.latitude, pos.coords.longitude);
        } else {
            document.getElementById("gpsStatus").textContent = json.message || "上传失败";
        }
    }, (err) => {
        document.getElementById("gpsStatus").textContent = "定位失败：" + err.message;
    });
}

function sendLocationToTrackers(latitude, longitude) {
    // 使用当前追踪的工单 ID 推送位置
    if (currentTrackOrderId && trackWebSocket && trackWebSocket.readyState === WebSocket.OPEN) {
        trackWebSocket.send(JSON.stringify({
            type: "location_update",
            work_order_id: currentTrackOrderId,
            engineer_id: getEngineerId(),
            engineer_name: document.getElementById("name").value || "维修工",
            latitude,
            longitude,
        }));
    }
}

async function loadOrders() {
    const res = await fetch(`/api/app/engineer/orders?engineer_id=${encodeURIComponent(getEngineerId())}`);
    const json = await res.json();
    if (json.status !== "success") {
        document.getElementById("orderList").innerHTML =
            `<div class="empty">${json.message || "请先保存维修工信息"}</div>`;
        return;
    }
    allTasks = json.data || [];
    renderOrderList();
}

function renderOrderList() {
    let list;
    if (currentFilter === "全部") {
        list = allTasks;
    } else if (currentFilter === "已接单") {
        list = allTasks.filter(t => t["任务状态"] === "已接单" || t["任务状态"] === "处理中");
    } else {
        list = allTasks.filter(t => mapFilterStatus(t["任务状态"]) === currentFilter);
    }

    // 筛选待处理的报警工单
    const pendingAlarmOrders = list.filter(t => 
        (t["任务状态"] === "待处理" || t["任务状态"] === "已派单") && 
        t["工单类型"] === "报警"
    );

    // 按紧急程度排序，报警工单优先
    list.sort((a, b) => {
        // 报警工单优先
        const aIsAlarm = a["工单类型"] === "报警";
        const bIsAlarm = b["工单类型"] === "报警";
        if (aIsAlarm && !bIsAlarm) return -1;
        if (!aIsAlarm && bIsAlarm) return 1;
        
        // 紧急程度排序
        const urgencyOrder = { "紧急": 0, "较急": 1, "普通": 2 };
        const aUrgency = urgencyOrder[a["紧急程度"]] || 2;
        const bUrgency = urgencyOrder[b["紧急程度"]] || 2;
        return aUrgency - bUrgency;
    });

    if (list.length === 0) {
        document.getElementById("orderList").innerHTML = '<div class="empty">暂无工单</div>';
        return;
    }

    // 如果有待处理的报警工单，添加醒目提示
    let alarmAlert = "";
    if (pendingAlarmOrders.length > 0) {
        alarmAlert = `
        <div class="alarm-alert">
            <div class="alarm-icon">🚨</div>
            <div class="alarm-content">
                <div class="alarm-title">紧急报警工单</div>
                <div class="alarm-count">您有 ${pendingAlarmOrders.length} 个待处理的报警工单，请尽快处理！</div>
            </div>
        </div>`;
    }

    document.getElementById("orderList").innerHTML = alarmAlert + list.map(t => {
        const st = t["任务状态"];
        const urgency = t["紧急程度"] || "普通";
        const orderType = t["工单类型"] || "报修";
        const isAlarm = orderType === "报警";
        const urgencyClass = urgency === "紧急" ? "urgent" : (urgency === "较急" ? "" : "normal");
        const orderTypeIcon = isAlarm ? "🚨" : "🔧";
        
        return `
        <div class="order-card ${urgencyClass} ${isAlarm ? 'alarm' : ''}" data-order-id="${t["工单ID"]}" onclick="openDetailById(this.dataset.orderId)">
            <div class="head">
                <span class="order-type">${orderTypeIcon}</span>
                <span class="oid">${t["工单ID"]}</span>
                <span class="status-tag ${taskStatusClass(st)}">${st}</span>
            </div>
            <div class="meta">
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px;">
                    <span style="font-size:12px;color:#64748b;">${orderType}</span>
                    <span style="font-size:12px;color:#94a3b8;">·</span>
                    <span style="font-size:14px;font-weight:600;">${t["故障类型"] || "—"}</span>
                    <span class="urgency-badge ${urgency === '紧急' ? 'urgent' : ''}">${urgency}</span>
                </div>
                地址：${t["设备地址"] || "—"}<br>
                用户电话：${t["用户电话"] || "—"}
            </div>
        </div>`;
    }).join("");
}

document.getElementById("filterBar").addEventListener("click", e => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    document.querySelectorAll("#filterBar .chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    currentFilter = chip.dataset.filter;
    renderOrderList();
});

function openDetailById(orderId) {
    const task = allTasks.find(t => t["工单ID"] === orderId);
    if (task) openDetail(task);
}

function openDetail(task) {
    selectedTask = task;
    const st = task["任务状态"];
    const orderType = task["工单类型"] || "报修";
    const isAlarm = orderType === "报警";
    document.getElementById("detailTitle").innerHTML = isAlarm ? "🚨 " + orderType + "工单详情" : "🔧 " + orderType + "工单详情";
    document.getElementById("detailBody").innerHTML = renderInfoRows([
        ["工单ID", task["工单ID"]],
        ["工单类型", isAlarm ? '<span style="color:#dc2626;font-weight:600;">🚨 ' + orderType + '</span>' : '<span style="color:#3b82f6;font-weight:600;">🔧 ' + orderType + '</span>'],
        ["任务状态", task["任务状态"]],
        ["下单时间", task["下单时间"] || "—"],
        ["最后操作时间", task["最后操作时间"] || "—"],
        ["故障类型", task["故障类型"]],
        ["紧急程度", task["紧急程度"]],
        ["设备ID", task["设备ID"]],
        ["设备品牌", task["设备品牌"]],
        ["设备型号", task["设备型号"]],
        ["设备地址", task["设备地址"]],
        ["用户电话", task["用户电话"] || "—"],
        ["维修工通知", task["维修工通知"]],
    ]) + renderProgressBar(st, task);
    let actions = "";
    if (st === "待处理" || st === "已派单") {
        actions = `
            <button class="btn btn-primary" onclick="acceptOrder()">确认接单</button>
            <button class="btn btn-danger" onclick="rejectOrder()">拒绝接单</button>
        `;
    } else if (st === "已接单") {
        actions = '<button class="btn btn-primary" onclick="startOrder()">开始处理</button>';
    } else if (st === "处理中") {
        actions = '<button class="btn btn-success" onclick="completeOrder()">完成工单</button>';
    }
    document.getElementById("detailActions").innerHTML = actions;
    document.getElementById("detailModal").classList.add("show");
}

function closeDetail() {
    document.getElementById("detailModal").classList.remove("show");
    selectedTask = null;
}

function closeDetailIfMask(e) {
    if (e.target.id === "detailModal") closeDetail();
}

async function acceptOrder() {
    if (!selectedTask) return;
    const res = await fetch("/api/engineer/order/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            engineer_id: getEngineerId(),
            work_order_id: selectedTask["工单ID"],
        }),
    });
    const json = await res.json();
    showToast(json.message || "完成");
    closeDetail();
    loadProfile();
    loadOrders();
}

async function startOrder() {
    if (!selectedTask) return;
    const res = await fetch("/api/engineer/order/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            engineer_id: getEngineerId(),
            work_order_id: selectedTask["工单ID"],
        }),
    });
    const json = await res.json();
    showToast(json.message || "完成");
    closeDetail();
    loadProfile();
    loadOrders();
}

async function completeOrder() {
    if (!selectedTask) return;
    const res = await fetch("/api/engineer/order/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            engineer_id: getEngineerId(),
            work_order_id: selectedTask["工单ID"],
        }),
    });
    const json = await res.json();
    showToast(json.message || "完成");
    closeDetail();
    loadProfile();
    loadOrders();
}

async function rejectOrder() {
    if (!selectedTask) return;
    const reason = prompt("请输入拒绝原因：");
    if (!reason) return;

    const res = await fetch("/api/engineer/order/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            engineer_id: getEngineerId(),
            work_order_id: selectedTask["工单ID"],
            reason,
        }),
    });
    const json = await res.json();
    showToast(json.message || "已拒绝");
    closeDetail();
    loadProfile();
    loadOrders();
}

// 页面加载由登录成功后触发，此处不再自动加载
