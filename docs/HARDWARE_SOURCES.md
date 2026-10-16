# Hardware and integration evidence

Read on 2026-10-16 from the user's AVL bookmarks in Brave. Only links relevant to hardware/software were used; no complete browser history/bookmark export is included.

- [AVROS README](https://github.com/Paarseus/IGVC_ROS2): Jetson Orin, JetPack 6, ZED X GMSL2 through ZED Link Quad; ROS 2 Jazzy/Humble described.
- [Perception node](https://github.com/Paarseus/IGVC_ROS2/blob/a898e4bf107dae0fc9917f3733967ecf109b7dae/src/avros_perception/avros_perception/perception_node.py): current defaults `/zed_{cam}/zed_node/rgb/color/rect/image` (wrapper v5 convention).
- [Perception configuration](https://github.com/Paarseus/IGVC_ROS2/blob/a898e4bf107dae0fc9917f3733967ecf109b7dae/src/avros_perception/config/perception.yaml): historical 2026-05-30 comments describe fixed brightness thresholds flickering with ZED auto-exposure, and an adaptive alternative. This is a documented prior observation, not proof that every flicker in these recordings has that cause.
- [AVL-IGVC2026](https://github.com/Paarseus/AVL-IGVC2026) and [CARLA/Nav2 AVL](https://github.com/arassal/carla-nav2-avl) provide broader project context.
- [OpenCV VideoCapture](https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html): camera/video input API. Backend buffering behavior varies; setting buffersize is a request, not an acquisition-latency guarantee.

The robot was not connected. OS version, installed ROS distribution, live topic names, camera exposure settings and three-camera performance remain to be measured. No modifications were made to the existing AVROS repositories or robot sensor/steering configuration.
