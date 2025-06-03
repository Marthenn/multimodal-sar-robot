/*******************************************************************************
* Combined OpenCR code for controlling two XL430 wheels and one AX-18A pan servo
* via micro-ROS, using DynamixelSDK.
*
* - XL430 (ID 1, ID 2): Wheel mode, velocity controlled independently by:
* - /left_wheel_vel (std_msgs/Int32) - Raw Dynamixel Units
* - /right_wheel_vel (std_msgs/Int32) - Raw Dynamixel Units
* - AX-18A (ID 7): Position mode, angle controlled by /pan_angle (std_msgs/Int32) - Raw Dynamixel Units
*******************************************************************************/

#include <micro_ros_arduino.h>
#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>

#include <std_msgs/msg/int32.h> // For individual wheel velocities (raw DXL) and pan angle (raw DXL)

#include <DynamixelSDK.h>

//================================================================================
//== Robot & Servo Configuration
//================================================================================

// --- Servo IDs ---
#define DXL_ID_LEFT_WHEEL               1  // XL430
#define DXL_ID_RIGHT_WHEEL              2  // XL430
#define DXL_ID_PAN_SERVO                7  // AX-18A

// --- Protocol Version ---
#define PROTOCOL_VERSION_XL430          2.0
#define PROTOCOL_VERSION_AX18A          1.0

// --- Communication Settings ---
#define DXL_BAUDRATE                    1000000
#define DXL_DEVICENAME                  ""  // For OpenCR, "" defaults to Serial3 (DXL port)

// --- Control Table Addresses (XL430-W250, Protocol 2.0) ---
#define ADDR_XL430_TORQUE_ENABLE        64
#define ADDR_XL430_GOAL_VELOCITY        104
#define ADDR_XL430_OPERATING_MODE       11

// --- Control Table Addresses (AX-18A, Protocol 1.0) ---
#define ADDR_AX_TORQUE_ENABLE           24
#define ADDR_AX_GOAL_POSITION_L         30
#define ADDR_AX_MOVING_SPEED_L          32
#define ADDR_AX_CW_ANGLE_LIMIT_L        6
#define ADDR_AX_CCW_ANGLE_LIMIT_L       8

// --- Operating Modes & Torque ---
#define XL430_WHEEL_MODE                1 // Value for Wheel Mode (Velocity Control)
#define TORQUE_ENABLE                   1
#define TORQUE_DISABLE                  0

// Max velocity for XL430 (0.229 rpm units). Max RPM is ~61. So max value is ~265.
// Your topics send raw DXL units, so this limit applies to the incoming Int32 data.
#define MAX_DXL_WHEEL_VELOCITY          200

// --- Pan Servo Limits (AX-18A: 0-1023 for 0-300 degrees) ---
#define PAN_SERVO_MIN_POS_RAW           0      // Raw Dynamixel value for 0 degrees (e.g., "leftmost")
#define PAN_SERVO_MAX_POS_RAW           1023   // Raw Dynamixel value for 300 degrees (e.g., "rightmost")
#define PAN_SERVO_MIN_ANGLE_DEG         0.0f
#define PAN_SERVO_MAX_ANGLE_DEG         300.0f
#define PAN_SERVO_DEFAULT_SPEED_RAW     150    // Speed for pan servo (0-1023 for AX, 0=max speed, 1-1023 = proportional)
                                               // 150 is approx 17 RPM

//================================================================================
//== DynamixelSDK Objects
//================================================================================
dynamixel::PortHandler *portHandler;
dynamixel::PacketHandler *packetHandlerXL430; // For Protocol 2.0
dynamixel::PacketHandler *packetHandlerAX18A; // For Protocol 1.0

//================================================================================
//== Micro-ROS Objects
//================================================================================
rclc_support_t support;
rcl_allocator_t allocator;
rcl_node_t node;
rclc_executor_t executor;

// Subscribers
rcl_subscription_t left_wheel_vel_subscriber;
std_msgs__msg__Int32 left_wheel_vel_msg; // Receives raw DXL velocity units

rcl_subscription_t right_wheel_vel_subscriber;
std_msgs__msg__Int32 right_wheel_vel_msg; // Receives raw DXL velocity units

rcl_subscription_t pan_angle_subscriber;
std_msgs__msg__Int32 pan_angle_msg; // Receives raw DXL position units

//================================================================================
//== Dynamixel Control Functions
//================================================================================

/**
 * @brief Initializes a Dynamixel servo. Sets operating mode and enables torque.
 * Uses specific packet handlers directly based on protocol_version.
 */
