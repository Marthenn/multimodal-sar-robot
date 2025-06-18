#include <stdio.h>
#include <string>
#include <cstring>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_random.h"
#include <freertos/FreeRTOS.h>

#include "uart_sender.h"

#define UART_PORT UART_NUM_0
#define BUF_SIZE (1024)

namespace {
    const char* TAG = "UART_SENDER";
    int i = 0;
    bool uart_initialized = false;
}


void init_uart() {
    if (uart_initialized) return;

    uart_config_t uart_config = {
        .baud_rate = 115200,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE
    };

    uart_param_config(UART_PORT, &uart_config);
    uart_driver_install(UART_PORT, BUF_SIZE * 2, 0, 0, NULL, 0);
    uart_initialized = true;
    ESP_LOGI(TAG, "UART initialized");
}

void send_uart(const std::string& message) {
    init_uart();

    char uart_message[128];
    snprintf(uart_message, sizeof(uart_message), "%s\n", message.c_str());

    uart_write_bytes(UART_PORT, uart_message, strlen(uart_message));
    ESP_LOGI(TAG, "Sent: %s", uart_message);
}

void send_test() {
    std::string message = "Value of i: " + std::to_string(i++);
    send_uart(message);
}