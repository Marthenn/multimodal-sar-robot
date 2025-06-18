#ifndef UART_SENDER_H
#define UART_SENDER_H

#include <string>

#ifdef __cplusplus
extern "C" {
#endif

// Initialize UART (optional if needed outside)
void init_uart();

// Send a message over UART
void send_uart(const std::string& message);

// Example function that sends a message with an incrementing counter
void send_test();

#ifdef __cplusplus
}
#endif

#endif // UART_SENDER_H