bool init_dynamixel(uint8_t dxl_id, float protocol_version, uint8_t operating_mode_xl430_or_dummy) {
  uint8_t dxl_error = 0;
  int dxl_comm_result = COMM_TX_FAIL;

  if (protocol_version == PROTOCOL_VERSION_XL430) {
    // 1. Disable Torque (XL430)
    dxl_comm_result = packetHandlerXL430->write1ByteTxRx(portHandler, dxl_id, ADDR_XL430_TORQUE_ENABLE, TORQUE_DISABLE, &dxl_error);
    if (dxl_comm_result != COMM_SUCCESS || dxl_error != 0) {
      Serial.print("ID:"); Serial.print(dxl_id); Serial.print(" (XL430) Failed to disable torque. Result: "); Serial.print(dxl_comm_result); Serial.print(" Error: "); Serial.println(dxl_error);
      return false;
    }
    Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" (XL430) Torque disabled.");
    delay(50);

    // 2. Set Operating Mode (XL430)
    dxl_comm_result = packetHandlerXL430->write1ByteTxRx(portHandler, dxl_id, ADDR_XL430_OPERATING_MODE, operating_mode_xl430_or_dummy, &dxl_error);
    if (dxl_comm_result != COMM_SUCCESS || dxl_error != 0) {
      Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" (XL430) Failed to set operating mode.");
      return false;
    }
    Serial.print("ID:"); Serial.print(dxl_id); Serial.print(" (XL430) OpMode set to: "); Serial.println(operating_mode_xl430_or_dummy);
    delay(50);

    // 3. Enable Torque (XL430)
    dxl_comm_result = packetHandlerXL430->write1ByteTxRx(portHandler, dxl_id, ADDR_XL430_TORQUE_ENABLE, TORQUE_ENABLE, &dxl_error);
    if (dxl_comm_result != COMM_SUCCESS || dxl_error != 0) {
      Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" (XL430) Failed to enable torque.");
      return false;
    }
    Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" (XL430) Torque enabled.");

  } else if (protocol_version == PROTOCOL_VERSION_AX18A) {
    // 1. Disable Torque (AX18A)
    dxl_comm_result = packetHandlerAX18A->write1ByteTxRx(portHandler, dxl_id, ADDR_AX_TORQUE_ENABLE, TORQUE_DISABLE, &dxl_error);
    if (dxl_comm_result != COMM_SUCCESS || dxl_error != 0) {
      Serial.print("ID:"); Serial.print(dxl_id); Serial.print(" (AX18A) Failed to disable torque. Result: "); Serial.print(dxl_comm_result); Serial.print(" Error: "); Serial.println(dxl_error);
      return false;
    }
    Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" (AX18A) Torque disabled.");
    delay(50);

    // 2. Set Angle Limits (AX18A) for Joint Mode
    // CW Angle Limit
    dxl_comm_result = packetHandlerAX18A->write2ByteTxRx(portHandler, dxl_id, ADDR_AX_CW_ANGLE_LIMIT_L, PAN_SERVO_MIN_POS_RAW, &dxl_error);
    if (dxl_comm_result != COMM_SUCCESS || dxl_error != 0) {
      Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" (AX18A) Failed to set CW Angle Limit.");
      return false;
    }
    // CCW Angle Limit
    dxl_comm_result = packetHandlerAX18A->write2ByteTxRx(portHandler, dxl_id, ADDR_AX_CCW_ANGLE_LIMIT_L, PAN_SERVO_MAX_POS_RAW, &dxl_error);
    if (dxl_comm_result != COMM_SUCCESS || dxl_error != 0) {
      Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" (AX18A) Failed to set CCW Angle Limit.");
      return false;
    }
    Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" (AX18A) Joint mode ensured (Angle Limits set).");
    delay(50);

    // 3. Enable Torque (AX18A)
    dxl_comm_result = packetHandlerAX18A->write1ByteTxRx(portHandler, dxl_id, ADDR_AX_TORQUE_ENABLE, TORQUE_ENABLE, &dxl_error);
    if (dxl_comm_result != COMM_SUCCESS || dxl_error != 0) {
      Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" (AX18A) Failed to enable torque.");
      return false;
    }
    Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" (AX18A) Torque enabled.");

  } else {
    Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" Unsupported protocol version for init.");
    return false;
  }
  return true;
}

/**
 * @brief Sets the goal velocity for an XL430 servo in wheel mode.
 * Input is raw Dynamixel velocity units.
 */
