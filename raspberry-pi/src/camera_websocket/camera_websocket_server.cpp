#include <libwebsockets.h>
#include <opencv2/opencv.hpp>
#include <vector>

static struct lws *client_wsi = nullptr;

static int callback_camera(struct lws *wsi, enum lws_callback_reasons reason,
                           void *user, void *in, size_t len) {
    static std::vector<uchar> jpeg_buf;
    static cv::VideoCapture cap;

    switch (reason) {
        case LWS_CALLBACK_ESTABLISHED:
            client_wsi = wsi;
            if (!cap.isOpened()) {
                cap.open(0);
                cap.set(cv::CAP_PROP_FRAME_WIDTH, 640);
                cap.set(cv::CAP_PROP_FRAME_HEIGHT, 480);
                if (!cap.isOpened()) {
                    fprintf(stderr, "Camera failed to open.\n");
                    return -1;
                }
            }
            break;

        case LWS_CALLBACK_SERVER_WRITEABLE:
            if (cap.isOpened()) {
                cv::Mat frame;
                cap >> frame;

                if (!frame.empty()) {
                    jpeg_buf.clear();
                    std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, 70};
                    cv::imencode(".jpg", frame, jpeg_buf, params);

                    unsigned char *buf = new unsigned char[LWS_PRE + jpeg_buf.size()];
                    memcpy(&buf[LWS_PRE], jpeg_buf.data(), jpeg_buf.size());
                    lws_write(wsi, &buf[LWS_PRE], jpeg_buf.size(), LWS_WRITE_BINARY);
                    delete[] buf;
                }
            }

            lws_callback_on_writable(wsi);
            break;

        default:
            break;
    }

    return 0;
}

static struct lws_protocols protocols[] = {
    { "cam-protocol", callback_camera, 0, 1024 * 1024 },
    { NULL, NULL, 0, 0 }
};

int main() {
    struct lws_context_creation_info info = {};
    info.port = 9002;
    info.protocols = protocols;
    info.options = LWS_SERVER_OPTION_DO_SSL_GLOBAL_INIT;

    struct lws_context *context = lws_create_context(&info);
    if (!context) {
        fprintf(stderr, "lws init failed\n");
        return -1;
    }

    printf("WebSocket server running at ws://vlg2.local:9002\n");
    while (true)
        lws_service(context, 1000);

    lws_context_destroy(context);
    return 0;
}
