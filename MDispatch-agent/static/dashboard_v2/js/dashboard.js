/* ================= 时间 ================= */

function updateTime(){

    const now = new Date();

    document.getElementById(
        "currentTime"
    ).innerText =
        now.toLocaleString();
}

setInterval(updateTime,1000);

updateTime();

/* ================= 图表初始化 ================= */

const rankChart = echarts.init(
    document.getElementById("rankChart")
);

const orderChart = echarts.init(
    document.getElementById("orderChart")
);

const chinaMap = echarts.init(
    document.getElementById("chinaMap")
);

/* ================= 中国地图 ================= */


async function loadChinaMap(){

    const res = await fetch("./geo/china.json");
    const chinaJson = await res.json();

    echarts.registerMap("china", chinaJson);

    chinaMap.clear();

    chinaMap.setOption({

        tooltip:{
            trigger:"item",
            formatter:function(params){
                return params.name + "<br/>设备数量：" + (params.value || 0);
            }
        },

        visualMap:{
            show:true,
            min:0,
            max:300,
            left:20,
            bottom:30,
            text:["高","低"],
            textStyle:{color:"#fff"},
            inRange:{
                color:["#0b2c66","#1456a0","#1f8fff","#5bdcff"]
            }
        },

        series:[
            {
                name:"设备数量",
                type:"map",
                map:"china",
                roam:true,
                zoom:1.2,
                layoutCenter:["50%","55%"],
                layoutSize:"120%",

                label:{
                    show:true,
                    color:"#dff6ff",
                    fontSize:10
                },

                itemStyle:{
                    areaColor:"#0b3d91",
                    borderColor:"#00f7ff",
                    borderWidth:1.2,
                    shadowBlur:18,
                    shadowColor:"rgba(0,255,255,.35)"
                },

                emphasis:{
                    label:{color:"#fff"},
                    itemStyle:{
                        areaColor:"#1cc7ff",
                        shadowBlur:28,
                        shadowColor:"rgba(0,255,255,.75)"
                    }
                },

                data:window.dynamicProvinceData || []
            }
        ]
    });
}


loadChinaMap();

/* ================= 工单饼图 ================= */

function extractOrderLocations(orders){
    // 从工单中提取有经纬度的数据点
    const locations = [];

    for(const id in orders){
        const order = orders[id];
        const lat = order["latitude"] || order["维修工窗口"]?.["latitude"];
        const lon = order["longitude"] || order["维修工窗口"]?.["longitude"];

        if(lat && lon && lat > 20 && lat < 60 && lon > 100 && lon < 130){
            locations.push({
                name: order["维修工窗口"]?.["维修工姓名"] || "工单" + id.slice(-4),
                value: [lon, lat, Math.floor(Math.random() * 50) + 50]
            });
        }
    }

    // 如果没有真实数据，返回空
    if(locations.length === 0){
        return {
            scatter: [],
            lines: [],
            hasRealData: false
        };
    }

    // 生成飞线：从第一个城市到其他城市
    const lines = [];
    if(locations.length > 1){
        const center = locations[0];
        for(let i = 1; i < Math.min(locations.length, 5); i++){
            lines.push({ coords: [center.value.slice(0,2), locations[i].value.slice(0,2)] });
        }
    }

    return {
        scatter: locations.slice(0, 10),
        lines: lines,
        hasRealData: true
    };
}

function renderOrderChart(
    pending,
    processing,
    done
){
    orderChart.setOption({

        tooltip:{
            trigger:'item',
            formatter:function(params){
                return params.name + "<br/>数量：" + params.value;
            }
        },

        legend:{
            top:5,
            right:10,
            orient:'vertical',
            textStyle:{
                color:'#fff',
                fontSize:12
            },
            itemGap:8
        },

        series:[{

            type:'pie',

            radius:[
                '35%',
                '65%'
            ],

            center:['45%', '55%'],

            avoidLabelOverlap:false,

            label:{
                color:'#fff',
                fontSize:12,
                alignTo:'labelLine',
                minMargin:8
            },

            labelLine:{
                length:10,
                length2:5,
                lineStyle:{
                    color:'rgba(255,255,255,0.5)'
                }
            },

            itemStyle:{
                shadowBlur:15,
                shadowColor:'rgba(0,0,0,.4)'
            },

            data:[

                {
                    value:pending,
                    name:'待派单',
                    itemStyle:{ color: '#ef4444' }
                },

                {
                    value:processing,
                    name:'处理中',
                    itemStyle:{ color: '#f59e0b' }
                },

                {
                    value:done,
                    name:'已完成',
                    itemStyle:{ color: '#22c55e' }
                }

            ]
        }]
    });
}

/* ================= 排行 ================= */