bool set_wheel_velocity(uint8_t dxl_id, int32_t velocity_dxl_units) {
  // Clamp velocity
  velocity_dxl_units = constrain(velocity_dxl_units, -MAX_DXL_WHEEL_VELOCITY, MAX_DXL_WHEEL_VELOCITY);
  uint8_t dxl_error = 0;
  // Use packetHandlerXL430 specifically
  int dxl_comm_result = packetHandlerXL430->write4ByteTxRx(portHandler, dxl_id, ADDR_XL430_GOAL_VELOCITY, velocity_dxl_units, &dxl_error);
  if (dxl_comm_result != COMM_SUCCESS || dxl_error != 0) {
    // Serial.print("ID:"); Serial.print(dxl_id); Serial.println(" Failed to set goal velocity.");
    return false;
  }
  return true;
}

/**
 * @brief Sets the goal position for the AX-18A pan servo.
 * Input is raw Dynamixel position units.
 */
bool set_pan_position_raw(uint16_t position_raw, uint16_t speed_raw) {
  position_raw = constrain(position_raw, PAN_SERVO_MIN_POS_RAW, PAN_SERVO_MAX_POS_RAW);
  speed_raw = constrain(speed_raw, 0, 1023); // AX speed range
  uint8_t dxl_error = 0;
  int dxl_comm_result;

  // Set Moving Speed - Use packetHandlerAX18A specifically
  dxl_comm_result = packetHandlerAX18A->write2ByteTxRx(portHandler, DXL_ID_PAN_SERVO, ADDR_AX_MOVING_SPEED_L, speed_raw, &dxl_error);
  if (dxl_comm_result != COMM_SUCCESS || dxl_error != 0) {
    // Serial.print("ID:"); Serial.print(DXL_ID_PAN_SERVO); Serial.println(" Failed to set pan speed.");
    return false;
  }

  // Set Goal Position - Use packetHandlerAX18A specifically
  dxl_comm_result = packetHandlerAX18A->write2ByteTxRx(portHandler, DXL_ID_PAN_SERVO, ADDR_AX_GOAL_POSITION_L, position_raw, &dxl_error);
  if (dxl_comm_result != COMM_SUCCESS || dxl_error != 0) {
    // Serial.print("ID:"); Serial.print(DXL_ID_PAN_SERVO); Serial.println(" Failed to set pan position.");
    return false;
  }
  return true;
}

//================================================================================
//== Micro-ROS Subscriber Callbacks
//================================================================================

void left_wheel_vel_callback(const void *msgin) {
  const std_msgs__msg__Int32 *msg = (const std_msgs__msg__Int32 *)msgin;
  int32_t dxl_vel_left = msg->data; 
  set_wheel_velocity(DXL_ID_LEFT_WHEEL, dxl_vel_left);
}

void right_wheel_vel_callback(const void *msgin) {
  const std_msgs__msg__Int32 *msg = (const std_msgs__msg__Int32 *)msgin;
  int32_t dxl_vel_right = msg->data; 
  set_wheel_velocity(DXL_ID_RIGHT_WHEEL, dxl_vel_right);
}

void pan_angle_callback(const void *msgin) {
  const std_msgs__msg__Int32 *angle_msg = (const std_msgs__msg__Int32 *)msgin;
  uint16_t target_pos_raw = (uint16_t)angle_msg->data;
  set_pan_position_raw(target_pos_raw, PAN_SERVO_DEFAULT_SPEED_RAW);
}

