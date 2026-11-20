#include <WiFi.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include <DHT.h>

// WiFi
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";

// HiveMQ MQTT
const char* MQTT_SERVER = "broker.hivemq.com";
const int   MQTT_PORT   = 1883;
const char* TOPIC_DATA  = "invernadero/datos";
const char* TOPIC_CTRL  = "invernadero/control";

// ThingsBoard MQTT
const char* TB_SERVER = "thingsboard.cloud";
const int   TB_PORT   = 1883;
const char* TB_TOKEN  = "TU_THINGSBOARD_TOKEN";
const char* TB_TOPIC_TELEMETRY = "v1/devices/me/telemetry";
const char* TB_TOPIC_RPC_REQ   = "v1/devices/me/rpc/request/+";

// InfluxDB
const char* INFLUX_URL   = "https://us-east-1-1.aws.cloud2.influxdata.com/api/v2/write?org=universidad&bucket=invernadero&precision=s";
const char* INFLUX_TOKEN = "TU_INFLUXDB_TOKEN";

// Pines
#define DHTPIN 4
#define DHTTYPE DHT22
const int PIN_POT = 36;
const int PIN_LED = 13;

// Tiempos de envio y reconexion
const unsigned long INTERVALO_MS = 5000;
const unsigned long REINTENTO_MQTT_MS = 2000;

unsigned long ultimoEnvio = 0;
unsigned long ultimoIntentoHive = 0;
unsigned long ultimoIntentoTB = 0;

DHT dht(DHTPIN, DHTTYPE);
WiFiClient wifiHive;
WiFiClient wifiTB;

PubSubClient mqttHive(wifiHive);
PubSubClient mqttTB(wifiTB);

void setLed(bool encender, const char* fuente) {
  digitalWrite(PIN_LED, encender ? HIGH : LOW);
  Serial.print("LED [");
  Serial.print(fuente);
  Serial.print("]: ");
  Serial.println(encender ? "ON" : "OFF");
}

void onHiveMessage(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }
  msg.trim();
  msg.toUpperCase();

  Serial.print("HiveMQ [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(msg);

  if (String(topic) == TOPIC_CTRL) {
    if (msg == "ON" || msg == "1" || msg == "ENCENDER") {
      setLed(true, "HiveMQ");
    } else if (msg == "OFF" || msg == "0" || msg == "APAGAR") {
      setLed(false, "HiveMQ");
    }
  }
}

void onTbMessage(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }

  Serial.print("ThingsBoard [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(msg);

  if (String(topic).startsWith("v1/devices/me/rpc/request/")) {
    String clean = msg;
    clean.replace(" ", "");
    clean.toLowerCase();

    if (clean.indexOf("\"params\":true") != -1 ||
        clean.indexOf("\"params\":1") != -1 ||
        clean.indexOf("\"params\":\"on\"") != -1 ||
        clean.indexOf("\"params\":\"1\"") != -1) {
      setLed(true, "ThingsBoard");
    } else if (clean.indexOf("\"params\":false") != -1 ||
               clean.indexOf("\"params\":0") != -1 ||
               clean.indexOf("\"params\":\"off\"") != -1 ||
               clean.indexOf("\"params\":\"0\"") != -1) {
      setLed(false, "ThingsBoard");
    }
  }
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("Conectando a WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConectado. IP: " + WiFi.localIP().toString());
}

void checkMqtt() {
  if (WiFi.status() != WL_CONNECTED) return;
  unsigned long now = millis();

  if (!mqttHive.connected() && (now - ultimoIntentoHive >= REINTENTO_MQTT_MS)) {
    ultimoIntentoHive = now;
    String clientId = "esp32-hive-" + String(random(1000, 9999));
    Serial.print("Conectando a HiveMQ... ");
    if (mqttHive.connect(clientId.c_str())) {
      Serial.println("ok");
      mqttHive.subscribe(TOPIC_CTRL);
    } else {
      Serial.print("error ");
      Serial.println(mqttHive.state());
    }
  }

  if (!mqttTB.connected() && (now - ultimoIntentoTB >= REINTENTO_MQTT_MS)) {
    ultimoIntentoTB = now;
    String clientId = "esp32-tb-" + String(random(1000, 9999));
    Serial.print("Conectando a ThingsBoard... ");
    if (mqttTB.connect(clientId.c_str(), TB_TOKEN, "")) {
      Serial.println("ok");
      mqttTB.subscribe(TB_TOPIC_RPC_REQ);
    } else {
      Serial.print("error ");
      Serial.println(mqttTB.state());
    }
  }
}

void sendInflux(float temp, float hum, int humSuelo) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(INFLUX_URL);
  http.addHeader("Authorization", String("Token ") + INFLUX_TOKEN);
  http.addHeader("Content-Type", "text/plain; charset=utf-8");

  String body = "invernadero temperatura=" + String(temp, 2) +
                ",humedad=" + String(hum, 2) +
                ",humedad_suelo=" + String(humSuelo);

  int code = http.POST(body);
  Serial.print("InfluxDB HTTP: ");
  Serial.println(code);
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  pinMode(PIN_POT, INPUT);

  dht.begin();
  connectWiFi();

  mqttHive.setServer(MQTT_SERVER, MQTT_PORT);
  mqttHive.setCallback(onHiveMessage);

  mqttTB.setServer(TB_SERVER, TB_PORT);
  mqttTB.setCallback(onTbMessage);

  checkMqtt();
}

void loop() {
  connectWiFi();
  checkMqtt();

  if (mqttHive.connected()) mqttHive.loop();
  if (mqttTB.connected()) mqttTB.loop();

  unsigned long now = millis();
  if (now - ultimoEnvio >= INTERVALO_MS) {
    ultimoEnvio = now;

    float temp = dht.readTemperature();
    float hum = dht.readHumidity();
    int rawPot = analogRead(PIN_POT);
    int humSuelo = map(rawPot, 0, 4095, 0, 100);

    if (isnan(temp) || isnan(hum)) {
      Serial.println("Fallo en lectura del DHT22");
      return;
    }

    String payload = "{\"temperatura\":" + String(temp, 2) +
                     ",\"humedad\":" + String(hum, 2) +
                     ",\"humedad_suelo\":" + String(humSuelo) +
                     ",\"pot_raw\":" + String(rawPot) + "}";

    if (mqttHive.connected()) {
      mqttHive.publish(TOPIC_DATA, payload.c_str());
      Serial.println("HiveMQ -> " + payload);
    }

    if (mqttTB.connected()) {
      mqttTB.publish(TB_TOPIC_TELEMETRY, payload.c_str());
      Serial.println("ThingsBoard -> " + payload);
    }

    sendInflux(temp, hum, humSuelo);
  }
}