function renderRankChart(
    names,
    values
){

    rankChart.setOption({

        grid:{
            left:80,
            right:30,
            top:20,
            bottom:20
        },

        xAxis:{
            type:'value',

            axisLine:{
                lineStyle:{
                    color:'#4cc9f0'
                }
            },

            splitLine:{
                lineStyle:{
                    color:
                        'rgba(255,255,255,.08)'
                }
            },

            axisLabel:{
                color:'#fff'
            }
        },

        yAxis:{
            type:'category',

            data:names,

            axisLine:{
                lineStyle:{
                    color:'#4cc9f0'
                }
            },

            axisLabel:{
                color:'#fff'
            }
        },

        series:[{

            type:'bar',

            data:values,

            barWidth:18,

            showBackground:true,

            backgroundStyle:{
                color:
                    'rgba(255,255,255,.05)'
            },

            itemStyle:{

                borderRadius:[0,8,8,0],

                color:new echarts.graphic.LinearGradient(
                    0,
                    0,
                    1,
                    0,
                    [
                        {
                            offset:0,
                            color:'#00c6ff'
                        },
                        {
                            offset:1,
                            color:'#0072ff'
                        }
                    ]
                )
            },

            label:{
                show:true,
                position:'right',
                color:'#fff'
            }

        }]
    });
}

/* ================= 主刷新 ================= */

async function refreshDashboard(){

    try{

        /* 工单 */
        const orderRes =
            await fetch(
                "/api/admin/orders"
            );

        const orderJson =
            await orderRes.json();

        const orders =
            orderJson.data || {};

        latestOrdersCache = orders;

        /* 维修工 */
        const engRes =
            await fetch(
                "/api/engineer/real/list"
            );

        const engJson =
            await engRes.json();

        const engineers =
            engJson.data || {};

        /* 用户 */
        const userRes =
            await fetch("/api/users");

        const userJson =
            await userRes.json();

        const users =
            userJson.data || {};

        /* 设备 */
        const deviceRes =
            await fetch("/api/devices");

        const deviceJson =
            await deviceRes.json();

        const devices =
            deviceJson.data || {};

        /* ================= 统计 ================= */

        let totalOrders = 0;

        let pending = 0;

        let processing = 0;

        let done = 0;

        for(const id in orders){

            totalOrders++;

            const order =
                orders[id];

            const status =
                order["内部维修工单表"]["工单状态"];

            if(
                status === "待人工派单"
            ){
                pending++;
            }

            else if(

                status === "已接单" ||

                status === "已派单" ||
                status === "处理中" ||
                status === "正在转派"

            ){
                processing++;
            }

            else if(
                status === "已完成"
            ){
                done++;
            }
        }

        /* ================= KPI 真实数据 ================= */

        // 安全运行天数：基于第一个工单创建时间计算
        let safeDays = 0;
        let earliestTime = null;
        for(const id in orders){
            const order = orders[id];
            const time = order["内部维修工单表"]["报修/报警时间"] || order["内部维修工单表"]["下单时间"];
            if(time){
                const t = new Date(time.replace(/-/g, "/"));
                if(!earliestTime || t < earliestTime){
                    earliestTime = t;
                }
            }
        }
        if(earliestTime){
            safeDays = Math.floor((new Date() - earliestTime) / (1000 * 60 * 60 * 24));
        }

        document.getElementById(
            "safe_days"
        ).innerText = Math.max(safeDays, 1);

        document.getElementById(
            "user_total"
        ).innerText =
            Object.keys(users).length;

        document.getElementById(
            "repair_total"
        ).innerText =
            Object.keys(engineers).length;

        // 在线设备数：设备状态为"正常"的数量
        let onlineDevices = 0;
        for(const id in devices){
            const device = devices[id];
            if(device["设备状态"] === "正常" || !device["设备状态"]){
                onlineDevices++;
            }
        }

        document.getElementById(
            "online_total"
        ).innerText = onlineDevices;

        document.getElementById(
            "total_devices"
        ).innerText =
            Object.keys(devices).length;



        /* ================= 地图动态数据 ================= */

        window.dynamicProvinceData =
            buildProvinceStats(orders, devices);

        loadChinaMap();

        /* ================= 饼图 ================= */

        renderOrderChart(
            pending,
            processing,
            done
        );

        /* ================= 排行 ================= */

        const countMap = {};

        for(const id in orders){

            const order =
                orders[id];

            const internal =
                order["内部维修工单表"];

            const task =
                order["维修工窗口"];

            const engId = task["维修工ID"];

            if(
                internal["工单状态"] === "已完成" &&
                engId &&
                engId !== "未分配" &&
                engId !== "暂未分配"
            ){

                const name =
                    task["维修工姓名"] ||
                    engineers[engId]?.["维修工姓名"] ||
                    "未知";

                countMap[engId] = countMap[engId] || { name, count: 0 };
                countMap[engId].count++;
            }
        }

        const sorted =

            Object.entries(countMap)

            .sort(
                (a,b)=>b[1].count-a[1].count
            )

            .slice(0,10);

        const names =
            sorted.map(i=>i[1].name);

        const values =
            sorted.map(i=>i[1].count);

        if(names.length === 0){

            names.push("暂无数据");

            values.push(0);
        }

        renderRankChart(
            names,
            values
        );

        /* ================= 生产商真实统计 ================= */

        // 从设备数据按品牌统计
        const manufacturerStats = {};

        for(const id in devices){
            const device = devices[id];
            const brand = device["品牌"] || "其他";

            if(!manufacturerStats[brand]){
                manufacturerStats[brand] = { device: 0, engineer: 0, online: 0 };
            }
            manufacturerStats[brand].device++;
            if(device["设备状态"] === "正常" || !device["设备状态"]){
                manufacturerStats[brand].online++;
            }
        }

        // 统计每个品牌的维修工数量
        for(const id in engineers){
            const e = engineers[id];
            const brand = e["技能品牌"] || e["品牌"] || "其他";

            if(!manufacturerStats[brand]){
                manufacturerStats[brand] = { device: 0, engineer: 0, online: 0 };
            }
            manufacturerStats[brand].engineer++;
        }

        const tbody = document.getElementById("manufacturerTable");
        tbody.innerHTML = "";

        for(const brand in manufacturerStats){
            const item = manufacturerStats[brand];

            tbody.innerHTML += `
                <tr>
                    <td>${brand}</td>
                    <td>${item.device}</td>
                    <td>${item.engineer}</td>
                    <td>${item.online}</td>
                </tr>
            `;
        }

        // 如果没有数据，显示提示
        if(Object.keys(manufacturerStats).length === 0){
            tbody.innerHTML = '<tr><td colspan="4" style="color:#888;">暂无数据</td></tr>';
        }

    }catch(err){

        console.log(
            "dashboard error:",
            err
        );
    }
}