//================================================================================
//== Arduino Setup
//================================================================================
void setup() {
  Serial.begin(115200); 
  // while(!Serial); 

  Serial.println("--- OpenCR Micro-ROS Dynamixel Controller (Dual Protocol) ---");

  portHandler = dynamixel::PortHandler::getPortHandler(DXL_DEVICENAME);
  packetHandlerXL430 = dynamixel::PacketHandler::getPacketHandler(PROTOCOL_VERSION_XL430);
  packetHandlerAX18A = dynamixel::PacketHandler::getPacketHandler(PROTOCOL_VERSION_AX18A);

  if (!portHandler->openPort()) {
    Serial.println("Failed to open DXL port. Halting.");
    while (1);
  }
  if (!portHandler->setBaudRate(DXL_BAUDRATE)) {
    Serial.println("Failed to set DXL baudrate. Halting.");
    while (1);
  }
  Serial.println("Dynamixel port opened and baudrate set.");
  delay(100);

  Serial.println("\nInitializing Left Wheel (XL430, Protocol 2.0)...");
  if (!init_dynamixel(DXL_ID_LEFT_WHEEL, PROTOCOL_VERSION_XL430, XL430_WHEEL_MODE)) {
    Serial.println("Failed to init Left Wheel. Check ID, connections, power, and protocol.");
  }

  Serial.println("\nInitializing Right Wheel (XL430, Protocol 2.0)...");
  if (!init_dynamixel(DXL_ID_RIGHT_WHEEL, PROTOCOL_VERSION_XL430, XL430_WHEEL_MODE)) {
    Serial.println("Failed to init Right Wheel. Check ID, connections, power, and protocol.");
  }

  Serial.println("\nInitializing Pan Servo (AX-18A, Protocol 1.0)...");
  if (!init_dynamixel(DXL_ID_PAN_SERVO, PROTOCOL_VERSION_AX18A, 0 /*dummy for AX init*/)) {
    Serial.println("Failed to init Pan Servo. Check ID, connections, power, and protocol.");
  } else {
    Serial.println("Pan Servo (AX-18A) initialized. Performing sweep test...");
    // Delays to allow servo to reach positions. Adjust if needed.
    // Full travel (e.g., min to max) might take ~2-3 seconds depending on speed.
    uint16_t sweep_full_travel_delay_ms = 2000; 
    uint16_t sweep_half_travel_delay_ms = 1500; 

    // 1. Move to "leftmost" (MIN_POS_RAW)
    Serial.print("Moving pan to MIN position (Leftmost): "); Serial.println(PAN_SERVO_MIN_POS_RAW);
    set_pan_position_raw(PAN_SERVO_MIN_POS_RAW, PAN_SERVO_DEFAULT_SPEED_RAW);
    delay(sweep_full_travel_delay_ms); // Allow time to reach from potential current position

    // 2. Move to "rightmost" (MAX_POS_RAW)
    Serial.print("Moving pan to MAX position (Rightmost): "); Serial.println(PAN_SERVO_MAX_POS_RAW);
    set_pan_position_raw(PAN_SERVO_MAX_POS_RAW, PAN_SERVO_DEFAULT_SPEED_RAW);
    delay(sweep_full_travel_delay_ms);

    // 3. Move to middle/neutral position
    uint16_t neutral_pos_raw = (PAN_SERVO_MAX_POS_RAW - PAN_SERVO_MIN_POS_RAW) / 2 + PAN_SERVO_MIN_POS_RAW;
    Serial.print("Moving pan to NEUTRAL position (Middle): "); Serial.println(neutral_pos_raw);
    set_pan_position_raw(neutral_pos_raw, PAN_SERVO_DEFAULT_SPEED_RAW);
    delay(sweep_half_travel_delay_ms); 

    Serial.println("Pan servo sweep test complete. Final position: Neutral.");
  }
  Serial.println("\nDynamixel setup complete.");

  Serial.println("Initializing micro-ROS...");
  set_microros_transports(); 

  allocator = rcl_get_default_allocator();
  rclc_support_init(&support, 0, NULL, &allocator);

  rclc_node_init_default(&node, "opencr_dynamixel_dual_protocol_node", "", &support);

  rclc_subscription_init_default(
    &left_wheel_vel_subscriber,
    &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
    "left_wheel_vel");

  rclc_subscription_init_default(
    &right_wheel_vel_subscriber,
    &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
    "right_wheel_vel");

  rclc_subscription_init_default(
    &pan_angle_subscriber,
    &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
    "pan_angle");

  rclc_executor_init(&executor, &support.context, 3, &allocator);
  rclc_executor_add_subscription(&executor, &left_wheel_vel_subscriber, &left_wheel_vel_msg, &left_wheel_vel_callback, ON_NEW_DATA);
  rclc_executor_add_subscription(&executor, &right_wheel_vel_subscriber, &right_wheel_vel_msg, &right_wheel_vel_callback, ON_NEW_DATA);
  rclc_executor_add_subscription(&executor, &pan_angle_subscriber, &pan_angle_msg, &pan_angle_callback, ON_NEW_DATA);

  Serial.println("Micro-ROS setup complete. Waiting for agent...");

  while (RMW_RET_OK != rmw_uros_ping_agent(100, 1)) { 
    Serial.print(".");
    delay(100);
  }
  Serial.println("\nMicro-ROS agent connected!");
}

//================================================================================
//== Arduino Loop
//================================================================================
void loop() {
  rclc_executor_spin_some(&executor, RCL_MS_TO_NS(10));
  delay(5); 
}