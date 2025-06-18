/* Copyright 2020 The TensorFlow Authors. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
==============================================================================*/
#include "esp_wifi.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include <string.h>

#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/system_setup.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "main_functions.h"
#include "model_a.h"  
#include "model_b.h"
#include "model_c.h"
#include "constants.h"
#include "centroid_utils.h"
#include "uart_sender.h"

// Globals, used for compatibility with Arduino-style sketches.
namespace {
const char* TAG = "BEACON_SCANNER";

Point* pos_network_a = new Point{300.0f, 0.0f};
Point* pos_network_b = new Point{-300.0f, 0.0f};
Point* pos_network_c = new Point{0.0f, 300.0f};

const tflite::Model* model_a = nullptr;
const tflite::Model* model_b = nullptr;
const tflite::Model* model_c = nullptr;
tflite::MicroInterpreter* interpreter_a = nullptr;
tflite::MicroInterpreter* interpreter_b = nullptr;
tflite::MicroInterpreter* interpreter_c = nullptr;
TfLiteTensor* input_a = nullptr;
TfLiteTensor* input_b = nullptr;
TfLiteTensor* input_c = nullptr;
TfLiteTensor* output_a = nullptr;
TfLiteTensor* output_b = nullptr;
TfLiteTensor* output_c = nullptr;

constexpr int kTensorArenaSize = 2000;
uint8_t tensor_arena[kTensorArenaSize];
}  // namespace

void init_wifi_sta_only() {
  ESP_LOGI(TAG, "Initializing WiFi in STA mode...");

  esp_netif_init();
  esp_event_loop_create_default();
  esp_netif_create_default_wifi_sta();

  wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
  ESP_ERROR_CHECK(esp_wifi_init(&cfg));

  wifi_config_t wifi_config = {}; // no connection needed
  ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
  ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
  ESP_ERROR_CHECK(esp_wifi_start());

  ESP_LOGI(TAG, "WiFi STA mode initialized.");
}


// The name of this function is important for Arduino compatibility.
void setup() {
  esp_log_level_set("wifi", ESP_LOG_ERROR);
  esp_err_t ret = nvs_flash_init();
  if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
      ESP_ERROR_CHECK(nvs_flash_erase());         // Erase NVS if corrupted or full
      ret = nvs_flash_init();                     // Try again
  }
  ESP_ERROR_CHECK(ret);

  init_wifi_sta_only();

  init_uart();
  send_test();

  // Map the model into a usable data structure. This doesn't involve any
  // copying or parsing, it's a very lightweight operation.
  model_a = tflite::GetModel(model_a_tflite);
  model_b = tflite::GetModel(model_b_tflite);
  model_c = tflite::GetModel(model_c_tflite);
  if (model_a->version() != TFLITE_SCHEMA_VERSION ||
      model_b->version() != TFLITE_SCHEMA_VERSION ||
      model_c->version() != TFLITE_SCHEMA_VERSION) {
    MicroPrintf("Model schema version mismatch.");
    return;
  }

  // Pull in only the operation implementations we need.
  static tflite::MicroMutableOpResolver<2> resolver;
  if (resolver.AddFullyConnected() != kTfLiteOk) {
    return;
  }
  if (resolver.AddRelu() != kTfLiteOk) {
    return;
  }

  // Build an interpreter to run the model with.
  static tflite::MicroInterpreter static_interpreter_a(
      model_a, resolver, tensor_arena, kTensorArenaSize);
  interpreter_a = &static_interpreter_a;

  static tflite::MicroInterpreter static_interpreter_b(
    model_b, resolver, tensor_arena, kTensorArenaSize);
  interpreter_b = &static_interpreter_b;

  static tflite::MicroInterpreter static_interpreter_c(
    model_c, resolver, tensor_arena, kTensorArenaSize);
  interpreter_c = &static_interpreter_c;

  // Allocate memory from the tensor_arena for the model's tensors.
  if (interpreter_a->AllocateTensors() != kTfLiteOk ||
      interpreter_b->AllocateTensors() != kTfLiteOk ||
      interpreter_c->AllocateTensors() != kTfLiteOk) {
    MicroPrintf("Tensor allocation failed");
    return;
  }

  // Obtain pointers to the model's input and output tensors.
  input_a = interpreter_a->input(0); output_a = interpreter_a->output(0);
  input_b = interpreter_b->input(0); output_b = interpreter_b->output(0);
  input_c = interpreter_c->input(0); output_c = interpreter_c->output(0);
}

