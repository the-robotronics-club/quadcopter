import rclpy
from rclpy.node import Node
from px4_msgs.msg import VehicleOdometry
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped

class OdomTranslator(Node):
    def __init__(self):
        super().__init__('odom_translator')
        from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        self.subscription = self.create_subscription(
            VehicleOdometry,
            '/fmu/out/vehicle_odometry',
            self.listener_callback,
            qos_profile)
        
        self.publisher = self.create_publisher(Odometry, '/odom', 10)
        self.tf_broadcaster = TransformBroadcaster(self)

    def listener_callback(self, msg):
        odom_msg = Odometry()
        odom_msg.header.stamp = self.get_clock().now().to_msg()
        odom_msg.header.frame_id = 'odom'
        odom_msg.child_frame_id = 'base_link'
        
        # Explicitly cast numpy.float32 to native Python float to satisfy C bindings
        odom_msg.pose.pose.position.x = float(msg.position[1])
        odom_msg.pose.pose.position.y = float(msg.position[0])
        odom_msg.pose.pose.position.z = float(-msg.position[2])
        
        odom_msg.pose.pose.orientation.x = float(msg.q[1])
        odom_msg.pose.pose.orientation.y = float(msg.q[0])
        odom_msg.pose.pose.orientation.z = float(-msg.q[2])
        odom_msg.pose.pose.orientation.w = float(msg.q[3])
        
        self.publisher.publish(odom_msg)

        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        
        t.transform.translation.x = float(msg.position[1])
        t.transform.translation.y = float(msg.position[0])
        t.transform.translation.z = float(-msg.position[2])
        
        t.transform.rotation.x = float(msg.q[1])
        t.transform.rotation.y = float(msg.q[0])
        t.transform.rotation.z = float(-msg.q[2])
        t.transform.rotation.w = float(msg.q[3])
        
        self.tf_broadcaster.sendTransform(t)

def main(args=None):
    rclpy.init(args=args)
    node = OdomTranslator()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
