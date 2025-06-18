
#
# Main component of TF Micro project 'micro_speech'.
#

idf_component_register(
    SRCS main.cc main_functions.cc constants.cc model_a.cc model_b.cc model_c.cc centroid_utils.cc uart_sender.cc
    PRIV_REQUIRES spi_flash
    REQUIRES nvs_flash esp_wifi esp_event driver
    INCLUDE_DIRS "")