/* ================= 启动 ================= */

refreshDashboard();

setInterval(
    refreshDashboard,
    5000
);

/* ================= 自适应 ================= */

window.addEventListener(
    "resize",
    ()=>{

        rankChart.resize();

        orderChart.resize();

        chinaMap.resize();
    }
);


/* ================= 省份设备统计 ================= */

function buildProvinceStats(orders, devices){

    const provinceMap = {};

    const provinceList = [
        '北京市', '天津市', '上海市', '重庆市',
        '河北省', '山西省', '辽宁省', '吉林省', '黑龙江省',
        '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省',
        '河南省', '湖北省', '湖南省', '广东省', '海南省',
        '四川省', '贵州省', '云南省', '陕西省', '甘肃省', '青海省', '台湾省',
        '内蒙古自治区', '广西壮族自治区', '西藏自治区', '宁夏回族自治区', '新疆维吾尔自治区',
        '香港特别行政区', '澳门特别行政区'
    ];

    provinceList.forEach(p=>{
        provinceMap[p] = 0;
    });

    // 从设备数据中提取省份信息
    for(const id in devices){
        const device = devices[id];
        const location = device["安装位置"] || device["地址"] || device["location"] || "";

        for(const province of provinceList){
            if(location.includes(province) || location.includes(province.replace(/省|市|自治区|特别行政区/g, ""))){
                provinceMap[province]++;
                break;
            }
        }
    }

    // 如果没有设备数据，从工单中统计
    if(Object.values(provinceMap).every(v => v === 0)){
        for(const id in orders){
            const order = orders[id];
            const userTable = order["用户端维修工单表"] || {};
            const location = JSON.stringify(userTable);

            for(const province of provinceList){
                if(location.includes(province)){
                    provinceMap[province]++;
                    break;
                }
            }
        }
    }

    const result = [];

    for(const p in provinceMap){
        if(provinceMap[p] > 0){
            result.push({
                name: p,
                value: provinceMap[p]
            });
        }
    }

    // 如果仍然没有数据，返回空数组（不显示假数据）
    return result;
}

/* ================= 地图点击联动 ================= */

let latestOrdersCache = {};
let latestDevicesCache = {};

function bindMapClick(){

    chinaMap.off("click");

    chinaMap.on("click", function(params){

        const province = params.name;
        let orderCount = 0;
        let deviceCount = params.value || 0;

        // 从工单中统计该省份的工单数
        for(const id in latestOrdersCache){
            const order = latestOrdersCache[id];
            const text = JSON.stringify(order);

            if(text.includes(province)){
                orderCount++;
            }
        }

        // 从设备中统计该省份的设备数
        if(latestDevicesCache && Object.keys(latestDevicesCache).length > 0){
            for(const id in latestDevicesCache){
                const device = latestDevicesCache[id];
                const location = device["安装位置"] || device["地址"] || device["location"] || "";

                if(location.includes(province)){
                    deviceCount++;
                }
            }
        }

        const info = document.getElementById("provinceInfo");

        if(info){
            info.innerText =
                "当前区域：" + province +
                "｜设备数量：" + deviceCount +
                "｜工单数量：" + orderCount;
        }
    });
}

// 保存设备数据供地图点击使用
const originalRefresh = refreshDashboard;
refreshDashboard = async function(){
    try{
        const result = await originalRefresh();

        // 获取设备数据供地图使用
        try{
            const deviceRes = await fetch("/api/devices");
            const deviceJson = await deviceRes.json();
            latestDevicesCache = deviceJson.data || {};
        }catch(e){}

        return result;
    }catch(e){}
};

setTimeout(bindMapClick, 1000);
setInterval(bindMapClick, 5000);
