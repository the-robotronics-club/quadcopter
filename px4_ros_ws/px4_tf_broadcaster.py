import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from px4_msgs.msg import VehicleOdometry
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
import numpy as np

class PX4TFBroadcaster(Node):
    def __init__(self):
        super().__init__('px4_tf_broadcaster')

        # PX4 uses Best Effort QoS for high-frequency telemetry
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        self.subscription = self.create_subscription(
            VehicleOdometry,
            '/fmu/out/vehicle_odometry',
            self.odometry_callback,
            qos_profile
        )

        self.tf_broadcaster = TransformBroadcaster(self)
        self.get_logger().info("PX4 Odometry to TF Broadcaster Initialized (NED -> ENU).")

    def odometry_callback(self, msg):
        t = TransformStamped()

        # Sync timestamp with ROS /clock
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'

        # Position Conversion: PX4 NED to ROS ENU
        # North (NED X) -> ROS Y
        # East  (NED Y) -> ROS X
        # Down  (NED Z) -> ROS -Z (Up)
        t.transform.translation.x = float(msg.position[1])
        t.transform.translation.y = float(msg.position[0])
        t.transform.translation.z = float(-msg.position[2])

        # Orientation Conversion: PX4 Hamiltonian Quaternion (w, x, y, z) in NED to ENU
        # q_enu = [w, y, x, -z] roughly for standard NED->ENU coordinate rotation
        w = msg.q[0]
        x = msg.q[1]
        y = msg.q[2]
        z = msg.q[3]

        # Convert NED quaternion to ENU/FLU
        t.transform.rotation.w = float(w)
        t.transform.rotation.x = float(y)
        t.transform.rotation.y = float(x)
        t.transform.rotation.z = float(-z)

        self.tf_broadcaster.sendTransform(t)

def main(args=None):
    rclpy.init(args=args)
    node = PX4TFBroadcaster()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