float inference(tflite::MicroInterpreter* interpreter, float x, TfLiteTensor* input, TfLiteTensor* output) {
  input->data.f[0] = x;

  // Run inference, and report any error
  if (interpreter->Invoke() != kTfLiteOk) {
    MicroPrintf("Invoke failed on x: %f\n",
                         static_cast<double>(x));
    return 0.0f;
  }

  float y = pow(10, output_a->data.f[0]);

  return y;
}

std::string serialize_beacons(Point pos_a, Point pos_b, Point pos_c) {
  std::string data;
  if (pos_a.x != 0.0f && pos_a.y != 0.0f) 
    data += "Beacon A: (" + std::to_string(pos_a.x) + ", " + std::to_string(pos_a.y) + ")\n";
  if (pos_b.x != 0.0f && pos_b.y != 0.0f) 
    data += "Beacon B: (" + std::to_string(pos_b.x) + ", " + std::to_string(pos_b.y) + ")\n";
  if (pos_c.x != 0.0f && pos_c.y != 0.0f) 
    data += "Beacon C: (" + std::to_string(pos_c.x) + ", " + std::to_string(pos_c.y) + ")\n";
  return data;
}

// The name of this function is important for Arduino compatibility.
void loop() {
  wifi_scan_config_t scan_config = {};
  scan_config.ssid = 0;
  scan_config.bssid = 0;
  scan_config.channel = 0;
  scan_config.show_hidden = false;
  scan_config.scan_type = WIFI_SCAN_TYPE_ACTIVE;
  scan_config.scan_time.active.min = 100;
  scan_config.scan_time.active.max = 300;

  // Start Wi-Fi scan (blocking)
  ESP_ERROR_CHECK(esp_wifi_scan_start(&scan_config, true));

  // Get the number of found access points
  uint16_t ap_count = 0;
  ESP_ERROR_CHECK(esp_wifi_scan_get_ap_num(&ap_count));
  if (ap_count == 0) {
      ESP_LOGI(TAG, "No access points found.");
      return;
  }

  // Dynamically allocate space for AP records
  wifi_ap_record_t* ap_records = (wifi_ap_record_t*)malloc(sizeof(wifi_ap_record_t) * ap_count);
  if (ap_records == NULL) {
      ESP_LOGE(TAG, "Failed to allocate memory for AP records.");
      return;
  }

  // Get scan results
  ESP_ERROR_CHECK(esp_wifi_scan_get_ap_records(&ap_count, ap_records));

  float distance_a = 0;
  float distance_b = 0;
  float distance_c = 0;

  for (int i = 0; i < ap_count; ++i) {
    const char* ssid = (const char*)ap_records[i].ssid;
    float rssi = static_cast<float>(ap_records[i].rssi);

    if (strncmp(ssid, "BEACON-A", 8) == 0 && interpreter_a) {
        distance_a = inference(interpreter_a, rssi, input_a, output_a);
        ESP_LOGI(TAG, "Beacon A: RSSI=%.1f Result=%.4f", rssi, distance_a);
    } else if (strncmp(ssid, "BEACON-B", 8) == 0 && interpreter_b) {
        distance_b = inference(interpreter_b, rssi, input_b, output_b);
        ESP_LOGI(TAG, "Beacon B: RSSI=%.1f Result=%.4f", rssi, distance_b);
    } else if (strncmp(ssid, "BEACON-C", 8) == 0 && interpreter_c) {
        distance_c = inference(interpreter_c, rssi, input_c, output_c);
        ESP_LOGI(TAG, "Beacon C: RSSI=%.1f Result=%.4f", rssi, distance_c);
    }
  }

  std::vector<Point> beacon_positions = getBeaconPositions(
      pos_network_a, pos_network_b, pos_network_c,
      distance_a, distance_b, distance_c);

  std::string beacon_data = serialize_beacons(beacon_positions[0], 
                                              beacon_positions[1], 
                                              beacon_positions[2]);
  send_uart(beacon_data.c_str());

  free(ap_records); 

}
