import asyncio
import cv2
import numpy as np
import websockets

class WSVideoClient:
    def __init__(self, uri, name="Stream"):
        self.uri = uri
        self.name = name
        self.running = True

    async def _run_stream(self):
        async with websockets.connect(self.uri, max_size=None) as websocket:
            print(f"[{self.name}] Connected to {self.uri}")
            while self.running:
                try:
                    data = await websocket.recv()
                    np_arr = np.frombuffer(data, np.uint8)
                    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if img is not None:
                        cv2.imshow(self.name, img)
                        if cv2.waitKey(1) == 27:  # ESC key
                            self.running = False
                            break
                except websockets.ConnectionClosed:
                    print(f"[{self.name}] Connection closed.")
                    break

        cv2.destroyWindow(self.name)

    def start(self):
        asyncio.run(self._run_stream())

if __name__ == "__main__":
    client = WSVideoClient("ws://vlg2.local:9002", name="Raspberry Pi Cam")
    client.start()
