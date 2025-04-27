#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "opencv2/opencv.hpp"

class WebcamSubscriber : public rclcpp::Node
{
public:
  WebcamSubscriber()
  : Node("camera_subscriber")
  {
    subscription_ = this->create_subscription<sensor_msgs::msg::Image>(
        "camera_feed", 10,
        std::bind(&WebcamSubscriber::topic_callback, this, std::placeholders::_1)
    );
  }

private:
  void topic_callback(const sensor_msgs::msg::Image::SharedPtr msg)
  {
    // Reconstruct cv::Mat from ROS2 Image message
    cv::Mat frame(msg->height, msg->width, CV_8UC3, const_cast<unsigned char*>(msg->data.data()), msg->step);

    // Show the frame
    cv::imshow("Received Webcam Stream", frame);
    cv::waitKey(1);  // Needed to refresh the imshow window
  }

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr subscription_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<WebcamSubscriber>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
