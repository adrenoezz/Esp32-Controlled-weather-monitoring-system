import network
import socket
import dht
from machine import Pin, I2C
import time
import json
import urequests
from lcd import LCD

# ================= WIFI =================
ssid = "YOUR_SSID"
password = "YOUR_PASSWORD"

# ================= GAS SENSORS =================
mq5 = Pin(13, Pin.IN)
mq7 = Pin(14, Pin.IN)

# ================= LCD =================
i2c = I2C(0, scl=Pin(22), sda=Pin(21))
lcd = LCD(i2c, 0x27)
lcd.backlight_on()

# ================= WIFI CONNECT =================
wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(ssid, password)

print("Connecting to WiFi...")
while not wifi.isconnected():
    time.sleep(1)

print("Connected:", wifi.ifconfig())

# ================= DHT11 =================
sensor = dht.DHT11(Pin(5))

# ================= SERVER =================
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)

print("Server running...")

# ================= MAIN LOOP =================
while True:

    # ===== SENSOR READ =====
    try:
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()
    except:
        temp = 0
        hum = 0

    gas5 = mq5.value()
    gas7 = mq7.value()

    # ===== LCD DISPLAY =====
    mq5_status = "OK" if gas5 == 1 else "GA"
    mq7_status = "OK" if gas7 == 1 else "CO"

    lcd.cmd(0x01)
    time.sleep_ms(50)

    lcd.move(0, 0)
    lcd.print("T:{}C H:{}%".format(temp, hum))

    lcd.move(1, 0)
    lcd.print("M5:{} M7:{}".format(mq5_status, mq7_status))

    # ===== WAIT FOR CLIENT =====
    cl, addr = s.accept()
    request = cl.recv(1024).decode('utf-8', 'ignore')

    # ===== API DATA =====
    if '/data' in request:

        data = json.dumps({
            "temp": temp,
            "hum": hum,
            "mq5": gas5,
            "mq7": gas7
        })

        cl.send(b'HTTP/1.1 200 OK\r\n')
        cl.send(b'Content-Type: application/json\r\n\r\n')
        cl.send(data.encode())

    # ===== DASHBOARD PAGE =====
    else:

        html = """
        <html>
        <head>
        <meta charset="UTF-8">
        <title>ESP32 Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <style>
        body{
            font-family: Arial;
            text-align:center;
            background:#0f172a;
            color:white;
        }

        .card{
            background:#1e293b;
            padding:20px;
            margin:20px auto;
            width:320px;
            border-radius:15px;
        }

        canvas{
            max-width:90%%;
            background:white;
            border-radius:10px;
            padding:10px;
        }
        </style>
        </head>

        <body>

        <h1>ESP32 Dashboard</h1>

        <div class="card">
            <h2>🌡 Temp: <span id="temp">--</span> °C</h2>
            <h2>💧 Hum: <span id="hum">--</span> %%</h2>
            <h2>🔥 MQ5: <span id="mq5">--</span></h2>
            <h2>🔥 MQ7: <span id="mq7">--</span></h2>
        </div>

        <canvas id="chart"></canvas>

        <script>

        let labels = [];
        let tempData = [];
        let mq5Data = [];
        let mq7Data = [];

        const ctx = document.getElementById('chart').getContext('2d');

        const chart = new Chart(ctx,{
            type:'line',
            data:{
                labels:labels,
                datasets:[
                    {
                        label:'Temp',
                        data:tempData,
                        borderColor:'cyan',
                        fill:false
                    },
                    {
                        label:'MQ5',
                        data:mq5Data,
                        borderColor:'red',
                        fill:false
                    },
                    {
                        label:'MQ7',
                        data:mq7Data,
                        borderColor:'yellow',
                        fill:false
                    }
                ]
            }
        });

        async function fetchData(){

            let res = await fetch('/data');
            let data = await res.json();

            document.getElementById('temp').innerText = data.temp;
            document.getElementById('hum').innerText = data.hum;
            document.getElementById('mq5').innerText = data.mq5;
            document.getElementById('mq7').innerText = data.mq7;

            let t = new Date().toLocaleTimeString();

            labels.push(t);
            tempData.push(data.temp);
            mq5Data.push(data.mq5);
            mq7Data.push(data.mq7);

            if(labels.length > 10){
                labels.shift();
                tempData.shift();
                mq5Data.shift();
                mq7Data.shift();
            }

            chart.update();
        }

        setInterval(fetchData,2000);
        fetchData();

        </script>
        </body>
        </html>
        """

        cl.send(b'HTTP/1.1 200 OK\r\n')
        cl.send(b'Content-Type: text/html\r\n\r\n')
        cl.send(html.encode())

    cl.close()
